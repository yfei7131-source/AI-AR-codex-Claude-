#!/usr/bin/env python3
"""Save, reload and independently capture all three final native boards.

Only document saves, read-only checks and exports are performed. Native DRC/ERC
violations are retained as design results, never suppressed to make a pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

R7 = Path(__file__).resolve().parents[1]
REPO = R7.parents[2]
EVIDENCE = R7 / "verification"
FINAL = EVIDENCE / "final"
RUNNER = R7 / "tools/r7_native.py"
PROJECT = "37f434ba2161d11e7536f134c776285fbdc9db9c040debca7ccd85f6ebbea46d"
WINDOW = "0df3b77f-c2ac-44c5-b137-d6c9320e4e7d"
BOARDS = [
    ("PCB1", "8fbc3cae65886fe5", "4d38590959875927", "61", "M-MAIN-L"),
    ("PCB2", "9ce45f14cb79dc9d", "e00fbca5c08cc114", "62", "M-OPT-BRIDGE"),
    ("PCB3", "1db01a36f669a47a", "e98944c2045546cf", "63", "M-AUD-R"),
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cli(label: str, arguments: list[str], allow_failure: bool = False):
    receipt = EVIDENCE / f"{label}.stdout.json"
    if receipt.exists():
        # A resumed report reads the original evidence. It never silently repeats
        # an already executed native command or overwrites its raw output.
        raw = receipt.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "240", label, *arguments],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=260)
    (EVIDENCE / f"{label}.console.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8")
    raw = receipt.read_text(encoding="utf-8")
    if completed.returncode and not allow_failure:
        raise RuntimeError(f"{label}: native command exit {completed.returncode}; see raw evidence")
    return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}


def main() -> int:
    FINAL.mkdir(exist_ok=True)
    summary = {"project": PROJECT, "mode": "integrated-final", "boards": {}}
    for board, doc, root, prefix, net_name in BOARDS:
        scope = ["--project", PROJECT, "--doc", doc]
        save_receipt = EVIDENCE / f"{prefix}-{board}-final-save.stdout.json"
        reload_receipt = EVIDENCE / f"{prefix}-{board}-final-reload.stdout.json"
        # A prior partial run may already have persisted a successful save/reload.
        # Reuse only its validated raw receipts; never repeat a reload blindly.
        if save_receipt.exists() and reload_receipt.exists():
            saved, reloaded = load(save_receipt), load(reload_receipt)
        elif save_receipt.exists() or reload_receipt.exists():
            raise ValueError(f"{board}: partial save/reload evidence; inspect before retrying")
        else:
            saved = cli(f"{prefix}-{board}-final-save", ["pcb", "save", *scope])
            reloaded = cli(f"{prefix}-{board}-final-reload", ["doc", "reload", "--json", *scope])
        if saved.get("result", {}).get("saved") is not True:
            raise ValueError(f"{board}: saved:true missing")
        reopened = any(step.get("stage") == "reopen" and step.get("ok") is True
                       and step.get("context", {}).get("documentUuid") == doc
                       for step in reloaded.get("steps", []))
        recovery_ready = False
        if (reloaded.get("status") == "partial" and reloaded.get("saved") is True
                and reloaded.get("closed") is True and reopened):
            ready_receipt = EVIDENCE / f"{prefix}b-{board}-final-ready-after-partial.stdout.json"
            if not ready_receipt.exists():
                raise ValueError(f"{board}: partial reload requires an explicit bounded read-only ready check")
            ready = load(ready_receipt)
            recovery_ready = (ready.get("ready") is True
                              and ready.get("active", {}).get("projectUuid") == PROJECT
                              and ready.get("active", {}).get("documentUuid") == doc)
        if not recovery_ready and not (
                reloaded.get("status") == "passed" and reloaded.get("saved") is True
                and reloaded.get("closed") is True and reloaded.get("reloaded") == doc
                and reloaded.get("activeRestored") == doc
                and reloaded.get("readiness", {}).get("ready") is True
                and reloaded.get("finalContext", {}).get("projectUuid") == PROJECT):
            raise ValueError(f"{board}: explicit save/close/reopen/readiness receipt missing")
        dump_path = FINAL / f"{board}-copper.json"
        cli(f"{prefix}-{board}-final-dump", [
            "pcb", "dump", "--include-copper", "--no-silk", "--out", str(dump_path), *scope])
        dump = load(dump_path)
        capture = dump["capture"]
        if (not capture["identityVerified"] or dump.get("partial")
                or (capture["projectUuid"], capture["documentUuid"]) != (PROJECT, doc)
                or set(dump["copper"]["availability"].values()) != {"available"}):
            raise ValueError(f"{board}: final native capture incomplete or wrong identity")
        drc = cli(f"{prefix}-{board}-final-drc", [
            "pcb", "drc", "--strict", "--json", "--timeout", "120", *scope], allow_failure=True)
        erc = cli(f"{prefix}-{board}-final-erc", [
            "sch", "drc", "--strict", "--json", "--project", PROJECT, "--doc", root], allow_failure=True)
        receipt = cli(f"{prefix}-{board}-final-netlist", [
            "sch", "netlist", "--type", "Protel2", "--project", PROJECT, "--doc", root])
        artifacts = receipt.get("artifacts", [])
        if len(artifacts) != 1 or not receipt.get("result", {}).get("artifactPath"):
            raise ValueError(f"{board}: no unique native Protel2 netlist")
        source = Path(receipt["result"]["artifactPath"])
        target = FINAL / f"{net_name}-r7.net"
        shutil.copyfile(source, target)
        actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_sha != artifacts[0]["sha256"]:
            raise ValueError(f"{board}: copied netlist SHA mismatch")
        summary["boards"][board] = {
            "saved": True, "reloaded": True, "captureIdentityVerified": True,
            "drcCounts": drc.get("counts"), "ercFatal": erc.get("result", {}).get("fatal"),
            "netlist": str(target), "netlistSha256": actual_sha,
        }
    archive = R7 / "native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2"
    archive.parent.mkdir(exist_ok=True)
    export = cli("65-r7-final-export", [
        "project", "export", "--window", WINDOW, "--project-uuid", PROJECT, "--out", str(archive)])
    result = export.get("result", {})
    if result.get("sha256") != hashlib.sha256(archive.read_bytes()).hexdigest():
        raise ValueError("Final native archive SHA mismatch")
    summary["archive"] = str(archive)
    summary["archiveSha256"] = result["sha256"]
    (FINAL / "native-validation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
