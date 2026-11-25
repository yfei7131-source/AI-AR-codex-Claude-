#!/usr/bin/env python3
"""Universal 4-Layer Steiner Multi-Target A* + Pad-Escape + Same-Layer GND Chaining Router for EVT-1 H03 (PCB1, PCB2, PCB3).

Inherits PR #41's exact 3-board component placement without moving a single part or relaxing any locked 6L HDI DRC rule:
  - True Steiner multi-target routing: routes each unconnected pad to the ENTIRE already-routed copper tree of that net,
    eliminating same-net overlapping corridors (so CLI track count == persisted EasyEDA track count after save+reload!).
  - Same-layer GND chaining + multi-hop A* L2/L5 plane stitching across all 3 boards.
  - Strict DRC safety margins: Track-Pad >= 7.0 mil (> 6.0), Via-Pad >= 12.0 mil (> 6.0 & Hole-Pad > 6.9),
    Edge-Track >= 14.0 mil (> 11.811), non-GND Via-Edge >= 27.0 mil (for r=15.2 mil L2/L5 SDF-union anti-pads).
  - Supports PCB1 stepped outline (8.2x46.0 / 5.8 stem + Y=[0,4.2] RF keepout + U1 9x EPAD thermal GND vias),
    PCB2 MECR-01 4.6x25.0 (+ U2 0.40mm BGA checkerboard VIPPO), and PCB3 5.2x34.0 (+ Y=[0,4.0] RF keepout).
"""

import argparse
import heapq
import json
import math
from pathlib import Path

L_IDS = [1, 16, 18, 2]  # 0=TOP, 1=L3(Inner2), 2=L4(Inner4), 3=BOT
SIDE_TO_LI = {1: 0, 2: 3}
U2_INNER_BALLS = {"B2", "C2", "D2", "E2", "B3", "C3", "D3", "E3", "B4", "C4", "D4", "E4"}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


PCB2_PRIORITY = [
    ("clk_48m", 2.5),
    ("FPGA_1V2_SENSE", 2.5),
    ("FPGA_1V8_EN", 2.5),
    ("PRIV_LED_ANODE", 3.5),
    ("FPGA_CRESET_B", 2.5),
    ("FPGA_CDONE_VSYNC_N", 2.5),
    ("opt_l_qdo0_PANEL", 2.5), ("opt_l_qdo1_PANEL", 2.5), ("opt_l_qdo2_PANEL", 2.5), ("opt_l_qdo3_PANEL", 2.5),
    ("opt_r_qdo0_PANEL", 2.5), ("opt_r_qdo1_PANEL", 2.5), ("opt_r_qdo2_PANEL", 2.5), ("opt_r_qdo3_PANEL", 2.5),
    ("OPT_SCK_L", 2.5), ("OPT_CS_N_L", 2.5), ("OPT_SCK_R", 2.5), ("OPT_CS_N_R", 2.5),
    ("opt_sck", 2.5), ("opt_cs_n", 2.5),
    ("opt_l_qdo0", 2.5), ("opt_l_qdo1", 2.5), ("opt_l_qdo2", 2.5), ("opt_l_qdo3", 2.5),
    ("opt_r_qdo0", 2.5), ("opt_r_qdo1", 2.5), ("opt_r_qdo2", 2.5), ("opt_r_qdo3", 2.5),
    ("host_sck", 2.5), ("host_cs_n", 2.5), ("host_qio0", 2.5), ("host_qio1", 2.5), ("host_qio2", 2.5), ("host_qio3", 2.5),
    ("SYS_I2C_SCL_1V8", 2.5), ("SYS_I2C_SDA_1V8", 2.5), ("PDM_CLK_1V8", 2.5), ("PDM_D0_1V8", 2.5),
    ("AVDD_WD_SET", 2.5), ("AVDD_WD_DIV", 2.5), ("AVDD_CRESET_VSYS", 2.5), ("AVDD_PULSE_QUAL", 2.5),
    ("AVDD_PG_OK", 2.5), ("AVDD_QUAL_CLR_N", 2.5), ("AVDD_REQ_FILTER", 2.5), ("AVDD_QUAL_RC", 2.5),
    ("AVDD_D3_VSYS", 2.5), ("AVDD_WD_Q", 2.5), ("AVDD_PG_NODE", 2.5), ("OPT_AVDD_EN", 2.5), ("AVDD_OPT_BIAS", 3.5),
    ("1V8_FPGA_VPP", 3.5), ("1V2_FPGA_PLL", 3.5), ("1V2_FPGA_CORE", 3.5), ("1V8_SYS", 3.5), ("1V8_FPGA_IO", 3.5), ("VSYS", 3.5),
]

PCB1_PRIORITY = [
    # RF & Antenna matching
    ("ESP_ANT_FEED", 3.5), ("ESP_RF_ANT", 3.5),
    # USB ECO-07 & ECO-14
    ("USB_DP", 3.0), ("USB_DM", 3.0), ("USB_LIM_ILIM", 3.0), ("VBUS_5V_USB", 4.0), ("VBUS_5V", 4.0),
    # Privacy Interlock ECO-02 & ECO-09
    ("LED_3V3_PRIV", 3.5), ("PRIV_LED_ANODE", 3.5), ("PRIV_VTH_H", 3.0), ("PRIV_VTH_L", 3.0),
    ("PRIV_WINDOW_OK", 3.0), ("PRIV_WINDOW_OK_F", 3.0), ("CAM_PWR_REQ", 3.0), ("CAM_DOVDD_OK_3V3", 3.0),
    # Audio I2S / PDM / IPC / I2C
    ("I2S_BCLK_1V8", 3.0), ("I2S_LRCLK_1V8", 3.0), ("I2S_AMP_DIN_1V8", 3.0), ("I2S_S3_DOUT_1V8", 3.0),
    ("I2S_BCLK_3V3", 3.0), ("I2S_LRCLK_3V3", 3.0), ("I2S_S3_DOUT_3V3", 3.0), ("AMP_SD_MODE_1V8", 3.0),
    ("IPC_NRF_TX_1V8", 3.0), ("IPC_S3_TX_1V8", 3.0), ("IPC_NRF_TX_3V3", 3.0), ("IPC_S3_TX_3V3", 3.0),
    ("SYS_I2C_SCL_1V8", 3.0), ("SYS_I2C_SDA_1V8", 3.0), ("SYS_I2C_SCL_3V3", 3.0), ("SYS_I2C_SDA_3V3", 3.0),
    ("PDM_CLK_1V8", 3.0), ("PDM_D0_1V8", 3.0), ("PDM_D1_1V8", 3.0),
    # Host QSPI & Power
    ("host_sck_3v3", 3.0), ("host_cs_n_3v3", 3.0), ("host_qio0_3v3", 3.0), ("host_qio1_3v3", 3.0), ("host_qio2_3v3", 3.0), ("host_qio3_3v3", 3.0),
    ("ESP_VDD_SPI_3V3", 3.5), ("1V8_FPGA_IO", 3.5), ("VBAT_L", 4.0), ("VBAT_R_ISOLATED", 4.0), ("VBAT_R_RET", 4.0),
    ("VSYS", 4.0), ("1V8_SYS", 4.0), ("3V3_SYS", 4.0),
]

PCB3_PRIORITY = [
    # Clocks (32MHz HFXO + ECO-08 32.768kHz LFXO)
    ("BLE_XC1", 2.5), ("BLE_XC2", 2.5), ("LFXO_XL1", 2.5), ("LFXO_XL2", 2.5),
    # RF & nRF5340 decoupling
    ("BLE_ANT_FEED", 3.5), ("BLE_RF_MID", 3.5), ("BLE_RF_ANT", 3.5),
    ("NRF_DECA", 3.0), ("NRF_DECN", 3.0), ("NRF_DCC", 3.0), ("NRF_DCCD", 3.0), ("NRF_DECD", 3.0), ("NRF_DECR_RF", 3.0),
    # SWD Debug & IPC
    ("BLE_SWDIO", 2.5), ("BLE_SWDCLK", 2.5), ("IPC_NRF_TX_1V8", 2.5), ("IPC_S3_TX_1V8", 2.5),
    # I2S / Audio / PDM
    ("I2S_BCLK_1V8", 2.5), ("I2S_LRCLK_1V8", 2.5), ("I2S_AMP_DIN_1V8", 2.5), ("I2S_S3_DOUT_1V8", 2.5),
    ("AMP_SD_REQ_1V8", 2.5), ("AMP_SD_MODE_1V8", 2.5), ("AMP_R_SD_MODE", 2.5), ("PDM_CLK_1V8", 2.5), ("PDM_D1_1V8", 2.5),
    # Power
    ("VBUS_5V", 4.0), ("VBAT_R_RET", 4.0), ("1V8_SYS", 3.5),
]


def board_geometry(board: str):
    """Return (W_MIL, H_MIL, STEP, inside_track_fn, inside_via_fn, mic_ref, priority_list, fixed_gnd_vias)."""
    if board == "PCB2":
        W, H = 181.1024, 984.2520
        def in_trk(x, y, margin):
            return margin <= x <= W - margin and margin <= y <= H - margin
        def in_via(x, y, is_gnd):
            m = 18.0 if is_gnd else 27.0
            return m <= x <= W - m and m <= y <= H - m
        return W, H, 2.0, in_trk, in_via, "MK2", PCB2_PRIORITY, []
    elif board == "PCB1":
        # Stepped outline: Y in [0, 165.35] RF PROHIBIT; Y in [165.35, 551.18] X=[0, 322.83]; Y in [551.18, 1811.02] X=[0, 228.35]
        W, H = 322.8346, 1811.0236
        def in_trk(x, y, margin):
            if x < margin or y < 165.3543 + margin or y > H - margin:
                return False
            if y > 551.1811 - margin:
                return x <= 228.3465 - margin
            return x <= W - margin
        def in_via(x, y, is_gnd):
            m = 18.5 if is_gnd else 27.5
            if x < m or y < 176.0 + (8.0 if is_gnd else 16.5) or y > H - m:
                return False
            if y > 540.5 - (8.0 if is_gnd else 16.5):
                return x <= 217.8 - (8.0 if is_gnd else 16.5)
            return x <= 312.3 - (8.0 if is_gnd else 16.5)
        u1x, u1y = 4.10 / 0.0254, 9.10 / 0.0254
        u1_vias = [(round(u1x + dx * 39.37, 2), round(u1y + dy * 39.37, 2), 8.0, 14.0) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        return W, H, 3.0, in_trk, in_via, "MK1", PCB1_PRIORITY, u1_vias
    elif board == "PCB3":
        # Outline 5.20 x 34.00 mm (204.72 x 1338.58 mil); Y in [0, 157.48] RF PROHIBIT
        W, H = 204.7244, 1338.5827
        def in_trk(x, y, margin):
            return margin <= x <= W - margin and 157.4803 + margin <= y <= H - margin
        def in_via(x, y, is_gnd):
            m = 18.5 if is_gnd else 27.5
            y_lo = 168.0 + (8.0 if is_gnd else 16.5)
            return m <= x <= W - m and y_lo <= y <= H - m
        return W, H, 2.5, in_trk, in_via, "MK3", PCB3_PRIORITY, []
    raise ValueError(f"Unknown board {board}")


def route_board(board: str, dump_path: Path, plan_out: Path, antipads_out: Path, max_nets_budget: int = 80):
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
    placed_vias: list[tuple[float, float, float, str]] = []  # (vx, vy, outer_r, net)
    tracks_out = []
    vias_out = []

    def add_via(vx, vy, net, hole=4.0, diam=8.0):
        for ovx, ovy, _, onet in placed_vias:
            if onet == net and math.hypot(vx - ovx, vy - ovy) < 1.5:
                return False
        placed_vias.append((vx, vy, 0.5 * diam, net))
        vias_out.append({"x": round(vx, 2), "y": round(vy, 2), "hole": hole, "diameter": diam, "net": net})
        return True

    def add_track(li, x1, y1, x2, y2, width, net):
        if math.hypot(x2 - x1, y2 - y1) < 0.2:
            return False
        # Prevent exact duplicate segment on same layer & net!
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

    # Seed fixed GND thermal vias (e.g., U1 9x EPAD thermal vias on PCB1)
    fixed_gnd_count = 0
    for vx, vy, h_m, d_m in fixed_gnd_vias:
        if add_via(vx, vy, "GND", h_m, d_m):
            fixed_gnd_count += 1

    def via_is_legal(vx, vy, net, vippo_u2=False):
        is_gnd = (net == "GND")
        if not in_via(vx, vy, is_gnd):
            return False
        mk_r = 37.0 if is_gnd else 45.5
        if math.hypot(vx - mic_hx, vy - mic_hy) < mk_r:
            return False
        if not is_gnd and in_mic_body(vx, vy, 12.0):
            return False
        for ovx, ovy, orad, onet in placed_vias:
            d = math.hypot(vx - ovx, vy - ovy)
            if is_gnd and onet == "GND":
                if d < 14.5 + orad:
                    return False
            elif (not is_gnd) and (onet != "GND"):
                if d < 18.5:
                    return False
            else:
                if d < 17.5 + orad:
                    return False
        for p in all_pads:
            if p["net"] == net:
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            dist = math.hypot(dx, dy)
            if vippo_u2 and p["ref"] == "U2" and p["li"] == 0:
                if dist < 6.8:
                    return False
            else:
                if dist < 11.8:
                    return False
        for _, x1, y1, x2, y2, w, onet in routed_segs:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 11.8 + 0.5 * w:
                return False
        return True

    def seg_is_legal(li, x1, y1, x2, y2, width, net):
        margin = 14.0 + 0.5 * width
        if not (in_trk(x1, y1, margin) and in_trk(x2, y2, margin)):
            return False
        if pt_seg_dist(mic_hx, mic_hy, x1, y1, x2, y2) < 33.0 + 0.5 * width:
            return False
        if li == 3 and net != "GND":
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                if in_mic_body(x1 + t * (x2 - x1), y1 + t * (y2 - y1), 7.5 + 0.5 * width):
                    return False
        for vx, vy, vrad, onet in placed_vias:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 7.2 + vrad + 0.5 * width:
                return False
        steps = max(3, int(math.hypot(x2 - x1, y2 - y1) / 2.0) + 1)
        if li in (0, 3):
            clr = 6.9 + 0.5 * width
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
            min_d = 3.2 + 0.5 * (width + ow)
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if pt_seg_dist(cx, cy, ox1, oy1, ox2, oy2) < min_d:
                    return False
        return True

    def build_net_masks(net, width):
        is_gnd = (net == "GND")
        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))
        t_margin = 14.0 + 0.5 * width
        mk_t = 33.0 + 0.5 * width
        mk_v = 37.0 if is_gnd else 45.5

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
                    if in_mic_body(x, y, 12.0):
                        via_ok[idx] = 0

        pad_clr = 7.0 + 0.5 * width
        via_pad_clr = 12.0
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
                    dx = max(0.0, abs(gx * STEP - p["x"]) - p["hw"])
                    base = gx * NY
                    for gy in range(gy0, gy1 + 1):
                        dy = max(0.0, abs(gy * STEP - p["y"]) - p["hh"])
                        if math.hypot(dx, dy) < clr:
                            if target is not None:
                                target[base + gy] = 1
                            else:
                                via_ok[base + gy] = 0

        for vx, vy, vrad, onet in placed_vias:
            r_v = (14.5 + vrad) if (is_gnd and onet == "GND") else (18.8 if (not is_gnd and onet != "GND") else (17.8 + vrad))
            r_t = 7.5 + vrad + 0.5 * width
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
            trk_clr = 3.2 + 0.5 * (width + ow)
            via_trk_clr = 12.0 + 0.5 * ow
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
        dirs = sorted(
            [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 360, 45)],
            key=lambda v: -(v[0] * math.cos(base_ang) + v[1] * math.sin(base_ang)),
        )
        seen_g = set()
        max_reach = max(18.0, p["hw"] + 13.0, p["hh"] + 13.0)
        for dx, dy in dirs:
            for dist in (4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0):
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
            if len(entries) >= 4:
                break

        if board == "PCB2" and p["ref"] == "U2" and p["pnum"] in U2_INNER_BALLS:
            if via_is_legal(px, py, p["net"], vippo_u2=True):
                vgx, vgy = to_grid(px, py)
                for ili in (1, 2):
                    if not blocked[ili][vgx * NY + vgy]:
                        entries.append(("VIPPO", ili, vgx, vgy, px, py))
        return entries

    def astar_to_targets(starts, goal_nodes_map, blocked, via_ok, max_iters=45000, allow_via=True):
        """Steiner multi-source, multi-target 4-layer A*."""
        if not starts or not goal_nodes_map:
            return None
        # Sample up to 24 representative goal coords for fast admissible heuristic
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
            sc = 4.0 if s[0] == "VIPPO" else 0.0
            h = min(abs(s[2] - gx) + abs(s[3] - gy) for gx, gy in g_sample)
            g_cost[node] = sc
            heapq.heappush(pq, (sc + h * 1.75, sc, node))

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
                        step_c = 1.45
                    elif li == 2 and dx != 0:
                        step_c = 1.45
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
                    ng = gc + 15.0
                    nxt = (nli, gx, gy)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = min(abs(gx - tx) + abs(gy - ty) for tx, ty in g_sample)
                        heapq.heappush(pq, (ng + h * 1.75, ng, nxt))
        return None

    def commit_path(p_src, s_ent, g_ent, path, width, net, tree_nodes: dict):
        nt, nv, vippo = 0, 0, 0
        sx, sy = from_grid(path[0][1], path[0][2])
        if s_ent[0] == "VIPPO":
            if add_via(p_src["x"], p_src["y"], net):
                nv += 1
                vippo += 1
            if add_track(s_ent[1], p_src["x"], p_src["y"], sx, sy, width, net):
                nt += 1
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
                if add_via(vx, vy, net):
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

        # If target was a pad entry (not an existing tree node), emit goal pad stub / VIPPO!
        if g_ent[0] in ("STUB", "VIPPO"):
            p_dst = g_ent[6]
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if g_ent[0] == "VIPPO":
                if add_track(g_ent[1], ex, ey, p_dst["x"], p_dst["y"], width, net):
                    nt += 1
                if add_via(p_dst["x"], p_dst["y"], net):
                    nv += 1
                    vippo += 1
            else:
                if add_track(p_dst["li"], ex, ey, p_dst["x"], p_dst["y"], width, net):
                    nt += 1
        return nt, nv, vippo

    # Build ordered net list
    ordered_nets = list(prio_list)
    seen = {n for n, _ in ordered_nets} | {"GND"}
    for n in sorted(pads_by_net):
        if n not in seen and len(pads_by_net[n]) >= 2:
            ordered_nets.append((n, 2.5 if board != "PCB1" else 3.0))
    ordered_nets = ordered_nets[:max_nets_budget]

    net_reports = []
    total_conns_made = 0
    total_vippo = 0

    # -------------------------------------------------------------------------
    # PHASE 1: STEINER MULTI-TARGET ROUTING OF SIGNAL & POWER NETS
    # -------------------------------------------------------------------------
    for net, width_mil in ordered_nets:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        blocked, via_ok = build_net_masks(net, width_mil)
        # Precompute legal pad entries for every pad of this net
        pad_entries = {}
        for i, p in enumerate(pts):
            ents = find_pad_entries(p, width_mil, blocked)
            if ents:
                pad_entries[i] = [(*e, p) for e in ents]
        if len(pad_entries) < 2:
            continue

        # True Kruskal-Steiner Forest: every reachable pad starts in its own cluster; merge shortest cross-cluster pairs!
        # Prevents an isolated first pad from starving the rest of a multi-pad net (VSYS, 1V8_FPGA_IO, 3V3_SYS, 1V8_SYS)!
        reach = list(pad_entries.keys())
        uf_parent = {i: i for i in reach}
        def uf_find(x):
            while uf_parent[x] != x:
                uf_parent[x] = uf_parent[uf_parent[x]]
                x = uf_parent[x]
            return x
        cluster_nodes = {i: {(e[1], e[2], e[3]): e for e in pad_entries[i]} for i in reach}

        # Candidate pairs sorted by Manhattan distance (+25 mil penalty for opposite layer), capped to shortest 3 neighbors per pad
        cand_pairs = []
        seen_pair = set()
        for i in reach:
            nbrs = sorted(
                [j for j in reach if j != i],
                key=lambda j: abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 25.0),
            )[:4]
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
            # Route from pad i's entries to cluster rj's ENTIRE copper tree!
            starts = pad_entries[i]
            targets = cluster_nodes[rj]
            res = astar_to_targets(starts, targets, blocked, via_ok, max_iters=35000)
            if not res:
                continue
            s_ent, g_ent, path = res
            dt, dv, dvip = commit_path(pts[i], s_ent, g_ent, path, width_mil, net, cluster_nodes[rj])
            nt += dt
            nv += dv
            total_vippo += dvip
            conns += 1
            total_conns_made += 1
            # Merge clusters ri -> rj (converting merged pad entries into TREE nodes!)
            uf_parent[ri] = rj
            for k_node, v_ent in cluster_nodes[ri].items():
                if k_node not in cluster_nodes[rj]:
                    cluster_nodes[rj][k_node] = ("TREE", k_node[0], k_node[1], k_node[2], None) if v_ent[0] == "TREE" else v_ent
            for e in starts:
                cluster_nodes[rj][(e[1], e[2], e[3])] = ("TREE", e[1], e[2], e[3], None)
            if g_ent[0] in ("STUB", "VIPPO"):
                cluster_nodes[rj][(g_ent[1], g_ent[2], g_ent[3])] = ("TREE", g_ent[1], g_ent[2], g_ent[3], None)
            if dv > 0:
                blocked, via_ok = build_net_masks(net, width_mil)
            if conns == len(pts) - 1:
                break

        if conns > 0:
            complete = (conns == len(pts) - 1)
            net_reports.append({
                "net": net, "pads": len(pts), "connections_made": conns,
                "complete": complete, "width_mil": width_mil, "tracks": nt, "vias": nv,
            })
            tag = "100%" if complete else f"{conns}/{len(pts)-1}"
            print(f"  [{board}] {net:22s}: {tag:6s} | tracks={nt:3d}, vias={nv:2d}", flush=True)

    # -------------------------------------------------------------------------
    # PHASE 2: SAME-LAYER GND CHAINING + MULTI-HOP A* L2/L5 PLANE STITCHING!
    # -------------------------------------------------------------------------
    gnd_pads = [p for p in pads_by_net.get("GND", []) if not (board == "PCB1" and p["ref"] == "U1")]
    gnd_tracks = 0
    gnd_vias = 0
    grounded_set = set()
    gnd_tree_nodes = {}  # (li, gx, gy) -> ("TREE", ...)

    blocked_g, via_ok_g = build_net_masks("GND", 3.5)

    # 2A: First, directly stitch GND pads that have an immediate 1-hop legal via site (fast & low-inductance!)
    for i, gp in enumerate(gnd_pads):
        px, py, li = gp["x"], gp["y"], gp["li"]
        if board == "PCB2" and gp["ref"] == "U2" and gp["pnum"] in U2_INNER_BALLS:
            if via_is_legal(px, py, "GND", vippo_u2=True):
                if add_via(px, py, "GND"):
                    gnd_vias += 1
                    total_vippo += 1
                    grounded_set.add(i)
                    gx, gy = to_grid(px, py)
                    gnd_tree_nodes[(li, gx, gy)] = ("TREE", li, gx, gy, None)
                continue
        found = None
        for r_mil in (8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0):
            for ang in range(0, 360, 20):
                vx = round(px + r_mil * math.cos(math.radians(ang)), 2)
                vy = round(py + r_mil * math.sin(math.radians(ang)), 2)
                if via_is_legal(vx, vy, "GND") and seg_is_legal(li, px, py, vx, vy, 3.5, "GND"):
                    found = (vx, vy)
                    break
            if found:
                break
        if found:
            vx, vy = found
            if add_via(vx, vy, "GND"):
                gnd_vias += 1
            if add_track(li, px, py, vx, vy, 3.5, "GND"):
                gnd_tracks += 1
            grounded_set.add(i)
            for qx, qy in ((px, py), (vx, vy)):
                gx, gy = to_grid(qx, qy)
                gnd_tree_nodes[(li, gx, gy)] = ("TREE", li, gx, gy, None)

    # 2B: Multi-hop same-layer GND chaining (2 passes so 2-hop pads chain cleanly onto pass-1 grounded clusters!)
    blocked_g, via_ok_g = build_net_masks("GND", 3.5)
    for _gpass in range(2):
        added_this_pass = 0
        for i, gp in enumerate(gnd_pads):
            if i in grounded_set:
                continue
            li = gp["li"]
            ents = find_pad_entries(gp, 3.5, blocked_g)
            if not ents:
                continue
            local_targets = {
                k: v for k, v in gnd_tree_nodes.items()
                if k[0] == li and abs(k[1] * STEP - gp["x"]) + abs(k[2] * STEP - gp["y"]) <= 220.0
            }
            gx0, gy0 = to_grid(gp["x"], gp["y"])
            rad_g = int(85.0 / STEP)
            via_targets = {}
            for gx in range(max(0, gx0 - rad_g), min(NX, gx0 + rad_g + 1)):
                base = gx * NY
                for gy in range(max(0, gy0 - rad_g), min(NY, gy0 + rad_g + 1)):
                    if via_ok_g[base + gy] and not blocked_g[li][base + gy]:
                        via_targets[(li, gx, gy)] = ("NEW_GND_VIA", li, gx, gy, None)
            merged_targets = {**via_targets, **local_targets}
            if not merged_targets:
                continue
            res = astar_to_targets([(*e, gp) for e in ents], merged_targets, blocked_g, via_ok_g, max_iters=6000, allow_via=False)
            if not res:
                continue
            s_ent, g_ent, path = res
            if g_ent[0] == "NEW_GND_VIA":
                vx, vy = from_grid(path[-1][1], path[-1][2])
                if not via_is_legal(vx, vy, "GND"):
                    continue
                if add_via(vx, vy, "GND"):
                    gnd_vias += 1
            dt, _, _ = commit_path(gp, s_ent, ("TREE", 0, 0, 0, None), path, 3.5, "GND", gnd_tree_nodes)
            gnd_tracks += dt
            grounded_set.add(i)
            added_this_pass += 1
            if g_ent[0] == "NEW_GND_VIA":
                blocked_g, via_ok_g = build_net_masks("GND", 3.5)
        if added_this_pass == 0:
            break

    net_reports.append({
        "net": "GND (chain + L2/L5 stitch)", "pads": len(pads_by_net.get("GND", [])),
        "grounded_pads": len(grounded_set), "fixed_thermal_vias": fixed_gnd_count,
        "tracks": gnd_tracks, "vias": gnd_vias + fixed_gnd_count,
    })
    print(f"  [{board}] GND chain+stitch   : {len(grounded_set)}/{len(gnd_pads)} pads grounded | tracks={gnd_tracks}, vias={gnd_vias}+{fixed_gnd_count} thermal", flush=True)

    non_gnd_vias = [[v["x"], v["y"]] for v in vias_out if v["net"] != "GND"]
    plan = {
        "board": board,
        "summary": {
            "total_tracks": len(tracks_out),
            "total_vias": len(vias_out),
            "gnd_vias": gnd_vias + fixed_gnd_count,
            "non_gnd_signal_vias": len(non_gnd_vias),
            "u2_bga_vippo_vias": total_vippo,
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
    print(f"=== {board} ROUTING PLAN SUMMARY ===")
    print(json.dumps(plan["summary"], indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--board", choices=["PCB1", "PCB2", "PCB3"], required=True)
    p.add_argument("--dump", type=Path, required=True)
    p.add_argument("--plan-out", type=Path, required=True)
    p.add_argument("--antipads-out", type=Path, required=True)
    p.add_argument("--max-nets", type=int, default=80)
    a = p.parse_args()
    route_board(a.board, a.dump, a.plan_out, a.antipads_out, a.max_nets)


if __name__ == "__main__":
    main()
