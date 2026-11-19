#!/usr/bin/env python3
"""Freeze the user-imported EVT1 project without changing design content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
EDA = Path(r"C:\Users\Admin（无密码）\.local\bin\easyeda.exe")
PROJECT = "93483f037ddad8ee94645e465e387433745bea2cc21a4fb8703af0b2b8cd7199"
OUT = ROOT / "hardware/evt1-native-eda-20261118/kimi-h02-return/backup"
ARCHIVE = OUT / "original-EVT1-AR-YF-001.epro2"
COMMANDS: list[dict] = []


def run(label: str, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    command = [str(EDA), *args, "--project", PROJECT]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    (OUT / f"{label}.stdout.json").write_text(completed.stdout, encoding="utf-8", newline="")
    (OUT / f"{label}.stderr.log").write_text(completed.stderr, encoding="utf-8", newline="")
    COMMANDS.append({"label": label, "command": command, "exitCode": completed.returncode})
    (OUT / "command-ledger.json").write_text(json.dumps(COMMANDS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"{label} failed with exit {completed.returncode}; see raw stdout/stderr")
    return completed


def json_output(completed: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(completed.stdout)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    documents = json_output(run("00-documents", ["doc", "ls", "--json"]))
    if documents.get("activeUuid") is None:
        raise RuntimeError("No active document in source project")
    pages = [d for d in documents.get("documents", []) if d.get("type") == "schematic"]
    if len(pages) != 21 or len(documents.get("documents", [])) != 21:
        raise RuntimeError(f"Expected exactly 21 schematic documents and no others, got {documents}")
    run("01-project-info", ["project", "info"])
    run("02-board-list-before", ["board", "list"])
    run("03-pages-before", ["sch", "pages"])
    saved = []
    for index, page in enumerate(pages, 1):
        uuid = page["uuid"]
        result = json_output(run(f"save-{index:02d}-{uuid}", ["sch", "save", "--doc", uuid]))
        if result.get("result", {}).get("saved") is not True:
            raise RuntimeError(f"Save did not return saved:true for {uuid}: {result}")
        saved.append(uuid)
        print(f"SAVED {index:02d}/21 {uuid}", flush=True)
    run("04-project-export", [
        "project", "export", "--project-uuid", PROJECT, "--out", str(ARCHIVE),
    ], timeout=180)
    if not ARCHIVE.is_file():
        raise RuntimeError("Export returned success but archive is missing")
    with zipfile.ZipFile(ARCHIVE) as archive:
        corrupt = archive.testzip()
        names = archive.namelist()
    if corrupt is not None:
        raise RuntimeError(f"Archive CRC failure: {corrupt}")
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    summary = {
        "status": "PASS_BACKUP_ONLY",
        "sourceProjectUuid": PROJECT,
        "sourceProjectName": "EVT1-AR-YF-001",
        "sourceDesignModified": False,
        "schematicDocumentsSaved": len(saved),
        "savedDocumentUuids": saved,
        "archive": ARCHIVE.name,
        "archiveBytes": ARCHIVE.stat().st_size,
        "archiveSha256": digest,
        "archiveZipCrc": "PASS",
        "archiveMembers": len(names),
        "containsEpru": any(name.endswith(".epru") for name in names),
        "restoreVerified": False,
        "notes": "Native backup of the manually imported source; no KiCad import or redraw performed.",
    }
    (OUT / "backup-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
