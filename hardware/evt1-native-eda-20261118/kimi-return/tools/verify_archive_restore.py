#!/usr/bin/env python3
"""Read back a separately imported native archive; never overwrite the source project."""
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CLI = Path.home() / ".local/bin/easyeda.exe"
OUT = ROOT / "native" / "restored-readback"
BOARDS = {
    "M-MAIN-L": "8fbc3cae65886fe5",
    "M-OPT-BRIDGE": "9ce45f14cb79dc9d",
    "M-AUD-R": "1db01a36f669a47a",
}


def run(project, name, args, doc=None):
    command = [str(CLI), *args, "--project", project]
    if doc:
        command += ["--doc", doc]
    completed = subprocess.run(command, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
    (OUT / f"{name}.log").write_text(
        "$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
        encoding="utf-8")
    parsed = None
    try:
        start = completed.stdout.find("{")
        if start >= 0:
            parsed = json.JSONDecoder().raw_decode(completed.stdout[start:])[0]
    except (ValueError, json.JSONDecodeError):
        pass
    record = {"command": command, "exitCode": completed.returncode,
              "log": str((OUT / f"{name}.log").relative_to(ROOT)), "response": parsed}
    if completed.returncode:
        raise RuntimeError(f"Restore readback failed; see {record['log']}")
    return record


def component_signature(data):
    return {c["designator"]: {
        "primitiveId": c.get("primitiveId"), "layer": c.get("layer"),
        "bbox": c.get("bbox"),
        "pads": sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                       for p in c.get("pads", [])),
    } for c in data.get("components", [])}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    import_text = (ROOT / "native/archive-import.log").read_text(encoding="utf-8")
    start = import_text.find("{")
    if start < 0:
        raise RuntimeError("No native import receipt")
    receipt = json.JSONDecoder().raw_decode(import_text[start:])[0]
    result = receipt["result"]
    project = result["uuid"]
    if project == "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662":
        raise RuntimeError("Refusing to validate by overwriting the source project")
    report = {"scope": "Separate native project import and readback, not fabrication approval",
              "createdAt": datetime.now(timezone.utc).isoformat(),
              "sourceProjectUuid": "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662",
              "importedProjectUuid": project, "importReceipt": result,
              "librariesExtracted": False, "boards": {}, "operations": {}}
    # Do not force project open: the CLI warns that it may discard unsaved tabs.
    # Address the imported project and document explicitly for read-only inspection instead.
    report["openPolicy"] = "No project-open or allow-discard-unsaved; explicit project/document readback only."
    for board, doc in BOARDS.items():
        dump_path = OUT / f"{board}.json"
        dump_op = run(project, f"{board}-dump",
                      ["pcb", "dump", "--include-copper", "--out", str(dump_path)], doc)
        list_op = run(project, f"{board}-list",
                      ["pcb", "list", "--include-bbox", "--include-pads"], doc)
        restored = json.loads(dump_path.read_text(encoding="utf-8"))
        original_path = ROOT / "layout" / "review-3" / board / "fresh-board.json"
        original = json.loads(original_path.read_text(encoding="utf-8"))
        original_sig = component_signature(original)
        restored_sig = component_signature(restored)
        listed = list_op["response"]["result"]
        assert listed["count"] == len(restored_sig)
        assert not listed.get("incomplete"), f"{board}: incomplete component/pad readback"
        assert restored["outline"]["points"] == original["outline"]["points"], f"{board}: outline changed"
        assert restored["rules"] == original["rules"], f"{board}: rules changed"
        assert restored_sig == original_sig, f"{board}: component/pad signatures changed"
        report["boards"][board] = {
            "documentUuid": doc, "candidateComponents": len(restored_sig),
            "componentPadsAndBboxParity": "PASS", "outlineParity": "PASS", "rulesParity": "PASS",
            "dumpOperation": dump_op, "listOperation": list_op,
        }
    report["nativeEditableRestoreReadback"] = "PASS_LIMITED_TO_35_CANDIDATES_AND_EMPTY_SCHEMATICS"
    report["controlledSchematicParity"] = "BLOCKED"
    report["routingStatus"] = "UNROUTED_PARTIAL_CANDIDATE"
    report["fabricationStatus"] = "BLOCKED"
    path = ROOT / "native" / "archive-restore-verification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"importedProjectUuid": project,
                      "boards": {k: v["candidateComponents"] for k, v in report["boards"].items()},
                      "result": report["nativeEditableRestoreReadback"],
                      "report": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
