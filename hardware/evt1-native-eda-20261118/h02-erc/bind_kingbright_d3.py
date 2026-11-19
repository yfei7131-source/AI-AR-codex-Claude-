#!/usr/bin/env python3
"""Derive the native Kingbright APHD1608LCGCK copper binding for D3."""

import argparse
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from bind_murata_l2 import ASADV_ASSET, BASELINE, BASELINE_SHA, PACKAGE, asset_metadata, mil, rectangle
from prepare_hierarchy import Archive, Document, Record, compact, digest
from repair_native_fields import attr_value, part_attrs


SOURCE_REF = "D3_PRIV"
MPN = "APHD1608LCGCK"
LEGACY_MPN = "APHD1608LZGCK (or WP710A10LID)"
LEGACY_URL = "https://www.kingbrightusa.com/images/catalog/SPEC/WP710A10LID.pdf"
SOURCE = "https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf"
LAND = "Kingbright_APHD1608LCGCK_1608"
ASSET = ("FOOTPRINT", sha256(f"EVT1-reviewed/{LAND}".encode()).hexdigest()[:16])
DEVICE = ("DEVICE", "1c28d1d16e4e1c73")
SYMBOL = ("SYMBOL", "e8d00c0a7c5ed55d")
PAGE = ("SCH_PAGE", "a7f2cc2b0cf16956")
PRIMITIVE = "ie200"
TERMINALS = {"K": "GND", "A": "PRIV_LED_ANODE"}
MANUFACTURER_PINS = {"1": "K", "2": "A"}
LAND_COPPER = [("K", -0.75, 0.0, 0.70, 0.80), ("A", 0.75, 0.0, 0.70, 0.80)]
FIELD_EDITS = {"MPN": (LEGACY_MPN, MPN), "UserDocLink": (LEGACY_URL, SOURCE)}


def d3_row():
    plan = json.loads((PACKAGE / "h02-native/catalog-plan.json").read_text(encoding="utf-8"))
    row, = (r for r in plan["records"] if (r["board"], r["sourceReference"]) == ("M-OPT-BRIDGE", SOURCE_REF))
    identity = tuple(row[k] for k in (
        "capturePage", "capturePrimitiveId", "captureUniqueId", "cadReference", "bomLine",
        "controlledManufacturerId", "sourceDnp"))
    if identity != (PAGE[1], PRIMITIVE, "81689f1d3303caec", "D3", "BOM-25", MPN, False):
        raise ValueError("D3 controlled catalog identity has changed")
    with (PACKAGE / "Inputs/effective_bom.csv").open(encoding="utf-8-sig", newline="") as stream:
        part, = (r for r in csv.DictReader(stream) if r["Item_ID"] == row["bomLine"])
    if (part["RefDes"], part["Board_Zone"], part["MPN"], part["Datasheet_URL"]) != (
        SOURCE_REF, "M-OPT-BRIDGE", MPN, SOURCE
    ):
        raise ValueError("D3 controlled BOM no longer identifies this device and drawing")
    return row


def check_terminal_contract():
    with (PACKAGE / "Inputs/effective_netlist.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = [r for r in csv.DictReader(stream)
                if (r["Board"], r["RefDes"]) == ("M-OPT-BRIDGE", SOURCE_REF)]
    if len(rows) != len(TERMINALS) or {r["Pin"]: r["Net"] for r in rows} != TERMINALS:
        raise ValueError("D3 effective netlist has changed")


def guarded_d3(archive):
    _, attrs = part_attrs(archive, d3_row())
    if tuple(attr_value(attrs, key) for key in ("Device", "Symbol", "Manufacturer Part", "Footprint")) != (
        DEVICE[1], SYMBOL[1], MPN, None
    ):
        raise ValueError("D3 instance binding identity has changed")
    device = asset_metadata(archive, DEVICE)["attributes"]
    if (device["Symbol"], device["EVT1 Source Ref"], device["Footprint"]) != (SYMBOL[1], SOURCE_REF, ""):
        raise ValueError("D3 device identity has changed or is already bound")
    for field, (old, _) in FIELD_EDITS.items():
        if attr_value(attrs, field) != old or device.get(field) != old:
            raise ValueError(f"D3 source metadata does not match the expected legacy value: {field}")
    pins = [r.payload["value"] for r in archive.documents[SYMBOL].records
            if r.header["type"] == "ATTR" and r.payload["key"] == "Pin Number"]
    if sorted(pins) != sorted(TERMINALS):
        raise ValueError("D3 symbol no longer uses the controlled K and A pins")
    placements = sum(r.header["type"] == "ATTR" and r.payload.get("key") == "Device"
                     and r.payload.get("value") == DEVICE[1]
                     for (kind, _), d in archive.documents.items() if kind == "SCH_PAGE" for r in d.records)
    if placements != 1:
        raise ValueError("The local D3 device is shared by other placed objects")
    check_terminal_contract()
    return attrs, device


def create_footprint(template):
    if template.one("META").payload["title"] != "Abracon_ASADV_2016-4Pin_2.0x1.6mm":
        raise ValueError("native SMT template identity changed")
    head = deepcopy(template.one("DOCHEAD"))
    head.payload.update(uuid=ASSET[1], user={"uuid": ASSET[1]})
    footprint = Document(head)
    for original in template.records[1:]:
        if original.header["type"] in {"PAD", "POLY", "FILL"}:
            continue
        record = deepcopy(original)
        if record.header["type"] == "META":
            record.payload.update(title=LAND, description=f"Kingbright V.4B page 1. {SOURCE}", tags=["1608"])
        elif record.header["type"] == "ATTR":
            if record.payload["key"] == "Name":
                record.payload["value"] = LAND
            elif record.payload["key"] == "Designator":
                record.payload.update(value="D?", x=0, y=mil(1.10))
            else:
                raise ValueError("unreviewed native footprint template attribute")
        footprint.records.append(record)

    def add(kind, payload):
        index = len(footprint.records)
        header = {"type": kind, "ticket": 200 + index, "id": f"d3{index}"}
        footprint.records.append(Record(compact(header) + b"||" + compact(payload) + b"|\n"))

    outline, = (r.payload for r in template.records if r.header["type"] == "POLY" and r.payload["layerId"] == 76)
    body = template.one("FILL").payload
    if body["layerId"] != 9 or body["isBridgingCopper"]:
        raise ValueError("native non-copper body template changed")
    add("POLY", dict(outline, path=rectangle(1.35, 0.65), zIndex=2))
    add("FILL", dict(body, path=[rectangle(0.80, 0.40)], zIndex=3))
    pad, = (r.payload for r in template.records if r.header["type"] == "PAD" and r.payload["num"] == "1")
    if pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["defaultPad"]["padType"] != "RECT":
        raise ValueError("native rectangular SMT pad template changed")
    for index, (number, x, y, width, height) in enumerate(LAND_COPPER, start=4):
        shape = dict(pad["defaultPad"], width=mil(width), height=mil(height))
        add("PAD", dict(pad, num=number, centerX=mil(x), centerY=mil(y), defaultPad=shape, zIndex=index))
    return footprint


def bind_d3(archive):
    attrs, device = guarded_d3(archive)
    if ASSET in archive.documents or any(
        doc.one("META").payload["title"] == LAND
        for (kind, _), doc in archive.documents.items() if kind == "FOOTPRINT"
    ):
        raise ValueError("D3 footprint identity already exists")
    footprint = create_footprint(archive.documents[ASADV_ASSET])
    ordered = {}
    for key, doc in archive.documents.items():
        if key == ("CONFIG", "CONFIG"):
            ordered[ASSET] = footprint
        ordered[key] = doc
    if ASSET not in ordered:
        raise ValueError("native document ordering anchor absent")
    archive.documents = ordered
    for field, (_, desired) in FIELD_EDITS.items():
        attrs[field].payload["value"] = desired
        device[field] = desired
    device["Footprint"] = ASSET[1]
    return {"assetId": ASSET[1], "deviceId": DEVICE[1], "sourceReference": SOURCE_REF, "mpn": MPN,
            "manufacturerSource": SOURCE, "drawing": "DSAO7428 / 1203015409 V.4B p. 1",
            "landCopperMm": LAND_COPPER, "manufacturerPins": MANUFACTURER_PINS, "terminalContract": TERMINALS,
            "fields": FIELD_EDITS}


def validate_d3_postimage(before, after):
    if after.documents.keys() - before.documents.keys() != {ASSET} or before.documents.keys() - after.documents.keys():
        raise ValueError("unexpected archive document coverage change")
    changed = {key for key in before.documents if before.documents[key].encode() != after.documents[key].encode()}
    if changed != {PAGE, DEVICE}:
        raise ValueError(f"unexpected D3 document diff: {changed}")
    lhs, rhs = (deepcopy(asset_metadata(a, DEVICE)) for a in (before, after))
    for key, (old, new) in {**FIELD_EDITS, "Footprint": ("", ASSET[1])}.items():
        if lhs["attributes"].pop(key) != old or rhs["attributes"].pop(key) != new:
            raise ValueError(f"unexpected D3 device field edit: {key}")
    if lhs != rhs:
        raise ValueError("non-D3 device metadata changed")
    row = d3_row()
    page_before, _ = part_attrs(before, row)
    page_after, attrs = part_attrs(after, row)
    restored = deepcopy(page_after)
    changed_ids = {attrs[field].header["id"]: values for field, values in FIELD_EDITS.items()}
    for record in restored.records:
        if record.header.get("id") in changed_ids:
            old, new = changed_ids[record.header["id"]]
            if record.payload.get("value") != new or record.payload.get("parentId") != PRIMITIVE:
                raise ValueError("D3 schematic field edit disagrees with the scope or source")
            record.payload["value"] = old
    if [r.header for r in restored.records] != [r.header for r in page_before.records] or (
        [r.payload for r in restored.records] != [r.payload for r in page_before.records]
    ):
        raise ValueError("D3 schematic elements other than the two legacy fields changed")
    pads = [r.payload for r in after.documents[ASSET].records if r.header["type"] == "PAD"]
    measured = []
    for pad in pads:
        geom = [pad["centerX"], pad["centerY"], pad["defaultPad"]["width"], pad["defaultPad"]["height"]]
        measured.append((pad["num"], *(round(v * 0.0254, 3) for v in geom)))
        if pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["defaultPad"]["padType"] != "RECT" or (
            pad["netName"] or pad["hole"]["width"] or pad["hole"]["height"]
        ):
            raise ValueError("D3 lands are not unassigned top-side rectangular SMT copper")
    if measured != LAND_COPPER or MANUFACTURER_PINS != {"1": measured[0][0], "2": measured[1][0]}:
        raise ValueError(f"D3 pad geometry or polarity changed: {measured}")
    with ZipFile(before.path) as a, ZipFile(after.path) as b:
        if a.namelist() != b.namelist() or any(a.read(name) != b.read(name) for name in a.namelist() if name != before.stream):
            raise ValueError("non-record archive data changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASELINE)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.input, args.output, args.report)}) != 3 or args.report.exists():
        parser.error("input, output and report must be distinct and report must be new")
    if digest(args.input) != BASELINE_SHA:
        raise ValueError("input differs from the PR #34 editor archive")
    candidate = Archive(args.input)
    binding = bind_d3(candidate)
    candidate.write(args.output)
    output = Archive(args.output)
    validate_d3_postimage(Archive(args.input), output)
    if output.encode() != candidate.encode():
        raise ValueError("D3 archive round trip changed encoded records")
    report = {"offline_native_footprint": "PASS", "editor_import_readback": "UNVERIFIED",
              "pcb_transfer_drc_and_manufacturing": "BLOCKED", "baselineSha256": BASELINE_SHA,
              "candidateSha256": digest(args.output), "binding": binding}
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"PASS one Kingbright native footprint binding and two corrected D3 source fields; {report['candidateSha256']}")


if __name__ == "__main__":
    main()
