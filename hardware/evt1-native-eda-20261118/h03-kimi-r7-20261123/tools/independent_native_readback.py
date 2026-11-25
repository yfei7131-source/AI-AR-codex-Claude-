#!/usr/bin/env python3
"""Read the newly imported R7 project; perform no design edits."""
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
OUT = EVIDENCE / "independent"
RUNNER = R7 / "tools/r7_native.py"
PROJECT = "038ca2c55a325ffb9f130a53eab997bca78c8b05f2c589857db34f8be255a3e2"
BOARDS = [
    ("PCB1", "8fbc3cae65886fe5", "4d38590959875927", "69", "M-MAIN-L"),
    ("PCB2", "9ce45f14cb79dc9d", "e00fbca5c08cc114", "70", "M-OPT-BRIDGE"),
    ("PCB3", "1db01a36f669a47a", "e98944c2045546cf", "71", "M-AUD-R"),
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cli(label: str, arguments: list[str], allow_failure: bool = False):
    receipt = EVIDENCE / f"{label}.stdout.json"
    if receipt.exists():
        raw = receipt.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "240", label, *arguments],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=260)
    (EVIDENCE / f"{label}.console.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    raw = receipt.read_text(encoding="utf-8")
    if completed.returncode and not allow_failure:
        raise RuntimeError(f"{label}: native command exit {completed.returncode}; see raw evidence")
    return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}


def main() -> int:
    OUT.mkdir(exist_ok=True)
    summary = {"project": PROJECT, "designEdits": False, "boards": {}}
    for board, doc, root, prefix, net_name in BOARDS:
        scope = ["--project", PROJECT, "--doc", doc]
        dump_path = OUT / f"{board}-copper.json"
        cli(f"{prefix}-{board}-independent-dump", [
            "pcb", "dump", "--include-copper", "--no-silk", "--out", str(dump_path), *scope])
        dump = load(dump_path)
        capture = dump["capture"]
        if (not capture["identityVerified"] or dump.get("partial")
                or (capture["projectUuid"], capture["documentUuid"]) != (PROJECT, doc)
                or set(dump["copper"]["availability"].values()) != {"available"}):
            raise ValueError(f"{board}: independent capture incomplete or wrong identity")
        drc = cli(f"{prefix}-{board}-independent-drc", [
            "pcb", "drc", "--strict", "--json", "--timeout", "120", *scope], allow_failure=True)
        erc = cli(f"{prefix}-{board}-independent-erc", [
            "sch", "drc", "--strict", "--json", "--project", PROJECT, "--doc", root], allow_failure=True)
        receipt = cli(f"{prefix}-{board}-independent-netlist", [
            "sch", "netlist", "--type", "Protel2", "--project", PROJECT, "--doc", root])
        if len(receipt.get("artifacts", [])) != 1:
            raise ValueError(f"{board}: independent Protel2 receipt is not unique")
        source = Path(receipt["result"]["artifactPath"])
        target = OUT / f"{net_name}-r7.net"
        shutil.copyfile(source, target)
        net_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if net_sha != receipt["artifacts"][0]["sha256"]:
            raise ValueError(f"{board}: independent netlist copy mismatch")
        summary["boards"][board] = {
            "captureIdentityVerified": True, "drcCounts": drc.get("counts"),
            "ercFatal": erc.get("result", {}).get("fatal"), "netlistSha256": net_sha,
            "components": len(dump["components"]),
        }
    (OUT / "validation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
