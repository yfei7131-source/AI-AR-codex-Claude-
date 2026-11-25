#!/usr/bin/env python3
"""Audit exact EasyEDA device pads in a separate non-manufacturing Board.

Every instance is placed in the audit Board only.  The saved/reloaded native
pad readback is authoritative; library names and symbol pin matches alone are
not a land-pattern or assembly qualification.
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "pad-audit"
PLAN = ROOT / "evidence" / "native-library" / "device-plan.json"
CLI = Path.home() / ".local/bin/easyeda.exe"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
DOC = "271a28697816c22b"


def run(name, args, timeout=120, check=True):
    command = [str(CLI), *args, "--project", PROJECT, "--doc", DOC]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    (OUT / (name + ".log")).write_text("$ " + " ".join(command) + "\n" + result.stdout + result.stderr,
                                       encoding="utf-8")
    try:
        start = result.stdout.find("{")
        parsed = json.JSONDecoder().raw_decode(result.stdout[start:])[0] if start >= 0 else {"message": result.stdout.strip()}
    except Exception as exc:
        raise RuntimeError(f"{name}: unreadable response, see log: {exc}")
    if check and (result.returncode or not parsed.get("ok", True)
                  or parsed.get("result", {}).get("partial") is True
                  or parsed.get("result", {}).get("verified") is False):
        raise RuntimeError(f"{name}: command failed or partial, see log")
    return parsed


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    exact = [p for p in plan["parts"] if p["sourceKind"] == "EXACT_SYSTEM_SYMBOL_PIN_SET_PASS"]
    groups = defaultdict(list)
    for part in exact:
        key = (part["device"]["deviceUuid"], part["device"]["libraryUuid"])
        groups[key].append(part)
    current = run("00-active", ["project", "doc"])
    if current.get("result", {}).get("document", {}).get("uuid") not in {None, DOC}:
        # Some CLI versions use documentUuid instead of a nested document object.
        if current["result"].get("documentUuid") != DOC:
            raise RuntimeError("Audit PCB is not active; refusing writes")
    run("01-switch", ["doc", "switch", DOC])
    before = run("02-before-list", ["pcb", "list", "--include-bbox", "--include-pads"])
    existing = before.get("result", {}).get("components", [])
    known = {c.get("designator"): c for c in existing}
    placement = []
    for i, ((device_uuid, library_uuid), parts) in enumerate(groups.items()):
        ref = "AUDIT_ESP32" if parts[0]["device"]["deviceUuid"] == "6b9f2fd1fbdd415a9fe17c35acdeee3b" else f"AUDIT_{i+1:02d}"
        if ref in known:
            print(f"REUSE {ref}: existing audit instance; fresh readback will decide", flush=True)
            placement.append({"ref": ref, "uuid": device_uuid, "library": library_uuid, "reused": True, "parts": parts})
            continue
        x = 400 + (i % 6) * 900
        y = 400 + (i // 6) * 1100
        nets = {p["number"]: p["net"] for p in parts[0]["pins"] if p["localState"] == "CONNECTED" and p["net"]}
        stem = f"place-{i+1:02d}"
        receipt = run(stem, ["pcb", "add-component", "--library", library_uuid, "--uuid", device_uuid,
                             "--designator", ref, "--x", str(x), "--y", str(y),
                             "--nets", json.dumps(nets, separators=(",", ":"))])
        if receipt.get("result", {}).get("bindingVerified") is not True:
            raise RuntimeError(f"{ref}: placement binding not verified")
        placement.append({"ref": ref, "uuid": device_uuid, "library": library_uuid, "reused": False, "parts": parts})
        print(f"PLACED {ref}: {parts[0]['mpn']}", flush=True)
    saved = run("03-save", ["pcb", "save"])
    if saved.get("result", {}).get("saved") is not True:
        raise RuntimeError("Audit Board save did not return saved:true")
    run("04-reload", ["doc", "reload", DOC], timeout=150)
    after = run("05-after-reload-list", ["pcb", "list", "--include-bbox", "--include-pads"])
    (OUT / "audit-pads-fresh.json").write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run("06-after-reload-dump", ["pcb", "dump", "--include-copper", "--out", str(OUT / "audit-board-after.json")])
    components = after.get("result", {}).get("components", [])
    by_ref = {c.get("designator"): c for c in components}
    audit = []
    for entry in placement:
        ref = entry["ref"]
        part = entry["parts"][0]
        expected = {p["number"] for p in part["pins"]}
        component = by_ref.get(ref)
        pads = component.get("pads", []) if component else []
        observed = {p.get("padNumber") for p in pads}
        geometry_ok = bool(pads) and all(p.get("availability", {}).get("shape") == "available"
                                          and p.get("shape") for p in pads)
        pin_pass = bool(component) and expected == observed and geometry_ok
        audit.append({
            "auditReference": ref,
            "cadReferences": [{"board": p["board"], "ref": p["cadReference"], "sourceRef": p["sourceReference"]} for p in entry["parts"]],
            "mpn": part["mpn"], "device": entry["parts"][0]["device"],
            "expectedPinNumbers": sorted(expected), "observedPadNumbers": sorted(x for x in observed if x),
            "missingPadNumbers": sorted(expected - observed), "unexpectedPadNumbers": sorted(observed - expected),
            "padCount": len(pads), "nativePadGeometryAvailable": geometry_ok,
            "pinPadSetStatus": "PASS" if pin_pass else "FAIL",
            "primitiveId": component.get("primitiveId") if component else None,
            "anchor": {k: component.get(k) for k in ("x", "y", "rotation", "layer")} if component else None,
            "bbox": component.get("bbox") if component else None,
            "uniqueId": component.get("uniqueId") if component else None,
            "landPatternQualification": "UNVERIFIED",
            "scope": "Native placed-pad readback only; not supplier land-pattern, mask/paste, installed fit, or assembly approval."
        })
    report = {
        "scope": "Exact-system device physical pin-to-pad identifiers and observed native geometry in a separate audit Board; NOT FOR FAB",
        "projectUuid": PROJECT, "auditBoard": "evt1-footprint-audit", "auditPcbUuid": DOC,
        "source": str(PLAN.relative_to(ROOT)), "sourceSha256": hashlib.sha256(plan_bytes).hexdigest(),
        "saved": True, "reloaded": True, "devices": audit,
        "passed": sum(a["pinPadSetStatus"] == "PASS" for a in audit),
        "failed": sum(a["pinPadSetStatus"] != "PASS" for a in audit),
        "limitations": ["Supplier mechanical land/paste pattern is not approved.", "System-library pad identity does not verify supplier stock or assembly.", "Audit placement and nets are not manufacturing-board placement or routed connectivity."],
    }
    (OUT / "native-pad-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"AUDIT PASS={report['passed']} FAIL={report['failed']} saved/reloaded", flush=True)
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"AUDIT BLOCKED: {exc}", file=sys.stderr)
        raise
