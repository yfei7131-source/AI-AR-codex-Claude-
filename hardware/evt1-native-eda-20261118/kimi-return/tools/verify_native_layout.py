#!/usr/bin/env python3
"""Run scoped EasyEDA checks and capture real candidate-layout review artifacts.

Checks are preserved even when their native verdict is FAIL. This tool never
turns an empty schematic, missing devices, absent copper, or unavailable stackup
into a whole-board PASS and never writes routing.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
BOARDS = {
    "M-MAIN-L": {"pcb": "8fbc3cae65886fe5", "sch": "dff3a8fe270050d6"},
    "M-OPT-BRIDGE": {"pcb": "9ce45f14cb79dc9d", "sch": "43a42f20d31f8062"},
    "M-AUD-R": {"pcb": "1db01a36f669a47a", "sch": "388fb7a3b1e5f2d6"},
}


def unique_path(path):
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-retry-{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many preserved versions of {path}")


def run(log_dir, name, args, doc, timeout=180, document_routing=True):
    command = [str(CLI), *args]
    if document_routing:
        command += ["--project", PROJECT, "--doc", doc]
    completed = subprocess.run(command, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
    path = unique_path(log_dir / f"{name}.log")
    path.write_text("$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
                    encoding="utf-8")
    parsed = None
    try:
        start = completed.stdout.find("{")
        if start >= 0:
            parsed = json.JSONDecoder().raw_decode(completed.stdout[start:])[0]
    except Exception:
        parsed = None
    return {"command": command, "exitCode": completed.returncode,
            "log": str(path.relative_to(ROOT)), "response": parsed}


def latest_successful_result(board):
    candidates = []
    for path in OUT.glob(f"{board}-placement-result*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("savedReloadedVerified") is True:
            candidates.append((path.stat().st_mtime, path, data))
    if not candidates:
        raise RuntimeError(f"{board}: no saved/reloaded placement result")
    _, path, data = max(candidates)
    return path, data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--export3d", action="store_true")
    parser.add_argument("--export-project", action="store_true")
    args = parser.parse_args()
    review = OUT / f"review-{args.round}"
    review.mkdir(parents=True, exist_ok=True)
    health = run(review, "00-health", ["health"], BOARDS["M-MAIN-L"]["pcb"])
    (review / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    windows = []
    if health["response"]:
        windows = health["response"].get("found", {}).get("raw", {}).get("windows", [])
    matching = [w for w in windows if w.get("context", {}).get("projectUuid") == PROJECT]
    window = matching[0].get("windowId") if len(matching) == 1 else None
    manifest = {
        "round": args.round, "scope": "PARTIAL_UNROUTED_CANDIDATE_NOT_FOR_FAB",
        "createdAt": datetime.now(timezone.utc).isoformat(), "projectUuid": PROJECT,
        "windowId": window, "boards": {},
        "nativeRefinementChain": [
            "layout/refinement-1/manifest.json",
            "layout/refinement-2/manifest.json",
            "layout/refinement-3/manifest.json",
            "layout/refinement-4/manifest.json",
            "layout/refinement-5/manifest.json"
        ],
        "nativeSchematicScope": "EMPTY_UNREBUILT_SCHEMATICS; native ERC cannot substitute for KiCad ERC of the controlled design",
        "coverageLimits": [
            "No complete native schematic or schematic-to-PCB binding exists.",
            "Placement excludes unresolved connectors, passives, antennas, nRF and two blocked bridge devices.",
            "No script-authored tracks, standalone vias or pours exist; embedded footprint vias and native plane/slot objects remain. No routing or connectivity PASS is implied.",
            "Supplier stackup, impedance, VIPPO layer spans, courtyard, installed mechanical fit, thermal and mass remain unverified.",
        ],
    }
    for board, ids in BOARDS.items():
        result_path, placement = latest_successful_result(board)
        board_dir = review / board
        board_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "placementResult": str(result_path.relative_to(ROOT)),
            "placementResultSha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "candidateComponentCount": placement["candidateComponentCount"],
            "operations": {},
        }
        if args.round == 2:
            record["operations"]["save"] = run(board_dir, "00-save", ["pcb", "save"], ids["pcb"])
            record["operations"]["reload"] = run(board_dir, "01-reload", ["doc", "reload", ids["pcb"]], ids["pcb"])
        else:
            record["operations"]["switch"] = run(board_dir, "00-switch", ["doc", "switch", ids["pcb"]], ids["pcb"])
        dump_path = unique_path(board_dir / "fresh-board.json")
        record["operations"]["dump"] = run(board_dir, "02-fresh-dump",
            ["pcb", "dump", "--include-copper", "--out", str(dump_path)], ids["pcb"])
        record["operations"]["list"] = run(board_dir, "03-fresh-list",
            ["pcb", "list", "--include-bbox", "--include-pads"], ids["pcb"])
        record["operations"]["drc"] = run(board_dir, "04-native-drc-strict",
            ["pcb", "drc", "--strict", "--json", "--timeout", "120"], ids["pcb"], timeout=150)
        record["operations"]["check"] = run(board_dir, "05-check-strict-json",
            ["pcb", "check", "--strict", "--json"], ids["pcb"])
        record["operations"]["lint"] = run(board_dir, "06-layout-lint",
            ["pcb", "layout-lint", "--json", "--min-gap", "7.874015748031496"], ids["pcb"])
        svg = unique_path(board_dir / "actual-both.svg")
        record["operations"]["actualRender"] = run(board_dir, "07-actual-render",
            ["pcb", "layout", "render", "--actual", "--board", str(dump_path),
             "--side", "both", "--out", str(svg)], ids["pcb"])
        snapshot_dir = unique_path(board_dir / "stage")
        record["operations"]["stageSnapshot"] = run(board_dir, "08-stage-snapshot",
            ["pcb", "stage-snapshot", "--fit-mode", "board", "--stage",
             f"EVT1-PARTIAL-REVIEW-{args.round}", "--out", str(snapshot_dir)], ids["pcb"])
        record["operations"]["models"] = run(board_dir, "09-3d-models",
            ["pcb", "3d", "models"], ids["pcb"])
        # Native ERC is intentionally run on the actual, currently empty SCH page.
        record["operations"]["schematicSwitch"] = run(board_dir, "10-schematic-switch",
            ["doc", "switch", ids["sch"]], ids["sch"])
        record["operations"]["nativeErc"] = run(board_dir, "11-native-erc-strict-json",
            ["sch", "drc", "--strict", "--json"], ids["sch"])
        if args.export3d:
            record["exports3d"] = {}
            for fmt in ("obj", "step"):
                export_dir = unique_path(ROOT / "3d" / f"{board}-{fmt}")
                export_args = ["pcb", "export-3d", "--format", fmt, "--out", str(export_dir)]
                if window:
                    export_args += ["--window", window]
                record["operations"]["pcbSwitchFor3d_" + fmt] = run(board_dir, f"12-pcb-switch-{fmt}",
                    ["doc", "switch", ids["pcb"]], ids["pcb"])
                record["exports3d"][fmt] = run(board_dir, f"13-export-3d-{fmt}", export_args, ids["pcb"], timeout=240)
        manifest["boards"][board] = record
        print(f"{board}: review-{args.round} commands preserved", flush=True)
    if args.export_project:
        archive = unique_path(ROOT / "native" / "ZY_AIAR_EVT1_KIMI_20261118.epro2")
        archive.parent.mkdir(parents=True, exist_ok=True)
        export_args = ["project", "export", "--project-uuid", PROJECT, "--out", str(archive)]
        if window:
            export_args += ["--window", window]
        manifest["nativeProjectExport"] = run(review, "90-project-export",
            export_args, BOARDS["M-AUD-R"]["pcb"], timeout=240, document_routing=False)
    manifest_path = unique_path(review / "manifest.json")
    manifest["manifestSha256Input"] = "Hash the file after writing; this field is not a self-hash."
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MANIFEST {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
