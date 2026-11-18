#!/usr/bin/env python3
"""Build controlled native symbol-only devices for unresolved EVT-1 parts.

Exact EasyEDA devices are reused only after their complete physical symbol pin
number set passes. No footprint is attached to newly authored symbol-only devices;
--pcb=false prevents accidental transfer of unqualified copper to the PCB.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parent
EVIDENCE = ROOT / "evidence"
OUT = EVIDENCE / "native-library"
CLI = Path.home() / ".local/bin/easyeda.exe"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
BOARDS = ["M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"]


def read_csv(path):
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decode(output):
    start = output.find("{")
    if start >= 0:
        return json.JSONDecoder().raw_decode(output[start:])[0]
    return {"ok": True, "message": output.strip()}


def command(args, log):
    result = subprocess.run([str(CLI), *args, "--project", PROJECT], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("$ " + " ".join([str(CLI), *args, "--project", PROJECT]) + "\n" + result.stdout + result.stderr,
                   encoding="utf-8")
    parsed = decode(result.stdout)
    details = parsed.get("result", {}) if isinstance(parsed, dict) else {}
    if result.returncode or not parsed.get("ok", True) or details.get("partial") or details.get("verified") is False:
        raise RuntimeError(f"{args[:3]} failed or was not verified; original output: {log}")
    return parsed


def asset_identity(receipt, kind):
    keys = [kind + "Uuid", "uuid"]
    for obj in [receipt, receipt.get("result", {}), receipt.get("result", {}).get(kind, {})]:
        if isinstance(obj, dict):
            for key in keys:
                if obj.get(key):
                    return obj[key], obj.get("libraryUuid")
    raise ValueError(f"Cannot locate {kind} identity in {receipt}")


def natural(value):
    return [int(x) if x.isdigit() else x.casefold() for x in re.split(r"(\d+)", value)]


def generic_key(ref, rows):
    pins = {r["Pin"] for r in rows}
    if pins == {"1"} and ref.startswith("TP"):
        return "TP_1P"
    if pins == {"1", "2"}:
        if ref.startswith(("R", "NRF_R")):
            return "R_2P"
        if ref.startswith(("C", "NRF_C")):
            return "C_2P"
        if ref.startswith(("L", "NRF_L")):
            return "L_2P"
        if ref.startswith("TP"):
            return "TP_2P"
    return None


def custom_spec(key, ref, rows, bom):
    generic = generic_key(ref, rows)
    if generic:
        count = 1 if generic == "TP_1P" else 2
        prefix = generic.split("_")[0]
        pins = []
        for i in range(count):
            x = -35 if i == 0 else 35
            if count == 1:
                x = -35
            pins.append({"number": str(i + 1), "name": str(i + 1), "x": x, "y": 0,
                         "rotation": 0 if i == 0 else 180, "length": 20, "pinType": "Undefined"})
        geometry = {"outline": [-15, -7, 15, -7, 15, 7, -15, 7, -15, -7], "pins": pins}
        name = f"EVT1_{generic}_SCHEMATIC_ONLY"
        return {"name": name, "description": "Controlled physical terminals; no fabrication footprint attached",
                "geometry": geometry, "designator": prefix, "manufacturer": "TBD",
                "mpn": "CONTROLLED_SCHEMATIC_ONLY", "properties": {"Fabrication": "BLOCKED_NO_QUALIFIED_FOOTPRINT"}}
    ordered = sorted(rows, key=lambda r: natural(r["Pin"]))
    half = (len(ordered) + 1) // 2
    y_top = (half - 1) * 5
    pins = []
    for index, row in enumerate(ordered):
        left = index < half
        i = index if left else index - half
        y = y_top - i * 10
        role = row["Role"]
        ptype = {"RCV": "Input", "DRV": "Output", "BIDIR": "Bidirectional", "BIDIR_OD": "Bidirectional",
                 "BIDIR_FW": "Bidirectional", "BIDIR_CFG": "Bidirectional", "SINK": "Power", "SRC": "Power"}.get(role, "Undefined")
        pins.append({"number": row["Pin"], "name": row["Pin_Function"] or row["Pin"],
                     "x": -50 if left else 50, "y": y, "rotation": 0 if left else 180,
                     "length": 20, "pinType": ptype})
    height = max(20, half * 10)
    outline = [-30, -height // 2, 30, -height // 2, 30, height // 2, -30, height // 2, -30, -height // 2]
    return {"name": f"EVT1_{ref}_CONTROLLED_SYMBOL", "description": f"Controlled EVT-1 terminals for {ref}; symbol only",
            "geometry": {"outline": outline, "pins": pins}, "designator": re.match(r"[A-Za-z]+", ref).group().upper(),
            "manufacturer": bom["Manufacturer"], "mpn": bom["MPN"],
            "properties": {"Fabrication": "BLOCKED_NO_QUALIFIED_FOOTPRINT", "EVT1_BOM_Line": bom["Item_ID"]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Create only the custom asset containing this CAD reference")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    terminals = read_csv(PACKAGE / "kicad/CAD_TERMINALS.csv")
    bom = {r["Item_ID"]: r for r in read_csv(PACKAGE / "Inputs/effective_bom.csv")}
    groups = defaultdict(list)
    for row in terminals:
        groups[(row["Board"], row["CAD_Reference"])].append(row)
    audit = {p["mpn"]: p for p in json.loads((EVIDENCE / "library-symbols/symbol-pin-audit.json").read_text(encoding="utf-8"))["parts"]}
    plan = []
    customs = {}
    for (board, ref), rows in groups.items():
        source = rows[0]["Source_RefDes"]
        item = bom[rows[0]["BOM_Line"]]
        record = audit.get(item["MPN"], {})
        exact = record.get("status") == "PASS" and not record.get("missingPins") and not record.get("unexpectedPins") and rows[0]["PCB_Use"] == "BOARD"
        if exact:
            candidate = record["device"]
            device = {"deviceUuid": candidate["uuid"], "libraryUuid": candidate["libraryUuid"], "name": candidate["name"]}
            source_kind = "EXACT_SYSTEM_SYMBOL_PIN_SET_PASS"
        else:
            key = generic_key(ref, rows) or f"{board}__{ref}"
            custom = custom_spec(key, ref, rows, item)
            customs.setdefault(key, custom)
            device = {"customKey": key}
            source_kind = "CONTROLLED_SYMBOL_ONLY_PCB_FALSE"
        plan.append({"board": board, "cadReference": ref, "sourceReference": source, "bomLine": item["Item_ID"],
                     "mpn": item["MPN"], "pcbUse": rows[0]["PCB_Use"], "sourceKind": source_kind,
                     "device": device, "pinCount": len(rows),
                     "pins": [{"number": r["Pin"], "name": r["Pin_Function"], "net": r["CAD_Net"],
                               "localState": r["Local_State"], "role": r["Role"]} for r in rows]})
    dump(OUT / "device-plan.json", {"projectUuid": PROJECT, "scope": "Physical symbol pins; system footprints remain unverified until native pad readback", "parts": plan})
    dump(OUT / "custom-symbol-specs.json", customs)
    print(f"PLAN components={len(plan)} exactSystem={sum(p['sourceKind'].startswith('EXACT') for p in plan)} customAssets={len(customs)}", flush=True)
    if args.plan_only:
        return 0
    state_path = OUT / "native-device-assets.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"assets": {}}
    selected = set()
    if args.only:
        selected = {p["device"].get("customKey") for p in plan if p["cadReference"] == args.only and p["device"].get("customKey")}
        if not selected:
            raise ValueError(f"No custom asset for {args.only}")
    for key, spec in customs.items():
        if selected and key not in selected:
            continue
        safe = hashlib.sha256(key.encode()).hexdigest()[:16]
        stem = OUT / safe
        existing = state["assets"].get(key, {})
        try:
            # Only a build receipt with a concrete tab, all requested pins and
            # verified=true authorizes reuse. Failed or partial assets get a new
            # attempt directory; old evidence and UUIDs are never overwritten.
            attempt = 0
            while True:
                suffix = "" if attempt == 0 else f"-retry-{attempt:02d}"
                symbol_receipt_path = OUT / f"{safe}{suffix}-symbol-create.json"
                build_log = OUT / f"{safe}{suffix}-symbol-build.log"
                if not symbol_receipt_path.is_file() and not build_log.exists():
                    break
                attempt += 1
            if existing.get("status") == "CREATED_SYMBOL_ONLY":
                verified_log = OUT / f"{safe}{existing.get('attemptSuffix', '')}-symbol-build.log"
                receipt = decode(verified_log.read_text(encoding="utf-8"))
                result = receipt.get("result", {})
                if result.get("verified") is True and result.get("tabId") and len(result.get("created", {}).get("pins", [])) == len(spec["geometry"]["pins"]):
                    print(f"REUSE VERIFIED {key} device={existing['deviceUuid']}", flush=True)
                    continue
                raise RuntimeError(f"Recorded asset is not backed by a verified build: {verified_log}")
            symbol_receipt = command(["lib", "symbol", "create", "--scope", "project", "--name", spec["name"],
                                      "--description", spec["description"]], OUT / f"{safe}{suffix}-symbol-create.log")
            dump(symbol_receipt_path, symbol_receipt)
            symbol_uuid, symbol_library = asset_identity(symbol_receipt, "symbol")
            spec_path = OUT / f"{safe}{suffix}-symbol-geometry.json"
            dump(spec_path, spec["geometry"])
            build = command(["lib", "symbol", "build", "--library", symbol_library, "--uuid", symbol_uuid,
                             "--spec", str(spec_path)], build_log)
            built = build.get("result", {}).get("created", {})
            if not build.get("result", {}).get("tabId") or len(built.get("pins", [])) != len(spec["geometry"]["pins"]):
                raise RuntimeError(f"Symbol build did not create every physical pin: {build_log}")
            device_receipt_path = OUT / f"{safe}{suffix}-device-create.json"
            device_receipt = command(["lib", "device", "create", "--library", symbol_library,
                "--name", spec["name"], "--description", spec["description"], "--symbol-library", symbol_library,
                "--symbol-uuid", symbol_uuid, "--designator", spec["designator"], "--manufacturer", spec["manufacturer"],
                "--mpn", spec["mpn"], "--pcb=false", "--properties", json.dumps(spec["properties"], ensure_ascii=False),
            ], OUT / f"{safe}{suffix}-device-create.log")
            dump(device_receipt_path, device_receipt)
            device_uuid, device_library = asset_identity(device_receipt, "device")
            readback = command(["lib", "device", "get", "--library", device_library, "--uuid", device_uuid], OUT / f"{safe}{suffix}-device-readback.log")
            dump(OUT / f"{safe}{suffix}-device-readback.json", readback)
            state["assets"][key] = {"symbolUuid": symbol_uuid, "symbolLibraryUuid": symbol_library,
                                    "deviceUuid": device_uuid, "libraryUuid": device_library,
                                    "name": spec["name"], "pcb": False, "attemptSuffix": suffix, "status": "CREATED_SYMBOL_ONLY"}
            dump(state_path, state)
            print(f"CREATED {key} device={device_uuid}", flush=True)
        except Exception as exc:
            state["assets"][key] = {**existing, "status": "BLOCKED", "reason": str(exc)}
            dump(state_path, state)
            print(f"BLOCKED {key}: {exc}", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
