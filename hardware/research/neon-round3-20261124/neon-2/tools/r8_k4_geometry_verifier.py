#!/usr/bin/env python3
"""
H03-R8 Offline HDI Geometry & Rule-Compliance Verifier
Validates:
1. 0.80 mm 6-layer 2nd-order HDI (2+2+2) stack-up budget vs JLCPCB capabilities.
2. R6/R7 K4 failing coordinates vs R8 staggered remediation coordinates
   against BOTH JLCPCB fab minimums (5.0 mil same-net) and EasyEDA Pro native
   Multi-Layer Hole-to-Hole DRC floor (11.8 mil) without rule relaxation.
3. Outputs structured JSON verification log.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

MIL_TO_MM = 0.0254
MM_TO_MIL = 1.0 / MIL_TO_MM

# Locked project & JLCPCB rules (zero relaxation)
RULES = {
    "easyeda_native_hole_to_hole_mil": 11.8,
    "jlcpcb_same_net_blind_via_spacing_mil": 5.0,
    "jlcpcb_diff_net_blind_via_spacing_mil": 9.5,
    "jlcpcb_min_core_for_buried_via_um": 300.0,
    "jlcpcb_min_pp_um": 50.0,
    "jlcpcb_max_laser_aspect_ratio": 1.0,
    "jlcpcb_min_annular_ring_mil": 3.0,
    "project_locked_copper_clearance_mm": 0.1524,
}

# R8 0.800 mm 6L 2+2+2 stack-up candidates
STACKUP_CANDIDATES = [
    {"name": "R6_R8_Base_50um_PP", "pp_um": 50.0, "core_um": 418.0, "outer_cu_um": 35.0, "inner_cu_um": 18.0, "sm_per_side_um": 20.0},
    {"name": "R8_Alt_55um_PP", "pp_um": 55.0, "core_um": 398.0, "outer_cu_um": 35.0, "inner_cu_um": 18.0, "sm_per_side_um": 20.0},
    {"name": "R8_Alt_60um_PP", "pp_um": 60.0, "core_um": 378.0, "outer_cu_um": 35.0, "inner_cu_um": 18.0, "sm_per_side_um": 20.0},
    {"name": "Conflict_Check_86um_1080_PP", "pp_um": 86.0, "core_um": 274.0, "outer_cu_um": 35.0, "inner_cu_um": 18.0, "sm_per_side_um": 20.0},
]

# Via specs (mil)
LASER_100UM_HOLE_MIL = 0.100 * MM_TO_MIL  # 3.937008 mil
LASER_100UM_PAD_MIL = LASER_100UM_HOLE_MIL + 6.0  # 9.937008 mil (0.2524 mm)
BURIED_6MIL_HOLE_MIL = 6.0  # 0.1524 mm
BURIED_6MIL_PAD_MIL = 12.0  # 0.3048 mm

# R8 staggered K4 trial vias (net: I2S_LRCLK_1V8)
R8_VIAS = [
    {"id": "e53_r8", "span": "BV_L1_L2", "x_mil": 179.47, "y_mil": 328.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
    {"id": "e54_r8", "span": "BV_L2_L3", "x_mil": 195.47, "y_mil": 328.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
    {"id": "e55_r8", "span": "BV_L3_L4", "x_mil": 195.47, "y_mil": 311.00, "hole_mil": BURIED_6MIL_HOLE_MIL, "pad_mil": BURIED_6MIL_PAD_MIL},
    {"id": "e56_r8", "span": "BV_L4_L5", "x_mil": 102.97, "y_mil": 301.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
    {"id": "e57_r8", "span": "BV_L5_L6", "x_mil": 118.97, "y_mil": 301.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
    {"id": "e58_r8", "span": "BV_L4_L5", "x_mil": 137.97, "y_mil": 376.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
    {"id": "e59_r8", "span": "BV_L5_L6", "x_mil": 153.97, "y_mil": 376.00, "hole_mil": LASER_100UM_HOLE_MIL, "pad_mil": LASER_100UM_PAD_MIL},
]


def evaluate_stackups():
    results = []
    for s in STACKUP_CANDIDATES:
        total_um = 4 * s["pp_um"] + s["core_um"] + 2 * s["outer_cu_um"] + 4 * s["inner_cu_um"] + 2 * s["sm_per_side_um"]
        ar_75 = s["pp_um"] / 75.0
        ar_100 = s["pp_um"] / 100.0
        core_ok = s["core_um"] >= RULES["jlcpcb_min_core_for_buried_via_um"]
        pp_ok = s["pp_um"] >= RULES["jlcpcb_min_pp_um"]
        ar_75_ok = ar_75 <= RULES["jlcpcb_max_laser_aspect_ratio"]
        ar_100_ok = ar_100 <= RULES["jlcpcb_max_laser_aspect_ratio"]
        results.append({
            "name": s["name"],
            "total_thickness_mm": round(total_um / 1000.0, 4),
            "pp_um": s["pp_um"],
            "core_um": s["core_um"],
            "ar_75um_laser": round(ar_75, 3),
            "ar_100um_laser": round(ar_100, 3),
            "core_ge_300um_pass": core_ok,
            "pp_ge_50um_pass": pp_ok,
            "laser_75um_ar_pass": ar_75_ok,
            "laser_100um_ar_pass": ar_100_ok,
            "overall_jlc_feasible": core_ok and pp_ok and ar_100_ok,
        })
    return results


def evaluate_k4_pairs():
    pair_checks = []
    min_wall_mil = float("inf")
    native_pass_all = True
    jlc_pass_all = True
    for i in range(len(R8_VIAS)):
        for j in range(i + 1, len(R8_VIAS)):
            a, b = R8_VIAS[i], R8_VIAS[j]
            c2c_mil = math.hypot(a["x_mil"] - b["x_mil"], a["y_mil"] - b["y_mil"])
            wall_mil = c2c_mil - (a["hole_mil"] + b["hole_mil"]) / 2.0
            pad_gap_mil = c2c_mil - (a["pad_mil"] + b["pad_mil"]) / 2.0
            if wall_mil < min_wall_mil:
                min_wall_mil = wall_mil
            native_ok = wall_mil >= RULES["easyeda_native_hole_to_hole_mil"]
            jlc_ok = wall_mil >= RULES["jlcpcb_same_net_blind_via_spacing_mil"]
            native_pass_all = native_pass_all and native_ok
            jlc_pass_all = jlc_pass_all and jlc_ok
            if c2c_mil < 30.0:  # log adjacent transition pairs
                pair_checks.append({
                    "pair": f"{a['id']} ({a['span']}) <-> {b['id']} ({b['span']})",
                    "center_to_center_mil": round(c2c_mil, 4),
                    "wall_to_wall_mil": round(wall_mil, 4),
                    "wall_to_wall_mm": round(wall_mil * MIL_TO_MM, 4),
                    "pad_to_pad_gap_mil": round(pad_gap_mil, 4),
                    "easyeda_11_8mil_pass": native_ok,
                    "jlcpcb_5_0mil_pass": jlc_ok,
                })
    return {
        "adjacent_pair_checks": pair_checks,
        "min_wall_to_wall_mil_all_pairs": round(min_wall_mil, 4),
        "all_pairs_pass_easyeda_11_8mil": native_pass_all,
        "all_pairs_pass_jlcpcb_5_0mil": jlc_pass_all,
    }


def main():
    report = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "H03-R8 Offline Geometry & Stack-up Verification (NOT native EasyEDA Pro DRC)",
        "native_easyeda_pro_drc_status": "BLOCKED - requires local Windows EasyEDA Pro daemon (127.0.0.1:60832-60841)",
        "rules_checked": RULES,
        "stackup_verification": evaluate_stackups(),
        "k4_remediation_geometry": evaluate_k4_pairs(),
    }
    out_path = Path("/working_dir/c_092afa91da962bf4/artifacts/file_generation/ttl=63d/output/r8_offline_verification_log.json")
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
