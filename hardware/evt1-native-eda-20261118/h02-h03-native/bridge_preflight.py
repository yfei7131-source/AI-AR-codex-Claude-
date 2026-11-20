#!/usr/bin/env python3
"""Audit a native bridge dump, PCB archive, DRC, and D3 placement evidence."""

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path[:0] = [str(PACKAGE / "h02-erc"), str(PACKAGE / "h02-native")]
import bind_kingbright_d3 as led
import bridge_island_trial as trial
from bind_murata_l2 import Archive, asset_metadata
from verify_h02 import parse_protel


geometry = trial.prior
BOARD = "M-OPT-BRIDGE"
PCB = "9ce45f14cb79dc9d"
SCHEMATIC = "73f2bfaeffaf2767"
TOLERANCE_MM = 0.005
TRIAL_EVIDENCE = PACKAGE / "h02-erc/bridge_island_trial.json"
BOARD_NETLIST = PACKAGE / "h02-erc/evidence/board-netlists/M-OPT-BRIDGE.net"
TERM_TABLE = PACKAGE / "kicad/CAD_TERMINALS.csv"
CATALOG = PACKAGE / "h02-native/catalog-plan.json"
CONSTRAINTS = PACKAGE / "PCB_CONSTRAINTS.json"


def load_json(path):
    return json.loads(path.read_bytes())


def verify_bridge_target(board, drc):
    capture = board["capture"]
    if (capture.get("documentUuid"), capture.get("documentType"), capture.get("identityVerified")) != (PCB, "pcb", True):
        raise ValueError("The dump must come from the identity-verified optical bridge PCB")
    if board["componentsAvailability"] != "available" or any(
        board["availability"].get(key) != "available" for key in ("rules", "outline", "components")
    ):
        raise ValueError("The bridge capture misses rules, components or outline")
    if drc["binding"]["pcbUuid"] != PCB or drc["binding"]["schematicUuid"] != SCHEMATIC:
        raise ValueError("The DRC receipt has a different SCH/PCB binding")
    violations = Counter(row["rule"] for row in drc["violations"])
    if violations != drc["counts"] or sum(violations.values()) != drc["total"]:
        raise ValueError("The native DRC counts differ from the listed violations")


def pad_and_link_report(archive, components):
    with TERM_TABLE.open(encoding="utf-8-sig", newline="") as source:
        terms = {(row["CAD_Reference"], row["Pin"]): row for row in csv.DictReader(source)
                 if (row["Board"], row["PCB_Use"]) == (BOARD, "BOARD")}
    instances = {row["cadReference"]: row for row in load_json(CATALOG)["records"] if row["board"] == BOARD}
    _, groups = parse_protel(BOARD_NETLIST.read_text(encoding="utf-8-sig"))
    expected = {}
    for net, members in groups:
        for terminal in members:
            if terminal in expected:
                raise ValueError(f"Ambiguous schematic terminal {terminal}")
            expected[terminal] = net
    pcb_records = {r.header["id"]: r.payload for r in archive.documents[("PCB", PCB)].records
                   if r.header["type"] == "COMPONENT"}
    if pcb_records.keys() != {obj["primitiveId"] for obj in components.values()}:
        raise ValueError("Archive and native dump contain different PCB instances")

    report = []
    for ref, observed in sorted(components.items()):
        identity = observed["primitiveId"]
        source = pcb_records[identity]
        if ((source["layerId"], source["angle"]) != (observed["layer"], observed["rotation"])
                or any(not isclose(source[axis], observed[axis], abs_tol=0.01) for axis in ("x", "y"))):
            raise ValueError(f"Live/archive pose disagreement for {ref}")
        rows, duplicates = [], Counter()
        for pad in observed["pads"]:
            pin, net = pad["padNumber"], pad["net"]
            logical = (ref, pin)
            term = terms[logical]
            if term["Local_State"] not in {"NC", "CONNECTED"} or expected.get(logical, "") != term["CAD_Net"]:
                raise ValueError(f"PR #35 schematic or controlled terminal mismatch for {ref}.{pin}")
            if net != term["CAD_Net"]:
                raise ValueError(f"Native PCB pad mismatch for {ref}.{pin}: {net!r}")
            rows.append({"pad": pin, "net": net, "state": term["Local_State"]})
            duplicates[pin] += 1
        if set(duplicates) != {pin for designator, pin in terms if designator == ref}:
            raise ValueError(f"Missing native PCB pads for {ref}")
        actual_uid = source["attrs"].get("Unique ID", "")
        expected_uid = instances[ref]["captureUniqueId"]
        report.append({"ref": ref, "pcbPrimitiveId": identity, "mpn": observed["device"],
                       "pcbUniqueId": actual_uid, "schematicUniqueId": expected_uid,
                       "uniqueIdMatches": actual_uid == expected_uid and bool(actual_uid), "physicalPads": rows,
                       "repeatedPadNumbers": {pin: count for pin, count in duplicates.items() if count > 1}})
    return report


def led_preflight(archive, components, outline, reserves, copper_edge, gap):
    source = asset_metadata(archive, led.DEVICE)["attributes"]
    _, attrs = led.part_attrs(archive, led.d3_row())
    if (source["Footprint"], led.attr_value(attrs, "Device"), led.attr_value(attrs, "Manufacturer Part")) != (
        led.ASSET[1], led.DEVICE[1], led.MPN
    ):
        raise ValueError("D3 SCH device and native footprint identities differ from the controlled binding")
    doc = archive.documents[led.ASSET]
    pads = sorted((r.payload for r in doc.records if r.header["type"] == "PAD"), key=lambda r: r["num"])
    found = [(p["num"], *(round(v * geometry.MIL, 4) for v in (
        p["centerX"], p["centerY"], p["defaultPad"]["width"], p["defaultPad"]["height"]))) for p in pads]
    if found != sorted(led.LAND_COPPER) or any(
        (p["layerId"], p["padAngle"], p["defaultPad"]["padType"], p["hole"]["width"], p["hole"]["height"])
        != (1, 0, "RECT", 0, 0) for p in pads
    ):
        raise ValueError("D3 native footprint differs from the controlled manufacturer data")

    projected = load_json(TRIAL_EVIDENCE)["privacyLedProjection"]
    x, y = trial.center(geometry.Box(*projected["originalNominalBodyMm"]))
    layer = 1
    rotation = 90
    mechanical, = (r.payload for r in doc.records if r.header["type"] == "POLY" and r.payload["layerId"] == 76)
    coords = [v * geometry.MIL for v in mechanical["path"] if isinstance(v, (float, int))]
    xs, ys = coords[::2], coords[1::2]
    guard = geometry.Box(min(xs), min(ys), max(xs), max(ys)).rotated().translated(x, y)
    pad_boxes = {}
    for pin, px, py, w, h in found:
        local = geometry.Box(px - w/2, py - h/2, px + w/2, py + h/2)
        pad_boxes[pin] = local.rotated().translated(x, y)
    copper = geometry.bbox_union(list(pad_boxes.values()))
    d3 = components.get("D3")
    if d3:
        if (d3["layer"], d3["rotation"]) != (layer, rotation) or any(
            not isclose(d3[axis] * geometry.MIL, mm, abs_tol=TOLERANCE_MM) for axis, mm in (("x", x), ("y", y))
        ):
            raise ValueError("Native D3 placement differs from the preflight target")
        actual = {row["padNumber"]: geometry.pad_box(row) for row in d3["pads"]}
        if actual.keys() != pad_boxes.keys() or any(
            not isclose(a, b, abs_tol=TOLERANCE_MM) for pin in actual
            for a, b in zip(actual[pin].values(), pad_boxes[pin].values())
        ):
            raise ValueError("Native D3 pad boxes differ from the projected lands")
        copper = geometry.bbox_union(list(actual.values()))
        guard = geometry.bbox_union((guard, geometry.mm_box(d3["bbox"], geometry.MIL)))

    top_peers = [trial.native_pose(ref, row).occupied for ref, row in components.items()
                 if ref != "D3" and row["layer"] == layer]
    nearest_body = min(guard.gap(other) for other in top_peers)
    nearest_keepout = min(guard.gap(box) for _, box in reserves[layer])
    if (outline.inset(copper) < copper_edge or outline.inset(guard) < 0 or nearest_body < gap
            or any(guard.intersect_keepout(box, gap) for _, box in reserves[layer])):
        raise ValueError("D3 fails the observed footprint/copper/keepout preflight")
    return {"status": "NATIVE_POSE_VERIFIED" if d3 else "PREFLIGHT_ONLY", "designator": "D3", "manufacturerPart": led.MPN,
            "deviceId": led.DEVICE[1], "footprintId": led.ASSET[1],
            "schematicUniqueId": led.attr_value(attrs, "Unique ID"), "netByPad": led.TERMINALS,
            "anchorMm": [round(x, 6), round(y, 6)], "anchorMil": [round(x / geometry.MIL, 6), round(y / geometry.MIL, 6)],
            "layer": layer, "angleDegrees": rotation, "landCopperMm": {pin: geometry.rounded(b) for pin, b in pad_boxes.items()},
            "occupiedBoxMm": geometry.rounded(guard), "minimumCopperEdgeMm": round(outline.inset(copper), 6),
            "nearestExistingTopComponentMm": round(nearest_body, 6), "nearestTopReservationMm": round(nearest_keepout, 6)}


def optical_keepout_plan(outline, top_reserves, top_parts, gap):
    planned = []
    for name, reserve in top_reserves:
        if name not in {"J_DISP_L_FPC_CORRIDOR", "J_DISP_R_FPC_CORRIDOR"}:
            continue
        corridor = geometry.Box(max(reserve.x0, outline.x0), reserve.y0, min(reserve.x1, outline.x1), reserve.y1)
        clearance, nearest = min((corridor.gap(bounds), ref) for ref, bounds in top_parts)
        if outline.inset(corridor) < 0 or clearance < gap:
            raise ValueError(f"{name} conflicts with occupied TOP board geometry")
        planned.append({"purpose": name, "pcbLayer": 1, "rule": "no-components",
                        "rectMil": [round(mm / geometry.MIL, 6) for mm in corridor.values()],
                        "nearestPlacedPart": nearest, "minSameSideGapMm": round(clearance, 6)})
    if len(planned) != 2:
        raise ValueError("Missing one or both original optical FPC corridors")
    return planned


def readback_keepouts(board, archive, planned, required):
    if board["availability"].get("copper") != "available":
        if required:
            raise ValueError("The post-reload dump must include native region geometry")
        return {"status": "NOT_CAPTURED"}
    regions = board["copper"]["regions"]
    written = []
    for target in planned:
        x0, y0, x1, y1 = target["rectMil"]
        polygon = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        matches = []
        for row in regions:
            path = row.get("source", [])
            if not (row.get("geometryAvailable") and row["layer"] == 1 and row["ruleType"] == [2]
                    and row["locked"] is True and len(path) == 11 and path[2] == "L"):
                continue
            points = path[:2] + path[3:]
            if points[:2] != points[-2:]:
                continue
            seen = sorted(zip(points[0:-2:2], points[1:-2:2]))
            if all(isclose(a, b, abs_tol=0.01) for p, q in zip(seen, sorted(polygon)) for a, b in zip(p, q)):
                matches.append(row)
        if len(matches) > 1 or (required and len(matches) != 1):
            raise ValueError(f"Expected one native region for {target['purpose']}")
        if matches:
            row = matches[0]
            written.append({**target, "nativePrimitiveId": row["primitiveId"], "locked": row["locked"],
                            "nativeClosedPathMil": row["source"]})
    if required:
        records = {r.header["id"]: r.payload for r in archive.documents[("PCB", PCB)].records
                   if r.header["type"] == "REGION"}
        for row in written:
            source = records.get(row["nativePrimitiveId"], {})
            if (source.get("layerId"), source.get("prohibitType"), source.get("path"), source.get("locked")) != (
                1, ["COMPONENT"], [row["nativeClosedPathMil"]], True
            ):
                raise ValueError(f"Editable archive region differs from readback: {row['purpose']}")
    return {"status": "CAPTURED", "regionsObserved": len(regions), "matchingLockedRegions": written}


def microphone_slot(archive, row):
    # The archived production part choice supplies the local source identity.
    footprint = ("FOOTPRINT", "46f530bc0d70e19b")
    source = asset_metadata(archive, ("DEVICE", "79563a076c33f9d7"))["attributes"]
    if (source["Footprint"], source["Manufacturer Part"]) != (footprint[1], row["device"]):
        raise ValueError("The captured MK2 definition no longer matches the optical bridge part")
    record, = (r for r in archive.documents[footprint].records if r.header.get("id") == "e26")
    shape, x, y, radius = record.payload["path"]
    if (record.header["type"], shape, record.payload["layerId"]) != ("FILL", "CIRCLE", 12):
        raise ValueError("The MK2 sound-port definition changed")
    return {"footprintId": footprint[1], "pcbSlotId": row["primitiveId"] + "e26", "shape": shape,
            "localCenterMil": [x, y], "radiusMil": radius,
            "observedDiameterMm": round(2 * radius * geometry.MIL, 6),
            "manufacturerRecommendedPcbPortDiameterMm": 0.8,
            "manufacturerSource": "https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf",
            "manufacturerFigure": "Section 7 and Fig. 12"}


def compare_keepout_round(before, after, before_drc, after_drc):
    for key in ("project", "outline", "rules", "copperLayers", "routedLines", "silk"):
        if before[key] != after[key]:
            raise ValueError(f"Bridge {key} changed during the optical keepout operation")
    if geometry.components(before) != geometry.components(after):
        raise ValueError("A bridge component or pad changed during the optical keepout operation")
    if len(after["copper"]["regions"]) - len(before.get("copper", {}).get("regions", [])) != 2:
        raise ValueError("The bridge region count did not increase by exactly two")

    def violations(check):
        return Counter(json.dumps({k: v for k, v in row.items() if k != "globalIndex"}, sort_keys=True)
                       for row in check["violations"])

    if before_drc["passed"] != after_drc["passed"] or violations(before_drc) != violations(after_drc):
        raise ValueError("The strict native DRC violation set changed")
    return {"existingComponentsPadsAndSilkUnchanged": True, "outlineAndRulesUnchanged": True,
            "routedLinesUnchanged": True, "strictViolationSetUnchanged": True,
            "newRegions": 2, "scope": "Existing component and pad raw fields; DRC entries compared modulo list order and globalIndex."}


def audit(dump_path, archive_path, drc_path, require_keepouts=False):
    board, drc, archive = load_json(dump_path), load_json(drc_path), Archive(archive_path)
    verify_bridge_target(board, drc)
    spec = load_json(CONSTRAINTS)
    baseline = load_json(trial.BRIDGE_AUDIT)
    outline = geometry.validate_outline(board, spec["boards"][BOARD])
    copper_edge = max(spec["do_not_relax"]["minimum_edge_clearance_mm"], board["rules"]["copperToEdgeMil"] * geometry.MIL)
    gap = spec["do_not_relax"]["minimum_courtyard_gap_mm"]
    components = geometry.components(board)
    mapping = pad_and_link_report(archive, components)
    reserves = {side: [(r["ref"], geometry.Box(*r["boxMm"])) for r in baseline["reservations"] if r["layer"] == side]
                for side in (1, 2)}
    d3 = led_preflight(archive, components, outline, reserves, copper_edge, gap)
    reserves[1].append(("D3_PRIV", geometry.Box(*d3["occupiedBoxMm"])))
    placed = {side: [(ref, trial.native_pose(ref, row).occupied) for ref, row in components.items() if row["layer"] == side]
              for side in (1, 2)}
    keepouts = optical_keepout_plan(outline, reserves[1], placed[1], gap)
    sources = trial.read_sources()
    sources["restored"] = board
    u8 = geometry.search("U8", trial.with_reverse_angles(geometry.templates(sources)["U8"]),
                         outline, placed, reserves, copper_edge, gap)
    v = drc["violations"]
    return {"scope": "Native partial PCB pose and visible pad nets; prior keepouts and exact D3 footprint projection.",
            "manufacturing": "BLOCKED", "projectUuid": board["project"], "documentUuid": PCB,
            "inputSha256": {label: sha256(path.read_bytes()).hexdigest() for label, path in (
                ("dump", dump_path), ("archive", archive_path), ("drc", drc_path), ("schematicNetlist", BOARD_NETLIST),
                ("cadTerminals", TERM_TABLE), ("constraintManifest", CONSTRAINTS), ("PR35Geometry", TRIAL_EVIDENCE),
                ("PR32Geometry", trial.BRIDGE_AUDIT))},
            "observedComponentCount": len(components),
            "observedPhysicalPads": dict(Counter(p["state"] for r in mapping for p in r["physicalPads"])),
            "visiblePadNetAgreement": "PASS", "nativeComponents": mapping,
            "unmatchedLinkRefs": [r["ref"] for r in mapping if not r["uniqueIdMatches"]],
            "nativeDRC": {"passed": drc["passed"], "ruleCounts": drc["counts"], "total": drc["total"],
                          "acousticSlotClearance": [r for r in v if "Slot Region" in r["objType"]],
                          "netlistErrors": [r for r in v if r["rule"] == "Netlist Error"]},
            "microphoneSlot": microphone_slot(archive, components["MK2"]),
            "d3": d3, "plannedTopOpticalFpcKeepouts": keepouts,
            "nativeTopOpticalFpcKeepouts": readback_keepouts(board, archive, keepouts, require_keepouts),
            "u8RetainingOriginalInterfaceReservations": u8,
            "copperCoverage": board["availability"].get("copper"), "routedLines": board["routedLines"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--require-keepouts", action="store_true", help="Require both optical keepouts in the dump and archive")
    parser.add_argument("--before-dump", type=Path)
    parser.add_argument("--before-drc", type=Path)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path)
    output.add_argument("--check", type=Path)
    args = parser.parse_args()
    if bool(args.before_dump) != bool(args.before_drc):
        parser.error("--before-dump and --before-drc must be supplied together")
    result = audit(args.dump, args.archive, args.drc, args.require_keepouts)
    if args.before_dump:
        result["inputSha256"].update({"beforeDump": sha256(args.before_dump.read_bytes()).hexdigest(),
                                      "beforeDrc": sha256(args.before_drc.read_bytes()).hexdigest()})
        result["beforeAfter"] = compare_keepout_round(load_json(args.before_dump), load_json(args.dump),
                                                    load_json(args.before_drc), load_json(args.drc))
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check and args.check.read_bytes() != encoded:
        raise SystemExit("Bridge preflight evidence differs")
    if args.output:
        with args.output.open("xb") as stream:
            stream.write(encoded)
    keepouts = result["nativeTopOpticalFpcKeepouts"].get("matchingLockedRegions", [])
    print(f"Bridge pad/net agreement: {result['observedPhysicalPads']}; D3: {result['d3']['status']}; "
          f"matched keepouts: {len(keepouts)}; strict native DRC: {result['nativeDRC']['passed']}; manufacturing BLOCKED.")


if __name__ == "__main__":
    main()
