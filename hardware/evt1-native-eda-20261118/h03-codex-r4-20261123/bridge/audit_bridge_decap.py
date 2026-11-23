#!/usr/bin/env python3
"""Read-only R3 optical bridge decoupling and harness screen. Units are mil."""

import argparse
import hashlib
import json
import math
from collections import Counter
from itertools import product
from pathlib import Path
from zipfile import ZipFile

BRIDGE_ID = "9ce45f14cb79dc9d"
WINDOW = (460, 850)
COPPER_MARGIN = 6
CAP_TO_TARGET_MIL = 100
CAP_REFS = ("C5", "C8", "C9", "C10", "C11", "C12", "C31", "C32")
FUNCTIONAL_RC = ("C2", "C3")
VERIFIED_KINDS = ("PAD_NET", "LINE", "VIA", "POLY", "RULE", "RULE_TEMPLATE",
                  "LAYER", "LAYER_PHYS", "LAYER_FILL")


def read_archive(path):
    with ZipFile(path) as archive:
        entries = [name for name in archive.namelist() if name.endswith(".epru")]
        stream = archive.read(entries[0]) if len(entries) == 1 else b""
    documents = {}
    for row in stream.splitlines():
        header, raw_payload = row.split(b"||", 1)
        header = json.loads(header)
        raw_payload = raw_payload.removesuffix(b"|")
        if not raw_payload and header["type"] != "PRIMITIVE":
            raise ValueError(f"Unexpected empty {header['type']} record")
        payload = json.loads(raw_payload or b"null")
        if header["type"] == "DOCHEAD":
            objects = documents.setdefault((payload["docType"], payload["uuid"]), {})
        else:
            key = (header["type"], header["id"])
            if key in objects:
                raise ValueError(f"Duplicate native record {key}")
            objects[key] = payload
    return documents


def by_kind(document, kind):
    return {identity: payload for (category, identity), payload in document.items()
            if category == kind}


def bounds(box):
    return box["minX"], box["minY"], box["maxX"], box["maxY"]


def intersects(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def point_to_segment(point, start, end):
    ab = (end[0] - start[0], end[1] - start[1])
    numerator = sum((p - a) * d for p, a, d in zip(point, start, ab))
    denominator = sum(d*d for d in ab)
    t = min(1, max(0, numerator / denominator)) if denominator else 0
    return math.dist(point, tuple(a + t*d for a, d in zip(start, ab)))


def point_to_rectangle(point, box):
    x, y = point
    return math.hypot(max(box[0] - x, x - box[2], 0), max(box[1] - y, y - box[3], 0))


def rectangle_to_segment(box, start, end):
    t0, t1 = 0, 1
    for axis in (0, 1):
        d = end[axis] - start[axis]
        if not d:
            if box[axis] <= start[axis] <= box[axis + 2]:
                continue
            break
        low, high = sorted(((box[i] - start[axis]) / d for i in (axis, axis + 2)))
        t0, t1 = max(t0, low), min(t1, high)
        if t0 > t1:
            break
    else:
        return 0
    corners = product((box[0], box[2]), (box[1], box[3]))
    return min(point_to_rectangle(start, box), point_to_rectangle(end, box),
               *(point_to_segment(corner, start, end) for corner in corners))


def segment_entry(identity, line):
    return (identity, line["netName"], (line["startX"], line["startY"]),
            (line["endX"], line["endY"]), line["width"] / 2)


def via_entry(identity, via):
    point = via["centerX"], via["centerY"]
    return identity, via["netName"], point, point, via["viaDiameter"] / 2


def cap_search(cap, target, outline, components, obstacle_sets):
    candidates = {}
    for side, obstacles in obstacle_sets.items():
        distances = Counter()
        best = None
        occupied = [bounds(c["bbox"]) for c in components.values()
                    if c["layer"] == side and c != cap]
        offsets = []
        for pad in cap["pads"]:
            assert pad["shape"][0] == "RECT"
            offsets.append((pad["net"], pad["x"]-cap["x"], pad["y"]-cap["y"],
                            pad["width"]/2, pad["height"]/2))
        bbox = bounds(cap["bbox"])
        local_bbox = (bbox[0]-cap["x"], bbox[1]-cap["y"], bbox[2]-cap["x"], bbox[3]-cap["y"])
        for turn in range(4):
            def rotate(x, y):
                return ((x, y), (-y, x), (-x, -y), (y, -x))[turn]

            rotated = [(net, *rotate(dx, dy), *( (hy, hx) if turn % 2 else (hx, hy)))
                       for net, dx, dy, hx, hy in offsets]
            cx, cy = (target["x"] - rotated[0][1], target["y"] - rotated[0][2])
            corners = [rotate(x, y) for x, y in product((local_bbox[0], local_bbox[2]),
                                                       (local_bbox[1], local_bbox[3]))]
            l, b, r, t = min(x for x, y in corners), min(y for x, y in corners), max(x for x, y in corners), max(y for x, y in corners)
            for x, y in product(range(math.ceil(max(outline[0] - l, cx - CAP_TO_TARGET_MIL)),
                                      math.floor(min(outline[2] - r, cx + CAP_TO_TARGET_MIL)) + 1),
                                range(math.ceil(max(outline[1] - b, cy - CAP_TO_TARGET_MIL)),
                                      math.floor(min(outline[3] - t, cy + CAP_TO_TARGET_MIL)) + 1)):
                distance = math.hypot(x - cx, y - cy)
                if distance > CAP_TO_TARGET_MIL:
                    continue
                distances["inside_outline_and_near_target"] += 1
                if any(intersects((x+l, y+b, x+r, y+t), other) for other in occupied):
                    continue
                distances["clear_component_envelopes"] += 1
                pads = [(net, (x+dx-hx, y+dy-hy, x+dx+hx, y+dy+hy))
                        for net, dx, dy, hx, hy in rotated]
                if any(box[0] < outline[0] + COPPER_MARGIN or box[1] < outline[1] + COPPER_MARGIN
                       or box[2] > outline[2] - COPPER_MARGIN or box[3] > outline[3] - COPPER_MARGIN
                       for _, box in pads):
                    continue
                blocked = set()
                for pad_net, box in pads:
                    for identity, net, start, end, radius in obstacles:
                        if net != pad_net and rectangle_to_segment(box, start, end) < COPPER_MARGIN + radius:
                            blocked.add(identity)
                if blocked:
                    continue
                distances["clear_component_envelopes_and_foreign_line_via_copper"] += 1
                if best is None or distance < best["distance_mil"]:
                    best = {"x_mil": x, "y_mil": y, "turn_deg": 90 * turn,
                            "distance_mil": round(distance, 3)}
        candidates[str(side)] = {
            **dict.fromkeys(("inside_outline_and_near_target", "clear_component_envelopes",
                             "clear_component_envelopes_and_foreign_line_via_copper"), 0),
            **distances, "nearest_placement_only": best,
        }
    return candidates


def touching_copper(cap, obstacles):
    """Collect conservatively intersecting copper at the current cap terminals."""
    contacts = {}
    for pad in cap["pads"]:
        x, y = pad["x"], pad["y"]
        half_x, half_y = pad["width"] / 2, pad["height"] / 2
        box = (x - half_x, y - half_y, x + half_x, y + half_y)
        contacts[pad["padNumber"]] = sorted(i for i, net, start, end, radius in obstacles[pad["layer"]]
                                            if net == pad["net"]
                                            and rectangle_to_segment(box, start, end) <= radius)
    return contacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r3", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("reference_dump", type=Path)
    parser.add_argument("reference_loops", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    r3_docs, ref_docs = read_archive(args.r3), read_archive(args.reference)
    r3, ref = (docs["PCB", BRIDGE_ID] for docs in (r3_docs, ref_docs))
    counts = {}
    for kind in VERIFIED_KINDS:
        cur, old = by_kind(r3, kind), by_kind(ref, kind)
        if cur != old:
            raise ValueError(f"R3 differs from the observed bridge copper/rules in {kind}")
        counts[kind] = len(cur)

    dump = json.loads(args.reference_dump.read_text(encoding="utf-8-sig"))
    components = {row["designator"]: row for row in dump["components"]}
    current = by_kind(r3, "COMPONENT")
    prior = by_kind(ref, "COMPONENT")
    current_attrs = { (p["parentId"], p["key"]): p["value"] for p in by_kind(r3, "ATTR").values() }
    prior_attrs = { (p["parentId"], p["key"]): p["value"] for p in by_kind(ref, "ATTR").values() }
    for component in components.values():
        identity = component["primitiveId"]
        item, old = current[identity], prior[identity]
        assert current_attrs[identity, "Designator"] == component["designator"]
        assert (item["x"], item["y"], item["angle"] % 360, item["layerId"]) == (
            old["x"], old["y"], old["angle"] % 360, old["layerId"])
        assert item["layerId"] == component["layer"]
        assert all(math.isclose(item[key], component[key], abs_tol=1e-7) for key in ("x", "y"))
        assert item["attrs"]["Unique ID"] == old["attrs"]["Unique ID"] == component["uniqueId"]
        f = current_attrs[identity, "Footprint"]
        assert f == prior_attrs[identity, "Footprint"]
        # Exclude only non-visible 3D model links introduced by the later editor.
        def planar_footprint(archive):
            return {key: value for key, value in archive["FOOTPRINT", f].items()
                    if key[0] != "ATTR" or value.get("key") not in ("3D Model", "3D Model Title")
                    or value.get("keyVisible") or value.get("valueVisible")}
        assert planar_footprint(r3_docs) == planar_footprint(ref_docs)

    all_lines, all_vias = by_kind(r3, "LINE"), by_kind(r3, "VIA")
    outer_via_rules = {1: "BV_L1_L2", 2: "BV_L5_L6"}
    obstacles = {layer: [segment_entry(identity, p) for identity, p in all_lines.items()
                         if p["layerId"] == layer]
                       + [via_entry(identity, p) for identity, p in all_vias.items()
                          if p["viaType"] == "NORMAL" or p["ruleName"] == rule]
                 for layer, rule in outer_via_rules.items()}
    via_types = Counter((p["viaType"], p["ruleName"]) for p in all_vias.values())
    assert all(via_type == "NORMAL" or rule in outer_via_rules.values() for via_type, rule in via_types)
    points = dump["outline"]["points"]
    outline = (min(p[0] for p in points), min(p[1] for p in points),
               max(p[0] for p in points), max(p[1] for p in points))
    harness = {identity: p for identity, p in all_lines.items() if p["netName"].startswith("FPGA_C")}
    harness_window = {identity: p for identity, p in harness.items() if p["layerId"] == 2
                      and min(p["startY"], p["endY"]) <= WINDOW[1]
                      and max(p["startY"], p["endY"]) >= WINDOW[0]}
    ref_loops = json.loads(args.reference_loops.read_text(encoding="utf-8-sig"))
    rows = ref_loops["boards"]["PCB2"]["decouplingReview"]
    selected = [row for row in rows if row["ref"] in CAP_REFS]
    assert set(row["ref"] for row in selected) == set(CAP_REFS)
    results = []
    for row in selected:
        cap = components[row["ref"]]
        owner, pin = (row["actualLoopTarget"][key] for key in ("ref", "pin"))
        supply, = (p for p in cap["pads"] if p["padNumber"] == "1")
        load, = (p for p in components[owner]["pads"] if p["padNumber"] == pin)
        assert supply["net"] == load["net"] == row["net"]
        assert cap["pads"][1]["net"] == "GND"
        assert cap["pads"][0] == supply
        supply_distance = math.dist((supply["x"], supply["y"]), (load["x"], load["y"]))
        results.append({"cap": cap["designator"], "cap_layer": cap["layer"], "net": supply["net"],
                        "role": row["role"], "target": f"{owner}.{pin}", "target_layer": load["layer"],
                        "target_function": row["actualLoopTarget"]["function"],
                        "current_pad_center_distance_mil": round(supply_distance, 2),
                        "existing_pad_copper_contacts": touching_copper(cap, obstacles),
                        "placement_screen": cap_search(cap, load, outline, components, obstacles)})
    report = {
        "scope": ("Read-only archive geometry and inherited native readback. The filter covers component box overlap, "
                  "board containment and foreign line/via copper, without routing, full DRC or assembly clearance."),
        "r3_sha256": hashlib.sha256(args.r3.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "components_unchanged_in_xy_side_and_normalized_angle": len(components),
        "raw_native_object_payloads_identical_to_reference": counts,
        "outline_mil": outline,
        "harness_all_by_net_and_layer": [
            {"net": net, "layer_id": layer, "segments": count}
            for (net, layer), count in sorted(Counter((p["netName"], p["layerId"]) for p in harness.values()).items())
        ],
        "harness_bottom_window_mil": WINDOW,
        "harness_window_segments": harness_window,
        "harness_vias": {i: p for i, p in all_vias.items() if p["netName"].startswith("FPGA_C")},
        "harness_named_pads": [{"ref": c["designator"], "pad": p["padNumber"], "net": p["net"], "layer": p["layer"]}
                               for c in components.values() for p in c["pads"] if p["net"].startswith("FPGA_C")],
        "ground_plane_layers_with_fill": sorted({r["layerId"] for p in by_kind(r3, "LAYER_FILL").values()
                                                 for r in p["fill"] if r["netName"] == "GND"}),
        "guard_mil_for_foreign_track_and_via_copper": COPPER_MARGIN,
        "decaps": results,
        "functional_rc_excluded": {ref: {p["padNumber"]: p["net"] for p in components[ref]["pads"]}
                                   for ref in FUNCTIONAL_RC},
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in results:
        print(row["cap"], row["target"], row["current_pad_center_distance_mil"], row["placement_screen"])


if __name__ == "__main__":
    main()
