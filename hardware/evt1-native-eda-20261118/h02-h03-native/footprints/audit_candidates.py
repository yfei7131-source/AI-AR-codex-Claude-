#!/usr/bin/env python3
"""Cross-reference raw PR #35 findings, controlled terminals, and native donor footprints."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
sys.path.insert(0, str(PACKAGE / "h02-native"))

from prepare_hierarchy import Archive, digest
from repair_native_fields import attr_value, part_attrs
from verify_h02 import parse_protel


PR35 = PACKAGE / "h02-erc"
ROOTS = {"M-MAIN-L": "4d38590959875927", "M-OPT-BRIDGE": "e00fbca5c08cc114", "M-AUD-R": "e98944c2045546cf"}
ARCHIVE = PR35 / "native/ZY_AIAR_EVT1_H02_ERC_L2_D3_NOT_FOR_FAB.epro2"
EXPECTED_SHA = "5984b61b9ada411d0ef9cdb8d735817bd51dfd1ba10fcd3c775b452f79840a37"
MM_PER_MIL = 0.0254
MANUFACTURER_LANDS = {
    "U_AVDD_QUAL": {
        "geometry": "ti-dck0006a.geometry.json", "drawing": "TI 4214835/D 11/2024 DCK0006A",
        "pinoutPage": 3, "outlinePage": 21, "landPage": 22, "stencilPage": 23,
        "bodyMaxMm": [1.40, 2.15, 1.10], "widthMm": 0.90, "heightMm": 0.40, "radiusMm": 0.05,
        "halfRowSpanMm": 1.10, "pitchMm": 0.65,
        "functions": ["CLK", "GND", "D", "Q", "VCC", "CLR"],
        "nets": ["AVDD_D3_VSYS", "GND", "VSYS", "AVDD_PULSE_QUAL", "VSYS", "AVDD_QUAL_CLR_N"],
    },
    "U_AVDD_SCHMITT": {
        "geometry": "ti-dck0006a.geometry.json", "drawing": "TI 4214835/D 11/2024 DCK0006A",
        "pinoutPage": 3, "outlinePage": 20, "landPage": 21, "stencilPage": 22,
        "bodyMaxMm": [1.40, 2.15, 1.10], "widthMm": 0.90, "heightMm": 0.40, "radiusMm": 0.05,
        "halfRowSpanMm": 1.10, "pitchMm": 0.65,
        "functions": ["1A", "GND", "2A", "2Y", "VCC", "1Y"],
        "nets": ["AVDD_PG_NODE", "GND", "AVDD_QUAL_RC", "AVDD_QUAL_CLR_N", "VSYS", "AVDD_PG_OK"],
    },
    "U_AVDD_WD": {
        "geometry": "adi-ltc-s6.geometry.json", "drawing": "Analog Devices LTC DWG 05-08-1636 S6",
        "pinoutPage": 2, "outlinePage": 26, "landPage": 26,
        "bodyWidthMaxMm": 1.75, "bodyLengthReferenceMm": 2.90, "bodyHeightMaxMm": 1,
        "widthMm": 1.22, "heightMm": 0.62, "radiusMm": 0,
        "halfRowSpanMm": 1.31, "pitchMm": 0.95, "landHeightIsManufacturerMaximum": True,
        "functions": ["TRIG", "GND", "SET", "DIV", "V+", "OUT"],
        "nets": ["AVDD_D3_VSYS", "GND", "AVDD_WD_SET", "AVDD_WD_DIV", "VSYS", "AVDD_WD_Q"],
    },
}


def read(path):
    return json.loads(path.read_bytes())


def donor_inventory(archive):
    by_mpn = defaultdict(list)
    for (kind, uuid), doc in archive.documents.items():
        if kind != "DEVICE":
            continue
        meta = doc.one("META").payload
        attrs = meta["attributes"]
        mpn, footprint = attrs.get("Manufacturer Part"), attrs.get("Footprint")
        if not mpn or ("FOOTPRINT", footprint) not in archive.documents or not meta.get("source"):
            continue
        footprint_meta = archive.documents["FOOTPRINT", footprint].one("META").payload
        pads = [r.payload["num"] for r in archive.documents["FOOTPRINT", footprint].records if r.header["type"] == "PAD"]
        by_mpn[mpn.casefold()].append({
            "device": uuid, "deviceSource": meta["source"], "manufacturer": attrs.get("Manufacturer", ""),
            "supplierPart": attrs.get("Supplier Part", ""), "footprint": footprint,
            "footprintName": footprint_meta["title"], "footprintSource": footprint_meta.get("source", ""),
            "uniquePadLabels": sorted(set(pads)), "copperPrimitives": len(pads),
        })
    return by_mpn


def manufacturer_candidate(row, terminals, native_nets, pin_numbers):
    pattern = MANUFACTURER_LANDS[row["sourceReference"]]
    geometry_path = HERE / pattern["geometry"]
    geometry = read(geometry_path)
    pads = {p["number"]: p for p in geometry["pads"]}
    pitch, row_x = (pattern[key] for key in ("pitchMm", "halfRowSpanMm"))
    center_points = [(-row_x, pitch), (-row_x, 0), (-row_x, -pitch),
                     (row_x, -pitch), (row_x, 0), (row_x, pitch)]
    if set(pin_numbers) != set(pads) or len(pads) != len(geometry["pads"]) or len(pads) != len(center_points):
        raise ValueError(f"Pin or pad inventory differs: {row['sourceReference']}")
    pin_map = {}
    for i, ((x, y), function, net) in enumerate(zip(center_points, pattern["functions"], pattern["nets"], strict=True), 1):
        number = str(i)
        pad = pads[number]
        shape, width, height, rounding = pad["shape"]
        if (shape, pad["layer"], pad["rotation"]) != ("RECT", 1, 0):
            raise ValueError(f"Unexpected pad shape/layer/angle: {row['sourceReference']}/{number}")
        actual = [round(v * MM_PER_MIL, 4) for v in (pad["x"], pad["y"], width, height)]
        actual.append(round(rounding * min(actual[-2:]) / 200, 4))
        expected = [x, y, pattern["widthMm"], pattern["heightMm"], pattern["radiusMm"]]
        if actual != expected:
            raise ValueError(f"Manufacturer land does not match geometry: {row['sourceReference']}/{number}")
        ref = row["cadReference"]
        terminal = terminals[row["board"], ref, number]
        if (terminal["Pin_Function"], terminal["CAD_Net"], terminal["Local_State"]) != (function, net, "CONNECTED"):
            raise ValueError(f"Controlled terminal does not match primary pinout: {row['sourceReference']}/{number}")
        if native_nets.get((ref, number)) != [net]:
            raise ValueError(f"Original native board net does not match: {row['sourceReference']}/{number}")
        pin_map[number] = {"function": function, "net": net, "centerMm": [x, y]}
    return {**pattern, "datasheet": row["source"], "geometrySha256": digest(geometry_path),
            "pinOneTopView": "left upper", "verifiedOfflinePins": pin_map,
            "libraryBinding": "PENDING", "maskPasteAndAssembly": "BLOCKED"}


def classify(row):
    if row["pcbUse"] == "EXTERNAL":
        return "OFF_BOARD"
    if row["sourceDnp"]:
        return "DNP"
    if row["sourceReference"] in MANUFACTURER_LANDS:
        return "PRIMARY_LAND_READY"
    if row["footprintSourceStatus"] != "PASS":
        return "SOURCE_FOOTPRINT_BLOCKED"
    if row["controlledManufacturerId"]:
        return "PRIMARY_LAND_PENDING"
    return "PACKAGE_CLASS_ONLY"


def make_report():
    if digest(ARCHIVE) != EXPECTED_SHA:
        raise ValueError("PR #35 native archive hash differs")
    archive = Archive(ARCHIVE)
    catalog = read(PACKAGE / "h02-native/catalog-plan.json")["records"]
    by_primitive = {(r["board"], r["capturePage"], r["capturePrimitiveId"]): r for r in catalog}
    with (PACKAGE / "kicad/CAD_TERMINALS.csv").open(encoding="utf-8-sig", newline="") as stream:
        terminals = {(r["Board"], r["CAD_Reference"], r["Pin"]): r for r in csv.DictReader(stream)}
    donors = donor_inventory(archive)
    records, proxies = [], []
    for board, root in ROOTS.items():
        result = read(PR35 / "evidence" / "erc" / f"{root}.json")["result"]
        if not result["strict"] or not result["detailsAvailable"] or result["passed"]:
            raise ValueError(f"Expected failed strict ERC baseline: {board}")
        _, groups = parse_protel((PR35 / "evidence" / "board-netlists" / f"{board}.net").read_text(encoding="utf-8-sig"))
        native_nets = defaultdict(list)
        for net, members in groups:
            for member in members:
                native_nets[member].append(net)
        for violation in result["violations"]:
            rule = violation["rule"]
            raw, = violation["raw"]["primitives"]
            page, primitive = raw["sheet"], raw["primitiveId"]
            if rule == "ONLYSYMBOL":
                proxies.append((board, page, primitive))
                continue
            if rule != "MISSFOOTPRINT":
                raise ValueError(f"Unexpected baseline rule: {board}/{rule}")
            row = by_primitive[board, page, primitive]
            _, attrs = part_attrs(archive, row)
            device, symbol = (attr_value(attrs, field) for field in ("Device", "Symbol"))
            footprint = archive.documents["DEVICE", device].one("META").payload["attributes"].get("Footprint")
            if footprint or attr_value(attrs, "Footprint") or row["cadReference"] != raw["name"]:
                raise ValueError(f"ERC provenance no longer agrees with controlled instance: {board}/{row['cadReference']}")
            pin_numbers = sorted(r.payload["value"] for r in archive.documents["SYMBOL", symbol].records
                                 if r.header["type"] == "ATTR" and r.payload["key"] == "Pin Number")
            classification = classify(row)
            donor_matches = [{**donor, "labelsMatch": donor["uniquePadLabels"] == pin_numbers}
                             for donor in donors.get(row["controlledManufacturerId"].casefold(), ())]
            record = {
                "board": board, "page": page, "primitive": primitive, "uniqueId": row["captureUniqueId"],
                "ref": row["cadReference"], "sourceRef": row["sourceReference"], "mpn": row["controlledManufacturerId"],
                "nativeDevice": device, "nativeSymbol": symbol, "nativeSymbolPins": pin_numbers,
                "controlledFootprintStatus": row["footprintSourceStatus"], "controlledFootprint": row["kicadFootprint"],
                "sourceDnp": row["sourceDnp"], "class": classification,
                "exactMpnDonorsUnqualified": donor_matches,
            }
            if classification == "PRIMARY_LAND_READY":
                record["candidate"] = manufacturer_candidate(row, terminals, native_nets, pin_numbers)
            if row["sourceReference"] == "Q_CHG_ISO_R":
                record["donorRejection"] = "TECH PUBLIC donor conflicts with controlled Nexperia manufacturer."
            records.append(record)
    by_board = Counter(row["board"] for row in records)
    if len(records) != 250 or len(proxies) != 18 or dict(by_board) != {"M-MAIN-L": 117, "M-OPT-BRIDGE": 81, "M-AUD-R": 52}:
        raise ValueError("PR #35 diagnostic coverage does not match baseline")
    return {
        "baselineSha256": EXPECTED_SHA, "nativeWriteStatus": "UNVERIFIED", "manufacturing": "BLOCKED",
        "boardCounts": dict(by_board), "classCounts": dict(sorted(Counter(row["class"] for row in records).items())),
        "exactMpnDonorObjects": sum(bool(row["exactMpnDonorsUnqualified"]) for row in records),
        "objects": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="reproduce and compare the checked-in evidence")
    args = parser.parse_args()
    report = make_report()
    output = HERE / "candidate-audit.json"
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("FAIL: footprint candidate audit drift")
    else:
        output.write_text(encoded, encoding="utf-8", newline="\n")
    counts = ", ".join(f"{key}={count}" for key, count in report["classCounts"].items())
    print(f"VERIFIED_OFFLINE: 250 raw MISSFOOTPRINT objects; {counts}")


if __name__ == "__main__":
    main()
