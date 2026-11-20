#!/usr/bin/env python3
"""Live EasyEDA Pro V4.1.97 edit, save/reload, 3-board ERC/netlist, PCB2 dump/DRC, and export."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]

from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards

PROJECT_UUID = "69e0af55d0371eb2dc23e878fa4739d7541262712a367a7dafaeb9549ef936e9"
PROJECT_NAME = "EVT1-H02-H03-RD-20261120"
BRIDGE_PCB = "9ce45f14cb79dc9d"

# Live ECO-10 schematic edits executed directly via EasyEDA Pro V4.1.97 CLI
LIVE_SCH_PATCHES = [
    (
        "ant1",
        "3e7683d1ed324ce9",
        "ie993",
        {
            "customAttributes": {
                "Value": "ANT1 | 2450AT18B100E (Z=1.50mm BOM fix, ECO-10)",
            }
        },
    ),
    (
        "ant2",
        "07dc7dde94c1bf76",
        "ie740",
        {
            "customAttributes": {
                "Value": "ANT2_BLE | 2450AT18B100E (Z=1.50mm BOM fix, ECO-10)",
            }
        },
    ),
]

READBACK_PAGES = {
    "eco01_13_power": "3fdc6001a068d82e",
    "eco02_priv_ldo": "e99e682aca69cae1",
    "eco02_priv_win": "35d0bca337813128",
    "bridge_avdd": "d643a0611d67a31a",
    "eco10_ant1": "3e7683d1ed324ce9",
    "eco10_ant2": "07dc7dde94c1bf76",
}


def run_cli_raw(exe: str, args: list[str], allow_nonzero: bool = False) -> tuple[int, str, str]:
    proc = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"CLI failed ({proc.returncode}): {' '.join(args)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return proc.returncode, proc.stdout, proc.stderr


def run_capture(probe: Capture, manifest: dict, window: str, output_dir: Path, archive_path: Path, exe: str):
    info = probe.run("project-info.json", ["project", "info"])
    context = info["context"]
    if (context.get("projectUuid"), context.get("projectName")) != (PROJECT_UUID, PROJECT_NAME):
        raise ValueError(f"Active project mismatch: {context}")

    # 1. Live ECO-10 schematic edits via official easyeda sch modify + save + doc reload
    ops_dir = output_dir / "operations"
    ops_dir.mkdir(parents=True, exist_ok=True)
    for tag, page_uuid, prim_id, patch in LIVE_SCH_PATCHES:
        patch_file = ops_dir / f"{tag}-patch.json"
        write_json(patch_file, patch)
        probe.run(
            f"operations/{tag}-modify.json",
            ["--doc", page_uuid, "sch", "modify", "--id", prim_id, "--patch-file", str(patch_file.resolve())],
            mutates=True,
        )
        save = probe.run(f"operations/{tag}-save.json", ["--doc", page_uuid, "sch", "save"], mutates=True)
        reload = probe.run(f"operations/{tag}-reload.json", ["doc", "reload", page_uuid, "--json"], mutates=True)
        if save["result"].get("saved") is not True or reload.get("saved") is not True or reload.get("closed") is not True or reload.get("reloaded") != page_uuid:
            raise ValueError(f"Live save/reload failed for {tag} ({page_uuid})")

    # 2. Fresh pin+property readback on all ECO-modified and footprint-bound pages
    rb_dir = output_dir / "readback"
    rb_dir.mkdir(parents=True, exist_ok=True)
    for tag, page_uuid in READBACK_PAGES.items():
        rb = probe.run(f"readback/{tag}.json", ["sch", "list", "--page", page_uuid, "--include-pins", "--stay"])
        if (rb["context"]["projectUuid"], rb["context"]["documentUuid"]) != (PROJECT_UUID, page_uuid):
            raise ValueError(f"Readback scope mismatch for {tag}")

    # 3. Full 3-board save -> doc reload -> strict ERC -> Protel2 netlist export
    capture_boards(probe, manifest)

    # 4. Live PCB2 (M-OPT-BRIDGE) readback: regions, full dump with copper, and strict DRC
    bridge_dir = output_dir / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    # Switch foreground to PCB2 cleanly
    probe.run("bridge/doc-switch.json", ["doc", "switch", BRIDGE_PCB, "--json"])
    probe.run("bridge/keepouts.json", ["--doc", BRIDGE_PCB, "pcb", "region", "list"])
    dump_path = bridge_dir / "bridge-rd-persisted.dump.json"
    run_cli_raw(
        exe,
        ["--project", PROJECT_UUID, "--doc", BRIDGE_PCB, "pcb", "dump", "--include-copper", "--label", PROJECT_NAME, "--out", str(dump_path.resolve())],
    )
    # Strict PCB DRC returns non-zero when violations exist (expected: 66 pre-existing items)
    rc, out, err = run_cli_raw(
        exe,
        ["--project", PROJECT_UUID, "--doc", BRIDGE_PCB, "pcb", "drc", "--strict", "--json"],
        allow_nonzero=True,
    )
    if not out.strip().startswith("{"):
        raise RuntimeError(f"PCB DRC did not return JSON (rc={rc}): {out} / {err}")
    (bridge_dir / "pcb-drc-after.json").write_text(out, encoding="utf-8")

    # 5. Export live editor-persisted .epro2 archive
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
        raise ValueError("Editor did not confirm the intended archive export")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--easyeda", default=r"easyeda")
    parser.add_argument("--retries", type=int, choices=(0, 1, 2), default=1)
    args = parser.parse_args()

    manifest = json.loads((PACKAGE / "h02-erc/evidence/board_pages.json").read_bytes())
    manifest["project_id"] = PROJECT_UUID
    manifest["project_name"] = PROJECT_NAME
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "board_pages.json", manifest)

    probe = Capture(args.output, args.easyeda, PROJECT_UUID, args.retries)
    try:
        run_capture(probe, manifest, args.window, args.output, args.archive, args.easyeda)
    except Exception as error:
        write_json(args.output / "capture-state.json", {"status": "BLOCKED", "error": str(error)})
        print(f"BLOCKED: {error}", flush=True)
        return 2
    write_json(args.output / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    print("CAPTURED SUCCESSFULLY!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
