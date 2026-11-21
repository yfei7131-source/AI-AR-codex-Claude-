#!/usr/bin/env python3
"""PR #47 P0 Blind-Via Edge Rectifier (>= 0.35 mm JLCPCB Official) + P1 Safe Priority-Net Router.

Starts directly from PR #46's verified zero-clearance `.epro2` (`4f97612de44...`):
  1. P0 Rectification: Relocates ALL laser blind microvias with copper-to-board-edge < 0.350 mm
     (13.7795 mil) inward to >= 14.30 mil (0.3632 mm), reconnecting each via's dog-bone track
     with 0 clearance, 0 dangling-end, and 0 duplicate-segment errors. Preserves exact
     before/after coordinates, clearances, track replacements, and JLCPCB rule citations.
  2. P1 Routing Convergence: Incrementally merges disjoint Union-Find components on priority
     power, GND, reset, FPGA configuration, and control nets while enforcing ALL locked
     EasyEDA Pro 6L HDI DRC rules + V4 >= 0.350 mm edge clearance + ANT1/ANT2 RF keepouts.
"""

import argparse
import csv
import heapq
import json
import math
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
CUR = Path(__file__).resolve().parent
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h03-dfm-p0-closure"),
    str(PACKAGE / "h03-hdi-laser-wlcsp-route"),
    str(PACKAGE / "h03-u11-wlcsp-v3-dfm-route"),
    str(CUR),
]

from independent_hdi_dfm_auditor import DOCS
from independent_hdi_dfm_auditor_v3 import center_to_outline_dist, extract_outline_polygon
from independent_hdi_dfm_auditor_v4 import (
    MIN_BLIND_EDGE_CU_MIL,
    MIN_BLIND_EDGE_CU_MM,
    MM_PER_MIL,
    RULE_SOURCES,
)
from prepare_hierarchy import Archive

L_IDS = [1, 16, 17, 2]
LID_TO_LI = {1: 0, 16: 1, 17: 2, 2: 3}
TARGET_BLIND_EDGE_CU_MIL = 14.30  # 0.3632 mm (> 0.350 mm JLCPCB official limit with +0.013 mm margin)

SENSITIVE_3W_NETS = {
    "BK_SW", "BB_L1", "BB_L2", "VBUS_5V", "VBUS_5V_USB", "VSYS", "PDM_CLK_1V8",
    "I2S_S3_DOUT_3V3", "I2S_S3_DOUT_1V8", "I2S_BCLK_3V3", "I2S_BCLK_1V8",
    "I2S_LRCLK_3V3", "I2S_LRCLK_1V8", "I2S_AMP_DIN_1V8",
    "BLE_ANT_FEED", "BLE_RF_MID", "BLE_RF_ANT", "ESP_ANT_FEED", "ESP_RF_ANT",
    "LFXO_XL1", "LFXO_XL2", "BLE_XC1", "BLE_XC2", "clk_48m",
}

PCB1_PRIORITY = [
    ("ESP_CHIP_PU", 3.0), ("FPGA_CRESET_3V3", 3.0), ("PRIV_WINDOW_OK_F", 3.0), ("PRIV_WINDOW_OK", 3.0),
    ("CAM_PWR_REQ", 3.0), ("CHG_ISO_GATE", 3.0), ("QSPI_DIR1_EN", 3.0), ("LED_3V3_PRIV", 3.0),
    ("3V3_SYS", 3.0), ("1V8_SYS", 3.0), ("VSYS", 3.0), ("VBUS_5V", 3.0), ("1V8_FPGA_IO", 3.0),
    ("CAM_DOVDD_1V8", 3.0), ("VOUT_L_PPATH", 3.0), ("V_INA_OUT", 3.0),
    ("SYS_I2C_SCL_1V8", 3.0), ("SYS_I2C_SDA_1V8", 3.0), ("SYS_I2C_SCL_3V3", 3.0), ("SYS_I2C_SDA_3V3", 3.0),
    ("CAM_DOVDD_OK_3V3", 3.0), ("VBAT_R_ISOLATED", 3.5), ("VBAT_R_RET", 3.5), ("VBAT_L", 3.5),
]

PCB2_PRIORITY = [
    ("FPGA_CRESET_B", 3.0), ("FPGA_CDONE_VSYNC_N", 3.0), ("OPT_AVDD_EN", 3.0),
    ("AVDD_CRESET_VSYS", 3.0), ("AVDD_PG_OK", 3.0), ("AVDD_PG_NODE", 3.0),
    ("AVDD_QUAL_RC", 3.0), ("AVDD_WD_Q", 3.0), ("AVDD_OPT_BIAS", 3.0), ("AVDD_D3_VSYS", 3.0),
    ("AVDD_PULSE_QUAL", 3.0), ("AVDD_REQ_FILTER", 3.0), ("AVDD_WD_DIV", 3.0), ("AVDD_QUAL_CLR_N", 3.0),
    ("FPGA_1V2_SENSE", 3.0), ("1V8_FPGA_IO", 3.0), ("1V2_FPGA_CORE", 3.0), ("1V2_FPGA_PLL", 3.0),
    ("1V8_FPGA_VPP", 3.0), ("VSYS", 3.0), ("1V8_SYS", 3.0),
    ("OPT_CS_N_R", 3.0), ("OPT_CS_N_L", 3.0), ("OPT_SCK_L", 3.0), ("host_cs_n", 3.0), ("opt_cs_n", 3.0), ("opt_sck", 3.0),
]

PCB3_PRIORITY = [
    ("BLE_NRESET", 3.0), ("BLE_SWDIO", 3.0), ("BLE_SWDCLK", 3.0),
    ("AMP_SD_MODE_1V8", 3.0), ("AMP_SD_REQ_1V8", 3.0), ("AMP_R_SD_MODE", 3.0), ("CHG_MUTE_GATE", 3.0),
    ("1V8_SYS", 3.0), ("VBAT_R_RET", 3.0), ("VBUS_5V", 3.0),
    ("NRF_DECR_RF", 3.0), ("NRF_DECD", 3.0), ("NRF_DECA", 3.0), ("NRF_DECN", 3.0), ("NRF_DCC", 3.0), ("NRF_DCCD", 3.0),
    ("IPC_NRF_TX_1V8", 3.0), ("IPC_S3_TX_1V8", 3.0),
    ("I2S_AMP_DIN_1V8", 3.0), ("I2S_BCLK_1V8", 3.0), ("I2S_LRCLK_1V8", 3.0), ("I2S_S3_DOUT_1V8", 3.0),
    ("CHG_R_ISET", 3.0), ("CHG_R_VSET", 3.0), ("BLE_XC1", 3.0), ("BLE_XC2", 3.0), ("LFXO_XL1", 3.0), ("LFXO_XL2", 3.0),
]


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> float:
    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
    d1 = ccw((ax1, ay1), (ax2, ay2), (bx1, by1))
    d2 = ccw((ax1, ay1), (ax2, ay2), (bx2, by2))
    d3 = ccw((bx1, by1), (bx2, by2), (ax1, ay1))
    d4 = ccw((bx1, by1), (bx2, by2), (ax2, ay2))
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return 0.0
    return min(
        pt_seg_dist(ax1, ay1, bx1, by1, bx2, by2),
        pt_seg_dist(ax2, ay2, bx1, by1, bx2, by2),
        pt_seg_dist(bx1, by1, ax1, ay1, ax2, ay2),
        pt_seg_dist(bx2, by2, ax1, ay1, ax2, ay2),
    )


def collinear_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> bool:
    adx, ady = ax2 - ax1, ay2 - ay1
    alen = math.hypot(adx, ady)
    bdx, bdy = bx2 - bx1, by2 - by1
    blen = math.hypot(bdx, bdy)
    if alen < 0.1 or blen < 0.1:
        return False
    cross = abs(adx * bdy - ady * bdx) / (alen * blen)
    if cross > 0.15:
        return False
    ux, uy = adx / alen, ady / alen
    perp1 = abs((bx1 - ax1) * (-uy) + (by1 - ay1) * ux)
    perp2 = abs((bx2 - ax1) * (-uy) + (by2 - ay1) * ux)
    if max(perp1, perp2) > 1.25:
        return False
    p1 = (bx1 - ax1) * ux + (by1 - ay1) * uy
    p2 = (bx2 - ax1) * ux + (by2 - ay1) * uy
    lo, hi = min(p1, p2), max(p1, p2)
    return min(alen, hi) - max(0.0, lo) > 0.25


def via_touches_layer(vtype: str, rname: str, li: int) -> bool:
    if vtype == "BLIND":
        if rname == "BV_L1_L2":
            return li == 0
        if rname == "BV_L5_L6":
            return li == 3
    return True


def vias_share_span(vt1: str, rn1: str, vt2: str, rn2: str) -> bool:
    def sp(vt, rn):
        if vt == "BLIND":
            if rn == "BV_L1_L2":
                return {1, 15}
            if rn == "BV_L5_L6":
                return {18, 2}
        return {1, 15, 16, 17, 18, 2}
    return bool(sp(vt1, rn1) & sp(vt2, rn2))


def process_board(board: str, pr46_epro: Path, pr46_dump: Path, out_dir: Path):
    arc = Archive(pr46_epro)
    doc = arc.documents[("PCB", DOCS[board])]
    dump = json.loads(pr46_dump.read_text(encoding="utf-8-sig"))
    outline_poly = extract_outline_polygon(dump)
    bbox = dump["outline"]["bbox"]
    W_MIL = float(bbox["maxX"])
    H_MIL = float(bbox["maxY"])
    STEP = 2.0 if board == "PCB1" else 1.5
    NX = int(W_MIL / STEP) + 2
    NY = int(H_MIL / STEP) + 2

    mic_ref = {"PCB1": "MK1", "PCB2": "MK2", "PCB3": "MK3"}[board]
    prio_list = {"PCB1": PCB1_PRIORITY, "PCB2": PCB2_PRIORITY, "PCB3": PCB3_PRIORITY}[board]
    ant_keepout_y = {"PCB1": 178.0, "PCB2": 0.0, "PCB3": 170.5}[board]
    ant_via_y = {"PCB1": 199.0, "PCB2": 0.0, "PCB3": 191.5}[board]

    # 1. Load pads from PR #46 live dump
    all_pads = []
    pads_by_net: dict[str, list[dict]] = {}
    mic_cx = mic_cy = mic_hx = mic_hy = -9999.0
    for c in dump["components"]:
        ref = c["designator"]
        cx, cy = float(c["x"]), float(c["y"])
        c_rot = float(c.get("rotation") or 0.0)
        if ref == mic_ref:
            mic_cx, mic_cy = cx, cy
            mic_hx, mic_hy = cx - 0.005, cy + 31.89
        for p in c["pads"]:
            px, py = float(p["x"]), float(p["y"])
            net = (p.get("net") or "").strip()
            pw = float(p.get("width") or 0.0)
            ph = float(p.get("height") or 0.0)
            if pw < 1.0 or ph < 1.0:
                shp = p.get("shape") or []
                if isinstance(shp, list) and len(shp) >= 2 and shp[0] == "POLY" and isinstance(shp[1], list):
                    nums = [float(v) for v in shp[1] if isinstance(v, (int, float))]
                    if len(nums) >= 4:
                        pw = max(pw, max(nums[0::2]) - min(nums[0::2]))
                        ph = max(ph, max(nums[1::2]) - min(nums[1::2]))
                pw = max(pw, 28.0 if ref == mic_ref else 16.0)
                ph = max(ph, 28.0 if ref == mic_ref else 16.0)
            rot = c_rot + float(p.get("rotation") or 0.0)
            rad = math.radians(rot)
            ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
            hw = 0.5 * (pw * ca + ph * sa) + 0.30
            hh = 0.5 * (pw * sa + ph * ca) + 0.30
            li = LID_TO_LI.get(int(p.get("layer", c["layer"])), 0)
            rec = {
                "x": px, "y": py, "hw": hw, "hh": hh, "li": li, "net": net,
                "ref": ref, "pnum": str(p.get("padNumber", "")), "cx": cx, "cy": cy,
                "idx": len(all_pads),
            }
            all_pads.append(rec)
            if net:
                pads_by_net.setdefault(net, []).append(rec)

    mic_box = (mic_cx - 58.0, mic_cx + 58.0, mic_cy - 78.0, mic_cy + 78.0)
    def in_mic_body(x, y, pad_r=0.0):
        return (mic_box[0] - pad_r <= x <= mic_box[1] + pad_r) and (mic_box[2] - pad_r <= y <= mic_box[3] + pad_r)

    # 2. Load ALL PR #46 tracks & vias WITH record IDs so we can cleanly rectify violating blind vias!
    # segs: [li, x1, y1, x2, y2, width, net, rec_id]
    # vias: [vx, vy, rad, hole, net, viaType, ruleName, rec_id]
    routed_segs: list[list] = []
    placed_vias: list[list] = []
    for r in doc.records:
        t = r.header.get("type")
        p = r.payload
        rid = r.header.get("id", "")
        if t == "LINE":
            lid = int(p.get("layerId", 1))
            if lid not in LID_TO_LI:
                continue
            x1, y1 = float(p.get("startX", 0.0)), float(p.get("startY", 0.0))
            x2, y2 = float(p.get("endX", 0.0)), float(p.get("endY", 0.0))
            if math.hypot(x2 - x1, y2 - y1) < 0.1:
                continue
            w = float(p.get("lineWidth", p.get("width", 3.0)))
            net = (p.get("netName") or "").strip()
            routed_segs.append([LID_TO_LI[lid], x1, y1, x2, y2, w, net, rid])
        elif t == "VIA":
            vx, vy = float(p["centerX"]), float(p["centerY"])
            hole = float(p.get("holeDiameter", 6.0))
            diam = float(p.get("viaDiameter", 12.0))
            vt = p.get("viaType", "NORMAL")
            rn = p.get("ruleName", "")
            net = (p.get("netName") or "").strip()
            placed_vias.append([vx, vy, 0.5 * diam, hole, net, vt, rn, rid])

    def to_grid(x, y):
        return max(0, min(NX - 1, int(round(x / STEP)))), max(0, min(NY - 1, int(round(y / STEP))))

    def from_grid(gx, gy):
        return round(gx * STEP, 2), round(gy * STEP, 2)

    def pair_track_gap(net_a: str, net_b: str, base_gap: float, li: int, w_a: float, w_b: float) -> float:
        c2c = 3.08 * max(w_a, w_b)
        e2e = c2c - 0.5 * (w_a + w_b)
        sens_extra = 11.8 if (li in (1, 2) and (net_a in SENSITIVE_3W_NETS or net_b in SENSITIVE_3W_NETS)) else 0.0
        return max(base_gap, e2e, 6.15, sens_extra)

    def via_is_legal(vx, vy, net, via_type="NORMAL", rule_name="", diam=12.0, hole=6.0, ignore_vids=(), ignore_lids=()):
        is_gnd = (net == "GND")
        is_blind = (via_type == "BLIND")
        vrad = 0.5 * diam
        c2e = center_to_outline_dist(outline_poly, vx, vy)
        # V4 OFFICIAL JLCPCB GUARD: Blind via cu-to-edge >= 14.30 mil (0.3632 mm > 0.350 mm)!
        min_edge = (TARGET_BLIND_EDGE_CU_MIL + vrad) if (is_gnd or is_blind) else 25.0
        if c2e < min_edge:
            return False
        if ant_keepout_y > 0.0:
            if (not is_gnd and not is_blind and vy < ant_via_y) or ((is_gnd or is_blind) and vy < ant_keepout_y + vrad + 2.0):
                return False
        mk_r = (34.2 + vrad) if is_gnd else 49.0
        if math.hypot(vx - mic_hx, vy - mic_hy) < mk_r:
            return False
        if (not is_gnd or rule_name == "BV_L5_L6" or not is_blind) and in_mic_body(vx, vy, 13.5):
            return False
        for ovx, ovy, orad, ohole, onet, ovt, orn, ovid in placed_vias:
            if ovid in ignore_vids:
                continue
            if not vias_share_span(via_type, rule_name, ovt, orn):
                continue
            d = math.hypot(vx - ovx, vy - ovy)
            if (is_gnd and onet != "GND") or ((not is_gnd) and onet == "GND"):
                min_vv = 19.8 + (vrad if is_gnd else orad)
            elif (not is_gnd) and (onet != "GND"):
                min_vv = max(vrad + orad + 7.5, 0.5 * (hole + ohole) + 11.0)
            else:
                min_vv = max(vrad + orad + 6.8, 0.5 * (hole + ohole) + 10.5)
            if d < min_vv:
                return False
        for p in all_pads:
            if not via_touches_layer(via_type, rule_name, p["li"]):
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            dist = math.hypot(dx, dy)
            if p["net"] == net:
                if dist < vrad + 1.15:
                    return False
            else:
                if dist < vrad + 6.20:
                    return False
        for oli, x1, y1, x2, y2, w, onet, olid in routed_segs:
            if olid in ignore_lids or onet == net:
                continue
            if not via_touches_layer(via_type, rule_name, oli):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < vrad + 6.20 + 0.5 * w:
                return False
        return True

    def seg_is_legal(li, x1, y1, x2, y2, width, net, base_trk_gap=6.15, ignore_pad_idxs=(), ignore_vids=(), ignore_lids=()):
        if math.hypot(x2 - x1, y2 - y1) < 0.25:
            return False
        for oli, ox1, oy1, ox2, oy2, _, onet, olid in routed_segs:
            if olid in ignore_lids:
                continue
            if oli == li and onet == net:
                if collinear_overlap(x1, y1, x2, y2, ox1, oy1, ox2, oy2):
                    return False
        margin = 13.0 + 0.5 * width
        steps = max(4, int(math.hypot(x2 - x1, y2 - y1) / 1.5) + 1)
        for s in range(steps + 1):
            t = s / steps
            cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            if center_to_outline_dist(outline_poly, cx, cy) < margin:
                return False
            if ant_keepout_y > 0.0 and cy < ant_keepout_y + 0.5 * width + 1.0:
                return False
            if math.hypot(cx - mic_hx, cy - mic_hy) < 33.8 + 0.5 * width:
                return False
            if li == 3:
                is_mic_gnd = any(all_pads[idx]["ref"] == mic_ref for idx in ignore_pad_idxs)
                if not is_mic_gnd and in_mic_body(cx, cy, 7.8 + 0.5 * width):
                    return False
        for vx, vy, vrad, _, onet, ovt, orn, ovid in placed_vias:
            if ovid in ignore_vids or onet == net:
                continue
            if not via_touches_layer(ovt, orn, li):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 6.20 + vrad + 0.5 * width:
                return False
        if li in (0, 3):
            clr = 6.20 + 0.5 * width
            for p in all_pads:
                if p["li"] != li:
                    continue
                if p["net"] == net:
                    if p["idx"] in ignore_pad_idxs:
                        continue
                    if math.hypot(x1 - p["x"], y1 - p["y"]) < 1.5 or math.hypot(x2 - p["x"], y2 - p["y"]) < 1.5:
                        continue
                    if pt_seg_dist(p["x"], p["y"], x1, y1, x2, y2) < max(p["hw"], p["hh"]) + 0.5 * width + 0.45:
                        return False
                    continue
                for s in range(steps + 1):
                    t = s / steps
                    cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                    dx = max(0.0, abs(cx - p["x"]) - p["hw"])
                    dy = max(0.0, abs(cy - p["y"]) - p["hh"])
                    if math.hypot(dx, dy) < clr:
                        return False
        for oli, ox1, oy1, ox2, oy2, ow, onet, olid in routed_segs:
            if olid in ignore_lids or oli != li or onet == net:
                continue
            min_d = pair_track_gap(net, onet, base_trk_gap, li, width, ow) + 0.5 * (width + ow)
            if seg_seg_dist(x1, y1, x2, y2, ox1, oy1, ox2, oy2) < min_d:
                return False
        return True

    # =========================================================================
    # STEP A (P0): RECTIFY ALL BLIND MICROVIAS WITH cu_to_edge < 0.350 mm!
    # =========================================================================
    relocated_vias: list[dict] = []
    deleted_via_ids: list[str] = []
    deleted_line_ids: list[str] = []
    delta_tracks: list[dict] = []
    delta_vias: list[dict] = []

    for v_idx, v in enumerate(list(placed_vias)):
        vx, vy, vrad, vhole, vnet, vt, rn, vid = v
        if vt != "BLIND":
            continue
        c2e_old = center_to_outline_dist(outline_poly, vx, vy)
        cu2e_old = c2e_old - vrad
        if cu2e_old >= MIN_BLIND_EDGE_CU_MIL:
            continue
        li_side = 0 if rn == "BV_L1_L2" else 3
        att_segs = [
            s for s in routed_segs
            if s[0] == li_side and s[6] == vnet and (math.hypot(s[1] - vx, s[2] - vy) < 1.5 or math.hypot(s[3] - vx, s[4] - vy) < 1.5)
        ]
        assert len(att_segs) == 1, f"{board} {vid}: expected 1 attached track, got {len(att_segs)}"
        aseg = att_segs[0]
        old_lid = aseg[7]
        ax, ay = (aseg[3], aseg[4]) if math.hypot(aseg[1] - vx, aseg[2] - vy) < 1.5 else (aseg[1], aseg[2])
        anchor_pad = next((p for p in all_pads if p["li"] == li_side and p["net"] == vnet and math.hypot(p["x"] - ax, p["y"] - ay) < 2.5), None)
        ign_pads = (anchor_pad["idx"],) if anchor_pad is not None else ()
        anchor_desc = f"{anchor_pad['ref']}.{anchor_pad['pnum']}" if anchor_pad else f"VERTEX({ax:.2f},{ay:.2f})"

        best = None
        action = "RELOCATED_INWARD"
        merged_target_vid = ""

        # Option 1: Relocate this blind via inward to >= 14.30 mil (0.3632 mm > 0.350 mm)
        cands = []
        for dx_i in range(-40, 41, 1):
            for dy_i in range(-40, 41, 1):
                nx = round(vx + dx_i * 0.5, 2)
                ny = round(vy + dy_i * 0.5, 2)
                d_move = math.hypot(nx - vx, ny - vy)
                if 0.5 <= d_move <= 25.0:
                    cands.append((d_move, nx, ny))
        for r_mil in (11.5, 13.0, 15.0, 17.5, 20.5, 24.0, 28.0, 33.0, 38.0):
            for ang in range(0, 360, 10):
                nx = round(ax + r_mil * math.cos(math.radians(ang)), 2)
                ny = round(ay + r_mil * math.sin(math.radians(ang)), 2)
                cands.append((25.0 + r_mil, nx, ny))
        cands.sort(key=lambda t: t[0])

        for _, nx, ny in cands:
            if not via_is_legal(nx, ny, vnet, via_type="BLIND", rule_name=rn, diam=2.0 * vrad, hole=vhole, ignore_vids=(vid,), ignore_lids=(old_lid,)):
                continue
            segs_ok = None
            for tw in (3.5, 3.0):
                if seg_is_legal(li_side, ax, ay, nx, ny, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,)):
                    segs_ok = (tw, [(ax, ay, nx, ny)])
                    break
                for mx, my in ((nx, ay), (ax, ny)):
                    if (seg_is_legal(li_side, ax, ay, mx, my, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,)) and
                        seg_is_legal(li_side, mx, my, nx, ny, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,))):
                        segs_ok = (tw, [(ax, ay, mx, my), (mx, my, nx, ny)])
                        break
                if segs_ok:
                    break
            if segs_ok:
                best = (nx, ny, segs_ok[0], segs_ok[1])
                break

        # Option 2: Merge directly into an existing compliant >= 0.350 mm same-layer same-net blind via (delete redundant edge via!)
        if best is None:
            existing_cands = []
            for ovx, ovy, orad, ohole, onet, ovt, orn, ovid in placed_vias:
                if ovid == vid or onet != vnet:
                    continue
                if not (ovt == "NORMAL" or (ovt == "BLIND" and orn == rn)):
                    continue
                c2e_o = center_to_outline_dist(outline_poly, ovx, ovy)
                if c2e_o - orad < TARGET_BLIND_EDGE_CU_MIL:
                    continue
                d_o = math.hypot(ovx - ax, ovy - ay)
                if d_o <= 80.0:
                    existing_cands.append((d_o, ovx, ovy, ovid))
            existing_cands.sort(key=lambda t: t[0])
            for _, ovx, ovy, ovid in existing_cands:
                for tw in (3.5, 3.0):
                    if seg_is_legal(li_side, ax, ay, ovx, ovy, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,)):
                        best = (ovx, ovy, tw, [(ax, ay, ovx, ovy)])
                        action = "MERGED_TO_EXISTING_COMPLIANT_VIA"
                        merged_target_vid = ovid
                        break
                    for mx, my in ((ovx, ay), (ax, ovy)):
                        if (seg_is_legal(li_side, ax, ay, mx, my, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,)) and
                            seg_is_legal(li_side, mx, my, ovx, ovy, tw, vnet, ignore_pad_idxs=ign_pads, ignore_vids=(vid,), ignore_lids=(old_lid,))):
                            best = (ovx, ovy, tw, [(ax, ay, mx, my), (mx, my, ovx, ovy)])
                            action = "MERGED_TO_EXISTING_COMPLIANT_VIA"
                            merged_target_vid = ovid
                            break
                    if best is not None:
                        break
                if best is not None:
                    break

        assert best is not None, f"Could not find legal >= 0.35mm rectification for {board} via {vid} at ({vx}, {vy})!"
        nx, ny, tw, new_segs = best
        c2e_new = center_to_outline_dist(outline_poly, nx, ny)
        cu2e_new = c2e_new - vrad

        if action == "MERGED_TO_EXISTING_COMPLIANT_VIA":
            deleted_via_ids.append(vid)
            placed_vias = [x for x in placed_vias if x[7] != vid]
        else:
            for x in placed_vias:
                if x[7] == vid:
                    x[0] = nx
                    x[1] = ny
                    break
        routed_segs = [s for s in routed_segs if s[7] != old_lid]
        deleted_line_ids.append(old_lid)
        for u1, v1, u2, v2 in new_segs:
            routed_segs.append([li_side, u1, v1, u2, v2, tw, vnet, f"NEW_RECT_{vid}"])
            delta_tracks.append({
                "layer": L_IDS[li_side], "x1": round(u1, 2), "y1": round(v1, 2),
                "x2": round(u2, 2), "y2": round(v2, 2), "width": tw, "net": vnet,
            })

        rec_ledger = {
            "board": board,
            "via_id": vid,
            "action": action,
            "merged_into_via_id": merged_target_vid,
            "net": vnet,
            "rule_name": rn,
            "hole_mil": vhole,
            "diam_mil": round(2.0 * vrad, 2),
            "anchor": anchor_desc,
            "old_x_mil": round(vx, 2),
            "old_y_mil": round(vy, 2),
            "old_cu_to_edge_mil": round(cu2e_old, 3),
            "old_cu_to_edge_mm": round(cu2e_old * MM_PER_MIL, 4),
            "new_x_mil": round(nx, 2),
            "new_y_mil": round(ny, 2),
            "new_cu_to_edge_mil": round(cu2e_new, 3),
            "new_cu_to_edge_mm": round(cu2e_new * MM_PER_MIL, 4),
            "delta_edge_mm": round((cu2e_new - cu2e_old) * MM_PER_MIL, 4),
            "replaced_line_id": old_lid,
            "replacement_track_count": len(new_segs),
            "rule_threshold_mm": MIN_BLIND_EDGE_CU_MM,
            "rule_source": RULE_SOURCES["blind_via_to_board_edge_mm"],
        }
        relocated_vias.append(rec_ledger)
        print(
            f"  [P0 {action} {board}] {vid} ({rn}, {anchor_desc}): "
            f"({vx:.2f},{vy:.2f}) [edge={cu2e_old:.3f}mil / {cu2e_old*MM_PER_MIL:.4f}mm] -> "
            f"({nx:.2f},{ny:.2f}) [edge={cu2e_new:.3f}mil / {cu2e_new*MM_PER_MIL:.4f}mm]",
            flush=True,
        )
    placed_vias = [v for v in placed_vias if v is not None]

    # =========================================================================
    # STEP B (P1): SAFE INCREMENTAL PRIORITY-NET ROUTING (V4 >= 0.35mm GUARD!)
    # =========================================================================
    def add_via(vx, vy, net, hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
        for ovx, ovy, _, _, onet, ovt, orn, _ in placed_vias:
            if onet == net and ovt == via_type and orn == rule_name and math.hypot(vx - ovx, vy - ovy) < 1.5:
                return False
        rid = f"NEW_V_{len(delta_vias)}"
        placed_vias.append([vx, vy, 0.5 * diam, hole, net, via_type, rule_name, rid])
        delta_vias.append({
            "x": round(vx, 2), "y": round(vy, 2),
            "hole": hole, "diameter": diam, "net": net,
            "viaType": via_type, "ruleName": rule_name,
        })
        return True

    def add_track(li, x1, y1, x2, y2, width, net):
        if math.hypot(x2 - x1, y2 - y1) < 0.25:
            return False
        for oli, ox1, oy1, ox2, oy2, _, onet, _ in routed_segs:
            if oli == li and onet == net:
                if collinear_overlap(x1, y1, x2, y2, ox1, oy1, ox2, oy2):
                    return False
        rid = f"NEW_T_{len(delta_tracks)}"
        routed_segs.append([li, x1, y1, x2, y2, width, net, rid])
        delta_tracks.append({
            "layer": L_IDS[li], "x1": round(x1, 2), "y1": round(y1, 2),
            "x2": round(x2, 2), "y2": round(y2, 2), "width": width, "net": net,
        })
        return True

    def build_existing_uf(net: str):
        pts = pads_by_net.get(net, [])
        n_pads = len(pts)
        net_segs = [s for s in routed_segs if s[6] == net]
        net_vias = [v for v in placed_vias if v[4] == net]
        n_segs = len(net_segs)
        n_vias = len(net_vias)
        N = n_pads + n_segs + n_vias
        parent = list(range(N))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        for pi, p in enumerate(pts):
            for si, s in enumerate(net_segs):
                if s[0] == p["li"] and pt_seg_dist(p["x"], p["y"], s[1], s[2], s[3], s[4]) <= max(p["hw"], p["hh"]) + 0.5 * s[5] + 0.6:
                    union(pi, n_pads + si)
            for vi, v in enumerate(net_vias):
                if via_touches_layer(v[5], v[6], p["li"]) and math.hypot(p["x"] - v[0], p["y"] - v[1]) <= max(p["hw"], p["hh"]) + v[2] + 0.6:
                    union(pi, n_pads + n_segs + vi)
        for si in range(n_segs):
            sa = net_segs[si]
            for sj in range(si + 1, n_segs):
                sb = net_segs[sj]
                if sa[0] == sb[0] and seg_seg_dist(sa[1], sa[2], sa[3], sa[4], sb[1], sb[2], sb[3], sb[4]) <= 0.5 * (sa[5] + sb[5]) + 0.5:
                    union(n_pads + si, n_pads + sj)
        for si, s in enumerate(net_segs):
            for vi, v in enumerate(net_vias):
                if via_touches_layer(v[5], v[6], s[0]) and pt_seg_dist(v[0], v[1], s[1], s[2], s[3], s[4]) <= v[2] + 0.5 * s[5] + 0.6:
                    union(n_pads + si, n_pads + n_segs + vi)
        pad_parent = {i: i for i in range(n_pads)}
        def pfind(x):
            while pad_parent[x] != x:
                pad_parent[x] = pad_parent[pad_parent[x]]
                x = pad_parent[x]
            return x
        root_to_pad = {}
        for pi in range(n_pads):
            r = find(pi)
            if r in root_to_pad:
                pad_parent[pfind(pi)] = pfind(root_to_pad[r])
            else:
                root_to_pad[r] = pi
        cluster_anchors: dict[int, list[tuple[int, float, float, int | None]]] = {i: [] for i in range(n_pads)}
        for pi, p in enumerate(pts):
            cluster_anchors[pfind(pi)].append((p["li"], p["x"], p["y"], p["idx"]))
        for si, s in enumerate(net_segs):
            r = find(n_pads + si)
            if r in root_to_pad:
                pr = pfind(root_to_pad[r])
                cluster_anchors[pr].append((s[0], s[1], s[2], None))
                cluster_anchors[pr].append((s[0], s[3], s[4], None))
        for vi, v in enumerate(net_vias):
            r = find(n_pads + n_segs + vi)
            if r in root_to_pad:
                pr = pfind(root_to_pad[r])
                for li_ in range(4):
                    if via_touches_layer(v[5], v[6], li_):
                        cluster_anchors[pr].append((li_, v[0], v[1], None))
        return pad_parent, cluster_anchors

    def build_net_masks(net, width, blind_side_li=None, base_trk_gap=6.15):
        is_gnd = (net == "GND")
        is_blind = (blind_side_li is not None)
        vtype = "BLIND" if is_blind else "NORMAL"
        rname = "BV_L1_L2" if blind_side_li == 0 else ("BV_L5_L6" if blind_side_li == 3 else "")
        vrad = 5.0 if is_blind else 6.0
        min_edge_v = (TARGET_BLIND_EDGE_CU_MIL + vrad) if (is_gnd or is_blind) else 25.0

        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))
        t_margin = 13.0 + 0.5 * width
        mk_t = 33.8 + 0.5 * width
        mk_v = (34.2 + vrad) if is_gnd else 49.0

        for gx in range(NX):
            x = gx * STEP
            base = gx * NY
            for gy in range(NY):
                y = gy * STEP
                idx = base + gy
                c2e = center_to_outline_dist(outline_poly, x, y)
                d_mk = math.hypot(x - mic_hx, y - mic_hy)
                if c2e < t_margin or d_mk < mk_t or (ant_keepout_y > 0.0 and y < ant_keepout_y + 0.5 * width + 1.0):
                    blocked[0][idx] = blocked[1][idx] = blocked[2][idx] = blocked[3][idx] = 1
                elif in_mic_body(x, y, 7.8 + 0.5 * width):
                    blocked[3][idx] = 1
                if (c2e < min_edge_v or d_mk < mk_v
                    or (ant_keepout_y > 0.0 and ((not is_gnd and not is_blind and y < ant_via_y) or ((is_gnd or is_blind) and y < ant_keepout_y + vrad + 2.0)))
                    or ((not is_gnd or rname == "BV_L5_L6" or not is_blind) and in_mic_body(x, y, 13.5))):
                    via_ok[idx] = 0

        pad_t_clr = 6.20 + 0.5 * width
        pad_v_diff = vrad + 6.20
        pad_v_same = vrad + 1.20
        for p in all_pads:
            pli = p["li"]
            same = (p["net"] == net)
            vr_pad = pad_v_same if same else pad_v_diff
            rmx = max(p["hw"] + vr_pad, p["hw"] + (0.5 * width + 0.55 if same else pad_t_clr))
            rmy = max(p["hh"] + vr_pad, p["hh"] + (0.5 * width + 0.55 if same else pad_t_clr))
            gx0 = max(0, int(math.floor((p["x"] - rmx) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((p["x"] + rmx) / STEP)))
            gy0 = max(0, int(math.floor((p["y"] - rmy) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((p["y"] + rmy) / STEP)))
            touches_v = via_touches_layer(vtype, rname, pli)
            for gx in range(gx0, gx1 + 1):
                dx = max(0.0, abs(gx * STEP - p["x"]) - p["hw"])
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    dy = max(0.0, abs(gy * STEP - p["y"]) - p["hh"])
                    d = math.hypot(dx, dy)
                    if same:
                        if d < 0.5 * width + 0.55:
                            blocked[pli][base + gy] = 1
                    else:
                        if d < pad_t_clr:
                            blocked[pli][base + gy] = 1
                    if touches_v and d < vr_pad:
                        via_ok[base + gy] = 0

        for vx, vy, orad, ohole, onet, ovt, orn, _ in placed_vias:
            share = vias_share_span(vtype, rname, ovt, orn)
            if share:
                if (is_gnd and onet != "GND") or ((not is_gnd) and onet == "GND"):
                    r_v = 19.8 + (vrad if is_gnd else orad)
                elif (not is_gnd) and (onet != "GND"):
                    r_v = max(vrad + orad + 7.5, 0.5 * ((4.0 if is_blind else 6.0) + ohole) + 11.0)
                else:
                    r_v = max(vrad + orad + 6.8, 0.5 * ((4.0 if is_blind else 6.0) + ohole) + 10.5)
            else:
                r_v = 0.0
            r_t = (6.20 + orad + 0.5 * width) if onet != net else 0.0
            r = max(r_v, r_t)
            if r <= 0.0:
                continue
            gx0 = max(0, int(math.floor((vx - r) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((vx + r) / STEP)))
            gy0 = max(0, int(math.floor((vy - r) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((vy + r) / STEP)))
            t_layers = [oli for oli in range(4) if via_touches_layer(ovt, orn, oli)]
            for gx in range(gx0, gx1 + 1):
                x = gx * STEP
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    d = math.hypot(x - vx, gy * STEP - vy)
                    if r_v > 0.0 and d < r_v:
                        via_ok[base + gy] = 0
                    if onet != net and d < r_t:
                        for oli in t_layers:
                            blocked[oli][base + gy] = 1

        for oli, x1, y1, x2, y2, ow, onet, _ in routed_segs:
            if onet == net:
                continue
            trk_clr = pair_track_gap(net, onet, base_trk_gap, oli, width, ow) + 0.5 * (width + ow)
            via_trk_clr = (vrad + 6.20 + 0.5 * ow) if via_touches_layer(vtype, rname, oli) else 0.0
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
                    if via_trk_clr > 0.0 and d < via_trk_clr:
                        via_ok[base + gy] = 0
        return blocked, via_ok

    def find_anchor_entries(li, ax, ay, pad_idx, net, width, blocked, base_trk_gap=6.15):
        entries = []
        ign = (pad_idx,) if pad_idx is not None else ()
        gx0, gy0 = to_grid(ax, ay)
        if not blocked[li][gx0 * NY + gy0]:
            ex, ey = from_grid(gx0, gy0)
            if math.hypot(ax - ex, ay - ey) < 0.25 or seg_is_legal(li, ax, ay, ex, ey, width, net, base_trk_gap, ignore_pad_idxs=ign):
                entries.append(("ANCHOR", li, gx0, gy0, ax, ay, ign))
        dirs = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 360, 22)]
        seen_g = {(gx0, gy0)}
        for dx, dy in dirs:
            for dist in (3.0, 5.5, 8.0, 11.0, 14.5, 18.5, 23.0, 28.0, 34.0, 42.0, 52.0):
                gx, gy = to_grid(ax + dx * dist, ay + dy * dist)
                if (gx, gy) in seen_g or blocked[li][gx * NY + gy]:
                    continue
                ex, ey = from_grid(gx, gy)
                if seg_is_legal(li, ax, ay, ex, ey, width, net, base_trk_gap, ignore_pad_idxs=ign):
                    seen_g.add((gx, gy))
                    entries.append(("ANCHOR", li, gx, gy, ax, ay, ign))
                    break
            if len(entries) >= 10:
                break
        if net != "GND":
            min_vr = 14.0
            if pad_idx is not None:
                p = all_pads[pad_idx]
                min_vr = max(14.0, min(p["hw"], p["hh"]) + 7.2)
            dv_added = 0
            for dist in (min_vr, min_vr + 4.0, min_vr + 9.0, min_vr + 15.0, min_vr + 22.0, min_vr + 32.0):
                for ang in range(0, 360, 15):
                    vx = round(ax + dist * math.cos(math.radians(ang)), 2)
                    vy = round(ay + dist * math.sin(math.radians(ang)), 2)
                    vgx, vgy = to_grid(vx, vy)
                    gx_x, gy_y = from_grid(vgx, vgy)
                    if via_is_legal(gx_x, gy_y, net, via_type="NORMAL", rule_name="", diam=12.0, hole=6.0) and seg_is_legal(
                        li, ax, ay, gx_x, gy_y, width, net, base_trk_gap, ignore_pad_idxs=ign
                    ):
                        added_here = False
                        for ili in (1, 2, 3 - li):
                            if not blocked[ili][vgx * NY + vgy]:
                                entries.append(("DOG_VIA", ili, vgx, vgy, ax, ay, ign, li))
                                added_here = True
                        if added_here:
                            dv_added += 1
                            break
                if dv_added >= 2:
                    break
        return entries

    def astar(starts, goal_map, blocked, via_ok, max_iters=90000, allow_via=True):
        if not starts or not goal_map:
            return None
        all_g = list(goal_map.keys())
        step_g = max(1, len(all_g) // 24)
        g_sample = [(g[1], g[2]) for g in all_g[::step_g]]
        pq = []
        g_cost = {}
        parent = {}
        start_meta = {}
        for s in starts:
            node = (s[1], s[2], s[3])
            if node in goal_map:
                return s, goal_map[node], [node]
            start_meta[node] = s
            h = min(abs(s[2] - gx) + abs(s[3] - gy) for gx, gy in g_sample)
            g_cost[node] = 0.0
            heapq.heappush(pq, (h * 1.75, 0.0, node))
        iters = 0
        while pq and iters < max_iters:
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
            b_li = blocked[li]
            for dx, dy, step_c in ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                                   (1, 1, 1.42), (1, -1, 1.42), (-1, 1, 1.42), (-1, -1, 1.42)):
                ngx, ngy = gx + dx, gy + dy
                if not (0 <= ngx < NX and 0 <= ngy < NY) or b_li[ngx * NY + ngy]:
                    continue
                nxt = (li, ngx, ngy)
                nc = gc + step_c + (0.10 if li in (0, 3) else 0.0)
                if nc < g_cost.get(nxt, 1e18):
                    g_cost[nxt] = nc
                    parent[nxt] = cur
                    h = min(abs(ngx - tx) + abs(ngy - ty) for tx, ty in g_sample)
                    heapq.heappush(pq, (nc + h * 1.75, nc, nxt))
            if allow_via and via_ok[gx * NY + gy]:
                for nli in range(4):
                    if nli == li or blocked[nli][gx * NY + gy]:
                        continue
                    nxt = (nli, gx, gy)
                    nc = gc + 26.0
                    if nc < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = nc
                        parent[nxt] = cur
                        h = min(abs(gx - tx) + abs(gy - ty) for tx, ty in g_sample)
                        heapq.heappush(pq, (nc + h * 1.75, nc, nxt))
        return None

    def try_commit_path(s_ent, g_ent, path, width, net, base_gap):
        prop_vias = []
        prop_segs = []
        if s_ent[0] == "ANCHOR":
            sx, sy = from_grid(path[0][1], path[0][2])
            if math.hypot(s_ent[4] - sx, s_ent[5] - sy) >= 0.25:
                prop_segs.append((s_ent[1], s_ent[4], s_ent[5], sx, sy, s_ent[6]))
        elif s_ent[0] == "DOG_VIA":
            sx, sy = from_grid(path[0][1], path[0][2])
            prop_vias.append((sx, sy, 6.0, 12.0, "NORMAL", ""))
            prop_segs.append((s_ent[7], s_ent[4], s_ent[5], sx, sy, s_ent[6]))
        seg_start = path[0]
        prev = path[0]
        cur_dir = None
        for node in path[1:]:
            if node[0] != prev[0]:
                if prev != seg_start:
                    x1, y1 = from_grid(seg_start[1], seg_start[2])
                    x2, y2 = from_grid(prev[1], prev[2])
                    prop_segs.append((seg_start[0], x1, y1, x2, y2, ()))
                vx, vy = from_grid(prev[1], prev[2])
                prop_vias.append((vx, vy, 6.0, 12.0, "NORMAL", ""))
                seg_start = node
                cur_dir = None
            else:
                d = (node[1] - prev[1], node[2] - prev[2])
                if cur_dir is not None and d != cur_dir:
                    x1, y1 = from_grid(seg_start[1], seg_start[2])
                    x2, y2 = from_grid(prev[1], prev[2])
                    prop_segs.append((seg_start[0], x1, y1, x2, y2, ()))
                    seg_start = prev
                cur_dir = d
            prev = node
        if prev != seg_start:
            x1, y1 = from_grid(seg_start[1], seg_start[2])
            x2, y2 = from_grid(prev[1], prev[2])
            prop_segs.append((seg_start[0], x1, y1, x2, y2, ()))
        if g_ent[0] == "ANCHOR":
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if math.hypot(ex - g_ent[4], ey - g_ent[5]) >= 0.25:
                prop_segs.append((g_ent[1], ex, ey, g_ent[4], g_ent[5], g_ent[6]))
        elif g_ent[0] == "DOG_VIA":
            ex, ey = from_grid(path[-1][1], path[-1][2])
            prop_vias.append((ex, ey, 6.0, 12.0, "NORMAL", ""))
            prop_segs.append((g_ent[7], ex, ey, g_ent[4], g_ent[5], g_ent[6]))
        elif g_ent[0] == "NEW_BLIND_VIA":
            ex, ey = from_grid(path[-1][1], path[-1][2])
            prop_vias.append((ex, ey, 4.0, 10.0, "BLIND", g_ent[4]))

        for vx, vy, h, dm, vt, rn in prop_vias:
            if not via_is_legal(vx, vy, net, via_type=vt, rule_name=rn, diam=dm, hole=h):
                return None
        for li_, x1, y1, x2, y2, ign in prop_segs:
            if not seg_is_legal(li_, x1, y1, x2, y2, width, net, base_trk_gap=base_gap, ignore_pad_idxs=ign):
                return None

        nt, nv = 0, 0
        for vx, vy, h, dm, vt, rn in prop_vias:
            if add_via(vx, vy, net, hole=h, diam=dm, via_type=vt, rule_name=rn):
                nv += 1
        for li_, x1, y1, x2, y2, _ in prop_segs:
            if add_track(li_, x1, y1, x2, y2, width, net):
                nt += 1
        if nt == 0 and nv == 0:
            return None
        return nt, nv

    ordered_nets = list(prio_list)
    seen_nets = {n for n, _ in ordered_nets} | {"GND"}
    for n in sorted(pads_by_net):
        if n not in seen_nets and len(pads_by_net[n]) >= 2:
            ordered_nets.append((n, 3.0))

    total_new_merges = 0
    net_summary = []
    for net, pref_w in ordered_nets:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        pad_parent, cluster_anchors = build_existing_uf(net)
        def pfind(x):
            while pad_parent[x] != x:
                pad_parent[x] = pad_parent[pad_parent[x]]
                x = pad_parent[x]
            return x
        init_comps = len({pfind(i) for i in range(len(pts))})
        if init_comps <= 1:
            continue

        merges_net = nt_net = nv_net = 0
        # Direct same-layer straight / L / Z bridges (<= 300 mil)
        for _dr in range(6):
            merged_d = False
            roots = sorted({pfind(i) for i in range(len(pts))})
            if len(roots) <= 1:
                break
            cands = []
            for ia in range(len(roots)):
                ra = roots[ia]
                for ib in range(ia + 1, len(roots)):
                    rb = roots[ib]
                    for li_a, ax, ay, p_a in cluster_anchors[ra][:28]:
                        for li_b, bx, by, p_b in cluster_anchors[rb][:28]:
                            if li_a != li_b:
                                continue
                            d = math.hypot(ax - bx, ay - by)
                            if 1.0 < d <= 300.0:
                                cands.append((d, ra, rb, li_a, ax, ay, p_a, bx, by, p_b))
            cands.sort(key=lambda t: t[0])
            for _, ra, rb, li_, ax, ay, p_a, bx, by, p_b in cands:
                if pfind(ra) == pfind(rb):
                    continue
                ign = tuple(x for x in (p_a, p_b) if x is not None)
                segs_ok = None
                for tw in ((pref_w, 3.0) if pref_w > 3.0 else (3.0,)):
                    if seg_is_legal(li_, ax, ay, bx, by, tw, net, ignore_pad_idxs=ign):
                        segs_ok = (tw, [(ax, ay, bx, by)])
                        break
                    for mx, my in ((bx, ay), (ax, by)):
                        if seg_is_legal(li_, ax, ay, mx, my, tw, net, ignore_pad_idxs=ign) and seg_is_legal(li_, mx, my, bx, by, tw, net, ignore_pad_idxs=ign):
                            segs_ok = (tw, [(ax, ay, mx, my), (mx, my, bx, by)])
                            break
                    if segs_ok:
                        break
                    for frac in (0.3, 0.5, 0.7):
                        mx, my = round(ax + frac * (bx - ax), 2), round(ay + frac * (by - ay), 2)
                        for path3 in (
                            [(ax, ay, mx, ay), (mx, ay, mx, by), (mx, by, bx, by)],
                            [(ax, ay, ax, my), (ax, my, bx, my), (bx, my, bx, by)],
                        ):
                            if all(seg_is_legal(li_, u1, v1, u2, v2, tw, net, ignore_pad_idxs=ign) for u1, v1, u2, v2 in path3):
                                segs_ok = (tw, path3)
                                break
                        if segs_ok:
                            break
                    if segs_ok:
                        break
                if segs_ok:
                    tw, s_list = segs_ok
                    added = sum(1 for u1, v1, u2, v2 in s_list if add_track(li_, u1, v1, u2, v2, tw, net))
                    if added > 0:
                        nt_net += added
                        merges_net += 1
                        total_new_merges += 1
                        r1, r2 = pfind(ra), pfind(rb)
                        pad_parent[r1] = r2
                        cluster_anchors[r2].extend(cluster_anchors[r1])
                        merged_d = True
            if not merged_d:
                break

        # Multi-Source -> Multi-Target A* (same-layer first, then multi-layer via-enabled!)
        rem_roots = sorted({pfind(i) for i in range(len(pts))})
        if len(rem_roots) >= 2:
            w_try = 3.0
            blocked, via_ok = build_net_masks(net, w_try, blind_side_li=None, base_trk_gap=6.15)
            failed_roots = set()
            for _around in range(len(rem_roots)):
                roots = sorted({pfind(i) for i in range(len(pts))})
                if len(roots) <= 1:
                    break
                comp_entries = {}
                for r in roots:
                    emap = {}
                    anchors_sorted = sorted(cluster_anchors[r], key=lambda a: (0 if a[3] is not None else 1))
                    for li_, ax, ay, p_idx in anchors_sorted[:28]:
                        for e in find_anchor_entries(li_, ax, ay, p_idx, net, w_try, blocked, base_trk_gap=6.15):
                            k = (e[1], e[2], e[3])
                            if k not in emap:
                                emap[k] = e
                    if emap:
                        comp_entries[r] = emap
                reach_roots = [r for r in comp_entries if r not in failed_roots]
                if len(comp_entries) < 2 or not reach_roots:
                    break
                merged_a = False
                for ra in reach_roots:
                    target_map, target_owner = {}, {}
                    for rb, emap_b in comp_entries.items():
                        if rb == ra:
                            continue
                        for k, e in emap_b.items():
                            if k not in target_map:
                                target_map[k] = e
                                target_owner[k] = rb
                    if not target_map:
                        continue
                    # Try zero-via same-layer A* first, then full 4-layer A*!
                    res = astar(list(comp_entries[ra].values()), target_map, blocked, via_ok, max_iters=22000, allow_via=False)
                    if not res:
                        res = astar(list(comp_entries[ra].values()), target_map, blocked, via_ok, max_iters=95000, allow_via=True)
                    if not res:
                        failed_roots.add(ra)
                        continue
                    s_ent, g_ent, path = res
                    rb = target_owner[path[-1]]
                    committed = try_commit_path(s_ent, g_ent, path, w_try, net, 6.15)
                    if not committed:
                        failed_roots.add(ra)
                        continue
                    dt, dv = committed
                    nt_net += dt
                    nv_net += dv
                    merges_net += 1
                    total_new_merges += 1
                    r1, r2 = pfind(ra), pfind(rb)
                    pad_parent[r1] = r2
                    cluster_anchors[r2].extend(cluster_anchors[r1])
                    for node in path[::3]:
                        gx_, gy_ = from_grid(node[1], node[2])
                        cluster_anchors[r2].append((node[0], gx_, gy_, None))
                    failed_roots.clear()
                    blocked, via_ok = build_net_masks(net, w_try, blind_side_li=None, base_trk_gap=6.15)
                    merged_a = True
                    break
                if not merged_a:
                    break

        if merges_net > 0:
            final_comps = len({pfind(i) for i in range(len(pts))})
            net_summary.append({
                "net": net, "pads": len(pts),
                "components_before": init_comps, "components_after": final_comps,
                "merges_added": merges_net, "new_tracks": nt_net, "new_vias": nv_net,
            })
            print(f"  [{board}] {net:22s}: comps {init_comps:2d} -> {final_comps:2d} (-{merges_net:2d} unconn) | +tracks={nt_net:3d}, +vias={nv_net:2d}", flush=True)

    # Phase C: GND incremental closure (strictly >= 14.30 mil / 0.363 mm edge clearance!)
    gnd_pads = [p for p in pads_by_net.get("GND", []) if not (board == "PCB1" and p["ref"] == "U1")]
    gnd_vias_list = [v for v in placed_vias if v[4] == "GND"]
    gnd_segs_list = [s for s in routed_segs if s[6] == "GND"]
    N_g = len(gnd_pads) + len(gnd_segs_list) + len(gnd_vias_list)
    g_uf = list(range(N_g))
    def guf_find(x):
        while g_uf[x] != x:
            g_uf[x] = g_uf[g_uf[x]]
            x = g_uf[x]
        return x
    def guf_union(a, b):
        ra, rb = guf_find(a), guf_find(b)
        if ra != rb:
            g_uf[ra] = rb
    for pi, p in enumerate(gnd_pads):
        for si, s in enumerate(gnd_segs_list):
            if s[0] == p["li"] and pt_seg_dist(p["x"], p["y"], s[1], s[2], s[3], s[4]) <= max(p["hw"], p["hh"]) + 0.5 * s[5] + 0.6:
                guf_union(pi, len(gnd_pads) + si)
        for vi, v in enumerate(gnd_vias_list):
            if via_touches_layer(v[5], v[6], p["li"]) and math.hypot(p["x"] - v[0], p["y"] - v[1]) <= max(p["hw"], p["hh"]) + v[2] + 0.6:
                guf_union(pi, len(gnd_pads) + len(gnd_segs_list) + vi)
    for si in range(len(gnd_segs_list)):
        sa = gnd_segs_list[si]
        for sj in range(si + 1, len(gnd_segs_list)):
            sb = gnd_segs_list[sj]
            if sa[0] == sb[0] and seg_seg_dist(sa[1], sa[2], sa[3], sa[4], sb[1], sb[2], sb[3], sb[4]) <= 0.5 * (sa[5] + sb[5]) + 0.5:
                guf_union(len(gnd_pads) + si, len(gnd_pads) + sj)
    for si, s in enumerate(gnd_segs_list):
        for vi, v in enumerate(gnd_vias_list):
            if via_touches_layer(v[5], v[6], s[0]) and pt_seg_dist(v[0], v[1], s[1], s[2], s[3], s[4]) <= v[2] + 0.5 * s[5] + 0.6:
                guf_union(len(gnd_pads) + si, len(gnd_pads) + len(gnd_segs_list) + vi)
    via_roots = {guf_find(len(gnd_pads) + len(gnd_segs_list) + vi) for vi in range(len(gnd_vias_list))}
    grounded_idx = {pi for pi in range(len(gnd_pads)) if guf_find(pi) in via_roots}
    gnd_before = len(grounded_idx)
    new_gnd_blinds = new_gnd_tracks = 0

    for side_li, rname in ((0, "BV_L1_L2"), (3, "BV_L5_L6")):
        ungr_side = [i for i in range(len(gnd_pads)) if i not in grounded_idx and gnd_pads[i]["li"] == side_li]
        if not ungr_side:
            continue
        blocked_g, via_ok_g = build_net_masks("GND", 3.0, blind_side_li=side_li, base_trk_gap=6.15)
        for i in ungr_side:
            gp = gnd_pads[i]
            starts = find_anchor_entries(side_li, gp["x"], gp["y"], gp["idx"], "GND", 3.0, blocked_g, base_trk_gap=6.15)
            if not starts:
                continue
            goal_map = {}
            gx0, gy0 = to_grid(gp["x"], gp["y"])
            rad_g = int(220.0 / STEP)
            for gx in range(max(0, gx0 - rad_g), min(NX, gx0 + rad_g + 1)):
                base = gx * NY
                for gy in range(max(0, gy0 - rad_g), min(NY, gy0 + rad_g + 1)):
                    if via_ok_g[base + gy] and not blocked_g[side_li][base + gy]:
                        goal_map[(side_li, gx, gy)] = ("NEW_BLIND_VIA", side_li, gx, gy, rname)
            for j in grounded_idx:
                if gnd_pads[j]["li"] == side_li and abs(gnd_pads[j]["x"] - gp["x"]) + abs(gnd_pads[j]["y"] - gp["y"]) <= 450.0:
                    for e in find_anchor_entries(side_li, gnd_pads[j]["x"], gnd_pads[j]["y"], gnd_pads[j]["idx"], "GND", 3.0, blocked_g, base_trk_gap=6.15):
                        goal_map[(e[1], e[2], e[3])] = e
            for vx, vy, _, _, onet, ovt, orn, _ in placed_vias:
                if onet == "GND" and via_touches_layer(ovt, orn, side_li) and abs(vx - gp["x"]) + abs(vy - gp["y"]) <= 450.0:
                    for e in find_anchor_entries(side_li, vx, vy, None, "GND", 3.0, blocked_g, base_trk_gap=6.15):
                        goal_map[(e[1], e[2], e[3])] = e
            if not goal_map:
                continue
            res = astar(starts, goal_map, blocked_g, via_ok_g, max_iters=45000, allow_via=False)
            if not res:
                continue
            s_ent, g_ent, path = res
            committed = try_commit_path(s_ent, g_ent, path, 3.0, "GND", 6.15)
            if not committed:
                continue
            dt, dv = committed
            new_gnd_tracks += dt
            new_gnd_blinds += dv
            grounded_idx.add(i)
            blocked_g, via_ok_g = build_net_masks("GND", 3.0, blind_side_li=side_li, base_trk_gap=6.15)

    gnd_added = len(grounded_idx) - gnd_before
    print(f"  [{board}] GND incremental (>=0.35mm edge): {gnd_before} -> {len(grounded_idx)}/{len(gnd_pads)} (+{gnd_added}) | +tracks={new_gnd_tracks}, +blind={new_gnd_blinds}", flush=True)

    all_non_gnd_through = [[round(v[0], 2), round(v[1], 2)] for v in placed_vias if v[4] != "GND" and v[5] == "NORMAL"]
    out = {
        "board": board,
        "summary": {
            "p0_blind_vias_rectified_ge_0p35mm": len(relocated_vias),
            "deleted_line_ids_count": len(deleted_line_ids),
            "delta_tracks": len(delta_tracks),
            "delta_vias": len(delta_vias),
            "delta_blind_vias": sum(1 for v in delta_vias if v["viaType"] == "BLIND"),
            "delta_mech_signal_vias": sum(1 for v in delta_vias if v["viaType"] == "NORMAL" and v["net"] != "GND"),
            "non_gnd_merges_added": total_new_merges,
            "gnd_pads_newly_grounded": gnd_added,
            "total_projected_unconn_reduction": total_new_merges + gnd_added,
        },
        "relocated_vias": relocated_vias,
        "deleted_via_ids": deleted_via_ids,
        "deleted_line_ids": deleted_line_ids,
        "nets": net_summary,
        "delta_tracks": delta_tracks,
        "delta_vias": delta_vias,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{board}-pr47-delta.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / f"{board}-antipads.json").write_text(json.dumps(all_non_gnd_through, indent=2) + "\n", encoding="utf-8")
    print(f"=== {board} PR47 RECTIFY + DELTA SUMMARY ===")
    print(json.dumps(out["summary"], indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--board", choices=["PCB1", "PCB2", "PCB3"], required=True)
    p.add_argument("--pr46-epro", type=Path, required=True)
    p.add_argument("--pr46-dump", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()
    process_board(a.board, a.pr46_epro, a.pr46_dump, a.out_dir)


if __name__ == "__main__":
    main()
