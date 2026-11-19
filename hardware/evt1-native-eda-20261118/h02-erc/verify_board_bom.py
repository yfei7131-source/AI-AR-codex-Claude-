#!/usr/bin/env python3
"""Compare unfiltered one-set BOM exports with the archived H02 schematic fields."""

import argparse
import csv
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "h02-native"))
from prepare_hierarchy import Archive, digest
from repair_native_fields import attr_value, part_attrs
from verify_h02 import PR31


def archive_rows(archive):
    records = PR31.read_json(PACKAGE / "h02-native/catalog-plan.json")["records"]
    boards = {board: {} for board in PR31.BOARDS}
    for row in records:
        _, attrs = part_attrs(archive, row)
        board, ref = row["board"], row["cadReference"]
        if ref in boards[board]:
            raise ValueError(f"duplicate controlled component: {board}/{ref}")
        device_uuid = attr_value(attrs, "Device")
        device = archive.documents["DEVICE", device_uuid].one("META").payload["attributes"]
        footprint_uuid = attr_value(attrs, "Footprint") or device.get("Footprint") or ""
        title = archive.documents["FOOTPRINT", footprint_uuid].one("META").payload["title"] if footprint_uuid else ""
        mpn = attr_value(attrs, "Manufacturer Part") or ""
        if mpn != row["controlledManufacturerId"]:
            raise ValueError(f"archived manufacturer part differs from control: {board}/{ref}")
        boards[board][ref] = {
            "board": board, "designator": ref, "source_ref": row["sourceReference"],
            "page_uuid": row["capturePage"], "bom_line": row["bomLine"], "quantity": 1,
            "value": attr_value(attrs, "Value") or "", "manufacturer_part": mpn,
            "manufacturer": attr_value(attrs, "Manufacturer") or "",
            "footprint": title, "footprint_uuid": footprint_uuid, "pcb_use": row["pcbUse"],
            "source_dnp_flag": str(row["sourceDnp"]).lower(),
            "schematic_add_into_bom": attr_value(attrs, "Add into BOM") or "UNSPECIFIED",
            "assembly_status": "BLOCKED",
        }
    return boards


def compare_csv(path, expected):
    if not path.is_file():
        return {"status": "BLOCKED", "reason": "Current board BOM CSV required."}
    file_hash = digest(path)
    try:
        rows = PR31.read_native_bom(path)
        seen, mismatches = set(), []
        for number, row in enumerate(rows, 2):
            required = ("Designator", "Quantity", "Manufacturer Part", "Footprint")
            if None in row or any(not isinstance(row.get(field), str) for field in required):
                raise ValueError(f"line {number}: incomplete or malformed native BOM row")
            refs = [ref.strip() for ref in re.split(r"[,;，；\n]", row["Designator"]) if ref.strip()]
            if not refs or int(row["Quantity"]) != len(refs):
                raise ValueError(f"line {number}: printed quantity differs from designators")
            for ref in refs:
                if ref in seen:
                    raise ValueError(f"duplicate designator: {ref}")
                seen.add(ref)
                if ref not in expected:
                    continue
                wanted = expected[ref]
                observed_mpn = row["Manufacturer Part"].strip()
                if observed_mpn != wanted["manufacturer_part"]:
                    mismatches.append({"designator": ref, "field": "Manufacturer Part",
                                       "expected": wanted["manufacturer_part"], "observed": observed_mpn})
                observed_footprint = row["Footprint"].strip()
                if observed_footprint not in {wanted["footprint"], wanted["footprint_uuid"]}:
                    mismatches.append({"designator": ref, "field": "Footprint",
                                       "expected": wanted["footprint"], "observed": observed_footprint})
    except (ValueError, csv.Error) as error:
        return {"status": "FAIL", "sha256": file_hash, "reason": str(error)}
    missing, extra = sorted(expected.keys() - seen), sorted(seen - expected.keys())
    return {"status": "FAIL" if missing or extra or mismatches else "PASS", "sha256": file_hash,
            "csv_designator_count": len(seen), "missing_designators": missing,
            "extra_designators": extra, "field_mismatches": mismatches}


def write_inventory(folder, boards):
    folder.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for board, components in boards.items():
        path = folder / f"{board}.archive-derived.csv"
        with path.open("x", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=next(iter(components.values())).keys())
            writer.writeheader()
            writer.writerows(components[ref] for ref in sorted(components))
        hashes[board] = digest(path)
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--raw-bom-dir", type=Path, help="board-named CSV files with the English connector columns")
    parser.add_argument("--inventory-dir", type=Path, help="new directory for archive-derived engineering CSVs")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    report = {"scope": "Data comparison for one-set unfiltered board schematic BOMs. "
              "Editor provenance must be verified using original export evidence.", "manufacturing": "BLOCKED"}
    try:
        boards = archive_rows(Archive(args.archive))
        report["archive_sha256"] = digest(args.archive)
        report["boards"] = {}
        for board, components in boards.items():
            raw = compare_csv(args.raw_bom_dir / f"{board}.csv", components) if args.raw_bom_dir else {
                "status": "BLOCKED", "reason": "Current board BOM CSV not supplied."}
            report["boards"][board] = {
                "archived_designator_count": len(components),
                "archived_bound_footprint_count": sum(bool(row["footprint_uuid"]) for row in components.values()),
                "source_dnp_flags": sorted(ref for ref, row in components.items() if row["source_dnp_flag"] == "true"),
                "raw_bom_comparison": raw,
            }
        if args.inventory_dir:
            report["archive_derived_inventory_sha256"] = write_inventory(args.inventory_dir, boards)
        statuses = {row["raw_bom_comparison"]["status"] for row in report["boards"].values()}
        report["status"] = "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
        exit_code = int(args.raw_bom_dir is not None and report["status"] != "PASS")
    except (BadZipFile, KeyError, OSError, ValueError) as error:
        report.update(status="FAIL", error=str(error))
        exit_code = 1
    with args.report.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print(f"{report['status']}: {args.report}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
