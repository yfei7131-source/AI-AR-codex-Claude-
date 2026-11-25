#!/usr/bin/env python3
"""Run one bounded EasyEDA CLI command and preserve immutable raw evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

R7 = Path(__file__).resolve().parents[1]
REPO = R7.parents[2]
EDA = Path(r"C:\Users\Admin（无密码）\.local\bin\easyeda.exe")
EVIDENCE = R7 / "verification"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    if not ns.args:
        parser.error("EasyEDA arguments are required after the label")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stdout_path = EVIDENCE / f"{ns.label}.stdout.json"
    stderr_path = EVIDENCE / f"{ns.label}.stderr.log"
    if stdout_path.exists() or stderr_path.exists():
        raise FileExistsError(f"Evidence label already exists: {ns.label}")
    command = [str(EDA), *ns.args]
    timed_out = False
    try:
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=ns.timeout)
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or "", exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        code, timed_out = 124, True
    stdout_path.write_text(stdout, encoding="utf-8", newline="")
    stderr_path.write_text(stderr, encoding="utf-8", newline="")
    entry = {"label": ns.label, "command": command, "exitCode": code,
             "timedOut": timed_out, "timeoutSeconds": ns.timeout}
    ledger_path = EVIDENCE / "command-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else []
    ledger.append(entry)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
    print(json.dumps(entry, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
