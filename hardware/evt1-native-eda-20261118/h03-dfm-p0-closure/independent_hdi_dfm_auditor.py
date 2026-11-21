#!/usr/bin/env python3
"""Untruncated, 3D layer-span-aware (BV_L1_L2 / BV_L5_L6) independent HDI DFM auditor & conflict classifier.

Reads the native .epro2 directly (no 40-item truncation, no blind-via Z-blindness) and reproduces BOTH:
  - 2D blind-unaware clearance counts (explaining easyeda `pcb check`'s 184 / 103 / 78 clearance items), AND
  - 3D Z-layer-exact physical conflict classification across every single primitive pair on PCB1, PCB2, PCB3:
      1. TRUE_PHYSICAL_VIOLATION       (real copper violation on shared Z-layer under locked rules / <3.0 mil HDI)
      2. RULE_THRESHOLD_DIFF_3_TO_6MIL (same-layer track-track 3.0..5.99 mil: passes native DRC & 6L HDI >=3.0 mil, fails pcb-check hardcoded 6 mil)
      3. BLIND_VIA_Z_FALSE_POSITIVE    (easyeda pcb-check bug: treats BV_L1_L2/BV_L5_L6 blind microvias as 6-layer through-vias!)
      4. VIA_IN_PAD_REAL_SMD_EDGE      (same-layer via touching non-BGA/non-EPAD SMD pad -> real reflow solder-wicking/tombstoning risk!)
      5. VIA_IN_PAD_INTENTIONAL_VIPPO  (intentional U2 BGA / U1 EPAD thermal VIPPO)
      6. VIA_IN_PAD_OPPOSITE_BLIND_FP  (easyeda pcb-check bug: BV_L1_L2 under a BOT pad or BV_L5_L6 under a TOP pad!)
"""

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native")]
from prepare_hierarchy import Archive

DOCS = {"PCB1": "8fbc3cae65886fe5", "PCB2": "9ce45f14cb79dc9d", "PCB3": "1db01a36f669a47a"}
ALL_COPPER_LAYERS = {1, 15, 16, 17, 18, 2}


def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> float:
    # Check intersection first
    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
    A, B, C, D = (ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2)
    d1, d2 = ccw(A, B, C), ccw(A, B, D)
    d3, d4 = ccw(C, D, A), ccw(C, D, B)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return 0.0
    return min(
        pt_seg_dist(ax1, ay1, bx1, by1, bx2, by2),
        pt_seg_dist(ax2, ay2, bx1, by1, bx2, by2),
        pt_seg_dist(bx1, by1, ax1, ay1, ax2, ay2),
        pt_seg_dist(bx2, by2, ax1, ay1, ax2, ay2),
    )


def via_copper_layers(vtype: str, rule_name: str, blind_spans: dict[str, set[int]]) -> set[int]:
    if vtype == "BLIND" and rule_name in blind_spans:
        return blind_spans[rule_name]
    return set(ALL_COPPER_LAYERS)


def extract_board_objects(arc: Archive, pcb_uid: str, dump_path: Path):
    doc = arc.documents[("PCB", pcb_uid)]
    # Read blind-via layer spans from RULE[BLIND]
    blind_spans = {}
    for r in doc.records:
        if r.header["type"] == "RULE" and r.header["id"] == '["RULE","BLIND","blindVia"]':
            for item in r.payload.get("ruleContext", {}).get("blinds", {}).get("content", []):
                s, e = int(item["staLayerId"]), int(item["endLayerId"])
                order = [1, 15, 16, 17, 18, 2]
                i0, i1 = sorted((order.index(s), order.index(e)))
                blind_spans[item["name"]] = set(order[i0:i1 + 1])

    # Read vias with true viaType & ruleName from .epcb
    vias = []
    for r in doc.records:
        if r.header["type"] == "VIA":
            p = r.payload
            vt = p.get("viaType", "NORMAL")
            rn = p.get("ruleName", "")
            vias.append({
                "id": r.header["id"],
                "x": float(p["centerX"]),
                "y": float(p["centerY"]),
                "hole": float(p["holeDiameter"]),
                "dia": float(p["viaDiameter"]),
                "r": 0.5 * float(p["viaDiameter"]),
                "net": p.get("netName", ""),
                "viaType": vt,
                "ruleName": rn,
                "layers": via_copper_layers(vt, rn, blind_spans),
            })

    # Read tracks from .epcb (non-degenerate >= 0.1 mil)
    tracks = []
    for r in doc.records:
        if r.header["type"] == "LINE":
            p = r.payload
            x1, y1, x2, y2 = float(p["startX"]), float(p["startY"]), float(p["endX"]), float(p["endY"])
            if math.hypot(x2 - x1, y2 - y1) < 0.1:
                continue
            tracks.append({
                "id": r.header["id"],
                "layer": int(p["layerId"]),
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "w": float(p.get("width", p.get("lineWidth", 0))),
                "net": p.get("netName", ""),
            })

    # Read pads with exact world coordinates from dump
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    pads = []
    for c in dump["components"]:
        ref, cx, cy = c["designator"], float(c["x"]), float(c["y"])
        c_rot = float(c.get("rotation") or 0.0)
        for p in c.get("pads", []):
            pw, ph = float(p.get("width") or 0.0), float(p.get("height") or 0.0)
            if pw < 1.0 or ph < 1.0:
                shp = p.get("shape") or []
                if isinstance(shp, list) and len(shp) >= 2 and shp[0] == "POLY" and isinstance(shp[1], list):
                    nums = [float(v) for v in shp[1] if isinstance(v, (int, float))]
                    if len(nums) >= 4:
                        pw = max(pw, max(nums[0::2]) - min(nums[0::2]))
                        ph = max(ph, max(nums[1::2]) - min(nums[1::2]))
            rot = c_rot + float(p.get("rotation") or 0.0)
            rad = math.radians(rot)
            ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
            hw = 0.5 * (pw * ca + ph * sa)
            hh = 0.5 * (pw * sa + ph * ca)
            pads.append({
                "id": p.get("primitiveId", f"{ref}.{p.get('padNumber')}"),
                "ref": ref,
                "pnum": str(p.get("padNumber", "")),
                "x": float(p["x"]), "y": float(p["y"]),
                "hw": hw, "hh": hh,
                "layer": int(p.get("layer", c["layer"])),
                "net": p.get("net") or "",
            })
    return blind_spans, vias, tracks, pads


def audit_board(board: str, arc: Archive, dump_path: Path, out_csv: Path | None = None) -> dict:
    blind_spans, vias, tracks, pads = extract_board_objects(arc, DOCS[board], dump_path)
    rows = []

    # 1. Track-to-Via (different net) — reproduces BOTH 2D blind-unaware (<6mil) and 3D Z-exact!
    for t in tracks:
        for v in vias:
            if t["net"] == v["net"]:
                continue
            gap = pt_seg_dist(v["x"], v["y"], t["x1"], t["y1"], t["x2"], t["y2"]) - v["r"] - 0.5 * t["w"]
            if gap < 6.0:
                shares_z = (t["layer"] in v["layers"])
                cls = "TRUE_PHYSICAL_VIOLATION" if shares_z else "CHECKER_FP_BLIND_VIA_CROSS_LAYER"
                rows.append({
                    "board": board, "pair_type": "Track-to-Via", "classification": cls,
                    "obj1": f"track:{t['id']}(L{t['layer']},{t['net']},w={t['w']})",
                    "obj2": f"via:{v['id']}({v['viaType']}:{v['ruleName'] or 'THRU'},{v['net']},{v['hole']}/{v['dia']})",
                    "gap_mil": round(max(0.0, gap), 2), "shares_z_layer": shares_z,
                    "x": round(v["x"], 2), "y": round(v["y"], 2),
                })

    # 2. Track-to-Track (different net, same layer, < 6.0 mil)
    for i in range(len(tracks)):
        a = tracks[i]
        for j in range(i + 1, len(tracks)):
            b = tracks[j]
            if a["layer"] != b["layer"] or a["net"] == b["net"]:
                continue
            # fast bbox reject
            if (max(a["x1"], a["x2"]) + 12 < min(b["x1"], b["x2"]) or
                max(b["x1"], b["x2"]) + 12 < min(a["x1"], a["x2"]) or
                max(a["y1"], a["y2"]) + 12 < min(b["y1"], b["y2"]) or
                max(b["y1"], b["y2"]) + 12 < min(a["y1"], a["y2"])):
                continue
            gap = seg_seg_dist(a["x1"], a["y1"], a["x2"], a["y2"], b["x1"], b["y1"], b["x2"], b["y2"]) - 0.5 * (a["w"] + b["w"])
            if gap < 6.0:
                cls = "TRUE_PHYSICAL_VIOLATION" if gap < 3.0 else "RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK"
                rows.append({
                    "board": board, "pair_type": "Track-to-Track", "classification": cls,
                    "obj1": f"track:{a['id']}(L{a['layer']},{a['net']},w={a['w']})",
                    "obj2": f"track:{b['id']}(L{b['layer']},{b['net']},w={b['w']})",
                    "gap_mil": round(max(0.0, gap), 2), "shares_z_layer": True,
                    "x": round(0.5 * (a["x1"] + b["x1"]), 2), "y": round(0.5 * (a["y1"] + b["y1"]), 2),
                })

    # 3. Via-to-Via (different net OR overlapping same-net)
    for i in range(len(vias)):
        a = vias[i]
        for j in range(i + 1, len(vias)):
            b = vias[j]
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            gap = d - a["r"] - b["r"]
            shares_z = bool(a["layers"] & b["layers"])
            if a["net"] != b["net"] and gap < 6.0:
                cls = "TRUE_PHYSICAL_VIOLATION" if shares_z else "CHECKER_FP_BLIND_VIA_CROSS_LAYER"
                rows.append({
                    "board": board, "pair_type": "Via-to-Via(DiffNet)", "classification": cls,
                    "obj1": f"via:{a['id']}({a['viaType']}:{a['ruleName'] or 'THRU'},{a['net']})",
                    "obj2": f"via:{b['id']}({b['viaType']}:{b['ruleName'] or 'THRU'},{b['net']})",
                    "gap_mil": round(max(0.0, gap), 2), "shares_z_layer": shares_z,
                    "x": round(a["x"], 2), "y": round(a["y"], 2),
                })
            elif a["net"] == b["net"] and d < 0.5 * (a["dia"] + b["dia"]):
                cls = "TRUE_OVERLAPPING_VIA_SAME_SPAN" if shares_z else "CHECKER_FP_OPPOSITE_BLIND_VIAS_L1L2_VS_L5L6"
                rows.append({
                    "board": board, "pair_type": "Overlapping-Via(SameNet)", "classification": cls,
                    "obj1": f"via:{a['id']}({a['viaType']}:{a['ruleName'] or 'THRU'},{a['net']})",
                    "obj2": f"via:{b['id']}({b['viaType']}:{b['ruleName'] or 'THRU'},{b['net']})",
                    "gap_mil": round(d, 2), "shares_z_layer": shares_z,
                    "x": round(a["x"], 2), "y": round(a["y"], 2),
                })

    # 4. Via-to-Pad (different net < 6.0 mil AND same-net via-in-pad audit!)
    for v in vias:
        for p in pads:
            dx = max(0.0, abs(v["x"] - p["x"]) - p["hw"])
            dy = max(0.0, abs(v["y"] - p["y"]) - p["hh"])
            gap = math.hypot(dx, dy) - v["r"]
            shares_z = (p["layer"] in v["layers"])
            if p["net"] != v["net"] and gap < 6.0:
                cls = "TRUE_PHYSICAL_VIOLATION" if shares_z else "CHECKER_FP_BLIND_VIA_CROSS_LAYER"
                rows.append({
                    "board": board, "pair_type": "Via-to-Pad(DiffNet)", "classification": cls,
                    "obj1": f"via:{v['id']}({v['viaType']}:{v['ruleName'] or 'THRU'},{v['net']})",
                    "obj2": f"pad:{p['ref']}.{p['pnum']}(L{p['layer']},{p['net']})",
                    "gap_mil": round(max(0.0, gap), 2), "shares_z_layer": shares_z,
                    "x": round(v["x"], 2), "y": round(v["y"], 2),
                })
            elif p["net"] == v["net"] and gap < 0.0:
                if not shares_z:
                    cls = "CHECKER_FP_VIA_IN_PAD_OPPOSITE_BLIND"
                elif (board == "PCB2" and p["ref"] == "U2") or (board == "PCB1" and p["ref"] == "U1"):
                    cls = "INTENTIONAL_VIPPO_BGA_OR_EPAD"
                else:
                    cls = "REAL_DFM_VIA_TOUCHES_SMD_PAD"
                rows.append({
                    "board": board, "pair_type": "Via-in-Pad(SameNet)", "classification": cls,
                    "obj1": f"via:{v['id']}({v['viaType']}:{v['ruleName'] or 'THRU'},{v['net']})",
                    "obj2": f"pad:{p['ref']}.{p['pnum']}(L{p['layer']},{p['net']})",
                    "gap_mil": round(gap, 2), "shares_z_layer": shares_z,
                    "x": round(v["x"], 2), "y": round(v["y"], 2),
                })

    # 5. Track-to-Pad (different net, same layer, < 6.0 mil)
    for t in tracks:
        if t["layer"] not in (1, 2):
            continue
        for p in pads:
            if p["layer"] != t["layer"] or p["net"] == t["net"]:
                continue
            # conservative check using pad center-to-segment minus bounding radius, then exact sampled distance
            if pt_seg_dist(p["x"], p["y"], t["x1"], t["y1"], t["x2"], t["y2"]) > math.hypot(p["hw"], p["hh"]) + 0.5 * t["w"] + 6.5:
                continue
            steps = max(4, int(math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) / 1.0) + 1)
            min_g = 1e9
            for s in range(steps + 1):
                u = s / steps
                cx, cy = t["x1"] + u * (t["x2"] - t["x1"]), t["y1"] + u * (t["y2"] - t["y1"])
                dx = max(0.0, abs(cx - p["x"]) - p["hw"])
                dy = max(0.0, abs(cy - p["y"]) - p["hh"])
                g = math.hypot(dx, dy) - 0.5 * t["w"]
                if g < min_g:
                    min_g = g
            if min_g < 5.95:
                rows.append({
                    "board": board, "pair_type": "Track-to-Pad(DiffNet)", "classification": "TRUE_PHYSICAL_VIOLATION",
                    "obj1": f"track:{t['id']}(L{t['layer']},{t['net']},w={t['w']})",
                    "obj2": f"pad:{p['ref']}.{p['pnum']}(L{p['layer']},{p['net']})",
                    "gap_mil": round(max(0.0, min_g), 2), "shares_z_layer": True,
                    "x": round(p["x"], 2), "y": round(p["y"], 2),
                })

    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        cols = ["board", "pair_type", "classification", "obj1", "obj2", "gap_mil", "shares_z_layer", "x", "y"]
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    summary = Counter((r["pair_type"], r["classification"]) for r in rows)
    by_cls = Counter(r["classification"] for r in rows)
    return {
        "board": board,
        "tracks": len(tracks),
        "vias": len(vias),
        "pads": len(pads),
        "blind_spans": {k: sorted(v) for k, v in blind_spans.items()},
        "total_matrix_rows": len(rows),
        "by_classification": dict(by_cls),
        "by_pair_and_class": {f"{k[0]} | {k[1]}": v for k, v in sorted(summary.items())},
        "sample_true_violations": [r for r in rows if r["classification"] == "TRUE_PHYSICAL_VIOLATION"][:15],
        "sample_rule_diff_3_to_6": [r for r in rows if r["classification"] == "RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK"][:10],
        "sample_blind_fp": [r for r in rows if r["classification"] == "CHECKER_FP_BLIND_VIA_CROSS_LAYER"][:10],
    }


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
        res = audit_board(b, arc, a.dump_dir / f"{b}{a.dump_suffix}", a.out_dir / f"{b}-conflict-matrix.csv")
        full[b] = res
        print(f"\n=== {b} UNTRUNCATED 3D HDI DFM AUDIT ===")
        print("  by_classification:", json.dumps(res["by_classification"], indent=2))
        print("  by_pair_and_class:", json.dumps(res["by_pair_and_class"], indent=2))
        if res["sample_true_violations"]:
            print("  TRUE VIOLATIONS:", json.dumps(res["sample_true_violations"][:5], indent=2))
    (a.out_dir / "independent-dfm-summary.json").write_text(json.dumps(full, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
