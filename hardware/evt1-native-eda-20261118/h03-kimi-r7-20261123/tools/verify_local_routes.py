#!/usr/bin/env python3
"""Typed-apply explicit local pad-to-pad routes and verify persisted native copper.

Run in an isolated native project first. Integration additionally requires a passing
isolated acceptance receipt. The tool never changes electrical design or DRC rules.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

R7 = Path(__file__).resolve().parents[1]
REPO = R7.parents[2]
EVIDENCE = R7 / "verification"
RUNNER = R7 / "tools/r7_native.py"
sys.path.insert(0, str(R7.parent / "h03-codex-r6-20261123"))
from apply_widths import compare_routes

MIN_WIDTH_MIL = 50 / 25.4
BOARD_FIELDS = ("components", "rules", "outline", "copperLayers")
COPPER_FIELDS = ("vias", "arcs", "fills", "pours", "poured", "regions")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def view(board: dict):
    return {key: board[key] for key in (*BOARD_FIELDS, "copper")}


def signature(violation: dict):
    return json.dumps({key: violation.get(key) for key in
                       ("rule", "objType", "ruleName", "net", "objs")}, sort_keys=True)


def signatures(drc: dict):
    return Counter(signature(row) for row in drc.get("violations", []))


def expanded(counter: Counter):
    return [json.loads(key) for key, count in counter.items() for _ in range(count)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--source-dump", required=True, type=Path)
    parser.add_argument("--source-drc", required=True, type=Path)
    parser.add_argument("--select", required=True, help="Zero-based route indices; explicit scope only")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--integration-acceptance", type=Path)
    args = parser.parse_args()
    selected = [int(value) for value in args.select.split(",")]
    if len(selected) != len(set(selected)) or min(selected) < 0:
        raise ValueError("Route indices must be unique and nonnegative")
    plan = load(args.plan)
    for field, path in (("archive_sha256", args.source_archive),
                        ("dump_sha256", args.source_dump), ("drc_sha256", args.source_drc)):
        if plan[field] != sha(path):
            raise ValueError(f"Plan input digest mismatch: {field}")
    source_dump, source_drc = load(args.source_dump), load(args.source_drc)
    if source_dump["capture"]["documentUuid"] != args.doc:
        raise ValueError("Source dump belongs to another PCB")
    routes = [plan["routes"][index] for index in selected]
    if len(routes) != len(selected):
        raise ValueError("Missing selected route")
    for route in routes:
        if (route["endpoint_kind"] != "pad" or route["layer"] not in (1, 2)
                or route["width_mil"] < MIN_WIDTH_MIL or not route["segments"]):
            raise ValueError(f"Unsupported route scope: {route['from']} -> {route['to']}")
    if args.integration_acceptance:
        acceptance = load(args.integration_acceptance)
        if (acceptance.get("candidateStatus") != "live-verified-local-route"
                or acceptance.get("project") == args.project
                or acceptance.get("document") != args.doc
                or acceptance.get("planSha256") != sha(args.plan)
                or acceptance.get("selectedIndices") != selected
                or acceptance.get("sourceDumpSha256") != sha(args.source_dump)
                or acceptance.get("sourceDrcSha256") != sha(args.source_drc)):
            raise ValueError("Integration requires matching isolated live verification")

    scope = ["--project", args.project, "--doc", args.doc]

    def cli(label: str, arguments: list[str], allow_failure: bool = False):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--timeout", "240", f"{args.prefix}-{label}", *arguments, *scope],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=260)
        (EVIDENCE / f"{args.prefix}-{label}.console.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode and not allow_failure:
            raise RuntimeError(f"{label}: native command exit {completed.returncode}; see raw evidence")
        raw = (EVIDENCE / f"{args.prefix}-{label}.stdout.json").read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}

    def dump(label: str):
        output = EVIDENCE / f"{args.prefix}-{label}.json"
        cli(f"dump-{label}", ["pcb", "dump", "--include-copper", "--no-silk", "--out", str(output)])
        data = load(output)
        capture = data["capture"]
        if not capture["identityVerified"] or (capture["projectUuid"], capture["documentUuid"]) != (args.project, args.doc):
            raise ValueError("Fresh native capture has the wrong identity")
        if data.get("partial") or set(data["copper"]["availability"].values()) != {"available"}:
            raise ValueError("Incomplete native copper capture")
        return data

    before = dump("before")
    if view(before) != view(source_dump):
        raise ValueError("Target board differs from the screened native baseline")
    before_drc = cli("drc-before", ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_failure=True)
    if before_drc.get("counts") != source_drc.get("counts") or signatures(before_drc) != signatures(source_drc):
        raise ValueError("Fresh strict DRC differs from the screened native baseline")

    pads = {f'{part["designator"]}.{pad["padNumber"]}': pad
            for part in before["components"] for pad in part["pads"]}
    for route in routes:
        source, target = pads.get(route["from"]), pads.get(route["to"])
        if source is None or target is None:
            raise ValueError("Missing physical route pad")
        for pad, endpoint in ((source, route["segments"][0][0]), (target, route["segments"][-1][1])):
            if (pad["net"] != route["net"] or pad["layer"] not in (route["layer"], 12)
                    or math.dist((pad["x"], pad["y"]), endpoint) > 0.001):
                raise ValueError(f"Pad identity, net, layer or coordinate mismatch: {route}")

    created = []
    for route_index, route in zip(selected, routes):
        for segment_index, (start, end) in enumerate(route["segments"], 1):
            response = cli(f"create-{route_index:03d}-{segment_index:02d}", [
                "pcb", "track", "--net", route["net"], "--layer", str(route["layer"]),
                "--width", str(route["width_mil"]), "--x1", str(start[0]), "--y1", str(start[1]),
                "--x2", str(end[0]), "--y2", str(end[1])])
            if (response.get("ok") is not True
                    or response.get("mutationContext", {}).get("projectUuid") != args.project
                    or response.get("mutationContext", {}).get("documentUuid") != args.doc):
                raise ValueError("Native create did not confirm the requested board")
            created.append(response["result"]["primitiveId"])
    if cli("save", ["pcb", "save"]).get("result", {}).get("saved") is not True:
        raise ValueError("Positive saved:true receipt required")
    cli("reload", ["doc", "reload"])
    after = dump("after")
    for key in BOARD_FIELDS:
        if before[key] != after[key]:
            raise ValueError(f"Out-of-scope board change: {key}")
    for key in COPPER_FIELDS:
        if before["copper"][key] != after["copper"][key]:
            raise ValueError(f"Out-of-scope copper change: {key}")

    originals = {line["primitiveId"]: line for line in before["copper"]["lines"]}
    ending = {line["primitiveId"]: line for line in after["copper"]["lines"]}
    common = {identifier for identifier in originals.keys() & ending.keys()
              if originals[identifier] == ending[identifier]}
    expected = [line for identifier, line in originals.items() if identifier not in common]
    for route in routes:
        for start, end in route["segments"]:
            expected.append({"net": route["net"], "layer": route["layer"], "lineWidth": route["width_mil"],
                             "startX": start[0], "startY": start[1], "endX": end[0], "endY": end[1]})
    observed = [line for identifier, line in ending.items() if identifier not in common]
    compare_routes(expected, observed, tolerance=0.02)
    after_drc = cli("drc-after", ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_failure=True)
    old_signatures, new_signatures = signatures(before_drc), signatures(after_drc)
    added_errors = new_signatures - old_signatures
    removed_errors = old_signatures - new_signatures

    paths = []
    for index, route in zip(selected, routes):
        result = cli(f"path-{index:03d}", ["pcb", "net-path", "--from", route["from"],
                     "--to", route["to"], "--layer", str(route["layer"]),
                     "--net", route["net"], "--json"], allow_failure=True)
        paths.append({"routeIndex": index, "from": route["from"], "to": route["to"],
                      "layer": route["layer"], "connected": result.get("connected") is True,
                      "report": result})
    connection_delta = {rule: before_drc["counts"].get(rule, 0) - after_drc["counts"].get(rule, 0)
                        for rule in set(before_drc["counts"]) | set(after_drc["counts"])}
    accepted = (not added_errors and all(row["connected"] for row in paths)
                and connection_delta.get("Connection Error", 0) >= len(routes)
                and after_drc.get("passed") is False)
    result = {
        "schemaVersion": 1,
        "project": args.project,
        "document": args.doc,
        "mode": "integration" if args.integration_acceptance else "isolated-trial",
        "integrationAcceptance": str(args.integration_acceptance.resolve()) if args.integration_acceptance else None,
        "plan": str(args.plan.resolve()),
        "planSha256": sha(args.plan),
        "selectedIndices": selected,
        "sourceDumpSha256": sha(args.source_dump),
        "sourceDrcSha256": sha(args.source_drc),
        "beforeDumpSha256": sha(EVIDENCE / f"{args.prefix}-before.json"),
        "afterDumpSha256": sha(EVIDENCE / f"{args.prefix}-after.json"),
        "createdPrimitiveIds": created,
        "saved": True,
        "reloaded": True,
        "geometryScopeVerified": True,
        "beforeDrcCounts": before_drc.get("counts"),
        "afterDrcCounts": after_drc.get("counts"),
        "connectionDelta": connection_delta,
        "addedErrorSignatures": expanded(added_errors),
        "removedErrorSignatures": expanded(removed_errors),
        "paths": paths,
        "candidateStatus": "live-verified-local-route" if accepted else "candidate-rejected",
        "limitations": ["Local routed copper only; no full-net, plane-return, impedance, fabrication or hardware proof."],
    }
    output = EVIDENCE / f"{args.prefix}-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
