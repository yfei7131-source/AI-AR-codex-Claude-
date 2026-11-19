#!/usr/bin/env python3
"""Capture the H02 hierarchy defect and available typed repair surface."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "hardware/evt1-native-eda-20261118/kimi-h02-return"
OUT = BASE / "hierarchy"
OUT.mkdir(parents=True, exist_ok=True)
PROJECT = "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"
EDA = Path(r"C:\Users\Admin（无密码）\.local\bin\easyeda.exe")
EXPECTED = {
    "M-MAIN-L": "c04afd3a85971cef",
    "M-OPT-BRIDGE": "73f2bfaeffaf2767",
    "M-AUD-R": "4e4521c87aee3006",
}
command = [str(EDA), "sch", "connectivity", "--all-pages", "--project", PROJECT]
completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
(OUT / "all-pages-connectivity.stdout.json").write_text(completed.stdout, encoding="utf-8", newline="")
(OUT / "all-pages-connectivity.stderr.log").write_text(completed.stderr, encoding="utf-8", newline="")
(OUT / "all-pages-connectivity.command.json").write_text(json.dumps({
    "command": command, "exitCode": completed.returncode, "retryCount": 0,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = json.loads((BASE / "working-before/board_pages.json").read_text(encoding="utf-8"))
pages_raw = json.loads((BASE / "working-before/lceda-pages.stdout.json").read_text(encoding="utf-8"))
pages = {row["uuid"]: row for row in pages_raw["result"]["pages"]}
boards = {}
for board, expected in EXPECTED.items():
    rows = []
    for page in manifest["boards"][board]:
        actual = pages[page].get("parentSchematicUuid")
        rows.append({"pageUuid": page, "expectedParent": expected,
                     "observedParent": actual, "correct": actual == expected})
    boards[board] = {"expectedPages": len(rows), "correctlyParentedPages": sum(r["correct"] for r in rows),
                     "pages": rows}
actions = json.loads((BASE / "tools/easyeda-actions.json").read_text(encoding="utf-8"))
action_list = actions if isinstance(actions, list) else actions.get("actions", [])
page_actions = [{"name": row.get("name"), "description": row.get("description"), "inputs": row.get("inputs")}
                for row in action_list if str(row.get("name", "")).startswith("schematic.page.")]
report = {
    "status": "BLOCKED",
    "projectUuid": PROJECT,
    "expectedHierarchy": {"M-MAIN-L": 8, "M-OPT-BRIDGE": 7, "M-AUD-R": 6},
    "observedHierarchy": boards,
    "typedPageActions": page_actions,
    "typedMoveOrCopyActionAvailable": any(str(row["name"]) in
        ("schematic.page.move", "schematic.page.copy") for row in page_actions),
    "officialSdkFunctionsObserved": [
        "eda.dmt_Schematic.copySchematicPage(schematicPageUuid, schematicUuid?)",
        "eda.dmt_Schematic.createSchematicPage(...)",
        "eda.dmt_Schematic.deleteSchematicPage(...)",
        "eda.dmt_Schematic.reorderSchematicPages(...)",
    ],
    "copyDeleteUsed": False,
    "archiveSourceEdited": False,
    "controlledBatDesignatorsRenamed": False,
    "allPagesConnectivityExitCode": completed.returncode,
    "allPagesConnectivityStderr": completed.stderr,
    "blockingReason": "No guarded typed move/copy action is exposed for existing pages. Copy+delete can change page/primitive identity and is not an approved substitute. Project-level connectivity remains unusable while the two controlled BAT1 instances share separate schematic hierarchies.",
    "resolutionRequired": "A native guarded page-move operation that preserves page/component/pin identity, followed by fresh 21-page terminal and NC comparison.",
}
(OUT / "hierarchy-capability.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": report["status"], "allPagesExitCode": completed.returncode,
                  "correctPages": {b: v["correctlyParentedPages"] for b, v in boards.items()},
                  "typedMoveOrCopyActionAvailable": report["typedMoveOrCopyActionAvailable"]}, ensure_ascii=False))
