#!/usr/bin/env python3
"""Bounded native moves for observed U15/U18 via and Q1/MK1 slot conflicts."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout" / "refinement-3"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
DOC = "8fbc3cae65886fe5"
MM = 1000 / 25.4
MOVES = {
    "U18": (0.0, -0.96, "Move all right-side pads below the lowest conflicting SoC via row; candidate margin, not a proof of optimality."),
    "U15": (0.0, 2.82, "Move the three left-side pads above the highest conflicting SoC via row while retaining the 8.2 mm-wide board region."),
    "Q1": (0.0, 0.15, "Move pad 2 away from the microphone slot; retain bottom-side bbox separation from U14 and U8."),
}


def unique_path(path):
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-retry-{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many preserved versions of {path}")


def run(name, args, allow_fail=False):
    command = [str(CLI), *args, "--project", PROJECT, "--doc", DOC]
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
    result = {"command": command, "exitCode": completed.returncode,
              "log": str(path.relative_to(ROOT)), "response": parsed}
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Native command failed; see {path}")
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before_path = ROOT / "layout/refinement-2/main-fresh.json"
    before = json.loads(before_path.read_text(encoding="utf-8"))
    components = {c["designator"]: c for c in before["components"]}
    signatures = {ref: sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                              for p in comp["pads"]) for ref, comp in components.items()}
    manifest = {"scope": "BOUNDED_NATIVE_VIA_AND_SLOT_REFINEMENT_NOT_FOR_FAB",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "source": "layout/refinement-2/main-fresh.json", "sourceDrc": "layout/refinement-2/15-main-native-drc.log",
                "rulesChanged": False, "outlinesChanged": False, "routingAuthored": False,
                "libraryOrPlaneObjectsDeleted": False, "moves": {}, "operations": {}}
    manifest["operations"]["health"] = run("00-health", ["health"])
    for index, (ref, (dx_mm, dy_mm, reason)) in enumerate(MOVES.items(), start=1):
        comp = components[ref]
        old_x = (comp["bbox"]["minX"] + comp["bbox"]["maxX"]) / 2
        old_y = (comp["bbox"]["minY"] + comp["bbox"]["maxY"]) / 2
        x = old_x + dx_mm * MM
        y = old_y + dy_mm * MM
        manifest["moves"][ref] = {"primitiveId": comp["primitiveId"], "deltaMm": {"x": dx_mm, "y": dy_mm},
            "reason": reason, "oldCenterMm": {"x": old_x / MM, "y": old_y / MM},
            "targetCenterMm": {"x": x / MM, "y": y / MM}}
        manifest["operations"][f"move_{ref}"] = run(f"{index:02d}-move-{ref}",
            ["pcb", "modify", "--id", comp["primitiveId"], "--center", "--x", str(x), "--y", str(y)])
    manifest["operations"]["save"] = run("04-save", ["pcb", "save"])
    manifest["operations"]["reload"] = run("05-reload", ["doc", "reload", DOC])
    dump_path = unique_path(OUT / "main-fresh.json")
    manifest["operations"]["dump"] = run("06-dump",
        ["pcb", "dump", "--include-copper", "--out", str(dump_path)])
    after = json.loads(dump_path.read_text(encoding="utf-8"))
    for comp in after["components"]:
        ref = comp["designator"]
        actual = sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer")) for p in comp["pads"])
        if actual != signatures[ref]:
            raise RuntimeError(f"Pad signature changed for {ref}")
    manifest["operations"]["drc"] = run("07-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_fail=True)
    drc = manifest["operations"]["drc"]["response"]
    manifest["status"] = "SAVED_RELOADED_NATIVE_DRC_FAIL_EXPECTED_UNTIL_FULL_SCHEMATIC_AND_ROUTING"
    path = unique_path(OUT / "manifest.json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path),
                      "drc": {k: drc.get(k) for k in ("passed", "total", "counts")}}, indent=2))


if __name__ == "__main__":
    main()
