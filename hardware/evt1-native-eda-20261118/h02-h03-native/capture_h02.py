#!/usr/bin/env python3
"""Save, reopen, capture, and export the existing PR #35 EasyEDA Pro project."""

import argparse
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]
from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards


def run(probe, manifest, window, archive):
    info = probe.run("project-info.json", ["project", "info"])
    context = info["context"]
    if (context.get("projectUuid"), context.get("projectName")) != (probe.project, manifest["project_name"]):
        raise ValueError("The active project is not the existing PR #35 project")
    l2 = "3fdc6001a068d82e"
    save = probe.run("l2-save.json", ["--doc", l2, "sch", "save"], mutates=True)
    reload = probe.run("l2-reload.json", ["doc", "reload", l2, "--json"], mutates=True)
    if (save["result"]["saved"] is not True or reload["saved"] is not True or reload["closed"] is not True
            or reload["reloaded"] != l2 or reload["targetContext"]["projectUuid"] != probe.project):
        raise ValueError("L2 schematic save/reopen was not verified")
    l2_pins = probe.run("l2-pins.json", ["sch", "list", "--page", l2, "--include-pins", "--stay"])
    if (l2_pins["context"]["projectUuid"], l2_pins["context"]["documentUuid"]) != (probe.project, l2):
        raise ValueError("L2 field/pin readback has the wrong scope")
    capture_boards(probe, manifest)
    receipt = probe.run("archive-response.json", [
        "project", "export", "--project-uuid", probe.project, "--out", str(archive.resolve())
    ], mutates=True, window=window)
    if receipt["result"].get("uuid") != probe.project or not archive.is_file():
        raise ValueError("Editor did not confirm the intended archive export")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--retries", type=int, choices=(0, 1, 2), default=0)
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / "h02-erc/evidence/board_pages.json").read_bytes())
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "board_pages.json", manifest)
    probe = Capture(args.output, "easyeda", manifest["project_id"], args.retries)
    try:
        run(probe, manifest, args.window, args.archive)
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        write_json(args.output / "capture-state.json", {"status": "BLOCKED", "error": str(error)})
        print(f"BLOCKED: {error}", flush=True)
        return 2
    write_json(args.output / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
