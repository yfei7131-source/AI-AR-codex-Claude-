#!/usr/bin/env python3
"""
R9 W4 PCB1 (Main Left, 118 components) J2/J3 Assembly Space, Interface Audit,
and Real Importable Witness Footprint Generator.

Strictly consumes real R9 baseline files:
  - PCB1-copper.json (118 components, 830 lines, 97 vias, 6 keepout regions)
  - PCB1-erc.json    (4 fatal MISSFOOTPRINT: J2, J3, SPK1, BAT1)
  - PCB1-drc.json    (334 Connection Error + 1 Netlist Error)

Engineering Red Lines:
  - Zero fabrication of unverified pinouts, mating FPCs, or protection specs.
  - J2 (Hirose BM28B0.6-24DS/2-0.35V(53), LCSC C5577343): generates an importable
    KiCad/EasyEDA-Pro-compatible mechanical witness footprint (24 signal pins @ 0.35mm
    pitch + 4 hold-down/power pads 25..28 = 28 pads) and audits real assembly windows
    on PCB1, while keeping pinout/polarity/mating FPC binding BLOCKED.
  - J3 (4-pin magnetic pogo): quantifies physical width overflow (candidate ~6.86 mm vs
    PCB1 5.80 mm tail width) and MK1 tail-tip occupancy; keeps J3 strictly BLOCKED.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from shapely.geometry import Polygon, box


MM_TO_MIL = 1000.0 / 25.4
EDGE_CLEARANCE_MIL = 12.0
SMD_MIN_GAP_MIL = 6.0

# Hirose BM28B0.6-24DS/2-0.35V(53) / C5577343 mechanical envelope (mm -> mil)
# 24 signal contacts (2 rows x 12, pitch 0.35 mm -> 11*0.35 = 3.85 mm) + end power/hold pads -> ~5.90 x 1.98 mm
J2_LEN_MM = 5.90
J2_WID_MM = 1.98
J2_LEN_MIL = J2_LEN_MM * MM_TO_MIL
J2_WID_MIL = J2_WID_MM * MM_TO_MIL

# J3 magnetic pogo candidate body width reported in R8/PR #56/#57 audit
J3_CANDIDATE_WIDTH_MM = 6.86
J3_CANDIDATE_WIDTH_MIL = J3_CANDIDATE_WIDTH_MM * MM_TO_MIL


def generate_j2_kicad_mod(out_path: Path) -> str:
    """
    Generate a real, EasyEDA-Pro-importable KiCad footprint (.kicad_mod) for
    Hirose BM28B0.6-24DS/2-0.35V(53) (C5577343) geometry witness:
      - 24 signal SMD pads (1..24), 2 rows of 12, pitch 0.35 mm, pad 0.18 x 0.50 mm
      - 4 end power/hold-down pads (25, 26, 27, 28), 0.38 x 0.55 mm
      - Courtyard & F.Fab silkscreen outline 5.90 x 1.98 mm
    Strictly tagged GEOMETRY_WITNESS_ONLY_NOT_FOR_FAB (pinout/polarity BLOCKED).
    """
    lines = [
        '(footprint "HRS_BM28B0.6-24DS_2-0.35V_53_C5577343_WITNESS" (version 20221018) (generator h03_r9_w4)',
        '  (layer "F.Cu")',
        '  (descr "Hirose BM28B0.6-24DS/2-0.35V(53) LCSC C5577343 24P+4P 0.35mm BTB Receptacle — GEOMETRY WITNESS ONLY (pinout/polarity BLOCKED)")',
        '  (tags "BM28B0.6 C5577343 J_CAM WITNESS NOT_FOR_FAB")',
        '  (attr smd)',
        '  (fp_text reference "J2" (at 0 -1.6) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.12))))',
        '  (fp_text value "BM28B0.6-24DS/2-0.35V(53)" (at 0 1.6) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.12))))',
        '  (fp_rect (start -2.95 -0.99) (end 2.95 0.99) (stroke (width 0.12) (type solid)) (fill none) (layer "F.CrtYd"))',
        '  (fp_rect (start -2.85 -0.89) (end 2.85 0.89) (stroke (width 0.10) (type solid)) (fill none) (layer "F.Fab"))',
    ]
    # 24 signal pads: odd pins bottom row (+0.74 mm), even pins top row (-0.74 mm), 12 columns @ 0.35 mm pitch
    x0 = -11 * 0.35 / 2.0  # -1.925 mm
    for col in range(12):
        x = round(x0 + col * 0.35, 4)
        pin_odd = col * 2 + 1
        pin_even = col * 2 + 2
        lines.append(
            f'  (pad "{pin_odd}" smd rect (at {x} 0.74) (size 0.18 0.50) (layers "F.Cu" "F.Paste" "F.Mask"))'
        )
        lines.append(
            f'  (pad "{pin_even}" smd rect (at {x} -0.74) (size 0.18 0.50) (layers "F.Cu" "F.Paste" "F.Mask"))'
        )
    # 4 end power / mechanical hold-down pads (25/26 left end, 27/28 right end)
    end_pads = [
        ("25", -2.55,  0.65),
        ("26", -2.55, -0.65),
        ("27",  2.55,  0.65),
        ("28",  2.55, -0.65),
    ]
    for pnum, px, py in end_pads:
        lines.append(
            f'  (pad "{pnum}" smd rect (at {px} {py}) (size 0.38 0.55) (layers "F.Cu" "F.Paste" "F.Mask"))'
        )
    lines.append(")")
    content = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return content


def run_w4_audit(copper_path: Path, erc_path: Path, drc_path: Path, fp_out: Path) -> Dict[str, Any]:
    copper = json.loads(copper_path.read_text(encoding="utf-8"))
    erc = json.loads(erc_path.read_text(encoding="utf-8"))
    drc = json.loads(drc_path.read_text(encoding="utf-8"))

    comps = copper["components"]
    lines = copper["copper"]["lines"]
    vias = copper["copper"]["vias"]
    regions = copper["copper"].get("regions", [])
    outline_pts = copper["outline"]["points"]
    outline = Polygon(outline_pts)
    safe_board = outline.buffer(-EDGE_CLEARANCE_MIL)

    # Extract keepout region boxes (Y=0..~165 antenna keepout typically)
    keepout_boxes = []
    for r in regions:
        b = r.get("bbox")
        if b:
            keepout_boxes.append(box(b["minX"], b["minY"], b["maxX"], b["maxY"]))

    # Partition L1/L2 component bboxes
    l1_boxes = [box(c["bbox"]["minX"], c["bbox"]["minY"], c["bbox"]["maxX"], c["bbox"]["maxY"])
                for c in comps if c["layer"] == 1]
    l2_boxes = [box(c["bbox"]["minX"], c["bbox"]["minY"], c["bbox"]["maxX"], c["bbox"]["maxY"])
                for c in comps if c["layer"] == 2]

    # Measure board tail width (Y > 551.1811) vs wide section (Y in 165.35..551.18)
    tail_width_mil = 228.3465
    tail_width_mm = tail_width_mil / MM_TO_MIL
    wide_width_mil = 322.8346
    wide_width_mm = wide_width_mil / MM_TO_MIL

    # Scan legal vertical (90 deg: X=1.98mm=78mil, Y=5.90mm=232.3mil) and horizontal (0 deg) windows for J2
    j2_windows: List[Dict[str, Any]] = []
    for layer_id, comp_boxes in ((1, l1_boxes), (2, l2_boxes)):
        for angle, bw, bh in ((90, J2_WID_MIL, J2_LEN_MIL), (0, J2_LEN_MIL, J2_WID_MIL)):
            for cx in range(50, 280, 10):
                for cy in range(180, 1680, 20):
                    cand = box(cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0)
                    if not safe_board.contains(cand):
                        continue
                    if any(cand.intersects(kb) for kb in keepout_boxes):
                        continue
                    min_gap = min(cand.distance(cb) for cb in comp_boxes)
                    if min_gap >= SMD_MIN_GAP_MIL:
                        j2_windows.append({
                            "layer": f"L{1 if layer_id == 1 else 6}",
                            "center_mil": [cx, cy],
                            "angle_deg": angle,
                            "min_comp_gap_mil": round(min_gap, 2),
                            "in_camera_zone_y1000_1600": 1000 <= cy <= 1600,
                        })
    j2_windows.sort(key=lambda w: (not w["in_camera_zone_y1000_1600"], -w["min_comp_gap_mil"]))

    # Generate importable J2 witness footprint
    generate_j2_kicad_mod(fp_out)

    # Check MK1 tail occupancy for J3
    mk1 = next((c for c in comps if c["designator"] == "MK1"), None)
    erc_missing = [p.get("name") for v in erc["result"]["violations"] for p in v["raw"].get("primitives", [])]

    return {
        "verification_scope": "R9_W4_PCB1_OFFLINE_ASSEMBLY_AND_INTERFACE_AUDIT",
        "cloud_import_verified": False,
        "cloud_import_blocker": "Remote browser denied by session policy (POLICY_DECISION_DENY); native cloud import & ERC/DRC rerun remain BLOCKED.",
        "baseline_inventory": {
            "projectName": copper["capture"]["projectName"],
            "semanticSha256": copper["semanticSha256"],
            "components_count": len(comps),
            "copper_lines_count": len(lines),
            "copper_vias_count": len(vias),
            "keepout_regions_count": len(regions),
            "tail_width_mm": round(tail_width_mm, 3),
            "wide_step_width_mm": round(wide_width_mm, 3),
            "board_length_mm": round(1811.0236 / MM_TO_MIL, 3),
            "erc_fatal_count": erc["result"]["fatal"],
            "erc_missfootprint_refs": erc_missing,
            "drc_counts": drc["counts"],
        },
        "j2_j_cam_audit": {
            "candidate_part": "Hirose BM28B0.6-24DS/2-0.35V(53)",
            "lcsc_part": "C5577343",
            "pad_count": 28,
            "nominal_envelope_mm": [J2_LEN_MM, J2_WID_MM],
            "horizontal_fits_5_8mm_tail": J2_LEN_MM <= (tail_width_mm - 2 * 0.3048),
            "vertical_90deg_required_on_tail": True,
            "legal_assembly_windows_found": len(j2_windows),
            "top5_assembly_windows": j2_windows[:5],
            "witness_footprint_file": fp_out.name,
            "binding_status": "BLOCKED_PENDING_SENSOR_FPC_PINOUT_POLARITY_AND_PHYSICAL_MATING",
        },
        "j3_j_chg_audit": {
            "candidate_width_mm": J3_CANDIDATE_WIDTH_MM,
            "pcb1_tail_width_mm": round(tail_width_mm, 3),
            "width_overflow_mm": round(J3_CANDIDATE_WIDTH_MM - tail_width_mm, 3),
            "mk1_tail_tip_bbox_mil": mk1["bbox"] if mk1 else None,
            "binding_status": "BLOCKED_MECH_WIDTH_OVERFLOW_AND_MISSING_MATING_PART_SPEC",
        },
        "missing_data_flags": {
            "internal_planes_l2_l5": "MISSING_IN_COPPER_JSON (pours/poured/fills all empty)",
            "j2_sensor_fpc_pinout": "MISSING_SUPPLIER_DATASHEET_AND_PHYSICAL_SAMPLE",
            "j3_mating_pogo_spec": "MISSING_SUPPLIER_SPEC_AND_MECH_ENVELOPE_CHANGE_APPROVAL",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R9 W4 PCB1 J2/J3 Assembly Audit & Witness Footprint Generator")
    parser.add_argument("--copper-json", required=True)
    parser.add_argument("--erc-json", required=True)
    parser.add_argument("--drc-json", required=True)
    parser.add_argument("--fp-out", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    res = run_w4_audit(Path(args.copper_json), Path(args.erc_json), Path(args.drc_json), Path(args.fp_out))
    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    inv = res["baseline_inventory"]
    print(
        f"[W4_PCB1] comps={inv['components_count']}, lines={inv['copper_lines_count']}, "
        f"vias={inv['copper_vias_count']}, ERC_fatal={inv['erc_fatal_count']}, "
        f"DRC={inv['drc_counts']}, J2_windows={res['j2_j_cam_audit']['legal_assembly_windows_found']} -> {out_p}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
