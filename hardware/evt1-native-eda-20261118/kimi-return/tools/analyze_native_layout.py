#!/usr/bin/env python3
"""Independent geometric audit of a fresh native PCB dump, without editing it."""
from pathlib import Path
import argparse
import itertools
import json
import math

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "layout/candidate-placement-plan.json"
MM = 39.37007874015748


def inside(point, polygon):
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            result = not result
    return result


def gap(a, b):
    dx = max(a["minX"] - b["maxX"], b["minX"] - a["maxX"], 0)
    dy = max(a["minY"] - b["maxY"], b["minY"] - a["maxY"], 0)
    return math.hypot(dx, dy)


def bbox_mm(component):
    return {k: component["bbox"][k] / MM for k in ("minX", "maxX", "minY", "maxY")}


def overlap(a, b, clearance=0.0):
    return (a["minX"] < b["maxX"] + clearance and a["maxX"] > b["minX"] - clearance
            and a["minY"] < b["maxY"] + clearance and a["maxY"] > b["minY"] - clearance)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, choices=[1, 2, 3], required=True)
    args = parser.parse_args()
    review = ROOT / "layout" / f"review-{args.round}"
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    report = {
        "round": args.round,
        "scope": "Actual native rendered-bbox candidate geometry only; not supplier courtyard, land-pattern, installed STEP, SI/RF/thermal or fabrication qualification.",
        "requiredBboxGapMm": 0.20,
        "boards": {},
    }
    overall_failures = 0
    for board, expected in plan["boards"].items():
        dump_path = review / board / "fresh-board.json"
        dump = json.loads(dump_path.read_text(encoding="utf-8"))
        polygon = dump["outline"]["points"]
        polygon_mm = [[x/MM, y/MM] for x, y in polygon]
        expected_polygon = expected["outlinePolygonMm"]
        # Native coordinates are serialized to 0.0001 mil. Accept only that
        # coordinate-round-trip quantum (0.00000127 mm), never a DRC relaxation.
        outline_tolerance_mm = 0.00005 / MM
        outline_deviations = []
        if len(polygon_mm) != len(expected_polygon):
            raise RuntimeError(f"{board}: fresh outline vertex count differs from approved candidate input")
        for index, (actual, planned) in enumerate(zip(polygon_mm, expected_polygon)):
            for axis, actual_value, planned_value in zip(("x", "y"), actual, planned):
                deviation = abs(actual_value - planned_value)
                if deviation > 1e-9:
                    outline_deviations.append({"vertex": index, "axis": axis,
                                               "actualMm": actual_value, "plannedMm": planned_value,
                                               "absoluteDeviationMm": deviation})
                if deviation > outline_tolerance_mm:
                    raise RuntimeError(f"{board}: fresh outline exceeds native coordinate quantization tolerance")
        components = dump.get("components", [])
        by_ref = {c["designator"]: c for c in components}
        expected_by_ref = {p["ref"]: p for p in expected["placements"]}
        failures = []
        if set(by_ref) != set(expected_by_ref):
            failures.append({"kind": "component-set", "actual": sorted(by_ref), "expected": sorted(expected_by_ref)})
        off_board = []
        actual_boxes = {}
        for ref, component in by_ref.items():
            box = bbox_mm(component)
            actual_boxes[ref] = box
            probes = [(box["minX"],box["minY"]),(box["minX"],box["maxY"]),
                      (box["maxX"],box["minY"]),(box["maxX"],box["maxY"]),
                      ((box["minX"]+box["maxX"])/2,box["minY"]),
                      ((box["minX"]+box["maxX"])/2,box["maxY"]),
                      (box["minX"],(box["minY"]+box["maxY"])/2),
                      (box["maxX"],(box["minY"]+box["maxY"])/2)]
            if not all(inside(p, polygon_mm) for p in probes):
                off_board.append(ref)
        pairs = []
        for a, b in itertools.combinations(by_ref.values(), 2):
            if a.get("layer") != b.get("layer"):
                continue
            distance = gap(bbox_mm(a), bbox_mm(b))
            if distance < 0.20 - 1e-6:
                pairs.append({"a": a["designator"], "b": b["designator"], "gapMm": distance, "layer": a.get("layer")})
        reserve_intersections = []
        self_reserved_regions = []
        for reservation in expected["reservations"]:
            if "bbox" not in reservation:
                continue
            for ref, component in by_ref.items():
                layer = "TOP" if component.get("layer") == 1 else "BOTTOM"
                is_clock_own_region = (board == "M-OPT-BRIDGE" and ref == "Y1"
                                       and reservation.get("ref") == "Y1_CLOCK_SEARCH_RESERVE")
                if is_clock_own_region:
                    self_reserved_regions.append({"component": ref, "reservation": reservation["ref"],
                                                  "scope": "Region was reserved for this oscillator, not a keepout against itself."})
                    continue
                if layer in reservation.get("layers", []) and overlap(actual_boxes[ref], reservation["bbox"], 0.20):
                    reserve_intersections.append({"component": ref, "reservation": reservation["ref"], "layer": layer})
        if off_board:
            failures.append({"kind": "off-board-full-bbox", "refs": off_board})
        if pairs:
            failures.append({"kind": "bbox-gap-below-0.20mm", "pairs": pairs})
        if reserve_intersections:
            failures.append({"kind": "candidate-reservation-intersection", "pairs": reserve_intersections})
        copper = dump.get("copper", {})
        copper_counts = {key: len(copper.get(key, [])) for key in ("lines", "arcs", "vias", "pours", "poured", "fills")}
        authored_routing_counts = {key: copper_counts[key] for key in ("lines", "arcs", "pours", "poured", "fills")}
        embedded_vias = []
        unowned_vias = []
        for via in copper.get("vias", []):
            via_id = via.get("primitiveId", "")
            owners = [ref for ref, component in by_ref.items()
                      if via_id.startswith(component.get("primitiveId", "") + "e")]
            record = {"primitiveId": via_id, "net": via.get("net"),
                      "diameterMil": via.get("diameter"), "holeDiameterMil": via.get("holeDiameter")}
            if len(owners) == 1:
                embedded_vias.append({**record, "owner": owners[0]})
            else:
                unowned_vias.append({**record, "possibleOwners": owners})
        if any(authored_routing_counts.values()) or unowned_vias:
            failures.append({"kind": "unexpected-authored-routing-copper",
                             "counts": authored_routing_counts, "unownedVias": unowned_vias})
        overall_failures += len(failures)
        report["boards"][board] = {
            "freshDump": str(dump_path.relative_to(ROOT)),
            "candidateComponents": len(components),
            "offlineFailedPlacements": expected["failedPlacements"],
            "requiredButNotPlaced": expected["requiredButNotPlaced"],
            "offBoardRefs": off_board,
            "bboxPairsBelow0_20Mm": pairs,
            "reserveIntersectionsWithin0_20Mm": reserve_intersections,
            "selfReservedRegions": self_reserved_regions,
            "minimumObservedSameSideBboxGapMm": min((gap(bbox_mm(a), bbox_mm(b))
                for a, b in itertools.combinations(by_ref.values(), 2) if a.get("layer") == b.get("layer")), default=None),
            "outlinePolygonMm": polygon_mm,
            "outlineComparisonToleranceMm": outline_tolerance_mm,
            "outlineToleranceBasis": "Half of 0.0001 mil native coordinate serialization quantum; geometry comparison only, not a manufacturing-rule relaxation.",
            "outlineDeviationsFromMilRoundTrip": outline_deviations,
            "copperCounts": copper_counts,
            "authoredRoutingCopperCounts": authored_routing_counts,
            "embeddedFootprintVias": embedded_vias,
            "unownedVias": unowned_vias,
            "routingScope": "No script-authored tracks, arcs, standalone vias, pours, poured polygons or fills. Embedded footprint vias and rule regions remain physical/native objects and are not deleted or waived.",
            "copperAvailability": copper.get("availability"),
            "copperLayerCountObserved": dump.get("copperLayers"),
            "scalarRulesObserved": dump.get("rules"),
            "regions": [{"primitiveId": r.get("primitiveId"), "layer": r.get("layer"),
                         "geometryAvailable": r.get("geometryAvailable"), "ruleTypeNames": r.get("ruleTypeNames"),
                         "bbox": r.get("bbox"), "source": r.get("source")} for r in copper.get("regions", [])],
            "dumpPartial": dump.get("partial"),
            "failures": failures,
            "candidateGeometryStatus": "PASS_WITHIN_LIMITED_SCOPE" if not failures else "FAIL",
            "rfStatus": "UNVERIFIED: candidate components avoid reserved RF envelope, but antenna/feed/matching are missing and region rules are not a complete antenna qualification.",
            "mechanicalStatus": "BLOCKED: connectors/FPC/optics/battery/shell/acoustic parts and mated STEP are incomplete.",
            "stackupStatus": "BLOCKED: six copper layers observed; dielectric, via spans, VIPPO, impedance and bridge 0.50 mm stack are not proven.",
        }
    report["aggregateFailureCount"] = overall_failures
    report["aggregateCandidateGeometryStatus"] = "PASS_WITHIN_LIMITED_SCOPE" if overall_failures == 0 else "FAIL"
    report["fabricationStatus"] = "BLOCKED"
    output = review / "geometric-audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"round": args.round, "aggregateFailureCount": overall_failures,
                      "boards": {b: {"components": d["candidateComponents"], "status": d["candidateGeometryStatus"]}
                                 for b, d in report["boards"].items()}}, indent=2))


if __name__ == "__main__":
    main()
