#!/usr/bin/env python3
"""Compare PR31 native evidence with the restored H02 working copy."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "hardware/evt1-native-eda-20261118"
OLD = BASE / "closure/evidence/jlc-import"
NEW = BASE / "kimi-h02-return/working-before"
OUT = NEW / "restoration-diff.json"
PROJECT = "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items() if key != "libraryUuid"}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


def differences(old, new, path="$", output=None):
    output = [] if output is None else output
    if len(output) >= 500:
        return output
    if type(old) is not type(new):
        output.append({"path": path, "baseline": old, "working": new})
    elif isinstance(old, dict):
        for key in sorted(old.keys() | new.keys()):
            if key not in old:
                # Newer readbacks may add bbox/diagnostic fields. Additions are
                # retained in raw snapshots but are not baseline regressions.
                continue
            elif key not in new:
                output.append({"path": f"{path}.{key}", "baseline": old[key], "working": "<absent>"})
            else:
                differences(old[key], new[key], f"{path}.{key}", output)
    elif isinstance(old, list):
        if len(old) != len(new):
            output.append({"path": f"{path}.length", "baseline": len(old), "working": len(new)})
        for index, (left, right) in enumerate(zip(old, new)):
            differences(left, right, f"{path}[{index}]", output)
    elif old != new:
        output.append({"path": path, "baseline": old, "working": new})
    return output


def terminal_map(connectivity):
    nets = {net["id"]: net.get("name", "") for net in connectivity["nets"]}
    connections = {(row["componentId"], str(row["pinNumber"])): row["netId"]
                   for row in connectivity["connections"]}
    result = {}
    for component in connectivity["components"]:
        for pin in component["pins"]:
            key = (component["ref"], str(pin["number"]))
            if key in result:
                raise ValueError(f"duplicate terminal {key}")
            net_id = connections.get((component["id"], str(pin["number"])))
            result[key] = {
                "name": pin["name"], "net": nets.get(net_id, ""),
                "uniqueId": component.get("uniqueId"),
                "x": pin.get("x"), "y": pin.get("y"),
            }
    return result


def main():
    manifest = read(NEW / "board_pages.json")
    if manifest["project_id"] != PROJECT:
        raise ValueError("working manifest project mismatch")
    pages = [page for board in manifest["boards"].values() for page in board]
    report = {
        "status": "PASS",
        "scope": "Every PR31 baseline field must be preserved; additive readback diagnostics and libraryUuid owner fields are excluded.",
        "sourceProjectUuid": manifest["source_project_id"],
        "workingProjectUuid": PROJECT,
        "pageCount": len(pages),
        "pages": {},
        "totals": {"terminals": 0, "connectivity_differences": 0, "list_differences": 0},
    }
    for page in pages:
        old_conn = read(OLD / "sch" / f"{page}.json")
        new_conn = read(NEW / "connectivity" / f"{page}.stdout.json")
        old_conn = dict(old_conn)
        new_conn = dict(new_conn)
        old_conn.pop("projectId", None)
        new_conn.pop("projectId", None)
        conn_diff = differences(normalized(old_conn), normalized(new_conn))
        old_terms = terminal_map(read(OLD / "sch" / f"{page}.json"))
        new_terms = terminal_map(new_conn | {"projectId": PROJECT})
        term_diff = differences(old_terms, new_terms)
        old_list = dict(read(OLD / "pins" / f"{page}.json")["result"])
        new_list = dict(read(NEW / "pins" / f"{page}.stdout.json")["result"])
        # PR31 captured an empty wires array without the richer wire geometry
        # now returned by 1.17.0. Do not equate that old coverage gap with deletion.
        baseline_wire_rows = len(old_list.get("wires", []))
        working_wire_rows = len(new_list.get("wires", []))
        old_list.pop("wires", None)
        new_list.pop("wires", None)
        list_diff = differences(normalized(old_list), normalized(new_list))
        page_status = "PASS" if not (conn_diff or term_diff or list_diff) else "FAIL"
        if page_status != "PASS":
            report["status"] = "FAIL"
        report["pages"][page] = {
            "status": page_status,
            "baselineTerminals": len(old_terms),
            "workingTerminals": len(new_terms),
            "connectivityDifferences": conn_diff,
            "terminalSemanticDifferences": term_diff,
            "baselineWireRowsNotComparable": baseline_wire_rows,
            "workingWireRowsCapturedSeparately": working_wire_rows,
            "componentPinAttributeGeometryDifferences": list_diff,
        }
        report["totals"]["terminals"] += len(new_terms)
        report["totals"]["connectivity_differences"] += len(conn_diff)
        report["totals"]["list_differences"] += len(list_diff)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "totals": report["totals"], "output": str(OUT)},
                     ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
