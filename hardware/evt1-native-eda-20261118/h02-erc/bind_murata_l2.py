#!/usr/bin/env python3
"""Derive the native, source-reviewed Murata DFE21CCN copper binding for L2."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "h02-native"))
from prepare_hierarchy import Archive, Document, Record, compact, digest
from repair_native_fields import attr_value, part_attrs


BASELINE_SHA = "760cf179ecc0ea545f59ecbafb4466b11bf2677369d2d0eadffb2630ae342a0c"
BASELINE = PACKAGE / "h02-native/native/ZY_AIAR_EVT1_H02_NATIVE_NOT_FOR_FAB.epro2"
ASADV_ASSET = ("FOOTPRINT", "f2382a3a65e883d1")
L2_DEVICE = ("DEVICE", "2c8383e512515cad")
L2_SYMBOL = ("SYMBOL", "e4491303e10c9ece")
MPN = "DFE21CCN2R2MELL"
LAND = "Murata_DFE21CCN_2012_2.0x1.2mm"
ASSET = ("FOOTPRINT", sha256(f"EVT1-reviewed/{LAND}".encode()).hexdigest()[:16])
MURATA_SOURCE = "https://search.murata.co.jp/Ceramy/image/img/P02/JETE243A-0052.pdf"
LAND_COPPER = [("1", -0.8, 0.0, 0.8, 1.4), ("2", 0.8, 0.0, 0.8, 1.4)]
TERMINALS = {"1": "BK_SW", "2": "1V8_SYS"}


def mil(value):
    return round(value / 0.0254, 5)


def rectangle(x, y):
    # EasyEDA native footprint coordinates have positive Y upwards.
    x, y = mil(x), mil(y)
    return [-x, y, "L", -x, -y, x, -y, x, y, -x, y]


def asset_metadata(archive, key):
    return archive.documents[key].one("META").payload


def create_native_footprint(template):
    if template.one("META").payload["title"] != "Abracon_ASADV_2016-4Pin_2.0x1.6mm":
        raise ValueError("native copper template identity drift")
    head = deepcopy(template.one("DOCHEAD"))
    head.payload.update(uuid=ASSET[1], user={"uuid": ASSET[1]})
    footprint = Document(head)
    for raw in template.records[1:]:
        kind = raw.header["type"]
        if kind in {"PAD", "POLY", "FILL"}:
            continue
        record = deepcopy(raw)
        if kind == "META":
            record.payload.update(title=LAND, description=f"JETE243A-0052D-01 section 12.1. {MURATA_SOURCE}", tags=["2012"])
        elif kind == "ATTR":
            if record.payload["key"] == "Name":
                record.payload["value"] = LAND
            elif record.payload["key"] == "Designator":
                record.payload.update(value="L?", x=0, y=mil(1.45))
            else:
                raise ValueError("unreviewed native footprint attribute template")
        footprint.records.append(record)

    def add(kind, payload):
        h = {"type": kind, "ticket": 200 + len(footprint.records), "id": f"l2{len(footprint.records)}"}
        footprint.records.append(Record(compact(h) + b"||" + compact(payload) + b"|\n"))

    polygon, = (r.payload for r in template.records if r.header["type"] == "POLY" and r.payload["layerId"] == 76)
    body = template.one("FILL").payload
    if body["layerId"] != 9 or body["isBridgingCopper"]:
        raise ValueError("native fabrication-layer body template drift")
    add("POLY", dict(polygon, path=rectangle(1.45, 0.95), zIndex=2))
    add("FILL", dict(body, path=[rectangle(1.0, 0.6)], zIndex=3))
    pad, = (r.payload for r in template.records if r.header["type"] == "PAD" and r.payload["num"] == "1")
    if pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["defaultPad"]["padType"] != "RECT":
        raise ValueError("native SMT geometry template drift")
    for number, x, y, width, height in LAND_COPPER:
        default = dict(pad["defaultPad"], width=mil(width), height=mil(height))
        add("PAD", dict(pad, num=number, centerX=mil(x), centerY=mil(y), defaultPad=default, zIndex=3 + int(number)))
    return footprint


def guarded_l2(archive):
    plan = json.loads((PACKAGE / "h02-native/catalog-plan.json").read_text(encoding="utf-8"))
    row, = (r for r in plan["records"] if (r["board"], r["sourceReference"]) == ("M-MAIN-L", "L2_1V8"))
    _, attrs = part_attrs(archive, row)
    device = asset_metadata(archive, L2_DEVICE)["attributes"]
    if (row["controlledManufacturerId"], row["bomLine"], row["kicadFootprint"], row["sourceDnp"]) != (
        MPN, "BOM-09", f"EVT1_Reviewed:{LAND}", False
    ) or (attr_value(attrs, "Device"), attr_value(attrs, "Symbol"), attr_value(attrs, "Manufacturer Part")) != (
        L2_DEVICE[1], L2_SYMBOL[1], MPN
    ) or (device["Symbol"], device["EVT1 Source Ref"], device["Footprint"]) != (L2_SYMBOL[1], "L2_1V8", ""):
        raise ValueError("L2 placement, catalog or unbound asset guard failed")
    pins = [r.payload["value"] for r in archive.documents[L2_SYMBOL].records
            if r.header["type"] == "ATTR" and r.payload["key"] == "Pin Number"]
    if sorted(pins) != sorted(TERMINALS) or sorted(pins) != row["footprintPins"]:
        raise ValueError("L2 effective terminal set differs from actual native symbol")
    count = sum(r.header["type"] == "ATTR" and r.payload.get("key") == "Device" and
                r.payload.get("value") == L2_DEVICE[1]
                for (kind, _), d in archive.documents.items() if kind == "SCH_PAGE" for r in d.records)
    if count != 1 or attr_value(attrs, "Footprint"):
        raise ValueError("L2 footprint replacement would affect a shared or already bound device")
    return device


def bind_l2(archive):
    """Add one internal asset and change exactly one local symbol device binding."""
    device = guarded_l2(archive)
    if ASSET in archive.documents or any(
        doc.one("META").payload["title"] == LAND
        for (kind, _), doc in archive.documents.items() if kind == "FOOTPRINT"
    ):
        raise ValueError("native Murata footprint identity or title already exists")
    footprint = create_native_footprint(archive.documents[ASADV_ASSET])
    document_order = {}
    for key, doc in archive.documents.items():
        if key == ("CONFIG", "CONFIG"):
            document_order[ASSET] = footprint
        document_order[key] = doc
    if ASSET not in document_order:
        raise ValueError("native document ordering anchor absent")
    archive.documents = document_order
    device["Footprint"] = ASSET[1]
    return {"assetId": ASSET[1], "deviceId": L2_DEVICE[1], "sourceReference": "L2_1V8",
            "mpn": MPN, "manufacturerSource": MURATA_SOURCE, "drawing": "JETE243A-0052D-01 §12.1",
            "landCopperMm": LAND_COPPER, "terminalContract": TERMINALS}


def validate_postimage(before, after):
    if after.documents.keys() - before.documents.keys() != {ASSET} or before.documents.keys() - after.documents.keys():
        raise ValueError("native document coverage changed unexpectedly")
    changed = [key for key in before.documents if before.documents[key].encode() != after.documents[key].encode()]
    if changed != [L2_DEVICE]:
        raise ValueError(f"non-L2 native document changed: {changed}")
    lhs, rhs = (deepcopy(asset_metadata(archive, L2_DEVICE)) for archive in (before, after))
    if lhs["attributes"].pop("Footprint") != "" or rhs["attributes"].pop("Footprint") != ASSET[1] or lhs != rhs:
        raise ValueError("unexpected L2 device field edit")
    footprint = after.documents[ASSET]
    lands = [r.payload for r in footprint.records if r.header["type"] == "PAD"]
    measured = []
    for pad in lands:
        point = [pad["centerX"], pad["centerY"], pad["defaultPad"]["width"], pad["defaultPad"]["height"]]
        measured.append((pad["num"], *(round(v * 0.0254, 3) for v in point)))
        if pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["netName"] or pad["hole"]["width"] or pad["hole"]["height"]:
            raise ValueError("Murata was not archived as unassigned top SMT copper")
    if measured != LAND_COPPER or len(set(pad["num"] for pad in lands)) != len(lands):
        raise ValueError(f"Murata copper geometry or unique pad numbers changed: {measured}")
    with ZipFile(before.path) as a, ZipFile(after.path) as b:
        if a.namelist() != b.namelist() or any(a.read(name) != b.read(name) for name in a.namelist() if name != before.stream):
            raise ValueError("non-record ZIP data changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASELINE)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.input, args.output, args.report)}) != 3 or args.report.exists():
        parser.error("input, output and report must be distinct; report must not already exist")
    if digest(args.input) != BASELINE_SHA:
        raise ValueError("input archive is not exactly the PR #34 editor-export baseline")
    candidate = Archive(args.input)
    binding = bind_l2(candidate)
    candidate.write(args.output)
    exported = Archive(args.output)
    validate_postimage(Archive(args.input), exported)
    if exported.encode() != candidate.encode() or digest(args.input) != BASELINE_SHA:
        raise ValueError("native round trip or protected input failed")
    report = {
        "offline_native_footprint": "PASS", "editor_import_readback": "UNVERIFIED",
        "pcb_transfer_drc_and_manufacturing": "BLOCKED", "baselineSha256": BASELINE_SHA,
        "candidateSha256": digest(args.output), "assetsAdded": 1, "deviceBindingsAdded": 1,
        "otherDocumentsUnchanged": True, "binding": binding,
        "excluded": [
            "All JBD, DNP, wire, schematic pin, PCB, stack, solder mask, paste and assembly qualification remain separate.",
            "TI donor land sizes or shape variant differ from controlled or primary examples. No added TI binding in this candidate.",
        ],
    }
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"PASS one new exact native Murata asset and one device binding; {report['candidateSha256']}")


if __name__ == "__main__":
    main()
