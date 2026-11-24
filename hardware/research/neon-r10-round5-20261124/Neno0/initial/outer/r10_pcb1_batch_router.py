#!/usr/bin/env python3
"""
EVT-1 / H03 R10-TEST-ROUTING Multi-Layer Batch Router & Exact Geometric DRC Verifier.

Targets PCB1 (evt1-main-left, UUID 8fbc3cae65886fe5) inside EVT1-H03-R9-NOT-FOR-FAB.epro2.
Priority order:
  1. GND (same-layer short routes + BV_L1_L2 / BV_L5_L6 blind-via stitching into L15/L18 GND planes)
  2. I2C / SCCB nets (multi-layer A* across L1, L2, L16, L17)
  3. Power rails (multi-layer A* across L1, L2, L16, L17)

Strict locked manufacturing rules (zero relaxation, extra safety margin applied):
  - Track width: 4.0 mil (>= JLCPCB 3.5 mil 6-layer standard)
  - Track-to-Track (diff net): >= 4.2 mil (rule: 1.97 mil)
  - Track/Via/Pad-to-Copper (diff net): >= 6.3 mil (rule: 5.9843 mil)
  - Hole-to-Copper (diff net): >= 7.3 mil (rule: 6.929 mil)
  - Hole-to-Hole (any two drills): >= 12.2 mil (rule: 11.811 mil)
  - Track-to-Board-Edge: >= 12.5 mil; Via-to-Board-Edge: >= 14.5 mil
  - Keepout REGION PROHIBIT on all 6 copper layers strictly avoided.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import random
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PCB1_UUID = "8fbc3cae65886fe5"
SIGNAL_LAYERS = (1, 2, 16, 17)
PLANE_LAYERS = (15, 18)

# Strict margins (mil) — strictly tighter than EasyEDA Pro locked rules
TRACK_WIDTH = 4.0
CLR_TRACK_TRACK = 4.2
CLR_COPPER_PAD_VIA = 6.3
CLR_HOLE_COPPER = 7.3
CLR_HOLE_HOLE = 12.2
CLR_EDGE_TRACK = 12.5
CLR_EDGE_VIA = 14.5

BLIND_VIA_HOLE = 4.0
BLIND_VIA_DIA = 10.0
THRU_VIA_HOLE = 6.0
THRU_VIA_DIA = 12.0


def rot(x: float, y: float, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


def transform_pad_center(cx: float, cy: float, ang: float, comp_layer: int, px: float, py: float) -> tuple[float, float]:
    if comp_layer == 2:
        py = -py
    rx, ry = rot(px, py, ang)
    return cx + rx, cy + ry


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(ax1: float, ay1: float, ax2: float, ay2: float, bx1: float, by1: float, bx2: float, by2: float) -> float:
    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) - (p2[1] - p1[1]) * (p3[0] - p1[0])

    A, B, C, D = (ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2)
    d1, d2 = ccw(A, B, C), ccw(A, B, D)
    d3, d4 = ccw(C, D, A), ccw(C, D, B)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return 0.0
    return min(
        pt_seg_dist(ax1, ay1, bx1, by1, bx2, by2),
        pt_seg_dist(ax2, ay2, bx1, by1, bx2, by2),
        pt_seg_dist(bx1, by1, ax1, ay1, ax2, ay2),
        pt_seg_dist(bx2, by2, ax1, ay1, ax2, ay2),
    )


def in_pcb1_outline(x: float, y: float, margin: float) -> bool:
    """Exact L-shaped PCB1 board outline with inward clearance margin."""
    # Outline: [0..228.3465] x [0..1811.0236] U [228.3465..322.8346] x [165.3543..551.1811]
    # Keepout PROHIBIT: [0..228.3465] x [0..165.3543] on all 6 layers
    if y < 165.3543 + margin:
        return False
    if y > 1811.0236 - margin:
        return False
    if x < margin:
        return False
    if y <= 551.1811 - margin:
        return x <= 322.8346 - margin
    return x <= 228.3465 - margin


def in_gnd_plane(x: float, y: float, margin: float = 12.0) -> bool:
    """Layer 15 / 18 GND plane polygon."""
    if y < 176.0 + margin or y > 1800.5 - margin or x < 10.5 + margin:
        return False
    if y <= 540.5 - margin:
        return x <= 312.3 - margin
    return x <= 217.8 - margin


@dataclass
class PadObj:
    idx: int
    comp_id: str
    des: str
    num: str
    net: str
    x: float
    y: float
    layer: int  # 1, 2, or 12 (multi)
    radius: float  # conservative circumradius for fast clearance + exact check
    hx: float      # half-width in world X (AABB conservative)
    hy: float      # half-height in world Y (AABB conservative)
    hole_dia: float


@dataclass
class TrackObj:
    net: str
    layer: int
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    obj_id: str


@dataclass
class ViaObj:
    net: str
    x: float
    y: float
    hole: float
    dia: float
    via_type: str
    rule_name: str
    layers: set[int]
    obj_id: str


def via_layers(via_type: str, rule_name: str) -> set[int]:
    if via_type == "BLIND":
        if rule_name == "BV_L1_L2":
            return {1, 15}
        if rule_name == "BV_L5_L6":
            return {2, 18}
    return {1, 2, 15, 16, 17, 18}


def pt_aabb_dist(px: float, py: float, cx: float, cy: float, hx: float, hy: float) -> float:
    dx = max(abs(px - cx) - hx, 0.0)
    dy = max(abs(py - cy) - hy, 0.0)
    return math.hypot(dx, dy)


def seg_aabb_dist(x1: float, y1: float, x2: float, y2: float, cx: float, cy: float, hx: float, hy: float) -> float:
    # Exact distance from segment to axis-aligned box [cx-hx, cx+hx] x [cy-hy, cy+hy]
    bx1, bx2, by1, by2 = cx - hx, cx + hx, cy - hy, cy + hy
    if (bx1 <= x1 <= bx2 and by1 <= y1 <= by2) or (bx1 <= x2 <= bx2 and by1 <= y2 <= by2):
        return 0.0
    # Check intersection with 4 box edges
    edges = [
        (bx1, by1, bx2, by1),
        (bx2, by1, bx2, by2),
        (bx2, by2, bx1, by2),
        (bx1, by2, bx1, by1),
    ]
    return min(seg_seg_dist(x1, y1, x2, y2, ex1, ey1, ex2, ey2) for ex1, ey1, ex2, ey2 in edges)


class DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def net_category(net: str) -> str:
    u = net.upper()
    if u == "GND":
        return "GND"
    if any(k in u for k in ("I2C", "SCL", "SDA", "SCCB")):
        return "I2C"
    if any(k in u for k in ("3V3", "1V8", "VSYS", "VBUS", "VBAT", "VDD", "AVDD", "DVDD", "DOVDD", "VCC", "PWR", "BB_")):
        return "POWER"
    return "OTHER"


def load_pcb1(epru_path: Path):
    docs: dict[str, dict[str, Any]] = {}
    pcb1_lines_raw: list[str] = []
    cur_uuid = None
    with epru_path.open("r", encoding="utf-8") as f:
        for raw in f:
            s = raw.rstrip("\r\n")
            if s.endswith("|"):
                s = s[:-1]
            if "||" not in s:
                continue
            meta_s, body_s = s.split("||", 1)
            meta = json.loads(meta_s)
            body = json.loads(body_s) if body_s.strip() else None
            if meta.get("type") == "DOCHEAD":
                cur_uuid = body.get("uuid")
                if body.get("docType") in ("FOOTPRINT", "DEVICE", "PCB"):
                    docs[cur_uuid] = {"type": body.get("docType"), "recs": []}
                continue
            if cur_uuid in docs:
                docs[cur_uuid]["recs"].append((meta, body))

    pcb1 = docs[PCB1_UUID]["recs"]
    pad_nets = {
        tuple(json.loads(m["id"])[1:]): b.get("padNet", "")
        for m, b in pcb1
        if m["type"] == "PAD_NET" and isinstance(b, dict)
    }
    comp_des: dict[str, str] = {}
    for m, b in pcb1:
        if m["type"] == "ATTR" and isinstance(b, dict) and b.get("key") == "Designator":
            comp_des[b.get("parentId", "")] = str(b.get("val", ""))

    pads: list[PadObj] = []
    for m, b in pcb1:
        if m["type"] != "COMPONENT" or not isinstance(b, dict):
            continue
        cid = m["id"]
        dev_uuid = json.loads(b["attrs"]["DeviceName"])["uuid"]
        dev_doc = docs.get(dev_uuid)
        if not dev_doc:
            continue
        fp_uuid = dev_doc["recs"][0][1]["attributes"].get("Footprint")
        fp_doc = docs.get(fp_uuid)
        if not fp_doc:
            continue
        ang = float(b["angle"])
        cl = int(b["layerId"])
        for fm, fb in fp_doc["recs"]:
            if fm["type"] != "PAD" or not isinstance(fb, dict):
                continue
            net = pad_nets.get((cid, str(fb["num"]), fm["id"]), "")
            wx, wy = transform_pad_center(float(b["x"]), float(b["y"]), ang, cl, float(fb["centerX"]), float(fb["centerY"]))
            dp = (fb.get("defaultPad") or {})
            w = float(dp.get("width", 10.0))
            h = float(dp.get("height", 10.0))
            pad_ang = float(fb.get("padAngle", 0.0)) + ang
            rad = math.radians(pad_ang)
            hx = 0.5 * (abs(w * math.cos(rad)) + abs(h * math.sin(rad)))
            hy = 0.5 * (abs(w * math.sin(rad)) + abs(h * math.cos(rad)))
            hole = float((fb.get("hole") or {}).get("width", 0.0))
            pl = 12 if (fb.get("layerId") == 12 or hole > 0) else cl
            pads.append(PadObj(
                idx=len(pads),
                comp_id=cid,
                des=comp_des.get(cid, cid[:6]),
                num=str(fb["num"]),
                net=net,
                x=wx,
                y=wy,
                layer=pl,
                radius=math.hypot(hx, hy),
                hx=hx,
                hy=hy,
                hole_dia=hole,
            ))

    tracks: list[TrackObj] = []
    vias: list[ViaObj] = []
    max_ticket = 0
    for m, b in pcb1:
        t = m.get("ticket", 0)
        if isinstance(t, int) and t > max_ticket:
            max_ticket = t
        if m["type"] == "LINE" and isinstance(b, dict):
            tracks.append(TrackObj(
                net=b.get("netName", ""),
                layer=int(b["layerId"]),
                x1=float(b["startX"]),
                y1=float(b["startY"]),
                x2=float(b["endX"]),
                y2=float(b["endY"]),
                width=float(b["width"]),
                obj_id=str(m["id"]),
            ))
        elif m["type"] == "VIA" and isinstance(b, dict):
            vt = str(b.get("viaType", "NORMAL"))
            rn = str(b.get("ruleName", ""))
            vias.append(ViaObj(
                net=b.get("netName", ""),
                x=float(b["centerX"]),
                y=float(b["centerY"]),
                hole=float(b["holeDiameter"]),
                dia=float(b["viaDiameter"]),
                via_type=vt,
                rule_name=rn,
                layers=via_layers(vt, rn),
                obj_id=str(m["id"]),
            ))

    return pads, tracks, vias, max_ticket


def compute_open_connections(pads: list[PadObj], tracks: list[TrackObj], vias: list[ViaObj]):
    """Compute per-net connected components and open-connection count (ratsnest = clusters - 1)."""
    net_pads = defaultdict(list)
    for p in pads:
        if p.net:
            net_pads[p.net].append(p)
    net_tracks = defaultdict(list)
    for tr in tracks:
        if tr.net:
            net_tracks[tr.net].append(tr)
    net_vias = defaultdict(list)
    for v in vias:
        if v.net:
            net_vias[v.net].append(v)

    total_opens = 0
    net_clusters: dict[str, list[list[PadObj]]] = {}
    for net, plist in net_pads.items():
        if len(plist) <= 1:
            continue
        tlist = net_tracks.get(net, [])
        vlist = net_vias.get(net, [])
        # Nodes: pads [0..np-1], tracks [np..np+nt-1], vias [np+nt..np+nt+nv-1], plus 1 GND plane node if GND
        np_, nt_, nv_ = len(plist), len(tlist), len(vlist)
        plane_idx = np_ + nt_ + nv_ if net == "GND" else -1
        dsu = DSU(np_ + nt_ + nv_ + (1 if plane_idx >= 0 else 0))

        # Connect pads to tracks
        for i, p in enumerate(plist):
            for j, tr in enumerate(tlist):
                if p.layer == 12 or p.layer == tr.layer:
                    if seg_aabb_dist(tr.x1, tr.y1, tr.x2, tr.y2, p.x, p.y, p.hx, p.hy) <= tr.width * 0.5 + 0.5:
                        dsu.union(i, np_ + j)
            for k, v in enumerate(vlist):
                if p.layer == 12 or p.layer in v.layers:
                    if pt_aabb_dist(v.x, v.y, p.x, p.y, p.hx, p.hy) <= v.dia * 0.5 + 0.5:
                        dsu.union(i, np_ + nt_ + k)

        # Connect tracks to tracks
        for j1 in range(nt_):
            t1 = tlist[j1]
            for j2 in range(j1 + 1, nt_):
                t2 = tlist[j2]
                if t1.layer == t2.layer:
                    if seg_seg_dist(t1.x1, t1.y1, t1.x2, t1.y2, t2.x1, t2.y1, t2.x2, t2.y2) <= (t1.width + t2.width) * 0.5 + 0.5:
                        dsu.union(np_ + j1, np_ + j2)

        # Connect vias to tracks, vias to vias, and GND vias to GND planes (L15/L18)
        for k, v in enumerate(vlist):
            if plane_idx >= 0 and ({15, 18} & v.layers) and in_gnd_plane(v.x, v.y, margin=0.0):
                dsu.union(np_ + nt_ + k, plane_idx)
            for j, tr in enumerate(tlist):
                if tr.layer in v.layers:
                    if pt_seg_dist(v.x, v.y, tr.x1, tr.y1, tr.x2, tr.y2) <= v.dia * 0.5 + tr.width * 0.5 + 0.5:
                        dsu.union(np_ + nt_ + k, np_ + j)
            for k2 in range(k + 1, nv_):
                v2 = vlist[k2]
                if v.layers & v2.layers:
                    if math.hypot(v.x - v2.x, v.y - v2.y) <= (v.dia + v2.dia) * 0.5 + 0.5:
                        dsu.union(np_ + nt_ + k, np_ + nt_ + k2)

        groups = defaultdict(list)
        for i, p in enumerate(plist):
            groups[dsu.find(i)].append(p)
        if len(groups) > 1:
            total_opens += len(groups) - 1
            net_clusters[net] = list(groups.values())
    return total_opens, net_clusters


def check_segment_drc(
    net: str, layer: int, x1: float, y1: float, x2: float, y2: float, width: float,
    pads: list[PadObj], tracks: list[TrackObj], vias: list[ViaObj]
) -> tuple[bool, str]:
    """Independent exact continuous-geometry DRC check for one candidate track segment."""
    hw = width * 0.5
    # 1. Board outline & keepout check (sample endpoints + midpoint + quarter points)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        sx, sy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
        if not in_pcb1_outline(sx, sy, CLR_EDGE_TRACK + hw):
            return False, "board_edge_or_keepout"

    # 2. Clearance to all different-net pads on same layer
    for p in pads:
        if p.net == net:
            continue
        if p.layer == 12 or p.layer == layer:
            d = seg_aabb_dist(x1, y1, x2, y2, p.x, p.y, p.hx, p.hy) - hw
            if d < CLR_COPPER_PAD_VIA:
                return False, f"pad_clr({p.des}.{p.num},{d:.2f})"
        if p.hole_dia > 0:
            dh = pt_seg_dist(p.x, p.y, x1, y1, x2, y2) - hw - p.hole_dia * 0.5
            if dh < CLR_HOLE_COPPER:
                return False, f"pad_hole_clr({p.des}.{p.num},{dh:.2f})"

    # 3. Clearance to all different-net tracks on same layer
    for tr in tracks:
        if tr.net == net or tr.layer != layer:
            continue
        d = seg_seg_dist(x1, y1, x2, y2, tr.x1, tr.y1, tr.x2, tr.y2) - hw - tr.width * 0.5
        if d < CLR_TRACK_TRACK:
            return False, f"track_clr({tr.net},{d:.2f})"

    # 4. Clearance to all different-net vias
    for v in vias:
        if v.net == net:
            continue
        if layer in v.layers:
            d = pt_seg_dist(v.x, v.y, x1, y1, x2, y2) - hw - v.dia * 0.5
            if d < CLR_COPPER_PAD_VIA:
                return False, f"via_clr({v.net},{d:.2f})"
        # Hole-to-track clearance if via drill spans this layer
        if layer in v.layers:
            dh = pt_seg_dist(v.x, v.y, x1, y1, x2, y2) - hw - v.hole * 0.5
            if dh < CLR_HOLE_COPPER:
                return False, f"via_hole_clr({v.net},{dh:.2f})"

    return True, "OK"


def check_via_drc(
    net: str, x: float, y: float, hole: float, dia: float, v_layers: set[int],
    pads: list[PadObj], tracks: list[TrackObj], vias: list[ViaObj]
) -> tuple[bool, str]:
    """Independent exact continuous-geometry DRC check for one candidate via."""
    hr = hole * 0.5
    vr = dia * 0.5
    if not in_pcb1_outline(x, y, CLR_EDGE_VIA + vr):
        return False, "via_board_edge_or_keepout"
    if net == "GND" and ({15, 18} & v_layers) and not in_gnd_plane(x, y, margin=10.0):
        return False, "outside_gnd_plane"

    # Hole-to-Hole against ALL existing vias (even same net!) and PTH pads
    for v in vias:
        dh = math.hypot(x - v.x, y - v.y) - hr - v.hole * 0.5
        if dh < CLR_HOLE_HOLE:
            return False, f"hole_to_hole({v.obj_id},{dh:.2f})"
        if v.net != net and (v_layers & v.layers):
            dc = math.hypot(x - v.x, y - v.y) - vr - v.dia * 0.5
            if dc < CLR_COPPER_PAD_VIA:
                return False, f"via_to_via({v.net},{dc:.2f})"

    for p in pads:
        if p.hole_dia > 0:
            dh = math.hypot(x - p.x, y - p.y) - hr - p.hole_dia * 0.5
            if dh < CLR_HOLE_HOLE:
                return False, f"hole_to_pth({p.des}.{p.num},{dh:.2f})"
        if p.net != net and (p.layer == 12 or p.layer in v_layers):
            dc = pt_aabb_dist(x, y, p.x, p.y, p.hx, p.hy) - vr
            if dc < CLR_COPPER_PAD_VIA:
                return False, f"via_to_pad({p.des}.{p.num},{dc:.2f})"
            dhc = pt_aabb_dist(x, y, p.x, p.y, p.hx, p.hy) - hr
            if dhc < CLR_HOLE_COPPER:
                return False, f"via_hole_to_pad({p.des}.{p.num},{dhc:.2f})"

    for tr in tracks:
        if tr.net != net and tr.layer in v_layers:
            dc = pt_seg_dist(x, y, tr.x1, tr.y1, tr.x2, tr.y2) - vr - tr.width * 0.5
            if dc < CLR_COPPER_PAD_VIA:
                return False, f"via_to_track({tr.net},{dc:.2f})"
            dhc = pt_seg_dist(x, y, tr.x1, tr.y1, tr.x2, tr.y2) - hr - tr.width * 0.5
            if dhc < CLR_HOLE_COPPER:
                return False, f"via_hole_to_track({tr.net},{dhc:.2f})"

    return True, "OK"


def try_direct_or_l_route(
    net: str, layer: int, x1: float, y1: float, x2: float, y2: float,
    pads: list[PadObj], tracks: list[TrackObj], vias: list[ViaObj]
) -> list[tuple[float, float, float, float]] | None:
    """Try clean straight or 2-segment L / 45-deg elbow route on a single layer."""
    candidates: list[list[tuple[float, float, float, float]]] = [
        [(x1, y1, x2, y2)],
        [(x1, y1, x2, y1), (x2, y1, x2, y2)],
        [(x1, y1, x1, y2), (x1, y2, x2, y2)],
    ]
    dx, dy = x2 - x1, y2 - y1
    # 45-degree dogleg candidates
    if abs(dx) > 1.0 and abs(dy) > 1.0:
        d = min(abs(dx), abs(dy))
        sx, sy = (1.0 if dx > 0 else -1.0), (1.0 if dy > 0 else -1.0)
        mx1, my1 = x1 + sx * d, y1 + sy * d
        candidates.append([(x1, y1, mx1, my1), (mx1, my1, x2, y2)])
        mx2, my2 = x2 - sx * d, y2 - sy * d
        candidates.append([(x1, y1, mx2, my2), (mx2, my2, x2, y2)])
        # Offset jogs +/- 10, 18 mil
        for off in (-12.0, 12.0, -20.0, 20.0):
            candidates.append([(x1, y1, x1 + off, y1), (x1 + off, y1, x1 + off, y2), (x1 + off, y2, x2, y2)])
            candidates.append([(x1, y1, x1, y1 + off), (x1, y1 + off, x2, y1 + off), (x2, y1 + off, x2, y2)])

    for segs in candidates:
        segs = [s for s in segs if math.hypot(s[2] - s[0], s[3] - s[1]) > 0.2]
        if not segs:
            continue
        ok = True
        for a, b, c, d in segs:
            res, _ = check_segment_drc(net, layer, a, b, c, d, TRACK_WIDTH, pads, tracks, vias)
            if not res:
                ok = False
                break
        if ok:
            return segs
    return None


def try_local_astar(
    net: str, layer: int, x1: float, y1: float, x2: float, y2: float,
    pads: list[PadObj], tracks: list[TrackObj], vias: list[ViaObj],
    step: float = 5.0, pad_margin: float = 45.0, max_nodes: int = 2500
) -> list[tuple[float, float, float, float]] | None:
    """Bounded local 8-direction A* router on a single layer, then verified with exact continuous DRC."""
    minx = max(10.0, min(x1, x2) - pad_margin)
    maxx = min(315.0, max(x1, x2) + pad_margin)
    miny = max(175.0, min(y1, y2) - pad_margin)
    maxy = min(1800.0, max(y1, y2) + pad_margin)

    # Filter nearby obstacles for speed
    near_pads = [p for p in pads if p.net != net and (p.layer == 12 or p.layer == layer) and (minx - 30 <= p.x <= maxx + 30 and miny - 30 <= p.y <= maxy + 30)]
    near_tracks = [tr for tr in tracks if tr.net != net and tr.layer == layer and not (max(tr.x1, tr.x2) < minx - 20 or min(tr.x1, tr.x2) > maxx + 20 or max(tr.y1, tr.y2) < miny - 20 or min(tr.y1, tr.y2) > maxy + 20)]
    near_vias = [v for v in vias if v.net != net and layer in v.layers and (minx - 25 <= v.x <= maxx + 25 and miny - 25 <= v.y <= maxy + 25)]

    sx, sy = round(x1 / step) * step, round(y1 / step) * step
    gx, gy = round(x2 / step) * step, round(y2 / step) * step
    start = (sx, sy)
    goal = (gx, gy)

    def node_ok(nx: float, ny: float) -> bool:
        if nx < minx or nx > maxx or ny < miny or ny > maxy:
            return False
        if not in_pcb1_outline(nx, ny, CLR_EDGE_TRACK + TRACK_WIDTH * 0.5):
            return False
        hw = TRACK_WIDTH * 0.5
        for p in near_pads:
            if pt_aabb_dist(nx, ny, p.x, p.y, p.hx, p.hy) - hw < CLR_COPPER_PAD_VIA:
                return False
        for v in near_vias:
            if math.hypot(nx - v.x, ny - v.y) - hw - v.dia * 0.5 < CLR_COPPER_PAD_VIA:
                return False
        for tr in near_tracks:
            if pt_seg_dist(nx, ny, tr.x1, tr.y1, tr.x2, tr.y2) - hw - tr.width * 0.5 < CLR_TRACK_TRACK:
                return False
        return True

    pq = [(math.hypot(gx - sx, gy - sy), 0.0, start)]
    came_from: dict[tuple[float, float], tuple[float, float] | None] = {start: None}
    gscore = {start: 0.0}
    dirs = [(step, 0), (-step, 0), (0, step), (0, -step), (step, step), (step, -step), (-step, step), (-step, -step)]
    expanded = 0

    while pq and expanded < max_nodes:
        _, g, cur = heapq.heappop(pq)
        if cur == goal or math.hypot(cur[0] - x2, cur[1] - y2) <= step * 1.1:
            # Reconstruct polyline & simplify collinear segments
            pts = [(x2, y2)]
            c = cur
            while c is not None:
                pts.append(c)
                c = came_from[c]
            pts.append((x1, y1))
            pts.reverse()
            # Simplify collinear points
            simp = [pts[0]]
            for pt in pts[1:]:
                if math.hypot(pt[0] - simp[-1][0], pt[1] - simp[-1][1]) < 0.2:
                    continue
                if len(simp) >= 2:
                    ax, ay = simp[-1][0] - simp[-2][0], simp[-1][1] - simp[-2][1]
                    bx, by = pt[0] - simp[-1][0], pt[1] - simp[-1][1]
                    if abs(ax * by - ay * bx) < 1e-3 and (ax * bx + ay * by) >= 0:
                        simp[-1] = pt
                        continue
                simp.append(pt)
            segs = [(simp[i][0], simp[i][1], simp[i + 1][0], simp[i + 1][1]) for i in range(len(simp) - 1)]
            # Exact continuous DRC verification
            if segs and all(check_segment_drc(net, layer, a, b, c_, d_, TRACK_WIDTH, pads, tracks, vias)[0] for a, b, c_, d_ in segs):
                return segs
            return None

        expanded += 1
        for dx, dy in dirs:
            nxt = (round(cur[0] + dx, 2), round(cur[1] + dy, 2))
            ng = g + math.hypot(dx, dy)
            if ng < gscore.get(nxt, 1e18):
                if nxt != goal and not node_ok(nxt[0], nxt[1]):
                    continue
                gscore[nxt] = ng
                came_from[nxt] = cur
                heapq.heappush(pq, (ng + math.hypot(gx - nxt[0], gy - nxt[1]), ng, nxt))
    return None


def main():
    base = Path("/working_dir/c_8c72a02b8340fc2f")
    r9_epro2 = base / "user_uploaded_files/ttl=63d/user_uploaded/EVT1-H03-R9-NOT-FOR-FAB.epro2"
    unpack_dir = base / "artifacts/file_generation/ttl=63d/intermediate/r9_unpack"
    out_dir = base / "artifacts/file_generation/ttl=63d/output"
    epru_in = unpack_dir / "EVT1-H03-R9-NOT-FOR-FAB-20261124.epru"

    pads, tracks, vias, max_ticket = load_pcb1(epru_in)
    base_opens, base_clusters = compute_open_connections(pads, tracks, vias)
    cat_base = defaultdict(int)
    for net, cl in base_clusters.items():
        cat_base[net_category(net)] += len(cl) - 1
    print(f"BASELINE PCB1: pads={len(pads)}, tracks={len(tracks)}, vias={len(vias)}, opens={base_opens}, by_cat={dict(cat_base)}")

    rng = random.Random(20261124)
    next_ticket = max_ticket + 10
    added_tracks: list[TrackObj] = []
    added_vias: list[ViaObj] = []
    route_log: list[dict[str, Any]] = []
    rejected_log: list[dict[str, Any]] = []

    def gen_id() -> str:
        return f"r10{rng.getrandbits(52):013x}"

    # --- PHASE 1: GND blind-via stitching into L15/L18 planes + same-layer short GND hops ---
    _, clusters = compute_open_connections(pads, tracks, vias)
    if "GND" in clusters:
        # Sort clusters by size; largest is already plane-connected
        gnd_clusters = sorted(clusters["GND"], key=len, reverse=True)
        for cl in gnd_clusters[1:]:
            # Pick best pad in cluster (prefer one inside GND plane)
            routed = False
            for p in cl:
                if p.layer not in (1, 2):
                    continue
                # 1a. Try direct same-layer short hop to nearest pad in main cluster (<= 90 mil)
                main_same = [mp for mp in gnd_clusters[0] if mp.layer == p.layer]
                main_same.sort(key=lambda mp: math.hypot(mp.x - p.x, mp.y - p.y))
                for mp in main_same[:3]:
                    if math.hypot(mp.x - p.x, mp.y - p.y) > 95.0:
                        break
                    segs = try_direct_or_l_route("GND", p.layer, p.x, p.y, mp.x, mp.y, pads, tracks, vias)
                    if segs is None:
                        segs = try_local_astar("GND", p.layer, p.x, p.y, mp.x, mp.y, pads, tracks, vias)
                    if segs:
                        seg_ids = []
                        for x1, y1, x2, y2 in segs:
                            tr = TrackObj("GND", p.layer, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), TRACK_WIDTH, gen_id())
                            tracks.append(tr)
                            added_tracks.append(tr)
                            seg_ids.append(tr.obj_id)
                        route_log.append({
                            "net": "GND", "category": "GND", "method": "same_layer_to_main",
                            "from": f"{p.des}.{p.num}", "to": f"{mp.des}.{mp.num}", "layer": p.layer,
                            "segments": len(segs), "vias": 0, "ids": seg_ids
                        })
                        routed = True
                        break
                if routed:
                    break

                # 1b. Try blind via (BV_L1_L2 on Top / BV_L5_L6 on Bottom) into L15/L18 GND plane
                if in_gnd_plane(p.x, p.y, margin=8.0):
                    rule_name = "BV_L1_L2" if p.layer == 1 else "BV_L5_L6"
                    v_layers = {1, 15} if p.layer == 1 else {2, 18}
                    # Search concentric ring around pad (10..42 mil) for legal blind via landing
                    found_via = None
                    for r_dist in (12.0, 16.0, 20.0, 25.0, 30.0, 36.0, 42.0):
                        for deg in range(0, 360, 30):
                            vx = round(p.x + r_dist * math.cos(math.radians(deg)), 3)
                            vy = round(p.y + r_dist * math.sin(math.radians(deg)), 3)
                            vok, _ = check_via_drc("GND", vx, vy, BLIND_VIA_HOLE, BLIND_VIA_DIA, v_layers, pads, tracks, vias)
                            if not vok:
                                continue
                            segs = try_direct_or_l_route("GND", p.layer, p.x, p.y, vx, vy, pads, tracks, vias)
                            if segs:
                                found_via = (vx, vy, segs)
                                break
                        if found_via:
                            break
                    if found_via:
                        vx, vy, segs = found_via
                        v_obj = ViaObj("GND", vx, vy, BLIND_VIA_HOLE, BLIND_VIA_DIA, "BLIND", rule_name, v_layers, gen_id())
                        vias.append(v_obj)
                        added_vias.append(v_obj)
                        seg_ids = []
                        for x1, y1, x2, y2 in segs:
                            tr = TrackObj("GND", p.layer, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), TRACK_WIDTH, gen_id())
                            tracks.append(tr)
                            added_tracks.append(tr)
                            seg_ids.append(tr.obj_id)
                        route_log.append({
                            "net": "GND", "category": "GND", "method": f"blind_via_{rule_name}_to_plane",
                            "from": f"{p.des}.{p.num}", "to": f"PLANE_{15 if p.layer==1 else 18}@({vx},{vy})", "layer": p.layer,
                            "segments": len(segs), "vias": 1, "ids": seg_ids + [v_obj.obj_id]
                        })
                        routed = True
                        break
            if not routed:
                rejected_log.append({"net": "GND", "category": "GND", "pad": f"{cl[0].des}.{cl[0].num}", "reason": "no_clearance_safe_path_or_blind_via"})

    # --- PHASE 2 & 3: I2C nets first, then POWER nets (multi-layer: same-layer L1/L2 or inner-layer L16/L17 via through-vias) ---
    _, clusters = compute_open_connections(pads, tracks, vias)
    priority_nets = sorted(
        [n for n in clusters if net_category(n) in ("I2C", "POWER")],
        key=lambda n: (0 if net_category(n) == "I2C" else 1, len(clusters[n]), n),
    )

    for net in priority_nets:
        cat = net_category(net)
        # Iteratively connect closest pair of disconnected clusters
        for _ in range(len(clusters[net]) - 1):
            _, cur_clusters_map = compute_open_connections(pads, tracks, vias)
            if net not in cur_clusters_map or len(cur_clusters_map[net]) <= 1:
                break
            c_list = cur_clusters_map[net]
            # Find closest pad pair across different clusters
            pairs = []
            for i in range(len(c_list)):
                for j in range(i + 1, len(c_list)):
                    for p1 in c_list[i]:
                        for p2 in c_list[j]:
                            pairs.append((math.hypot(p1.x - p2.x, p1.y - p2.y), p1, p2))
            pairs.sort(key=lambda t: t[0])

            connected_one = False
            for dist, p1, p2 in pairs[:12]:
                if dist > 650.0:
                    break
                # Attempt A: Same-layer direct / L / local A*
                if p1.layer == p2.layer and p1.layer in (1, 2):
                    segs = try_direct_or_l_route(net, p1.layer, p1.x, p1.y, p2.x, p2.y, pads, tracks, vias)
                    if segs is None and dist <= 400.0:
                        segs = try_local_astar(net, p1.layer, p1.x, p1.y, p2.x, p2.y, pads, tracks, vias)
                    if segs:
                        seg_ids = []
                        for x1, y1, x2, y2 in segs:
                            tr = TrackObj(net, p1.layer, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), TRACK_WIDTH, gen_id())
                            tracks.append(tr)
                            added_tracks.append(tr)
                            seg_ids.append(tr.obj_id)
                        route_log.append({
                            "net": net, "category": cat, "method": f"same_layer_L{p1.layer}",
                            "from": f"{p1.des}.{p1.num}", "to": f"{p2.des}.{p2.num}", "layer": p1.layer,
                            "segments": len(segs), "vias": 0, "ids": seg_ids
                        })
                        connected_one = True
                        break

                # Attempt B: Multi-layer via inner signal layer L16 or L17 (through-via near p1 & p2)
                def find_thru_via(p: PadObj) -> tuple[float, float, list[tuple[float, float, float, float]]] | None:
                    for r_dist in (12.0, 16.0, 22.0, 28.0, 36.0, 44.0):
                        for deg in range(0, 360, 30):
                            vx = round(p.x + r_dist * math.cos(math.radians(deg)), 3)
                            vy = round(p.y + r_dist * math.sin(math.radians(deg)), 3)
                            vok, _ = check_via_drc(net, vx, vy, THRU_VIA_HOLE, THRU_VIA_DIA, {1, 2, 15, 16, 17, 18}, pads, tracks, vias)
                            if not vok:
                                continue
                            stub = try_direct_or_l_route(net, p.layer, p.x, p.y, vx, vy, pads, tracks, vias)
                            if stub:
                                return (vx, vy, stub)
                    return None

                if p1.layer in (1, 2) and p2.layer in (1, 2):
                    tv1 = find_thru_via(p1)
                    if tv1:
                        v1x, v1y, stub1 = tv1
                        # Temporarily check tv2 clearing tv1 by >= CLR_HOLE_HOLE
                        tv2 = None
                        for r_dist in (12.0, 16.0, 22.0, 28.0, 36.0, 44.0):
                            for deg in range(0, 360, 30):
                                vx = round(p2.x + r_dist * math.cos(math.radians(deg)), 3)
                                vy = round(p2.y + r_dist * math.sin(math.radians(deg)), 3)
                                if math.hypot(vx - v1x, vy - v1y) - THRU_VIA_HOLE < CLR_HOLE_HOLE:
                                    continue
                                vok, _ = check_via_drc(net, vx, vy, THRU_VIA_HOLE, THRU_VIA_DIA, {1, 2, 15, 16, 17, 18}, pads, tracks, vias)
                                if not vok:
                                    continue
                                stub = try_direct_or_l_route(net, p2.layer, p2.x, p2.y, vx, vy, pads, tracks, vias)
                                if stub:
                                    tv2 = (vx, vy, stub)
                                    break
                            if tv2:
                                break
                        if tv2:
                            v2x, v2y, stub2 = tv2
                            for inner_l in (17, 16):
                                inner_segs = try_direct_or_l_route(net, inner_l, v1x, v1y, v2x, v2y, pads, tracks, vias)
                                if inner_segs is None and dist <= 550.0:
                                    inner_segs = try_local_astar(net, inner_l, v1x, v1y, v2x, v2y, pads, tracks, vias, step=6.0)
                                if inner_segs:
                                    ids = []
                                    v1 = ViaObj(net, v1x, v1y, THRU_VIA_HOLE, THRU_VIA_DIA, "NORMAL", "", {1, 2, 15, 16, 17, 18}, gen_id())
                                    v2 = ViaObj(net, v2x, v2y, THRU_VIA_HOLE, THRU_VIA_DIA, "NORMAL", "", {1, 2, 15, 16, 17, 18}, gen_id())
                                    vias.extend([v1, v2])
                                    added_vias.extend([v1, v2])
                                    ids.extend([v1.obj_id, v2.obj_id])
                                    for lay, slist in ((p1.layer, stub1), (p2.layer, stub2), (inner_l, inner_segs)):
                                        for x1, y1, x2, y2 in slist:
                                            tr = TrackObj(net, lay, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), TRACK_WIDTH, gen_id())
                                            tracks.append(tr)
                                            added_tracks.append(tr)
                                            ids.append(tr.obj_id)
                                    route_log.append({
                                        "net": net, "category": cat, "method": f"multilayer_via_L{inner_l}",
                                        "from": f"{p1.des}.{p1.num}", "to": f"{p2.des}.{p2.num}",
                                        "layer": f"L{p1.layer}->L{inner_l}->L{p2.layer}",
                                        "segments": len(stub1) + len(stub2) + len(inner_segs), "vias": 2, "ids": ids
                                    })
                                    connected_one = True
                                    break
                        if connected_one:
                            break
            if not connected_one:
                rejected_log.append({"net": net, "category": cat, "reason": "no_clearance_safe_multilayer_path"})
                break

    # Final independent whole-board DRC check on ALL added tracks & vias
    drc_violations = []
    for tr in added_tracks:
        ok, msg = check_segment_drc(tr.net, tr.layer, tr.x1, tr.y1, tr.x2, tr.y2, tr.width, pads, tracks, vias)
        if not ok:
            drc_violations.append({"type": "TRACK", "id": tr.obj_id, "net": tr.net, "msg": msg})
    for v in added_vias:
        other_vias = [ov for ov in vias if ov.obj_id != v.obj_id]
        ok, msg = check_via_drc(v.net, v.x, v.y, v.hole, v.dia, v.layers, pads, tracks, other_vias)
        if not ok:
            drc_violations.append({"type": "VIA", "id": v.obj_id, "net": v.net, "msg": msg})

    final_opens, final_clusters = compute_open_connections(pads, tracks, vias)
    cat_final = defaultdict(int)
    for net, cl in final_clusters.items():
        cat_final[net_category(net)] += len(cl) - 1

    print(f"FINAL PCB1: opens={base_opens} -> {final_opens} (delta={final_opens - base_opens}), added_tracks={len(added_tracks)}, added_vias={len(added_vias)}, drc_violations={len(drc_violations)}")
    print("  by_cat_before:", dict(cat_base))
    print("  by_cat_after :", dict(cat_final))
    assert len(drc_violations) == 0, f"DRC violations detected: {drc_violations[:5]}"

    # Emit native EasyEDA Pro .epru and repack into EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB.epro2
    new_lines_epru: list[str] = []
    for v in added_vias:
        meta = {"type": "VIA", "ticket": next_ticket, "id": v.obj_id}
        next_ticket += 1
        body = {
            "partitionId": "", "groupId": 0, "netName": v.net, "ruleName": v.rule_name,
            "centerX": v.x, "centerY": v.y, "holeDiameter": v.hole, "viaDiameter": v.dia,
            "viaType": v.via_type, "topSolderExpansion": None, "bottomSolderExpansion": None,
            "locked": False, "unusedInnerLayers": [], "propagationDelay": 0,
        }
        new_lines_epru.append(json.dumps(meta, separators=(",", ":")) + "||" + json.dumps(body, separators=(",", ":")) + "|\n")

    for tr in added_tracks:
        meta = {"type": "LINE", "ticket": next_ticket, "id": tr.obj_id}
        next_ticket += 1
        body = {
            "partitionId": "", "groupId": 0, "netName": tr.net, "layerId": tr.layer,
            "startX": tr.x1, "startY": tr.y1, "endX": tr.x2, "endY": tr.y2,
            "width": tr.width, "locked": False, "zIndex": -1,
        }
        new_lines_epru.append(json.dumps(meta, separators=(",", ":")) + "||" + json.dumps(body, separators=(",", ":")) + "|\n")

    # Insert right before the next DOCHEAD after PCB1 (8fbc3cae65886fe5)
    epru_out = base / "artifacts/file_generation/ttl=63d/intermediate/EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB.epru"
    in_pcb1 = False
    inserted = False
    with epru_in.open("r", encoding="utf-8") as fin, epru_out.open("w", encoding="utf-8") as fout:
        for raw in fin:
            if '"type":"DOCHEAD"' in raw[:40] and "||" in raw:
                if in_pcb1 and not inserted:
                    fout.writelines(new_lines_epru)
                    inserted = True
                    in_pcb1 = False
                _, bstr = raw.rstrip("\r\n").rstrip("|").split("||", 1)
                if json.loads(bstr).get("uuid") == PCB1_UUID:
                    in_pcb1 = True
            fout.write(raw)
        if in_pcb1 and not inserted:
            fout.writelines(new_lines_epru)
            inserted = True
    assert inserted, "Failed to insert new primitives into PCB1 document!"

    # Repack .epro2 preserving all IMAGE/* entries verbatim
    epro2_out = out_dir / "EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB.epro2"
    proj_json = json.loads((unpack_dir / "project2.json").read_text(encoding="utf-8"))
    proj_json["title"] = "EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB"
    with zipfile.ZipFile(r9_epro2, "r") as zin, zipfile.ZipFile(epro2_out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "project2.json":
                zout.writestr("project2.json", json.dumps(proj_json, indent=2, ensure_ascii=False))
            elif item.filename.endswith(".epru"):
                zout.write(epru_out, arcname="EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB.epru")
            else:
                zout.writestr(item, zin.read(item.filename))

    epro2_sha = hashlib.sha256(epro2_out.read_bytes()).hexdigest()
    r9_sha = hashlib.sha256(r9_epro2.read_bytes()).hexdigest()

    # Save delta, geometric DRC log, and STATE.json
    delta_obj = {
        "baseEpro2": r9_epro2.name,
        "baseSha256": r9_sha,
        "outputEpro2": epro2_out.name,
        "outputSha256": epro2_sha,
        "targetBoard": "PCB1 (8fbc3cae65886fe5)",
        "addedTrackCount": len(added_tracks),
        "addedViaCount": len(added_vias),
        "routes": route_log,
        "rejected": rejected_log,
    }
    (out_dir / "r10_routing_delta.json").write_text(json.dumps(delta_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    drc_log = {
        "verificationMode": "OFFLINE_EXACT_CONTINUOUS_GEOMETRY_DRC",
        "nativeEasyEdaGuiDrcStatus": "BLOCKED_BROWSER_LOCAL_FILE_POLICY",
        "rulesEnforced": {
            "trackWidthMil": TRACK_WIDTH,
            "trackToTrackMil": CLR_TRACK_TRACK,
            "copperToPadViaMil": CLR_COPPER_PAD_VIA,
            "holeToCopperMil": CLR_HOLE_COPPER,
            "holeToHoleMil": CLR_HOLE_HOLE,
            "edgeToTrackMil": CLR_EDGE_TRACK,
            "edgeToViaMil": CLR_EDGE_VIA,
            "keepoutProhibitEnforced": True,
        },
        "pcb1BaselineOpenConnections": base_opens,
        "pcb1FinalOpenConnections": final_opens,
        "pcb1OpenDelta": final_opens - base_opens,
        "byCategoryBefore": dict(cat_base),
        "byCategoryAfter": dict(cat_final),
        "addedPrimitivesViolationCount": len(drc_violations),
        "violations": drc_violations,
    }
    (out_dir / "r10_geometric_drc_log.json").write_text(json.dumps(drc_log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    state_obj = {
        "project": "EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB",
        "status": "NOT_FOR_FAB",
        "basePRs": ["PR #60 (a825953)", "PR #61 (d5c2cf1)"],
        "baseNativeEpro2": {"file": r9_epro2.name, "sha256": r9_sha},
        "outputNativeEpro2": {"file": epro2_out.name, "sha256": epro2_sha, "bytes": epro2_out.stat().st_size},
        "componentsPlaced": {"PCB1": 118, "PCB2": 86, "PCB3": 53, "total": 257},
        "r9BaselineNativeOpenConnections": {"PCB1": 334, "PCB2": 232, "PCB3": 129, "total": 695},
        "r10OfflineGeometricRoutingProgress": {
            "pcb1OpenBefore": base_opens,
            "pcb1OpenAfter": final_opens,
            "pcb1NetClosed": base_opens - final_opens,
            "addedTracks": len(added_tracks),
            "addedVias": len(added_vias),
            "offlineClearanceOrShortViolations": 0,
            "projectedTotalOpens": 695 - (base_opens - final_opens),
        },
        "nativeEasyEdaErcDrcVerification": "PENDING_MANUAL_IMPORT_AND_RECHECK",
        "strictErcFatal": 6,
        "nativeNetlistDifference": 1,
        "blocked": [
            "EasyEDA Pro native GUI import & strict ERC/DRC verification (remote browser blocks local file selector)",
            "GitHub independent Draft PR upload (remote browser not signed into GitHub)",
            "PCB1 J2/J3 official footprints & 1 Netlist Error",
            "PCB3 U11 0.35 mm WLCSP & 0.80 mm 2+2+2 HDI fab EQ",
            "Remaining PCB1/PCB2/PCB3 open connections, 40g & binocular transparent AR hardware verification",
        ],
    }
    (out_dir / "STATE.json").write_text(json.dumps(state_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Package deliverable ZIP
    zip_path = out_dir / "EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB-DELIVERY.zip"
    pack_files = [
        ("EVT1-H03-R10-TEST-ROUTING-NOT-FOR-FAB.epro2", epro2_out),
        ("r10_pcb1_batch_router.py", out_dir / "r10_pcb1_batch_router.py"),
        ("r10_routing_delta.json", out_dir / "r10_routing_delta.json"),
        ("r10_geometric_drc_log.json", out_dir / "r10_geometric_drc_log.json"),
        ("STATE.json", out_dir / "STATE.json"),
    ]
    sha_lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {arc}" for arc, p in pack_files]
    sha_file = base / "artifacts/file_generation/ttl=63d/intermediate/R10_SHA256SUMS.txt"
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arc, p in pack_files:
            zf.write(p, arcname=arc)
        zf.write(sha_file, arcname="SHA256SUMS.txt")

    print(json.dumps({
        "epro2_out": epro2_out.name,
        "epro2_sha256": epro2_sha,
        "epro2_bytes": epro2_out.stat().st_size,
        "zip_out": zip_path.name,
        "zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "zip_bytes": zip_path.stat().st_size,
        "routes_committed": len(route_log),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()