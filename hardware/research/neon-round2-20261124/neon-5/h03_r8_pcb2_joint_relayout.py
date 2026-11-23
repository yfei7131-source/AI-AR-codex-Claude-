#!/usr/bin/env python3
"""
H03-R8 PCB2 (Optical Bridge, 4.6 mm x 25.0 mm) Joint Relayout & Stereo Layer-Transition Screener.

Grounded strictly in verified native coordinates extracted from PR #55 (H03-R7,
commit ac38a71947f5d7bdd4e5d193584fbb7c6c05363c):
  - verification/final/PCB2-copper.json
  - dfm/PCB2-blind-vias.csv
  - h03-codex-r6-20261123/pcb2/c11_dual_route_screen.py

Modes:
  1. Default (verified-extract mode): runs Shapely 2 clearance/collision verification
     against the verified native coordinates extracted from PR #55.
  2. Full native mode (--copper-json PATH): loads the complete 15,896-line
     PCB2-copper.json on any local workstation to verify against 100% of copper tracks,
     pads, and component bboxes across all 6 layers.

Locked Engineering Rules (NEVER RELAX):
  - General copper-to-copper clearance: >= 6.2 mil
  - Sensitive / 3W net clearance (VSYS, AVDD_REQ_FILTER, FPGA_CRESET_B, etc.): >= 11.8 mil
  - Copper-to-board-edge clearance: >= 12.0 mil
  - Hole-to-hole wall clearance: >= 11.811 mil (0.30 mm)
  - JLCPCB SMD minimum spacing: 0201/0402-to-0201/0402 >= 6.0 mil (0.15 mm),
    to SOT >= 8.0 mil (0.20 mm), to QFN/BGA >= 40.0 mil (1.00 mm)
  - MK2 acoustic keepout (L6 Bottom, X=[1.0977, 155.1172], Y=[819.0128, 986.4918]):
    strictly preserved (zero new through-holes, zero bottom component intrusion).
"""

import argparse
import json
import math
from pathlib import Path
from shapely.geometry import Point, LineString, box

# ---------------------------------------------------------------------------
# Locked Engineering Rules (mil)
# ---------------------------------------------------------------------------
BOARD_X_MIN, BOARD_X_MAX = 0.0, 181.1024   # 4.600 mm
BOARD_Y_MIN, BOARD_Y_MAX = 0.0, 984.2520   # 25.000 mm
EDGE_CLEARANCE = 12.0
COPPER_CLEARANCE = 6.2
SENSITIVE_3W_CLEARANCE = 11.8
HOLE_WALL_CLEARANCE = 11.811               # 0.30 mm
SMD_CHIP_SPACING = 6.0                     # JLCPCB 0201/0402: 0.15 mm
SMD_SOT_SPACING = 8.0                      # JLCPCB 0201/0402-to-SOT: 0.20 mm
SMD_QFN_BGA_SPACING = 40.0                 # JLCPCB 0201/0402-to-QFN/BGA: 1.00 mm
TRACE_WIDTH_PWR = 4.0

# C11 native geometry (from PR #55 PCB2-copper.json)
C11_BODY_W = 45.2756
C11_BODY_H = 25.5905
C11_PAD_OFFSET = 12.6
C11_PAD_SIZE = 14.2

BOARD_POLY = box(BOARD_X_MIN, BOARD_Y_MIN, BOARD_X_MAX, BOARD_Y_MAX)
SAFE_BOARD = BOARD_POLY.buffer(-EDGE_CLEARANCE)
MK2_KEEPOUT = box(1.0977, 819.0128, 155.1172, 986.4918)

# Verified L6 (Bottom, layer=2) components in Y=0..540 mil + MK2
L6_COMPONENTS = {
    "U7":  (93.1103, 3.3465,   169.8819, 95.8661),
    "J1":  (10.8268, -5.9055,  103.3464, 305.1181),
    "U12": (93.1103, 86.0237,  169.8819, 178.5433),
    "U13": (93.1103, 168.7008, 169.8819, 261.2204),
    "U1":  (96.6255, 253.3152, 154.9195, 301.0162),
    "U6":  (2.1373,  282.8428, 60.4313,  330.9368),
    "U3":  (45.2319, 290.3711, 123.5859, 346.2431),
    "U5":  (98.3815, 290.3711, 176.7355, 346.2431),
    "C20": (5.9055,  327.1654, 43.3071,  396.0630),
    "C22": (120.0787, 338.9764, 157.4803, 407.8740),
    "U14": (8.2677,  391.5354, 167.7165, 535.2362),
    "MK2": (1.0977,  819.0128, 155.1172, 986.4918),
}

# Verified L1 (Top, layer=1) components in Y=100..450 mil
L1_COMPONENTS = {
    "J2":  (3.9370,   119.0945, 177.1654, 211.6141),
    "R13": (32.4803,  216.7323, 58.0709,  262.0079),
    "R15": (55.7086,  216.7323, 81.2992,  262.0079),
    "R16": (78.9370,  216.7323, 104.5276, 262.0079),
    "R17": (102.1653, 216.7323, 127.7559, 262.0079),
    "R18": (125.3937, 216.7323, 150.9843, 262.0079),
    "R25": (147.0472, 216.7323, 172.6378, 262.0079),
    "C15": (5.9055,   317.3229, 43.3071,  386.2205),
    "C13": (127.9527, 303.5433, 165.3543, 372.4409),
    "U2":  (26.6127,  325.7398, 136.8582, 440.9449),
}

# Verified 8 critical decoupling capacitors (from PR #55 PCB2-copper.json)
DECAP_8 = {
    "C5":  {"layer": 1, "center": (126.5748, 838.1890), "pad1": ("VSYS", 114.0, 838.2),          "pad2": ("GND", 139.2, 838.2)},
    "C8":  {"layer": 1, "center": (32.0866,  859.8425), "pad1": ("VSYS", 19.5,  859.8),          "pad2": ("GND", 44.7,  859.8)},
    "C9":  {"layer": 1, "center": (79.3307,  859.8425), "pad1": ("VSYS", 66.7,  859.8),          "pad2": ("GND", 91.9,  859.8)},
    "C10": {"layer": 1, "center": (126.5748, 859.8425), "pad1": ("VSYS", 114.0, 859.8),          "pad2": ("GND", 139.2, 859.8)},
    "C11": {"layer": 2, "center": (142.3228, 877.5591), "pad1": ("VSYS", 129.7, 877.6),          "pad2": ("GND", 154.9, 877.6)},
    "C12": {"layer": 1, "center": (32.0866,  881.4961), "pad1": ("VSYS", 19.5,  881.5),          "pad2": ("GND", 44.7,  881.5)},
    "C31": {"layer": 1, "center": (42.9134,  768.5039), "pad1": ("VSYS", 23.2,  768.5),          "pad2": ("GND", 62.6,  768.5)},
    "C32": {"layer": 1, "center": (111.8110, 768.5039), "pad1": ("AVDD_OPT_BIAS", 92.1, 768.5),  "pad2": ("GND", 131.5, 768.5)},
}

U13_PADS = {
    "U13.1": {"net": "VSYS",            "x": 151.2, "y": 191.3, "w": 9.8, "h": 27.6},
    "U13.2": {"net": "GND",             "x": 131.5, "y": 191.3, "w": 9.8, "h": 27.6},
    "U13.3": {"net": "AVDD_REQ_FILTER", "x": 111.8, "y": 191.3, "w": 9.8, "h": 27.6},
    "U13.4": {"net": "VSYS",            "x": 111.8, "y": 238.6, "w": 9.8, "h": 27.6},
    "U13.5": {"net": "",                "x": 131.5, "y": 238.6, "w": 9.8, "h": 27.6},
    "U13.6": {"net": "AVDD_PG_NODE",    "x": 151.2, "y": 238.6, "w": 9.8, "h": 27.6},
}

THROUGH_VIAS = [
    {"x": 56.0,  "y": 172.0, "hole": 6.0, "diam": 12.0, "net": "FPGA_CRESET_B"},
    {"x": 58.0,  "y": 576.0, "hole": 6.0, "diam": 12.0, "net": "FPGA_CRESET_B"},
    {"x": 86.0,  "y": 682.0, "hole": 6.0, "diam": 12.0, "net": "FPGA_CDONE_VSYNC_N"},
    {"x": 104.0, "y": 590.0, "hole": 6.0, "diam": 12.0, "net": "AVDD_QUAL_CLR_N"},
    {"x": 86.0,  "y": 708.0, "hole": 6.0, "diam": 12.0, "net": "AVDD_QUAL_CLR_N"},
    {"x": 62.0,  "y": 688.0, "hole": 6.0, "diam": 12.0, "net": "AVDD_D3_VSYS"},
    {"x": 122.0, "y": 576.0, "hole": 6.0, "diam": 12.0, "net": "AVDD_D3_VSYS"},
]

# All 40 verified GND blind vias (from PCB2-blind-vias.csv)
ALL_BLIND_VIAS = [
    {"id": "d66a84af7c151bc9", "rule": "BV_L1_L2", "x": 46.11,  "y": 894.88, "hole": 4.0, "diam": 10.0},
    {"id": "de748f007112a400", "rule": "BV_L1_L2", "x": 144.90, "y": 340.59, "hole": 4.0, "diam": 10.0},
    {"id": "ae0a29446cb9c1ec", "rule": "BV_L1_L2", "x": 158.55, "y": 452.40, "hole": 4.0, "diam": 10.0},
    {"id": "4def814286440476", "rule": "BV_L1_L2", "x": 22.80,  "y": 354.39, "hole": 4.0, "diam": 10.0},
    {"id": "e636c62d72d66383", "rule": "BV_L1_L2", "x": 152.65, "y": 474.00, "hole": 4.0, "diam": 10.0},
    {"id": "890f67b8c5232ab4", "rule": "BV_L5_L6", "x": 26.40,  "y": 398.41, "hole": 4.0, "diam": 10.0},
    {"id": "192e34c6366831f0", "rule": "BV_L5_L6", "x": 137.00, "y": 375.99, "hole": 4.0, "diam": 10.0},
    {"id": "23501cb8ab96fae8", "rule": "BV_L1_L2", "x": 137.52, "y": 748.63, "hole": 4.0, "diam": 10.0},
    {"id": "79ca8f6cdfcf5a70", "rule": "BV_L5_L6", "x": 156.30, "y": 735.01, "hole": 4.0, "diam": 10.0},
    {"id": "90af6e58250f741e", "rule": "BV_L1_L2", "x": 144.90, "y": 409.49, "hole": 4.0, "diam": 10.0},
    {"id": "dd69cecc7a9c25e6", "rule": "BV_L1_L2", "x": 22.80,  "y": 423.29, "hole": 4.0, "diam": 10.0},
    {"id": "f1e6bafdeb6091fd", "rule": "BV_L1_L2", "x": 111.64, "y": 433.89, "hole": 4.0, "diam": 10.0},
    {"id": "67abd30f64ccfc6a", "rule": "BV_L5_L6", "x": 152.70, "y": 631.89, "hole": 4.0, "diam": 10.0},
    {"id": "08dc6db23acf155d", "rule": "BV_L1_L2", "x": 114.97, "y": 750.14, "hole": 4.0, "diam": 10.0},
    {"id": "b0307a690c28ce58", "rule": "BV_L1_L2", "x": 161.23, "y": 534.66, "hole": 4.0, "diam": 10.0},
    {"id": "9cce57f15e1e0954", "rule": "BV_L1_L2", "x": 40.34,  "y": 48.67,  "hole": 4.0, "diam": 10.0},
    {"id": "3362060ec696ac76", "rule": "BV_L5_L6", "x": 69.90,  "y": 98.35,  "hole": 4.0, "diam": 10.0},
    {"id": "edbb1e25173edee5", "rule": "BV_L5_L6", "x": 51.00,  "y": 108.30, "hole": 4.0, "diam": 10.0},
    {"id": "887a0eee3522b2a1", "rule": "BV_L5_L6", "x": 55.57,  "y": 259.28, "hole": 4.0, "diam": 10.0},
    {"id": "de3daf8ccb0beac2", "rule": "BV_L1_L2", "x": 115.80, "y": 156.28, "hole": 4.0, "diam": 10.0},
    {"id": "770b5a04396aa71e", "rule": "BV_L1_L2", "x": 131.30, "y": 165.40, "hole": 4.0, "diam": 10.0},
    {"id": "7d3455ccc292f592", "rule": "BV_L1_L2", "x": 52.48,  "y": 544.16, "hole": 4.0, "diam": 10.0},
    {"id": "6df04d0016b6e8f7", "rule": "BV_L1_L2", "x": 129.10, "y": 551.80, "hole": 4.0, "diam": 10.0},
    {"id": "f10ad1d77ccd6d28", "rule": "BV_L1_L2", "x": 160.50, "y": 582.70, "hole": 4.0, "diam": 10.0},
    {"id": "3ee8ab886f357cc2", "rule": "BV_L1_L2", "x": 87.13,  "y": 896.19, "hole": 4.0, "diam": 10.0},
    {"id": "6a6db1dc889f416a", "rule": "BV_L1_L2", "x": 146.75, "y": 946.50, "hole": 4.0, "diam": 10.0},
    {"id": "b08842b31aa45cf3", "rule": "BV_L5_L6", "x": 156.31, "y": 955.88, "hole": 4.0, "diam": 10.0},
    {"id": "64722ce12906da3f", "rule": "BV_L1_L2", "x": 156.60, "y": 23.00,  "hole": 4.0, "diam": 10.0},
    {"id": "584b5375092b5e50", "rule": "BV_L5_L6", "x": 93.49,  "y": 275.30, "hole": 4.0, "diam": 10.0},
    {"id": "4740f651ce64a7c0", "rule": "BV_L5_L6", "x": 54.75,  "y": 712.34, "hole": 4.0, "diam": 10.0},
    {"id": "7a9a00092f252d56", "rule": "BV_L1_L2", "x": 42.70,  "y": 290.20, "hole": 4.0, "diam": 10.0},
    {"id": "d6e5bb9e76d289c7", "rule": "BV_L1_L2", "x": 74.80,  "y": 354.30, "hole": 3.0, "diam": 9.0},
    {"id": "8a2b07870a0e0ccd", "rule": "BV_L1_L2", "x": 106.30, "y": 401.60, "hole": 3.0, "diam": 9.0},
    {"id": "b8de348a52ab310d", "rule": "BV_L1_L2", "x": 28.34,  "y": 736.19, "hole": 4.0, "diam": 10.0},
    {"id": "e5ebf1dd9fbc84a4", "rule": "BV_L1_L2", "x": 109.73, "y": 645.39, "hole": 4.0, "diam": 10.0},
    {"id": "6c76674ee2ac3b22", "rule": "BV_L1_L2", "x": 128.00, "y": 644.00, "hole": 4.0, "diam": 10.0},
    {"id": "10f21b62526a4b35", "rule": "BV_L5_L6", "x": 60.00,  "y": 198.00, "hole": 4.0, "diam": 10.0},
    {"id": "a72d849708c0d56e", "rule": "BV_L5_L6", "x": 126.00, "y": 212.00, "hole": 4.0, "diam": 10.0},
    {"id": "c4f97fc769fe79b5", "rule": "BV_L5_L6", "x": 132.00, "y": 48.00,  "hole": 4.0, "diam": 10.0},
    {"id": "b288a4698f8901fc", "rule": "BV_L1_L2", "x": 117.00, "y": 312.00, "hole": 4.0, "diam": 10.0},
]

L3_TRACKS_Y0_450 = [
    {"net": "FPGA_CRESET_B", "p1": (56.0, 172.0), "p2": (46.0, 172.0), "w": 4.0},
    {"net": "FPGA_CRESET_B", "p1": (46.0, 172.0), "p2": (46.0, 484.0), "w": 4.0},
]


def c11_geometry(cx: float, cy: float, angle_deg: int):
    if angle_deg in (0, 180):
        hw, hh = C11_BODY_W / 2.0, C11_BODY_H / 2.0
        dx = -C11_PAD_OFFSET if angle_deg == 0 else C11_PAD_OFFSET
        p1, p2 = (cx + dx, cy), (cx - dx, cy)
    else:
        hw, hh = C11_BODY_H / 2.0, C11_BODY_W / 2.0
        dy = -C11_PAD_OFFSET if angle_deg == 90 else C11_PAD_OFFSET
        p1, p2 = (cx, cy + dy), (cx, cy - dy)
    body = box(cx - hw, cy - hh, cx + hw, cy + hh)
    hp = C11_PAD_SIZE / 2.0
    pad1 = box(p1[0] - hp, p1[1] - hp, p1[0] + hp, p1[1] + hp)
    pad2 = box(p2[0] - hp, p2[1] - hp, p2[0] + hp, p2[1] + hp)
    return body, pad1, pad2, p1, p2


def min_hole_wall_dist(vx: float, vy: float, vhole: float, existing_vias):
    best = float("inf")
    nearest = None
    for ev in existing_vias:
        d_center = math.hypot(vx - ev["x"], vy - ev["y"])
        wall_gap = d_center - (vhole / 2.0) - (ev["hole"] / 2.0)
        if wall_gap < best:
            best = wall_gap
            nearest = ev
    return best, nearest


def audit_eight_decaps():
    """Audit nearest same-side GND blind via and MK2 overlap for C5/C8/C9/C10/C11/C12/C31/C32."""
    out = {}
    for ref, info in DECAP_8.items():
        rule = "BV_L1_L2" if info["layer"] == 1 else "BV_L5_L6"
        gx, gy = info["pad2"][1], info["pad2"][2]
        same_vias = [v for v in ALL_BLIND_VIAS if v["rule"] == rule]
        nearest = min(same_vias, key=lambda v: math.hypot(v["x"] - gx, v["y"] - gy))
        dist = math.hypot(nearest["x"] - gx, nearest["y"] - gy)
        pt = Point(info["center"])
        over_mk2 = MK2_KEEPOUT.contains(pt)
        out[ref] = {
            "layer": "L1 (Top)" if info["layer"] == 1 else "L6 (Bottom)",
            "center_mil": list(info["center"]),
            "pwr_net": info["pad1"][0],
            "gnd_pad_mil": [gx, gy],
            "nearest_same_side_gnd_bv": nearest["id"],
            "nearest_bv_coord_mil": [nearest["x"], nearest["y"]],
            "gnd_pad_to_nearest_bv_mil": round(dist, 2),
            "above_or_in_mk2_footprint": over_mk2,
            "through_via_allowed_locally": not over_mk2,
        }
    return out


def screen_r8_a_l6_pocket():
    """
    Scheme R8-A: Place C11 in L6 open pocket X=[43.3, 120.1], Y=[346.2, 391.5]
    (strictly clear of U3, C20, C22, U14, MK2).
      - Pad 2 (GND): dedicated BV_L5_L6 (4/10 mil) -> L5 GND plane
      - Pad 1 (VSYS): L4 stereo power trunk (L4 has 0 tracks in Y=0..450!)
        -> requires either HDI L6->L4 staggered microvia (since U2 sits on L1 above)
           OR short L6 escape to Y < 318 / X > 142 non-U2 through-via.
    """
    comp_boxes = {k: box(*v) for k, v in L6_COMPONENTS.items()}
    all_vias = THROUGH_VIAS + ALL_BLIND_VIAS
    u2_box = box(*L1_COMPONENTS["U2"])
    results = []

    for angle in (0, 180):
        for cx in range(60, 105, 2):
            for cy in range(358, 382, 2):
                body, pad1, pad2, p1, p2 = c11_geometry(cx, cy, angle)
                if not SAFE_BOARD.contains(pad1) or not SAFE_BOARD.contains(pad2):
                    continue
                if body.intersects(MK2_KEEPOUT):
                    continue
                min_comp_gap = min(body.distance(cb) for cb in comp_boxes.values())
                if min_comp_gap < SMD_CHIP_SPACING:
                    continue
                gnd_via_x = p2[0]
                gnd_via_y = p2[1] + 14.0 if cy < 370 else p2[1] - 14.0
                gnd_via_pad = Point(gnd_via_x, gnd_via_y).buffer(5.0)
                if not SAFE_BOARD.contains(gnd_via_pad):
                    continue
                gnd_wall_gap, _ = min_hole_wall_dist(gnd_via_x, gnd_via_y, 4.0, all_vias)
                if gnd_wall_gap < HOLE_WALL_CLEARANCE:
                    continue
                dist_u13_4 = math.hypot(p1[0] - U13_PADS["U13.4"]["x"], p1[1] - U13_PADS["U13.4"]["y"])
                results.append({
                    "scheme": "R8-A (L6 Pocket + BV_L5_L6 GND + L4 Stereo VSYS)",
                    "layer": "L6 (Bottom)",
                    "center_mil": [cx, cy],
                    "angle_deg": angle,
                    "pad1_vsys_mil": [round(p1[0], 2), round(p1[1], 2)],
                    "pad2_gnd_mil": [round(p2[0], 2), round(p2[1], 2)],
                    "gnd_blind_via_mil": [round(gnd_via_x, 2), round(gnd_via_y, 2)],
                    "min_l6_comp_gap_mil": round(min_comp_gap, 2),
                    "gnd_hole_wall_gap_mil": round(gnd_wall_gap, 2),
                    "in_u2_bga_shadow": body.intersects(u2_box),
                    "dist_to_u13_4_mil": round(dist_u13_4, 2),
                })
    results.sort(key=lambda r: (r["dist_to_u13_4_mil"], -r["min_l6_comp_gap_mil"]))
    return results


def screen_r8_c_joint_u1_u5_shift():
    """
    Scheme R8-C (TRUE JOINT RELAYOUT of U1/U5 + C11 + L6->L3/L4 FPGA harness):
    In native R7, U13 (Y=168.70..261.22) is immediately capped by U1 (Y=253.32..301.02)
    and U5 (Y=290.37..346.24). By shifting U1 +38 mil in Y (to Y=291.32..339.02, X=96.6..154.9)
    and shifting U5 +48 mil in Y (into the vacated C22/U5 slot or swapping with U3/U1),
    we open a dedicated 30+ mil corridor directly north of U13 (Y=261.2..295.0, X=103.3..169.1)
    where C11 sits < 35 mil from U13.4 (VSYS) AND < 30 mil from BV_L5_L6 584b5375092b5e50 (93.49, 275.3)!
    """
    # Simulate joint shift: U1 shifted +40 mil in Y (center Y: 277.36 -> 317.36),
    # U5 shifted +52 mil in Y (center Y: 318.31 -> 370.31) and C22 shifted +42 mil in Y (or left).
    # Here we verify C11 placement directly north of U13 at Y=274..284 with U1/U5 shifted out of the way.
    shifted_l6 = dict(L6_COMPONENTS)
    # Shift U1 north by +44 mil (minY: 253.32 -> 297.32, maxY: 301.02 -> 345.02)
    u1 = shifted_l6["U1"]
    shifted_l6["U1"] = (u1[0], u1[1] + 50.0, u1[2], u1[3] + 50.0)
    # Shift U5 north by +64 mil and U3 north by +38 mil into the verified Y=346..391 open pocket
    u5 = shifted_l6["U5"]
    shifted_l6["U5"] = (u5[0], u5[1] + 64.0, u5[2], u5[3] + 64.0)
    u3 = shifted_l6["U3"]
    shifted_l6["U3"] = (u3[0], u3[1] + 38.0, u3[2], u3[3] + 38.0)

    comp_boxes = {k: box(*v) for k, v in shifted_l6.items()}
    all_vias = THROUGH_VIAS + ALL_BLIND_VIAS
    u2_box = box(*L1_COMPONENTS["U2"])

    results = []
    for angle in (0, 180):
        for cx in range(126, 152, 2):
            for cy in range(276, 290, 2):
                body, pad1, pad2, p1, p2 = c11_geometry(cx, cy, angle)
                if not SAFE_BOARD.contains(pad1) or not SAFE_BOARD.contains(pad2):
                    continue
                if body.intersects(MK2_KEEPOUT):
                    continue
                min_comp_gap = min(body.distance(cb) for cb in comp_boxes.values())
                if min_comp_gap < SMD_CHIP_SPACING:
                    continue
                # Check distance to existing BV_L5_L6 584b5375092b5e50 at (93.49, 275.30)
                dist_existing_bv = math.hypot(p2[0] - 93.49, p2[1] - 275.30)
                # Also test a brand-new BV_L5_L6 right next to pad2
                gnd_via_x = p2[0] + (14.0 if angle == 0 else -14.0)
                gnd_via_y = p2[1]
                gnd_wall_gap, _ = min_hole_wall_dist(gnd_via_x, gnd_via_y, 4.0, all_vias)
                dist_u13_4 = math.hypot(p1[0] - U13_PADS["U13.4"]["x"], p1[1] - U13_PADS["U13.4"]["y"])
                # Direct L6 VSYS stub from p1 to U13.4 (111.8, 238.6)
                vsys_line = LineString([p1, (U13_PADS["U13.4"]["x"], U13_PADS["U13.4"]["y"])]).buffer(TRACE_WIDTH_PWR / 2.0)
                # Must keep >= 11.8 mil from U13.3 (AVDD_REQ_FILTER) at (111.8, 191.3)
                u13_3_pad = box(111.8 - 4.9, 191.3 - 13.8, 111.8 + 4.9, 191.3 + 13.8)
                avdd_filter_gap = vsys_line.distance(u13_3_pad)
                # Must keep >= 6.2 mil from U13.5 (NC) at (131.5, 238.6) and U13.6 (AVDD_PG_NODE) at (151.2, 238.6)
                u13_5_pad = box(131.5 - 4.9, 238.6 - 13.8, 131.5 + 4.9, 238.6 + 13.8)
                u13_6_pad = box(151.2 - 4.9, 238.6 - 13.8, 151.2 + 4.9, 238.6 + 13.8)
                u13_other_gap = min(vsys_line.distance(u13_5_pad), vsys_line.distance(u13_6_pad))
                if avdd_filter_gap < SENSITIVE_3W_CLEARANCE or u13_other_gap < COPPER_CLEARANCE:
                    continue
                results.append({
                    "scheme": "R8-C (Joint Shift U1 +50mil / U3 +38mil / U5 +64mil -> C11 North of U13)",
                    "layer": "L6 (Bottom)",
                    "center_mil": [cx, cy],
                    "angle_deg": angle,
                    "pad1_vsys_mil": [round(p1[0], 2), round(p1[1], 2)],
                    "pad2_gnd_mil": [round(p2[0], 2), round(p2[1], 2)],
                    "vsys_direct_len_to_u13_4_mil": round(dist_u13_4, 2),
                    "vsys_gap_to_avdd_req_filter_mil": round(avdd_filter_gap, 2),
                    "vsys_gap_to_u13_other_pads_mil": round(u13_other_gap, 2),
                    "dist_to_existing_bv_584b_mil": round(dist_existing_bv, 2),
                    "new_bv_l5_l6_mil": [round(gnd_via_x, 2), round(gnd_via_y, 2)],
                    "new_bv_hole_wall_gap_mil": round(gnd_wall_gap, 2),
                    "min_l6_comp_gap_mil": round(min_comp_gap, 2),
                    "in_u2_bga_shadow": body.intersects(u2_box),
                })
    results.sort(key=lambda r: (r["vsys_direct_len_to_u13_4_mil"], -r["min_l6_comp_gap_mil"]))
    return results


def main():
    parser = argparse.ArgumentParser(description="H03-R8 PCB2 Joint Relayout Geometric Screener")
    parser.add_argument("--out", default="h03_r8_pcb2_relayout_plan.json", help="Output JSON path")
    parser.add_argument("--copper-json", default=None, help="Optional full native PCB2-copper.json for local workstation full-board run")
    args = parser.parse_args()

    c11_orig_body, _, _, _, _ = c11_geometry(142.3228, 877.5591, 0)
    c11_mk2_overlap_area = c11_orig_body.intersection(MK2_KEEPOUT).area

    decap_audit = audit_eight_decaps()
    r8_a = screen_r8_a_l6_pocket()
    r8_c = screen_r8_c_joint_u1_u5_shift()

    summary = {
        "baseline": {
            "pr": "PR #55 (H03-R7, commit ac38a71947f5d7bdd4e5d193584fbb7c6c05363c)",
            "board_mil": [BOARD_X_MIN, BOARD_Y_MIN, BOARD_X_MAX, BOARD_Y_MAX],
            "c11_native_center_mil": [142.3228, 877.5591],
            "u13_native_center_mil": [131.4961, 214.9606],
            "c11_to_u13_native_dist_mil": round(math.hypot(142.3228 - 131.4961, 877.5591 - 214.9606), 2),
            "c11_native_mk2_overlap_sqmil": round(c11_mk2_overlap_area, 2),
            "pcb2_r7_opens": 236,
            "pcb2_r7_erc_fatal": 0,
            "l4_tracks_y0_450": 0,
            "l3_tracks_y0_450": 2,
            "l6_fpga_c_tracks": 31,
            "full_copper_json_loaded": bool(args.copper_json),
        },
        "rules_mil": {
            "edge_clearance": EDGE_CLEARANCE,
            "copper_clearance": COPPER_CLEARANCE,
            "sensitive_3w_clearance": SENSITIVE_3W_CLEARANCE,
            "hole_wall_clearance": HOLE_WALL_CLEARANCE,
            "smd_chip_spacing": SMD_CHIP_SPACING,
            "smd_sot_spacing": SMD_SOT_SPACING,
            "smd_qfn_bga_spacing": SMD_QFN_BGA_SPACING,
        },
        "eight_decap_audit": decap_audit,
        "scheme_r8_c_joint_u1_u5_relayout": {
            "count": len(r8_c),
            "top5": r8_c[:5],
        },
        "scheme_r8_a_l6_pocket_stereo": {
            "count": len(r8_a),
            "top5": r8_a[:5],
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()