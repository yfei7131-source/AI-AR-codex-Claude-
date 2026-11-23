#!/usr/bin/env python3
"""Replace an explicit set of native tracks at identical centerlines, with receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

R7 = Path(__file__).resolve().parents[1]
REPO = R7.parents[2]
EVIDENCE = R7 / "verification"
RUNNER = R7 / "tools/r7_native.py"
sys.path.insert(0, str(REPO / "hardware/evt1-native-eda-20261118/h03-codex-r6-20261123"))
from apply_widths import compare_routes


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--ids", required=True, help="Comma-separated fresh native track IDs")
    parser.add_argument("--before", required=True, type=Path, help="Fresh saved/reloaded board dump")
    parser.add_argument("--from-width", required=True, type=float)
    parser.add_argument("--to-width", required=True, type=float)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    ids = args.ids.split(",")
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("IDs must be unique and nonempty")
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
        cli(f"dump-{label}", ["pcb", "dump", "--include-copper", "--out", str(output)])
        data = json.loads(output.read_text(encoding="utf-8"))
        capture = data["capture"]
        if not capture["identityVerified"] or (capture["projectUuid"], capture["documentUuid"]) != (args.project, args.doc):
            raise ValueError("Fresh board identity differs from the requested target")
        return data

    before = json.loads(args.before.read_text(encoding="utf-8"))
    capture = before["capture"]
    if not capture["identityVerified"] or (capture["projectUuid"], capture["documentUuid"]) != (args.project, args.doc):
        raise ValueError("Input dump is not the requested target")
    originals = {line["primitiveId"]: line for line in before["copper"]["lines"]}
    wanted = {}
    for identifier in ids:
        line = originals.get(identifier)
        if line is None or line["lineWidth"] != args.from_width or line["locked"]:
            raise ValueError(f"Source state mismatch: {identifier}")
        wanted[identifier] = line | {"lineWidth": args.to_width}
    created = []
    for index, line in enumerate(wanted.values(), 1):
        response = cli(f"create-{index:02d}", [
            "pcb", "track", "--net", line["net"], "--layer", str(line["layer"]),
            "--width", str(args.to_width), "--x1", str(line["startX"]), "--y1", str(line["startY"]),
            "--x2", str(line["endX"]), "--y2", str(line["endY"])])
        if response.get("ok") is not True or response.get("mutationContext", {}).get("projectUuid") != args.project:
            raise ValueError("Native create did not confirm the requested project")
        created.append(response["result"]["primitiveId"])
    after_create = dump("after-create")
    remaining = sorted(wanted.keys() & {line["primitiveId"] for line in after_create["copper"]["lines"]})
    if remaining:
        response = cli("delete-old", ["pcb", "track-delete", "--ids", ",".join(remaining)])
        if {line["primitiveId"] for line in response["result"]["removed"]} != set(remaining):
            raise ValueError("Original track removal differs from explicit scope")
    if cli("save", ["pcb", "save"])["result"]["saved"] is not True:
        raise ValueError("Positive saved:true receipt required")
    cli("reload", ["doc", "reload"])
    after = dump("after")
    for name in ("components", "rules", "outline", "copperLayers"):
        if before[name] != after[name]:
            raise ValueError(f"Out-of-scope board change: {name}")
    for name in ("vias", "arcs", "fills", "pours", "poured", "regions"):
        if before["copper"][name] != after["copper"][name]:
            raise ValueError(f"Out-of-scope copper change: {name}")
    ending = {line["primitiveId"]: line for line in after["copper"]["lines"]}
    common = {identifier for identifier in originals.keys() & ending.keys() - wanted.keys()
              if originals[identifier] == ending[identifier]}
    expected = [wanted.get(identifier, line) for identifier, line in originals.items() if identifier not in common]
    observed = [line for identifier, line in ending.items() if identifier not in common]
    compare_routes(expected, observed)
    drc = cli("drc", ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_failure=True)
    clearance = [v for v in drc.get("violations", []) if v.get("rule") == "Clearance Error"]
    result = {
        "schemaVersion": 1,
        "project": args.project,
        "document": args.doc,
        "before": str(args.before.resolve()),
        "beforeSha256": sha(args.before),
        "after": str((EVIDENCE / f"{args.prefix}-after.json").resolve()),
        "afterSha256": sha(EVIDENCE / f"{args.prefix}-after.json"),
        "ids": ids,
        "fromWidthMil": args.from_width,
        "toWidthMil": args.to_width,
        "createdPrimitiveIds": created,
        "removedOriginalIds": sorted(wanted.keys() - ending.keys()),
        "geometryScopeVerified": True,
        "saved": True,
        "reloaded": True,
        "drcCounts": drc.get("counts"),
        "nativeDrcPassed": drc.get("passed"),
        "clearanceErrors": clearance,
        "candidateStatus": "candidate-rejected" if clearance else "native-copper-verified-not-full-net",
        "limitations": ["Full-net connectivity, controlled impedance, manufacturer approval and hardware are not proven."],
    }
    output = EVIDENCE / f"{args.prefix}-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if clearance else 0


if __name__ == "__main__":
    raise SystemExit(main())
