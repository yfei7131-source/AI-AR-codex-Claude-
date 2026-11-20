#!/usr/bin/env python3
"""HDI-DFM-Compliant 4-Signal-Layer (L1/L3/L4/L6) Kruskal-Steiner + Blind Microvia (BV_L1_L2 / BV_L5_L6) Router.

Manufacturing constraints strictly enforced (ZERO rule relaxation):
  - Symmetric 1+4+1 6-Layer HDI stackup: L1 Top(1) / L2 GND(15) / L3 Sig(16) / L4 Sig(17) / L5 GND(18) / L6 Bot(2).
  - ZERO < 3.0 mil fine-line tracks: minimum trace width = 3.0 mil (0.0762 mm, JLCPCB/PCBWay std 6L HDI);
    power/GND = 3.5-4.0 mil (0.089-0.102 mm).
  - ZERO illegal 4/8 mil through-vias:
      * 4/8 mil (0.10/0.20 mm) vias are STRICTLY true laser blind microvias:
          - BV_L1_L2 (layer 1 <-> 15): Top-side GND stitch / VIPPO microvias (never pierce L3/L4/L5/L6!).
          - BV_L5_L6 (layer 18 <-> 2): Bottom-side GND stitch microvias (never pierce L1/L2/L3/L4!).
      * All L1 <-> L3/L4/L6 signal & power transitions use 6/12 mil (0.15/0.30 mm) NORMAL mechanical through-vias
        with r = 17.8 mil SDF-union anti-pads on L2 (15) & L5 (18) GND planes.
      * U1 ESP32-S3 EPAD thermal array uses 9x 8/14 mil (0.20/0.35 mm) NORMAL mechanical through-vias.
"""

import argparse
import heapq
import json
import math
from pathlib import Path

L_IDS = [1, 16, 17, 2]  # 0=L1 Top, 1=L3 Inner2(Sig), 2=L4 Inner3(Sig), 3=L6 Bottom
SIDE_TO_LI = {1: 0, 2: 3}
U2_INNER_BALLS = {"B2", "C2", "D2", "E2", "B3", "C3", "D3", "E3", "B4", "C4", "D4", "E4"}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ALL trace widths >= 3.0 mil (ZERO 2.5 mil tracks!)
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
    ("1V8_FPGA_VPP", 3.5), ("1V2_FPGA_PLL", 3.5), ("1V2_FPGA_CORE", 3.5), ("1V8_SYS", 3.5), ("1V8_FPGA_IO", 3.5), ("VSYS", 3.5),
]

PCB1_PRIORITY = [
    ("ESP_ANT_FEED", 3.5), ("ESP_RF_ANT", 3.5),
    ("USB_DP", 3.0), ("USB_DM", 3.0), ("USB_LIM_ILIM", 3.0), ("VBUS_5V_USB", 4.0), ("VBUS_5V", 4.0),
    ("LED_3V3_PRIV", 3.5), ("PRIV_LED_ANODE", 3.5), ("PRIV_VTH_H", 3.0), ("PRIV_VTH_L", 3.0),
    ("PRIV_WINDOW_OK", 3.0), ("PRIV_WINDOW_OK_F", 3.0), ("CAM_PWR_REQ", 3.0), ("CAM_DOVDD_OK_3V3", 3.0),
    ("I2S_BCLK_1V8", 3.0), ("I2S_LRCLK_1V8", 3.0), ("I2S_AMP_DIN_1V8", 3.0), ("I2S_S3_DOUT_1V8", 3.0),
    ("I2S_BCLK_3V3", 3.0), ("I2S_LRCLK_3V3", 3.0), ("I2S_S3_DOUT_3V3", 3.0), ("AMP_SD_MODE_1V8", 3.0),
    ("IPC_NRF_TX_1V8", 3.0), ("IPC_S3_TX_1V8", 3.0), ("IPC_NRF_TX_3V3", 3.0), ("IPC_S3_TX_3V3", 3.0),
    ("SYS_I2C_SCL_1V8", 3.0), ("SYS_I2C_SDA_1V8", 3.0), ("SYS_I2C_SCL_3V3", 3.0), ("SYS_I2C_SDA_3V3", 3.0),
    ("PDM_CLK_1V8", 3.0), ("PDM_D0_1V8", 3.0), ("PDM_D1_1V8", 3.0),
    ("host_sck_3v3", 3.0), ("host_cs_n_3v3", 3.0), ("host_qio0_3v3", 3.0), ("host_qio1_3v3", 3.0), ("host_qio2_3v3", 3.0), ("host_qio3_3v3", 3.0),
    ("ESP_VDD_SPI_3V3", 3.5), ("1V8_FPGA_IO", 3.5), ("VBAT_L", 4.0), ("VBAT_R_ISOLATED", 4.0), ("VBAT_R_RET", 4.0),
    ("BK_SW", 3.5), ("BB_L1", 3.5), ("BB_L2", 3.5), ("BB_FB", 3.0),
    ("VSYS", 4.0), ("1V8_SYS", 4.0), ("3V3_SYS", 4.0),
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
    """Return (W_MIL, H_MIL, STEP, inside_track_fn, inside_via_fn, mic_ref, priority_list, fixed_gnd_vias)."""
    if board == "PCB2":
        W, H = 181.1024, 984.2520
        def in_trk(x, y, margin):
            return margin <= x <= W - margin and margin <= y <= H - margin
        def in_via(x, y, is_gnd):
            # Signal 6/12 through-via has r=17.8 anti-pad -> needs >= 30.0 mil from board edge (> 10.5 + 17.8 + 1.7)
            m = 18.0 if is_gnd else 30.0
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
            m = 18.5 if is_gnd else 30.5
            pad_e = 8.0 if is_gnd else 19.5
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
            m = 18.5 if is_gnd else 30.5
            y_lo = 168.0 + (8.0 if is_gnd else 19.5)
            return m <= x <= W - m and y_lo <= y <= H - m
        return W, H, 2.5, in_trk, in_via, "MK3", PCB3_PRIORITY, []
    raise ValueError(f"Unknown board {board}")


def via_touches_layer(vtype: str, rule_name: str, li: int) -> bool:
    """Return True if a via physically exists on signal-layer index li (0=L1, 1=L3, 2=L4, 3=L6)."""
    if vtype != "BLIND":
        return True
    if rule_name == "BV_L1_L2":
        return li == 0
    if rule_name == "BV_L5_L6":
        return li == 3
    return True


def vias_share_vertical_span(vt1: str, rn1: str, vt2: str, rn2: str) -> bool:
    """Return True if two vias overlap in Z-stackup (e.g., BV_L1_L2 and BV_L5_L6 do NOT overlap in Z!)."""
    if vt1 == "BLIND" and vt2 == "BLIND" and rn1 != rn2:
        return False
    return True


def route_board(board: str, dump_path: Path, plan_out: Path, antipads_out: Path, max_nets_budget: int = 140):
    W_MIL, H_MIL, STEP, in_trk, in_via, mic_ref, prio_list, fixed_gnd_vias = board_geometry(board)
    NX = int(W_MIL / STEP) + 1
    NY = int(H_MIL / STEP) + 1
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))

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
    # placed_vias: (vx, vy, outer_r, net, via_type, rule_name)
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
        if math.hypot(x2 - x1, y2 - y1) < 0.2:
            return False
        for oli, ox1, oy1, ox2, oy2, _, onet in routed_segs:
            if oli == li and onet == net:
                if (math.hypot(x1 - ox1, y1 - oy1) < 0.3 and math.hypot(x2 - ox2, y2 - oy2) < 0.3) or (
                    math.hypot(x1 - ox2, y1 - oy2) < 0.3 and math.hypot(x2 - ox1, y2 - oy1) < 0.3
                ):
                    return False
        routed_segs.append((li, x1, y1, x2, y2, width, net))
        tracks_out.append({
            "layer": L_IDS[li], "x1": round(x1, 2), "y1": round(y1, 2),
            "x2": round(x2, 2), "y2": round(y2, 2), "width": width, "net": net,
        })
        return True

    # Seed fixed GND thermal mechanical through-vias (U1 9x 8/14 mil EPAD vias on PCB1)
    fixed_gnd_count = 0
    for vx, vy, h_m, d_m in fixed_gnd_vias:
        if add_via(vx, vy, "GND", h_m, d_m, "NORMAL", ""):
            fixed_gnd_count += 1

    def via_is_legal(vx, vy, net, via_type="NORMAL", rule_name="", vippo_u2=False):
        is_gnd = (net == "GND")
        vrad = 4.0 if via_type == "BLIND" else 6.0  # 4/8 blind microvia vs 6/12 mech through-via
        if not in_via(vx, vy, is_gnd):
            return False
        # Acoustic port keepout (NPTH + L2/L5 r=28 mil cutout)
        mk_r = 37.5 if is_gnd else 49.0
        if math.hypot(vx - mic_hx, vy - mic_hy) < mk_r:
            return False
        if (not is_gnd or rule_name == "BV_L5_L6") and in_mic_body(vx, vy, 13.0):
            return False
        # Via-to-via clearance (respecting Z-span: BV_L1_L2 and BV_L5_L6 don't share Z layers!)
        for ovx, ovy, orad, onet, ovt, orn in placed_vias:
            if not vias_share_vertical_span(via_type, rule_name, ovt, orn):
                continue
            d = math.hypot(vx - ovx, vy - ovy)
            # If one is a non-GND through-via (r=17.8 anti-pad on L2/L5) and other is GND (touches L2/L5), keep clear of anti-pad!
            if (is_gnd and onet != "GND") or ((not is_gnd) and onet == "GND"):
                min_vv = 19.5 + (vrad if is_gnd else orad)
            elif (not is_gnd) and (onet != "GND"):
                min_vv = vrad + orad + 8.5  # 6+6+8.5 = 20.5 mil (> 6 mil pad-pad & drill-drill!)
            else:
                min_vv = vrad + orad + 8.0  # GND-GND same-span
            if d < min_vv:
                return False
        # Pad clearance (ONLY check pads on layers this via physically touches!)
        for p in all_pads:
            if p["net"] == net:
                continue
            if not via_touches_layer(via_type, rule_name, p["li"]):
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            dist = math.hypot(dx, dy)
            if vippo_u2 and p["ref"] == "U2" and p["li"] == 0:
                if dist < 6.8:
                    return False
            else:
                # Pad-to-via edge >= 7.2 mil (> 6.0) AND Hole-to-pad >= 7.8 mil (> 6.9)
                if dist < vrad + 7.6:
                    return False
        # Track clearance (ONLY check tracks on layers this via physically touches!)
        for oli, x1, y1, x2, y2, w, onet in routed_segs:
            if onet == net:
                continue
            if not via_touches_layer(via_type, rule_name, oli):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < vrad + 7.6 + 0.5 * w:
                return False
        return True

    def seg_is_legal(li, x1, y1, x2, y2, width, net):
        margin = 14.0 + 0.5 * width
        if not (in_trk(x1, y1, margin) and in_trk(x2, y2, margin)):
            return False
        if pt_seg_dist(mic_hx, mic_hy, x1, y1, x2, y2) < 33.5 + 0.5 * width:
            return False
        if li == 3 and net != "GND":
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                if in_mic_body(x1 + t * (x2 - x1), y1 + t * (y2 - y1), 7.5 + 0.5 * width):
                    return False
        for vx, vy, vrad, onet, ovt, orn in placed_vias:
            if onet == net:
                continue
            if not via_touches_layer(ovt, orn, li):
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 7.4 + vrad + 0.5 * width:
                return False
        steps = max(3, int(math.hypot(x2 - x1, y2 - y1) / 2.0) + 1)
        if li in (0, 3):
            clr = 6.55 + 0.5 * width
            for p in all_pads:
                if p["li"] != li or p["net"] == net:
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
            min_d = 3.25 + 0.5 * (width + ow)  # >= 3.25 mil track-track gap (> 3.0 mil JLCPCB std!)
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if pt_seg_dist(cx, cy, ox1, oy1, ox2, oy2) < min_d:
                    return False
        return True

    def build_net_masks(net, width, blind_side_li=None):
        """Build 4-layer track obstacle masks and via_ok mask.
        If blind_side_li is 0 (BV_L1_L2) or 3 (BV_L5_L6), via_ok is computed for a 4/8 blind GND microvia on that side ONLY!
        Otherwise via_ok is computed for a 6/12 mechanical through-via (L1-L6)."""
        is_gnd = (net == "GND")
        is_blind = (blind_side_li is not None)
        vtype = "BLIND" if is_blind else "NORMAL"
        rname = "BV_L1_L2" if blind_side_li == 0 else ("BV_L5_L6" if blind_side_li == 3 else "")
        vrad = 4.0 if is_blind else 6.0

        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))
        t_margin = 14.0 + 0.5 * width
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
                if not is_gnd:
                    if in_mic_body(x, y, 7.5 + 0.5 * width):
                        blocked[3][idx] = 1
                    if in_mic_body(x, y, 13.0):
                        via_ok[idx] = 0
                elif rname == "BV_L5_L6" and in_mic_body(x, y, 13.0):
                    via_ok[idx] = 0

        pad_clr = 6.55 + 0.5 * width
        via_pad_clr = vrad + 7.2  # 11.2 for blind 4/8, 13.2 for mech 6/12 (>6.0 pad-via & >6.9 hole-pad!)
        for p in all_pads:
            if p["net"] == net:
                continue
            li = p["li"]
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
            trk_clr = 3.25 + 0.5 * (width + ow)
            via_trk_clr = (vrad + 7.2 + 0.5 * ow) if via_touches_layer(vtype, rname, oli) else 0.0
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

    def find_pad_entries(p, width, blocked):
        px, py, li = p["x"], p["y"], p["li"]
        entries = []
        gx0, gy0 = to_grid(px, py)
        if not blocked[li][gx0 * NY + gy0]:
            ex, ey = from_grid(gx0, gy0)
            if seg_is_legal(li, px, py, ex, ey, width, p["net"]):
                entries.append(("STUB", li, gx0, gy0, ex, ey))

        odx, ody = px - p["cx"], py - p["cy"]
        base_ang = math.atan2(ody, odx) if math.hypot(odx, ody) > 0.5 else 0.0
        # Prefer orthogonal/45-degree exits, with 22.5-degree fallback for dense fine-pitch pads
        dirs = sorted(
            [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (0, 90, 180, 270, 45, 135, 225, 315)],
            key=lambda v: -(v[0] * math.cos(base_ang) + v[1] * math.sin(base_ang)),
        ) + [
            (math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5)
        ]
        seen_g = set()
        max_reach = max(24.0, p["hw"] + 16.0, p["hh"] + 16.0)
        for dx, dy in dirs:
            for dist in (4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0, 30.0):
                if dist > max_reach:
                    break
                gx, gy = to_grid(px + dx * dist, py + dy * dist)
                if (gx, gy) in seen_g or blocked[li][gx * NY + gy]:
                    continue
                ex, ey = from_grid(gx, gy)
                if seg_is_legal(li, px, py, ex, ey, width, p["net"]):
                    seen_g.add((gx, gy))
                    entries.append(("STUB", li, gx, gy, ex, ey))
                    break
            if len(entries) >= 6:
                break
        return entries

    def astar_to_targets(starts, goal_nodes_map, blocked, via_ok, max_iters=45000, allow_via=True):
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
                    # L3(1) prefers X, L4(2) prefers Y, L1/L6 slight penalty to keep outer layers clean
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
                    ng = gc + 12.0  # Encourage clean inner-layer L3/L4 hops via 6/12 mech through-vias
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
                # Signal/power layer change = 6/12 mil (0.15/0.30 mm) NORMAL mechanical through-via!
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
        return nt, nv

    # Ordered net list — ALL widths >= 3.0 mil!
    ordered_nets = list(prio_list)
    seen = {n for n, _ in ordered_nets} | {"GND"}
    for n in sorted(pads_by_net):
        if n not in seen and len(pads_by_net[n]) >= 2:
            ordered_nets.append((n, 3.0))
    ordered_nets = ordered_nets[:max_nets_budget]

    net_reports = []
    total_conns_made = 0

    # -------------------------------------------------------------------------
    # PHASE 1: 4-LAYER (L1/L3/L4/L6) KRUSKAL-STEINER SIGNAL & POWER ROUTING (>= 3.0 mil, 6/12 mech vias)
    # -------------------------------------------------------------------------
    for net, width_mil in ordered_nets:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        blocked, via_ok = build_net_masks(net, width_mil, blind_side_li=None)
        pad_entries = {}
        for i, p in enumerate(pts):
            ents = find_pad_entries(p, width_mil, blocked)
            if ents:
                pad_entries[i] = [(*e, p) for e in ents]
        if len(pad_entries) < 2:
            continue

        reach = list(pad_entries.keys())
        uf_parent = {i: i for i in reach}
        def uf_find(x):
            while uf_parent[x] != x:
                uf_parent[x] = uf_parent[uf_parent[x]]
                x = uf_parent[x]
            return x
        cluster_nodes = {i: {(e[1], e[2], e[3]): e for e in pad_entries[i]} for i in reach}

        cand_pairs = []
        seen_pair = set()
        for i in reach:
            nbrs = sorted(
                [j for j in reach if j != i],
                key=lambda j: abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0),
            )[:5]
            for j in nbrs:
                pk = (min(i, j), max(i, j))
                if pk not in seen_pair:
                    seen_pair.add(pk)
                    d = abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0)
                    cand_pairs.append((d, i, j))
        cand_pairs.sort(key=lambda x: x[0])

        nt, nv, conns = 0, 0, 0
        for _, i, j in cand_pairs:
            ri, rj = uf_find(i), uf_find(j)
            if ri == rj:
                continue
            starts = pad_entries[i]
            targets = cluster_nodes[rj]
            res = astar_to_targets(starts, targets, blocked, via_ok, max_iters=40000, allow_via=True)
            if not res:
                continue
            s_ent, g_ent, path = res
            dt, dv = commit_path(pts[i], s_ent, g_ent, path, width_mil, net, cluster_nodes[rj])
            nt += dt
            nv += dv
            conns += 1
            total_conns_made += 1
            uf_parent[ri] = rj
            for k_node, v_ent in cluster_nodes[ri].items():
                if k_node not in cluster_nodes[rj]:
                    cluster_nodes[rj][k_node] = ("TREE", k_node[0], k_node[1], k_node[2], None) if v_ent[0] == "TREE" else v_ent
            for e in starts:
                cluster_nodes[rj][(e[1], e[2], e[3])] = ("TREE", e[1], e[2], e[3], None)
            if g_ent[0] == "STUB":
                cluster_nodes[rj][(g_ent[1], g_ent[2], g_ent[3])] = ("TREE", g_ent[1], g_ent[2], g_ent[3], None)
            if dv > 0:
                blocked, via_ok = build_net_masks(net, width_mil, blind_side_li=None)
            if conns == len(pts) - 1:
                break

        if conns > 0:
            complete = (conns == len(pts) - 1)
            net_reports.append({
                "net": net, "pads": len(pts), "connections_made": conns,
                "complete": complete, "width_mil": width_mil, "tracks": nt, "vias": nv,
            })
            tag = "100%" if complete else f"{conns}/{len(pts)-1}"
            print(f"  [{board}] {net:22s}: {tag:6s} | w={width_mil:.1f}mil tracks={nt:3d}, vias(6/12)={nv:2d}", flush=True)

    # -------------------------------------------------------------------------
    # PHASE 2: TRUE LASER BLIND MICROVIA GND STITCHING (BV_L1_L2 & BV_L5_L6) + SAME-LAYER GND CHAINING!
    # -------------------------------------------------------------------------
    gnd_pads = [p for p in pads_by_net.get("GND", []) if not (board == "PCB1" and p["ref"] == "U1")]
    gnd_tracks = 0
    bv_l1_l2_cnt = 0
    bv_l5_l6_cnt = 0
    u2_blind_vippo = 0
    grounded_set = set()
    gnd_tree_nodes = {}  # (li, gx, gy) -> ("TREE", ...)

    # 2A: Direct 1-hop true laser blind microvia stitching (TOP -> BV_L1_L2, BOT -> BV_L5_L6)
    for i, gp in enumerate(gnd_pads):
        px, py, li = gp["x"], gp["y"], gp["li"]
        rname = "BV_L1_L2" if li == 0 else "BV_L5_L6"
        # U2 inner GND balls: true L1-L2 laser VIPPO directly on ball!
        if board == "PCB2" and gp["ref"] == "U2" and gp["pnum"] in U2_INNER_BALLS and li == 0:
            if via_is_legal(px, py, "GND", via_type="BLIND", rule_name="BV_L1_L2", vippo_u2=True):
                if add_via(px, py, "GND", hole=4.0, diam=8.0, via_type="BLIND", rule_name="BV_L1_L2"):
                    bv_l1_l2_cnt += 1
                    u2_blind_vippo += 1
                    grounded_set.add(i)
                    gx, gy = to_grid(px, py)
                    gnd_tree_nodes[(li, gx, gy)] = ("TREE", li, gx, gy, None)
                continue
        found = None
        for r_mil in (8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0):
            for ang in range(0, 360, 15):
                vx = round(px + r_mil * math.cos(math.radians(ang)), 2)
                vy = round(py + r_mil * math.sin(math.radians(ang)), 2)
                if via_is_legal(vx, vy, "GND", via_type="BLIND", rule_name=rname) and seg_is_legal(li, px, py, vx, vy, 3.5, "GND"):
                    found = (vx, vy)
                    break
            if found:
                break
        if found:
            vx, vy = found
            if add_via(vx, vy, "GND", hole=4.0, diam=8.0, via_type="BLIND", rule_name=rname):
                if rname == "BV_L1_L2":
                    bv_l1_l2_cnt += 1
                else:
                    bv_l5_l6_cnt += 1
            if add_track(li, px, py, vx, vy, 3.5, "GND"):
                gnd_tracks += 1
            grounded_set.add(i)
            for qx, qy in ((px, py), (vx, vy)):
                gx, gy = to_grid(qx, qy)
                gnd_tree_nodes[(li, gx, gy)] = ("TREE", li, gx, gy, None)

    # 2B: Multi-hop same-layer GND chaining into blind-stitched clusters or nearby legal blind-via sites (TOP & BOT separately!)
    for side_li, rname in ((0, "BV_L1_L2"), (3, "BV_L5_L6")):
        blocked_g, via_ok_g = build_net_masks("GND", 3.5, blind_side_li=side_li)
        for _gpass in range(2):
            added_this_pass = 0
            for i, gp in enumerate(gnd_pads):
                if i in grounded_set or gp["li"] != side_li:
                    continue
                ents = find_pad_entries(gp, 3.5, blocked_g)
                if not ents:
                    continue
                local_targets = {
                    k: v for k, v in gnd_tree_nodes.items()
                    if k[0] == side_li and abs(k[1] * STEP - gp["x"]) + abs(k[2] * STEP - gp["y"]) <= 240.0
                }
                gx0, gy0 = to_grid(gp["x"], gp["y"])
                rad_g = int(90.0 / STEP)
                via_targets = {}
                for gx in range(max(0, gx0 - rad_g), min(NX, gx0 + rad_g + 1)):
                    base = gx * NY
                    for gy in range(max(0, gy0 - rad_g), min(NY, gy0 + rad_g + 1)):
                        if via_ok_g[base + gy] and not blocked_g[side_li][base + gy]:
                            via_targets[(side_li, gx, gy)] = ("NEW_BLIND_VIA", side_li, gx, gy, None)
                merged_targets = {**via_targets, **local_targets}
                if not merged_targets:
                    continue
                res = astar_to_targets([(*e, gp) for e in ents], merged_targets, blocked_g, via_ok_g, max_iters=7000, allow_via=False)
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
                dt, _ = commit_path(gp, s_ent, ("TREE", 0, 0, 0, None), path, 3.5, "GND", gnd_tree_nodes)
                gnd_tracks += dt
                grounded_set.add(i)
                added_this_pass += 1
                if g_ent[0] == "NEW_BLIND_VIA":
                    blocked_g, via_ok_g = build_net_masks("GND", 3.5, blind_side_li=side_li)
            if added_this_pass == 0:
                break

    net_reports.append({
        "net": "GND (BV_L1_L2/BV_L5_L6 blind + chain)", "pads": len(pads_by_net.get("GND", [])),
        "grounded_pads": len(grounded_set), "bv_l1_l2": bv_l1_l2_cnt, "bv_l5_l6": bv_l5_l6_cnt,
        "fixed_thermal_vias": fixed_gnd_count, "tracks": gnd_tracks,
        "vias": bv_l1_l2_cnt + bv_l5_l6_cnt + fixed_gnd_count,
    })
    print(f"  [{board}] GND blind+chain    : {len(grounded_set)}/{len(gnd_pads)} pads grounded | tracks={gnd_tracks}, BV_L1_L2={bv_l1_l2_cnt}, BV_L5_L6={bv_l5_l6_cnt}, thermal={fixed_gnd_count}", flush=True)

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
    print(f"=== {board} HDI-DFM ROUTING PLAN SUMMARY ===")
    print(json.dumps(plan["summary"], indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--board", choices=["PCB1", "PCB2", "PCB3"], required=True)
    p.add_argument("--dump", type=Path, required=True)
    p.add_argument("--plan-out", type=Path, required=True)
    p.add_argument("--antipads-out", type=Path, required=True)
    p.add_argument("--max-nets", type=int, default=140)
    a = p.parse_args()
    route_board(a.board, a.dump, a.plan_out, a.antipads_out, a.max_nets)


if __name__ == "__main__":
    main()
