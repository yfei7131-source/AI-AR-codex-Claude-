#!/usr/bin/env python3
"""Export official EasyEDA symbols and compare every physical pin with CAD_TERMINALS."""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parent
EVIDENCE = ROOT / "evidence"
OUT = EVIDENCE / "library-symbols"
CLI = Path.home() / ".local/bin/easyeda.exe"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"


def command(args, stem):
    result = subprocess.run([str(CLI), *args, "--project", PROJECT], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    (OUT / f"{stem}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{stem}: {result.stdout}{result.stderr}")
    return json.JSONDecoder().raw_decode(result.stdout)[0]


def norm(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def pins_from_elib(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".elibu")]
        if len(names) != 1:
            raise ValueError(f"Expected one native symbol stream, got {names}")
        objects = []
        for line in archive.read(names[0]).decode("utf-8").splitlines():
            if "||" in line:
                header, payload = line.split("||", 1)
                obj = {**json.loads(header), **json.JSONDecoder().raw_decode(payload)[0]}
                objects.append(obj)
    parents = {}
    attrs = defaultdict(dict)
    for obj in objects:
        if obj.get("type") == "PIN":
            parents[obj["id"]] = obj
        if obj.get("type") == "ATTR":
            attrs[obj.get("parentId")][obj.get("key")] = obj.get("value")
    pins = {}
    for key, pin in parents.items():
        attr = attrs[key]
        number = attr.get("Pin Number")
        if not number or number in pins:
            raise ValueError(f"Missing/duplicate physical symbol pin {number}")
        pins[number] = {"name": attr.get("Pin Name"), "type": attr.get("Pin Type"),
                        "x": pin.get("x"), "y": pin.get("y"), "rotation": pin.get("rotation"), "length": pin.get("length")}
    return pins


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    identity = json.loads((EVIDENCE / "library-identity/identity-audit.json").read_text(encoding="utf-8"))
    terminals = list(csv.DictReader((PACKAGE / "kicad/CAD_TERMINALS.csv").open(encoding="utf-8-sig")))
    bom = list(csv.DictReader((PACKAGE / "Inputs/effective_bom.csv").open(encoding="utf-8-sig")))
    expected = defaultdict(dict)
    expected_names = defaultdict(dict)
    for row in terminals:
        item = next(b for b in bom if b["Item_ID"] == row["BOM_Line"])
        expected[item["MPN"]][row["Pin"]] = row["CAD_Reference"]
        expected_names[item["MPN"]][row["Pin"]] = row["Pin_Function"]
    report = []
    for part in identity["parts"]:
        if not part["exactCandidates"]:
            report.append({"mpn": part["mpn"], "status": "BLOCKED", "reason": "No exact library identity."})
            continue
        candidates = part["exactCandidates"]
        if len(candidates) > 1:
            manufacturer = next(b["Manufacturer"] for b in bom if b["MPN"] == part["mpn"])
            brand = norm(manufacturer).replace("texasinstruments", "ti")
            branded = [c for c in candidates if brand and brand in norm(c.get("manufacturer") or "")]
            if len(branded) == 1:
                candidates = branded
            else:
                report.append({"mpn": part["mpn"], "status": "UNVERIFIED", "reason": f"Multiple exact candidates and no unique manufacturer match: {manufacturer}", "candidates": candidates})
                continue
        candidate = candidates[0]
        stem = hashlib.sha256((part["mpn"] + "/" + candidate["uuid"]).encode()).hexdigest()[:16]
        try:
            detail_path = OUT / f"{stem}-device.json"
            if detail_path.is_file():
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
            else:
                detail = command(["lib", "device", "get", "--library", candidate["libraryUuid"], "--uuid", candidate["uuid"]], stem + "-device")
                detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            device = detail["result"]["device"]
            symbol = device["association"]["symbol"]
            source_path = OUT / f"{stem}.elibz2"
            if not source_path.is_file():
                command(["lib", "symbol", "export-source", "--library", symbol["libraryUuid"], "--uuid", symbol["uuid"], "--out", str(source_path)], stem + "-export")
            pins = pins_from_elib(source_path.read_bytes())
            want = expected[part["mpn"]]
            missing = sorted(set(want) - set(pins))
            extra = sorted(set(pins) - set(want))
            names = [{"pin": pin, "source": expected_names[part["mpn"]][pin], "library": pins[pin]["name"]}
                     for pin in sorted(set(want) & set(pins)) if norm(expected_names[part["mpn"]][pin]) != norm(pins[pin]["name"] or "")]
            status = "PASS" if not missing and not extra else "FAIL"
            record = {"mpn": part["mpn"], "status": status, "scope": "Exact library device identity and complete physical symbol-pin identifiers only; footprint not checked.",
                      "device": candidate, "association": device["association"], "lcsc": device["property"].get("supplierId"),
                      "symbolPins": pins, "expectedPins": want, "missingPins": missing, "unexpectedPins": extra,
                      "pinNameDifferences": names, "sourceSha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "sourceFile": source_path.name}
            report.append(record)
            print(f"{status} {part['mpn']} pins={len(pins)} missing={missing} extra={extra} nameDifferences={len(names)}", flush=True)
        except Exception as exc:
            report.append({"mpn": part["mpn"], "status": "UNVERIFIED", "reason": str(exc), "device": candidate})
            print(f"UNVERIFIED {part['mpn']}: {exc}", flush=True)
        (OUT / "symbol-pin-audit.json").write_text(json.dumps({"projectUuid": PROJECT, "scope": "Symbol identity/pins only, no footprint or land-pattern PASS implied", "parts": report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if any(r["status"] == "FAIL" for r in report) else 0

if __name__ == "__main__":
    sys.exit(main())
