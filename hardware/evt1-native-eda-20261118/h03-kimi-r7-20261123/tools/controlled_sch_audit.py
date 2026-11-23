#!/usr/bin/env python3
"""Audit controlled schematic terminals without assuming globally unique PIDs/UIDs."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def controlled_terminal_audit(native, catalog, *, strict=True):
    components, attrs = {}, defaultdict(dict)
    for key, page in native.documents.items():
        if key[0] != "SCH_PAGE":
            continue
        for record in page:
            if record.header["type"] == "COMPONENT":
                components[(key[1], record.header["id"])] = record.payload
            elif record.header["type"] == "ATTR":
                payload = record.payload
                identity = (key[1], payload["parentId"])
                key_name = payload.get("key")
                if key_name in attrs[identity]:
                    raise ValueError(f"Duplicate native attribute {identity}/{key_name}")
                attrs[identity][key_name] = payload.get("value")
    by_source, by_uid = defaultdict(list), defaultdict(list)
    for identity in components:
        source = attrs[identity].get("EVT1 Source Ref")
        uid = attrs[identity].get("Unique ID")
        if source:
            by_source[source].append(identity)
        if uid:
            by_uid[uid].append(identity)
    controlled_nc, controlled = set(), set()
    package = Path(__file__).resolve().parents[2]
    with (package / "kicad/CAD_TERMINALS.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            item = (row["Board"], row["CAD_Reference"], row["Pin"])
            if row["Local_State"] in ("CONNECTED", "NC", "LOCAL_NC"):
                controlled.add(item)
            if row["Local_State"] in ("NC", "LOCAL_NC"):
                controlled_nc.add(item)
    terminals, markers, resolved, unresolved = set(), set(), [], []
    for row in catalog:
        matches = by_source.get(row["sourceReference"], [])
        match_kind = "controlled-source-reference"
        if len(matches) != 1:
            # Only use page+UID+designator when the stable source reference is
            # absent; this also disambiguates the controlled BAT1 duplicates.
            matches = [identity for identity in by_uid.get(row["captureUniqueId"], [])
                       if identity[0] == row["capturePage"]
                       and attrs[identity].get("Designator") == row["cadReference"]]
            match_kind = "controlled-page-uid-designator-fallback"
        if len(matches) != 1:
            unresolved.append({"sourceReference": row["sourceReference"], "board": row["board"],
                               "designator": row["cadReference"], "capturePage": row["capturePage"],
                               "captureUniqueId": row["captureUniqueId"], "candidateIdentities": matches})
            continue
        page_uuid, primitive = matches[0]
        identity = (page_uuid, primitive)
        fields = attrs[identity]
        if (fields.get("Designator") != row["cadReference"]
                or fields.get("Unique ID") != row["captureUniqueId"]
                or (fields.get("EVT1 Source Ref") is not None
                    and fields["EVT1 Source Ref"] != row["sourceReference"])):
            raise ValueError(f"Controlled identity mismatch: {row['sourceReference']}")
        symbol = native.documents["SYMBOL", fields["Symbol"]]
        instance = components[identity]
        pins = {record.header["id"] for record in symbol
                if record.header["type"] == "PIN" and record.payload["partId"] == instance["partId"]}
        by_number = {record.payload["parentId"]: record.payload["value"] for record in symbol
                     if record.header["type"] == "ATTR" and record.payload["key"] == "Pin Number"
                     and record.payload["parentId"] in pins}
        if by_number.keys() != pins or not pins or len(set(by_number.values())) != len(pins):
            raise ValueError(f"Incomplete/duplicate native pins: {row['sourceReference']}")
        page = native.documents["SCH_PAGE", page_uuid]
        prefix = primitive + "-"
        nc = [record.payload["parentId"].removeprefix(prefix) for record in page
              if record.header["type"] == "ATTR" and record.payload.get("key") == "NO_CONNECT"
              and record.payload.get("value") == "yes" and record.payload["parentId"].startswith(prefix)]
        if len(nc) != len(set(nc)) or not set(nc) <= pins:
            raise ValueError(f"Invalid NC identity: {row['sourceReference']}")
        part = (row["board"], row["cadReference"])
        terminals.update((*part, number) for number in by_number.values())
        markers.update((*part, by_number[pin]) for pin in nc)
        resolved.append({"sourceReference": row["sourceReference"], "match": match_kind,
                         "page": page_uuid, "primitiveId": primitive, "uniqueId": fields["Unique ID"],
                         "physicalPins": len(pins), "explicitNC": len(nc)})
    archive_markers = sum(record.header["type"] == "ATTR" and record.payload.get("key") == "NO_CONNECT"
                          for key, page in native.documents.items() if key[0] == "SCH_PAGE" for record in page)
    report = {"status": "PASS" if not unresolved and terminals == controlled and markers == controlled_nc
                         and archive_markers == len(markers) else "FAIL",
              "resolvedComponents": len(resolved), "unresolvedComponents": unresolved,
              "terminalCount": len(terminals), "controlledTerminalCount": len(controlled),
              "terminalDifference": sorted(terminals ^ controlled),
              "explicitNCCount": len(markers), "controlledNCCount": len(controlled_nc),
              "ncDifference": sorted(markers ^ controlled_nc), "archiveRawNCMarkers": archive_markers,
              "resolvedIdentities": resolved}
    if strict and report["status"] != "PASS":
        raise ValueError(f"Controlled terminal audit failed: {len(unresolved)} unresolved, "
                         f"{len(terminals ^ controlled)} terminal differences, {len(markers ^ controlled_nc)} NC differences")
    return report
