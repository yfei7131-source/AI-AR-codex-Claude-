#!/usr/bin/env python3
"""Resolve only observed native board-outline pad violations by bounded moves."""
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout" / "refinement-2"
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


def parse_log(path):
    text = path.read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(text[text.find("{"):])[0]


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


def center(comp):
    return ((comp["bbox"]["minX"] + comp["bbox"]["maxX"]) / 2,
            (comp["bbox"]["minY"] + comp["bbox"]["maxY"]) / 2)


def signature(comp):
    return sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                  for p in comp["pads"])


def pad_min_y(pad):
    if pad["shape"][0] == "POLYGON":
        coordinates = pad["shape"][1]
        values = [v for v in coordinates if isinstance(v, (int, float))]
        return min(values[1::2])
    if pad["shape"][0] in ("RECT", "OVAL", "ELLIPSE"):
        return pad["y"] - pad["height"] / 2
    raise RuntimeError(f"Unsupported pad geometry for bounded edge audit: {pad['shape'][0]}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"scope": "BOUNDED_NATIVE_EDGE_CLEARANCE_REFINEMENT_NOT_FOR_FAB",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "source": "layout/refinement-1", "rulesChanged": False,
                "outlinesChanged": False, "routingAuthored": False,
                "nativeRequiredClearanceSource": "Observed DRC message; add 0.01 mm positional margin, never reduce requirement.",
                "operations": {}, "mainMoves": {}, "bridgeMove": {}}
    manifest["operations"]["health"] = run("00-health", ["health"], MAIN)
    main_dump = json.loads((ROOT / "layout/refinement-1/main-fresh.json").read_text(encoding="utf-8"))
    main_drc_path = ROOT / "layout/refinement-1/10-main-native-drc.log"
    main_drc = parse_log(main_drc_path)
    owner = {p["primitiveId"]: c["designator"] for c in main_dump["components"] for p in c["pads"]}
    deficits = {}
    for violation in main_drc["violations"]:
        if violation.get("objType") != "Board Outline to SMD Pad":
            continue
        match = re.search(r"distance is ([0-9.]+)mil, should be >= ([0-9.]+)mil", violation["message"])
        if not match:
            raise RuntimeError("Cannot parse observed native edge clearance")
        refs = {owner[obj] for obj in violation.get("objs", []) if obj in owner}
        if len(refs) != 1:
            raise RuntimeError(f"Cannot uniquely attribute edge violation: {violation}")
        ref = next(iter(refs))
        deficit_mm = (float(match.group(2)) - float(match.group(1))) / MM
        deficits[ref] = max(deficits.get(ref, 0), deficit_mm)
    if set(deficits) != {"U13", "U14", "U15"}:
        raise RuntimeError(f"Unexpected main board-edge violation set: {sorted(deficits)}")
    before_signatures = {c["designator"]: signature(c) for c in main_dump["components"]}
    for index, ref in enumerate(("U13", "U14", "U15"), start=1):
        comp = component(main_dump, ref)
        x, y = center(comp)
        shift = deficits[ref] + 0.01
        target_x = x - shift * MM
        manifest["mainMoves"][ref] = {"primitiveId": comp["primitiveId"],
            "maximumObservedDeficitMm": deficits[ref], "marginMm": 0.01,
            "oldCenterMm": {"x": x / MM, "y": y / MM},
            "targetCenterMm": {"x": target_x / MM, "y": y / MM}}
        manifest["operations"][f"mainMove_{ref}"] = run(f"{index:02d}-main-{ref}-move",
            ["pcb", "modify", "--id", comp["primitiveId"], "--center", "--x", str(target_x), "--y", str(y)], MAIN)
    manifest["operations"]["mainSave"] = run("04-main-save", ["pcb", "save"], MAIN)
    manifest["operations"]["mainReload"] = run("05-main-reload", ["doc", "reload", MAIN], MAIN)
    main_after_path = unique_path(OUT / "main-fresh.json")
    manifest["operations"]["mainDump"] = run("06-main-dump",
        ["pcb", "dump", "--include-copper", "--out", str(main_after_path)], MAIN)
    main_after = json.loads(main_after_path.read_text(encoding="utf-8"))
    for comp in main_after["components"]:
        if signature(comp) != before_signatures[comp["designator"]]:
            raise RuntimeError(f"Pad signature changed for {comp['designator']}")

    bridge_path = ROOT / "layout/refinement-1/bridge-fresh.json"
    bridge_before = json.loads(bridge_path.read_text(encoding="utf-8"))
    u8 = component(bridge_before, "U8")
    u8_signature = signature(u8)
    manifest["operations"]["bridgeRotate"] = run("07-bridge-U8-rotate",
        ["pcb", "modify", "--id", u8["primitiveId"], "--patch", '{"rotation":90}'], BRIDGE)
    manifest["operations"]["bridgeRotateSave"] = run("08-bridge-rotate-save", ["pcb", "save"], BRIDGE)
    manifest["operations"]["bridgeRotateReload"] = run("09-bridge-rotate-reload",
        ["doc", "reload", BRIDGE], BRIDGE)
    rotated_path = unique_path(OUT / "bridge-rotated-fresh.json")
    manifest["operations"]["bridgeRotatedDump"] = run("10-bridge-rotated-dump",
        ["pcb", "dump", "--include-copper", "--out", str(rotated_path)], BRIDGE)
    rotated = json.loads(rotated_path.read_text(encoding="utf-8"))
    u8_rotated = component(rotated, "U8")
    x, y = center(u8_rotated)
    minimum_pad_y = min(pad_min_y(p) for p in u8_rotated["pads"])
    delta = max(0, 0.31 * MM - minimum_pad_y)
    target_y = y + delta
    manifest["bridgeMove"] = {"primitiveId": u8["primitiveId"],
        "postRotationMinimumPadYMm": minimum_pad_y / MM,
        "targetMinimumPadYMm": 0.31, "translationMm": delta / MM,
        "targetCenterMm": {"x": x / MM, "y": target_y / MM}}
    manifest["operations"]["bridgeCenter"] = run("11-bridge-U8-center",
        ["pcb", "modify", "--id", u8["primitiveId"], "--center", "--x", str(x), "--y", str(target_y)], BRIDGE)
    manifest["operations"]["bridgeSave"] = run("12-bridge-save", ["pcb", "save"], BRIDGE)
    manifest["operations"]["bridgeReload"] = run("13-bridge-reload", ["doc", "reload", BRIDGE], BRIDGE)
    bridge_after_path = unique_path(OUT / "bridge-fresh.json")
    manifest["operations"]["bridgeDump"] = run("14-bridge-dump",
        ["pcb", "dump", "--include-copper", "--out", str(bridge_after_path)], BRIDGE)
    bridge_after = json.loads(bridge_after_path.read_text(encoding="utf-8"))
    if signature(component(bridge_after, "U8")) != u8_signature:
        raise RuntimeError("U8 pad signature changed")
    manifest["operations"]["mainDrc"] = run("15-main-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], MAIN, allow_fail=True)
    manifest["operations"]["bridgeDrc"] = run("16-bridge-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], BRIDGE, allow_fail=True)
    manifest["status"] = "SAVED_RELOADED_NATIVE_DRC_FAIL_EXPECTED_UNTIL_FULL_SCHEMATIC_AND_ROUTING"
    path = unique_path(OUT / "manifest.json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path),
        "mainDrc": {k: manifest["operations"]["mainDrc"]["response"].get(k) for k in ("passed", "total", "counts")},
        "bridgeDrc": {k: manifest["operations"]["bridgeDrc"]["response"].get(k) for k in ("passed", "total", "counts")},
        "bridgeMove": manifest["bridgeMove"]}, indent=2))


if __name__ == "__main__":
    main()
