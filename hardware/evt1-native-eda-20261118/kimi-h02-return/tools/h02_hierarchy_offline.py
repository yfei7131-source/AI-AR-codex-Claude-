#!/usr/bin/env python3
"""Build the hierarchy BLOCKED record without repeating the timed-out call."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "hardware/evt1-native-eda-20261118/kimi-h02-return"
OUT = BASE / "hierarchy"
EXPECTED = {"M-MAIN-L": "c04afd3a85971cef", "M-OPT-BRIDGE": "73f2bfaeffaf2767",
            "M-AUD-R": "4e4521c87aee3006"}
manifest = json.loads((BASE / "working-before/board_pages.json").read_text(encoding="utf-8"))
pages_raw = json.loads((BASE / "working-before/lceda-pages.stdout.json").read_text(encoding="utf-8"))
pages = {row["uuid"]: row for row in pages_raw["result"]["pages"]}
boards = {}
for board, expected in EXPECTED.items():
    rows = [{"pageUuid": page, "expectedParent": expected,
             "observedParent": pages[page].get("parentSchematicUuid"),
             "correct": pages[page].get("parentSchematicUuid") == expected}
            for page in manifest["boards"][board]]
    boards[board] = {"expectedPages": len(rows),
                     "correctlyParentedPages": sum(row["correct"] for row in rows), "pages": rows}
actions = json.loads((BASE / "tools/easyeda-actions.json").read_text(encoding="utf-8"))
action_list = actions if isinstance(actions, list) else actions.get("actions", [])
page_actions = [{"name": row.get("name"), "description": row.get("description"), "inputs": row.get("inputs")}
                for row in action_list if str(row.get("name", "")).startswith("schematic.page.")]
timeout = json.loads((OUT / "all-pages-connectivity.command.json").read_text(encoding="utf-8"))
report = {
    "status": "BLOCKED", "projectUuid": manifest["project_id"],
    "expectedHierarchy": {"M-MAIN-L": 8, "M-OPT-BRIDGE": 7, "M-AUD-R": 6},
    "observedHierarchy": boards, "typedPageActions": page_actions,
    "typedMoveOrCopyActionAvailable": any(row["name"] in ("schematic.page.move", "schematic.page.copy")
                                           for row in page_actions),
    "officialSdkFunctionsObserved": [
        "eda.dmt_Schematic.copySchematicPage(schematicPageUuid, schematicUuid?)",
        "eda.dmt_Schematic.createSchematicPage(...)",
        "eda.dmt_Schematic.deleteSchematicPage(...)",
        "eda.dmt_Schematic.reorderSchematicPages(...)"],
    "copyDeleteUsed": False, "archiveSourceEdited": False, "controlledBatDesignatorsRenamed": False,
    "allPagesConnectivity": timeout,
    "blockingReason": "No guarded typed move/copy action is exposed for existing pages. Copy+delete can change page/primitive identity and was not used. The project-level all-pages read timed out; controlled BAT1 names were not renamed to bypass board isolation.",
    "resolutionRequired": "Provide a guarded native page-move operation preserving page/component/pin identity; then save/reload and repeat 1,075-terminal and 92-NC comparison plus board-scoped connectivity.",
}
(OUT / "hierarchy-capability.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": report["status"], "correctPages": {b: v["correctlyParentedPages"] for b, v in boards.items()},
                  "typedMoveOrCopyActionAvailable": report["typedMoveOrCopyActionAvailable"],
                  "allPagesTimedOut": timeout["timedOut"]}, ensure_ascii=False))
