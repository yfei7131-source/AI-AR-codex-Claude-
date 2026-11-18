#!/usr/bin/env python3
"""Relocate U15 outside the SoC via field and preserve local bbox gaps."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout" / "refinement-4"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
DOC = "8fbc3cae65886fe5"
MM = 1000 / 25.4


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
    before = json.loads((ROOT / "layout/refinement-3/main-fresh.json").read_text(encoding="utf-8"))
    components = {c["designator"]: c for c in before["components"]}
    signatures = {ref: sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer"))
                              for p in comp["pads"]) for ref, comp in components.items()}
    manifest = {"scope": "BOUNDED_U15_RELOCATION_OUTSIDE_SOC_VIA_FIELD_NOT_FOR_FAB",
                "createdAt": datetime.now(timezone.utc).isoformat(), "source": "layout/refinement-3/main-fresh.json",
                "rulesChanged": False, "outlinesChanged": False, "routingAuthored": False,
                "operations": {}, "targets": {},
                "plannedSameSideBboxGapsMm": {"U3_to_U15_minimum": 0.20, "U15_to_U9_minimum": 0.20},
                "qualificationLimits": "Camera routing length, return path, FPC, supplier courtyard and installed mechanics remain UNVERIFIED."}
    manifest["operations"]["health"] = run("00-health", ["health"])
    u15 = components["U15"]
    manifest["operations"]["rotateU15"] = run("01-U15-rotate",
        ["pcb", "modify", "--id", u15["primitiveId"], "--patch", '{"rotation":0}'])
    for index, (ref, x_mm, y_mm, reason) in enumerate((
        ("U15", 2.90, 27.89, "Use vacant bottom-side bay away from all SoC embedded vias."),
        ("U3", 2.90, 25.27, "Shift 0.23 mm toward board start to preserve U3/U15 bbox gap."),
        ("U9", 2.90, 30.74, "Shift 0.24 mm toward board end to preserve U15/U9 bbox gap."),
    ), start=2):
        comp = components[ref]
        old_x = (comp["bbox"]["minX"] + comp["bbox"]["maxX"]) / 2 / MM
        old_y = (comp["bbox"]["minY"] + comp["bbox"]["maxY"]) / 2 / MM
        manifest["targets"][ref] = {"primitiveId": comp["primitiveId"],
            "oldCenterMm": {"x": old_x, "y": old_y}, "targetCenterMm": {"x": x_mm, "y": y_mm}, "reason": reason}
        manifest["operations"][f"center_{ref}"] = run(f"{index:02d}-{ref}-center",
            ["pcb", "modify", "--id", comp["primitiveId"], "--center", "--x", str(x_mm * MM), "--y", str(y_mm * MM)])
    manifest["operations"]["save"] = run("05-save", ["pcb", "save"])
    manifest["operations"]["reload"] = run("06-reload", ["doc", "reload", DOC])
    dump_path = unique_path(OUT / "main-fresh.json")
    manifest["operations"]["dump"] = run("07-dump", ["pcb", "dump", "--include-copper", "--out", str(dump_path)])
    after = json.loads(dump_path.read_text(encoding="utf-8"))
    for comp in after["components"]:
        ref = comp["designator"]
        actual = sorted((p.get("primitiveId"), p.get("padNumber"), p.get("net"), p.get("layer")) for p in comp["pads"])
        if actual != signatures[ref]:
            raise RuntimeError(f"Pad signature changed for {ref}")
    actual_u15 = next(c for c in after["components"] if c["designator"] == "U15")
    if actual_u15["rotation"] != 0:
        raise RuntimeError("U15 saved/reloaded rotation mismatch")
    manifest["operations"]["drc"] = run("08-native-drc",
        ["pcb", "drc", "--strict", "--json", "--timeout", "120"], allow_fail=True)
    drc = manifest["operations"]["drc"]["response"]
    manifest["status"] = "SAVED_RELOADED_NATIVE_DRC_FAIL_EXPECTED_UNTIL_FULL_SCHEMATIC_AND_ROUTING"
    path = unique_path(OUT / "manifest.json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "drc": {k: drc.get(k) for k in ("passed", "total", "counts")}}, indent=2))


if __name__ == "__main__":
    main()
