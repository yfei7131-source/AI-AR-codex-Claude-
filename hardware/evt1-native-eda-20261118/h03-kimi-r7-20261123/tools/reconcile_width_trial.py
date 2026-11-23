#!/usr/bin/env python3
"""Reconcile existing native width-replacement receipts without replaying edits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

R7 = Path(__file__).resolve().parents[1]
EVIDENCE = R7 / "verification"
sys.path.insert(0, str(R7.parent / "h03-codex-r6-20261123"))
from apply_widths import compare_routes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--to-width", required=True, type=float)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after_path = EVIDENCE / f"{args.prefix}-after.json"
    after = json.loads(after_path.read_text(encoding="utf-8"))
    originals = {line["primitiveId"]: line for line in before["copper"]["lines"]}
    ending = {line["primitiveId"]: line for line in after["copper"]["lines"]}
    create_receipts = []
    for path in sorted(EVIDENCE.glob(f"{args.prefix}-create-*.stdout.json")):
        response = json.loads(path.read_text(encoding="utf-8"))
        if response.get("ok") is not True:
            raise ValueError(f"Unsuccessful native create: {path}")
        create_receipts.append(response["result"])
    ids = [line["primitiveId"] for line in create_receipts]
    old_ids = set()
    for line in create_receipts:
        for original_id, original in originals.items():
            same_geometry = (line["start"] == {"x": original["startX"], "y": original["startY"]}
                             and line["end"] == {"x": original["endX"], "y": original["endY"]})
            if same_geometry and all(line[field] == original[field] for field in ("net", "layer")):
                old_ids.add(original_id)
    if len(create_receipts) != 8 or len(old_ids) != len(create_receipts):
        raise ValueError("Create receipts do not map one-to-one to the source tracks")
    for name in ("components", "rules", "outline", "copperLayers"):
        if before[name] != after[name]:
            raise ValueError(f"Out-of-scope board change: {name}")
    for name in ("vias", "arcs", "fills", "pours", "poured", "regions"):
        if before["copper"][name] != after["copper"][name]:
            raise ValueError(f"Out-of-scope copper change: {name}")
    common = {identifier for identifier in originals.keys() & ending.keys() - old_ids
              if originals[identifier] == ending[identifier]}
    expected = [(originals[i] | {"lineWidth": args.to_width}) if i in old_ids else line
                for i, line in originals.items() if i not in common]
    observed = [line for identifier, line in ending.items() if identifier not in common]
    compare_routes(expected, observed)
    drc = json.loads((EVIDENCE / f"{args.prefix}-drc.stdout.json").read_text(encoding="utf-8"))
    clearance = [v for v in drc.get("violations", []) if v.get("rule") == "Clearance Error"]
    saved = json.loads((EVIDENCE / f"{args.prefix}-save.stdout.json").read_text(encoding="utf-8"))
    if saved["result"]["saved"] is not True:
        raise ValueError("saved:true not present")
    result = {
        "schemaVersion": 1,
        "project": after["capture"]["projectUuid"],
        "document": after["capture"]["documentUuid"],
        "beforeSha256": hashlib.sha256(args.before.read_bytes()).hexdigest(),
        "afterSha256": hashlib.sha256(after_path.read_bytes()).hexdigest(),
        "originalIds": sorted(old_ids),
        "createdPrimitiveIds": ids,
        "toWidthMil": args.to_width,
        "geometryScopeVerified": True,
        "saved": True,
        "reloaded": "reloaded" in (EVIDENCE / f"{args.prefix}-reload.stdout.json").read_text(encoding="utf-8"),
        "drcCounts": drc.get("counts"),
        "nativeDrcPassed": drc.get("passed"),
        "clearanceErrors": clearance,
        "candidateStatus": "candidate-rejected" if clearance else "native-copper-verified-not-full-net",
        "reconciliation": "Existing native receipts only; no EDA command or edit was replayed.",
        "limitations": ["Full-net connectivity, controlled impedance, manufacturer approval and hardware are not proven."],
    }
    if not result["reloaded"]:
        raise ValueError("Reload evidence missing")
    output = EVIDENCE / f"{args.prefix}-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if clearance else 0


if __name__ == "__main__":
    raise SystemExit(main())
