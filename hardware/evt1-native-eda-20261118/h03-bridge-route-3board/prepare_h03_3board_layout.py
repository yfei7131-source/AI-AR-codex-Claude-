#!/usr/bin/env python3
"""H03 3-Board Real PCB Layout Builder (Independent MECR-01 25.0x4.6mm Bridge + Full Main-Left PCB1 + Full Audio-Right PCB3).

Inherits strictly from PR #40 Track A (ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2) WITHOUT modifying
the 22.0x4.2mm baseline! Produces an independent 3-board H03 engineering trial where:
  - PCB1 (M-MAIN-L, 8.2x46.0mm stepped temple): ALL 118/118 placeable OEM-bound components placed,
    honoring stepped outline (>=0.315mm), locked 6L RF antenna keepout Y=[0,4.2mm], and MK1 Ø0.80mm/Ø1.40mm acoustic clearance.
    Retains J2 (Camera NDA), J3 (Pogo ID-TBD), BAT1, SPK1 strictly unplaced & BLOCKED.
  - PCB2 (M-OPT-BRIDGE, 4.6x25.0mm MECR-01 trial): ALL 86/86 components placed with U2 BGA positioned clear
    of BOT J1 for checkerboard VIPPO inner-ball fanout, MK2 BOTH-SIDES acoustic clearance, exact Channel IDs,
    and optional non-GND signal via anti-pad cutouts in L2/L5 GND planes (--pcb2-antipads).
  - PCB3 (M-AUD-R, 5.2x34.0mm right temple): ALL 53/53 placeable OEM-bound components placed (including
    Nordic nRF5340-CMAA WLCSP95, Hirose BM28-16+2P, FA-128, FC-1610AN ECO-08 crystal, ANT2, TP6 SWD, MK3),
    honoring locked 6L RF antenna keepout Y=[0,4.0mm] and MK3 acoustic clearance. Retains BAT1, SPK1 BLOCKED.
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from contourpy import contour_generator

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h02-erc"),
    str(PACKAGE / "h02-reve-h03-bridge"),
    str(PACKAGE / "h02-fp-h03-pcb"),
]

from bind_murata_l2 import ASADV_ASSET, asset_metadata, mil
from prepare_hierarchy import Archive, Document, Record, digest
from prepare_reve_h03 import PCB2_KEY, insert_before_config
from prepare_h02_fp_baseline import build_rect_fp, make_bm28_pads
from prepare_mecr01_25x4_6_trial import (
    BRIDGE_CHANNEL_ID,
    MIL_TO_MM,
    footprint_bbox_mm,
    parse_bridge_protel2,
)
from repair_supply_wire_names import ROOTS

PCB1_KEY = ("PCB", "8fbc3cae65886fe5")
PCB3_KEY = ("PCB", "1db01a36f669a47a")

EDGE_MM = 0.315  # > 0.300 mm (11.811 mil) EasyEDA Pro locked Board Outline to SMD Pad rule


def h03_uid(tag: str) -> str:
    return sha256(f"EVT1-H03-3BOARD-MECR01/{tag}".encode("utf-8")).hexdigest()[:16]


def make_circle_hole_poly(cx_mil: float, cy_mil: float, r_mil: float, n_pts: int = 32) -> list:
    pts = []
    for i in range(n_pts + 1):
        ang = -2.0 * math.pi * i / n_pts
        pts.extend([round(cx_mil + r_mil * math.cos(ang), 3), round(cy_mil + r_mil * math.sin(ang), 3)])
    return [pts[0], pts[1], "L", *pts[2:]]


def make_union_hole_polys(circles_mil: list[tuple[float, float, float]], x_min=12.5, x_max=168.5, y_min=12.5, y_max=971.5) -> list[list]:
    """Compute exact non-self-intersecting union cutout polygons of overlapping circles via SDF contour extraction."""
    if not circles_mil:
        return []
    # Fast path: single circle (MK2 only)
    if len(circles_mil) == 1:
        cx, cy, r = circles_mil[0]
        return [make_circle_hole_poly(cx, cy, r, 36)]
    # Group into connected components (circles within r1+r2+2.0 of each other) so isolated circles stay exact analytic!
    n = len(circles_mil)
    visited = [False] * n
    polys = []
    for i in range(n):
        if visited[i]:
            continue
        comp = [i]
        visited[i] = True
        q = [i]
        while q:
            u = q.pop()
            ux, uy, ur = circles_mil[u]
            for v in range(n):
                if not visited[v]:
                    vx, vy, vr = circles_mil[v]
                    if math.hypot(ux - vx, uy - vy) <= ur + vr + 2.0:
                        visited[v] = True
                        comp.append(v)
                        q.append(v)
        if len(comp) == 1:
            cx, cy, r = circles_mil[comp[0]]
            polys.append(make_circle_hole_poly(cx, cy, r, 28))
            continue
        # Connected cluster of 2+ overlapping circles: extract smooth SDF=0 union contour on 0.5 mil grid!
        xs_c = [circles_mil[k][0] for k in comp]
        ys_c = [circles_mil[k][1] for k in comp]
        rmax = max(circles_mil[k][2] for k in comp)
        gx0 = max(x_min, min(xs_c) - rmax - 2.0)
        gx1 = min(x_max, max(xs_c) + rmax + 2.0)
        gy0 = max(y_min, min(ys_c) - rmax - 2.0)
        gy1 = min(y_max, max(ys_c) + rmax + 2.0)
        xs = np.arange(gx0, gx1 + 0.5, 0.5)
        ys = np.arange(gy0, gy1 + 0.5, 0.5)
        X, Y = np.meshgrid(xs, ys)
        sdf = np.full_like(X, 1e9)
        for k in comp:
            cx, cy, r = circles_mil[k]
            sdf = np.minimum(sdf, np.hypot(X - cx, Y - cy) - r)
        # Ensure positive boundary around grid frame so contour closes cleanly
        sdf[0, :] = np.maximum(sdf[0, :], 0.5)
        sdf[-1, :] = np.maximum(sdf[-1, :], 0.5)
        sdf[:, 0] = np.maximum(sdf[:, 0], 0.5)
        sdf[:, -1] = np.maximum(sdf[:, -1], 0.5)
        gen = contour_generator(x=X, y=Y, z=sdf)
        verts_list = gen.lines(0.0)
        for verts in verts_list:
            if len(verts) < 6:
                continue
            # Subsample smoothly (~2.0 mil chord step) and ensure clockwise winding for EasyEDA hole
            sampled = [verts[0]]
            for pt in verts[1:]:
                if math.hypot(pt[0] - sampled[-1][0], pt[1] - sampled[-1][1]) >= 2.0:
                    sampled.append(pt)
            if len(sampled) < 4:
                continue
            # Signed area (shoelace): >0 CCW, <0 CW
            area = sum(sampled[j][0] * sampled[(j + 1) % len(sampled)][1] - sampled[(j + 1) % len(sampled)][0] * sampled[j][1] for j in range(len(sampled)))
            if area > 0:
                sampled.reverse()
            sampled.append(sampled[0])
            flat = []
            for pt in sampled:
                flat.extend([round(float(pt[0]), 2), round(float(pt[1]), 2)])
            polys.append([flat[0], flat[1], "L", *flat[2:]])
    return polys


def collect_board_sch_parts(archive: Archive, board_name: str, extra_overrides=None):
    """Return dict ref -> {dev, fp, uid, page, prim} for all placeable components on board_name."""
    sch_uid = archive.documents[("SCH_PAGE", ROOTS[board_name])].one("META").payload["schematic"]
    parts = {}
    blocked = []
    for (kind, puid), doc in archive.documents.items():
        if kind != "SCH_PAGE" or doc.one("META").payload.get("schematic") != sch_uid:
            continue
        by_p = {}
        for r in doc.records:
            if r.header["type"] == "ATTR" and r.payload.get("parentId"):
                by_p.setdefault(r.payload["parentId"], {})[r.payload["key"]] = r
        for r in doc.records:
            if r.header["type"] != "COMPONENT":
                continue
            cid = r.header["id"]
            attrs = by_p.get(cid, {})
            des = attrs["Designator"].payload["value"] if "Designator" in attrs else ""
            if not des or des.startswith("CBB") or des.startswith("#FLG"):
                continue
            duid = attrs["Device"].payload["value"]
            dev = asset_metadata(archive, ("DEVICE", duid))["attributes"]
            if extra_overrides:
                extra_overrides(des, dev, attrs)
            fuid = dev.get("Footprint", "")
            c2p = attrs["Convert to PCB"].payload["value"] if "Convert to PCB" in attrs else dev.get("Convert to PCB", "yes")
            if not fuid or c2p == "no":
                blocked.append(des)
                continue
            suid = attrs["Unique ID"].payload["value"] if "Unique ID" in attrs else r.payload.get("attrs", {}).get("Unique ID", "")
            if not suid:
                suid = h03_uid(f"SCHUID/{board_name}/{des}")
                r.payload.setdefault("attrs", {})["Unique ID"] = suid
            parts[des] = {"dev": duid, "fp": fuid, "uid": suid, "page": puid, "prim": cid}
    return parts, sorted(blocked)


def materialize_pcb(
    archive: Archive,
    pcb_doc: Document,
    board_tag: str,
    parts: dict,
    placements: dict,
    pad_nets: dict,
    comp_tmpl,
    attrs_tmpl,
    pn_tmpl,
    net_tmpl,
    channel_map: dict | None = None,
):
    """Write native NET + COMPONENT + PAD_NET + ATTR records onto pcb_doc."""
    ticket = max(r.header.get("ticket", 0) for r in pcb_doc.records) + 20
    all_nets = sorted({n for ref in placements for n in pad_nets.get(ref, {}).values() if n})
    for net_id in [""] + sorted({n.upper() for n in all_nets}):
        ticket += 1
        nr = deepcopy(net_tmpl)
        nr.header = {"type": "NET", "ticket": ticket, "id": f'["NET","{net_id}"]'}
        nr.payload.pop("netName", None)
        pcb_doc.records.append(nr)

    total_pads = 0
    for ref in sorted(placements.keys()):
        pinfo = placements[ref]
        bpart = parts[ref]
        fp_doc = archive.documents[("FOOTPRINT", bpart["fp"])]
        dev_title = archive.documents[("DEVICE", bpart["dev"])].one("META").payload["title"]
        fp_pads = [(r.header["id"], r.payload["num"]) for r in fp_doc.records if r.header["type"] == "PAD"]
        comp_id = h03_uid(f"{board_tag}/{ref}")
        chan_id = (channel_map or {}).get(ref, "")
        ticket += 1
        comp = deepcopy(comp_tmpl)
        comp.header = {"type": "COMPONENT", "ticket": ticket, "id": comp_id}
        comp.payload.update(
            layerId=pinfo["layerId"],
            x=round(mil(pinfo["x_mm"]), 4),
            y=round(mil(pinfo["y_mm"]), 4),
            angle=pinfo["rot"],
            locked=False,
            attrs={
                "Reuse Block": "",
                "Group ID": "",
                "Channel ID": chan_id,
                "Unique ID": bpart["uid"],
                "DeviceName": json.dumps({"name": dev_title, "source": "", "uuid": bpart["dev"]}, separators=(",", ":")),
            },
            pinSwapInfo={f"{comp_id}{pid}": {"pinClass": "", "differentialPairClass": ""} for pid, _ in fp_pads},
        )
        pcb_doc.records.append(comp)

        comp_nets = pad_nets.get(ref, {})
        for pid, pnum in fp_pads:
            total_pads += 1
            ticket += 1
            pn = deepcopy(pn_tmpl)
            pn.header = {"type": "PAD_NET", "ticket": ticket, "id": f'["PAD_NET","{comp_id}","{pnum}","{pid}"]'}
            pn.payload["padNet"] = comp_nets.get(pnum, "")
            pcb_doc.records.append(pn)

        silk_layer = 3 if pinfo["layerId"] == 1 else 4
        for idx, sa in enumerate(attrs_tmpl, start=1):
            ticket += 1
            ar = deepcopy(sa)
            ar.header = {"type": "ATTR", "ticket": ticket, "id": f"{comp_id}a{idx}"}
            ar.payload["parentId"] = comp_id
            ar.payload["layerId"] = silk_layer
            k = ar.payload["key"]
            if k == "Footprint":
                ar.payload["value"] = bpart["fp"]
            elif k == "Designator":
                ar.payload["value"] = ref
                ar.payload["x"] = round(mil(pinfo["x_mm"]), 4)
                ar.payload["y"] = round(mil(pinfo["y_mm"]), 4)
            elif k == "Device":
                ar.payload["value"] = bpart["dev"]
            pcb_doc.records.append(ar)

    return total_pads, len(all_nets)


def pack_board(
    archive: Archive,
    parts: dict,
    inside_fn,
    anchored: list,
    initial_obstacles: dict,
    gap_mm: float,
    x_max_mm: float,
    y_min_mm: float,
    y_max_mm: float,
    step_mm: float = 0.10,
    mic_ref: str | None = None,
    post_anchor_fn=None,
):
    """Exact 2D collision-free bottom-left packer honoring stepped outlines, keepouts, and mic acoustic holes."""
    obstacles = {1: list(initial_obstacles[1]), 2: list(initial_obstacles[2])}
    placements = {}

    def can_place(side: int, x: float, y: float, hw: float, hh: float, gap: float = gap_mm) -> bool:
        x0, x1, y0, y1 = x - hw, x + hw, y - hh, y + hh
        if not inside_fn(x0, x1, y0, y1):
            return False
        for ox0, ox1, oy0, oy1, _ in obstacles[side]:
            if not (x1 + gap <= ox0 or x0 - gap >= ox1 or y1 + gap <= oy0 or y0 - gap >= oy1):
                return False
        return True

    def commit(ref: str, side: int, x: float, y: float, rot: float, hw: float, hh: float):
        bb = (round(x - hw, 3), round(x + hw, 3), round(y - hh, 3), round(y + hh, 3))
        obstacles[side].append((*bb, ref))
        placements[ref] = {
            "ref": ref,
            "side": "TOP" if side == 1 else "BOT",
            "layerId": side,
            "x_mm": round(x, 3),
            "y_mm": round(y, 3),
            "rot": rot,
            "bbox_mm": bb,
        }

    for ref, side, x, y, rot in anchored:
        if ref not in parts:
            raise ValueError(f"Anchored ref {ref} not found in board parts")
        hw, hh = footprint_bbox_mm(archive.documents[("FOOTPRINT", parts[ref]["fp"])], rot)
        if not can_place(side, x, y, hw, hh, gap=gap_mm):
            raise ValueError(f"Anchored collision for {ref} side={side} at ({x},{y}) hw={hw} hh={hh}")
        commit(ref, side, x, y, rot, hw, hh)

    # Block opposite side around through-board mic Ø0.80mm acoustic slot!
    if mic_ref and mic_ref in placements:
        mp = placements[mic_ref]
        opp = 2 if mp["layerId"] == 1 else 1
        # rot=0: hole is at (x, y + 0.810); rot=180: (x, y - 0.810)
        dy_h = 0.810 if mp["rot"] == 0 else (-0.810 if mp["rot"] == 180 else 0.0)
        hx, hy = mp["x_mm"], mp["y_mm"] + dy_h
        obstacles[opp].append((hx - 0.70, hx + 0.70, hy - 0.70, hy + 0.70, f"KO_{mic_ref}_OPP_HOLE"))

    if post_anchor_fn:
        post_anchor_fn(placements, obstacles)

    remaining = [r for r in parts if r not in placements]
    remaining.sort(key=lambda r: -(lambda d: d[0] * d[1])(footprint_bbox_mm(archive.documents[("FOOTPRINT", parts[r]["fp"])], 0)))

    for ref in remaining:
        fp_doc = archive.documents[("FOOTPRINT", parts[ref]["fp"])]
        dims = {rot: footprint_bbox_mm(fp_doc, rot) for rot in (0, 90)}
        best = None
        for side in (1, 2):
            for rot in (0, 90):
                hw, hh = dims[rot]
                nx = int((x_max_mm - 2 * EDGE_MM - 2 * hw) / step_mm) + 1
                ny = int((y_max_mm - y_min_mm - 2 * hh) / step_mm) + 1
                if nx <= 0 or ny <= 0:
                    continue
                found_sr = False
                for j in range(ny):
                    y = round(y_min_mm + hh + j * step_mm, 3)
                    if best is not None and (y + hh) > best[0] + step_mm:
                        break
                    for i in range(nx):
                        x = round(EDGE_MM + hw + i * step_mm, 3)
                        if can_place(side, x, y, hw, hh, gap=gap_mm):
                            cand = (round(y + hh, 3), round(x + hw, 3), side, x, y, rot, hw, hh)
                            if best is None or cand[:2] < best[:2]:
                                best = cand
                            found_sr = True
                            break
                    if found_sr:
                        break
        if best is None:
            raise ValueError(f"Could not place {ref} (placed {len(placements)}/{len(parts)})")
        _, _, side, x, y, rot, hw, hh = best
        commit(ref, side, x, y, rot, hw, hh)

    return placements


def build_h03_3board(
    track_a_path: Path,
    net_dir: Path,
    output_path: Path,
    report_path: Path,
    pcb2_antipads_path: Path | None = None,
):
    archive = Archive(track_a_path)
    template = archive.documents[ASADV_ASSET]

    # Grab clean PCB2 templates before touching anything
    pcb2 = archive.documents[PCB2_KEY]
    y1_comp_tmpl = deepcopy(next(r for r in pcb2.records if r.header.get("id") == "6aeaf22afa429c01"))
    y1_attrs_tmpl = [deepcopy(r) for r in pcb2.records if r.header["type"] == "ATTR" and r.payload.get("parentId") == "6aeaf22afa429c01"]
    y1_pn_tmpl = deepcopy(next(r for r in pcb2.records if r.header["type"] == "PAD_NET" and "6aeaf22afa429c01" in r.header["id"]))
    sample_net_tmpl = deepcopy(next(r for r in pcb2.records if r.header["type"] == "NET"))

    # =========================================================================
    # 1. PCB2 (M-OPT-BRIDGE, 4.60 x 25.00 mm Independent MECR-01 Trial)
    # =========================================================================
    bm10_o, bm10_b, bm10_p = make_bm28_pads(10)
    bm10_asset, bm10_doc = build_rect_fp(
        template,
        "Hirose_BM28B0.6-10DS_2-0.35V_PROVISIONAL_NDA",
        "J?",
        "PROVISIONAL MECHANICAL ENVELOPE ONLY (JBD NDA BLOCKED): Hirose BM28B0.6-10DS/2-0.35V (4.35x1.80mm).",
        ["BM28", "10+2P", "NDA_PROVISIONAL"],
        bm10_o, bm10_b, bm10_p, "bm10p", "RECT",
    )
    insert_before_config(archive, {bm10_asset: bm10_doc})

    dqn_uid = "7fc3ca1940b32b12"
    fp_by_title = {d.one("META").payload["title"]: uid for (k, uid), d in archive.documents.items() if k == "FOOTPRINT"}
    fp_0201 = fp_by_title["IPC_0201_0603Metric"]
    fp_0402 = fp_by_title["IPC_0402_1005Metric"]
    caps_to_0201 = {f"C{i}" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 17, 18, 19, 21, 23)}
    caps_to_0402 = {"C13", "C15", "C20", "C22"}

    def bridge_overrides(des, dev, attrs):
        if des in ("J2", "J3"):
            dev["Footprint"] = bm10_asset[1]
            dev["Convert to PCB"] = "yes"
            if "Convert to PCB" in attrs:
                attrs["Convert to PCB"].payload["value"] = "yes"
        elif des == "U6":
            dev["Footprint"] = dqn_uid
            dev["Convert to PCB"] = "yes"
            if "Convert to PCB" in attrs:
                attrs["Convert to PCB"].payload["value"] = "yes"
        elif des in caps_to_0201:
            dev["Footprint"] = fp_0201
        elif des in caps_to_0402:
            dev["Footprint"] = fp_0402

    bridge_parts, bridge_blocked = collect_board_sch_parts(archive, "M-OPT-BRIDGE", bridge_overrides)
    if len(bridge_parts) != 86:
        raise ValueError(f"Expected 86 bridge parts, got {len(bridge_parts)}")

    pcb2.records = [r for r in pcb2.records if r.header["type"] not in ("COMPONENT", "PAD_NET", "ATTR", "NET", "REGION")]
    bw2, bl2 = 4.60, 25.00
    w2_mil, l2_mil = round(mil(bw2), 4), round(mil(bl2), 4)
    for r in pcb2.records:
        if r.header["type"] == "POLY" and r.payload.get("layerId") == 11:
            r.payload["path"] = [0, 0, "L", w2_mil, 0, w2_mil, l2_mil, 0, l2_mil, 0, 0]

    # J2 & J3 sit in their physical TOP optical FPC mating zones; block rest of both TOP bands!
    # U2 sits at (2.30, 9.60) on TOP (clear of BOT J1 ending at Y=7.25!) with a clean BOT BGA VIPPO pocket!
    def inside_pcb2(x0, x1, y0, y1):
        return x0 >= 0.310 and x1 <= bw2 - 0.310 and y0 >= 0.310 and y1 <= bl2 - 0.310

    def post_anchor_pcb2(pl, obs):
        # Block remaining TOP space in the two optical FPC mating bands
        obs[1].append((0.0, bw2, 3.03, 5.37, "KO_FPC_L"))
        obs[1].append((0.0, bw2, 13.63, 15.97, "KO_FPC_R"))
        # Reserve clean BOT BGA VIPPO fanout pocket directly under U2's inner balls!
        u2x, u2y = pl["U2"]["x_mm"], pl["U2"]["y_mm"]
        obs[2].append((u2x - 0.72, u2x + 0.72, u2y - 0.72, u2y + 0.72, "KO_U2_BOT_VIPPO"))

    pcb2_anchored = [
        ("J2",  1, 2.30, 4.20, 0),    # TOP Left optical FPC mating zone
        ("J3",  1, 2.30, 14.80, 0),   # TOP Right optical FPC mating zone
        ("D3",  1, 0.85, 1.45, 90),   # TOP front privacy LED
        ("U2",  1, 2.30, 9.60, 0),    # TOP iCE40UP5K BGA centered above J1 for BOT VIPPO fanout!
        ("U9",  1, 1.95, 17.65, 0),   # TOP ICM-42688-P IMU
        ("J1",  2, 1.45, 3.80, 90),   # BOT Hirose BM28-30+2P trunk (Y=[0.35..7.25])
        ("MK2", 2, 1.68, 22.80, 0),   # BOT IM69D130V01 mic (hole at (1.68, 23.61), leaves BOT Y=7.3..20.8 open!)
        # Functional QSPI clustering: Left-eye termination resistors (rot=270 so Pad 2 *_PANEL faces J2 SOUTH, Pad 1 faces U2 NORTH!)
        ("R23", 1, 0.56, 6.08, 270),  # OPT_SCK_L
        ("R13", 1, 1.15, 6.08, 270),  # OPT_CS_N_L
        ("R15", 1, 1.74, 6.08, 270),  # opt_l_qdo0
        ("R16", 1, 2.33, 6.08, 270),  # opt_l_qdo1
        ("R17", 1, 2.92, 6.08, 270),  # opt_l_qdo2
        ("R18", 1, 3.51, 6.08, 270),  # opt_l_qdo3
        ("R25", 1, 4.06, 6.08, 270),  # OPT_CS_N_L pull-up
        # Functional QSPI clustering: Right-eye termination resistors (rot=90 so Pad 1 faces U2 SOUTH, Pad 2 *_PANEL faces J3 NORTH!)
        ("R24", 1, 0.56, 12.92, 90),  # OPT_SCK_R
        ("R14", 1, 1.15, 12.92, 90),  # OPT_CS_N_R
        ("R19", 1, 1.74, 12.92, 90),  # opt_r_qdo0
        ("R20", 1, 2.33, 12.92, 90),  # opt_r_qdo1
        ("R21", 1, 2.92, 12.92, 90),  # opt_r_qdo2
        ("R22", 1, 3.51, 12.92, 90),  # opt_r_qdo3
        ("R26", 1, 4.06, 12.92, 90),  # OPT_CS_N_R pull-up
    ]
    pcb2_places = pack_board(
        archive, bridge_parts, inside_pcb2, pcb2_anchored,
        {1: [], 2: []}, gap_mm=0.175, x_max_mm=bw2, y_min_mm=0.310, y_max_mm=bl2 - 0.310,
        step_mm=0.05, mic_ref="MK2", post_anchor_fn=post_anchor_pcb2,
    )

    # Update PCB2 L2/L5 LAYER_FILL GND planes with MK2 Ø1.40mm anti-pad + exact SDF-union non-GND signal via anti-pads!
    mk2_wx = mil(pcb2_places["MK2"]["x_mm"]) - 0.005
    mk2_wy = mil(pcb2_places["MK2"]["y_mm"]) + 31.89
    circles = [(mk2_wx, mk2_wy, 28.0)]
    antipad_count = 0
    if pcb2_antipads_path and pcb2_antipads_path.exists():
        ap_list = json.loads(pcb2_antipads_path.read_text(encoding="utf-8"))
        for vx, vy in ap_list:
            # r = 15.2 mil -> 15.2 - 4.0 (via pad) = 11.2 mil > 10.0 mil Plane Zone to Via rule!
            circles.append((float(vx), float(vy), 15.2))
            antipad_count += 1
    pcb2_holes = make_union_hole_polys(circles)
    outer_p2 = [10.1, round(l2_mil - 10.1, 4), "L", round(w2_mil - 10.1, 4), round(l2_mil - 10.1, 4),
                round(w2_mil - 10.1, 4), 10.1, 10.1, 10.1, 10.1, round(l2_mil - 10.1, 4)]
    for r in pcb2.records:
        if r.header["type"] == "LAYER_FILL":
            for it in r.payload.get("fill", []):
                if it.get("layerId") in (15, 17):
                    it["netName"] = "GND"
                    it["path"] = [outer_p2, *pcb2_holes]

    bridge_nets = parse_bridge_protel2(net_dir / "M-OPT-BRIDGE.net")
    p2_pads, p2_ncnt = materialize_pcb(
        archive, pcb2, "PCB2", bridge_parts, pcb2_places, bridge_nets,
        y1_comp_tmpl, y1_attrs_tmpl, y1_pn_tmpl, sample_net_tmpl, BRIDGE_CHANNEL_ID,
    )

    # =========================================================================
    # 2. PCB1 (M-MAIN-L, 8.20 x 46.00 mm Stepped Left-Temple Main Board)
    # =========================================================================
    # Strip the 9 netless footprint-embedded thermal vias from U1 QFN-56 EP4.0 (EasyEDA #118 re-materializes
    # footprint-embedded vias netless on reload); real persisted PCB-level GND thermal vias are placed live
    # inside U1's EPAD via `easyeda pcb via --net GND`!
    u1_fp_doc = archive.documents[("FOOTPRINT", "f673d860669b20d7")]
    u1_fp_doc.records = [fr for fr in u1_fp_doc.records if fr.header["type"] != "VIA"]

    pcb1 = archive.documents[PCB1_KEY]
    main_parts, main_blocked = collect_board_sch_parts(archive, "M-MAIN-L")
    pcb1.records = [r for r in pcb1.records if r.header["type"] not in ("COMPONENT", "PAD_NET", "ATTR", "NET")]

    # Stepped outline:
    #   Y in [0.0, 4.2]: locked 6L RF antenna PROHIBIT keepout (0..5.8) -> NO components placed inside Y < 4.55!
    #   Y in [4.2, 14.0]: wide 8.20 mm head (X in [0.0, 8.20]) for U1 ESP32-S3!
    #   Y in [14.0, 46.0]: slim 5.80 mm temple stem (X in [0.0, 5.80])
    def inside_pcb1(x0, x1, y0, y1):
        if x0 < EDGE_MM or y0 < 4.20 + EDGE_MM or y1 > 46.00 - EDGE_MM:
            return False
        # Must stay inside X <= 5.80 - EDGE_MM whenever any part of bbox reaches Y > 14.00 - EDGE_MM
        if y1 > 14.00 - EDGE_MM:
            return x1 <= 5.80 - EDGE_MM
        # Inside Y in [4.20 + EDGE_MM, 14.00 - EDGE_MM], wide head allows X <= 8.20 - EDGE_MM
        return x1 <= 8.20 - EDGE_MM

    def post_anchor_pcb1(pl, obs):
        # Block BOT behind U1 ESP32-S3 4.0x4.0mm thermal EPAD & 9 embedded GND thermal vias!
        u1x, u1y = pl["U1"]["x_mm"], pl["U1"]["y_mm"]
        obs[2].append((u1x - 2.35, u1x + 2.35, u1y - 2.35, u1y + 2.35, "KO_U1_BOT_THERMAL_VIAS"))

    pcb1_anchored = [
        ("U1",   1, 4.10, 9.10, 0),    # TOP ESP32-S3-PICO-1 (7.48x7.48) centered in 8.2x9.8 wide head!
        ("ANT1", 2, 2.50, 5.45, 0),    # BOT Johanson 2450AT18B100E right at edge of Y=[0,4.2] RF keepout
        ("J1",   2, 4.30, 18.00, 90),  # BOT Hirose BM28-30+2P trunk to bridge
        ("MK1",  2, 2.20, 43.20, 0),   # BOT IM69D130V01 mic near temple tail (hole at (2.20, 44.01))
    ]
    pcb1_places = pack_board(
        archive, main_parts, inside_pcb1, pcb1_anchored,
        {1: [], 2: []}, gap_mm=0.205, x_max_mm=8.20, y_min_mm=4.20 + EDGE_MM, y_max_mm=46.00 - EDGE_MM,
        step_mm=0.10, mic_ref="MK1", post_anchor_fn=post_anchor_pcb1,
    )

    # Update PCB1 L2/L5 LAYER_FILL: assign net="GND", keep strictly clear of Y=[0,4.2] RF keepout (+10.5mil),
    # and cut MK1 Ø1.40mm acoustic anti-pad!
    mk1_wx = mil(pcb1_places["MK1"]["x_mm"]) - 0.005
    mk1_wy = mil(pcb1_places["MK1"]["y_mm"]) + 31.89
    mk1_hole = make_circle_hole_poly(mk1_wx, mk1_wy, 28.0, 36)
    # Clean stepped L2/L5 plane polygon strictly inside outline (>=10.5mil) AND strictly above Y >= 176.0 mil (4.47mm > 4.20+0.254)!
    y_rf_clr = 176.0
    outer_p1 = [
        10.5, 1800.5, "L",
        217.8, 1800.5,
        217.8, 540.5,
        312.3, 540.5,
        312.3, y_rf_clr,
        10.5, y_rf_clr,
        10.5, 1800.5,
    ]
    for r in pcb1.records:
        if r.header["type"] == "LAYER_FILL":
            for it in r.payload.get("fill", []):
                if it.get("layerId") in (15, 17):
                    it["netName"] = "GND"
                    it["path"] = [outer_p1, mk1_hole]

    main_nets = parse_bridge_protel2(net_dir / "M-MAIN-L.net")
    p1_pads, p1_ncnt = materialize_pcb(
        archive, pcb1, "PCB1", main_parts, pcb1_places, main_nets,
        y1_comp_tmpl, y1_attrs_tmpl, y1_pn_tmpl, sample_net_tmpl,
    )

    # =========================================================================
    # 3. PCB3 (M-AUD-R, 5.20 x 34.00 mm Right Audio & BLE Temple Board)
    # =========================================================================
    # Nordic nRF5340 WLCSP95 NSMD copper land = 0.195mm (7.677mil, official 0.18-0.21mm range)
    # -> ball-to-ball copper gap = 13.780 - 7.677 = 6.103mil > 6.0mil locked DRC rule!
    u11_fp_doc = archive.documents[("FOOTPRINT", "ddd711692e399705")]
    for fr in u11_fp_doc.records:
        if fr.header["type"] == "PAD":
            dp = fr.payload.get("defaultPad", {})
            if dp.get("padType") == "ELLIPSE":
                dp["width"] = 7.677
                dp["height"] = 7.677

    pcb3 = archive.documents[PCB3_KEY]
    aud_parts, aud_blocked = collect_board_sch_parts(archive, "M-AUD-R")
    pcb3.records = [r for r in pcb3.records if r.header["type"] not in ("COMPONENT", "PAD_NET", "ATTR", "NET")]

    # Outline: 5.20 x 34.00 mm; Y in [0.0, 4.00] is locked 6L RF antenna PROHIBIT keepout!
    def inside_pcb3(x0, x1, y0, y1):
        return x0 >= EDGE_MM and x1 <= 5.20 - EDGE_MM and y0 >= 4.00 + EDGE_MM and y1 <= 34.00 - EDGE_MM

    pcb3_anchored = [
        ("ANT2", 1, 2.60, 5.25, 0),    # TOP Johanson 2450AT18B100E right above Y=[0,4.0] RF keepout
        ("U11",  1, 2.60, 9.20, 90),   # TOP Nordic nRF5340-CMAA WLCSP95 (3.71W x 4.06H)
        ("Y2",   1, 1.60, 12.60, 0),   # TOP Epson FA-128 32MHz HFXO right beside nRF5340
        ("Y3",   1, 3.80, 12.60, 90),  # TOP Epson FC-1610AN ECO-08 32.768kHz LFXO right beside nRF5340
        ("TP6",  1, 0.70, 16.50, 90),  # TOP 5-pad SWD test header along edge
        ("J1",   2, 2.60, 6.80, 90),   # BOT Hirose BM28-16+2P trunk to bridge
        ("MK3",  2, 2.40, 31.20, 0),   # BOT IM69D130V01 mic near temple tail (hole at (2.40, 32.01))
    ]
    pcb3_places = pack_board(
        archive, aud_parts, inside_pcb3, pcb3_anchored,
        {1: [], 2: []}, gap_mm=0.205, x_max_mm=5.20, y_min_mm=4.00 + EDGE_MM, y_max_mm=34.00 - EDGE_MM,
        step_mm=0.10, mic_ref="MK3",
    )

    mk3_wx = mil(pcb3_places["MK3"]["x_mm"]) - 0.005
    mk3_wy = mil(pcb3_places["MK3"]["y_mm"]) + 31.89
    mk3_hole = make_circle_hole_poly(mk3_wx, mk3_wy, 28.0, 36)
    # Trim PCB3 L2/L5 GND planes cleanly above Y >= 168.0 mil (4.267 mm > 4.00 + 0.254 RF keepout)!
    outer_p3 = [10.5, 1328.0, "L", 194.2, 1328.0, 194.2, 168.0, 10.5, 168.0, 10.5, 1328.0]
    for r in pcb3.records:
        if r.header["type"] == "LAYER_FILL":
            for it in r.payload.get("fill", []):
                if it.get("layerId") in (15, 17):
                    it["netName"] = "GND"
                    it["path"] = [outer_p3, mk3_hole]

    aud_nets = parse_bridge_protel2(net_dir / "M-AUD-R.net")
    p3_pads, p3_ncnt = materialize_pcb(
        archive, pcb3, "PCB3", aud_parts, pcb3_places, aud_nets,
        y1_comp_tmpl, y1_attrs_tmpl, y1_pn_tmpl, sample_net_tmpl,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    archive.write(output_path)

    report = {
        "status": "H03_3BOARD_MECR01_LAYOUT_BUILT",
        "manufacturing": "BLOCKED",
        "baseline_22x4_2_preserved": True,
        "candidateSha256": digest(output_path),
        "pcb1_main_left": {
            "outline_mm": "8.20x46.00 stepped (5.80 stem)",
            "placed": len(pcb1_places),
            "top": sum(1 for v in pcb1_places.values() if v["side"] == "TOP"),
            "bot": sum(1 for v in pcb1_places.values() if v["side"] == "BOT"),
            "pads": p1_pads,
            "nets": p1_ncnt,
            "blocked_unplaced": main_blocked,
        },
        "pcb2_bridge_mecr01_25x4_6": {
            "outline_mm": [bw2, bl2],
            "placed": len(pcb2_places),
            "top": sum(1 for v in pcb2_places.values() if v["side"] == "TOP"),
            "bot": sum(1 for v in pcb2_places.values() if v["side"] == "BOT"),
            "pads": p2_pads,
            "nets": p2_ncnt,
            "antipads_cut": antipad_count,
            "nda_provisional_envelopes": ["J2", "J3", "U6"],
        },
        "pcb3_audio_right": {
            "outline_mm": [5.20, 34.00],
            "placed": len(pcb3_places),
            "top": sum(1 for v in pcb3_places.values() if v["side"] == "TOP"),
            "bot": sum(1 for v in pcb3_places.values() if v["side"] == "BOT"),
            "pads": p3_pads,
            "nets": p3_ncnt,
            "blocked_unplaced": aud_blocked,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built 3-Board H03 Candidate: {output_path}")
    print(f"  PCB1 (M-MAIN-L,   8.2x46.0 stepped): {len(pcb1_places)}/118 placed (Pads={p1_pads}, Blocked={main_blocked})")
    print(f"  PCB2 (M-OPT-BR,   4.6x25.0 MECR-01): {len(pcb2_places)}/86  placed (Pads={p2_pads}, AntiPads={antipad_count})")
    print(f"  PCB3 (M-AUD-R,    5.2x34.0 right)  : {len(pcb3_places)}/53  placed (Pads={p3_pads}, Blocked={aud_blocked})")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--track-a", type=Path, default=PACKAGE / "h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2")
    p.add_argument("--net-dir", type=Path, default=PACKAGE / "h02-fp-h03-pcb/evidence/track-a-22x4_2/board-netlists")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--pcb2-antipads", type=Path, default=None)
    a = p.parse_args()
    build_h03_3board(a.track_a, a.net_dir, a.output, a.report, a.pcb2_antipads)


if __name__ == "__main__":
    main()
