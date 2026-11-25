"""V2.0 acceptance and native replay for additive PCB batches and controlled placements."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys
from zipfile import ZipFile

R10 = "h03-codex-r10-master-20261124/increment"
for parent in Path(__file__).resolve().parents:
    choices = (parent / R10, parent / "evt1-h03-r11-master/hardware/evt1-native-eda-20261118" / R10)
    available = next((path for path in choices if (path / "easyeda_increment.py").is_file()), None)
    if available:
        sys.path.insert(0, str(available))
        break
else:
    raise ImportError("Run from the project checkout containing the inherited R10 increment helper")

import easyeda_increment as native

LEVELS = ("L1", "L2", "L3")
REGULAR_BOARD_LAYERS = {1, 2, 16, 17}
SCH_DOCS = {"PCB1": "4d38590959875927", "PCB2": "e00fbca5c08cc114", "PCB3": "e98944c2045546cf"}
POSE = {"x": "x", "y": "y", "rotation": "angle", "layer": "layerId"}
MASK = frozenset(("id", "before", "after"))
TRACK_FLOORS = {"GND": 6, "VSYS": 20}
MIN_SIGNAL = 4


def require(ok, problem):
    if not ok:
        raise ValueError(problem)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def point(p):
    return isinstance(p, list) and len(p) == 2 and all(map(number, p))


def equal_number(a, b, tolerance=.006):
    return number(a) and number(b) and abs(a - b) <= tolerance


def parse_plan(path, checkpoint):
    plan = native.read(path)
    require(plan.get("schemaVersion") == 1, "Unsupported plan schema")
    require(re.fullmatch(r"[A-Za-z0-9-]{4,56}", plan.get("id", "")), "Invalid batch id")
    require(plan.get("level") in LEVELS, "Specify L1, L2, or L3")
    require(plan.get("checkpointSha256") == native.digest(checkpoint), "Checkpoint SHA-256 mismatch")
    boards = plan.get("boards")
    require(isinstance(boards, dict) and boards and set(boards) <= set(native.PCB_IDS), "Unknown or empty board scope")
    for board, change in boards.items():
        require(set(change) <= {"moves", "routes", "trackFloorsMil"}, f"{board}: unknown operation")
        floors = change.get("trackFloorsMil", {})
        require(isinstance(floors, dict) and all(number(v) and v >= max(MIN_SIGNAL, TRACK_FLOORS.get(k, 0))
                                                for k, v in floors.items()), f"{board}: width downgrade")
        require(change.get("moves") or change.get("routes"), f"{board}: empty batch")
        for move in change.get("moves", []):
            require(set(move) == MASK and native.UID.fullmatch(move["id"]), f"{board}: malformed move")
            before, after = move["before"], move["after"]
            require(set(before) == set(after) == set(POSE) and all(map(number, (*before.values(), *after.values()))),
                    f"{board}: move must bind full before/after poses")
            require(before != after, f"{board}: component move is a no-op")
            require(before["layer"] == after["layer"] and before["layer"] in (1, 2),
                    f"{board}: layer flip is a separate physical ECO")
        for route in change.get("routes", []):
            validate_route(board, route, floors)
    if any(change.get("moves") for change in boards.values()):
        require(plan["level"] in ("L2", "L3"), "Placement batches require L2 or L3")
    return plan


def validate_route(board, route, floors):
    net, layer, width, pts = (route.get(k) for k in ("net", "layer", "width", "points"))
    require(isinstance(net, str) and net.strip() and layer in REGULAR_BOARD_LAYERS, f"{board}: invalid route net or layer")
    floor = floors.get(net, TRACK_FLOORS.get(net, MIN_SIGNAL))
    require(number(width) and width >= floor, f"{board}/{net}: route width {width} below {floor} mil")
    require(isinstance(pts, list) and len(pts) >= 2 and all(map(point, pts)), f"{board}/{net}: invalid path")
    for a, b in zip(pts, pts[1:]):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        require(math.dist(a, b) >= .1 and min(dx, dy, abs(dx-dy)) <= .003,
                f"{board}/{net}: duplicated or non-45-degree segment")
    via = route.get("via")
    refs = [route.get("from")]
    if via:
        require(net == "GND" and route.get("to") in (None, "L2-GND", "L5-GND"), f"{board}: unsupported plane return")
        require((layer, via.get("rule")) in ((1, "BV_L1_L2"), (2, "BV_L5_L6")),
                f"{board}: layer/laser span mismatch")
        require(all(number(via.get(k)) for k in ("x", "y", "drill", "diameter")), f"{board}: malformed via")
        require((via["drill"], via["diameter"]) == (4, 10), f"{board}: this adapter validates 4/10 mil blind vias")
        require(math.dist(pts[-1], (via["x"], via["y"])) <= .006, f"{board}: line does not meet placed via")
    else:
        refs.append(route.get("to"))
    require(all(isinstance(r, str) and (native.REF.fullmatch(r) or native.UID.fullmatch(r)) for r in refs),
            f"{board}: each route needs existing pad/primitive endpoint references")


def pose_matches(record, wanted):
    return all(equal_number(record.get(key), wanted[k]) for k, key in POSE.items())


def changed_fields(old, new):
    return {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}


def line_key(net, layer, width, start, end):
    return net, layer, width, *sorted(tuple(round(c, 4) for c in p) for p in (start, end))


def via_key(net, rule, x, y, drill, diameter):
    return net, "BLIND", rule, round(x, 4), round(y, 4), drill, diameter


def project_metadata(path):
    with ZipFile(path) as bundle:
        metadata = json.loads(bundle.read("project2.json"))
    metadata.pop("title", None)
    return metadata


def check_archive(before, after, plan):
    require(before.keys() == after.keys(), "Native document topology changed")
    boards = {("PCB", native.PCB_IDS[b]): b for b in plan["boards"]}
    require(boards.keys() <= before.keys(), "Target PCB missing from checkpoint")
    result = {}
    for doc, old in before.items():
        new = after[doc]
        if doc not in boards:
            require(old == new, f"Unexpected edit in {doc}")
            continue
        board = boards[doc]
        change = plan["boards"][board]
        moves = {move["id"]: move for move in change.get("moves", [])}
        require(len(moves) == len(change.get("moves", [])), f"{board}: duplicate component move")
        check_placements(board, old, new, moves)
        actual_lines, actual_vias, placeholders = Counter(), Counter(), Counter()
        for (typ, uid) in new.keys() - old.keys():
            item = new[typ, uid]
            if typ == "LINE":
                actual_lines[native.geometry(item)] += 1
            elif typ == "VIA" and item["viaType"] == "BLIND":
                actual_vias[via_key(item["netName"], item["ruleName"], item["centerX"], item["centerY"],
                                    item["holeDiameter"], item["viaDiameter"])] += 1
            elif typ == "ELE_PLACEHOLDER":
                require(re.fullmatch(r"placeholder[0-9]+", uid) and set(item) == {"dataType", "max"}
                        and item["dataType"] in ("LINE", "VIA") and type(item["max"]) is int and item["max"] > 0,
                        f"{board}: unexpected native placeholder contents {uid}")
                placeholders[item["dataType"]] += item["max"]
            else:
                raise ValueError(f"{board}: new undeclared {typ} {uid}")
        routes = change.get("routes", [])
        lines = Counter(line_key(r["net"], r["layer"], r["width"], a, b)
                        for r in routes for a, b in zip(r["points"], r["points"][1:]))
        vias = Counter(via_key(r["net"], v["rule"], v["x"], v["y"], v["drill"], v["diameter"])
                       for r in routes if (v := r.get("via")))
        require(lines == actual_lines and vias == actual_vias, f"{board}: native copper does not match approved route geometry")
        counts = {"LINE": sum(lines.values()), "VIA": sum(vias.values())}
        require(all(counts[k] == n for k, n in placeholders.items()),
                f"{board}: placeholder counts do not match the native additions")
        result[board] = {"addedLines": counts["LINE"], "addedBlindVias": counts["VIA"], "moved": sorted(moves),
                         "nativePlaceholderCounts": dict(placeholders)}
    return result


def check_placements(board, old, new, moves):
    require(old.keys() <= new.keys(), f"{board}: restored checkpoint required, existing native records were deleted")
    for uid, move in moves.items():
        key = ("COMPONENT", uid)
        require(key in old and pose_matches(old[key], move["before"]), f"{board} {uid}: stale original pose")
        require(key in new and pose_matches(new[key], move["after"]), f"{board} {uid}: wrong persisted pose")
    for key, left in old.items():
        right = new[key]
        if left == right:
            continue
        typ, uid = key
        if typ == "COMPONENT" and uid in moves:
            require(changed_fields(left, right) <= {"x", "y", "angle"}, f"{board} {uid}: component changed beyond position/rotation")
        elif typ == "ATTR" and any(uid.startswith(item) for item in moves):
            changed = changed_fields(left, right)
            if "zIndex" in changed:
                require((left.get("zIndex"), right.get("zIndex")) in ((23, -1), (24, 1)), f"{board} {uid}: unknown z-index change")
                changed.remove("zIndex")
            require(changed <= {"x", "y", "angle"}, f"{board} {uid}: attribute value or style changed")
        else:
            raise ValueError(f"{board}: retained rule, pad-net, outline, plane, or copper changed {key}")


def signatures(report, ignore_connection_coordinates=True):
    found = Counter()
    require("nativeResult" in report and "violations" in report and "counts" in report,
            "Native strict DRC lacks raw results or counts")
    require(Counter(v["rule"] for v in report["violations"]) == Counter(report["counts"]),
            "Native report counts and object rows disagree")
    for item in report["violations"]:
        signature = (item["rule"], item["objType"], item.get("ruleName"), item.get("net"),
                     tuple(sorted(item.get("objs") or ())) if item["rule"] != "Netlist Error" else ())
        if item["rule"] != "Connection Error" or not ignore_connection_coordinates:
            signature += (item.get("x"), item.get("y"), item.get("message"))
        found[signature] += 1
    return found


def capture_identity(folder, board):
    path = folder / (board + "-copper.json")
    dump = native.read(path)
    ident = dump["capture"]
    require(ident["documentUuid"] == native.PCB_IDS[board] and ident["identityVerified"] is True and not dump.get("partial"),
            f"{path.name}: native target not proven")
    required = {"routing", "vias", "fills", "pours", "poured", "regions"}
    require(required <= dump["copper"]["availability"].keys() and all(isinstance(dump["copper"].get(k), list) for k in ("lines", "arcs")), f"{path.name}: incomplete copper types")
    require(all(dump["copper"]["availability"][k] == "available" for k in required), f"{path.name}: unavailable native geometry")
    return ident["projectUuid"], dump


def check_capture_records(board, dump, records):
    components = comp_map(dump)
    packaged = {uid: item for (kind, uid), item in records.items() if kind == "COMPONENT"}
    require(components.keys() == packaged.keys(), f"{board}: capture and archive component identity differ")
    for uid, item in components.items():
        require(pose_matches(packaged[uid], item), f"{board}: stale captured pose for {uid}")
    tracks = {uid: v for (typ, uid), v in records.items() if typ == "LINE"}
    observed = {row["primitiveId"]: row for row in dump["copper"]["lines"]}
    # The legacy list omits inherited centerlines shorter than .1 mil.
    # All modeled new lines are at least this long.
    unexpected = [uid for uid, t in tracks.items() if uid not in observed and
                  math.dist((t["startX"], t["startY"]), (t["endX"], t["endY"])) >= .1]
    require(not unexpected and observed.keys() <= tracks.keys(), f"{board}: raw line inventory differs from archive: {unexpected}")
    for uid, row in observed.items():
        actual = line_key(row["net"], row["layer"], row["lineWidth"],
                          (row["startX"], row["startY"]), (row["endX"], row["endY"]))
        expected = native.geometry(tracks[uid])
        require(actual[:2] == expected[:2] and actual[3:] == expected[3:]
                and equal_number(actual[2], expected[2], .0001), f"{board}: changed raw line {uid}")
    vias = {uid: v for (typ, uid), v in records.items() if typ == "VIA"}
    observed = {row["primitiveId"]: row for row in dump["copper"]["vias"]}
    require(vias.keys() == observed.keys(), f"{board}: raw via inventory differs from archive")
    for uid, row in observed.items():
        expected = vias[uid]
        values = {"x": "centerX", "y": "centerY", "diameter": "viaDiameter", "holeDiameter": "holeDiameter"}
        require(row["net"] == expected["netName"] and all(equal_number(row[k], expected[v], .02)
                                                          for k, v in values.items()), f"{board}: changed raw via {uid}")


def comp_map(dump):
    return {c["primitiveId"]: c for c in dump["components"]}


def raw_terminals(dump):
    return {(c["designator"], str(p["padNumber"]), p["primitiveId"], p["net"], p.get("layer"))
            for c in dump["components"] for p in c["pads"]}


def endpoint(dump, records, ref, net, layer, at):
    if "." not in ref:
        return native.endpoint(dump, records, ref, net, layer, at)
    part, pad_no = ref.rsplit(".", 1)
    matches = [p for c in dump["components"] if c["designator"] == part for p in c["pads"]
               if str(p["padNumber"]) == pad_no and p["net"] == net and p["layer"] in (layer, 12)]
    require(len(matches) == 1 and pad_contains(matches[0], at),
            f"{ref}: endpoint does not enter native copper for {net} on layer {layer}")
    return matches[0]["primitiveId"]


def pad_contains(pad, at):
    if native.contains_pad_center(pad, at):
        return True
    shape = pad["shape"]
    if pad.get("specialPadPresent") or shape[0] != "RECT" or len(shape) != 4 or shape[3] != 0:
        return False
    theta = math.radians(pad["rotation"])
    dx, dy = at[0]-pad["x"], at[1]-pad["y"]
    x = dx*math.cos(theta) + dy*math.sin(theta)
    y = dy*math.cos(theta) - dx*math.sin(theta)
    return abs(x)+.12 < shape[1]/2 and abs(y)+.12 < shape[2]/2


def plane_containment(records, layer, net, center, radius):
    """Prove circular land is within true line-only plane boundary, outside every cutout."""
    areas = [polygon for (typ, _), item in records.items() if typ == "LAYER_FILL"
             for polygon in item["fill"] if polygon["layerId"] == layer and polygon["netName"] == net]
    for area in areas:
        if "path" not in area or not area["path"]:
            continue
        bearings = [plane_polygon(path, center) for path in area["path"]]
        if any(value is None for value in bearings):
            continue
        if bearings[0][0] and all(not p[0] for p in bearings[1:]) and min(p[1] for p in bearings) > radius + .02:
            return True
    return False


def plane_polygon(raw, center):
    if any(token != "L" for token in raw if isinstance(token, str)):
        return None
    nums = [v for v in raw if not isinstance(v, str)]
    if len(nums) < 6 or len(nums) % 2 or not all(map(number, nums)):
        return None
    points = list(zip(nums[::2], nums[1::2]))
    cx, cy = center
    inside = False
    distance = float("inf")
    for a, b in zip(points, points[1:] + points[:1]):
        ax, ay = a
        bx, by = b
        if (ay > cy) != (by > cy) and cx < (bx-ax) * (cy-ay) / (by-ay) + ax:
            inside = not inside
        d = point_distance(center, a, b)
        distance = min(distance, d)
    return inside, distance


def point_distance(p, a, b):
    dx, dy = (b[0] - a[0], b[1] - a[1])
    squared = dx*dx + dy*dy
    if squared == 0:
        return math.dist(p, a)
    projection = max(0, min(1, ((p[0] - a[0])*dx + (p[1] - a[1])*dy)/squared))
    return math.dist(p, (a[0]+projection*dx, a[1]+projection*dy))


def verify_endpoints(board, change, before_dump, after_dump, before_doc, after_doc):
    old_components, new_components = map(comp_map, (before_dump, after_dump))
    require(old_components.keys() == new_components.keys(), f"{board}: native component list changed")
    require(raw_terminals(before_dump) == raw_terminals(after_dump), f"{board}: native pad identity or pad net changed")
    verify_isolated_moves(board, change, before_dump, before_doc, old_components)
    verify_route_endpoints(board, change, after_dump, after_doc)


def verify_isolated_moves(board, change, before_dump, before_doc, old_components=None):
    if not change.get("moves"):
        return
    require(not any(before_dump["copper"].get(field) for field in ("arcs", "pours", "poured", "fills")),
            f"{board}: moved pad isolation on local arcs or poured/fill copper requires another adapter")
    if old_components is None:
        old_components = comp_map(before_dump)
    for uid in (item["id"] for item in change.get("moves", [])):
        old_pads = old_components[uid]["pads"]
        copper = [v for (kind, unused), v in before_doc.items() if kind in ("LINE", "VIA")]
        # Placement moves may only reposition previously isolated pads. Inscribed
        # copper check for moving components is conservative and refuses uncertain
        # continuity for geometry formats beyond the envelope.
        for pad in old_pads:
            require(pad.get("shape", [None])[0] in ("ELLIPSE", "RECT", "OVAL"), f"{board}: moving pad outline unsupported")
            radius = math.hypot(pad["width"], pad["height"])/2 + .12
            center = pad["x"], pad["y"]
            require(pad["layer"] in (1, 2) and not pad.get("specialPadPresent"),
                    f"{board} {uid}: only ordinary surface-mount pads can be moved")
            for other in old_components.values():
                if other["primitiveId"] == uid:
                    continue
                for p in other["pads"]:
                    if p["layer"] not in (pad["layer"], 12) or p["net"] != pad["net"]:
                        continue
                    envelope = pad_outer_radius(p)
                    require(math.dist(center, (p["x"], p["y"])) > radius + envelope,
                            f"{board} {uid}: another same-net pad could touch the moved pad")
            for shape in copper:
                if shape["netName"] != pad["net"]:
                    continue
                if "startX" in shape:
                    if shape["layerId"] == pad["layer"]:
                        require(point_distance(center, (shape["startX"], shape["startY"]),
                                               (shape["endX"], shape["endY"])) > radius + shape["width"]/2,
                                f"{board} {uid}: old track could be attached to moved pad")
                else:
                    if via_reaches(shape, before_doc, pad["layer"]):
                        require(math.dist(center, (shape["centerX"], shape["centerY"])) > radius + shape["viaDiameter"]/2,
                                f"{board} {uid}: old via could be attached to moved pad")


def verify_route_endpoints(board, change, after_dump, after_doc):
    layers = {item["layerId"]: item for (kind, _), item in after_doc.items() if kind == "LAYER"}
    for r in change.get("routes", []):
        layer = layers.get(r["layer"], {})
        require(layer.get("use") is True and layer.get("locked") is False
                and layer.get("layerType") in ("TOP", "BOTTOM", "SIGNAL"),
                f"{board}: route targets disabled, locked, or non-signal layer")
        endpoint(after_dump, after_doc, r["from"], r["net"], r["layer"], r["points"][0])
        via = r.get("via")
        if via:
            inner = {1: 15, 2: 18}[r["layer"]]
            require(blind_span(after_doc, via["rule"]) == ({1, 15} if inner == 15 else {18, 2}),
                    f"{board}: unchanged blind rule does not span requested layers")
            require(plane_containment(after_doc, inner, r["net"], (via["x"], via["y"]), via["diameter"]/2),
                    f"{board}: full blind via land not in the actual GND plane copper")
        else:
            endpoint(after_dump, after_doc, r["to"], r["net"], r["layer"], r["points"][-1])


def pad_outer_radius(pad):
    shape = pad["shape"]
    if shape[0] in ("ELLIPSE", "RECT", "OVAL"):
        return math.hypot(*shape[1:3])/2
    require(shape[0] == "POLYGON", f"Unsupported nearby pad shape {shape[0]}")
    coordinates = shape[1]
    require(all(v == "L" for v in coordinates if isinstance(v, str)), "Curved pad isolation needs a geometry adapter")
    nums = [v for v in coordinates if not isinstance(v, str)]
    center = pad["x"], pad["y"]
    return max(math.dist(center, q) for q in zip(nums[::2], nums[1::2], strict=True))


def blind_span(doc, name):
    rules = doc["RULE", '["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
    matching = [r for r in rules if r["name"] == name]
    require(len(matching) == 1, f"Blind via definition {name} missing or ambiguous")
    return {matching[0]["staLayerId"], matching[0]["endLayerId"]}


def via_reaches(via, doc, layer):
    return via["viaType"] == "NORMAL" or layer in blind_span(doc, via["ruleName"])


def drc_gate(before, after, change):
    left, right = signatures(before), signatures(after)
    added, removed = right-left, left-right
    allowed = {r["net"] for r in change.get("routes", [])}
    require(all(x[0] == "Connection Error" and x[3] in allowed for x in added + removed),
            "Native DRC changed rule/object outside planned connections")
    require(not added or sum(removed.values()) > sum(added.values()), "New unwitnessed disconnected objects")
    raw_before = before["counts"].get("Connection Error", 0)
    raw_after = after["counts"].get("Connection Error", 0)
    if change.get("routes"):
        require(raw_after < raw_before, "No strictly better native connection result")
    else:
        require(raw_after <= raw_before, "Placement increased disconnected objects")
    return {"connectionErrors": [raw_before, raw_after], "removedObjects": sum(removed.values()), "newObjects": sum(added.values())}


def strict_erc(path):
    erc = native.read(path)["result"]
    require(erc["strict"] is True and erc["detailsAvailable"] is True, f"{path.name}: strict ERC evidence missing")
    frozen = Counter(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in erc["violations"])
    return {"summary": erc["summary"], "objects": frozen}


def evidence(checkpoint, result, plan_path, baseline_dir, after_dir, extra, dfm):
    plan = parse_plan(plan_path, checkpoint)
    a, b = native.archive(checkpoint), native.archive(result)
    require(project_metadata(checkpoint) == project_metadata(result), "Project metadata differs beyond the sandbox title")
    geom = check_archive(a, b, plan)
    required = tuple(native.PCB_IDS) if plan["level"] == "L3" else tuple(plan["boards"])
    projects = [set(), set(), set()]
    after_drc = {}
    for board in required:
        for i, folder in enumerate((baseline_dir, after_dir)):
            project, dump = capture_identity(folder, board)
            projects[i].add(project)
            doc = ("PCB", native.PCB_IDS[board])
            check_capture_records(board, dump, (a if i == 0 else b)[doc])
            if i == 0:
                dump_before = dump
            else:
                dump_after = dump
        if board in geom:
            doc = ("PCB", native.PCB_IDS[board])
            verify_endpoints(board, plan["boards"][board], dump_before, dump_after, a[doc], b[doc])
        elif raw_terminals(dump_before) != raw_terminals(dump_after):
            raise ValueError(f"{board}: changed unaffected native terminals")
        original, changed = [native.read(p / f"{board}-drc.json") for p in (baseline_dir, after_dir)]
        after_drc[board] = changed
        if board in geom:
            geom[board].update(drc_gate(original, changed, plan["boards"][board]))
        else:
            require(signatures(original) == signatures(changed), f"{board}: unaffected native DRC object changed")
        check_erc_net(board, baseline_dir, after_dir)
        load_reload(after_dir / f"{board}-reload.json", board, project)
    require(len(projects[0]) == len(projects[1]) == 1, "Capture phases mixed projects")
    if plan["level"] in ("L2", "L3"):
        require(dfm is not None, "L2/L3 requires a reviewed independent DFM artifact")
        review = native.read(dfm)
        require(review.get("checkpointSha256") == native.digest(checkpoint) and review.get("postSha256") == native.digest(result)
                and review.get("planSha256") == native.digest(plan_path) and review.get("unresolvedNewFindings") == []
                and review.get("schemaVersion") == 1
                and review.get("method") == "inherited-native-v4-hdi-and-copper-dfm"
                and all(review.get("boards", {}).get(board, {}).get("v4NativeCheckpoints") ==
                        [native.digest(folder / f"{board}-copper.json") for folder in (baseline_dir, after_dir)]
                        for board in required),
                "DFM review is stale, incomplete, or contains new findings")
    if plan["level"] == "L3":
        require(extra is not None, "L3 requires a distinct re-import archive and native captures")
    if extra is not None:
        replica, logs = extra
        require(native.archive(replica) == b and project_metadata(replica) == project_metadata(result),
                "Independent re-import changed native documents or metadata")
        for board in required:
            other_project, dump = capture_identity(logs, board)
            projects[2].add(other_project)
            check_capture_records(board, dump, b["PCB", native.PCB_IDS[board]])
            require(raw_terminals(dump) == raw_terminals(capture_identity(after_dir, board)[1]),
                    f"{board}: re-import changed bound PCB pads")
            require(signatures(after_drc[board]) == signatures(native.read(logs / f"{board}-drc.json")),
                    f"{board}: re-import changed native DRC objects")
            check_erc_net(board, after_dir, logs)
        require(len(projects[2]) == 1 and projects[2].isdisjoint(projects[1]), "Re-import project was not independent")
    return {"status": "accepted-isolated", "releaseStatus": "NOT FOR FAB",
            "independentReimportVerified": bool(extra),
            "checkpointSha256": native.digest(checkpoint), "postSha256": native.digest(result),
            "planSha256": native.digest(plan_path), "level": plan["level"], "boards": geom,
            "projects": [sorted(p) for p in projects if p], "dfmReviewSha256": native.digest(dfm) if dfm else None}


def check_erc_net(board, left, right):
    require(strict_erc(left / f"{board}-erc.json") == strict_erc(right / f"{board}-erc.json"),
            f"{board}: native ERC objects changed")
    a, b = (native.digest(p / f"{board}.net") for p in (left, right))
    require(a == b, f"{board}: native Protel2 export changed")


def load_reload(path, board, project):
    rr = native.read(path)
    require(rr["status"] == "passed" and rr.get("saved") is True and rr["reloaded"] == native.PCB_IDS[board]
            and rr["finalContext"]["projectUuid"] == project, f"{board}: successful save/reload missing")


def main():
    config = argparse.ArgumentParser(description=__doc__)
    sub = config.add_subparsers(dest="command", required=True)
    lint = sub.add_parser("lint", help="Validate checkpoint and batch intent, no editor calls")
    verify = sub.add_parser("verify", help="Verify native archive diff, captures, DRC/ERC and applicable DFM/reimport")
    for parser in (lint, verify):
        parser.add_argument("--checkpoint", type=Path, required=True)
        parser.add_argument("--plan", type=Path, required=True)
    verify.add_argument("--post", type=Path, required=True)
    verify.add_argument("--baseline-logs", type=Path, required=True)
    verify.add_argument("--after-logs", type=Path, required=True)
    verify.add_argument("--dfm-review", type=Path)
    verify.add_argument("--reimport", type=Path)
    verify.add_argument("--reimport-logs", type=Path)
    verify.add_argument("--out", type=Path, required=True)
    args = config.parse_args()
    if args.command == "lint":
        plan = parse_plan(args.plan, args.checkpoint)
        print(plan["id"], plan["level"], ", ".join(plan["boards"]))
    else:
        require(bool(args.reimport) == bool(args.reimport_logs), "Pass both independent archive and logs")
        extra = None if not args.reimport else (args.reimport, args.reimport_logs)
        outcome = evidence(args.checkpoint, args.post, args.plan, args.baseline_logs,
                           args.after_logs, extra, args.dfm_review)
        require(not args.out.exists(), "Output exists")
        native.write(args.out, outcome)
        print(outcome["status"], outcome["level"], outcome["boards"])


if __name__ == "__main__":
    main()
