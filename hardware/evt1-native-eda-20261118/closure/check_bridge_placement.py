#!/usr/bin/env python3
"""Reproduce the PR #30 bridge collision and bound independent relocation options."""

import argparse
import csv
from dataclasses import dataclass
import hashlib
from itertools import combinations
import json
import io
from math import hypot, isfinite
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
RETURN = PACKAGE / "kimi-return"
RESTORED = "native/restored-readback/M-OPT-BRIDGE.json"
ROUND3 = "layout/review-3/M-OPT-BRIDGE/fresh-board.json"
AUDIT = "evidence/pad-audit/audit-board-after.json"
PLAN = "layout/candidate-placement-plan.json"
INHERITED_BOM = (PACKAGE.parent / "evt1-rev-d1-1-20261117" /
                 "02_BOM_PINMAP_ICD_Blocked" / "BOM_V1_0_FROZEN.csv")
CONNECTOR_BODIES = HERE / "bridge_connector_bodies.json"
INPUTS = {
    "original_archive": "native/ZY_AIAR_EVT1_KIMI_20261118.epro2",
    "restored": RESTORED,
    "review3": ROUND3,
    "reservations": PLAN,
    "u8_top_0": "layout/review-1/M-OPT-BRIDGE/fresh-board.json",
    "u8_top_90": "layout/review-2/M-OPT-BRIDGE/fresh-board.json",
    "footprint_geometry": AUDIT,
}
MIL = 0.0254
GRID = 0.05
SERIALIZATION_MM = MIL * 0.00005
SIDES = {"TOP": 1, "BOTTOM": 2}


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self):
        if not all(map(isfinite, self.values())) or self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError(f"Invalid bounding box {self}")

    def values(self):
        return [self.x0, self.y0, self.x1, self.y1]

    def translated(self, x, y):
        return Box(self.x0 + x, self.y0 + y, self.x1 + x, self.y1 + y)

    def rotated(self):
        return Box(-self.y1, self.x0, -self.y0, self.x1)

    def mirrored(self):
        return Box(-self.x1, self.y0, -self.x0, self.y1)

    def inset(self, item):
        return min(item.x0 - self.x0, item.y0 - self.y0, self.x1 - item.x1, self.y1 - item.y1)

    def gap(self, other):
        dx = max(self.x0 - other.x1, other.x0 - self.x1, 0.0)
        dy = max(self.y0 - other.y1, other.y0 - self.y1, 0.0)
        return hypot(dx, dy)

    def intersect_keepout(self, other, margin):
        return (self.x0 < other.x1 + margin and self.x1 > other.x0 - margin
                and self.y0 < other.y1 + margin and self.y1 > other.y0 - margin)


def mm_box(box, scale=1.0):
    return Box(*(box[key] * scale for key in ("minX", "minY", "maxX", "maxY")))


def bbox_union(boxes):
    return Box(min(b.x0 for b in boxes), min(b.y0 for b in boxes),
               max(b.x1 for b in boxes), max(b.y1 for b in boxes))


def pad_box(pad):
    kind, *args = pad["shape"]
    if pad.get("specialPadPresent") or pad.get("specialPad"):
        raise ValueError("Special pad geometry cannot be projected")
    if kind == "POLYGON":
        # Only the observed explicit straight-line path variant is supported.
        commands = [v for v in args[0] if isinstance(v, str)]
        coordinates = [v * MIL for v in args[0] if isinstance(v, (int, float))]
        if commands not in ([], ["L"]) or len(coordinates) < 6 or len(coordinates) % 2:
            raise ValueError("Unsupported polygon pad path")
        xs, ys = coordinates[::2], coordinates[1::2]
        return Box(min(xs), min(ys), max(xs), max(ys))
    if kind not in ("RECT", "OVAL", "ELLIPSE"):
        raise ValueError(f"Unsupported pad shape {kind}")
    # EasyEDA dump width/height are already rotation-aware AABB extents.
    x, y, w, h = (pad[k] * MIL for k in ("x", "y", "width", "height"))
    return Box(x - w/2, y - h/2, x + w/2, y + h/2)


def components(data):
    result = {row["designator"]: row for row in data["components"]}
    if len(result) != len(data["components"]):
        raise ValueError("Duplicate native component designators")
    return result


def static_geometry(rows):
    return {ref: (c["device"], c["layer"], c["rotation"], mm_box(c["bbox"], MIL),
                  tuple((p["padNumber"], p["net"], p["layer"], pad_box(p)) for p in c["pads"]))
            for ref, c in rows.items()}


def validate_outline(native, required):
    points = {(round(x * MIL, 8), round(y * MIL, 8)) for x, y in native["outline"]["points"]}
    x0, x1 = min(x for x, _ in points), max(x for x, _ in points)
    y0, y1 = min(y for _, y in points), max(y for _, y in points)
    corners = {(x0, y0), (x0, y1), (x1, y0), (x1, y1)}
    if native["outline"]["source"] != "polygon" or len(native["outline"]["points"]) != 4 or points != corners:
        raise ValueError("Checker requires the fully observed rectangular bridge centerline")
    corners = {(0, 0), (0, required["length_y_mm"]), (required["width_zones"][0]["width_x_mm"], 0),
               (required["width_zones"][0]["width_x_mm"], required["length_y_mm"])}
    if any(min(hypot(x-a, y-b) for a, b in corners) > SERIALIZATION_MM + 1e-8 for x, y in points):
        raise ValueError("Native outline differs from the inherited bridge envelope")
    return Box(x0, y0, x1, y1)


def templates(data):
    recent = components(data["restored"])
    u8 = [(name, components(data[name])["U8"]) for name in ("u8_top_0", "u8_top_90")]
    u8.append(("restored", recent["U8"]))
    audit = components(data["footprint_geometry"])
    results = {"U8": [], "U10": [], "U14": []}
    for ref, sources in (("U8", u8), ("U10", [("footprint_geometry", audit["AUDIT_24"])]),
                         ("U14", [("footprint_geometry", audit["AUDIT_21"])])):
        for name, row in sources:
            body = mm_box(row["bbox"], MIL)
            copper = bbox_union([pad_box(p) for p in row["pads"]])
            x, y = (row[axis] * MIL for axis in ("x", "y"))
            body, copper = body.translated(-x, -y), copper.translated(-x, -y)
            base = {"source": name, "readbackRef": row["designator"], "device": row["device"],
                    "layer": row["layer"], "rotation": row["rotation"], "nativeOrientationObserved": True}
            results[ref].append((base, body, copper))
            if ref != "U8":
                # Search only geometric projections. Fresh native reads are required
                # for rotations and layer variants that lack an observed instance.
                results[ref].extend((
                    ({**base, "layer": layer, "rotation": angle, "nativeOrientationObserved": False},
                     body_variant, copper_variant)
                    for layer, angle, body_variant, copper_variant in (
                        (1, 90, body.rotated(), copper.rotated()),
                        (2, 0, body.mirrored(), copper.mirrored()),
                        (2, 90, body.mirrored().rotated(), copper.mirrored().rotated()),
                    )
                ))
    return results


def search(ref, variants, board, same_layer, keeps, edge, gap):
    rows = []
    for source, body, copper in variants:
        layer = source["layer"]
        associated = [(peer, other) for peer, other in same_layer[layer] if peer != ref]
        clear, nearest, slack = 0, {}, {}
        kinematically_possible = 0
        for yi in range(round(board.y1 / GRID) + 1):
            y = yi * GRID
            for xi in range(round(board.x1 / GRID) + 1):
                x = xi * GRID
                placed, pads = body.translated(x, y), copper.translated(x, y)
                if board.inset(placed) < 0 or board.inset(pads) < edge:
                    continue
                if any(placed.intersect_keepout(zone, gap) for _, zone in keeps[layer]):
                    continue
                kinematically_possible += 1
                distances = [(peer, placed.gap(other)) for peer, other in associated]
                blocked = tuple(peer for peer, distance in distances if distance < gap)
                clear += not blocked
                count = nearest.get(blocked, {}).get("locations", 0) + 1
                margin = min(board.inset(placed), board.inset(pads) - edge,
                             *(placed.gap(zone) - gap for _, zone in keeps[layer]),
                             *(dist - gap for peer, dist in distances if peer not in blocked))
                if blocked not in slack or margin > slack[blocked]:
                    slack[blocked] = margin
                    nearest[blocked] = {
                        "locations": count, "mustMoveExistingRefs": blocked, "sampleNativeAnchorMm": [round(x, 6), round(y, 6)],
                        "sampleBodyBoxMm": rounded(placed), "sampleCopperBoxMm": rounded(pads),
                        "sampleMinimumSlackMm": round(margin, 6),
                    }
                else:
                    nearest[blocked]["locations"] = count
        minimum = min(map(len, nearest), default=None)
        rows.append({**source, "bodyAtNativeOriginMm": rounded(body), "copperAtNativeOriginMm": rounded(copper),
                     "copperWidthMm": round(copper.x1 - copper.x0, 6),
                     "anchorsWithOutlineAndReservationsOnly": kinematically_possible,
                     "anchorsWithAllExistingObjectsFixed": clear,
                     "minimumExistingObjectsToDisplace": minimum,
                     "minimalDisplacementSets": [nearest[k] for k in sorted(nearest) if len(k) == minimum]})
    return rows


def rounded(box):
    return [round(value, 6) for value in box.values()]


def privacy_reservation(bom_text):
    parts = list(csv.DictReader(io.StringIO(bom_text)))
    part, = [row for row in parts if row["RefDes"] == "D3_PRIV"]
    if part["Board_Zone"] != "M-OPT-BRIDGE" or part["Side"] != "TOP":
        raise ValueError("Inherited privacy position differs from bridge TOP reservation")
    x, y, w, h = (float(part[key]) for key in ("Center_X_mm", "Center_Y_mm", "Body_Width_X_mm", "Body_Length_Y_mm"))
    return Box(x-w/2, y-h/2, x+w/2, y+h/2)


def connector_box(profile, axis, center):
    width, height = profile["bodyWidthMm"], profile["bodyLengthMm"]
    if axis == "X":
        width, height = height, width
    if axis not in ("X", "Y"):
        raise ValueError(f"Unsupported connector axis {axis}")
    x, y = center
    return Box(x-width/2, y-height/2, x+width/2, y+height/2)


def connector_analysis(plan, catalog, board, original_reserved, sides, privacy, gap):
    updated = {layer: dict(reserves) for layer, reserves in original_reserved.items()}
    labels = {zone["ref"]: zone for zone in plan["reservations"]}
    observations = []
    for ref, profile in catalog["connectors"].items():
        reservation = labels[ref]
        side, = reservation["layers"]
        layer = SIDES[side]
        before = connector_box(profile, profile["baselineLongAxis"],
                               (reservation["center"]["x"], reservation["center"]["y"]))
        projected = connector_box(profile, profile["candidateLongAxis"], profile["candidateBodyCenterMm"])
        updated[layer][ref] = projected
        neighbors = sides[layer] + ([("D3_PRIV_NOMINAL_BODY", privacy)] if layer == 1 else [])
        conflicts = [{"ref": obj, "gapMm": round(projected.gap(other), 6)}
                     for obj, other in neighbors if projected.intersect_keepout(other, gap)]
        observations.append({
            "ref": ref, "layer": layer, **profile,
            "priorReservationMm": rounded(mm_box(reservation["bbox"])),
            "bodyAtBaselineAnchorMm": rounded(before),
            "bodyMarginAtBaselineAnchorMm": round(board.inset(before), 6),
            "originalGeometryStatus": "FAIL" if board.inset(before) < 0 else "UNVERIFIED",
            "projectedBodyMm": rounded(projected),
            "projectedBodyEdgeMm": round(board.inset(projected), 6), "projectedConflictRefs": conflicts,
            "projectedPlacementStatus": "FAIL" if conflicts or board.inset(projected) < 0 else "UNVERIFIED",
        })
    clock = dict(sides[2])["Y1"]
    max_left = max(0, clock.x0 - gap - board.x0)
    max_right = max(0, board.x1 - clock.x1 - gap)
    max_before = clock.y0 - gap - board.y0
    trunk_profile = catalog["connectors"]["J_BRIDGE_IN"]
    trunk_in_front_status = "FAIL" if (trunk_profile["bodyWidthMm"] > max(max_left, max_right)
                                       and trunk_profile["bodyLengthMm"] > max_before) else "UNVERIFIED"
    return {
        "sourceScope": catalog["sourceScope"],
        "orientations": observations,
        "trunkBeforeClock": {
            "status": trunk_in_front_status,
            "availableLeftLateralWidthMm": round(max_left, 6),
            "availableRightLateralWidthMm": round(max_right, 6),
            "requiredBodyWidthMm": trunk_profile["bodyWidthMm"],
            "requiredBodyLengthMm": trunk_profile["bodyLengthMm"],
            "maxBodyLengthBeforeClockMm": round(max_before, 6),
            "lengthDeficitMm": round(trunk_profile["bodyLengthMm"] - max_before, 6),
            "clockBodyMm": rounded(clock),
            "scope": "Axis-aligned trunk along Y in original entry end, with ASADV held fixed. Uses body geometry alone before any land, mated plugs, flex, or tooling.",
        },
        "layout": [{"ref": ref, "layer": layer, "boxMm": rounded(zone)}
                   for layer, reserves in updated.items() for ref, zone in reserves.items()],
        "manufacturing": "BLOCKED",
    }


def analyze(data, contract, inputs, privacy, catalog):
    active = data["restored"]
    current = components(active)
    geometry = static_geometry(current)
    if static_geometry(components(data["review3"])) != geometry:
        raise ValueError("Restored snapshot differs geometrically from PR #30 Review 3")
    board = validate_outline(active, contract["boards"]["M-OPT-BRIDGE"])
    gap = contract["do_not_relax"]["minimum_courtyard_gap_mm"]
    plan = data["reservations"]["boards"]["M-OPT-BRIDGE"]
    if gap < max(0.20, plan["minimumCandidateBboxGapMm"]):
        raise ValueError("Unexpected reduction in gap rule")
    edge = max(contract["do_not_relax"]["minimum_edge_clearance_mm"], active["rules"]["copperToEdgeMil"] * MIL)
    if edge < 0.25:
        raise ValueError("Unexpected reduction in copper edge rule")
    reserves = {1: [], 2: []}
    for zone in plan["reservations"]:
        for side in zone["layers"]:
            reserves[SIDES[side]].append((zone["ref"], mm_box(zone["bbox"])))
    sides = {1: [], 2: []}
    placed, failures = [], []
    for ref, (mpn, layer, rotation, body, pads) in sorted(geometry.items()):
        sides[layer].append((ref, body))
        copper = bbox_union([pad[3] for pad in pads])
        placed.append({"ref": ref, "device": mpn, "layer": layer, "rotation": rotation,
                       "bodyBoxMm": rounded(body), "copperBoxMm": rounded(copper),
                       "padCount": len(pads), "minPadEdgeMm": round(board.inset(copper), 6)})
        if board.inset(body) < 0:
            failures.append({"kind": "bodyOutsideOutline", "ref": ref})
        if board.inset(copper) < edge:
            failures.append({"kind": "copperNearEdge", "ref": ref,
                             "measuredMm": round(board.inset(copper), 6), "requiredMm": edge})
        for zone, area in reserves[layer]:
            if (ref, zone) != ("Y1", "Y1_CLOCK_SEARCH_RESERVE") and body.intersect_keepout(area, gap):
                failures.append({"kind": "reservedSpace", "ref": ref, "reserve": zone, "layer": layer,
                                 "gapMm": round(body.gap(area), 6)})
    for layer, items in sides.items():
        for (a, a_box), (b, b_box) in combinations(items, 2):
            if (distance := a_box.gap(b_box)) < gap:
                failures.append({"kind": "sameLayerGap", "refs": [a, b], "layer": layer, "gapMm": round(distance, 6)})
    candidates = {ref: search(ref, variants, board, sides, reserves, edge, gap)
                  for ref, variants in templates(data).items()}
    reserves_with_privacy = {**reserves, 1: [*reserves[1], ("D3_PRIV_NOMINAL_BODY", privacy)]}
    augmented = {ref: search(ref, variants, board, sides, reserves_with_privacy, edge, gap)
                 for ref, variants in templates(data).items()}
    return {
        "sourcePullRequest": 30, "sourceFiles": inputs, "archiveGeometryAgreement": "PASS",
        "existingSnapshotStatus": "FAIL" if failures else "PASS",
        "placementClosure": "BLOCKED", "manufacturing": "BLOCKED", "label": "NOT FOR FAB",
        "geometryScope": "2D native rendered AABBs and observed copper-pad extents. No supplier courtyard, routing, STEP, or electrical release.",
        "outlineMm": rounded(board), "copperEdgeMinimumMm": edge, "requiredBBoxGapMm": gap,
        "widthAvailableForCopperMm": round(board.x1 - board.x0 - 2 * edge, 6),
        "gridMm": GRID, "layerNames": SIDES, "components": placed, "violations": failures,
        "reservations": [{"ref": ref, "layer": layer, "boxMm": rounded(zone)}
                         for layer, zones in reserves.items() for ref, zone in zones],
        "independentSearch": candidates, "unplacedRequiredSourceRefs": plan["requiredButNotPlaced"],
        "privacyApertureStatus": "BLOCKED",
        "privacyNominalBodyBoxMm": rounded(privacy),
        "privacyNominalBodySource": "PR #25 BOM-25 D3_PRIV. Added to the search because PR #30 treated D3 as unplaced with no reservation. The nominal rectangle does not substitute for exact LED land, land orientation or shell aperture.",
        "independentSearchWithPrivacyReservation": augmented,
        "manufacturerConnectorEnvelopeAnalysis": connector_analysis(plan, catalog, board, reserves, sides, privacy, gap),
        "independentSearchScope": "Observed U8 TOP 0°, TOP 90°, and BOTTOM 90° only. U10/U14 0° and 90° both layers. In each search other existing refs stay fixed. Minimal conflict sets are separate constraints, not co-placeable moves. No conclusion outside the search domain.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Reproduce and compare committed evidence")
    parser.add_argument("--strict", action="store_true", help="Return exit 1 for actual geometry FAIL")
    args = parser.parse_args()
    sources = {key: (RETURN / name).read_bytes() for key, name in INPUTS.items()}
    data = {key: json.loads(value) for key, value in sources.items() if key != "original_archive"}
    contract = (PACKAGE / "PCB_CONSTRAINTS.json").read_bytes()
    inputs = [{"path": f"kimi-return/{name}", "sha256": hashlib.sha256(sources[key]).hexdigest()}
              for key, name in INPUTS.items()]
    inputs.append({"path": "PCB_CONSTRAINTS.json", "sha256": hashlib.sha256(contract).hexdigest()})
    bom = INHERITED_BOM.read_bytes()
    inputs.append({"path": INHERITED_BOM.relative_to(PACKAGE.parent).as_posix(),
                   "pathBase": "hardware", "sha256": hashlib.sha256(bom).hexdigest()})
    connectors = CONNECTOR_BODIES.read_bytes()
    inputs.append({"path": "closure/bridge_connector_bodies.json", "sha256": hashlib.sha256(connectors).hexdigest()})
    result = analyze(data, json.loads(contract), inputs, privacy_reservation(bom.decode("utf-8-sig")),
                     json.loads(connectors))
    content = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence" / "bridge_placement.json"
    if args.check:
        if not output.exists() or content != output.read_bytes():
            raise SystemExit("FAIL: bridge placement evidence differs from the checked inputs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
    print(f"PASS: geometry evidence reproduced. PR #30 placement {result['existingSnapshotStatus']}; closure BLOCKED.")
    for finding in result["violations"]:
        print(json.dumps(finding, ensure_ascii=False))
    for ref, rows in result["independentSearch"].items():
        baseline = sum(row["anchorsWithAllExistingObjectsFixed"] for row in rows)
        with_privacy = sum(row["anchorsWithAllExistingObjectsFixed"] for row in result["independentSearchWithPrivacyReservation"][ref])
        print(f"{ref}: {baseline} fixed-neighbor anchors with PR #30 reservations, {with_privacy} with additional D3 nominal body")
    for part in result["manufacturerConnectorEnvelopeAnalysis"]["orientations"]:
        print(f"{part['ref']}: original envelope {part['originalGeometryStatus']}, projected {part['projectedPlacementStatus']}, "
              f"projected conflict refs {[p['ref'] for p in part['projectedConflictRefs']]}")
    return int(args.strict and result["existingSnapshotStatus"] != "PASS")


if __name__ == "__main__":
    sys.exit(main())
