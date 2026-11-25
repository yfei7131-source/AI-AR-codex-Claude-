#!/usr/bin/env python3
"""Capture official three-board DRC, ERC, editable export, and independent re-import."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]
from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards


BOARDS = {"PCB1": "8fbc3cae65886fe5", "PCB2": "9ce45f14cb79dc9d", "PCB3": "1db01a36f669a47a"}


def checked(folder, name, command, accepted_codes=(0,)):
    try:
        p = subprocess.run(command, capture_output=True, timeout=90)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        out, err, code = exc.stdout or b"", exc.stderr or b"capture timed out", 124
    (folder / f"{name}.json").write_bytes(out)
    (folder / f"{name}.stderr.log").write_bytes(err)
    data = json.loads(out) if out.strip() else {}
    if code not in accepted_codes or not isinstance(data, dict) or data.get("ok") is False:
        raise RuntimeError(f"{name} failed with exit {code}; see raw report")
    return data


def capture(folder, project, name, window, output):
    folder.mkdir(parents=True, exist_ok=False)
    probe = Capture(folder, "easyeda", project, retries=0)
    manifest = json.loads((ROOT / "evidence/erc-3board/board_pages.json").read_bytes())
    manifest.update(project_id=project, project_name=name)
    write_json(folder / "board_pages.json", manifest)
    cmd = ["easyeda", "--project", project]
    focused = probe.run("first-pcb.json", ["doc", "switch", BOARDS["PCB1"], "--json"])
    if focused["active"]["projectUuid"] != project or focused["active"]["projectName"] != name:
        raise ValueError("Unexpected active editor project")
    for board, doc in BOARDS.items():
        saved = probe.run(f"{board}-save.json", ["--doc", doc, "pcb", "save"], mutates=True)
        reload = probe.run(f"{board}-reload.json", ["doc", "reload", doc, "--json"], mutates=True)
        active = probe.run(f"{board}-switch.json", ["doc", "switch", doc, "--json"])
        context = active.get("active", {})
        if (saved["result"]["saved"] is not True or not (reload["saved"] and reload["closed"])
                or reload["reloaded"] != doc or (context["projectUuid"], context["documentUuid"]) != (project, doc)):
            raise ValueError(f"PCB save/reopen/identity not verified for {board}")
        dump = (folder / f"{board}.dump.json").resolve()
        checked(folder, f"{board}-dump-response", cmd + ["pcb", "dump", "--include-copper", "--out", str(dump)])
        strict = checked(folder, f"{board}-drc", cmd + ["pcb", "drc", "--strict", "--json", "--timeout", "40"], (0, 1))
        if type(strict.get("passed")) is not bool or not isinstance(strict.get("violations"), list):
            raise ValueError(f"Missing native strict DRC result for {board}")
        checked(folder, f"{board}-dfm", cmd + ["pcb", "check", "--json"], (0, 1))
        print(f"{name} {board}: strict DRC passed={strict['passed']}, counts={strict['counts']}", flush=True)
    capture_boards(probe, manifest)
    receipt = probe.run("archive-response.json", [
        "project", "export", "--project-uuid", project, "--out", str(output.resolve())
    ], mutates=True, window=window)
    if receipt["result"]["uuid"] != project or not output.is_file():
        raise RuntimeError("Native archive export identity was not confirmed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--resume-independent", action="store_true",
                        help="Read the one already-created validation project after its tree has loaded")
    args = parser.parse_args()
    original_name = "EVT1-H03-CODEX-PR46-20261121"
    restore_name = "EVT1-H03-CODEX-PR46-VERIFY-20261121"
    if not args.resume_independent:
        args.output.mkdir(parents=True, exist_ok=False)
    try:
        if args.resume_independent:
            receipt = json.loads((args.output / "independent-import.json").read_bytes())
            stage = args.output / "independent-ready"
        else:
            capture(args.output / "after", args.project, original_name, args.window, args.archive)
            receipt = checked(args.output, "independent-import", [
                "easyeda", "--window", args.window, "project", "import", "--file", str(args.archive.resolve()),
                "--name", restore_name,
            ])
            stage = args.output / "independent"
        if receipt["result"]["uuid"] == args.project or receipt["result"]["friendlyName"] != restore_name:
            raise ValueError("Independent project import did not return a fresh identity")
        capture(stage, receipt["result"]["uuid"], restore_name,
                args.window, args.output / "independent-editor-export.epro2")
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        write_json(args.output / "state.json", {"status": "BLOCKED", "reason": str(error)})
        print(f"BLOCKED: {error}", flush=True)
        return 2
    write_json(args.output / "state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
