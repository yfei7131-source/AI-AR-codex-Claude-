#!/usr/bin/env python3
"""Resolve candidate/reservation intersections without changing reserved envelopes."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout" / "refinement-5"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
MM = 1000 / 25.4
MAIN = "8fbc3cae65886fe5"
BRIDGE = "9ce45f14cb79dc9d"


def unique_path(path):
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-retry-{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many preserved versions of {path}")


def run(name, args, doc, allow_fail=False):
    command = [str(CLI), *args, "--project", PROJECT, "--doc", doc]
    completed = subprocess.run(command, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
    path = unique_path(OUT / f"{name}.log")
    path.write_text("$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr, encoding="utf-8")
    parsed = None
    try:
        start = completed.stdout.find("{")
        if start >= 0:
            parsed = json.JSONDecoder().raw_decode(completed.stdout[start:])[0]
    except Exception:
        pass
    result = {"command": command, "exitCode": completed.returncode,
              "log": str(path.relative_to(ROOT)), "response": parsed}
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Native command failed; see {path}")
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"scope": "BOUNDED_RESERVATION_REFINEMENT_NOT_FOR_FAB",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "sourceReview": "layout/review-2", "rulesChanged": False,
                "outlinesChanged": False, "reservationsChanged": False,
                "routingAuthored": False, "operations": {}, "targets": {},
                "mechanicalQualification": "BLOCKED; bottom-side U8 is a candidate placement change, not an installed-mechanics approval."}
    manifest["operations"]["health"] = run("00-health", ["health"], MAIN)
    main_before = json.loads((ROOT / "layout/review-2/M-MAIN-L/fresh-board.json").read_text(encoding="utf-8"))
    main_components = {c["designator"]: c for c in main_before["components"]}
    main_signatures = {ref: sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                                   for p in comp["pads"]) for ref, comp in main_components.items()}
    u18 = main_components["U18"]
    manifest["operations"]["rotateU18"] = run("01-main-U18-rotate",
        ["pcb", "modify", "--id", u18["primitiveId"], "--patch", '{"rotation":0}'], MAIN)
    for index, (ref, x_mm, y_mm, reason) in enumerate((
        ("U18", 2.90, 6.35, "Keep full bbox after RF_FRONT_0_TO_4P2 plus 0.20 mm and keep pads below the lowest SoC via row."),
        ("U14", 4.08425972, 33.25, "Keep native board-edge clearance and place full bbox before U7_INA reservation with 0.20 mm gap."),
    ), start=2):
        comp = main_components[ref]
        manifest["targets"][ref] = {"primitiveId": comp["primitiveId"],
            "targetCenterMm": {"x": x_mm, "y": y_mm}, "reason": reason}
        manifest["operations"][f"center_{ref}"] = run(f"{index:02d}-main-{ref}-center",
            ["pcb", "modify", "--id", comp["primitiveId"], "--center", "--x", str(x_mm * MM), "--y", str(y_mm * MM)], MAIN)
    manifest["operations"]["mainSave"] = run("04-main-save", ["pcb", "save"], MAIN)
    manifest["operations"]["mainReload"] = run("05-main-reload", ["doc", "reload", MAIN], MAIN)
    main_dump_path = unique_path(OUT / "main-fresh.json")
    manifest["operations"]["mainDump"] = run("06-main-dump",
        ["pcb", "dump", "--include-copper", "--out", str(main_dump_path)], MAIN)
    main_after = json.loads(main_dump_path.read_text(encoding="utf-8"))
    for comp in main_after["components"]:
        ref = comp["designator"]
        actual = sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer")) for p in comp["pads"])
        if actual != main_signatures[ref]:
            raise RuntimeError(f"Main-board pad signature changed for {ref}")

    bridge_before = json.loads((ROOT / "layout/review-2/M-OPT-BRIDGE/fresh-board.json").read_text(encoding="utf-8"))
    bridge_components = {c["designator"]: c for c in bridge_before["components"]}
    u8 = bridge_components["U8"]
    manifest["targets"]["bridge_U8"] = {"primitiveId": u8["primitiveId"],
        "fromLayer": "TOP", "toLayer": "BOTTOM", "centerUnchanged": True,
        "reason": "Avoid J_DISP_L and its TOP FPC corridor without narrowing the reserved optical envelope."}
    manifest["operations"]["bridgeLayerU8"] = run("07-bridge-U8-bottom",
        ["pcb", "modify", "--id", u8["primitiveId"], "--patch", '{"layer":"bottom"}'], BRIDGE)
    manifest["operations"]["bridgeSave"] = run("08-bridge-save", ["pcb", "save"], BRIDGE)
    manifest["operations"]["bridgeReload"] = run("09-bridge-reload", ["doc", "reload", BRIDGE], BRIDGE)
    bridge_dump_path = unique_path(OUT / "bridge-fresh.json")
    manifest["operations"]["bridgeDump"] = run("10-bridge-dump",
        ["pcb", "dump", "--include-copper", "--out", str(bridge_dump_path)], BRIDGE)
    bridge_after = json.loads(bridge_dump_path.read_text(encoding="utf-8"))
    u8_after = next(c for c in bridge_after["components"] if c["designator"] == "U8")
    if u8_after["layer"] != 2:
        raise RuntimeError("Bridge U8 did not reload on BOTTOM")
    manifest["operations"]["mainDrc"] = run("11-main-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], MAIN, allow_fail=True)
    manifest["operations"]["bridgeDrc"] = run("12-bridge-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], BRIDGE, allow_fail=True)
    manifest["status"] = "SAVED_RELOADED_NATIVE_DRC_FAIL_EXPECTED_UNTIL_FULL_SCHEMATIC_AND_ROUTING"
    path = unique_path(OUT / "manifest.json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path),
        "mainDrc": {k: manifest["operations"]["mainDrc"]["response"].get(k) for k in ("passed", "total", "counts")},
        "bridgeDrc": {k: manifest["operations"]["bridgeDrc"]["response"].get(k) for k in ("passed", "total", "counts")}}, indent=2))


if __name__ == "__main__":
    main()
