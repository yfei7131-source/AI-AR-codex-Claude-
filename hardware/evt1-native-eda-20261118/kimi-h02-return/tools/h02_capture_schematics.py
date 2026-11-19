#!/usr/bin/env python3
"""Capture the restored H02 working copy without modifying design content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
EDA = Path(r"C:\Users\Admin（无密码）\.local\bin\easyeda.exe")
PROJECT = "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"
BASE = ROOT / "hardware/evt1-native-eda-20261118"
SOURCE_PAGES = BASE / "closure/evidence/jlc-import/board_pages.json"
OUT = BASE / "kimi-h02-return/working-before"
LEDGER: list[dict] = []
ERRORS: list[str] = []


def run(label: str, args: list[str], timeout: int = 180) -> dict | None:
    command = [str(EDA), *args, "--project", PROJECT]
    stdout_path = OUT / f"{label}.stdout.json"
    stderr_path = OUT / f"{label}.stderr.log"
    prior = next((entry for entry in reversed(LEDGER) if entry.get("label") == label), None)
    if prior and prior.get("exitCode") == 0 and prior.get("command") == command and stdout_path.is_file():
        try:
            return json.loads(stdout_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ERRORS.append(f"{label}: cached stdout is invalid; command must be explicitly reviewed")
            return None
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        code = 124
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    (OUT / f"{label}.stdout.json").write_text(stdout, encoding="utf-8", newline="")
    (OUT / f"{label}.stderr.log").write_text(stderr, encoding="utf-8", newline="")
    LEDGER.append({"label": label, "command": command, "exitCode": code})
    (OUT / "command-ledger.json").write_text(
        json.dumps(LEDGER, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if code:
        ERRORS.append(f"{label}: exit {code}")
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        ERRORS.append(f"{label}: invalid JSON stdout: {exc}")
        return None


def require(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "connectivity").mkdir(exist_ok=True)
    (OUT / "pins").mkdir(exist_ok=True)
    (OUT / "bom").mkdir(exist_ok=True)
    ledger_path = OUT / "command-ledger.json"
    if ledger_path.is_file():
        LEDGER.extend(json.loads(ledger_path.read_text(encoding="utf-8")))
    source = json.loads(SOURCE_PAGES.read_text(encoding="utf-8"))
    pages = [(board, page) for board, uuids in source["boards"].items() for page in uuids]
    require(len(pages) == 21 and len(set(page for _, page in pages)) == 21,
            "Controlled page list is not 21 unique pages")
    restored = dict(source)
    restored["project_id"] = PROJECT
    restored["project_name"] = "EVT1-AR-YF-001-H02-KIMI-20261119"
    restored["source_project_id"] = source["project_id"]
    (OUT / "board_pages.json").write_text(
        json.dumps(restored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    boards = run("lceda-boards", ["board", "list"])
    pages_response = run("lceda-pages", ["sch", "pages"])
    require(boards is not None and boards.get("ok") is True, "board list did not return ok:true")
    require(pages_response is not None and pages_response.get("ok") is True,
            "sch pages did not return ok:true")

    summary_pages = []
    for index, (board, page) in enumerate(pages, 1):
        print(f"CAPTURE {index:02d}/21 {board} {page}", flush=True)
        connectivity = run(
            f"connectivity/{page}",
            ["sch", "connectivity", "--page", page],
        )
        if connectivity is not None:
            require(connectivity.get("schemaVersion") == "1.4",
                    f"{page}: connectivity schemaVersion is not 1.4")
            require(connectivity.get("projectId") == PROJECT,
                    f"{page}: connectivity projectId mismatch")
            require(connectivity.get("documentId") == page,
                    f"{page}: connectivity documentId mismatch")
            require(not connectivity.get("captureErrors"),
                    f"{page}: connectivity captureErrors={connectivity.get('captureErrors')}")

        listing = run(
            f"pins/{page}",
            ["sch", "list", "--page", page, "--stay", "--include-pins",
             "--include-bbox", "--include-wires", "--include-device-identity"],
        )
        component_count = None
        pin_count = None
        if listing is not None:
            require(listing.get("ok") is True, f"{page}: sch list ok is not true")
            result = listing.get("result")
            require(isinstance(result, dict), f"{page}: sch list result missing")
            if isinstance(result, dict):
                require(not result.get("captureErrors"),
                        f"{page}: list captureErrors={result.get('captureErrors')}")
                components = result.get("components")
                require(isinstance(components, list), f"{page}: components missing")
                if isinstance(components, list):
                    component_count = len(components)
                    pin_count = 0
                    for component in components:
                        identity = component.get("primitiveId") or component.get("designator") or "<unknown>"
                        require(component.get("pinsAvailable") is True,
                                f"{page}/{identity}: pinsAvailable is not true")
                        pins = component.get("pins")
                        require(isinstance(pins, list), f"{page}/{identity}: pins missing")
                        if isinstance(pins, list):
                            pin_count += len(pins)

        bom = run(
            f"bom/{page}.response",
            ["bom", "export", "--type", "csv", "--enrich=false", "--doc", page],
        )
        bom_record = {"pageUuid": page, "board": board}
        if bom is not None:
            result = bom.get("result") or {}
            artifact = result.get("artifactPath")
            require(bom.get("ok") is True, f"{page}: BOM export ok is not true")
            require(isinstance(artifact, str) and bool(artifact),
                    f"{page}: BOM result.artifactPath missing")
            if isinstance(artifact, str) and artifact:
                source_artifact = Path(artifact)
                require(source_artifact.is_file(), f"{page}: BOM artifact missing: {artifact}")
                if source_artifact.is_file():
                    target = OUT / "bom" / f"{page}.csv"
                    shutil.copyfile(source_artifact, target)
                    data = target.read_bytes()
                    bom_record.update({
                        "artifactPath": artifact,
                        "capturedFile": target.name,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "sourceMetadata": result.get("artifacts"),
                    })
                    require(source_artifact.read_bytes() == data,
                            f"{page}: copied BOM bytes differ from native artifact")
        (OUT / "bom" / f"{page}.capture.json").write_text(
            json.dumps(bom_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summary_pages.append({
            "board": board, "pageUuid": page,
            "componentCountIncludingNonParts": component_count,
            "capturedPinRows": pin_count,
            "bomCaptured": "capturedFile" in bom_record,
        })
        (OUT / "capture-summary.json").write_text(json.dumps({
            "status": "FAIL" if ERRORS else "PASS_CAPTURE_ONLY",
            "projectUuid": PROJECT,
            "pageCount": len(summary_pages),
            "pages": summary_pages,
            "errors": ERRORS,
            "electricalDesignVerified": False,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"pages": len(summary_pages), "errors": ERRORS}, ensure_ascii=False), flush=True)
    if ERRORS:
        sys.exit(1)


if __name__ == "__main__":
    main()
