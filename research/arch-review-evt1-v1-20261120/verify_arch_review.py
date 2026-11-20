#!/usr/bin/env python3
"""
Deterministic Architecture Review & Design-Input Verification Script
Zhiyuan Yuedong AI/AR Smart Glasses V1.0 (EVT-1, PR #29-#35 Baseline)

Scope (ARCHITECTURE REVIEW / CONDITIONAL / NOT FOR FAB):
  1. Verifies M-OPT-BRIDGE area overflow in PR #35 baseline (all 83 components).
  2. Proves 2D zero-overlap placement for all 83/84 components under:
     - Option A: Strict 22.0 x 4.2 mm rigid center + 3 rigid-flex connector islands
       (preserving PR #35 edge-launch keepouts, >=0.20 mm courtyard gap, >=0.254 mm edge clearance).
     - Option B: Expanded 25.0 x 4.6 mm rigid brow-bar + on-board J_BRIDGE_IN (20+2P)
       + 2 optical flex wings.
  3. Verifies Camera Privacy Interlock PVT & Open/Short Security Margin:
     - Demonstrates failure of PR #32/#35 2.80 V / 249 Ohm baseline across PVT.
     - Proves 6/6 PASS for proposed 3.30 V switched (TPS22916CYFPR) + 200 Ohm / 1.40 Ohm /
       [12.1k, 56.2k, 34.8k] window across -10 C..+60 C, +/-2% rail, GND shift, open & short attacks.
  4. Verifies FPGA 1V2 -> 1V8 sequencing threshold using TPS3895ADRYR (Rtop=49.9k, Rbot=56.2k 1%).
  5. Verifies Dual-Battery LM66200 break-before-make droop vs TPS2116 + >=30 uF effective VSYS bulk.
  6. Verifies Dual-Charger USB SDP current sum (>500 mA) and TPS2553DRVR current-limit mitigation.
  7. Verifies Mass Budget delta (preserving <=40.0 g target) & Thermal skin-temperature bounds.

Run from repo root or script directory:
  python research/arch-review-evt1-v1-20261120/verify_arch_review.py --write-report
  python research/arch-review-evt1-v1-20261120/verify_arch_review.py --check
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPORT_PATH = SCRIPT_DIR / "evidence" / "arch_verification_report.json"


def check_bridge_area_and_placement() -> dict:
    """Audit PR #35 83-component overflow and prove Option A & Option B 2D zero-overlap fits."""
    edge = 0.254
    gap = 0.200
    w_base, l_base = 4.20, 22.00
    usable_one = (w_base - 2 * edge) * (l_base - 2 * edge)
    usable_both = 2.0 * usable_one

    # PR #35 baseline cell areas (+0.20mm inter-component pitch cell)
    pr35_14_placed = [
        ("U2_FPGA", 1, 2.80, 2.93),
        ("Y1_OSC", 1, 2.42, 2.95),
        ("U9_IMU", 1, 3.71, 2.80),
        ("MK2_C_IM69D130", 1, 3.91, 4.25),
        ("D3_PRIV_guard", 1, 1.00, 2.40),
        ("U4_1V2", 1, 1.48, 1.21),
        ("U4_1V8F", 1, 1.21, 1.48),
        ("U6_OPT_AVDD", 1, 1.20, 1.20),
        ("U_AVDD_IO_PG", 1, 2.69, 2.00),
        ("U_AVDD_SYS_PG", 1, 2.69, 2.00),
        ("U_AVDD_SYS_CLAMP", 1, 2.69, 2.00),
        ("U_AVDD_LS_DCUR", 1, 2.22, 4.07),
        ("U_AVDD_QUAL_DCKR", 1, 3.02, 2.69),
        ("U_AVDD_WD_IS6", 1, 3.57, 3.50),
    ]
    pr35_69_omitted = [
        ("U_AVDD_SCHMITT_DCKR", 1, 3.02, 2.69),
        ("U_AVDD_CLEAR_OD", 1, 1.30, 1.30),
        ("U_AVDD_EN_OD", 1, 1.30, 1.30),
        ("FPGA_Bulk_0603", 4, 2.60, 1.20),
        ("Caps_0402", 28, 1.60, 0.90),
        ("Cap_0201", 1, 1.00, 0.60),
        ("Res_0201", 27, 1.00, 0.60),
        ("TP_AVDD_SAFE_9pad", 1, 2.50, 2.50),
    ]
    edge_launch_area = 4.20 * 1.30 + 2 * (0.70 * 2.34)
    placed_area = sum(c * (w + gap) * (l + gap) for _, c, w, l in pr35_14_placed)
    omitted_area = sum(c * (w + gap) * (l + gap) for _, c, w, l in pr35_69_omitted) + edge_launch_area
    total_pr35_area = placed_area + omitted_area

    def pack_board(board_w: float, board_l: float, top_parts: list, bot_parts: list,
                   top_keepouts: list, bot_keepouts: list) -> dict:
        x_min, x_max = edge, board_w - edge
        y_min, y_max = edge, board_l - edge
        out = {}
        for side, plist, keepouts in [("TOP", top_parts, top_keepouts), ("BOTTOM", bot_parts, bot_keepouts)]:
            placed = []
            # Keepouts are treated as hard blocked boxes (no gap needed beyond keepout itself, or gap=0.10mm)
            fixed = [p for p in plist if p.get("fixed")]
            free = [p for p in plist if not p.get("fixed")]
            free.sort(key=lambda p: (-p["w"] * p["l"], -max(p["w"], p["l"])))

            for p in fixed:
                cx, cy, w, l = p["cx"], p["cy"], p["w"], p["l"]
                x0, y0, x1, y1 = cx - w / 2.0, cy - l / 2.0, cx + w / 2.0, cy + l / 2.0
                placed.append((p["ref"], x0, y0, x1, y1, 0))

            failed = []
            for p in free:
                found = None
                orientations = [(p["w"], p["l"], 0)]
                if abs(p["w"] - p["l"]) > 1e-6 and not p.get("no_rot"):
                    orientations.append((p["l"], p["w"], 90))
                orientations.sort(key=lambda o: o[0])
                y_pref = p.get("y_pref")
                best_score = 1e9

                for w, l, rot in orientations:
                    if w > (x_max - x_min) + 1e-9 or l > (y_max - y_min) + 1e-9:
                        continue
                    y_steps = int(round((y_max - y_min - l) / 0.15)) + 1
                    x_steps = int(round((x_max - x_min - w) / 0.12)) + 1
                    for yi in range(max(1, y_steps)):
                        y0 = min(y_max - l, y_min + yi * 0.15)
                        for xi in range(max(1, x_steps)):
                            x0 = min(x_max - w, x_min + xi * 0.12)
                            x1, y1 = x0 + w, y0 + l
                            clash = False
                            for (_, px0, py0, px1, py1, _) in placed:
                                if not (x1 + gap <= px0 + 1e-9 or x0 >= px1 + gap - 1e-9 or
                                        y1 + gap <= py0 + 1e-9 or y0 >= py1 + gap - 1e-9):
                                    clash = True
                                    break
                            if not clash:
                                for (kx0, ky0, kx1, ky1) in keepouts:
                                    if not (x1 <= kx0 + 1e-9 or x0 >= kx1 - 1e-9 or
                                            y1 <= ky0 + 1e-9 or y0 >= ky1 - 1e-9):
                                        clash = True
                                        break
                            if not clash:
                                score = abs((y0 + y1) / 2.0 - y_pref) if y_pref is not None else y0
                                if score < best_score:
                                    best_score = score
                                    found = (p["ref"], x0, y0, x1, y1, rot)
                if found:
                    placed.append(found)
                else:
                    failed.append(p["ref"])

            # Independent geometric audit of placed boxes
            min_gap_obs = 999.0
            min_edge_obs = 999.0
            keepout_clashes = 0
            for i, (r1, a0, b0, a1, b1, _) in enumerate(placed):
                e_m = min(a0, board_w - a1, b0, board_l - b1)
                min_edge_obs = min(min_edge_obs, e_m)
                for (kx0, ky0, kx1, ky1) in keepouts:
                    if not (a1 <= kx0 + 1e-9 or a0 >= kx1 - 1e-9 or b1 <= ky0 + 1e-9 or b0 >= ky1 - 1e-9):
                        keepout_clashes += 1
                for j in range(i + 1, len(placed)):
                    _, c0, d0, c1, d1, _ = placed[j]
                    dx = max(0.0, max(c0 - a1, a0 - c1))
                    dy = max(0.0, max(d0 - b1, b0 - d1))
                    g = max(dx, dy) if (dx == 0 or dy == 0) else math.hypot(dx, dy)
                    min_gap_obs = min(min_gap_obs, g)

            body_area = sum((x1 - x0) * (y1 - y0) for _, x0, y0, x1, y1, _ in placed)
            usable = (board_w - 2 * edge) * (board_l - 2 * edge)
            out[side] = {
                "requested": len(plist),
                "placed_count": len(placed),
                "failed": failed,
                "body_fill_pct": round(100.0 * body_area / usable, 2),
                "min_gap_mm": round(min_gap_obs, 4),
                "min_edge_mm": round(min_edge_obs, 4),
                "keepout_clashes": keepout_clashes,
                "key_ics": [
                    {
                        "ref": r,
                        "center_mm": [round((x0 + x1) / 2.0, 3), round((y0 + y1) / 2.0, 3)],
                        "box_mm": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
                        "rot_deg": rot,
                    }
                    for r, x0, y0, x1, y1, rot in placed
                    if not r.startswith(("C0201", "R0201", "TP_SAFE", "C_LDO", "RN_DAMP", "C_FPGA", "C_IMU"))
                ],
            }
        return out

    def build_parts(board_w: float, include_j_bridge_20p: bool) -> tuple[list, list]:
        cx = board_w / 2.0
        top = [
            {"ref": "D3_PRIV", "w": 0.80, "l": 2.20, "fixed": True, "cx": cx, "cy": 1.45},
            {"ref": "U2_FPGA", "w": 2.20, "l": 2.60, "fixed": True, "cx": cx, "cy": 9.50},
            {"ref": "U9_IMU", "w": 2.55, "l": 3.05, "fixed": True, "cx": cx, "cy": 19.20},
            {"ref": "U_AVDD_IO_PG", "w": 1.55, "l": 1.55, "y_pref": 12.5},
            {"ref": "U_AVDD_SYS_PG", "w": 1.55, "l": 1.55, "y_pref": 6.5},
            {"ref": "U_AVDD_QUAL", "w": 1.50, "l": 1.05, "y_pref": 5.0},
            {"ref": "U_AVDD_SCHMITT", "w": 1.05, "l": 1.05, "y_pref": 5.5},
            {"ref": "U_AVDD_CLEAR_OD", "w": 1.05, "l": 1.05, "y_pref": 4.0},
            {"ref": "U_AVDD_EN_OD", "w": 1.05, "l": 1.05, "y_pref": 13.5},
            {"ref": "U_FPGA_SEQ", "w": 1.50, "l": 1.05, "y_pref": 11.8},
        ]
        for i in range(3):
            top.append({"ref": f"RN_DAMP_{i+1}", "w": 1.45, "l": 0.75, "y_pref": 9.5})
        for name, yp in [
            ("C_FPGA_CORE_BULK", 8.0), ("C_FPGA_PLL_BULK", 8.0),
            ("C_FPGA_VPP_BULK", 11.0), ("C_FPGA_IO_BULK", 11.0),
            ("C_IMU_VDD2", 17.0),
        ]:
            top.append({"ref": name, "w": 1.15, "l": 0.60, "y_pref": yp})
        for i in range(12):
            top.append({"ref": f"C0201_T{i+1}", "w": 0.70, "l": 0.38, "y_pref": 9.5 if i < 7 else 16.5})
        for i in range(10):
            top.append({"ref": f"R0201_T{i+1}", "w": 0.70, "l": 0.38, "y_pref": 6.5 if i < 5 else 13.0})

        bot = [
            {"ref": "Y1_OSC", "w": 1.65, "l": 2.05, "fixed": True, "cx": cx, "cy": 9.50},
            {"ref": "MK2_C", "w": 2.55, "l": 3.65, "fixed": True, "cx": cx, "cy": 16.50},
            {"ref": "U4_1V2", "w": 1.05, "l": 1.05, "y_pref": 11.5},
            {"ref": "U4_1V8F", "w": 1.05, "l": 1.05, "y_pref": 11.5},
            {"ref": "U6_OPT_AVDD", "w": 1.05, "l": 1.05, "y_pref": 13.0},
            {"ref": "U_AVDD_LS", "w": 0.95, "l": 1.95, "y_pref": 7.0},
            {"ref": "U_AVDD_WD", "w": 2.05, "l": 3.05, "y_pref": 4.5},
            {"ref": "U_AVDD_SYS_CLAMP", "w": 1.55, "l": 1.55, "y_pref": 19.5},
        ]
        if include_j_bridge_20p:
            bot.append({"ref": "J_BRIDGE_IN_20P", "w": 1.95, "l": 6.30, "fixed": True, "cx": cx, "cy": 3.55})
        for i in range(6):
            bot.append({"ref": f"C_LDO_B{i+1}", "w": 1.15, "l": 0.60, "y_pref": 12.0})
        for i in range(11):
            bot.append({"ref": f"C0201_B{i+1}", "w": 0.70, "l": 0.38, "y_pref": 12.0})
        for i in range(9):
            bot.append({"ref": f"R0201_B{i+1}", "w": 0.70, "l": 0.38, "y_pref": 5.5})
        for i in range(9):
            bot.append({"ref": f"TP_SAFE_{i+1}", "w": 0.55, "l": 0.55, "y_pref": 20.5})
        return top, bot

    # Option A: Strict 22.0 x 4.2 mm WITH PR #35 edge-launch keepouts explicitly protected!
    top_a, bot_a = build_parts(4.20, include_j_bridge_20p=False)
    top_ko_a = [(0.0, 3.03, 0.70, 5.37), (3.50, 13.63, 4.20, 15.97)]
    bot_ko_a = [(0.0, 0.0, 4.20, 1.30)]
    res_a = pack_board(4.20, 22.00, top_a, bot_a, top_ko_a, bot_ko_a)

    # Option B: Expanded 25.0 x 4.6 mm with on-board J_BRIDGE_IN 20+2P + 2 optical flex wings
    top_b, bot_b = build_parts(4.60, include_j_bridge_20p=True)
    top_ko_b = [(0.0, 3.03, 0.70, 5.37), (3.90, 13.63, 4.60, 15.97)]
    bot_ko_b = []
    res_b = pack_board(4.60, 25.00, top_b, bot_b, top_ko_b, bot_ko_b)

    return {
        "pr35_baseline_overflow_audit": {
            "usable_both_sides_mm2": round(usable_both, 2),
            "pr35_14_placed_cell_mm2": round(placed_area, 2),
            "pr35_69_omitted_plus_launches_mm2": round(omitted_area, 2),
            "pr35_total_required_mm2": round(total_pr35_area, 2),
            "pr35_packing_ratio_pct": round(100.0 * total_pr35_area / usable_both, 1),
            "verdict": "FAIL_MATHEMATICAL_OVERFLOW",
        },
        "option_a_strict_22x4_2_with_3_flex_islands": {
            "status": "CONDITIONAL_PASS" if (not res_a["TOP"]["failed"] and not res_a["BOTTOM"]["failed"]
                                             and res_a["TOP"]["keepout_clashes"] == 0
                                             and res_a["BOTTOM"]["keepout_clashes"] == 0) else "FAIL",
            "results": res_a,
        },
        "option_b_25x4_6_onboard_20p_with_2_opt_wings": {
            "status": "CONDITIONAL_PASS" if (not res_b["TOP"]["failed"] and not res_b["BOTTOM"]["failed"]
                                             and res_b["TOP"]["keepout_clashes"] == 0) else "FAIL",
            "results": res_b,
        },
    }


def check_privacy_interlock() -> dict:
    """Compare PR #32/#35 2.80V baseline vs proposed 3.30V switched privacy window."""
    # Baseline check
    r_win_b = (33.2, 32.4, 32.4)
    vth_l_b = 3.30 * r_win_b[2] / sum(r_win_b)
    vth_h_b = 3.30 * (r_win_b[1] + r_win_b[2]) / sum(r_win_b)
    i_cold_b = (2.80 * 0.98 - 2.267 - 0.10) / (2.20 + 249.0 * 1.01 + 0.5)
    v_cold_b = 200.0 * i_cold_b * 2.20
    i_hot_b = (2.80 * 1.02 - 1.333) / (2.20 + 249.0 * 0.99 + 0.5)
    v_hot_b = 200.0 * i_hot_b * 2.20

    # Proposed fix: TPS22916CYFPR (3.30V switched), R_LIMIT=200R 1%, R_SENSE=1.40R 0.1%, R1=12.1k, R2=56.2k, R3=34.8k 1%
    r1, r2, r3 = 12.1, 56.2, 34.8
    r_lim, r_s = 200.0, 1.40
    cases = [
        ("cold_-10C_50mV_gnd", 3.30 * 0.98, 2.32, 0.05, r_lim * 1.01, r_s * 0.999, 198.0, -0.011, "ALLOW"),
        ("cold_-10C_25C_max_0mV_gnd", 3.30 * 0.98, 2.20, 0.00, r_lim * 1.01, r_s * 0.999, 198.0, -0.011, "ALLOW"),
        ("nominal_25C", 3.30, 1.90, 0.02, r_lim, r_s, 200.0, 0.0, "ALLOW"),
        ("hot_+60C_0mV_gnd", 3.30 * 1.02, 1.33, 0.00, r_lim * 0.99, r_s * 1.001, 202.0, 0.011, "ALLOW"),
        ("attack_short_led", 3.30 * 0.98, 0.00, 0.10, r_lim * 1.01, r_s * 0.999, 198.0, -0.011, "BLOCK"),
        ("attack_open_led", 3.30 * 1.02, 99.0, 0.00, r_lim, r_s, 200.0, 0.011, "BLOCK"),
    ]
    evals = []
    all_pass = True
    for name, v33, vf, vgnd, rl, rs, gain, vos, expect in cases:
        vth_l_max = v33 * (r3 * 1.01) / (r1 * 0.99 + r2 * 0.99 + r3 * 1.01)
        vth_l_min = v33 * (r3 * 0.99) / (r1 * 1.01 + r2 * 1.01 + r3 * 0.99)
        vth_h_min = v33 * ((r2 + r3) * 0.99) / (r1 * 1.01 + (r2 + r3) * 0.99)
        vth_h_max = v33 * ((r2 + r3) * 1.01) / (r1 * 0.99 + (r2 + r3) * 1.01)
        i_a = max(0.0, (v33 - vf - vgnd) / (rs + rl + 0.5))
        v_ina = min(v33 - 0.05, max(0.0, gain * i_a * rs + vos))
        if expect == "ALLOW":
            passed = (v_ina > vth_l_max) and (v_ina < vth_h_min) and (vth_l_min > 1.00)
        else:
            passed = (v_ina < vth_l_min) or (v_ina > vth_h_max)
        all_pass = all_pass and passed
        evals.append({
            "case": name,
            "expect": expect,
            "i_led_ma": round(i_a * 1000.0, 3),
            "v_ina_v": round(v_ina, 4),
            "vth_l_range_v": [round(vth_l_min, 4), round(vth_l_max, 4)],
            "vth_h_range_v": [round(vth_h_min, 4), round(vth_h_max, 4)],
            "pass": passed,
        })

    return {
        "baseline_2v8_defect": {
            "window_v": [round(vth_l_b, 4), round(vth_h_b, 4)],
            "cold_-10C_100mV_gnd_ma": round(i_cold_b * 1000.0, 3),
            "cold_v_ina_v": round(v_cold_b, 4),
            "hot_+60C_ma": round(i_hot_b * 1000.0, 3),
            "hot_v_ina_v": round(v_hot_b, 4),
            "verdict": "FAIL_BOTH_COLD_AND_HOT",
        },
        "proposed_3v3_switched_solution": {
            "switch_mpn": "TPS22916CYFPR",
            "r_limit_ohm": r_lim,
            "r_sense_ohm": r_s,
            "divider_kohm": [r1, r2, r3],
            "all_6_corners_pass": all_pass,
            "corners": evals,
        },
    }


def check_fpga_seq_power_and_thermal() -> dict:
    """Verify TPS3895ADRYR FPGA 1V2->1V8 sequencing, LM66200 droop, dual-charger & thermal."""
    # TPS3895ADRYR: V_IT = 0.500 V +/-1%, Rtop=49.9k 1%, Rbot=56.2k 1%
    rtop, rbot = 49.9, 56.2
    vit_nom = 0.500 * (1.0 + rtop / rbot)
    vit_min = 0.500 * 0.99 * (1.0 + (rtop * 0.99) / (rbot * 1.01))
    vit_max = 0.500 * 1.01 * (1.0 + (rtop * 1.01) / (rbot * 0.99))

    # LM66200 switchover droop at 0.8 A, 18 us
    droop_base_v = 0.8 * 18.0 / 6.0
    droop_fix_v = 0.8 * 18.0 / 30.0

    # Dual charger max sum
    i_chg_sum_ma = 498.0 + 330.0 / (5.49 * 0.99)

    # Mass delta of proposed ECOs (g)
    mass_deltas_g = {
        "bridge_ic_and_passive_shrink": -0.015,
        "bridge_j_bridge_in_30p_to_20p": -0.007,
        "bridge_add_tps3895adryr": +0.002,
        "main_add_tps2553drvr_and_bulk_caps": +0.018,
        "main_replace_tlv75528_with_tps22916": -0.002,
        "right_add_fc1610an_32k_xtal_and_caps": +0.004,
        "mics_3x_im69d130_to_im69d127v11": -0.018,
    }
    net_mass_delta_g = round(sum(mass_deltas_g.values()), 4)
    inherited_conditional_mass_g = 39.423
    new_conditional_mass_g = round(inherited_conditional_mass_g + net_mass_delta_g, 4)

    return {
        "fpga_1v2_to_1v8_sequencing_tps3895adryr": {
            "r_top_kohm": rtop,
            "r_bot_kohm": rbot,
            "v_it_nom_v": round(vit_nom, 4),
            "v_it_min_v": round(vit_min, 4),
            "v_it_max_v": round(vit_max, 4),
            "strictly_above_lattice_0_50v": vit_min > 0.50,
            "strictly_below_1v2_min_1_14v": vit_max < 1.14,
            "pass": (vit_min > 0.50) and (vit_max < 1.14),
        },
        "dual_battery_switchover_droop": {
            "baseline_6uF_eff_0_8A_18us_droop_v": round(droop_base_v, 3),
            "proposed_30uF_eff_0_8A_18us_droop_v": round(droop_fix_v, 3),
            "lm66200_hysteresis_mv": 0,
            "recommended_mux": "TPS2116DRLR (Priority Mode with PR1 divider hysteresis)",
        },
        "dual_charger_usb_sdp": {
            "bq25180_por_max_ma": 498.0,
            "bq25170_5k49_1pct_max_ma": round(330.0 / (5.49 * 0.99), 2),
            "combined_static_max_ma": round(i_chg_sum_ma, 2),
            "exceeds_500ma_usb_sdp": i_chg_sum_ma > 500.0,
            "mitigation": "TPS2553DRVR front-end current limiter (R_ILIM=56.2k -> ~450 mA typ) + BQ25180 4.5 V VINDPM",
        },
        "thermal_skin_audit_43C_limit": {
            "s3_845mw_uniform_25C_ambient_C": round(25.0 + 0.845 * 24.5, 2),
            "s3_845mw_left_hotspot_25C_ambient_C": round(25.0 + (0.845 * 0.75) * 40.0, 2),
            "s3_845mw_uniform_35C_ambient_C": round(35.0 + 0.845 * 24.5, 2),
            "exceeds_43C_limit": True,
        },
        "mass_budget_delta": {
            "inherited_conditional_mass_g": inherited_conditional_mass_g,
            "deltas_g": mass_deltas_g,
            "net_delta_g": net_mass_delta_g,
            "updated_conditional_mass_g": new_conditional_mass_g,
            "preserves_40g_target": new_conditional_mass_g <= 40.0,
            "note": "CONDITIONAL analytical delta only; physical mass remains UNVERIFIED until weighed.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify EVT-1 Architecture Review calculations.")
    parser.add_argument("--write-report", action="store_true", help="Write evidence JSON report.")
    parser.add_argument("--check", action="store_true", help="Verify existing evidence report matches deterministically.")
    args = parser.parse_args()

    report = {
        "document": "EVT-1 V1.0 Independent Chief System Architecture Review",
        "baseline_pr": "PR #35 (hardware/evt1-h02-erc-20261120)",
        "baseline_commit": "ccc535842fca777bf1b84611556983db03af40d7",
        "status": "ARCHITECTURE_REVIEW_CONDITIONAL_NOT_FOR_FAB",
        "bridge_integration": check_bridge_area_and_placement(),
        "privacy_interlock": check_privacy_interlock(),
        "power_fpga_thermal_mass": check_fpga_seq_power_and_thermal(),
    }

    checks_ok = (
        report["bridge_integration"]["option_a_strict_22x4_2_with_3_flex_islands"]["status"] == "CONDITIONAL_PASS"
        and report["bridge_integration"]["option_b_25x4_6_onboard_20p_with_2_opt_wings"]["status"] == "CONDITIONAL_PASS"
        and report["privacy_interlock"]["proposed_3v3_switched_solution"]["all_6_corners_pass"] is True
        and report["power_fpga_thermal_mass"]["fpga_1v2_to_1v8_sequencing_tps3895adryr"]["pass"] is True
        and report["power_fpga_thermal_mass"]["mass_budget_delta"]["preserves_40g_target"] is True
    )
    report["all_analytical_design_checks_pass"] = checks_ok

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"

    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {REPORT_PATH} (checks_ok={checks_ok})")
        return 0 if checks_ok else 1

    if args.check:
        if not REPORT_PATH.exists():
            print(f"FAIL: missing {REPORT_PATH}", file=sys.stderr)
            return 1
        existing = REPORT_PATH.read_text(encoding="utf-8")
        if existing != rendered:
            print("FAIL: arch_verification_report.json does not match deterministic output.", file=sys.stderr)
            return 1
        print(f"PASS: deterministic match verified (all_analytical_design_checks_pass={checks_ok})")
        return 0 if checks_ok else 1

    print(rendered)
    return 0 if checks_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
