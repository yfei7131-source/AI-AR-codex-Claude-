#!/usr/bin/env python3
"""Derive an isolated native candidate with guarded H02 field and ASADV edits."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
from zipfile import ZipFile

from build_catalog_plan import HERE, read_json
from prepare_hierarchy import Archive, Record, compact, digest, validate_instances


MANUFACTURER_PART = "Manufacturer Part"
ASADV_FOOTPRINT = "f2382a3a65e883d1"
ASADV_DEVICE = "db4214c8d667cb47"
ASADV_DONOR_DEVICE = "fa9efc4fc8fa9870"
ASADV_ORIGIN = "EVT1_Reviewed:Abracon_ASADV_2016-4Pin_2.0x1.6mm"
TOP_COPPER = 1
MIL_TO_MM = 0.0254


def part_attrs(archive, row):
    page = archive.documents["SCH_PAGE", row["capturePage"]]
    component = row["capturePrimitiveId"]
    if sum(r.header["type"] == "COMPONENT" and r.header.get("id") == component for r in page.records) != 1:
        raise ValueError(f"unresolved instance: {page.key}/{component}")
    attrs = {}
    for record in page.records:
        if record.header["type"] != "ATTR" or record.payload.get("parentId") != component:
            continue
        key = record.payload["key"]
        if key in attrs:
            raise ValueError(f"duplicate field: {page.key}/{component}/{key}")
        attrs[key] = record
    expected = {"Designator": row["cadReference"], "Unique ID": row["captureUniqueId"],
                "EVT1 Source Ref": row["sourceReference"], "BOM Line": row["bomLine"]}
    for key, value in expected.items():
        if attr_value(attrs, key) != value:
            raise ValueError(f"controlled identity changed: {page.key}/{component}/{key}")
    return page, attrs


def attr_value(attrs, key):
    return attrs[key].payload.get("value") if key in attrs else None


def add_attr(page, component, key, value, template):
    payload = deepcopy(template)
    z_index = max((r.payload.get("zIndex") or 0 for r in page.records
                   if r.payload.get("parentId") == component), default=0)
    payload.update({"parentId": component, "key": key, "value": value, "zIndex": z_index + 1})
    ticket = max(r.header.get("ticket", 0) for r in page.records) + 1
    identifier = sha256(f"{page.key[1]}/{component}/{key}".encode()).hexdigest()[:16]
    if any(r.header.get("id") == identifier for r in page.records):
        raise ValueError(f"attribute identity already exists: {page.key}/{identifier}")
    header = {"type": "ATTR", "ticket": ticket, "id": identifier}
    record = Record(compact(header) + b"||" + compact(payload) + b"|\n")
    page.records.append(record)
    return record


def guard_and_edit(original, candidate, records):
    template = None
    changes = []
    targets = []
    for row in records:
        original_page, original_attrs = part_attrs(original, row)
        page, attrs = part_attrs(candidate, row)
        for key in ("Device", "Symbol", "MPN", "Value"):
            if attr_value(original_attrs, key) != attr_value(attrs, key):
                raise ValueError(f"candidate A changed protected source field: {page.key}/{key}")
        historical = row["observedManufacturerId"]
        actual = attr_value(attrs, MANUFACTURER_PART)
        if (actual or "") != historical or actual != attr_value(original_attrs, MANUFACTURER_PART):
            raise ValueError(f"manufacturer guard failure: {original_page.key}/{row['cadReference']}")
        if actual and template is None:
            template = attrs[MANUFACTURER_PART].payload
        targets.append((row, page, attrs, actual))
    if template is None or (template["key"], template["x"], template["y"]) != (MANUFACTURER_PART, None, None):
        raise ValueError("no detached native Manufacturer Part attribute template")

    for row, page, attrs, actual in targets:
        desired = row["controlledManufacturerId"]
        action = row["catalogReviewAction"]
        if action == "KEEP_ID" and actual == desired:
            continue
        if action == "KEEP_ID_EMPTY" and not desired and not actual:
            continue
        if action == "CLEAR_LEGACY_DESCRIPTOR_IF_LIVE_MATCHES" and not desired and actual == row["legacyManufacturerIdTarget"]:
            if not actual:
                raise ValueError("empty legacy descriptor guard")
            device = candidate.documents["DEVICE", attr_value(attrs, "Device")]
            if device.one("META").payload["attributes"].get(MANUFACTURER_PART):
                raise ValueError(f"library default may restore a cleared descriptor: {row['sourceReference']}")
            attrs[MANUFACTURER_PART].payload["value"] = ""
            operation = "CLEAR"
        elif action == "RECONCILE_CONTROLLED_ID" and desired and (not actual or actual == row["legacyManufacturerIdTarget"]):
            if MANUFACTURER_PART in attrs:
                attrs[MANUFACTURER_PART].payload["value"] = desired
            else:
                add_attr(page, row["capturePrimitiveId"], MANUFACTURER_PART, desired, template)
            operation = "SET"
        else:
            raise ValueError(f"unsupported manufacturer change: {row['sourceReference']}/{action}")
        changes.append({"board": row["board"], "page": row["capturePage"], "ref": row["sourceReference"],
                        "cad_reference": row["cadReference"], "action": operation, "from": actual, "to": desired})
    return changes


def bind_asadv(candidate, records):
    row, = (row for row in records if row["sourceReference"] == "Y1_OSC" and row["board"] == "M-OPT-BRIDGE")
    page, attrs = part_attrs(candidate, row)
    device = candidate.documents["DEVICE", ASADV_DEVICE].one("META").payload["attributes"]
    donor = candidate.documents["DEVICE", ASADV_DONOR_DEVICE].one("META").payload["attributes"]
    footprint = candidate.documents["FOOTPRINT", ASADV_FOOTPRINT]
    if (attr_value(attrs, "Device"), attr_value(attrs, "MPN"), attr_value(attrs, "Origin Footprint")) != (
        ASADV_DEVICE, "ASADV-48.000MHZ-LC-T", ASADV_ORIGIN
    ) or (device["Symbol"], device["EVT1 Source Ref"], device["Footprint"]) != (
        attr_value(attrs, "Symbol"), "Y1_OSC", ""
    ) or donor["Footprint"] != ASADV_FOOTPRINT:
        raise ValueError(f"unsafe ASADV source, target, or donor: {page.key}")
    placement_count = sum(r.header["type"] == "ATTR" and r.payload.get("key") == "Device" and
                          r.payload.get("value") == ASADV_DEVICE
                          for (kind, _), doc in candidate.documents.items() if kind == "SCH_PAGE" for r in doc.records)
    if placement_count != 1:
        raise ValueError("ASADV target device is not unique on the schematic")
    if footprint.one("META").payload["title"] != ASADV_ORIGIN.split(":")[1] or row["kicadFootprint"] != ASADV_ORIGIN:
        raise ValueError("ASADV footprint does not match reviewed source land")
    pads = [r.payload for r in footprint.records if r.header["type"] == "PAD"]
    expected_centers = {"1": (-0.64, -0.49), "2": (0.64, -0.49), "3": (0.64, 0.49), "4": (-0.64, 0.49)}
    if len(pads) != 4 or {p["num"] for p in pads} != set(row["footprintPins"]) or set(row["footprintPins"]) != expected_centers.keys():
        raise ValueError("unexpected ASADV pad set")
    measurements = {}
    for pad in pads:
        geometry = pad["defaultPad"]
        measured = [pad["centerX"], pad["centerY"], geometry["width"], geometry["height"]]
        measured = [round(value * MIL_TO_MM, 5) for value in measured]
        wanted = (*expected_centers[pad["num"]], 0.88, 0.78)
        if pad["layerId"] != TOP_COPPER or geometry["padType"] != "RECT" or any(
            pad["hole"][axis] != 0 for axis in ("width", "height")
        ) or not all(isclose(a, b, abs_tol=0.001) for a, b in zip(measured, wanted)):
            raise ValueError(f"unexpected original ASADV native geometry: {pad['num']}")
        measurements[pad["num"]] = measured
    if attr_value(attrs, "Footprint"):
        raise ValueError("placed ASADV already has a footprint override")
    # This is the same device metadata association field used by the original donor.
    device["Footprint"] = ASADV_FOOTPRINT
    return {"device": ASADV_DEVICE, "donor_device": ASADV_DONOR_DEVICE, "asset": ASADV_FOOTPRINT,
            "reference": row["sourceReference"], "control_source": ASADV_ORIGIN,
            "pad_center_and_size_mm": measurements, "native_load_and_transfer": "UNVERIFIED"}


def check_postimage(safeguard, output, records, edits, binding):
    if safeguard.documents.keys() != output.documents.keys():
        raise ValueError("document coverage changed")
    changed = []
    edits_by_page = {}
    for edit in edits:
        edits_by_page.setdefault(edit["page"], set()).add(edit["cad_reference"])
    for key, before in safeguard.documents.items():
        after = output.documents[key]
        if before.encode() == after.encode():
            continue
        kind, uuid = key
        if key == ("DEVICE", ASADV_DEVICE):
            rhs = deepcopy(after.one("META").payload)
            if rhs["attributes"].pop("Footprint") != ASADV_FOOTPRINT:
                raise ValueError("ASADV association not persisted")
            lhs = deepcopy(before.one("META").payload)
            lhs["attributes"].pop("Footprint")
            before_other = [r.encode() for r in before.records if r.header["type"] != "META"]
            after_other = [r.encode() for r in after.records if r.header["type"] != "META"]
            if lhs != rhs or before_other != after_other or before.one("META").header != after.one("META").header:
                raise ValueError("unexpected ASADV device metadata edit")
        elif kind == "SCH_PAGE" and uuid in edits_by_page:
            allowed = {
                row["capturePrimitiveId"] for row in records if row["capturePage"] == uuid
                and row["cadReference"] in edits_by_page[uuid]
            }
            def retained(doc):
                return [r.encode() for r in doc.records if not (
                    r.header["type"] == "ATTR" and r.payload.get("key") == MANUFACTURER_PART
                    and r.payload.get("parentId") in allowed
                )]
            if retained(before) != retained(after):
                raise ValueError(f"non-catalog schematic data changed: {key}")
        else:
            raise ValueError(f"unauthorized document edit: {key}")
        changed.append(key)
    if len(changed) != len(edits_by_page) + 1 or not binding:
        raise ValueError("catalog/footprint edit scope mismatch")
    for row in records:
        _, fields = part_attrs(output, row)
        if (attr_value(fields, MANUFACTURER_PART) or "") != row["controlledManufacturerId"]:
            raise ValueError(f"catalog field failed offline round-trip: {row['sourceReference']}")
    for path in (safeguard.path, output.path):
        if not path.is_file():
            raise ValueError("native archive file absent")
    with ZipFile(safeguard.path) as base, ZipFile(output.path) as result:
        if base.namelist() != result.namelist() or any(base.read(name) != result.read(name)
            for name in base.namelist() if name != safeguard.stream):
            raise ValueError("non-schematic ZIP member changed")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.original, args.input, args.output, args.report)}) != 4:
        parser.error("source, input, output and report must be distinct")
    original = Archive(args.original)
    before = Archive(args.input)
    candidate = Archive(args.input)
    sha_original, sha_input = digest(args.original), digest(args.input)
    records = read_json(HERE / "catalog-plan.json")["records"]
    edits = guard_and_edit(original, candidate, records)
    binding = bind_asadv(candidate, records)
    validate_instances(candidate)
    candidate.write(args.output)
    after = Archive(args.output)
    changed = check_postimage(before, after, records, edits, binding)
    if after.encode() != candidate.encode() or (digest(args.original), digest(args.input)) != (sha_original, sha_input):
        raise ValueError("archive round-trip or protected input digest failed")
    report = {
        "offline_archive_check": "PASS",
        "native_import_and_field_readback": "UNVERIFIED",
        "assembly_release": "BLOCKED",
        "original_sha256": sha_original,
        "candidate_a_sha256": sha_input,
        "candidate_b_sha256": digest(args.output),
        "guarded_component_count": len(records),
        "catalog_target_count": sum(bool(row["controlledManufacturerId"]) for row in records),
        "catalog_write_counts": dict(Counter(row["action"] for row in edits)),
        "other_documents_and_zip_members_unchanged": True,
        "changed_documents": changed,
        "asadv_association": binding,
        "source_dnp_not_transferred": [
            row["sourceReference"] for row in records if row["sourceDnp"]
        ],
        "dnp_gate": "BLOCKED: native assembly population semantics and variant readback not verified",
        "catalog_edits": edits,
    }
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"PASS offline candidate B; {report['catalog_write_counts']}; SHA256 {report['candidate_b_sha256']}")


if __name__ == "__main__":
    main()
