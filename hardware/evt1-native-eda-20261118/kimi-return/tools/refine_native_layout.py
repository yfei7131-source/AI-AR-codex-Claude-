#!/usr/bin/env python3
"""Bounded native placement refinement from review-1 primitive IDs.

Only U1 on M-MAIN-L and Y1 on M-OPT-BRIDGE are changed. No board outline,
design rule, schematic binding, track, via, pour, slot or library object is
changed. Every mutation and subsequent native readback is preserved.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout" / "refinement-1"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
MM = 1000 / 25.4


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
    path.write_text("$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
                    encoding="utf-8")
    parsed = None
    try:
        start = completed.stdout.find("{")
        if start >= 0:
            parsed = json.JSONDecoder().raw_decode(completed.stdout[start:])[0]
    except Exception:
        pass
    record = {"command": command, "exitCode": completed.returncode,
              "log": str(path.relative_to(ROOT)), "response": parsed}
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Native command failed; see {path}")
    return record


def component(dump, ref):
    return next(c for c in dump["components"] if c["designator"] == ref)


def pad_signature(comp):
    return sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                  for p in comp["pads"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "scope": "BOUNDED_NATIVE_CANDIDATE_REFINEMENT_NOT_FOR_FAB",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceReview": "layout/review-1",
        "rulesChanged": False,
        "outlinesChanged": False,
        "routingAuthored": False,
        "operations": {},
    }
    manifest["operations"]["health"] = run("00-health", ["health"],
        "8fbc3cae65886fe5")

    main_doc = "8fbc3cae65886fe5"
    main_before_path = ROOT / "layout/review-1/M-MAIN-L/fresh-board.json"
    main_before = json.loads(main_before_path.read_text(encoding="utf-8"))
    soc = component(main_before, "U1")
    soc_id = soc["primitiveId"]
    manifest["operations"]["mainRotate"] = run("01-main-U1-rotate",
        ["pcb", "modify", "--id", soc_id, "--patch", '{"rotation":90}'], main_doc)
    manifest["operations"]["mainCenter"] = run("02-main-U1-center",
        ["pcb", "modify", "--id", soc_id, "--center", "--x", str(4.1 * MM),
         "--y", str(9.0 * MM)], main_doc)
    manifest["operations"]["mainSave"] = run("03-main-save", ["pcb", "save"], main_doc)
    manifest["operations"]["mainReload"] = run("04-main-reload",
        ["doc", "reload", main_doc], main_doc)
    main_dump_path = unique_path(OUT / "main-fresh.json")
    manifest["operations"]["mainDump"] = run("05-main-fresh-dump",
        ["pcb", "dump", "--include-copper", "--out", str(main_dump_path)], main_doc)
    main_after = json.loads(main_dump_path.read_text(encoding="utf-8"))
    soc_after = component(main_after, "U1")
    if pad_signature(soc) != pad_signature(soc_after):
        raise RuntimeError("SoC pad identity/net/layer signature changed unexpectedly")
    if soc_after["rotation"] != 90 or soc_after["layer"] != 1:
        raise RuntimeError("SoC saved/reloaded rotation/layer mismatch")

    bridge_doc = "9ce45f14cb79dc9d"
    bridge_before_path = ROOT / "layout/review-1/M-OPT-BRIDGE/fresh-board.json"
    bridge_before = json.loads(bridge_before_path.read_text(encoding="utf-8"))
    fpga = component(bridge_before, "U2")
    osc = component(bridge_before, "Y1")
    b3 = next(p for p in fpga["pads"] if p["padNumber"] == "B3")
    output = next(p for p in osc["pads"] if p["padNumber"] == "3")
    if b3["net"] != "clk_48m" or output["net"] != b3["net"]:
        raise RuntimeError("Controlled clk_48m pad mapping mismatch")
    old_distance = math.hypot(b3["x"] - output["x"], b3["y"] - output["y"]) / MM
    old_center_x = (osc["bbox"]["minX"] + osc["bbox"]["maxX"]) / 2
    old_center_y = (osc["bbox"]["minY"] + osc["bbox"]["maxY"]) / 2
    target_x = old_center_x + b3["x"] - output["x"]
    target_y = old_center_y + b3["y"] - output["y"]
    manifest["clockTarget"] = {
        "method": "Translate existing native Y1 bbox center by measured FPGA.B3 minus Y1.3 pad-center delta; no mirroring formula assumed.",
        "oldDistanceMm": old_distance,
        "targetCenterMil": {"x": target_x, "y": target_y},
        "targetCenterMm": {"x": target_x / MM, "y": target_y / MM},
        "sourcePrimitiveIds": {"fpga": fpga["primitiveId"], "oscillator": osc["primitiveId"],
                               "fpgaB3": b3["primitiveId"], "oscillatorPin3": output["primitiveId"]},
    }
    manifest["operations"]["bridgeCenter"] = run("06-bridge-Y1-center",
        ["pcb", "modify", "--id", osc["primitiveId"], "--center", "--x", str(target_x),
         "--y", str(target_y)], bridge_doc)
    manifest["operations"]["bridgeSave"] = run("07-bridge-save", ["pcb", "save"], bridge_doc)
    manifest["operations"]["bridgeReload"] = run("08-bridge-reload",
        ["doc", "reload", bridge_doc], bridge_doc)
    bridge_dump_path = unique_path(OUT / "bridge-fresh.json")
    manifest["operations"]["bridgeDump"] = run("09-bridge-fresh-dump",
        ["pcb", "dump", "--include-copper", "--out", str(bridge_dump_path)], bridge_doc)
    bridge_after = json.loads(bridge_dump_path.read_text(encoding="utf-8"))
    fpga_after = component(bridge_after, "U2")
    osc_after = component(bridge_after, "Y1")
    if pad_signature(osc) != pad_signature(osc_after):
        raise RuntimeError("Oscillator pad identity/net/layer signature changed unexpectedly")
    b3_after = next(p for p in fpga_after["pads"] if p["padNumber"] == "B3")
    output_after = next(p for p in osc_after["pads"] if p["padNumber"] == "3")
    new_distance = math.hypot(b3_after["x"] - output_after["x"],
                              b3_after["y"] - output_after["y"]) / MM
    manifest["clockResult"] = {
        "distanceMm": new_distance,
        "fpgaB3Mm": {"x": b3_after["x"] / MM, "y": b3_after["y"] / MM},
        "oscillatorPin3Mm": {"x": output_after["x"] / MM, "y": output_after["y"] / MM},
        "centerMm": {"x": (osc_after["bbox"]["minX"] + osc_after["bbox"]["maxX"]) / 2 / MM,
                     "y": (osc_after["bbox"]["minY"] + osc_after["bbox"]["maxY"]) / 2 / MM},
        "signalIntegrityStatus": "UNVERIFIED_NO_ROUTING_OR_VIA_AUTHORED",
    }
    manifest["operations"]["mainDrc"] = run("10-main-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], main_doc, allow_fail=True)
    manifest["operations"]["bridgeDrc"] = run("11-bridge-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], bridge_doc, allow_fail=True)
    manifest["status"] = "NATIVE_REFINEMENT_SAVED_RELOADED_DRC_LOGS_REQUIRE_REVIEW"
    path = unique_path(OUT / "manifest.json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "clockOldDistanceMm": old_distance,
                      "clockNewDistanceMm": new_distance,
                      "mainDrc": manifest["operations"]["mainDrc"].get("response"),
                      "bridgeDrc": manifest["operations"]["bridgeDrc"].get("response")}, indent=2))


if __name__ == "__main__":
    main()
