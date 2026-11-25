#!/usr/bin/env python3
"""Use the controlled rail names for imported native power-origin flags."""

import argparse
import csv
import json
from pathlib import Path

from prepare_hierarchy import Archive, PACKAGE, digest


PAGES = {"M-MAIN-L": "2d94cb183ed4ccdc", "M-OPT-BRIDGE": "2abf127033234e68", "M-AUD-R": "9e364700c984f124"}


def positions(page):
    attrs = {}
    for record in page.records:
        body = record.payload
        if record.header["type"] == "ATTR":
            properties = attrs.setdefault(body["parentId"], {})
            key = body["key"]
            if key in properties:
                raise ValueError(f"duplicate attribute {key!r} on {page.key}/{body['parentId']}")
            properties[key] = record
    return attrs


def repair(archive):
    with (PACKAGE / "kicad/POWER_ORIGINS.csv").open(encoding="utf-8-sig", newline="") as source:
        mappings = list(csv.DictReader(source))
    if len(mappings) != 11:
        raise ValueError("the reviewed power-origin table must have eleven rows")
    before = {key: doc.encode() for key, doc in archive.documents.items() if key[0] == "SCH_PAGE"}
    changes = []
    for item in mappings:
        board, flag, net = item["Board"], item["KiCad_Flag"], item["Net"]
        page = archive.documents["SCH_PAGE", PAGES[board]]
        attrs = positions(page)
        origin_id, = [key for key, value in attrs.items() if value.get("Designator")
                      and value["Designator"].payload["value"] == flag]
        origin = attrs[origin_id]
        symbol = archive.documents["SYMBOL", origin["Symbol"].payload["value"]]
        name = origin["Name"].payload
        expected = f"EVT1_{flag}_SUPPLY_ORIGIN"
        if symbol.one("META").payload["docType"] != 18 or name["value"] != expected:
            raise ValueError(f"{board}/{flag}: unexpected original native flag identity")
        if not any(row.get("Name") and row["Name"].payload["value"] == net for row in attrs.values()):
            raise ValueError(f"{board}/{flag}: controlled rail is absent from the native supply sheet")
        name["value"] = net
        changes.append({"board": board, "page": page.key[1], "primitive": origin_id,
                        "designator": flag, "prior": expected, "new": net})
    changed_pages = sorted(uuid for kind, uuid in before if archive.documents[kind, uuid].encode() != before[kind, uuid])
    if changed_pages != sorted(PAGES.values()):
        raise ValueError("unexpected page changes")
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        parser.error("choose new output and report paths")
    archive = Archive(args.archive)
    source = digest(args.archive)
    changes = repair(archive)
    archive.write(args.output)
    if digest(args.archive) != source or Archive(args.output).encode() != archive.encode():
        raise ValueError("immutable input or candidate roundtrip check failed")
    report = {"archive_transform": "PASS", "editor_acceptance": "UNVERIFIED", "manufacturing": "BLOCKED",
              "source_sha256": source, "output_sha256": digest(args.output), "renames": changes}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS: repaired {len(changes)} native flag names in isolated archive")


if __name__ == "__main__":
    main()
