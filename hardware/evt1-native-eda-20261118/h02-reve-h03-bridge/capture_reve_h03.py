#!/usr/bin/env python3
"""Open, save/reload, capture 3-board strict ERC + Protel2 netlists + live PCB2 dump/DRC,
and export the live EasyEDA Pro V4.1.97 H02 Rev E + H03 Bridge project."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]

from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards

PROJECT_UUID = "3986599b0e0b7459c7ccbe757fd9494ca2ea6a498e8401708e55d750b6959971"
PROJECT_NAME = "EVT1-H02-REVE-H03-20261120"
BRIDGE_PCB = "9ce45f14cb79dc9d"

READBACK_PAGES = {
    "eco03_bridge_fpga": "ed9e9866a1b746ac",
    "eco07_main_pwr": "3fdc6001a068d82e",
    "eco07_main_har": "89cd87358a17e3c2",
    "eco09_14_main_soc": "3e7683d1ed324ce9",
    "eco02_priv_ldo": "e99e682aca69cae1",
    "eco02_priv_win": "35d0bca337813128",
    "eco08_aud_ble": "07dc7dde94c1bf76",
}


def run_cli(exe: str, args: list[str], allow_nonzero: bool = False) -> tuple[int, str, str]:
    proc = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"CLI failed ({proc.returncode}): {' '.join(args)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return proc.returncode, proc.stdout, proc.stderr


def run_capture(window: str, output_dir: Path, archive_path: Path, exe: str, retries: int):
    # Open newly imported project
    run_cli(exe, ["project", "open", "--project-uuid", PROJECT_UUID, "--allow-discard-unsaved", "--window", window])
    time.sleep(2)

    manifest = json.loads((PACKAGE / "h02-erc/evidence/board_pages.json").read_bytes())
    manifest["project_id"] = PROJECT_UUID
    manifest["project_name"] = PROJECT_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "board_pages.json", manifest)

    probe = Capture(output_dir, exe, PROJECT_UUID, retries)
    info = probe.run("project-info.json", ["project", "info"])
    ctx = info["context"]
    if (ctx.get("projectUuid"), ctx.get("projectName")) != (PROJECT_UUID, PROJECT_NAME):
        raise ValueError(f"Active project mismatch: {ctx}")

    # 1. Readback all Rev E modified schematic pages with live pin nets
    rb_dir = output_dir / "readback"
    rb_dir.mkdir(parents=True, exist_ok=True)
    for tag, puid in READBACK_PAGES.items():
        rb = probe.run(f"readback/{tag}.json", ["sch", "list", "--page", puid, "--include-pins", "--stay"])
        if (rb["context"]["projectUuid"], rb["context"]["documentUuid"]) != (PROJECT_UUID, puid):
            raise ValueError(f"Readback context mismatch for {tag}")

    # 2. Full 3-board save -> doc reload -> strict ERC -> Protel2 netlist export
    capture_boards(probe, manifest)

    # 3. Live PCB2 switch, save, reload, keepouts, full copper dump, strict DRC
    br_dir = output_dir / "bridge"
    br_dir.mkdir(parents=True, exist_ok=True)
    probe.run("bridge/doc-switch.json", ["doc", "switch", BRIDGE_PCB, "--json"])
    probe.run("bridge/pcb-save.json", ["--doc", BRIDGE_PCB, "pcb", "save"], mutates=True)
    probe.run("bridge/pcb-reload.json", ["doc", "reload", BRIDGE_PCB, "--json"], mutates=True)
    probe.run("bridge/keepouts.json", ["--doc", BRIDGE_PCB, "pcb", "region", "list"])

    dump_path = br_dir / "bridge-reve-persisted.dump.json"
    run_cli(exe, [
        "--project", PROJECT_UUID, "--doc", BRIDGE_PCB, "pcb", "dump",
        "--include-copper", "--label", PROJECT_NAME, "--out", str(dump_path.resolve()),
    ])
    rc, out, err = run_cli(
        exe, ["--project", PROJECT_UUID, "--doc", BRIDGE_PCB, "pcb", "drc", "--strict", "--json"],
        allow_nonzero=True,
    )
    if not out.strip().startswith("{"):
        raise RuntimeError(f"PCB2 DRC did not emit JSON (rc={rc}): {out}\n{err}")
    (br_dir / "pcb-drc-after.json").write_text(out, encoding="utf-8")

    # 4. Export live editor-persisted .epro2
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    receipt = probe.run(
        "archive-response.json",
        ["project", "export", "--project-uuid", PROJECT_UUID, "--out", str(archive_path.resolve())],
        mutates=True,
        window=window,
    )
    if receipt["result"].get("uuid") != PROJECT_UUID or not archive_path.is_file():
        raise ValueError("Editor export receipt failed")

    write_json(output_dir / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    print("REV E + H03 LIVE CAPTURE & EXPORT COMPLETE!", archive_path, archive_path.stat().st_size, "bytes")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--easyeda", default="easyeda")
    p.add_argument("--retries", type=int, choices=(0, 1, 2), default=1)
    a = p.parse_args()
    try:
        run_capture(a.window, a.output, a.archive, a.easyeda, a.retries)
    except Exception as err:
        write_json(a.output / "capture-state.json", {"status": "BLOCKED", "error": str(err)})
        print(f"BLOCKED: {err}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
