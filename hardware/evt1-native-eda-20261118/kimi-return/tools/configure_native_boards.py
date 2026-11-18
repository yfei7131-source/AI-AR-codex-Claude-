#!/usr/bin/env python3
"""Persist approved board envelopes/rules; preserve partial RF-region failures."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
CLI = Path.home() / ".local/bin/easyeda.exe"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
MM = 1000.0 / 25.4
BOARDS = {
    "main": ("evt1-main-left", "8fbc3cae65886fe5"),
    "bridge": ("evt1-optical-bridge", "9ce45f14cb79dc9d"),
    "right": ("evt1-audio-right", "1db01a36f669a47a"),
}


def decode(result):
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    start = result.stdout.find("{")
    if start >= 0:
        return json.JSONDecoder().raw_decode(result.stdout[start:])[0]
    return {"ok": True, "result": {"message": result.stdout.strip()}}


def call(board, name, args, *, allow_partial=False):
    command = [str(CLI), *args, "--project", PROJECT]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    output = result.stdout + result.stderr
    (EVIDENCE / f"{board}-{name}.log").write_text("$ " + " ".join(command) + "\n" + output, encoding="utf-8")
    try:
        parsed = decode(result)
    except Exception:
        if result.returncode and allow_partial and "write not fully verified" in output:
            print(f"{board}: {name} PARTIAL (original log retained)", flush=True)
            return None
        raise
    print(f"{board}: {name} OK", flush=True)
    return parsed


def points(board):
    if board == "main":
        outline = [(0, 0), (5.8, 0), (5.8, 4.2), (8.2, 4.2), (8.2, 14.0), (5.8, 14.0), (5.8, 46.0), (0, 46.0)]
    elif board == "bridge":
        outline = [(0, 0), (4.2, 0), (4.2, 22.0), (0, 22.0)]
    else:
        outline = [(0, 0), (5.2, 0), (5.2, 34.0), (0, 34.0)]
    return [[round(x * MM, 6), round(y * MM, 6)] for x, y in outline]


def same_points(actual, expected):
    if len(actual) != len(expected):
        return False
    return any(all(abs(a[0] - b[0]) < 0.001 and abs(a[1] - b[1]) < 0.001
                   for a, b in zip(actual[n:] + actual[:n], oriented))
               for oriented in (expected, list(reversed(expected))) for n in range(len(actual)))


def configured(result):
    cfg = result["result"]["ruleConfiguration"]
    track = cfg["Physics"]["Track"]["copperThickness1oz"]["form"]["data"]
    via = cfg["Physics"]["Via Size"]["viaSize"]["form"]
    safe = cfg["Spacing"]["Safe Spacing"]["copperThickness1oz"]["tables"]["1"]["content"]
    return {
        "track": all(abs(v["minValue"] - 0.05) < 0.00001 and abs(v["defaultValue"] - 0.05) < 0.00001 for v in track.values()),
        "clearance": abs(safe[0][0] - 0.05) < 0.00001,
        "via": (abs(via["viaInnerdiameterMin"] - 0.075) < 0.00001 and abs(via["viaOuterdiameterMin"] - 0.18) < 0.00001
                and abs(via["viaInnerdiameterDefault"] - 0.2) < 0.00001 and abs(via["viaOuterdiameterDefault"] - 0.4) < 0.00001),
        "blindBuried": cfg["Physics"]["Blind/Buried Via"]["blindVia"]["table"],
        "courtyardDevice2Device": cfg["Spacing"]["Other Spacing"]["otherClearance"]["form"]["device2device"],
    }


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    identities = {}
    partial = []
    for board, (name, doc) in BOARDS.items():
        call(board, "open-pcb", ["doc", "open", doc])
        outline = call(board, "outline-resume-read", ["pcb", "outline-get", "--doc", doc])
        actual_outline = outline.get("result", {}).get("points") or []
        if not same_points(actual_outline, points(board)):
            if actual_outline:
                raise RuntimeError(f"{board}: unexpected existing outline {actual_outline}")
            call(board, "outline-set", ["pcb", "outline-set", "--doc", doc, "--points", json.dumps(points(board), separators=(",", ":")), "--line-width", "4"])
        before = call(board, "rules-resume-read", ["pcb", "config", "get", "--doc", doc])
        state = configured(before)
        for suffix, flag, args in [
            ("track", "track", ["pcb", "config", "track", "--doc", doc, "--name", "copperThickness1oz", "--unit", "mm", "--min", "0.05", "--default", "0.05"]),
            ("clearance", "clearance", ["pcb", "config", "clearance", "--doc", doc, "--name", "copperThickness1oz", "--unit", "mm", "--track-to-track", "0.05"]),
            ("via", "via", ["pcb", "config", "via", "--doc", doc, "--name", "viaSize", "--unit", "mm", "--min-hole", "0.075", "--min-outer", "0.18", "--default-hole", "0.2", "--default-outer", "0.4"]),
        ]:
            if not state[flag]:
                call(board, suffix + "-dry-run", [*args, "--dry-run"])
                call(board, suffix, args)
        layers = call(board, "stackup-resume-read", ["pcb", "stackup", "show", "--doc", doc])
        copper = layers.get("result", {}).get("copperLayerCount")
        layer_rows = layers.get("result", {}).get("layers", [])
        layer_types = {r["id"]: r.get("type") for r in layer_rows if r.get("id") in {1, 2, 15, 16, 17, 18}}
        if copper != 6 or layer_types != {1: "SIGNAL", 2: "SIGNAL", 15: "PLANE", 16: "SIGNAL", 17: "PLANE", 18: "SIGNAL"}:
            call(board, "stackup", ["pcb", "stackup", "set", "--doc", doc, "--layers", "6", "--plane", "15", "--signal", "16", "--plane", "17", "--signal", "18"])
        regions = call(board, "regions-resume-read", ["pcb", "region", "list", "--doc", doc]).get("result", {}).get("regions", [])
        if board in {"main", "right"}:
            height = 4.2 if board == "main" else 4.0
            width = 5.8 if board == "main" else 5.2
            for layer in [1, 2, 15, 16, 17, 18]:
                found = [r for r in regions if r.get("layer") == layer and set(r.get("ruleType", [])) == {5, 7}
                         and r.get("bbox") and abs(r["bbox"]["minX"] + 0.1) < 0.01 and abs(r["bbox"]["minY"] + 0.1) < 0.01
                         and abs(r["bbox"]["maxX"] - width * MM - 0.1) < 0.01 and abs(r["bbox"]["maxY"] - height * MM - 0.1) < 0.01]
                if not found:
                    # Explicit polygon is used because --rect readback was rejected by the connector verifier.
                    result = call(board, f"rf-keepout-layer-{layer}", ["pcb", "region", "create", "--doc", doc,
                         "--points", json.dumps([[0,0],[0,height*MM],[width*MM,height*MM],[width*MM,0]]),
                         "--layer", str(layer), "--rule", "no-wires", "--rule", "no-pours", "--locked"], allow_partial=True)
                    if result is None:
                        partial.append(f"{board}/L{layer}: region exists or may exist; CLI geometry verification failed; inspect fresh readback")
                    regions = call(board, f"regions-after-layer-{layer}", ["pcb", "region", "list", "--doc", doc]).get("result", {}).get("regions", [])
        saved = call(board, "save", ["pcb", "save", "--doc", doc])
        if saved.get("result", {}).get("saved") is not True:
            raise RuntimeError(f"{board}: explicit save failed: {saved}")
        call(board, "reload", ["doc", "reload", doc])
        call(board, "outline-after", ["pcb", "outline-get", "--doc", doc])
        call(board, "rules-after", ["pcb", "config", "get", "--doc", doc])
        call(board, "stackup-after", ["pcb", "stackup", "show", "--doc", doc])
        call(board, "regions-after", ["pcb", "region", "list", "--doc", doc])
        call(board, "dump-after", ["pcb", "dump", "--doc", doc, "--include-copper", "--out", str(EVIDENCE / f"{board}-configured-pcb.json")])
        identities[board] = {"name": name, "pcbUuid": doc, "saved": True}
    (EVIDENCE / "native-board-identities.json").write_text(json.dumps({"projectUuid": PROJECT, "boards": identities}, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "board-rule-limitations.json").write_text(json.dumps({
        "rfRegions": partial,
        "scope": "Explicit save/reload and basic rules do not qualify dielectric stack, impedance, via layer spans, VIPPO or courtyard.",
        "blocked": ["Supplier-accepted 6-layer 2+2+2 VIPPO stack and bridge 0.50 mm dielectric cross-section", "Microvia/buried-via layer spans and copper fill/cap", "0.20 mm courtyard native device2device rule", "0.25 mm copper-to-board-edge matrix rule", "Supplier-derived RF and USB impedance geometry"]}, indent=2) + "\n", encoding="utf-8")
    print("PARTIAL: all three boards saved/reloaded; unresolved RF region write verification and qualification remain recorded.", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
