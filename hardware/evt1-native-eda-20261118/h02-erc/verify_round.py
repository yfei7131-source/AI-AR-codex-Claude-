#!/usr/bin/env python3
"""Check exact native ERC changes, persisted edits, and expected H02 network membership."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from repair_supply_wire_names import BASELINE, ERC, PAGES, ROOTS, records_by_type
from prepare_hierarchy import Archive, digest
from repair_native_fields import attr_value, part_attrs
from verify_h02 import PR31, board_membership, context_ok, inventory
from verify_persisted_archive import verify


def load(path):
    return json.loads(path.read_bytes())


def read_erc(path):
    response = load(path)
    result = response["result"]
    if not (response.get("ok") is True and result["strict"] and result["detailsAvailable"]):
        raise ValueError(f"Unverified strict ERC report: {path}")
    objects = {}
    for item in result["violations"]:
        primitive, = item["raw"]["primitives"]
        key = (item["rule"], primitive["sheet"], primitive["primitiveId"])
        if key in objects:
            raise ValueError(f"Duplicate ERC identity: {key}")
        objects[key] = {"level": item["level"], "name": primitive["name"]}
    if len(objects) != result["summary"]["total"]:
        raise ValueError(f"Incomplete strict ERC report: {path}")
    return objects


def check_erc(capture, manifest, transform, catalog, bindings):
    footprints = {(part["board"], part["capturePage"], part["capturePrimitiveId"]): part for part in catalog}
    planned = {(item["board"], rule, item["page"], item[field])
               for item in transform["wire_net_attribute_edits"]
               for rule, field in (("FLAGTONET", "flag_primitive"), ("PORTTONET", "port_primitive"))}
    binding_refs = {item["sourceReference"] for item in bindings}
    planned.update((board, "MISSFOOTPRINT", page, key) for (board, page, key), part in footprints.items()
                   if part["sourceReference"] in binding_refs)
    proxies = {(item["board"], item["overview"], item["primitive"]): item for item in transform["hierarchy_proxies"]}
    boards = {}
    for board, root in ROOTS.items():
        switch = load(capture / "root" / f"{board}.json")
        project = manifest["project_id"]
        if not switch["ready"] or (switch["active"]["projectUuid"], switch["active"]["documentUuid"]) != (project, root):
            raise ValueError(f"ERC command scope not established for {board}")
        old, new = (read_erc(folder / f"{root}.json") for folder in (ERC, capture / "erc"))
        removed, added = old.keys() - new.keys(), new.keys() - old.keys()
        changed = [key for key in old.keys() & new.keys() if old[key] != new[key]]
        if removed != {item[1:] for item in planned if item[0] == board} or added or changed:
            raise ValueError(f"Unexpected strict ERC delta on {board}: removed={removed}, added={added}, changed={changed}")
        remaining = []
        for (rule, page, key), obj in sorted(new.items()):
            record = {"rule": rule, "page": page, "primitive": key, **obj}
            if rule == "ONLYSYMBOL":
                record.update(cause="Hierarchical sheet proxy", child_page=proxies[board, page, key]["child_page"])
            elif rule == "MISSFOOTPRINT":
                part = footprints[board, page, key]
                record.update(source_ref=part["sourceReference"], pcb_use=part["pcbUse"], dnp=part["sourceDnp"],
                              controlled_mpn=part["controlledManufacturerId"], kicad_footprint=part["kicadFootprint"],
                              source_footprint_status=part["footprintSourceStatus"], state="BLOCKED")
            else:
                raise ValueError(f"Unclassified diagnostic: {board}/{rule}")
            remaining.append(record)
        boards[board] = {
            "strict_status": "FAIL" if new else "PASS",
            "before": dict(sorted(Counter(key[0] for key in old).items())),
            "after": dict(sorted(Counter(key[0] for key in new).items())),
            "removed": [{"rule": rule, "page": page, "primitive": key, **old[rule, page, key]}
                        for rule, page, key in sorted(removed)],
            "remaining": remaining,
        }
    return boards


def check_page_pins(capture, manifest, catalog, terms, required):
    prior = BASELINE / "evidence/native-C/pins"
    pages = []
    for board, uuids in manifest["boards"].items():
        for uuid in uuids:
            receipt = capture / "pins" / f"{uuid}.json"
            if not receipt.is_file() and uuid not in required and (prior / receipt.name).is_file():
                pages.append({"board": board, "page": uuid, "scope": "PR #34 live capture; current archive checked"})
                continue
            data = load(receipt)
            if not context_ok(data, manifest["project_id"], uuid):
                raise ValueError(f"Native pin capture does not describe {uuid}")
            controlled = {row["capturePrimitiveId"]: row for row in catalog if row["capturePage"] == uuid}
            live = {row["primitiveId"]: row for row in data["result"]["components"]}
            pin_count = nc_count = 0
            for key, part in controlled.items():
                component = live[key]
                ref = part["cadReference"]
                expected = {number: row for (b, r, number), row in terms.items() if (b, r) == (board, ref)}
                pins = {str(pin["pinNumber"]): pin for pin in component["pins"]}
                if (component["designator"] != ref or component["uniqueId"] != part["captureUniqueId"]
                        or not component["pinsAvailable"] or len(pins) != len(component["pins"])
                        or set(pins) != set(expected)):
                    raise ValueError(f"Fresh schematic pin identity mismatch: {board}/{ref}")
                for pin, control in expected.items():
                    nc = control["Local_State"] in ("NC", "LOCAL_NC")
                    if pins[pin]["noConnected"] is not nc:
                        raise ValueError(f"Fresh NC marker mismatch: {board}/{ref}.{pin}")
                    nc_count += nc
                pin_count += len(pins)
            pages.append({"board": board, "page": uuid, "scope": "current live capture",
                          "components_checked": len(controlled), "pins_checked": pin_count, "nc_checked": nc_count})
    return pages


def check_footprint(archive, capture, part, binding):
    asset, device = binding["assetId"], binding["deviceId"]
    data = load(capture / "pins" / f"{part['capturePage']}.json")
    live, = (row for row in data["result"]["components"] if row["primitiveId"] == part["capturePrimitiveId"])
    device_attrs = archive.documents["DEVICE", device].one("META").payload["attributes"]
    _, attrs = part_attrs(archive, part)
    dimensions = []
    for row in records_by_type(archive.documents["FOOTPRINT", asset], "PAD").values():
        pad = row.payload
        if (pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["netName"]
                or pad["hole"]["width"] or pad["hole"]["height"] or pad["defaultPad"]["padType"] != "RECT"):
            raise ValueError(f"Unexpected copper primitive on {part['sourceReference']}")
        measured = (pad["centerX"], pad["centerY"], pad["defaultPad"]["width"], pad["defaultPad"]["height"])
        dimensions.append([pad["num"], *(round(v * 0.0254, 3) for v in measured)])
    pin_nets = {pin["pinNumber"]: pin["net"] for pin in live["pins"]}
    if (live["footprint"]["uuid"] != asset or live["manufacturerId"] != binding["mpn"]
            or sorted(dimensions) != sorted(binding["landCopperMm"]) or device_attrs["Footprint"] != asset
            or attr_value(attrs, "Device") != device or pin_nets != binding["terminalContract"]):
        raise ValueError(f"Native binding, copper or pin-to-net differs: {part['sourceReference']}")
    for field, (_, expected) in binding.get("fields", {}).items():
        if expected != attr_value(attrs, field) or expected != device_attrs.get(field):
            raise ValueError(f"Native field did not persist: {part['sourceReference']}/{field}")
    return {**binding, "copper_measured_mm": dimensions, "live_pin_to_net": pin_nets, "pcb_transfer": "BLOCKED"}


def audit(args):
    candidate = Archive(args.candidate)
    archive = Archive(args.persisted)
    capture = args.capture
    transform = load(args.transform)
    catalog = load(BASELINE / "catalog-plan.json")["records"]
    manifest = load(capture / "board_pages.json")
    if digest(candidate.path) != transform["candidate_sha256"]:
        raise ValueError("Transform does not identify the imported archive")
    persistence = verify(archive, candidate, capture)
    for row in transform["wire_net_attribute_edits"]:
        page = archive.documents["SCH_PAGE", row["page"]]
        attr = records_by_type(page, "ATTR")[row["wire_net_attribute"]].payload
        if (attr["parentId"], attr["key"], attr["value"]) != (row["wire"], "NET", row["after"]):
            raise ValueError(f"Wire NET attribute did not persist: {row['wire']}")
    terms, _ = PR31.baseline(BASELINE.parent)
    registered, registry = inventory(capture, manifest)
    graph = board_membership(capture, manifest, terms, registered)
    if (registry["status"] != "PASS" or registry["pcb_document_inventory"]["status"] != "PASS"
            or any(row["status"] != "PASS" for row in graph.values())):
        raise ValueError(f"Board registry or manufacturing net membership changed: {graph}")
    bindings = [transform["footprint_binding"], *transform.get("additional_footprint_bindings", [])]
    required = set(PAGES.values())
    footprints = []
    for binding in bindings:
        part, = (row for row in catalog if row["sourceReference"] == binding["sourceReference"])
        required.add(part["capturePage"])
        footprints.append(check_footprint(archive, capture, part, binding))
    return {
        "status": "VERIFIED",
        "manufacturing": "BLOCKED",
        "persistence": persistence,
        "registry": registry,
        "board_nets": graph,
        "pages": check_page_pins(capture, manifest, catalog, terms, required),
        "footprints": footprints,
        "strict_erc": check_erc(capture, manifest, transform, catalog, bindings),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("candidate", "persisted", "capture", "transform", "output"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args)
    except (KeyError, OSError, ValueError) as error:
        result = {"status": "FAIL", "manufacturing": "BLOCKED", "error": str(error)}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['status']}: {args.output}")
    return int(result["status"] != "VERIFIED")


if __name__ == "__main__":
    sys.exit(main())
