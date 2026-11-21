#!/usr/bin/env python3
"""Untruncated 3D Blind-Via-Aware + Laser Microvia Annular-Ring HDI DFM Auditor (V2, PR #45).

Extends PR #44's independent_hdi_dfm_auditor.py to additionally audit:
  1. Every laser blind microvia's exact hole diameter, capture pad diameter, and annular ring width
     against JLCPCB & PCBWay 6L 1+4+1 HDI rules (min hole >= 0.075 mm / 2.95 mil; min annular ring >= 3.0 mil / 0.075 mm).
  2. Flags ANY blind microvia with annular ring < 2.95 mil (< 0.075 mm) as `UNDER_ANNULAR_RING_BLIND_VIA`.
  3. Preserves exact 3D Z-layer clearance checks (`TRUE_PHYSICAL_VIOLATION`, `REAL_DFM_VIA_TOUCHES_SMD_PAD`,
     `RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK`, `CHECKER_FP_BLIND_VIA_CROSS_LAYER`).
"""

import argparse
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h03-dfm-p0-closure"),
]

from independent_hdi_dfm_auditor import DOCS, audit_board
from prepare_hierarchy import Archive


def audit_board_v2(board: str, arc: Archive, dump_path: Path, out_csv: Path | None = None) -> dict:
    base = audit_board(board, arc, dump_path, out_csv)
    doc = arc.documents[("PCB", DOCS[board])]

    blind_vias = []
    mech_vias = []
    under_ring_blind = []
    illegal_mech = []

    for r in doc.records:
        if r.header["type"] != "VIA":
            continue
        p = r.payload
        vt = p.get("viaType", "NORMAL")
        hole = float(p.get("holeDiameter", 0.0))
        diam = float(p.get("viaDiameter", 0.0))
        ring = round((diam - hole) / 2.0, 3)
        rec = {
            "id": r.header["id"],
            "net": p.get("netName", ""),
            "viaType": vt,
            "ruleName": p.get("ruleName", ""),
            "hole_mil": round(hole, 2),
            "diam_mil": round(diam, 2),
            "ring_mil": ring,
            "hole_mm": round(hole * 0.0254, 4),
            "diam_mm": round(diam * 0.0254, 4),
            "ring_mm": round(ring * 0.0254, 4),
            "x": round(float(p["centerX"]), 2),
            "y": round(float(p["centerY"]), 2),
        }
        if vt == "BLIND":
            blind_vias.append(rec)
            if ring < 2.95 or hole < 2.95:
                under_ring_blind.append(rec)
        else:
            mech_vias.append(rec)
            if hole < 5.95 or ring < 2.95:
                illegal_mech.append(rec)

    blind_sizes = {}
    for v in blind_vias:
        k = f"{v['ruleName']} ({v['hole_mil']}/{v['diam_mil']}mil, ring={v['ring_mil']}mil)"
        blind_sizes[k] = blind_sizes.get(k, 0) + 1

    base["laser_blind_annular_ring_audit"] = {
        "total_blind_vias": len(blind_vias),
        "total_mech_through_vias": len(mech_vias),
        "min_blind_hole_mil": min((v["hole_mil"] for v in blind_vias), default=0.0),
        "min_blind_diam_mil": min((v["diam_mil"] for v in blind_vias), default=0.0),
        "min_blind_ring_mil": min((v["ring_mil"] for v in blind_vias), default=0.0),
        "min_blind_ring_mm": min((v["ring_mm"] for v in blind_vias), default=0.0),
        "under_3mil_ring_blind_vias": len(under_ring_blind),
        "illegal_mech_through_vias": len(illegal_mech),
        "blind_size_breakdown": blind_sizes,
    }
    return base


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epro", type=Path, required=True)
    p.add_argument("--dump-dir", type=Path, required=True)
    p.add_argument("--dump-suffix", default="-post.dump.json")
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()

    arc = Archive(a.epro)
    full = {}
    for b in ("PCB1", "PCB2", "PCB3"):
        res = audit_board_v2(b, arc, a.dump_dir / f"{b}{a.dump_suffix}", a.out_dir / f"{b}-conflict-matrix.csv")
        full[b] = res
        print(f"\n=== {b} UNTRUNCATED 3D + LASER ANNULAR-RING HDI DFM AUDIT ===")
        print("  by_classification:", json.dumps(res["by_classification"], indent=2))
        print("  laser_blind_annular_ring_audit:", json.dumps(res["laser_blind_annular_ring_audit"], indent=2))
    (a.out_dir / "independent-dfm-v2-summary.json").write_text(
        json.dumps(full, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
