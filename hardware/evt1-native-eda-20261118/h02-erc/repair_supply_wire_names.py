#!/usr/bin/env python3
"""Reconcile the PR #34 native supply wires with their already-canonical terminals."""

import argparse
import csv
import json
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
BASELINE = PACKAGE / "h02-native"
sys.path.insert(0, str(BASELINE))
from prepare_hierarchy import Archive, digest
from repair_native_power_names import PAGES, positions


ROOTS = {"M-MAIN-L": "4d38590959875927", "M-OPT-BRIDGE": "e00fbca5c08cc114", "M-AUD-R": "e98944c2045546cf"}
ERC = BASELINE / "evidence/native-C/erc"


def records_by_type(document, kind):
    return {record.header["id"]: record for record in document.records if record.header["type"] == kind}


def endpoint(archive, component, attrs, kind):
    symbol = archive.documents["SYMBOL", attrs["Symbol"].payload["value"]]
    if symbol.one("META").payload["docType"] != kind or component["isMirror"] or component["rotation"] not in (0, 180):
        raise ValueError("unexpected native supply flag/port placement or symbol type")
    pin, = records_by_type(symbol, "PIN").values()
    if pin.payload["partId"] != component["partId"]:
        raise ValueError("supply symbol does not have a single placement-matched pin")
    sign = 1 if component["rotation"] == 0 else -1
    return component["x"] + sign * pin.payload["x"], component["y"] + sign * pin.payload["y"]


def baseline_findings(board):
    path = ERC / f"{ROOTS[board]}.json"
    data = json.loads(path.read_bytes())
    if data.get("ok") is not True or data["result"].get("detailsAvailable") is not True:
        raise ValueError(f"baseline ERC does not contain verified raw diagnostics: {path.name}")
    result = {}
    for item in data["result"]["violations"]:
        rule = item["rule"]
        if rule not in {"FLAGTONET", "PORTTONET", "ONLYSYMBOL"}:
            continue
        evidence, = item["raw"]["primitives"]
        where = evidence["sheet"], evidence["primitiveId"]
        names = result.setdefault(rule, {})
        if where in names:
            raise ValueError(f"duplicated {rule} raw identity: {where}")
        names[where] = evidence["name"]
    return result


def classify_proxies(archive, board, baseline):
    root = ROOTS[board]
    overview = archive.documents["SCH_PAGE", root]
    parent = overview.one("META").payload["schematic"]
    attrs = positions(overview)
    instances = {}
    for kind, uuid in archive.documents:
        if kind == "INSTANCE" and uuid.startswith(f"{parent}_${root}~"):
            placement, child_uuid = uuid.split("_$")[1:]
            instances[placement.split("~")[1]] = child_uuid
    output = []
    for (page, primitive), designator in sorted(baseline.items()):
        if page != root or attrs[primitive]["Designator"].payload["value"] != designator:
            raise ValueError(f"unexpected ONLYSYMBOL diagnostic: {board}/{designator}")
        sym = attrs[primitive]["Symbol"].payload["value"]
        child_uuid = instances[primitive]
        child = archive.documents["SCH_PAGE", child_uuid].one("META").payload
        if archive.documents["SYMBOL", sym].one("META").payload["docType"] != 17 or child["schematic"] != parent:
            raise ValueError(f"ONLYSYMBOL is not an in-board hierarchy proxy: {board}/{designator}")
        output.append({"board": board, "overview": root, "primitive": primitive, "designator": designator,
                       "use": "hierarchical sheet proxy", "child_page": child_uuid, "child_title": child["title"]})
    if len(output) != len(instances):
        raise ValueError(f"ONLYSYMBOL diagnostics do not cover all inherited hierarchy proxies on {board}")
    return output


def prepare(archive):
    with (PACKAGE / "kicad/POWER_ORIGINS.csv").open(encoding="utf-8-sig", newline="") as stream:
        controlled = list(csv.DictReader(stream))
    if len(controlled) != 11 or {item["Board"] for item in controlled} != PAGES.keys():
        raise ValueError("Unexpected controlled board supply table")
    planned, proxies = [], []
    before = {key: document.encode() for key, document in archive.documents.items()}
    for board, page_uuid in PAGES.items():
        page = archive.documents["SCH_PAGE", page_uuid]
        attrs = positions(page)
        components = records_by_type(page, "COMPONENT")
        wires = records_by_type(page, "WIRE")
        lines = records_by_type(page, "LINE")
        findings = baseline_findings(board)
        expected = {"FLAGTONET": set(), "PORTTONET": set()}
        proxies.extend(classify_proxies(archive, board, findings["ONLYSYMBOL"]))
        for row in controlled:
            if row["Board"] != board:
                continue
            flag, rail = row["KiCad_Flag"], row["Net"]
            old = f"EVT1_{flag}_SUPPLY_ORIGIN"
            flag_id, = (key for key in components if "Designator" in attrs[key]
                        and attrs[key]["Designator"].payload["value"] == flag)
            port_id, = (key for key in components if key != flag_id and "Name" in attrs[key]
                        and attrs[key]["Name"].payload["value"] == rail)
            if attrs[flag_id]["Name"].payload["value"] != rail:
                raise ValueError(f"{board}/{flag}: flag Name does not match controlled rail")
            wire_id, = (key for key in wires if attrs.get(key, {}).get("NET")
                        and attrs[key]["NET"].payload["value"] == old)
            line_id, = (key for key, record in lines.items() if record.payload.get("lineGroup") == wire_id)
            line = lines[line_id].payload
            endpoints = {(line["startX"], line["startY"]), (line["endX"], line["endY"])}
            intended = {endpoint(archive, components[flag_id].payload, attrs[flag_id], 18),
                        endpoint(archive, components[port_id].payload, attrs[port_id], 19)}
            if len(endpoints) != 2 or endpoints != intended:
                raise ValueError(f"{board}/{flag}: wire does not span the two independent native pin endpoints")
            for rule, primitive in (("FLAGTONET", flag_id), ("PORTTONET", port_id)):
                location = page_uuid, primitive
                if findings[rule][location].split("(", 1)[0] != rail:
                    raise ValueError(f"{board}/{flag}: original {rule} diagnostic reported another rail")
                expected[rule].add(location)
            writable = attrs[wire_id]["NET"]
            change = {"board": board, "page": page_uuid, "flag": flag, "flag_primitive": flag_id,
                      "port_primitive": port_id, "wire": wire_id, "wire_net_attribute": writable.header["id"],
                      "line": line_id, "endpoints": sorted(endpoints), "before": old, "after": rail,
                      "source": row["Electrical_Source"]}
            planned.append((writable, change))
        if any(expected[rule] != set(findings[rule]) for rule in expected):
            raise ValueError(f"{board}: expected FLAGTONET/PORTTONET evidence differs from the full set")

    for record, change in planned:
        record.payload["value"] = change["after"]
    changed_documents = {key for key, document in archive.documents.items() if document.encode() != before[key]}
    if changed_documents != {("SCH_PAGE", page) for page in PAGES.values()} or len(planned) != 11 or len(proxies) != 18:
        raise ValueError("Repair escaped the controlled 11 wire label records on three supply pages")
    return [change for _, change in planned], proxies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists() or args.output.resolve() == args.report.resolve():
        parser.error("output archive and report must use separate new paths")
    original_hash = digest(args.source)
    archive = Archive(args.source)
    changes, proxies = prepare(archive)
    archive.write(args.output)
    if digest(args.source) != original_hash or Archive(args.output).encode() != archive.encode():
        raise ValueError("Source integrity or candidate roundtrip check failed")
    report = {"offline_archive": "PASS", "native_erc_after_edit": "UNVERIFIED", "manufacturing": "BLOCKED",
              "source_sha256": original_hash, "candidate_sha256": digest(args.output), "wire_net_attribute_edits": changes,
              "unchanged_onlysymbol_proxy_classification": proxies}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS: {len(changes)} wire NET attributes checked and repaired; isolated archive at {args.output}")


if __name__ == "__main__":
    main()
