#!/usr/bin/env python3
"""Verify explicit existing-centerline width changes in native EasyEDA.

This is a width-only operation, not a new connectivity claim. Isolate first and
require its acceptance receipt before integration. No design rules are changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

R7 = Path(__file__).resolve().parents[1]
REPO = R7.parents[2]
EVIDENCE = R7 / "verification"
RUNNER = R7 / "tools/r7_native.py"
sys.path.insert(0, str(R7 / "tools"))
from verify_local_routes import (BOARD_FIELDS, COPPER_FIELDS, compare_routes, expanded,
                                 load, sha, signatures, view)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--source-dump", required=True, type=Path)
    parser.add_argument("--source-drc", required=True, type=Path)
    parser.add_argument("--ids", required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--integration-acceptance", type=Path)
    args = parser.parse_args()
    ids = args.ids.split(",")
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("Track IDs must be unique and nonempty")
    plan = load(args.plan)
    for field, path in (("archive_sha256", args.source_archive),
                        ("dump_sha256", args.source_dump), ("drc_sha256", args.source_drc)):
        if plan[field] != sha(path):
            raise ValueError(f"Plan input digest mismatch: {field}")
    source_dump, source_drc = load(args.source_dump), load(args.source_drc)
    if source_dump["capture"]["documentUuid"] != args.doc:
        raise ValueError("Source dump belongs to another PCB")
    proposal = [row for row in plan["width_candidates"] if row["id"] in ids]
    if (len(proposal) != len(ids) or any(row["net"] != args.net or row["before_width_mil"] != 3
            or row["after_width_mil"] != 4 for row in proposal)):
        raise ValueError("Explicit width scope differs from the plan")
    if args.integration_acceptance:
        acceptance = load(args.integration_acceptance)
        if (acceptance.get("candidateStatus") != "live-verified-track-widths"
                or acceptance.get("project") == args.project
                or acceptance.get("document") != args.doc
                or acceptance.get("planSha256") != sha(args.plan)
                or acceptance.get("ids") != ids
                or acceptance.get("sourceDumpSha256") != sha(args.source_dump)
                or acceptance.get("sourceDrcSha256") != sha(args.source_drc)):
            raise ValueError("Integration requires matching isolated width verification")

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
        if (not capture["identityVerified"] or data.get("partial")
                or (capture["projectUuid"], capture["documentUuid"]) != (args.project, args.doc)
                or set(data["copper"]["availability"].values()) != {"available"}):
            raise ValueError("Fresh native capture is incomplete or has the wrong identity")
        return data

    before = dump("before")
    if view(before) != view(source_dump):
        raise ValueError("Target board differs from the screened native baseline")
    before_drc = cli("drc-before", ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_failure=True)
    if before_drc.get("counts") != source_drc.get("counts") or signatures(before_drc) != signatures(source_drc):
        raise ValueError("Fresh strict DRC differs from the screened native baseline")
    originals = {line["primitiveId"]: line for line in before["copper"]["lines"]}
    wanted = {}
    for row in proposal:
        line = originals.get(row["id"])
        if (line is None or line["net"] != args.net or line["layer"] != row["layer"]
                or line["lineWidth"] != 3 or line["locked"]
                or (line["startX"], line["startY"]) != tuple(row["start"])
                or (line["endX"], line["endY"]) != tuple(row["end"])):
            raise ValueError(f"Source state mismatch: {row['id']}")
        wanted[row["id"]] = line | {"lineWidth": 4.0}

    created = []
    for index, line in enumerate(wanted.values(), 1):
        response = cli(f"create-{index:02d}", [
            "pcb", "track", "--net", line["net"], "--layer", str(line["layer"]),
            "--width", "4", "--x1", str(line["startX"]), "--y1", str(line["startY"]),
            "--x2", str(line["endX"]), "--y2", str(line["endY"])])
        if (response.get("ok") is not True
                or response.get("mutationContext", {}).get("projectUuid") != args.project
                or response.get("mutationContext", {}).get("documentUuid") != args.doc):
            raise ValueError("Native create did not confirm the requested board")
        created.append(response["result"]["primitiveId"])
    after_create = dump("after-create")
    remaining = sorted(wanted.keys() & {line["primitiveId"] for line in after_create["copper"]["lines"]})
    if remaining:
        response = cli("delete-old", ["pcb", "track-delete", "--ids", ",".join(remaining)])
        if {row["primitiveId"] for row in response["result"]["removed"]} != set(remaining):
            raise ValueError("Original track removal differs from explicit scope")
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
    ending = {line["primitiveId"]: line for line in after["copper"]["lines"]}
    common = {identifier for identifier in originals.keys() & ending.keys() - wanted.keys()
              if originals[identifier] == ending[identifier]}
    expected = [wanted.get(identifier, line) for identifier, line in originals.items() if identifier not in common]
    observed = [line for identifier, line in ending.items() if identifier not in common]
    compare_routes(expected, observed, tolerance=0.02)
    after_drc = cli("drc-after", ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_failure=True)
    added_errors = signatures(after_drc) - signatures(before_drc)
    connection_delta = {rule: before_drc["counts"].get(rule, 0) - after_drc["counts"].get(rule, 0)
                        for rule in set(before_drc["counts"]) | set(after_drc["counts"])}
    accepted = not added_errors and after_drc.get("passed") is False
    result = {
        "schemaVersion": 1,
        "project": args.project,
        "document": args.doc,
        "mode": "integration" if args.integration_acceptance else "isolated-trial",
        "integrationAcceptance": str(args.integration_acceptance.resolve()) if args.integration_acceptance else None,
        "planSha256": sha(args.plan),
        "sourceDumpSha256": sha(args.source_dump),
        "sourceDrcSha256": sha(args.source_drc),
        "beforeDumpSha256": sha(EVIDENCE / f"{args.prefix}-before.json"),
        "afterDumpSha256": sha(EVIDENCE / f"{args.prefix}-after.json"),
        "ids": ids,
        "net": args.net,
        "fromWidthMil": 3,
        "toWidthMil": 4,
        "createdPrimitiveIds": created,
        "removedOriginalIds": sorted(wanted.keys() - ending.keys()),
        "saved": True,
        "reloaded": True,
        "geometryScopeVerified": True,
        "beforeDrcCounts": before_drc.get("counts"),
        "afterDrcCounts": after_drc.get("counts"),
        "connectionDelta": connection_delta,
        "addedErrorSignatures": expanded(added_errors),
        "candidateStatus": "live-verified-track-widths" if accepted else "candidate-rejected",
        "limitations": ["Existing-centerline width change only; no new connectivity, impedance, fabrication or hardware proof."],
    }
    output = EVIDENCE / f"{args.prefix}-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
