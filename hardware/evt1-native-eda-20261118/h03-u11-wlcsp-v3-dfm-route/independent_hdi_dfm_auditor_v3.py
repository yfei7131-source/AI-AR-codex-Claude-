#!/usr/bin/env python3
"""Untruncated 3D + Extended V3 Laser Blind Microvia & U11 WLCSP HDI DFM Auditor (PR #46).

Extends PR #45's V2 auditor (`independent_hdi_dfm_auditor_v2.py`) with full manufacturing
constraint verification of EVERY laser blind microvia across PCB1, PCB2, and PCB3:
  1. Board-edge copper clearance >= 11.811 mil (0.300 mm) against each board's true outline
     (including PCB1's stepped notch outline: x in [0, 551.1811] for y >= 228.3465,
      x in [0, 228.3465] for y < 228.3465).
  2. Same-span via-to-via copper clearance >= 6.0 mil (0.1524 mm) across shared vertical spans
     (BV_L1_L2={1,15}, BV_L5_L6={18,2}, NORMAL={1,15,16,17,18,2}).
  3. Same-span via-to-via hole-wall spacing >= 8.0 mil (0.203 mm) for all laser blind pairs.
  4. Laser blind microvia annular ring >= 2.95 mil (0.075 mm; nominal 3.0 mil) & hole >= 2.95 mil.
  5. Layer-span compliance: strictly BV_L1_L2 or BV_L5_L6 for BLIND vias; 0 illegal < 6 mil
     mechanical through-vias.
  6. PCB3 U11 (nRF5340-CMAA-R7, 0.35 mm WLCSP-95) 95-ball ring-depth & escape audit.
  7. Preserves explicit BLOCKED governance status for all fab-unapproved HDI/VIPPO/WLCSP items.
"""

import argparse
import json
import math
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h03-dfm-p0-closure"),
    str(PACKAGE / "h03-hdi-laser-wlcsp-route"),
]

from independent_hdi_dfm_auditor import DOCS
from independent_hdi_dfm_auditor_v2 import audit_board_v2
from prepare_hierarchy import Archive

MIN_BLIND_EDGE_CU_MIL = 11.811     # 0.300 mm copper-to-outline minimum
MIN_BLIND_VV_CU_MIL = 6.0          # 0.1524 mm same-span copper-to-copper minimum
MIN_BLIND_VV_HOLE_WALL_MIL = 8.0   # 0.2032 mm same-span drill-wall-to-drill-wall minimum
MIN_BLIND_RING_MIL = 2.95          # 0.075 mm annular ring minimum (nominal 3.0 mil)
MIN_BLIND_HOLE_MIL = 2.95          # 0.075 mm laser drill minimum
ALLOWED_BLIND_RULES = {"BV_L1_L2", "BV_L5_L6"}


def via_layer_span(via_type: str, rule_name: str) -> set[int]:
    if via_type == "BLIND":
        if rule_name == "BV_L1_L2":
            return {1, 15}
        if rule_name == "BV_L5_L6":
            return {18, 2}
        return {1, 15, 16, 17, 18, 2}
    return {1, 15, 16, 17, 18, 2}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def extract_outline_polygon(dump: dict) -> list[tuple[float, float]]:
    pts = (dump.get("outline") or {}).get("points") or []
    poly = [(float(p[0]), float(p[1])) for p in pts]
    if len(poly) >= 2 and math.hypot(poly[0][0] - poly[-1][0], poly[0][1] - poly[-1][1]) < 1e-6:
        poly = poly[:-1]
    if len(poly) < 3:
        raise ValueError("Missing or invalid board outline polygon in PCB dump")
    return poly


def pt_inside_polygon(poly: list[tuple[float, float]], x: float, y: float) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                inside = not inside
    return inside


def center_to_outline_dist(poly: list[tuple[float, float]], x: float, y: float) -> float:
    n = len(poly)
    d = min(
        pt_seg_dist(x, y, poly[i][0], poly[i][1], poly[(i + 1) % n][0], poly[(i + 1) % n][1])
        for i in range(n)
    )
    return d if pt_inside_polygon(poly, x, y) else -d


def audit_u11_wlcsp_95(dump_path: Path) -> dict:
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    u11 = next((c for c in dump.get("components", []) if c.get("designator") == "U11"), None)
    if u11 is None:
        return {"found": False}
    pads = u11.get("pads", [])
    xs = sorted(round(float(p["x"]), 2) for p in pads)
    ys = sorted(round(float(p["y"]), 2) for p in pads)

    def cluster_coords(vals: list[float], tol: float = 3.0) -> list[float]:
        groups: list[list[float]] = []
        for v in vals:
            if not groups or abs(v - groups[-1][-1]) > tol:
                groups.append([v])
            else:
                groups[-1].append(v)
        return [round(sum(g) / len(g), 2) for g in groups]

    ux = cluster_coords(xs)
    uy = cluster_coords(ys)
    nx, ny = len(ux), len(uy)

    def nearest_idx(val: float, grid: list[float]) -> int:
        return min(range(len(grid)), key=lambda i: abs(grid[i] - val))

    outer_active = []
    ring1_active = []
    deep_inner_active = []
    nc_balls = []
    for p in pads:
        px, py = float(p["x"]), float(p["y"])
        ix = nearest_idx(px, ux)
        iy = nearest_idx(py, uy)
        depth = min(ix, nx - 1 - ix, iy, ny - 1 - iy)
        net = (p.get("net") or "").strip()
        rec = {
            "pad": str(p.get("padNumber", "")),
            "net": net,
            "grid_ix": ix,
            "grid_iy": iy,
            "ring_depth": depth,
            "x_mil": round(px, 2),
            "y_mil": round(py, 2),
        }
        if not net:
            nc_balls.append(rec)
        elif depth == 0:
            outer_active.append(rec)
        elif depth == 1:
            ring1_active.append(rec)
        else:
            deep_inner_active.append(rec)

    pitch_x_mil = round((ux[-1] - ux[0]) / max(1, nx - 1), 3) if nx > 1 else 0.0
    pitch_y_mil = round((uy[-1] - uy[0]) / max(1, ny - 1), 3) if ny > 1 else 0.0
    deep_inner_signals = [r for r in deep_inner_active if r["net"] != "GND"]
    deep_inner_gnd = [r for r in deep_inner_active if r["net"] == "GND"]
    ring1_signals = [r for r in ring1_active if r["net"] not in ("GND", "1V8_SYS")]
    ring1_power_gnd = [r for r in ring1_active if r["net"] in ("GND", "1V8_SYS")]

    return {
        "found": True,
        "designator": "U11",
        "bom_mpn": "nRF5340-CMAA-R7",
        "package": "WLCSP-95 (3.994 x 4.390 x 0.449 mm, 0.35 mm pitch)",
        "total_balls": len(pads),
        "grid_cols": nx,
        "grid_rows": ny,
        "measured_pitch_x_mil": pitch_x_mil,
        "measured_pitch_y_mil": pitch_y_mil,
        "measured_pitch_mm": round(0.5 * (pitch_x_mil + pitch_y_mil) * 0.0254, 4),
        "active_balls": len(outer_active) + len(ring1_active) + len(deep_inner_active),
        "nc_unassigned_balls": len(nc_balls),
        "outer_perimeter_depth0_active": len(outer_active),
        "ring1_depth1_active": len(ring1_active),
        "ring1_power_gnd_count": len(ring1_power_gnd),
        "ring1_signal_rf_clk_count": len(ring1_signals),
        "deep_inner_depth2plus_active": len(deep_inner_active),
        "deep_inner_gnd_count": len(deep_inner_gnd),
        "deep_inner_signal_count": len(deep_inner_signals),
        "deep_inner_signal_balls": [f"{r['pad']}:{r['net']}" for r in sorted(deep_inner_signals, key=lambda d: d["pad"])],
        "ring1_signal_balls": [f"{r['pad']}:{r['net']}" for r in sorted(ring1_signals, key=lambda d: d["pad"])],
        "inner_balls_blocked_under_std_1stage_hdi_6mil": len(ring1_active) + len(deep_inner_active),
        "selected_technical_route": "OPTION_1_RETAIN_CMAA_UPGRADE_PCB3_TIER1_ADVANCED_HDI_2N2_VIPPO",
        "fab_approval_status": "BLOCKED_PENDING_TIER1_HDI_FAB_EQ",
    }


def audit_board_v3(board: str, arc: Archive, dump_path: Path, out_csv: Path | None = None) -> dict:
    base = audit_board_v2(board, arc, dump_path, out_csv)
    doc = arc.documents[("PCB", DOCS[board])]
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    outline_poly = extract_outline_polygon(dump)

    all_vias = []
    for r in doc.records:
        if r.header["type"] != "VIA":
            continue
        p = r.payload
        vt = p.get("viaType", "NORMAL")
        rn = p.get("ruleName", "")
        hole = float(p.get("holeDiameter", 0.0))
        diam = float(p.get("viaDiameter", 0.0))
        ring = round((diam - hole) / 2.0, 3)
        x = float(p["centerX"])
        y = float(p["centerY"])
        all_vias.append({
            "id": r.header["id"],
            "net": p.get("netName", ""),
            "viaType": vt,
            "ruleName": rn,
            "hole_mil": round(hole, 3),
            "diam_mil": round(diam, 3),
            "ring_mil": ring,
            "x": round(x, 3),
            "y": round(y, 3),
            "span": via_layer_span(vt, rn),
        })

    blinds = [v for v in all_vias if v["viaType"] == "BLIND"]
    bad_edge = []
    bad_ring = []
    bad_hole = []
    bad_span = []
    edge_dists = []

    for v in blinds:
        c2e = center_to_outline_dist(outline_poly, v["x"], v["y"])
        cu2e = round(c2e - 0.5 * v["diam_mil"], 3)
        edge_dists.append(cu2e)
        if cu2e < MIN_BLIND_EDGE_CU_MIL:
            bad_edge.append({"id": v["id"], "net": v["net"], "ruleName": v["ruleName"], "cu_to_edge_mil": cu2e})
        if v["ring_mil"] < MIN_BLIND_RING_MIL:
            bad_ring.append({"id": v["id"], "net": v["net"], "ring_mil": v["ring_mil"]})
        if v["hole_mil"] < MIN_BLIND_HOLE_MIL:
            bad_hole.append({"id": v["id"], "net": v["net"], "hole_mil": v["hole_mil"]})
        if v["ruleName"] not in ALLOWED_BLIND_RULES:
            bad_span.append({"id": v["id"], "net": v["net"], "ruleName": v["ruleName"]})

    bad_vv_cu = []
    bad_vv_hole = []
    vv_cu_gaps = []
    vv_hole_walls = []
    for i in range(len(all_vias)):
        va = all_vias[i]
        for j in range(i + 1, len(all_vias)):
            vb = all_vias[j]
            if va["viaType"] != "BLIND" and vb["viaType"] != "BLIND":
                continue
            if not (va["span"] & vb["span"]):
                continue
            d = math.hypot(va["x"] - vb["x"], va["y"] - vb["y"])
            cu_gap = round(d - 0.5 * (va["diam_mil"] + vb["diam_mil"]), 3)
            hole_wall = round(d - 0.5 * (va["hole_mil"] + vb["hole_mil"]), 3)
            vv_cu_gaps.append(cu_gap)
            vv_hole_walls.append(hole_wall)
            if cu_gap < MIN_BLIND_VV_CU_MIL:
                bad_vv_cu.append({
                    "a": va["id"], "b": vb["id"],
                    "a_net": va["net"], "b_net": vb["net"],
                    "a_rule": va["ruleName"] or va["viaType"],
                    "b_rule": vb["ruleName"] or vb["viaType"],
                    "cu_gap_mil": cu_gap,
                })
            if hole_wall < MIN_BLIND_VV_HOLE_WALL_MIL:
                bad_vv_hole.append({
                    "a": va["id"], "b": vb["id"],
                    "a_net": va["net"], "b_net": vb["net"],
                    "hole_wall_mil": hole_wall,
                })

    bad_mech = [v for v in all_vias if v["viaType"] != "BLIND" and (v["hole_mil"] < 5.95 or v["ring_mil"] < 2.95)]
    span_counts: dict[str, int] = {}
    for v in blinds:
        k = v["ruleName"] or "UNSPECIFIED"
        span_counts[k] = span_counts.get(k, 0) + 1

    base["extended_blind_via_manufacturing_audit_v3"] = {
        "total_blind_vias": len(blinds),
        "span_breakdown": span_counts,
        "thresholds_mil": {
            "min_cu_to_edge_mil": MIN_BLIND_EDGE_CU_MIL,
            "min_same_span_vv_cu_gap_mil": MIN_BLIND_VV_CU_MIL,
            "min_same_span_vv_hole_wall_mil": MIN_BLIND_VV_HOLE_WALL_MIL,
            "min_annular_ring_mil": MIN_BLIND_RING_MIL,
            "min_laser_hole_mil": MIN_BLIND_HOLE_MIL,
        },
        "measured_min_cu_to_edge_mil": round(min(edge_dists), 3) if edge_dists else 0.0,
        "measured_min_cu_to_edge_mm": round(min(edge_dists) * 0.0254, 4) if edge_dists else 0.0,
        "measured_min_same_span_vv_cu_gap_mil": round(min(vv_cu_gaps), 3) if vv_cu_gaps else 0.0,
        "measured_min_same_span_vv_cu_gap_mm": round(min(vv_cu_gaps) * 0.0254, 4) if vv_cu_gaps else 0.0,
        "measured_min_same_span_vv_hole_wall_mil": round(min(vv_hole_walls), 3) if vv_hole_walls else 0.0,
        "measured_min_same_span_vv_hole_wall_mm": round(min(vv_hole_walls) * 0.0254, 4) if vv_hole_walls else 0.0,
        "measured_min_ring_mil": round(min((v["ring_mil"] for v in blinds), default=0.0), 3),
        "measured_min_hole_mil": round(min((v["hole_mil"] for v in blinds), default=0.0), 3),
        "violations": {
            "edge_clearance_violations": len(bad_edge),
            "same_span_vv_cu_violations": len(bad_vv_cu),
            "same_span_vv_hole_wall_violations": len(bad_vv_hole),
            "under_annular_ring_violations": len(bad_ring),
            "under_hole_violations": len(bad_hole),
            "invalid_layer_span_violations": len(bad_span),
            "illegal_mech_through_violations": len(bad_mech),
            "total_v3_blind_via_violations": (
                len(bad_edge) + len(bad_vv_cu) + len(bad_vv_hole)
                + len(bad_ring) + len(bad_hole) + len(bad_span) + len(bad_mech)
            ),
        },
        "violation_details": {
            "edge": bad_edge[:20],
            "vv_cu": bad_vv_cu[:20],
            "vv_hole": bad_vv_hole[:20],
            "ring": bad_ring[:20],
            "hole": bad_hole[:20],
            "span": bad_span[:20],
        },
        "fab_governance_blocked_items": [
            "6L_0p80mm_1plus4plus1_HDI_stackup_and_controlled_impedance_fab_EQ",
            "11_VIPPO_copper_fill_cap_sites_fab_EQ",
            "PCB3_U11_0p35mm_WLCSP_Tier1_Advanced_HDI_2N2_fab_EQ",
            "ANT1_ANT2_keepout_and_JBD_optical_camera_MECR01_signoff",
        ],
    }

    if board == "PCB3":
        base["u11_wlcsp_95_audit"] = audit_u11_wlcsp_95(dump_path)
    return base


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epro", type=Path, required=True)
    p.add_argument("--dump-dir", type=Path, required=True)
    p.add_argument("--dump-suffix", default="-post.dump.json")
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()

    a.out_dir.mkdir(parents=True, exist_ok=True)
    arc = Archive(a.epro)
    full = {}
    for b in ("PCB1", "PCB2", "PCB3"):
        res = audit_board_v3(b, arc, a.dump_dir / f"{b}{a.dump_suffix}", a.out_dir / f"{b}-conflict-matrix.csv")
        full[b] = res
        print(f"\n=== {b} V3 EXTENDED BLIND-VIA & 3D HDI DFM AUDIT ===")
        print("  by_classification:", json.dumps(res["by_classification"], indent=2))
        print("  v3_blind_audit:", json.dumps(res["extended_blind_via_manufacturing_audit_v3"]["violations"], indent=2))
        v3 = res["extended_blind_via_manufacturing_audit_v3"]
        print(
            f"  mins: ring={v3['measured_min_ring_mil']}mil edge={v3['measured_min_cu_to_edge_mil']}mil "
            f"vv_cu={v3['measured_min_same_span_vv_cu_gap_mil']}mil vv_hole={v3['measured_min_same_span_vv_hole_wall_mil']}mil"
        )
        if b == "PCB3":
            u11 = res["u11_wlcsp_95_audit"]
            print(
                f"  PCB3 U11 WLCSP-95: total={u11['total_balls']} outer={u11['outer_perimeter_depth0_active']} "
                f"ring1={u11['ring1_depth1_active']} deep={u11['deep_inner_depth2plus_active']} nc={u11['nc_unassigned_balls']}"
            )
    (a.out_dir / "independent-dfm-v3-summary.json").write_text(
        json.dumps(full, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
