#!/usr/bin/env python3
"""
Independent Verification & Regression Audit Script for H03 R10 PCB3 Offline Real-Data Delta.
Reads untouched R9 baseline (PCB3-copper.json, PCB3-drc.json) + r10_pcb3_executable_delta.json
and independently verifies:
  1. Component count == 53, board width == 5.2000 mm (204.7244 mil), baseline DRC == 129
  2. All 7 relocated components (U10, R6, R10, C3, R2, R3, R4):
     - 0 envelope collisions against all 53 components (with >= 6.0 mil courtyard gap)
     - 0.0000 mil pad/anchor coordinate mismatch
     - 0 board edge overhang
     - 0 double-sided U10/U11 overlap
  3. All new vias and track segments:
     - Trace width >= 4.0 mil
     - Copper-to-copper clearance >= 6.0 mil (>= 12.0 mil to NRF_DECR_RF)
     - Hole-to-hole wall >= 11.8 mil
     - Via pad edge to board edge >= 13.78 mil (0.35 mm)
     - Trace edge to board edge >= 11.85 mil (0.301 mm)
     - RF keepout Y <= 157.5803 mil strictly respected
"""

import json
import math
import sys

BASE_DIR = "/working_dir/c_67c857d48fac11e1/artifacts/file_generation/ttl=63d/intermediate/r9_pcb3_unpacked"
DELIVERY_DIR = "/working_dir/c_67c857d48fac11e1/artifacts/file_generation/ttl=63d/intermediate/r10_pcb3_delivery"


def pt_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) > (p2[1] - p1[1]) * (p3[0] - p1[0])
    A, B, C, D = (ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2)
    if ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D):
        return 0.0
    return min(
        pt_seg_dist(ax1, ay1, bx1, by1, bx2, by2),
        pt_seg_dist(ax2, ay2, bx1, by1, bx2, by2),
        pt_seg_dist(bx1, by1, ax1, ay1, ax2, ay2),
        pt_seg_dist(bx2, by2, ax1, ay1, ax2, ay2),
    )


def pt_rect_dist(px, py, cx, cy, w, h):
    dx = max(abs(px - cx) - w / 2.0, 0.0)
    dy = max(abs(py - cy) - h / 2.0, 0.0)
    return math.hypot(dx, dy)


def seg_pad_dist(x1, y1, x2, y2, pad):
    cx, cy, w, h = pad["x"], pad["y"], pad["width"], pad["height"]
    if isinstance(pad.get("shape"), list) and pad["shape"][0] == "ELLIPSE":
        return max(0.0, pt_seg_dist(cx, cy, x1, y1, x2, y2) - max(w, h) / 2.0)
    rx1, rx2, ry1, ry2 = cx - w / 2.0, cx + w / 2.0, cy - h / 2.0, cy + h / 2.0
    if (rx1 <= x1 <= rx2 and ry1 <= y1 <= ry2) or (rx1 <= x2 <= rx2 and ry1 <= y2 <= ry2):
        return 0.0
    return min(
        seg_seg_dist(x1, y1, x2, y2, rx1, ry1, rx2, ry1),
        seg_seg_dist(x1, y1, x2, y2, rx2, ry1, rx2, ry2),
        seg_seg_dist(x1, y1, x2, y2, rx2, ry2, rx1, ry2),
        seg_seg_dist(x1, y1, x2, y2, rx1, ry2, rx1, ry1),
    )


def main():
    cop = json.load(open(f"{BASE_DIR}/PCB3-copper.json"))
    drc = json.load(open(f"{BASE_DIR}/PCB3-drc.json"))
    delta = json.load(open(f"{DELIVERY_DIR}/r10_pcb3_executable_delta.json"))

    assert len(cop["components"]) == 53, "Component count mismatch"
    assert drc["total"] == 129, "Baseline DRC mismatch"

    BOARD_W, BOARD_H, RF_MAX_Y = 204.7244, 1338.5827, 157.5803
    reloc_map = {r["designator"]: r for r in delta["relocations"]}
    orig_comps = {c["designator"]: c for c in cop["components"]}

    # Reconstruct post-R10 components and verify 0 pad/anchor mismatch
    post_comps = []
    for c in cop["components"]:
        des = c["designator"]
        if des in reloc_map:
            r = reloc_map[des]
            dx = r["r10_xy_mil"][0] - c["x"]
            dy = r["r10_xy_mil"][1] - c["y"]
            nc = json.loads(json.dumps(c))
            nc["x"], nc["y"] = r["r10_xy_mil"]
            nc["bbox"] = r["r10_bbox_mil"]
            for p, rp in zip(nc["pads"], r["r10_pads"]):
                exp_x, exp_y = round(p["x"] + dx, 4), round(p["y"] + dy, 4)
                assert abs(exp_x - rp["x"]) < 1e-3 and abs(exp_y - rp["y"]) < 1e-3, f"Pad mismatch on {des}.{p['padNumber']}"
                p["x"], p["y"] = rp["x"], rp["y"]
            post_comps.append(nc)
        else:
            post_comps.append(c)

    # Check 0 envelope collisions & 0 edge overhang for all relocated parts
    for des in reloc_map:
        nc = [c for c in post_comps if c["designator"] == des][0]
        b = nc["bbox"]
        assert b["minX"] >= 13.78 and b["maxX"] <= BOARD_W - 13.78, f"Edge X fail {des}"
        assert b["minY"] >= RF_MAX_Y + 10.0 and b["maxY"] <= BOARD_H - 13.78, f"Edge Y fail {des}"
        for oc in post_comps:
            if oc["designator"] == des or oc["layer"] != nc["layer"]:
                continue
            ob = oc["bbox"]
            overlap = not (b["maxX"] + 6.0 <= ob["minX"] or b["minX"] - 6.0 >= ob["maxX"] or b["maxY"] + 6.0 <= ob["minY"] or b["minY"] - 6.0 >= ob["maxY"])
            assert not overlap, f"Collision {des} vs {oc['designator']}"

    # Check U10 vs U11 double-sided overlap
    u10b = [c for c in post_comps if c["designator"] == "U10"][0]["bbox"]
    u11b = [c for c in post_comps if c["designator"] == "U11"][0]["bbox"]
    assert u10b["minY"] > u11b["maxY"], "U10/U11 double-sided overlap detected"

    # Normalize all pads
    all_pads = []
    for c in post_comps:
        for p in c["pads"]:
            rec = dict(p)
            if "width" not in rec or rec["width"] is None:
                nums = [v for v in rec["shape"][1] if isinstance(v, (int, float))]
                xs, ys = nums[0::2], nums[1::2]
                rec["x"], rec["y"] = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
                rec["width"], rec["height"] = max(xs) - min(xs), max(ys) - min(ys)
            rec["compLayer"] = c["layer"]
            rec["key"] = f"{c['designator']}.{p['padNumber']}"
            all_pads.append(rec)

    detached = set(delta["detached_legacy_u10_lines"])
    orig_lines = [l for l in cop["copper"]["lines"] if l["primitiveId"] not in detached]
    orig_vias = cop["copper"]["vias"]
    new_vias = delta["new_vias"]
    new_lines = delta["new_lines"]

    violations = []
    min_clr_obs = 999.0
    min_wall_obs = 999.0
    min_via_edge_obs = 999.0
    min_tr_edge_obs = 999.0

    for i, v in enumerate(new_vias):
        r, hr = v["diameter"] / 2.0, v["holeDiameter"] / 2.0
        ed = min(v["x"] - r, BOARD_W - (v["x"] + r), v["y"] - r - RF_MAX_Y, BOARD_H - (v["y"] + r))
        min_via_edge_obs = min(min_via_edge_obs, min(v["x"] - r, BOARD_W - (v["x"] + r), BOARD_H - (v["y"] + r)))
        if v["x"] - r < 13.78 or v["x"] + r > BOARD_W - 13.78 or v["y"] - r < RF_MAX_Y or v["y"] + r > BOARD_H - 13.78:
            violations.append(f"VIA_EDGE {v['primitiveId']}")
        for ov in orig_vias + new_vias[:i]:
            dist = math.hypot(v["x"] - ov["x"], v["y"] - ov["y"])
            wall = dist - (hr + ov["holeDiameter"] / 2.0)
            min_wall_obs = min(min_wall_obs, wall)
            if wall < 11.8 - 1e-6:
                violations.append(f"VIA_WALL {v['primitiveId']} vs {ov['primitiveId']} ({wall:.2f})")
            if v["net"] != ov["net"]:
                c = dist - (r + ov["diameter"] / 2.0)
                min_clr_obs = min(min_clr_obs, c)
                req = 12.0 if ("NRF_DECR_RF" in (v["net"], ov["net"])) else 6.0
                if c < req - 1e-6:
                    violations.append(f"VIA_VIA_CLR {v['primitiveId']} vs {ov['primitiveId']} ({c:.2f})")
        for p in all_pads:
            if p["net"] == v["net"] or (v["net"] == "I2S_BCLK_1V8" and p["key"] == "U11.L9"):
                continue
            c = pt_rect_dist(v["x"], v["y"], p["x"], p["y"], p["width"], p["height"]) - r
            min_clr_obs = min(min_clr_obs, c)
            req = 12.0 if ("NRF_DECR_RF" in (v["net"], p["net"])) else 6.0
            if c < req - 1e-6:
                violations.append(f"VIA_PAD_CLR {v['primitiveId']} vs {p['key']} ({c:.2f})")

    for i, l in enumerate(new_lines):
        hw = l["lineWidth"] / 2.0
        if l["lineWidth"] < 4.0 - 1e-6:
            violations.append(f"TRACE_WIDTH {l['primitiveId']}")
        te = min(min(l["startX"], l["endX"]) - hw, BOARD_W - (max(l["startX"], l["endX"]) + hw), BOARD_H - (max(l["startY"], l["endY"]) + hw))
        min_tr_edge_obs = min(min_tr_edge_obs, te)
        if te < 11.85 - 1e-6 or min(l["startY"], l["endY"]) - hw < RF_MAX_Y:
            violations.append(f"TRACE_EDGE {l['primitiveId']} ({te:.2f})")
        if l["layer"] in (1, 2):
            for p in all_pads:
                if p["compLayer"] != l["layer"] or p["net"] == l["net"] or (l["net"] == "I2S_BCLK_1V8" and p["key"] == "U11.L9"):
                    continue
                c = seg_pad_dist(l["startX"], l["startY"], l["endX"], l["endY"], p) - hw
                min_clr_obs = min(min_clr_obs, c)
                req = 12.0 if ("NRF_DECR_RF" in (l["net"], p["net"])) else 6.0
                if c < req - 1e-6:
                    violations.append(f"LINE_PAD_CLR {l['primitiveId']} vs {p['key']} ({c:.2f})")
        for v in orig_vias + new_vias:
            if v["net"] == l["net"]:
                continue
            c = pt_seg_dist(v["x"], v["y"], l["startX"], l["startY"], l["endX"], l["endY"]) - (hw + v["diameter"] / 2.0)
            min_clr_obs = min(min_clr_obs, c)
            req = 12.0 if ("NRF_DECR_RF" in (l["net"], v["net"])) else 6.0
            if c < req - 1e-6:
                violations.append(f"LINE_VIA_CLR {l['primitiveId']} vs {v['primitiveId']} ({c:.2f})")
        for ol in orig_lines + new_lines[:i]:
            if ol["layer"] != l["layer"] or ol["net"] == l["net"]:
                continue
            c = seg_seg_dist(l["startX"], l["startY"], l["endX"], l["endY"], ol["startX"], ol["startY"], ol["endX"], ol["endY"]) - (hw + ol["lineWidth"] / 2.0)
            min_clr_obs = min(min_clr_obs, c)
            req = 12.0 if ("NRF_DECR_RF" in (l["net"], ol["net"])) else 6.0
            if c < req - 1e-6:
                violations.append(f"LINE_LINE_CLR {l['primitiveId']} vs {ol['primitiveId']} ({c:.2f})")

    report = [
        "=== H03 R10 PCB3 INDEPENDENT OFFLINE REAL-DATA AUDIT ===",
        f"Baseline: PR #60 (a825953) | Components: {len(cop['components'])} | R9 DRC: {drc['total']} Connection Errors",
        f"Board Outline: {BOARD_W:.4f} x {BOARD_H:.4f} mil (5.2000 x 34.0000 mm) [LOCKED]",
        f"Relocated Components Verified: {len(reloc_map)} ({', '.join(reloc_map.keys())}) -> 0 envelope collisions, 0.0000 mil pad/anchor mismatch, 0 U10/U11 overlap",
        f"New Vias Verified: {len(new_vias)} | New Track Segments Verified: {len(new_lines)}",
        f"Observed Minimum Copper Clearance   : {min_clr_obs:.2f} mil (Locked >= 6.00 mil)",
        f"Observed Minimum Via Hole Wall      : {min_wall_obs:.2f} mil (Locked >= 11.80 mil)",
        f"Observed Minimum Via Pad to Edge    : {min_via_edge_obs:.2f} mil (Locked >= 13.78 mil)",
        f"Observed Minimum Trace Edge to Edge : {min_tr_edge_obs:.2f} mil (Locked >= 11.85 mil)",
        f"Total Offline Geometric Violations  : {len(violations)}",
        f"Projected DRC Connection Errors     : 129 -> {delta['meta']['projected_drc_connection_errors_eco1']} (ECO-1 K5->L9, Delta -14) | 129 -> {delta['meta']['projected_drc_connection_errors_no_eco']} (No ECO, Delta -12)",
        "Verification Boundary: OFFLINE REAL-DATA AUDIT ONLY (NOT native EasyEDA Pro DRC; local .epro2 import blocked by browser admin policy).",
        "Release Gate: NOT FOR FAB.",
    ]
    out_text = "\n".join(report) + "\n"
    print(out_text)
    with open(f"{DELIVERY_DIR}/r10_pcb3_offline_drc_audit.log", "w") as f:
        f.write(out_text)
    assert len(violations) == 0, f"Audit failed with {len(violations)} violations: {violations[:10]}"


if __name__ == "__main__":
    main()
