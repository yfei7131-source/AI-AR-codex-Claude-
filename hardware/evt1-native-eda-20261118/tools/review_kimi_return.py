#!/usr/bin/env python3
"""Run native ERC and DRC with schematic parity on returned KiCad projects."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOTS = ("evt1-main-left", "evt1-optical-bridge", "evt1-audio-right")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_native(cli: str, source: Path, destination: Path, *, pcb: bool) -> dict:
    if not source.is_file():
        return {"status": "BLOCKED", "reason": "native input missing", "input": source.name}
    if not source.with_suffix(".kicad_pro").is_file():
        return {"status": "BLOCKED", "reason": "project settings required", "input": source.name}
    if pcb and not source.with_suffix(".kicad_sch").is_file():
        return {"status": "BLOCKED", "reason": "paired schematic required for parity", "input": source.name}
    command = [cli, "pcb", "drc", "--schematic-parity"] if pcb else [cli, "sch", "erc"]
    command += ["--format", "json", "--severity-all", "--exit-code-violations",
                "--output", str(destination), source.name]
    try:
        result = subprocess.run(command, cwd=source.parent, capture_output=True,
                                encoding="utf-8", errors="replace", timeout=180)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"status": "BLOCKED", "reason": str(exc), "input_sha256": sha256(source)}
    destination.with_suffix(".stdout.txt").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    if not destination.is_file():
        return {"status": "FAIL", "reason": "native report missing", "exit": result.returncode,
                "input_sha256": sha256(source)}
    try:
        report = json.loads(destination.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        return {"status": "FAIL", "reason": f"unreadable KiCad report: {exc}", "exit": result.returncode}
    if pcb:
        issues = {key: len(report[key]) for key in ("violations", "unconnected_items",
                                                    "schematic_parity") if key in report}
        has_report_data = "violations" in report and "unconnected_items" in report
    else:
        sheets = report.get("sheets", [])
        issues = {"violations": sum(len(sheet["violations"]) for sheet in sheets)}
        has_report_data = bool(sheets)
    passed = result.returncode == 0 and has_report_data and not any(issues.values())
    return {"status": "PASS" if passed else "FAIL", "exit": result.returncode,
            "input_sha256": sha256(source), "report_sha256": sha256(destination),
            "issues": issues, "excluded_findings_count_as_open": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incoming", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kicad-cli", default="kicad-cli")
    args = parser.parse_args()
    incoming, output = args.incoming.resolve(), args.output.resolve()
    if output == incoming or incoming in output.parents:
        parser.error("put generated reports outside the returned project tree")
    output.mkdir(parents=True, exist_ok=True)
    projects = {}
    for name in ROOTS:
        base = incoming / name / name
        projects[name] = {
            "schematic_erc": run_native(args.kicad_cli, base.with_suffix(".kicad_sch"),
                                        output / f"{name}-erc.json", pcb=False),
            "pcb_drc_and_parity": run_native(args.kicad_cli, base.with_suffix(".kicad_pcb"),
                                             output / f"{name}-drc.json", pcb=True),
        }
    status = ["FAIL", "BLOCKED", "PASS"]
    aggregate = min((result["status"] for project in projects.values()
                     for result in project.values()), key=status.index)
    version = None
    try:
        version = subprocess.check_output([args.kicad_cli, "version"], text=True, timeout=30).strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    review = {"native_review": aggregate, "kicad_version": version, "projects": projects,
              "manufacturing": "BLOCKED",
              "remaining_review": "Compare constraints, footprints and interface/DFM evidence against the handoff."}
    rendered = json.dumps(review, indent=2) + "\n"
    (output / "KIMI_NATIVE_REVIEW.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[aggregate]


if __name__ == "__main__":
    raise SystemExit(main())
