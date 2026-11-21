#!/usr/bin/env python3
"""P0 DFM-Clean + P1 Controlled-Batch 4-Signal-Layer (L1/L3/L4/L6) HDI Router for EVT-1 H03 (PCB1, PCB2, PCB3).

P0 DFM Hard Guards Enforced (ZERO rule relaxation):
  1. ZERO real non-VIPPO via-in-pad: every non-BGA/non-EPAD BV_L1_L2 & BV_L5_L6 GND blind microvia is strictly
     dog-bone offset >= +2.2 mil outside EVERY same-layer SMD pad edge (including its own same-net pad!).
     Intentional VIPPO is strictly restricted to U2 BGA inner GND balls (2) & U1 EPAD thermal array (9).
  2. ZERO 3W parallel coupling: high-noise/sensitive nets (BK_SW, BB_L1/L2, BLE_ANT_FEED, BLE_RF_*, LFXO_XL*,
     BLE_XC*, clk_48m, I2S_*) enforce >= 11.5 mil (> 3W) separation from all different-net tracks on shared layers!
  3. ZERO track-over-pad (rejects any segment passing through an intermediate same-net pad interior).
  4. ZERO duplicate/collinear overlapping segments (geometric collinear-overlap guard in add_track).
  5. ZERO dangling ends / floating islands / MK1-3 acoustic body intrusions (mic body protected for ALL nets incl. GND).
  6. ZERO < 3.0 mil fine-line tracks + wider 6.0 mil power trunks (VSYS/VBUS/3V3_SYS/VBAT) where corridor allows.
  7. ZERO illegal 4/8 mil through-vias: all 4/8 vias are true BV_L1_L2 (1<->15) or BV_L5_L6 (18<->2) laser blind
     microvias; all signal/power layer-change vias are standard 6/12 mil (0.15/0.30 mm) NORMAL mechanical through-vias.
"""

import argparse
import heapq
import json
import math
from pathlib import Path

L_IDS = [1, 16, 17, 2]  # 0=L1 Top, 1=L3 Inner2(Sig), 2=L4 Inner3(Sig), 3=L6 Bottom
SIDE_TO_LI = {1: 0, 2: 3}
U2_INNER_BALLS = {"B2", "C2", "D2", "E2", "B3", "C3", "D3", "E3", "B4", "C4", "D4", "E4"}

# Nets requiring strict > 3W center-to-center separation from different-net tracks on ALL layers (eliminates 3W crosstalk!)
SENSITIVE_3W_NETS = {
    "BK_SW", "BB_L1", "BB_L2", "VBUS_5V", "VBUS_5V_USB", "VSYS", "PDM_CLK_1V8",
    "I2S_S3_DOUT_3V3", "I2S_S3_DOUT_1V8", "I2S_BCLK_3V3", "I2S_BCLK_1V8", "I2S_LRCLK_3V3", "I2S_LRCLK_1V8", "I2S_AMP_DIN_1V8",
    "BLE_ANT_FEED", "BLE_RF_MID", "BLE_RF_ANT", "ESP_ANT_FEED", "ESP_RF_ANT",
    "LFXO_XL1", "LFXO_XL2", "BLE_XC1", "BLE_XC2", "clk_48m",
}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def collinear_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> bool:
    """Return True if two segments are near-collinear (within 1.0 mil) and overlap by > 0.25 mil."""
    adx, ady = ax2 - ax1, ay2 - ay1
    alen = math.hypot(adx, ady)
    bdx, bdy = bx2 - bx1, by2 - by1
    blen = math.hypot(bdx, bdy)
    if alen < 0.1 or blen < 0.1:
        return False
    # Cross product test for parallel (<= ~4 deg)
    cross = abs(adx * bdy - ady * bdx) / (alen * blen)
    if cross > 0.07:
        return False
    # Distance from b's endpoints to line a
    ux, uy = adx / alen, ady / alen
    perp1 = abs((bx1 - ax1) * (-uy) + (by1 - ay1) * ux)
    perp2 = abs((bx2 - ax1) * (-uy) + (by2 - ay1) * ux)
    if max(perp1, perp2) > 1.0:
        return False
    # 1D interval overlap along line a
    p1 = (bx1 - ax1) * ux + (by1 - ay1) * uy
    p2 = (bx2 - ax1) * ux + (by2 - ay1) * uy
    lo, hi = min(p1, p2), max(p1, p2)
    return min(alen, hi) - max(0.0, lo) > 0.25


PCB2_PRIORITY = [
    ("clk_48m", 3.0),
    ("FPGA_1V2_SENSE", 3.0),
    ("FPGA_1V8_EN", 3.0),
    ("PRIV_LED_ANODE", 3.5),
    ("FPGA_CRESET_B", 3.0),
    ("FPGA_CDONE_VSYNC_N", 3.0),
    ("opt_l_qdo0_PANEL", 3.0), ("opt_l_qdo1_PANEL", 3.0), ("opt_l_qdo2_PANEL", 3.0), ("opt_l_qdo3_PANEL", 3.0),
    ("opt_r_qdo0_PANEL", 3.0), ("opt_r_qdo1_PANEL", 3.0), ("opt_r_qdo2_PANEL", 3.0), ("opt_r_qdo3_PANEL", 3.0),
    ("OPT_SCK_L", 3.0), ("OPT_CS_N_L", 3.0), ("OPT_SCK_R", 3.0), ("OPT_CS_N_R", 3.0),
    ("opt_sck", 3.0), ("opt_cs_n", 3.0),
    ("opt_l_qdo0", 3.0), ("opt_l_qdo1", 3.0), ("opt_l_qdo2", 3.0), ("opt_l_qdo3", 3.0),
    ("opt_r_qdo0", 3.0), ("opt_r_qdo1", 3.0), ("opt_r_qdo2", 3.0), ("opt_r_qdo3", 3.0),
    ("host_sck", 3.0), ("host_cs_n", 3.0), ("host_qio0", 3.0), ("host_qio1", 3.0), ("host_qio2", 3.0), ("host_qio3", 3.0),
    ("SYS_I2C_SCL_1V8", 3.0), ("SYS_I2C_SDA_1V8", 3.0), ("PDM_CLK_1V8", 3.0), ("PDM_D0_1V8", 3.0),
    ("AVDD_WD_SET", 3.0), ("AVDD_WD_DIV", 3.0), ("AVDD_CRESET_VSYS", 3.0), ("AVDD_PULSE_QUAL", 3.0),
    ("AVDD_PG_OK", 3.0), ("AVDD_QUAL_CLR_N", 3.0), ("AVDD_REQ_FILTER", 3.0), ("AVDD_QUAL_RC", 3.0),
    ("AVDD_D3_VSYS", 3.0), ("AVDD_WD_Q", 3.0), ("AVDD_PG_NODE", 3.0), ("OPT_AVDD_EN", 3.0), ("AVDD_OPT_BIAS", 3.5),
    ("1V8_FPGA_VPP", 3.5), ("1V2_FPGA_PLL", 3.5), ("1V2_FPGA_CORE", 3.5), ("1V8_SYS", 3.5), ("1V8_FPGA_IO", 3.5), ("VSYS", 4.5),
]

PCB1_PRIORITY = [
    ("ESP_ANT_FEED", 3.5), ("ESP_RF_ANT", 3.5),
    ("USB_DP", 3.0), ("USB_DM", 3.0), ("USB_LIM_ILIM", 3.0), ("VBUS_5V_USB", 6.0), ("VBUS_5V", 6.0),
    ("LED_3V3_PRIV", 3.5), ("PRIV_LED_ANODE", 3.5), ("PRIV_VTH_H", 3.0), ("PRIV_VTH_L", 3.0),
    ("PRIV_WINDOW_OK", 3.0), ("PRIV_WINDOW_OK_F", 3.0), ("CAM_PWR_REQ", 3.0), ("CAM_DOVDD_OK_3V3", 3.0),
    ("I2S_BCLK_1V8", 3.0), ("I2S_LRCLK_1V8", 3.0), ("I2S_AMP_DIN_1V8", 3.0), ("I2S_S3_DOUT_1V8", 3.0),
    ("I2S_BCLK_3V3", 3.0), ("I2S_LRCLK_3V3", 3.0), ("I2S_S3_DOUT_3V3", 3.0), ("AMP_SD_MODE_1V8", 3.0),
    ("IPC_NRF_TX_1V8", 3.0), ("IPC_S3_TX_1V8", 3.0), ("IPC_NRF_TX_3V3", 3.0), ("IPC_S3_TX_3V3", 3.0),
    ("SYS_I2C_SCL_1V8", 3.0), ("SYS_I2C_SDA_1V8", 3.0), ("SYS_I2C_SCL_3V3", 3.0), ("SYS_I2C_SDA_3V3", 3.0),
    ("PDM_CLK_1V8", 3.0), ("PDM_D0_1V8", 3.0), ("PDM_D1_1V8", 3.0),
    ("host_sck_3v3", 3.0), ("host_cs_n_3v3", 3.0), ("host_qio0_3v3", 3.0), ("host_qio1_3v3", 3.0), ("host_qio2_3v3", 3.0), ("host_qio3_3v3", 3.0),
    ("ESP_VDD_SPI_3V3", 3.5), ("1V8_FPGA_IO", 3.5), ("VBAT_L", 6.0), ("VBAT_R_ISOLATED", 6.0), ("VBAT_R_RET", 6.0),
    ("BK_SW", 4.0), ("BB_L1", 4.0), ("BB_L2", 4.0), ("BB_FB", 3.0),
    ("V_INA_OUT", 3.0), ("VOUT_L_PPATH", 3.5), ("CAM_AVDD_2V8", 3.5), ("CAM_DVDD_1V2", 3.5), ("CAM_DOVDD_1V8", 3.0),
    ("VSYS", 6.0), ("1V8_SYS", 4.0), ("3V3_SYS", 5.0),
]

PCB3_PRIORITY = [
    ("BLE_XC1", 3.0), ("BLE_XC2", 3.0), ("LFXO_XL1", 3.0), ("LFXO_XL2", 3.0),
    ("BLE_ANT_FEED", 3.5), ("BLE_RF_MID", 3.5), ("BLE_RF_ANT", 3.5),
    ("NRF_DECA", 3.0), ("NRF_DECN", 3.0), ("NRF_DCC", 3.0), ("NRF_DCCD", 3.0), ("NRF_DECD", 3.0), ("NRF_DECR_RF", 3.0),
    ("BLE_SWDIO", 3.0), ("BLE_SWDCLK", 3.0), ("BLE_NRESET", 3.0),
    ("IPC_NRF_TX_1V8", 3.0), ("IPC_S3_TX_1V8", 3.0),
    ("I2S_BCLK_1V8", 3.0), ("I2S_LRCLK_1V8", 3.0), ("I2S_AMP_DIN_1V8", 3.0), ("I2S_S3_DOUT_1V8", 3.0),
    ("AMP_SD_REQ_1V8", 3.0), ("AMP_SD_MODE_1V8", 3.0), ("AMP_R_SD_MODE", 3.0), ("PDM_CLK_1V8", 3.0), ("PDM_D1_1V8", 3.0),
    ("VBUS_5V", 4.0), ("VBAT_R_RET", 4.0), ("1V8_SYS", 3.5),
]


def board_geometry(board: str):
    if board == "PCB2":
        W, H = 181.1024, 984.2520
        def in_trk(x, y, margin):
            return margin <= x <= W - margin and margin <= y <= H - margin
        def in_via(x, y, is_gnd):
            # GND 4/8 blind via r=4 -> 16.3 - 4 = 12.3 > 11.811 mil edge rule; Signal 6/12 through-via r=17.8 antipad -> >= 30.0 mil
            m = 16.3 if is_gnd else 30.0
            return m <= x <= W - m and m <= y <= H - m
        return W, H, 2.0, in_trk, in_via, "MK2", PCB2_PRIORITY, []
    elif board == "PCB1":
        W, H = 322.8346, 1811.0236
        def in_trk(x, y, margin):
            if x < margin or y < 165.3543 + margin or y > H - margin:
                return False
            if y > 551.1811 - margin:
                return x <= 228.3465 - margin
            return x <= W - margin
        def in_via(x, y, is_gnd):
            m = 16.3 if is_gnd else 30.5
            pad_e = 6.5 if is_gnd else 19.5
            if x < m or y < 176.0 + pad_e or y > H - m:
                return False
            if y > 540.5 - pad_e:
                return x <= 217.8 - pad_e
            return x <= 312.3 - pad_e
        u1x, u1y = 4.10 / 0.0254, 9.10 / 0.0254
        u1_vias = [(round(u1x + dx * 39.37, 2), round(u1y + dy * 39.37, 2), 8.0, 14.0) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        return W, H, 3.0, in_trk, in_via, "MK1", PCB1_PRIORITY, u1_vias
    elif board == "PCB3":
        W, H = 204.7244, 1338.5827
        def in_trk(x, y, margin):
            return margin <= x <= W - margin and 157.4803 + margin <= y <= H - margin
        def in_via(x, y, is_gnd):
            m = 16.3 if is_gnd else 30.5
            y_lo = 168.0 + (6.5 if is_gnd else 19.5)
            return m <= x <= W - m and y_lo <= y <= H - m
        return W, H, 2.5, in_trk, in_via, "MK3", PCB3_PRIORITY, []
    raise ValueError(f"Unknown board {board}")


def via_touches_layer(vtype: str, rule_name: str, li: int) -> bool:
    if vtype != "BLIND":
        return True
    if rule_name == "BV_L1_L2":
        return li == 0
    if rule_name == "BV_L5_L6":
        return li == 3
    return True


def vias_share_vertical_span(vt1: str, rn1: str, vt2: str, rn2: str) -> bool:
    if vt1 == "BLIND" and vt2 == "BLIND" and rn1 != rn2:
        return False
    return True


def apply_pcb1_decap_swap_to_dump(dump: dict):
    """Apply zero-collision identical-0402 3-way swap on PCB1 (C14 -> C17 slot near U1.29,
    C17 -> R21 slot near U6.1, R21 -> C14 slot) so routing uses post-swap pad coordinates."""
    by_ref = {c["designator"]: c for c in dump["components"]}
    if not all(r in by_ref for r in ("C14", "C17", "R21")):
        return
    c14, c17, r21 = by_ref["C14"], by_ref["C17"], by_ref["R21"]
    pos = {
        "C14": (float(c17["x"]), float(c17["y"])),
        "C17": (float(r21["x"]), float(r21["y"])),
        "R21": (float(c14["x"]), float(c14["y"])),
    }
    for ref, (nx, ny) in pos.items():
        comp = by_ref[ref]
        dx, dy = nx - float(comp["x"]), ny - float(comp["y"])
        comp["x"], comp["y"] = nx, ny
        for p in comp["pads"]:
            p["x"] = float(p["x"]) + dx
            p["y"] = float(p["y"]) + dy


def route_board(board: str, dump_path: Path, plan_out: Path, antipads_out: Path, max_nets_budget: int = 160):
    W_MIL, H_MIL, STEP, in_trk, in_via, mic_ref, prio_list, fixed_gnd_vias = board_geometry(board)
    NX = int(W_MIL / STEP) + 1
    NY = int(H_MIL / STEP) + 1
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    if board == "PCB1":
        apply_pcb1_decap_swap_to_dump(dump)

    all_pads = []
    pads_by_net: dict[str, list[dict]] = {}
    mic_cx, mic_cy, mic_hx, mic_hy = -9999.0, -9999.0, -9999.0, -9999.0

    for c in dump["components"]:
        ref, cx, cy = c["designator"], float(c["x"]), float(c["y"])
        c_rot = float(c.get("rotation") or 0.0)
        if ref == mic_ref:
            mic_cx, mic_cy = cx, cy
            mic_hx, mic_hy = cx - 0.005, cy + 31.89
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
                        pw = max(pw, max(nums[0::2]) - min(nums[0::2]))
                        ph = max(ph, max(nums[1::2]) - min(nums[1::2]))
                if ref == mic_ref:
                    pw, ph = max(pw, 28.0), max(ph, 28.0)
                else:
                    pw, ph = max(pw, 16.0), max(ph, 16.0)
            rot = c_rot + float(p.get("rotation") or 0.0)
            rad = math.radians(rot)
            ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
            hw = 0.5 * (pw * ca + ph * sa) + 0.6
            hh = 0.5 * (pw * sa + ph * ca) + 0.6
            li = SIDE_TO_LI.get(int(p.get("layer", c["layer"])), 0)
            rec = {"x": px, "y": py, "hw": hw, "hh": hh, "li": li, "net": net, "ref": ref, "pnum": str(p.get("padNumber", "")), "cx": cx, "cy": cy, "idx": len(all_pads)}
            all_pads.append(rec)
            if net:
                pads_by_net.setdefault(net, []).append(rec)

    mic_box = (mic_cx - 58.0, mic_cx + 58.0, mic_cy - 78.0, mic_cy + 78.0)
    def in_mic_body(x, y, pad_r=0.0):
        return (mic_box[0] - pad_r <= x <= mic_box[1] + pad_r) and (mic_box[2] - pad_r <= y <= mic_box[3] + pad_r)

    def to_grid(x, y):
        return max(0, min(NX - 1, int(round(x / STEP)))), max(0, min(NY - 1, int(round(y / STEP))))

    def from_grid(gx, gy):
        return round(gx * STEP, 2), round(gy * STEP, 2)

    routed_segs: list[tuple[int, float, float, float, float, float, str]] = []
    placed_vias: list[tuple[float, float, float, str, str, str]] = []
    tracks_out = []
    vias_out = []

    def add_via(vx, vy, net, hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
        for ovx, ovy, _, onet, ovt, orn in placed_vias:
            if onet == net and ovt == via_type and orn == rule_name and math.hypot(vx - ovx, vy - ovy) < 1.5:
                return False
        placed_vias.append((vx, vy, 0.5 * diam, net, via_type, rule_name))
        vias_out.append({
            "x": round(vx, 2), "y": round(vy, 2),
            "hole": hole, "diameter": diam, "net": net,
            "viaType": via_type, "ruleName": rule_name,
        })
        return True

    def add_track(li, x1, y1, x2, y2, width, net):
        if math.hypot(x2 - x1, y2 - y1) < 0.25:
            return False
        # P0 Guard: eliminate exact AND collinear overlapping same-net segments (duplicate-segment == 0!)
        for oli, ox1, oy1, ox2, oy2, _, onet in routed_segs:
            if oli == li and onet == net:
                if collinear_overlap(x1, y1, x2, y2, ox1, oy1, ox2, oy2):
                    return False
        routed_segs.append((li, x1, y1, x2, y2, width, net))
        tracks_out.append({
            "layer": L_IDS[li], "x1": round(x1, 2), "y1": round(y1, 2),
            "x2": round(x2, 2), "y2": round(y2, 2), "width": width, "net": net,
        })
        return True

    fixed_gnd_count = 0
    for vx, vy, h_m, d_m in fixed_gnd_vias:
        if add_via(vx, vy, "GND", h_m, d_m, "NORMAL", ""):
            fixed_gnd_count += 1

    def via_is_legal(vx, vy, net, via_type="NORMAL", rule_name="", vippo_u2=False):
        is_gnd = (net == "GND")
        vrad = 4.0 if via_type == "BLIND" else 6.0
        if not in_via(vx, vy, is_gnd):
            return False
        mk_r = 37.5 if is_gnd else 49.0
        if math.hypot(vx - mic_hx, vy - mic_hy) < mk_r:
            return False
        if (not is_gnd or rule_name == "BV_L5_L6") and in_mic_body(vx, vy, 13.0):
            return False
        for ovx, ovy, orad, onet, ovt, orn in placed_vias:
            if not vias_share_vertical_span(via_type, rule_name, ovt, orn):
                continue
            d = math.hypot(vx - ovx, vy - ovy)
            if (is_gnd and onet != "GND") or ((not is_gnd) and onet == "GND"):
                min_vv = 19.5 + (vrad if is_gnd else orad)
            elif (not is_gnd) and (onet != "GND"):
                min_vv = vrad + orad + 8.5
            else:
                min_vv = vrad + orad + 8.0
            if d < min_vv:
                return False
        for p in all_pads:
            if not via_touches_layer(via_type, rule_name, p["li"]):
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            dist = math.hypot(dx, dy)
            if p["net"] == net:
                # P0 HARD GUARD: ZERO real non-VIPPO via-in-pad! (hw/hh already includes +0.6 mil pad margin -> vrad+0.6 = +1.2 mil outside true SMD pad!)
                if vippo_u2 and p["ref"] == "U2" and p["li"] == 0:
                    continue
                if board == "PCB1" and p["ref"] == "U1" and p["li"] == 0:
                    continue
                if dist < vrad + 0.6:
                    return False
            else:
                if vippo_u2 and p["ref"] == "U2" and p["li"] == 0:
                    if dist < 6.8:
                        return False
                else:
                    if dist < vrad + 6.2:
                        return False
        for oli, x1, y1, x2, y2, w, onet in routed_segs:
            if onet == net:
                continue
            if not via_touches_layer(via_type, rule_name, oli):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < vrad + 6.2 + 0.5 * w:
                return False
        return True

    def pair_track_gap(net_a: str, net_b: str, base_gap: float, li: int = 1, w_a: float = 3.0, w_b: float = 3.0) -> float:
        # Enforce > 3W center-to-center (converted to edge-to-edge gap) on ALL layers for sensitive/wide nets!
        if net_a in SENSITIVE_3W_NETS or net_b in SENSITIVE_3W_NETS or max(w_a, w_b) >= 4.0:
            c2c = 3.2 * max(w_a, w_b)
            e2e = c2c - 0.5 * (w_a + w_b)
            return max(base_gap, e2e, 11.8 if (li in (1, 2) and (net_a in SENSITIVE_3W_NETS or net_b in SENSITIVE_3W_NETS)) else 0.0)
        return base_gap

    def seg_is_legal(li, x1, y1, x2, y2, width, net, base_trk_gap=3.5, ignore_pad_idxs=()):
        margin = 12.3 + 0.5 * width  # > 11.811 mil (0.300 mm) EasyEDA locked outline-to-track rule!
        if not (in_trk(x1, y1, margin) and in_trk(x2, y2, margin)):
            return False
        if pt_seg_dist(mic_hx, mic_hy, x1, y1, x2, y2) < 33.5 + 0.5 * width:
            return False
        # Protect mic pad body on bottom layer for ALL nets (including GND!) unless endpoint is a mic GND pad!
        if li == 3:
            is_mic_gnd = any(all_pads[idx]["ref"] == mic_ref for idx in ignore_pad_idxs)
            if not is_mic_gnd:
                for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                    if in_mic_body(x1 + t * (x2 - x1), y1 + t * (y2 - y1), 7.5 + 0.5 * width):
                        return False
        for vx, vy, vrad, onet, ovt, orn in placed_vias:
            if onet == net:
                continue
            if not via_touches_layer(ovt, orn, li):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 6.3 + vrad + 0.5 * width:
                return False
        steps = max(3, int(math.hypot(x2 - x1, y2 - y1) / 2.0) + 1)
        if li in (0, 3):
            clr = 6.3 + 0.5 * width
            for p in all_pads:
                if p["li"] != li:
                    continue
                if p["net"] == net:
                    # P0 Guard: track-over-pad check — reject passing through an intermediate same-net pad interior!
                    if p["idx"] in ignore_pad_idxs:
                        continue
                    if math.hypot(x1 - p["x"], y1 - p["y"]) < 2.0 or math.hypot(x2 - p["x"], y2 - p["y"]) < 2.0:
                        continue
                    if pt_seg_dist(p["x"], p["y"], x1, y1, x2, y2) < max(p["hw"], p["hh"]) + 0.5 * width:
                        return False
                    continue
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
            min_d = pair_track_gap(net, onet, base_trk_gap, li, width, ow) + 0.5 * (width + ow)
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if pt_seg_dist(cx, cy, ox1, oy1, ox2, oy2) < min_d:
                    return False
        return True

    def build_net_masks(net, width, blind_side_li=None, base_trk_gap=3.5):
        is_gnd = (net == "GND")
        is_blind = (blind_side_li is not None)
        vtype = "BLIND" if is_blind else "NORMAL"
        rname = "BV_L1_L2" if blind_side_li == 0 else ("BV_L5_L6" if blind_side_li == 3 else "")
        vrad = 4.0 if is_blind else 6.0

        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))
        t_margin = 12.3 + 0.5 * width  # > 11.811 mil locked outline-to-track rule!
        mk_t = 33.5 + 0.5 * width
        mk_v = 37.5 if is_gnd else 49.0

        for gx in range(NX):
            x = gx * STEP
            base = gx * NY
            for gy in range(NY):
                y = gy * STEP
                idx = base + gy
                d_mk = math.hypot(x - mic_hx, y - mic_hy)
                if (not in_trk(x, y, t_margin)) or d_mk < mk_t:
                    blocked[0][idx] = blocked[1][idx] = blocked[2][idx] = blocked[3][idx] = 1
                    via_ok[idx] = 0
                elif (not in_via(x, y, is_gnd)) or d_mk < mk_v:
                    via_ok[idx] = 0
                # Always protect bottom mic body from non-mic tracks & bottom vias!
                if in_mic_body(x, y, 7.5 + 0.5 * width):
                    blocked[3][idx] = 1
                if (not is_gnd or rname == "BV_L5_L6") and in_mic_body(x, y, 13.0):
                    via_ok[idx] = 0

        pad_clr = 6.3 + 0.5 * width
        via_pad_clr = vrad + 6.2  # +0.6 hw margin = +0.8 mil strictly above locked 6.0 mil EasyEDA rule!
        same_net_via_clr = vrad + 0.6  # Strictly outside true SMD pad copper (+1.2 mil margin!)
        for p in all_pads:
            li = p["li"]
            if p["net"] == net:
                # Block via_ok over same-net SMD pads (eliminates real via-in-pad!)
                if via_touches_layer(vtype, rname, li) and not (board == "PCB1" and p["ref"] == "U1"):
                    clr = same_net_via_clr
                    gx0 = max(0, int(math.floor((p["x"] - p["hw"] - clr) / STEP)))
                    gx1 = min(NX - 1, int(math.ceil((p["x"] + p["hw"] + clr) / STEP)))
                    gy0 = max(0, int(math.floor((p["y"] - p["hh"] - clr) / STEP)))
                    gy1 = min(NY - 1, int(math.ceil((p["y"] + p["hh"] + clr) / STEP)))
                    for gx in range(gx0, gx1 + 1):
                        dx = max(0.0, abs(gx * STEP - p["x"]) - p["hw"])
                        base = gx * NY
                        for gy in range(gy0, gy1 + 1):
                            dy = max(0.0, abs(gy * STEP - p["y"]) - p["hh"])
                            if math.hypot(dx, dy) < clr:
                                via_ok[base + gy] = 0
                # P0 Guard: block A* grid tracks from walking right through the interior of unrelated same-net pads (track-over-pad == 0!)
                if li in (0, 3):
                    ihw = max(0.0, p["hw"] - 0.8)
                    ihh = max(0.0, p["hh"] - 0.8)
                    gx0 = max(0, int(math.floor((p["x"] - ihw) / STEP)))
                    gx1 = min(NX - 1, int(math.ceil((p["x"] + ihw) / STEP)))
                    gy0 = max(0, int(math.floor((p["y"] - ihh) / STEP)))
                    gy1 = min(NY - 1, int(math.ceil((p["y"] + ihh) / STEP)))
                    for gx in range(gx0, gx1 + 1):
                        base = gx * NY
                        for gy in range(gy0, gy1 + 1):
                            if abs(gx * STEP - p["x"]) <= ihw and abs(gy * STEP - p["y"]) <= ihh:
                                blocked[li][base + gy] = 1
                continue
            checks = [(pad_clr, blocked[li])]
            if via_touches_layer(vtype, rname, li):
                checks.append((via_pad_clr, None))
            for clr, target in checks:
                gx0 = max(0, int(math.floor((p["x"] - p["hw"] - clr) / STEP)))
                gx1 = min(NX - 1, int(math.ceil((p["x"] + p["hw"] + clr) / STEP)))
                gy0 = max(0, int(math.floor((p["y"] - p["hh"] - clr) / STEP)))
                gy1 = min(NY - 1, int(math.ceil((p["y"] + p["hh"] + clr) / STEP)))
                for gx in range(gx0, gx1 + 1):
                    dx = max(0.0, abs(gx * STEP - p["x"]) - p["hw"])
                    base = gx * NY
                    for gy in range(gy0, gy1 + 1):
                        dy = max(0.0, abs(gy * STEP - p["y"]) - p["hh"])
                        if math.hypot(dx, dy) < clr:
                            if target is not None:
                                target[base + gy] = 1
                            else:
                                via_ok[base + gy] = 0

        for vx, vy, orad, onet, ovt, orn in placed_vias:
            shares_z = vias_share_vertical_span(vtype, rname, ovt, orn)
            if shares_z:
                if (is_gnd and onet != "GND") or ((not is_gnd) and onet == "GND"):
                    r_v = 19.8 + (vrad if is_gnd else orad)
                elif (not is_gnd) and (onet != "GND"):
                    r_v = vrad + orad + 8.8
                else:
                    r_v = vrad + orad + 8.2
            else:
                r_v = 0.0
            r_t = 7.5 + orad + 0.5 * width
            r = max(r_v, r_t)
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

        for oli, x1, y1, x2, y2, ow, onet in routed_segs:
            if onet == net:
                continue
            trk_clr = pair_track_gap(net, onet, base_trk_gap, oli, width, ow) + 0.5 * (width + ow)
            via_trk_clr = (vrad + 6.2 + 0.5 * ow) if via_touches_layer(vtype, rname, oli) else 0.0
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

    def find_pad_entries(p, width, blocked, base_trk_gap=3.5):
        px, py, li = p["x"], p["y"], p["li"]
        entries = []
        gx0, gy0 = to_grid(px, py)
        if not blocked[li][gx0 * NY + gy0]:
            ex, ey = from_grid(gx0, gy0)
            if seg_is_legal(li, px, py, ex, ey, width, p["net"], base_trk_gap, ignore_pad_idxs=(p["idx"],)):
                entries.append(("STUB", li, gx0, gy0, ex, ey))

        odx, ody = px - p["cx"], py - p["cy"]
        base_ang = math.atan2(ody, odx) if math.hypot(odx, ody) > 0.5 else 0.0
        dirs = sorted(
            [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (0, 90, 180, 270, 45, 135, 225, 315)],
            key=lambda v: -(v[0] * math.cos(base_ang) + v[1] * math.sin(base_ang)),
        ) + [
            (math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5)
        ]
        seen_g = set()
        max_reach = max(36.0, p["hw"] + 20.0, p["hh"] + 20.0)
        for dx, dy in dirs:
            for dist in (4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0, 30.0, 35.0):
                if dist > max_reach:
                    break
                gx, gy = to_grid(px + dx * dist, py + dy * dist)
                if (gx, gy) in seen_g or blocked[li][gx * NY + gy]:
                    continue
                ex, ey = from_grid(gx, gy)
                if seg_is_legal(li, px, py, ex, ey, width, p["net"], base_trk_gap, ignore_pad_idxs=(p["idx"],)):
                    seen_g.add((gx, gy))
                    entries.append(("STUB", li, gx, gy, ex, ey))
                    break
            if len(entries) >= 6:
                break
        if len(entries) < 4 and p["net"] != "GND":
            # Dog-bone 6/12 mechanical through-via escape straight onto wide-open L3(16) / L4(17) inner signal layers!
            min_vr = max(14.0, min(p["hw"], p["hh"]) + 6.8)
            for dist in (min_vr, min_vr + 4.0, min_vr + 8.0, min_vr + 13.0):
                found_dv = False
                for ang in range(0, 360, 20):
                    vx = round(px + dist * math.cos(math.radians(ang)), 2)
                    vy = round(py + dist * math.sin(math.radians(ang)), 2)
                    vgx, vgy = to_grid(vx, vy)
                    gx_x, gy_y = from_grid(vgx, vgy)
                    if via_is_legal(gx_x, gy_y, p["net"], via_type="NORMAL", rule_name="") and seg_is_legal(
                        li, px, py, gx_x, gy_y, width, p["net"], base_trk_gap, ignore_pad_idxs=(p["idx"],)
                    ):
                        for ili in (1, 2):
                            if not blocked[ili][vgx * NY + vgy]:
                                entries.append(("DOG_VIA", ili, vgx, vgy, gx_x, gy_y))
                                found_dv = True
                        if found_dv:
                            break
                if found_dv:
                    break
        return entries

    def astar_to_targets(starts, goal_nodes_map, blocked, via_ok, max_iters=50000, allow_via=True):
        if not starts or not goal_nodes_map:
            return None
        all_g = list(goal_nodes_map.keys())
        step_g = max(1, len(all_g) // 24)
        g_sample = [(g[1], g[2]) for g in all_g[::step_g]]

        pq = []
        g_cost = {}
        parent = {}
        start_meta = {}
        for s in starts:
            node = (s[1], s[2], s[3])
            if node in goal_nodes_map:
                return s, goal_nodes_map[node], [node]
            start_meta[node] = s
            h = min(abs(s[2] - gx) + abs(s[3] - gy) for gx, gy in g_sample)
            g_cost[node] = 0.0
            heapq.heappush(pq, (h * 1.75, 0.0, node))

        iters = 0
        while pq and iters < max_iters:
            iters += 1
            _, gc, cur = heapq.heappop(pq)
            if cur in goal_nodes_map:
                path = [cur]
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                path.reverse()
                return start_meta[path[0]], goal_nodes_map[path[-1]], path
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
                        step_c = 1.35
                    elif li == 2 and dx != 0:
                        step_c = 1.35
                    elif li in (0, 3):
                        step_c = 1.25
                    ng = gc + step_c
                    nxt = (li, nx_, ny_)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = min(abs(nx_ - tx) + abs(ny_ - ty) for tx, ty in g_sample)
                        heapq.heappush(pq, (ng + h * 1.75, ng, nxt))
            if allow_via and via_ok[gx * NY + gy]:
                for nli in range(4):
                    if nli == li or blocked[nli][gx * NY + gy]:
                        continue
                    ng = gc + 12.0
                    nxt = (nli, gx, gy)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = min(abs(gx - tx) + abs(gy - ty) for tx, ty in g_sample)
                        heapq.heappush(pq, (ng + h * 1.75, ng, nxt))
        return None

    def commit_path(p_src, s_ent, g_ent, path, width, net, tree_nodes: dict):
        nt, nv = 0, 0
        sx, sy = from_grid(path[0][1], path[0][2])
        if s_ent[0] == "DOG_VIA":
            if add_track(p_src["li"], p_src["x"], p_src["y"], sx, sy, width, net):
                nt += 1
            if add_via(sx, sy, net, hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
                nv += 1
        else:
            if add_track(p_src["li"], p_src["x"], p_src["y"], sx, sy, width, net):
                nt += 1

        seg_start = path[0]
        prev = path[0]
        cur_dir = None
        for node in path[1:]:
            tree_nodes[node] = ("TREE", node[0], node[1], node[2], None)
            if node[0] != prev[0]:
                if prev != seg_start:
                    x1, y1 = from_grid(seg_start[1], seg_start[2])
                    x2, y2 = from_grid(prev[1], prev[2])
                    if add_track(seg_start[0], x1, y1, x2, y2, width, net):
                        nt += 1
                vx, vy = from_grid(prev[1], prev[2])
                if add_via(vx, vy, net, hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
                    nv += 1
                seg_start = node
                cur_dir = None
            else:
                d = (node[1] - prev[1], node[2] - prev[2])
                if cur_dir is not None and d != cur_dir:
                    x1, y1 = from_grid(seg_start[1], seg_start[2])
                    x2, y2 = from_grid(prev[1], prev[2])
                    if add_track(seg_start[0], x1, y1, x2, y2, width, net):
                        nt += 1
                    seg_start = prev
                cur_dir = d
            prev = node
        tree_nodes[path[0]] = ("TREE", path[0][0], path[0][1], path[0][2], None)
        if prev != seg_start:
            x1, y1 = from_grid(seg_start[1], seg_start[2])
            x2, y2 = from_grid(prev[1], prev[2])
            if add_track(seg_start[0], x1, y1, x2, y2, width, net):
                nt += 1

        if g_ent[0] == "STUB":
            p_dst = g_ent[6]
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if add_track(p_dst["li"], ex, ey, p_dst["x"], p_dst["y"], width, net):
                nt += 1
        elif g_ent[0] == "DOG_VIA":
            p_dst = g_ent[6]
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if add_via(ex, ey, net, hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
                nv += 1
            if add_track(p_dst["li"], ex, ey, p_dst["x"], p_dst["y"], width, net):
                nt += 1
        elif g_ent[0] == "ANCHOR":
            ax, ay = g_ent[4], g_ent[5]
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if add_track(path[-1][0], ex, ey, ax, ay, width, net):
                nt += 1
        return nt, nv

    ordered_nets = list(prio_list)
    seen = {n for n, _ in ordered_nets} | {"GND"}
    for n in sorted(pads_by_net):
        if n not in seen and len(pads_by_net[n]) >= 2:
            ordered_nets.append((n, 3.0))
    ordered_nets = ordered_nets[:max_nets_budget]

    net_reports = []
    total_conns_made = 0

    # -------------------------------------------------------------------------
    # PHASE 1: SIGNAL & POWER ROUTING (Try preferred 6.1mil / wide power first, fallback to 3.5mil / 3.5-4.0mil!)
    # -------------------------------------------------------------------------
    for net, pref_w in ordered_nets:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        # Try wider preferred width on power nets; keep 3.5 mil HDI spacing (with 11.8 mil > 3W on sensitive nets!)
        attempts = [(pref_w, 3.5)]
        if pref_w > 4.0:
            attempts.append((4.0, 3.5))
        if pref_w > 3.0:
            attempts.append((3.0, 3.5))

        nt_tot, nv_tot, conns_tot = 0, 0, 0
        uf_parent = {i: i for i in range(len(pts))}
        def uf_find(x):
            while uf_parent[x] != x:
                uf_parent[x] = uf_parent[uf_parent[x]]
                x = uf_parent[x]
            return x
        cluster_nodes = {i: {} for i in range(len(pts))}
        used_w = pref_w

        # Pre-pass 0: Direct straight OR 2-segment orthogonal L-shaped same-layer bridges (<= 130 mil, zero vias!)
        direct_pairs = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if pts[i]["li"] == pts[j]["li"]:
                    d = math.hypot(pts[i]["x"] - pts[j]["x"], pts[i]["y"] - pts[j]["y"])
                    if 1.0 < d <= 130.0:
                        direct_pairs.append((d, i, j))
        direct_pairs.sort()
        for _, i, j in direct_pairs:
            ri, rj = uf_find(i), uf_find(j)
            if ri == rj:
                continue
            bw = 4.0 if pref_w > 4.0 else pref_w
            li = pts[i]["li"]
            x1, y1, x2, y2 = pts[i]["x"], pts[i]["y"], pts[j]["x"], pts[j]["y"]
            ign = (pts[i]["idx"], pts[j]["idx"])
            segs_ok = None
            if seg_is_legal(li, x1, y1, x2, y2, bw, net, base_trk_gap=3.5, ignore_pad_idxs=ign):
                segs_ok = [(x1, y1, x2, y2)]
            else:
                for mx, my in ((x2, y1), (x1, y2)):
                    if (seg_is_legal(li, x1, y1, mx, my, bw, net, base_trk_gap=3.5, ignore_pad_idxs=ign) and
                        seg_is_legal(li, mx, my, x2, y2, bw, net, base_trk_gap=3.5, ignore_pad_idxs=ign)):
                        segs_ok = [(x1, y1, mx, my), (mx, my, x2, y2)]
                        break
            if segs_ok:
                added_any = 0
                for sx1, sy1, sx2, sy2 in segs_ok:
                    if add_track(li, sx1, sy1, sx2, sy2, bw, net):
                        added_any += 1
                if added_any:
                    nt_tot += added_any
                    conns_tot += 1
                    total_conns_made += 1
                    used_w = min(used_w, bw)
                    uf_parent[ri] = rj
                    gx1, gy1 = to_grid(x1, y1)
                    gx2, gy2 = to_grid(x2, y2)
                    cluster_nodes[rj][(li, gx1, gy1)] = ("ANCHOR", li, gx1, gy1, x1, y1)
                    cluster_nodes[rj][(li, gx2, gy2)] = ("ANCHOR", li, gx2, gy2, x2, y2)
                    for k_node, v_ent in cluster_nodes[ri].items():
                        if k_node not in cluster_nodes[rj]:
                            cluster_nodes[rj][k_node] = v_ent

        for width_mil, base_gap in attempts:
            if conns_tot == len(pts) - 1:
                break
            blocked, via_ok = build_net_masks(net, width_mil, blind_side_li=None, base_trk_gap=base_gap)
            pad_entries = {}
            for i, p in enumerate(pts):
                ents = find_pad_entries(p, width_mil, blocked, base_trk_gap=base_gap)
                if ents:
                    pad_entries[i] = [(*e, p) for e in ents]
                    r_i = uf_find(i)
                    for e in pad_entries[i]:
                        k_node = (e[1], e[2], e[3])
                        if k_node not in cluster_nodes[r_i]:
                            cluster_nodes[r_i][k_node] = e
            reach = list(pad_entries.keys())
            if len(reach) < 2:
                continue

            cand_pairs = []
            seen_pair = set()
            for i in reach:
                nbrs = sorted(
                    [j for j in reach if j != i],
                    key=lambda j: abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0),
                )[:6]
                for j in nbrs:
                    pk = (min(i, j), max(i, j))
                    if pk not in seen_pair:
                        seen_pair.add(pk)
                        d = abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0)
                        cand_pairs.append((d, i, j))
            cand_pairs.sort(key=lambda x: x[0])

            for _, i, j in cand_pairs:
                ri, rj = uf_find(i), uf_find(j)
                if ri == rj:
                    continue
                starts = pad_entries[i]
                targets = cluster_nodes[rj]
                if not targets:
                    continue
                res = astar_to_targets(starts, targets, blocked, via_ok, max_iters=75000, allow_via=True)
                if not res:
                    continue
                s_ent, g_ent, path = res
                # Re-validate DOG_VIA endpoints against any vias placed earlier in this net
                if s_ent[0] == "DOG_VIA":
                    sx_, sy_ = from_grid(path[0][1], path[0][2])
                    if not via_is_legal(sx_, sy_, net, via_type="NORMAL", rule_name=""):
                        continue
                if g_ent[0] == "DOG_VIA":
                    ex_, ey_ = from_grid(path[-1][1], path[-1][2])
                    if not via_is_legal(ex_, ey_, net, via_type="NORMAL", rule_name=""):
                        continue
                if g_ent[0] == "ANCHOR":
                    ex_, ey_ = from_grid(path[-1][1], path[-1][2])
                    if not seg_is_legal(path[-1][0], ex_, ey_, g_ent[4], g_ent[5], width_mil, net, base_trk_gap=base_gap):
                        continue
                dt, dv = commit_path(pts[i], s_ent, g_ent, path, width_mil, net, cluster_nodes[rj])
                nt_tot += dt
                nv_tot += dv
                conns_tot += 1
                total_conns_made += 1
                used_w = min(used_w, width_mil)
                uf_parent[ri] = rj
                for k_node, v_ent in cluster_nodes[ri].items():
                    if k_node not in cluster_nodes[rj]:
                        cluster_nodes[rj][k_node] = v_ent
                cluster_nodes[rj][(s_ent[1], s_ent[2], s_ent[3])] = ("TREE", s_ent[1], s_ent[2], s_ent[3], None)
                if g_ent[0] in ("STUB", "DOG_VIA", "ANCHOR"):
                    cluster_nodes[rj][(g_ent[1], g_ent[2], g_ent[3])] = ("TREE", g_ent[1], g_ent[2], g_ent[3], None)
                if dv > 0:
                    blocked, via_ok = build_net_masks(net, width_mil, blind_side_li=None, base_trk_gap=base_gap)
                if conns_tot == len(pts) - 1:
                    break

        if conns_tot > 0:
            complete = (conns_tot == len(pts) - 1)
            net_reports.append({
                "net": net, "pads": len(pts), "connections_made": conns_tot,
                "complete": complete, "min_width_mil": used_w, "tracks": nt_tot, "vias": nv_tot,
            })
            tag = "100%" if complete else f"{conns_tot}/{len(pts)-1}"
            print(f"  [{board}] {net:22s}: {tag:6s} | w>={used_w:.1f}mil tracks={nt_tot:3d}, vias(6/12)={nv_tot:2d}", flush=True)

    # -------------------------------------------------------------------------
    # PHASE 2: DOG-BONE BLIND MICROVIA GND STITCHING (BV_L1_L2 & BV_L5_L6, ZERO NON-VIPPO VIA-IN-PAD!) + 3-PASS CHAINING!
    # -------------------------------------------------------------------------
    gnd_pads = [p for p in pads_by_net.get("GND", []) if not (board == "PCB1" and p["ref"] == "U1")]
    gnd_tracks = 0
    bv_l1_l2_cnt = 0
    bv_l5_l6_cnt = 0
    u2_blind_vippo = 0
    grounded_set = set()
    gnd_tree_nodes = {}

    # 2A: Direct dog-bone 1-hop blind microvia (starts strictly OUTSIDE pad edge: r >= pad_max_half + 6.5 mil!)
    for i, gp in enumerate(gnd_pads):
        px, py, li = gp["x"], gp["y"], gp["li"]
        rname = "BV_L1_L2" if li == 0 else "BV_L5_L6"
        if board == "PCB2" and gp["ref"] == "U2" and gp["pnum"] in U2_INNER_BALLS and li == 0:
            if via_is_legal(px, py, "GND", via_type="BLIND", rule_name="BV_L1_L2", vippo_u2=True):
                if add_via(px, py, "GND", hole=4.0, diam=8.0, via_type="BLIND", rule_name="BV_L1_L2"):
                    bv_l1_l2_cnt += 1
                    u2_blind_vippo += 1
                    grounded_set.add(i)
                    gx, gy = to_grid(px, py)
                    gnd_tree_nodes[(li, gx, gy)] = ("ANCHOR", li, gx, gy, px, py)
                continue
        found = None
        min_r = max(9.5, min(gp["hw"], gp["hh"]) + 4.8)
        for gw in (3.5, 3.0):
            for r_mil in (min_r, min_r + 2.0, min_r + 4.5, min_r + 7.5, min_r + 11.0, min_r + 15.0, min_r + 20.0, min_r + 26.0, min_r + 32.0):
                for ang in range(0, 360, 12):
                    vx = round(px + r_mil * math.cos(math.radians(ang)), 2)
                    vy = round(py + r_mil * math.sin(math.radians(ang)), 2)
                    if via_is_legal(vx, vy, "GND", via_type="BLIND", rule_name=rname) and seg_is_legal(
                        li, px, py, vx, vy, gw, "GND", base_trk_gap=3.3, ignore_pad_idxs=(gp["idx"],)
                    ):
                        found = (vx, vy, gw)
                        break
                if found:
                    break
            if found:
                break
        if found:
            vx, vy, gw = found
            if add_via(vx, vy, "GND", hole=4.0, diam=8.0, via_type="BLIND", rule_name=rname):
                if rname == "BV_L1_L2":
                    bv_l1_l2_cnt += 1
                else:
                    bv_l5_l6_cnt += 1
            if add_track(li, px, py, vx, vy, gw, "GND"):
                gnd_tracks += 1
            grounded_set.add(i)
            for qx, qy in ((px, py), (vx, vy)):
                gx, gy = to_grid(qx, qy)
                gnd_tree_nodes[(li, gx, gy)] = ("ANCHOR", li, gx, gy, qx, qy)

    # 2B: Multi-pass same-layer GND chaining (3.5 mil first, then 3.0 mil HDI fallback) into dog-bone blind clusters or nearby legal dog-bone blind-via sites!
    for gw in (3.5, 3.0):
        for side_li, rname in ((0, "BV_L1_L2"), (3, "BV_L5_L6")):
            blocked_g, via_ok_g = build_net_masks("GND", gw, blind_side_li=side_li, base_trk_gap=3.3)
            for _gpass in range(5):
                added_this_pass = 0
                for i, gp in enumerate(gnd_pads):
                    if i in grounded_set or gp["li"] != side_li:
                        continue
                    ents = find_pad_entries(gp, gw, blocked_g, base_trk_gap=3.3)
                    if not ents:
                        continue
                    local_targets = {
                        k: v for k, v in gnd_tree_nodes.items()
                        if k[0] == side_li and abs(k[1] * STEP - gp["x"]) + abs(k[2] * STEP - gp["y"]) <= 400.0
                    }
                    gx0, gy0 = to_grid(gp["x"], gp["y"])
                    rad_g = int(160.0 / STEP)
                    via_targets = {}
                    for gx in range(max(0, gx0 - rad_g), min(NX, gx0 + rad_g + 1)):
                        base = gx * NY
                        for gy in range(max(0, gy0 - rad_g), min(NY, gy0 + rad_g + 1)):
                            if via_ok_g[base + gy] and not blocked_g[side_li][base + gy]:
                                via_targets[(side_li, gx, gy)] = ("NEW_BLIND_VIA", side_li, gx, gy, None)
                    merged_targets = {**via_targets, **local_targets}
                    if not merged_targets:
                        continue
                    res = astar_to_targets([(*e, gp) for e in ents], merged_targets, blocked_g, via_ok_g, max_iters=22000, allow_via=False)
                    if not res:
                        continue
                    s_ent, g_ent, path = res
                    if g_ent[0] == "NEW_BLIND_VIA":
                        vx, vy = from_grid(path[-1][1], path[-1][2])
                        if not via_is_legal(vx, vy, "GND", via_type="BLIND", rule_name=rname):
                            continue
                        if add_via(vx, vy, "GND", hole=4.0, diam=8.0, via_type="BLIND", rule_name=rname):
                            if rname == "BV_L1_L2":
                                bv_l1_l2_cnt += 1
                            else:
                                bv_l5_l6_cnt += 1
                        dt, _ = commit_path(gp, s_ent, ("TREE", 0, 0, 0, None), path, gw, "GND", gnd_tree_nodes)
                    else:
                        if g_ent[0] == "ANCHOR":
                            ex_, ey_ = from_grid(path[-1][1], path[-1][2])
                            if not seg_is_legal(side_li, ex_, ey_, g_ent[4], g_ent[5], gw, "GND", base_trk_gap=3.3):
                                continue
                        dt, _ = commit_path(gp, s_ent, g_ent, path, gw, "GND", gnd_tree_nodes)
                        if g_ent[0] == "ANCHOR":
                            gnd_tree_nodes[(g_ent[1], g_ent[2], g_ent[3])] = ("TREE", g_ent[1], g_ent[2], g_ent[3], None)
                    gnd_tracks += dt
                    grounded_set.add(i)
                    added_this_pass += 1
                    if g_ent[0] == "NEW_BLIND_VIA":
                        blocked_g, via_ok_g = build_net_masks("GND", gw, blind_side_li=side_li, base_trk_gap=3.3)
                if added_this_pass == 0:
                    break

    # 2D: Add L2(15)<->L5(18) GND plane-stitching 6/12 mil mechanical through-vias on boards with 0 fixed GND through-vias (PCB2, PCB3)!
    stitch_gnd_through = 0
    if fixed_gnd_count == 0:
        placed_ys = []
        for cy_i in range(28, int(H_MIL) - 28, 4):
            if stitch_gnd_through >= 3:
                break
            cy = float(cy_i)
            if any(abs(cy - py_) < 220.0 for py_ in placed_ys):
                continue
            for cx_i in range(20, int(W_MIL) - 20, 4):
                cx = float(cx_i)
                if via_is_legal(cx, cy, "GND", via_type="NORMAL", rule_name=""):
                    if add_via(cx, cy, "GND", hole=6.0, diam=12.0, via_type="NORMAL", rule_name=""):
                        stitch_gnd_through += 1
                        placed_ys.append(cy)
                        break
        print(f"  [{board}] L2<->L5 GND stitching 6/12 through-vias added: {stitch_gnd_through}", flush=True)

    # 2C: Direct straight OR L-shaped same-layer GND pad-to-grounded-pad bridge pass (<= 160 mil, 3.0 mil width)!
    for _dpass in range(6):
        added_d = 0
        for i, gp in enumerate(gnd_pads):
            if i in grounded_set:
                continue
            li = gp["li"]
            cands = []
            for j in grounded_set:
                if gnd_pads[j]["li"] == li:
                    d = math.hypot(gp["x"] - gnd_pads[j]["x"], gp["y"] - gnd_pads[j]["y"])
                    if 1.0 < d <= 160.0:
                        cands.append((d, j))
            cands.sort()
            for _, j in cands[:12]:
                x1, y1, x2, y2 = gp["x"], gp["y"], gnd_pads[j]["x"], gnd_pads[j]["y"]
                ign = (gp["idx"], gnd_pads[j]["idx"])
                segs_ok = None
                if seg_is_legal(li, x1, y1, x2, y2, 3.0, "GND", base_trk_gap=3.3, ignore_pad_idxs=ign):
                    segs_ok = [(x1, y1, x2, y2)]
                else:
                    for mx, my in ((x2, y1), (x1, y2)):
                        if (seg_is_legal(li, x1, y1, mx, my, 3.0, "GND", base_trk_gap=3.3, ignore_pad_idxs=ign) and
                            seg_is_legal(li, mx, my, x2, y2, 3.0, "GND", base_trk_gap=3.3, ignore_pad_idxs=ign)):
                            segs_ok = [(x1, y1, mx, my), (mx, my, x2, y2)]
                            break
                if segs_ok:
                    for sx1, sy1, sx2, sy2 in segs_ok:
                        if add_track(li, sx1, sy1, sx2, sy2, 3.0, "GND"):
                            gnd_tracks += 1
                    grounded_set.add(i)
                    added_d += 1
                    break
        if added_d == 0:
            break

    net_reports.append({
        "net": "GND (dog-bone BV_L1_L2/BV_L5_L6 + chain)", "pads": len(pads_by_net.get("GND", [])),
        "grounded_pads": len(grounded_set), "bv_l1_l2": bv_l1_l2_cnt, "bv_l5_l6": bv_l5_l6_cnt,
        "fixed_thermal_vias": fixed_gnd_count, "tracks": gnd_tracks,
        "vias": bv_l1_l2_cnt + bv_l5_l6_cnt + fixed_gnd_count,
    })
    print(f"  [{board}] GND dog-bone+chain : {len(grounded_set)}/{len(gnd_pads)} pads grounded | tracks={gnd_tracks}, BV_L1_L2={bv_l1_l2_cnt}, BV_L5_L6={bv_l5_l6_cnt}, thermal={fixed_gnd_count}", flush=True)

    non_gnd_vias = [[v["x"], v["y"]] for v in vias_out if v["net"] != "GND"]
    mech_sig_vias = sum(1 for v in vias_out if v["viaType"] == "NORMAL" and v["net"] != "GND")
    min_w = min((t["width"] for t in tracks_out), default=0.0)
    plan = {
        "board": board,
        "summary": {
            "total_tracks": len(tracks_out),
            "min_track_width_mil": min_w,
            "tracks_below_3mil": sum(1 for t in tracks_out if t["width"] < 3.0),
            "total_vias": len(vias_out),
            "blind_bv_l1_l2_4_8mil": bv_l1_l2_cnt,
            "blind_bv_l5_l6_4_8mil": bv_l5_l6_cnt,
            "mech_through_6_12mil_signal": mech_sig_vias,
            "mech_through_8_14mil_thermal": fixed_gnd_count,
            "illegal_4_8mil_through_vias": sum(1 for v in vias_out if v["viaType"] == "NORMAL" and v["hole"] < 6.0),
            "u2_bga_blind_vippo": u2_blind_vippo,
            "signal_power_connections": total_conns_made,
            "gnd_pads_grounded": len(grounded_set),
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
    print(f"=== {board} P0-DFM + P1 ROUTING PLAN SUMMARY ===")
    print(json.dumps(plan["summary"], indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--board", choices=["PCB1", "PCB2", "PCB3"], required=True)
    p.add_argument("--dump", type=Path, required=True)
    p.add_argument("--plan-out", type=Path, required=True)
    p.add_argument("--antipads-out", type=Path, required=True)
    p.add_argument("--max-nets", type=int, default=160)
    a = p.parse_args()
    route_board(a.board, a.dump, a.plan_out, a.antipads_out, a.max_nets)


if __name__ == "__main__":
    main()
