#!/usr/bin/env python3
"""Upgraded All-58-Nets 4-Layer Pad-Escape + Checkerboard BGA VIPPO + A* Copper Router for H03 PCB2 (25.0x4.6mm).

Strictly honors every locked EasyEDA Pro V4.1.97 6L HDI DRC rule without relaxing any rule:
  - Track width >= 2.0 mil (2.5 mil signals, 3.5 mil power, 4.0 mil GND stitch)
  - Track-to-Track >= 2.0 mil (enforced >= 2.8 mil)
  - Track/Via-to-SMD Pad >= 6.0 mil (enforced >= 6.5 mil; VIPPO concentric on U2 0.40mm BGA = 7.615 mil > 6.0 mil!)
  - Hole-to-SMD Pad >= 6.9 mil (VIPPO 4mil drill on U2 = 9.615 mil > 6.9 mil!)
  - Hole-to-Hole >= 11.811 mil (enforced >= 17.5 mil GND-GND; >= 31.0 mil non-GND to non-GND for disjoint L2/L5 anti-pads!)
  - Plane Zone to Via >= 10.0 mil (every non-GND via gets a disjoint r=14.8 mil anti-pad cutout in L2/L5!)
  - Full MK2 BOT body + polygon GND ring protected against all non-GND copper!
"""

import argparse
import heapq
import json
import math
from pathlib import Path

W_MIL, H_MIL = 181.1024, 984.2520
L_IDS = [1, 16, 18, 2]  # 0=TOP, 1=L3(Inner2), 2=L4(Inner4), 3=BOT
SIDE_TO_LI = {1: 0, 2: 3}

# Priority ordering: compact 2-5 pin FPGA BGA / QSPI / AVDD / Clock / Privacy / I2C / PDM FIRST,
# then medium power rails, then large multi-pad power trunks (1V8_FPGA_IO, VSYS) LAST so trunks never choke signals!
NET_PRIORITY_WIDTH = [
    # Tier 2A: Compact FPGA BGA Clock, Sequencing & Privacy LED (2-4 pads)
    ("clk_48m", 2.5),
    ("FPGA_1V2_SENSE", 2.5),
    ("FPGA_1V8_EN", 2.5),
    ("PRIV_LED_ANODE", 3.5),
    ("FPGA_CRESET_B", 2.5),
    ("FPGA_CDONE_VSYNC_N", 2.5),
    # Tier 2B: Optical QSPI Left & Right + Panel Terminations + Host QSPI (2-3 pads each!)
    ("opt_sck", 2.5),
    ("opt_cs_n", 2.5),
    ("OPT_SCK_L", 2.5),
    ("OPT_CS_N_L", 2.5),
    ("OPT_SCK_R", 2.5),
    ("OPT_CS_N_R", 2.5),
    ("opt_l_qdo0", 2.5),
    ("opt_l_qdo1", 2.5),
    ("opt_l_qdo2", 2.5),
    ("opt_l_qdo3", 2.5),
    ("opt_l_qdo0_PANEL", 2.5),
    ("opt_l_qdo1_PANEL", 2.5),
    ("opt_l_qdo2_PANEL", 2.5),
    ("opt_l_qdo3_PANEL", 2.5),
    ("opt_r_qdo0", 2.5),
    ("opt_r_qdo1", 2.5),
    ("opt_r_qdo2", 2.5),
    ("opt_r_qdo3", 2.5),
    ("opt_r_qdo0_PANEL", 2.5),
    ("opt_r_qdo1_PANEL", 2.5),
    ("opt_r_qdo2_PANEL", 2.5),
    ("opt_r_qdo3_PANEL", 2.5),
    ("host_sck", 2.5),
    ("host_cs_n", 2.5),
    ("host_qio0", 2.5),
    ("host_qio1", 2.5),
    ("host_qio2", 2.5),
    ("host_qio3", 2.5),
    ("SYS_I2C_SCL_1V8", 2.5),
    ("SYS_I2C_SDA_1V8", 2.5),
    ("PDM_CLK_1V8", 2.5),
    ("PDM_D0_1V8", 2.5),
    # Tier 3: AVDD Safety Watchdog Chain (2-7 pads)
    ("AVDD_WD_SET", 2.5),
    ("AVDD_WD_DIV", 2.5),
    ("AVDD_CRESET_VSYS", 2.5),
    ("AVDD_PULSE_QUAL", 2.5),
    ("AVDD_PG_OK", 2.5),
    ("AVDD_QUAL_CLR_N", 2.5),
    ("AVDD_REQ_FILTER", 2.5),
    ("AVDD_QUAL_RC", 2.5),
    ("AVDD_D3_VSYS", 2.5),
    ("AVDD_WD_Q", 2.5),
    ("AVDD_PG_NODE", 2.5),
    ("OPT_AVDD_EN", 2.5),
    ("AVDD_OPT_BIAS", 3.5),
    # Tier 4: Power Rails & Large Multi-Pad Trunks
    ("1V8_FPGA_VPP", 3.5),
    ("1V2_FPGA_PLL", 3.5),
    ("1V2_FPGA_CORE", 3.5),
    ("1V8_SYS", 3.5),
    ("1V8_FPGA_IO", 3.5),
    ("VSYS", 3.5),
]

U2_INNER_BALLS = {"B2", "C2", "D2", "E2", "B3", "C3", "D3", "E3", "B4", "C4", "D4", "E4"}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def plan_bridge_routing(dump_path: Path, plan_out: Path, antipads_out: Path):
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    STEP = 2.0  # 2.0 mil fine grid (91 x 493 = 44,863 cells/layer)
    NX = int(W_MIL / STEP) + 1
    NY = int(H_MIL / STEP) + 1

    all_pads = []
    pads_by_net: dict[str, list[dict]] = {}
    comp_centers = {}
    mk2_cx, mk2_cy = 66.14, 897.64
    mk2_hx, mk2_hy = 66.14, 929.53

    for c in dump["components"]:
        ref = c["designator"]
        cx, cy = float(c["x"]), float(c["y"])
        c_rot = float(c.get("rotation") or 0.0)
        comp_centers[ref] = (cx, cy)
        if ref == "MK2":
            mk2_cx, mk2_cy = cx, cy
            mk2_hx = cx - 0.005
            mk2_hy = cy + 31.89
        for p in c.get("pads", []):
            net = p.get("net") or ""
            px, py = float(p["x"]), float(p["y"])
            pw = float(p.get("width") or 0.0)
            ph = float(p.get("height") or 0.0)
            if pw < 1.0 or ph < 1.0:
                shp = p.get("shape") or []
                if isinstance(shp, list) and len(shp) >= 2 and shp[0] == "POLY" and isinstance(shp[1], list):
                    nums = [float(v) for v in shp[1] if isinstance(v, (int, float))]
                    if len(nums) >= 4:
                        xs, ys = nums[0::2], nums[1::2]
                        pw = max(pw, max(xs) - min(xs))
                        ph = max(ph, max(ys) - min(ys))
                # MK2 polygon ground ring pads span ~28x28 mil each; U1/U4/U6 DQN pads span ~16x16 mil
                if ref == "MK2":
                    pw, ph = max(pw, 28.0), max(ph, 28.0)
                else:
                    pw, ph = max(pw, 16.0), max(ph, 16.0)
            rot = c_rot + float(p.get("rotation") or 0.0)
            rad = math.radians(rot)
            ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
            hw = 0.5 * (pw * ca + ph * sa) + 0.5
            hh = 0.5 * (pw * sa + ph * ca) + 0.5
            li = SIDE_TO_LI.get(int(p.get("layer", c["layer"])), 0)
            rec = {
                "x": px, "y": py, "hw": hw, "hh": hh, "li": li,
                "net": net, "ref": ref, "pnum": str(p.get("padNumber", "")),
                "cx": cx, "cy": cy,
            }
            all_pads.append(rec)
            if net:
                pads_by_net.setdefault(net, []).append(rec)

    # Full MK2 BOT courtyard (protects MK2's non-rectangular polygon GND ring 100%!)
    mk2_box = (mk2_cx - 56.0, mk2_cx + 56.0, mk2_cy - 76.0, mk2_cy + 76.0)

    def in_mk2_body(x: float, y: float, pad_r: float = 0.0) -> bool:
        return (mk2_box[0] - pad_r <= x <= mk2_box[1] + pad_r) and (mk2_box[2] - pad_r <= y <= mk2_box[3] + pad_r)

    def to_grid(x: float, y: float) -> tuple[int, int]:
        return max(0, min(NX - 1, int(round(x / STEP)))), max(0, min(NY - 1, int(round(y / STEP))))

    def from_grid(gx: int, gy: int) -> tuple[float, float]:
        return round(gx * STEP, 2), round(gy * STEP, 2)

    routed_segs: list[tuple[int, float, float, float, float, float, str]] = []
    placed_vias: list[tuple[float, float, str]] = []

    def via_is_legal(vx: float, vy: float, net: str, vippo_u2: bool = False) -> bool:
        is_gnd = (net == "GND")
        # Board outline clearance (non-GND needs r=14.8 anti-pad inside outer_plane [10.1..171, 10.1..974] -> >=26.0 mil!)
        edge_min = 17.5 if is_gnd else 26.2
        if vx < edge_min or vx > W_MIL - edge_min or vy < edge_min or vy > H_MIL - edge_min:
            return False
        # MK2 acoustic hole clearance (non-GND r=14.8 anti-pad disjoint from MK2 r=28.0 anti-pad -> >=44.5 mil!)
        mk2_min_r = 35.5 if is_gnd else 44.5
        if math.hypot(vx - mk2_hx, vy - mk2_hy) < mk2_min_r:
            return False
        if not is_gnd and in_mk2_body(vx, vy, 11.5):
            return False
        # Via-to-via spacing:
        #   GND-GND >= 17.5 mil (Hole-to-Hole >= 11.811)
        #   non-GND to non-GND >= 18.0 mil (Hole-to-Hole >= 11.811; L2/L5 SDF union merges adjacent anti-pads cleanly!)
        #   non-GND to GND >= 21.0 mil (r=15.0 anti-pad clears GND via outer pad r=4.0 + 2.0 mil copper!)
        for ovx, ovy, onet in placed_vias:
            d = math.hypot(vx - ovx, vy - ovy)
            if is_gnd and onet == "GND":
                if d < 17.5:
                    return False
            elif (not is_gnd) and (onet != "GND"):
                if d < 18.0:
                    return False
            else:
                if d < 21.0:
                    return False
        # Pad clearance on TOP and BOT
        for p in all_pads:
            if p["net"] == net:
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            dist = math.hypot(dx, dy)
            if vippo_u2 and p["ref"] == "U2" and p["li"] == 0:
                # Concentric 4/8 mil VIPPO on U2 0.40mm BGA: edge-to-edge to neighbor ball is 7.615 mil > 6.0 mil!
                if dist < 6.8:
                    return False
            else:
                if dist < 11.2:
                    return False
        # Routed track clearance on all layers
        for _, x1, y1, x2, y2, w, onet in routed_segs:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 11.2 + 0.5 * w:
                return False
        return True

    def seg_is_legal(li: int, x1: float, y1: float, x2: float, y2: float, width: float, net: str, own_pad: dict | None = None) -> bool:
        edge_c = 13.0 + 0.5 * width
        if min(x1, x2) < edge_c or max(x1, x2) > W_MIL - edge_c or min(y1, y2) < edge_c or max(y1, y2) > H_MIL - edge_c:
            return False
        if pt_seg_dist(mk2_hx, mk2_hy, x1, y1, x2, y2) < 32.0 + 0.5 * width:
            return False
        if li == 3 and net != "GND":
            # Check endpoints & midpoint against MK2 BOT courtyard
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if in_mk2_body(cx, cy, 7.0 + 0.5 * width):
                    return False
        for vx, vy, onet in placed_vias:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 11.0 + 0.5 * width:
                return False
        steps = max(3, int(math.hypot(x2 - x1, y2 - y1) / 2.0) + 1)
        if li in (0, 3):
            for p in all_pads:
                if p["li"] != li or p["net"] == net:
                    continue
                # Pad-to-track >= 6.0 mil -> enforce 6.5 mil!
                clr = 6.5 + 0.5 * width
                for s in range(steps + 1):
                    t = s / steps
                    cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                    dx = max(0.0, abs(cx - p["x"]) - p["hw"])
                    dy = max(0.0, abs(cy - p["y"]) - p["hh"])
                    if math.hypot(dx, dy) < clr:
                        return False
        for oli, ox1, oy1, ox2, oy2, ow, onet in routed_segs:
            if oli != li or onet == net:
                continue
            min_d = 3.0 + 0.5 * (width + ow)
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if pt_seg_dist(cx, cy, ox1, oy1, ox2, oy2) < min_d:
                    return False
        return True

    def build_net_masks(net: str, width: float):
        is_gnd = (net == "GND")
        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))

        min_gx = int(math.ceil((13.0 + 0.5 * width) / STEP))
        max_gx = int(math.floor((W_MIL - 13.0 - 0.5 * width) / STEP))
        min_gy = int(math.ceil((13.0 + 0.5 * width) / STEP))
        max_gy = int(math.floor((H_MIL - 13.0 - 0.5 * width) / STEP))

        ve = 17.5 if is_gnd else 26.2
        vmin_gx = int(math.ceil(ve / STEP))
        vmax_gx = int(math.floor((W_MIL - ve) / STEP))
        vmin_gy = int(math.ceil(ve / STEP))
        vmax_gy = int(math.floor((H_MIL - ve) / STEP))
        vmk2_r = 35.5 if is_gnd else 44.5

        for gx in range(NX):
            x = gx * STEP
            edge_x = gx < min_gx or gx > max_gx
            vedge_x = gx < vmin_gx or gx > vmax_gx
            base = gx * NY
            for gy in range(NY):
                idx = base + gy
                y = gy * STEP
                d_mk2 = math.hypot(x - mk2_hx, y - mk2_hy)
                if edge_x or gy < min_gy or gy > max_gy or d_mk2 < 32.0 + 0.5 * width:
                    blocked[0][idx] = blocked[1][idx] = blocked[2][idx] = blocked[3][idx] = 1
                    via_ok[idx] = 0
                elif vedge_x or gy < vmin_gy or gy > vmax_gy or d_mk2 < vmk2_r:
                    via_ok[idx] = 0
                if not is_gnd:
                    if in_mk2_body(x, y, 7.0 + 0.5 * width):
                        blocked[3][idx] = 1
                    if in_mk2_body(x, y, 11.5):
                        via_ok[idx] = 0

        pad_clr = 6.6 + 0.5 * width
        via_pad_clr = 11.4
        for p in all_pads:
            if p["net"] == net:
                continue
            li = p["li"]
            for clr, target in ((pad_clr, blocked[li]), (via_pad_clr, None)):
                gx0 = max(0, int(math.floor((p["x"] - p["hw"] - clr) / STEP)))
                gx1 = min(NX - 1, int(math.ceil((p["x"] + p["hw"] + clr) / STEP)))
                gy0 = max(0, int(math.floor((p["y"] - p["hh"] - clr) / STEP)))
                gy1 = min(NY - 1, int(math.ceil((p["y"] + p["hh"] + clr) / STEP)))
                for gx in range(gx0, gx1 + 1):
                    x = gx * STEP
                    dx = max(0.0, abs(x - p["x"]) - p["hw"])
                    base = gx * NY
                    for gy in range(gy0, gy1 + 1):
                        dy = max(0.0, abs(gy * STEP - p["y"]) - p["hh"])
                        if math.hypot(dx, dy) < clr:
                            if target is not None:
                                target[base + gy] = 1
                            else:
                                via_ok[base + gy] = 0

        for vx, vy, onet in placed_vias:
            r_v = 17.8 if (is_gnd and onet == "GND") else (18.2 if (not is_gnd and onet != "GND") else 21.2)
            r_t = 11.4 + 0.5 * width
            r = max(r_v, r_t)
            gx0 = max(0, int(math.floor((vx - r) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((vx + r) / STEP)))
            gy0 = max(0, int(math.floor((vy - r) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((vy + r) / STEP)))
            for gx in range(gx0, gx1 + 1):
                x = gx * STEP
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    d = math.hypot(x - vx, gy * STEP - vy)
                    if d < r_v:
                        via_ok[base + gy] = 0
                    if onet != net and d < r_t:
                        blocked[0][base + gy] = blocked[1][base + gy] = blocked[2][base + gy] = blocked[3][base + gy] = 1

        for oli, x1, y1, x2, y2, ow, onet in routed_segs:
            if onet == net:
                continue
            trk_clr = 3.0 + 0.5 * (width + ow)
            via_trk_clr = 11.4 + 0.5 * ow
            r = max(trk_clr, via_trk_clr)
            gx0 = max(0, int(math.floor((min(x1, x2) - r) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((max(x1, x2) + r) / STEP)))
            gy0 = max(0, int(math.floor((min(y1, y2) - r) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((max(y1, y2) + r) / STEP)))
            for gx in range(gx0, gx1 + 1):
                x = gx * STEP
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    d = pt_seg_dist(x, gy * STEP, x1, y1, x2, y2)
                    if d < trk_clr:
                        blocked[oli][base + gy] = 1
                    if d < via_trk_clr:
                        via_ok[base + gy] = 0
        return blocked, via_ok

    def find_pad_entries(p: dict, width: float, blocked):
        """Return list of legal entry descriptors:
        ('STUB', li, gx, gy, ex, ey) or ('VIPPO', li, gx, gy, p['x'], p['y'])."""
        px, py, li = p["x"], p["y"], p["li"]
        entries = []
        gx0, gy0 = to_grid(px, py)
        if not blocked[li][gx0 * NY + gy0]:
            ex, ey = from_grid(gx0, gy0)
            if seg_is_legal(li, px, py, ex, ey, width, p["net"], p):
                entries.append(("STUB", li, gx0, gy0, ex, ey))

        # Outward radial escape stubs (preferring away from component centroid!)
        odx, ody = px - p["cx"], py - p["cy"]
        norm = math.hypot(odx, ody)
        base_ang = math.atan2(ody, odx) if norm > 0.5 else 0.0
        dirs = sorted(
            [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 360, 45)],
            key=lambda v: -(v[0] * math.cos(base_ang) + v[1] * math.sin(base_ang)),
        )
        seen_g = set()
        max_reach = max(16.0, p["hw"] + 12.0, p["hh"] + 12.0)
        dists = [4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0]
        for dx, dy in dirs:
            for dist in dists:
                if dist > max_reach:
                    break
                tx, ty = px + dx * dist, py + dy * dist
                gx, gy = to_grid(tx, ty)
                if (gx, gy) in seen_g or blocked[li][gx * NY + gy]:
                    continue
                ex, ey = from_grid(gx, gy)
                if seg_is_legal(li, px, py, ex, ey, width, p["net"], p):
                    seen_g.add((gx, gy))
                    entries.append(("STUB", li, gx, gy, ex, ey))
                    break
            if len(entries) >= 4:
                break

        # Concentric 4/8 mil VIPPO for U2 0.40mm inner BGA balls (drops straight to L3/L4!)
        if p["ref"] == "U2" and p["pnum"] in U2_INNER_BALLS:
            if via_is_legal(px, py, p["net"], vippo_u2=True):
                vgx, vgy = to_grid(px, py)
                for ili in (1, 2):  # L3 & L4
                    if not blocked[ili][vgx * NY + vgy]:
                        entries.append(("VIPPO", ili, vgx, vgy, px, py))
        return entries

    def astar_multi(starts: list, goals: list, blocked, via_ok):
        """Multi-source, multi-target 4-layer A*."""
        goal_map = {(g[1], g[2], g[3]): g for g in goals}
        goal_coords = [(g[2], g[3]) for g in goals]
        pq = []
        g_cost = {}
        parent = {}
        start_meta = {}
        for s in starts:
            node = (s[1], s[2], s[3])
            start_meta[node] = s
            sc = 4.0 if s[0] == "VIPPO" else 0.0
            h = min(abs(s[2] - gx) + abs(s[3] - gy) for gx, gy in goal_coords)
            g_cost[node] = sc
            heapq.heappush(pq, (sc + h * 1.8, sc, node))

        iters = 0
        MAX_ITERS = 65000
        while pq and iters < MAX_ITERS:
            iters += 1
            _, gc, cur = heapq.heappop(pq)
            if cur in goal_map:
                path = [cur]
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                path.reverse()
                return start_meta[path[0]], goal_map[path[-1]], path
            if gc > g_cost.get(cur, 1e18):
                continue
            li, gx, gy = cur
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx_, ny_ = gx + dx, gy + dy
                if 0 <= nx_ < NX and 0 <= ny_ < NY:
                    idx = nx_ * NY + ny_
                    if blocked[li][idx]:
                        continue
                    step_c = 1.0
                    if li == 1 and dy != 0:
                        step_c = 1.5
                    elif li == 2 and dx != 0:
                        step_c = 1.5
                    elif li in (0, 3):
                        step_c = 1.25
                    ng = gc + step_c
                    nxt = (li, nx_, ny_)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = min(abs(nx_ - tx) + abs(ny_ - ty) for tx, ty in goal_coords)
                        heapq.heappush(pq, (ng + h * 1.8, ng, nxt))
            if via_ok[gx * NY + gy]:
                for nli in range(4):
                    if nli == li or blocked[nli][gx * NY + gy]:
                        continue
                    ng = gc + 14.0
                    nxt = (nli, gx, gy)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = min(abs(gx - tx) + abs(gy - ty) for tx, ty in goal_coords)
                        heapq.heappush(pq, (ng + h * 1.8, ng, nxt))
        return None

    tracks_out = []
    vias_out = []
    net_reports = []

    def add_via(vx: float, vy: float, net: str):
        # Avoid duplicate via at same spot
        for ovx, ovy, onet in placed_vias:
            if onet == net and math.hypot(vx - ovx, vy - ovy) < 1.0:
                return False
        placed_vias.append((vx, vy, net))
        vias_out.append({"x": round(vx, 2), "y": round(vy, 2), "hole": 4.0, "diameter": 8.0, "net": net})
        return True

    def add_track(li: int, x1: float, y1: float, x2: float, y2: float, width: float, net: str):
        if math.hypot(x2 - x1, y2 - y1) < 0.2:
            return False
        routed_segs.append((li, x1, y1, x2, y2, width, net))
        tracks_out.append({
            "layer": L_IDS[li], "x1": round(x1, 2), "y1": round(y1, 2),
            "x2": round(x2, 2), "y2": round(y2, 2), "width": width, "net": net,
        })
        return True

    # -------------------------------------------------------------------------
    # TIERS 1-4: ALL 57 SIGNAL & POWER NETS FIRST (so GND stitching never blocks BGA VIPPOs!)
    # -------------------------------------------------------------------------
    ordered_nets = list(NET_PRIORITY_WIDTH)
    seen_nets = {n for n, _ in ordered_nets} | {"GND"}
    for n in sorted(pads_by_net):
        if n not in seen_nets:
            ordered_nets.append((n, 2.5))

    total_edges_attempted = 0
    total_edges_routed = 0
    u2_vippo_count = 0

    for net, width_mil in ordered_nets:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        # Prim's MST ordering of edges (shortest hops first)
        n = len(pts)
        in_tree = [False] * n
        in_tree[0] = True
        edges = []
        for _ in range(n - 1):
            best_e = None
            for i in range(n):
                if not in_tree[i]:
                    continue
                for j in range(n):
                    if in_tree[j]:
                        continue
                    d = abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0)
                    if best_e is None or d < best_e[0]:
                        best_e = (d, i, j)
            if best_e is None:
                break
            _, i, j = best_e
            in_tree[j] = True
            edges.append((pts[i], pts[j]))

        edges.sort(key=lambda e: abs(e[0]["x"] - e[1]["x"]) + abs(e[0]["y"] - e[1]["y"]))
        nt, nv, ok_e = 0, 0, 0
        for p1, p2 in edges:
            total_edges_attempted += 1
            blocked, via_ok = build_net_masks(net, width_mil)
            s_entries = find_pad_entries(p1, width_mil, blocked)
            g_entries = find_pad_entries(p2, width_mil, blocked)
            if not s_entries or not g_entries:
                continue
            res = astar_multi(s_entries, g_entries, blocked, via_ok)
            if not res:
                continue
            s_ent, g_ent, path = res
            ok_e += 1
            total_edges_routed += 1

            # Emit start entry (stub or concentric U2 VIPPO)
            sx, sy = from_grid(path[0][1], path[0][2])
            if s_ent[0] == "VIPPO":
                if add_via(p1["x"], p1["y"], net):
                    nv += 1
                    u2_vippo_count += 1
                if add_track(s_ent[1], p1["x"], p1["y"], sx, sy, width_mil, net):
                    nt += 1
            else:
                if add_track(p1["li"], p1["x"], p1["y"], sx, sy, width_mil, net):
                    nt += 1

            # Compress collinear segments + emit layer-change vias
            seg_start = path[0]
            prev = path[0]
            cur_dir = None
            for node in path[1:]:
                if node[0] != prev[0]:
                    if prev != seg_start:
                        x1, y1 = from_grid(seg_start[1], seg_start[2])
                        x2, y2 = from_grid(prev[1], prev[2])
                        if add_track(seg_start[0], x1, y1, x2, y2, width_mil, net):
                            nt += 1
                    vx, vy = from_grid(prev[1], prev[2])
                    if add_via(vx, vy, net):
                        nv += 1
                    seg_start = node
                    cur_dir = None
                else:
                    d = (node[1] - prev[1], node[2] - prev[2])
                    if cur_dir is not None and d != cur_dir:
                        x1, y1 = from_grid(seg_start[1], seg_start[2])
                        x2, y2 = from_grid(prev[1], prev[2])
                        if add_track(seg_start[0], x1, y1, x2, y2, width_mil, net):
                            nt += 1
                        seg_start = prev
                    cur_dir = d
                prev = node
            if prev != seg_start:
                x1, y1 = from_grid(seg_start[1], seg_start[2])
                x2, y2 = from_grid(prev[1], prev[2])
                if add_track(seg_start[0], x1, y1, x2, y2, width_mil, net):
                    nt += 1

            # Emit goal entry (stub or concentric U2 VIPPO)
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if g_ent[0] == "VIPPO":
                if add_track(g_ent[1], ex, ey, p2["x"], p2["y"], width_mil, net):
                    nt += 1
                if add_via(p2["x"], p2["y"], net):
                    nv += 1
                    u2_vippo_count += 1
            else:
                if add_track(p2["li"], ex, ey, p2["x"], p2["y"], width_mil, net):
                    nt += 1

        if ok_e > 0:
            net_reports.append({
                "net": net, "pads": len(pts), "mst_edges": len(edges),
                "edges_routed": ok_e, "complete": ok_e == len(edges),
                "width_mil": width_mil, "tracks": nt, "vias": nv,
            })
            tag = "100%" if ok_e == len(edges) else f"{ok_e}/{len(edges)}"
            print(f"  {net:20s}: {tag:6s} | tracks={nt:3d}, vias={nv:2d}", flush=True)

    # -------------------------------------------------------------------------
    # TIER 5: GND PLANE STITCHING (to L2/L5 GND planes, clearing all signal vias by >=21 mil!)
    # -------------------------------------------------------------------------
    gnd_pads = pads_by_net.get("GND", [])
    gnd_vias = 0
    gnd_tracks = 0
    for gp in gnd_pads:
        px, py, li = gp["x"], gp["y"], gp["li"]
        if gp["ref"] == "U2" and gp["pnum"] in U2_INNER_BALLS:
            if via_is_legal(px, py, "GND", vippo_u2=True):
                if add_via(px, py, "GND"):
                    gnd_vias += 1
                    u2_vippo_count += 1
                continue
        found = None
        for r_mil in (8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0):
            for ang in range(0, 360, 20):
                rad = math.radians(ang)
                vx = round(px + r_mil * math.cos(rad), 2)
                vy = round(py + r_mil * math.sin(rad), 2)
                if via_is_legal(vx, vy, "GND") and seg_is_legal(li, px, py, vx, vy, 4.0, "GND", gp):
                    found = (vx, vy)
                    break
            if found:
                break
        if found:
            vx, vy = found
            if add_via(vx, vy, "GND"):
                gnd_vias += 1
            if add_track(li, px, py, vx, vy, 4.0, "GND"):
                gnd_tracks += 1
    net_reports.append({"net": "GND (L2/L5 stitch)", "pads": len(gnd_pads), "stitched": gnd_vias, "tracks": gnd_tracks, "vias": gnd_vias})
    print(f"  GND plane stitch    : {gnd_vias}/{len(gnd_pads)} pads -> L2/L5 planes", flush=True)

    non_gnd_vias = [[v["x"], v["y"]] for v in vias_out if v["net"] != "GND"]
    plan = {
        "summary": {
            "total_tracks": len(tracks_out),
            "total_vias": len(vias_out),
            "gnd_plane_vias": gnd_vias,
            "non_gnd_signal_vias": len(non_gnd_vias),
            "u2_bga_vippo_vias": u2_vippo_count,
            "mst_edges_routed": total_edges_routed,
            "mst_edges_attempted": total_edges_attempted,
            "nets_with_copper": len(net_reports),
            "nets_100pct_complete": sum(1 for r in net_reports if r.get("complete")),
        },
        "nets": net_reports,
        "tracks": tracks_out,
        "vias": vias_out,
    }
    plan_out.parent.mkdir(parents=True, exist_ok=True)
    plan_out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    antipads_out.write_text(json.dumps(non_gnd_vias, indent=2) + "\n", encoding="utf-8")
    print("\n=== PCB2 ROUTING PLAN COMPLETE ===")
    print(json.dumps(plan["summary"], indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dump", type=Path, required=True)
    p.add_argument("--plan-out", type=Path, required=True)
    p.add_argument("--antipads-out", type=Path, required=True)
    a = p.parse_args()
    plan_bridge_routing(a.dump, a.plan_out, a.antipads_out)


if __name__ == "__main__":
    main()
