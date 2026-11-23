"""Evaluate three PCB3 U11 microvia alternatives without writing EDA data."""

import argparse
import json
import math
from pathlib import Path
import sys

import screen_escape as geo


MM = 0.0254
GUARD = 6.02
RING = 3
MASK_REGISTRATION_RESERVE = 0.5
BOARD_CU_EDGE = 0.35 / MM
MIN_HOLE_SAME = 0.13 / MM
MIN_HOLE_FOREIGN = 0.24 / MM
PCB = ("PCB", "1db01a36f669a47a")
L2 = 15
LAYERS = [1, 15, 16, 17, 18, 2]


def touching_spans(a, b):
    return set(a).intersection(b)


def hole_objects(records):
    spans = {"": LAYERS}
    blind = records["RULE", '["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
    for row in blind:
        a, b = sorted(LAYERS.index(row[field]) for field in ("staLayerId", "endLayerId"))
        spans[row["name"]] = LAYERS[a : b + 1]
    holes = []
    for (kind, identity), row in records.items():
        if kind == "VIA":
            holes.append((identity, row["netName"], (row["centerX"], row["centerY"]),
                          row["holeDiameter"]/2, spans[row["ruleName"]]))
    return holes


def point_inside(coords, point):
    x, y = point
    inside = False
    for (px, py), (qx, qy) in zip(coords, coords[1:] + coords[:1]):
        if (py > y) != (qy > y) and x < (qx-px)*(y-py)/(qy-py)+px:
            inside = not inside
    return inside


def plane_shapes(records):
    result = []
    for row in records["LAYER_FILL", '["LAYER_FILL",15]']["fill"]:
        if row["netName"] == "GND":
            paths = []
            for polygon in row["path"]:
                coordinates = [v for v in polygon if v != "L"]
                paths.append(list(zip(coordinates[::2], coordinates[1::2], strict=True)))
            result.append(paths)
    return result


def edge_to_shape(center, outline):
    return min(geo.point_to_segment(center, a, b) for a, b in zip(outline, outline[1:] + outline[:1]))


def ground_plane_margin(shapes, point):
    margins = []
    for shell, *cutouts in shapes:
        if not point_inside(shell, point) or any(point_inside(hole, point) for hole in cutouts):
            continue
        margins.append(min(edge_to_shape(point, poly) for poly in [shell, *cutouts]))
    return max(margins, default=-1)


def make(spot, drill, span, bounds, holes, net):
    pad_r = drill/2 + RING
    layer = span[1]
    foreign = geo.nearest(spot, spot, pad_r, bounds, net, 30)
    margins = [((math.dist(spot, center) - drill/2 - other_drill_r), identity,
                MIN_HOLE_SAME if other_net == net else MIN_HOLE_FOREIGN)
               for identity, other_net, center, other_drill_r, other_span in holes
               if touching_spans(span, other_span)]
    near = min(margins, key=lambda x: x[0]-x[2], default=(100, None, 0))
    edge_gap = min(spot[0], 204.7244-spot[0], spot[1], 1338.5827-spot[1]) - pad_r
    clear = foreign[0] >= GUARD and near[0] >= near[2] and edge_gap >= BOARD_CU_EDGE
    return {"point": spot, "board_edge_copper_gap_mil": round(edge_gap, 5), "layer_end_id": layer,
            "nearest_foreign_top_copper": foreign[1], "foreign_top_copper_gap_mil": round(foreign[0], 5),
            "critical_hole_wall_gap_mil": round(near[0], 5), "critical_hole_wall_candidate": near[1],
            "critical_hole_wall_min_mil": round(near[2], 5), "independent_nominal_screen": clear}


def dogbone(ball, masks, obstacles, holes, planes):
    center = ball["center"]
    net = ball["native_pcb_net"]
    drill = 0.1 / MM
    via_r = drill/2 + RING
    width = 4
    feasible = []
    # Lowest non-overlap with source pad requires a trace between the two lands.
    for step_x in range(-88, 89):
        for step_y in range(-88, 89):
            dx, dy = step_x/4, step_y/4
            length = math.hypot(dx, dy)
            if (length < ball["radius"] + via_r or length > 22):
                continue
            spot = center[0]+dx, center[1]+dy
            if any(math.dist(spot, other) < mask_r + drill/2 + MASK_REGISTRATION_RESERVE
                   for other, mask_r in masks if math.dist(center, other) < 42):
                continue
            if net == "GND" and ground_plane_margin(planes, spot) < via_r:
                continue
            top_pad_gap = geo.nearest(spot, spot, via_r, obstacles, net, GUARD)
            if top_pad_gap[0] < GUARD:
                continue
            route_gap = geo.nearest(center, spot, width/2, obstacles, net, 25)
            if route_gap[0] < GUARD:
                continue
            quality = make(spot, drill, (1, L2), obstacles, holes, net)
            if quality["independent_nominal_screen"]:
                quality["trace_foreign_gap_mil"] = round(route_gap[0], 5)
                quality["via_diameter_mil"] = 2*via_r
                feasible.append((length, quality))
    best = min(feasible, key=lambda row: row[0], default=None)
    return {"ball": ball["ball"], "net": net, "start": center, "candidate_count": len(feasible),
            "best": (best[1] if best else None), "diameter_drill_mm": 0.100,
            "length_mil": (round(best[0], 5) if best else None),
            "l2_completion": "overlaps existing L2 GND plane" if net == "GND"
            else "requires isolated L2 capture and L2/L3 routing study"}


def alternatives(ball, blocked, masks, objects, holes, planes):
    name = ball["ball"]
    net = ball["native_pcb_net"]
    origin = ball["center"]
    exotic = make(origin, 0.035/MM, (1, L2), objects, holes, net)
    exotic["existing_land_drill_annular_ring_mil"] = round(ball["radius"] - (0.035 / MM)/2, 5)
    exotic["mask_geometry_changed"] = False
    return {"ball": name, "net": net, "blocked_in_r4": name in blocked,
            "centered_35um_research": exotic,
            "external_100um_dogbone_research": dogbone(ball, masks, objects, holes, planes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r4", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.r4 / "u11"))
    sys.path.insert(0, str(args.r4))
    from audit_r3_u11 import load, records
    from verify_pcb1_spur import segment_distance, point_to_segment
    geo.load, geo.records = load, records
    geo.segment_distance, geo.point_to_segment = segment_distance, point_to_segment
    archive, = (args.r4 / "native").glob("*.epro2")
    balls, raw = geo.archive_copper(archive, args.r4 / "verification/pcb3-restore-copper.json",
                                   args.r4 / "u11/r3-u11-95ball-native.csv")
    raw.append(geo.Copper("R5_B2_C2", "line", "GND", (balls["B2"]["center"], balls["C2"]["center"]), 2))
    data = records(load(archive).documents[PCB])
    pads = records(load(archive).documents[("FOOTPRINT", "ddd711692e399705")])
    expansions = {r.get("solderMaskExpansion") for (k, _), r in pads.items() if k == "PAD"}
    board_mask = data["RULE", '["RULE","SOLDER","solderMaskExpansion"]']["ruleContext"]["padTopExpan"]
    if expansions != {None} or board_mask != 2:
        raise ValueError(f"Unexpected footprint or board soldermask: {expansions}, {board_mask}")
    masks = [(row["center"], row["radius"] + board_mask) for row in balls.values()]
    holes = hole_objects(data)
    plane = plane_shapes(data)
    bounds = [(obj, obj.bounds) for obj in raw]
    ref = json.loads((args.r4 / "u11/r3-u11-native-audit.json").read_bytes())
    blocked = set(ref["inner_balls_failing_locked_6mil_clearance_with_0p2274mm_centered_via"])
    rows = [alternatives(row, blocked, masks, bounds, holes, plane) for row in balls.values()
            if row["ball"] in blocked or row["ball"] in ("A5","B12","K1","L5")]
    labels = ("centered_35um_research","external_100um_dogbone_research")
    result = {"scope": "Alternative copper geometry offline. No native edits. Ø35 µm is below inherited process "
                        "minimum. Process-specific PCB variant and written EQ would be required. Nominal hole wall "
                        "limits apply same-layer or intersecting spans. Dogbone uses unchanged U11 mask and paste.",
              "source_routes_stage": "R4 plus R5 B2–C2 top copper",
              "u11_top_soldermask_expansion_mil": board_mask,
              "board_radii_raw": data["RULE", '["RULE","RADIUS","viaSize"]']["ruleContext"],
              "prior_blocked_balls": 25,
              "centered_35um_individually_nominal_pass_count_of_25": sum(row["blocked_in_r4"]
                    and row[labels[0]]["independent_nominal_screen"] for row in rows),
              "dogbone_100um_individually_nominal_pass_count_of_25": sum(row["blocked_in_r4"]
                    and bool(row[labels[1]]["candidate_count"]) for row in rows),
              "rows": rows}
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print("35um", [r["ball"] for r in rows if r["centered_35um_research"]["independent_nominal_screen"]])
    for r in rows:
        if r["external_100um_dogbone_research"]["candidate_count"]:
            print(r["ball"], r["external_100um_dogbone_research"])


if __name__ == "__main__":
    main()
