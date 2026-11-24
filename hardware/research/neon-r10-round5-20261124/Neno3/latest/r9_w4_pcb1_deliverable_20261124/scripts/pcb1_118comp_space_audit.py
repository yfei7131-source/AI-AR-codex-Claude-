#!/usr/bin/env python3
"""Reproducible PCB1 (118 components) 2D collision & clearance audit against R9 PCB1-copper.json."""
import json, sys

MIL2MM = 0.0254
EDGE_CLEAR_MM = 10.0 * MIL2MM
CLR_MM = 6.0 * MIL2MM

def rect_inside_pcb1(x0, y0, x1, y1, margin=EDGE_CLEAR_MM):
    if x0 < margin or y0 < margin or y1 > 46.0 - margin:
        return False
    if y0 >= 4.2 + margin and y1 <= 14.0 - margin:
        return x1 <= 8.20 - margin
    return x1 <= 5.80 - margin

def check_box(copper, x0, y0, x1, y1, layer):
    if not rect_inside_pcb1(x0, y0, x1, y1):
        return ["OUT_OF_BOARD"]
    hits = []
    for c in copper["components"]:
        if c["layer"] != layer: continue
        bb = c["bbox"]
        if not (x1 + CLR_MM <= bb["minX"]*MIL2MM or x0 - CLR_MM >= bb["maxX"]*MIL2MM or
                y1 + CLR_MM <= bb["minY"]*MIL2MM or y0 - CLR_MM >= bb["maxY"]*MIL2MM):
            hits.append(f"COMP:{c['designator']}")
    for v in copper["copper"]["vias"]:
        vx, vy, vr = v["x"]*MIL2MM, v["y"]*MIL2MM, (v.get("diameter",15.75)/2)*MIL2MM
        if not (x1 + CLR_MM <= vx - vr or x0 - CLR_MM >= vx + vr or y1 + CLR_MM <= vy - vr or y0 - CLR_MM >= vy + vr):
            hits.append(f"VIA:{v['net']}")
    for l in copper["copper"]["lines"]:
        if l["layer"] != layer: continue
        lx0, lx1 = min(l["startX"],l["endX"])*MIL2MM, max(l["startX"],l["endX"])*MIL2MM
        ly0, ly1 = min(l["startY"],l["endY"])*MIL2MM, max(l["startY"],l["endY"])*MIL2MM
        hw = (l.get("lineWidth",3.5)/2)*MIL2MM
        if not (x1 + CLR_MM <= lx0 - hw or x0 - CLR_MM >= lx1 + hw or y1 + CLR_MM <= ly0 - hw or y0 - CLR_MM >= ly1 + hw):
            hits.append(f"LINE:{l['net']}")
    return hits

if __name__ == "__main__":
    copper_path = sys.argv[1]
    copper = json.load(open(copper_path, encoding="utf-8"))
    assert len(copper["components"]) == 118, f"Expected 118 components, got {len(copper['components'])}"
    checks = {
        "J3_Opt1_Solo_L1": check_box(copper, 1.795, 38.370, 4.005, 43.830, 1),
        "Joint_J2_L1": check_box(copper, 0.800, 36.600, 2.700, 43.400, 1),
        "Joint_J3_Opt1_L1": check_box(copper, 3.330, 38.000, 5.540, 43.460, 1),
        "Joint_J2_Alt_L1": check_box(copper, 2.450, 36.300, 4.350, 43.100, 1),
        "Joint_J3_Opt2_L1": check_box(copper, 1.650, 43.650, 5.450, 45.650, 1),
    }
    print(json.dumps({"component_count": len(copper["components"]), "checks": checks, "all_pass": all(len(v)==0 for v in checks.values())}, indent=2))
