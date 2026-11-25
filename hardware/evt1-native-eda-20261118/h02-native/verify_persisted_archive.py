#!/usr/bin/env python3
"""Verify a host-exported H02 archive retains the imported graph and guarded fields."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from zipfile import ZipFile

from prepare_hierarchy import Archive, PACKAGE, PCB_BINDINGS, digest, validate_instances
from repair_native_fields import ASADV_DEVICE, ASADV_FOOTPRINT, attr_value, part_attrs


def contents(archive, kind):
    return {key: [(row.header["type"], row.header.get("id"), row.payload) for row in doc.records[1:]]
            for key, doc in archive.documents.items() if key[0] == kind}


def without_record_order(archive, kind):
    return {key: Counter((record_type, identifier, json.dumps(payload, sort_keys=True))
                         for record_type, identifier, payload in rows)
            for key, rows in contents(archive, kind).items()}


def verify_pins_and_nc(archive, records):
    with (PACKAGE / "kicad/CAD_TERMINALS.csv").open(encoding="utf-8-sig", newline="") as source:
        controlled = {(row["Board"], row["CAD_Reference"], row["Pin"])
                      for row in csv.DictReader(source) if row["Local_State"] in ("CONNECTED", "NC", "LOCAL_NC")}
        source.seek(0)
        controlled_nc = {(row["Board"], row["CAD_Reference"], row["Pin"])
                         for row in csv.DictReader(source) if row["Local_State"] in ("NC", "LOCAL_NC")}
    terminals, markers = set(), set()
    for row in records:
        page, attrs = part_attrs(archive, row)
        primitive = row["capturePrimitiveId"]
        instance, = [r.payload for r in page.records if r.header["type"] == "COMPONENT" and r.header["id"] == primitive]
        symbol = archive.documents["SYMBOL", attr_value(attrs, "Symbol")]
        pins = {r.header["id"] for r in symbol.records if r.header["type"] == "PIN"
                and r.payload["partId"] == instance["partId"]}
        by_number = {r.payload["parentId"]: r.payload["value"] for r in symbol.records if r.header["type"] == "ATTR"
                     and r.payload["key"] == "Pin Number" and r.payload["parentId"] in pins}
        if by_number.keys() != pins or not pins or len(set(by_number.values())) != len(pins):
            raise ValueError(f"incomplete or duplicate native symbol pins for {row['sourceReference']}")
        prefix = primitive + "-"
        nc = [r.payload["parentId"].removeprefix(prefix) for r in page.records if r.header["type"] == "ATTR"
              and r.payload["key"] == "NO_CONNECT" and r.payload.get("value") == "yes"
              and r.payload["parentId"].startswith(prefix)]
        if len(nc) != len(set(nc)) or not set(nc) <= pins:
            raise ValueError(f"invalid native NC identity for {row['sourceReference']}")
        part = (row["board"], row["cadReference"])
        terminals.update((*part, number) for number in by_number.values())
        markers.update((*part, by_number[pin]) for pin in nc)
    archive_markers = sum(r.header["type"] == "ATTR" and r.payload.get("key") == "NO_CONNECT"
                          for key, doc in archive.documents.items() if key[0] == "SCH_PAGE" for r in doc.records)
    if terminals != controlled or markers != controlled_nc or archive_markers != len(markers):
        raise ValueError(f"archived terminal or NC identity differs: {len(terminals ^ controlled)} pins, {len(markers ^ controlled_nc)} NC")
    return len(terminals), len(markers)


def verify(persisted, candidate, evidence):
    for path in (candidate.path, persisted.path):
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"archive failed ZIP CRC: {path.name}")
    form = Counter(kind for kind, _ in persisted.documents)
    if [form[kind] for kind in ("BOARD", "SCH", "SCH_PAGE", "PCB")] != [3, 3, 21, 3]:
        raise ValueError("on-disk native board/schema/page count differs")
    if (validate_instances(persisted) != validate_instances(candidate)
            or without_record_order(persisted, "INSTANCE") != without_record_order(candidate, "INSTANCE")):
        raise ValueError("native hierarchy instance paths differ")
    parent_projections = []
    for archive in (candidate, persisted):
        parent_projections.append({key: doc.one("META").payload["schematic"]
                                   for key, doc in archive.documents.items() if key[0] == "SCH_PAGE"})
    if parent_projections[0] != parent_projections[1]:
        raise ValueError("native page UUID or schematic owner changed")
    if any(persisted.documents["PCB", uuid].one("META").payload["board"] != owner
           for uuid, owner in PCB_BINDINGS.items()):
        raise ValueError("native archive PCB association differs")
    if contents(persisted, "PCB") != contents(candidate, "PCB"):
        raise ValueError("native PCB geometry or rules differ from imported candidate")
    records = json.loads((Path(__file__).parent / "catalog-plan.json").read_bytes())["records"]
    terminal_count, nc_count = verify_pins_and_nc(persisted, records)
    for row in records:
        for archive in (candidate, persisted):
            _, attrs = part_attrs(archive, row)
            if (attr_value(attrs, "Manufacturer Part") or "") != row["controlledManufacturerId"]:
                raise ValueError(f"native catalog field mismatch: {row['sourceReference']}")
    meta = persisted.documents["DEVICE", ASADV_DEVICE].one("META").payload
    if meta["attributes"]["Footprint"] != ASADV_FOOTPRINT or ("FOOTPRINT", ASADV_FOOTPRINT) not in persisted.documents:
        raise ValueError("native ASADV footprint library association missing")
    expected_uuid = json.loads((evidence / "board_pages.json").read_bytes())["project_id"]
    exported_sha = digest(persisted.path)
    receipt = json.loads((evidence / "archive-response.json").read_bytes())
    result = receipt["result"]
    reported_hashes = {result[key] for key in ("artifactSha256", "sha256") if key in result}
    if receipt.get("ok") is not True or result.get("uuid") != expected_uuid or reported_hashes != {exported_sha}:
        raise ValueError("native project archive does not match host export receipt")
    for board, root in {"M-MAIN-L": "4d38590959875927", "M-OPT-BRIDGE": "e00fbca5c08cc114",
                        "M-AUD-R": "e98944c2045546cf"}.items():
        reload_raw = json.loads((evidence / f"reload/{board}.json").read_bytes())
        if not (reload_raw.get("saved") is True and reload_raw.get("closed") is True
                and reload_raw.get("reloaded") == reload_raw.get("target") == root
                and (reload_raw.get("targetContext", {}).get("projectUuid"), reload_raw.get("targetContext", {}).get("documentUuid")) == (expected_uuid, root)
                and (reload_raw.get("finalContext", {}).get("projectUuid"), reload_raw.get("finalContext", {}).get("documentUuid")) == (expected_uuid, root)):
            raise ValueError(f"native save/reload not established for {board}")
    return {"status": "PASS", "scope": "Host export after save/reload; source identity, catalog fields and donor geometry/rules retained.",
            "project_id": expected_uuid, "persisted_sha256": exported_sha, "candidate_sha256": digest(candidate.path),
            "board_count": form["BOARD"], "page_count": form["SCH_PAGE"], "pcb_count": form["PCB"],
            "archived_terminal_identifiers_verified": terminal_count, "archived_explicit_nc_verified": nc_count,
            "catalog_fields_verified": sum(bool(row["controlledManufacturerId"]) for row in records),
            "non_catalog_fields_empty": sum(not row["controlledManufacturerId"] for row in records),
            "asadv_native_footprint_uuid": ASADV_FOOTPRINT, "manufacturing": "BLOCKED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--persisted", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = verify(Archive(args.persisted), Archive(args.candidate), args.capture)
    except (KeyError, OSError, ValueError) as error:
        report = {"status": "FAIL", "error": str(error), "manufacturing": "BLOCKED"}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['status']}: {args.output}")
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
