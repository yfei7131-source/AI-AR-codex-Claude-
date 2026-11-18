#!/usr/bin/env python3
"""Apply the reviewed partial placement plan to real EasyEDA PCB documents.

This script places only audited exact system Devices. It does not create tracks,
vias, pours, connector stand-ins, custom footprints, or schematic bindings.
Every write is followed by a fresh component read; every successful board ends
with save -> doc reload -> fresh list/dump. Raw command responses are preserved.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "layout"
LOGS = OUT / "logs"
PLAN = OUT / "candidate-placement-plan.json"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
CLI = Path.home() / ".local/bin/easyeda.exe"
MM = 39.37007874015748
CENTER_TOLERANCE_MIL = 0.10


class CommandError(RuntimeError):
    pass


def unique_path(path):
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-retry-{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many preserved evidence versions: {path}")


def run(board, name, args, doc, timeout=150, check=True):
    command = [str(CLI), *args, "--project", PROJECT, "--doc", doc]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    log = unique_path(LOGS / f"{board}-{name}.log")
    log.write_text("$ " + " ".join(command) + "\n" + result.stdout + result.stderr,
                   encoding="utf-8")
    try:
        start = result.stdout.find("{")
        parsed = json.JSONDecoder().raw_decode(result.stdout[start:])[0] if start >= 0 else {"message": result.stdout.strip()}
    except Exception as exc:
        raise CommandError(f"{board}/{name}: unreadable response; {log}; {exc}")
    failed = (result.returncode or not parsed.get("ok", True)
              or parsed.get("result", {}).get("partial") is True
              or parsed.get("result", {}).get("verified") is False)
    if check and failed:
        raise CommandError(f"{board}/{name}: failed or partial; see {log}")
    return parsed


def components(response):
    return response.get("result", {}).get("components", [])


def component_by_ref(response, ref):
    matches = [c for c in components(response) if c.get("designator") == ref]
    if len(matches) != 1:
        raise CommandError(f"Expected one {ref}, found {len(matches)}")
    return matches[0]


def expected_nets(part):
    return {p["number"]: p["net"] for p in part["pins"]
            if p["localState"] == "CONNECTED" and p["net"]}


def check_component(component, part, label):
    errors = []
    expected = expected_nets(part)
    pads = component.get("pads", [])
    observed_numbers = [p.get("padNumber") for p in pads]
    expected_numbers = {p["number"] for p in part["pins"]}
    # One logical pad number may intentionally have multiple copper primitives,
    # e.g. IM69D130 pad 5 has four shaped ground/mounting regions. Compare the
    # distinct identifier set and verify every physical region's net separately.
    if set(observed_numbers) != expected_numbers:
        errors.append("distinct physical pad-number set mismatch")
    duplicate_numbers = sorted({n for n in observed_numbers if observed_numbers.count(n) > 1})
    for pad in pads:
        number = pad.get("padNumber")
        expected_net = expected.get(number, "")
        if pad.get("net", "") != expected_net:
            errors.append(f"pad {number} net {pad.get('net')!r} != {expected_net!r}")
        if not pad.get("shape") or pad.get("availability", {}).get("shape") != "available":
            errors.append(f"pad {number} geometry unavailable")
    if component.get("layer") != (1 if part["layer"] == "TOP" else 2):
        errors.append("assembly layer mismatch")
    if abs(float(component.get("rotation", 9999)) - float(part["rotation"])) > 0.001:
        errors.append("rotation mismatch")
    center = component.get("center", {})
    for axis in ("x", "y"):
        target = part["center"][axis] * MM
        if not isinstance(center.get(axis), (int, float)) or abs(center[axis] - target) > CENTER_TOLERANCE_MIL:
            errors.append(f"bbox center {axis} {center.get(axis)!r} != {target!r} mil")
    if component.get("uniqueId", "") != "":
        errors.append("unexpected schematic uniqueId on an explicitly unbound candidate")
    manufacturer = component.get("manufacturerId")
    if manufacturer is not None and manufacturer.casefold() != part["mpn"].casefold():
        errors.append(f"manufacturerId {manufacturer!r} != {part['mpn']!r} (case-insensitive identity)")
    if component.get("availability", {}).get("bbox") != "available" or component.get("availability", {}).get("pads") != "available":
        errors.append("component bbox/pad capture incomplete")
    return {
        "ref": part["ref"], "sourceRef": part["sourceRef"], "stage": label,
        "primitiveId": component.get("primitiveId"), "uniqueId": component.get("uniqueId", ""),
        "schematicBinding": "UNBOUND_CONTROLLED_NETLIST_CANDIDATE",
        "expectedCenterMm": part["center"], "observedCenterMil": center,
        "anchorMil": {"x": component.get("x"), "y": component.get("y")},
        "rotation": component.get("rotation"), "layer": component.get("layer"),
        "bboxMil": component.get("bbox"), "physicalPadPrimitiveCount": len(pads),
        "distinctPadNumberCount": len(set(observed_numbers)),
        "intentionallyRepeatedPadNumbers": duplicate_numbers,
        "connectedLogicalPadCount": len(expected),
        "ncAndLocalNcLogicalPadsRemainNetless": len(expected_numbers - set(expected)),
        "manufacturerId": component.get("manufacturerId"),
        "verificationErrors": errors,
        "verified": not errors,
    }


def fresh_list(board, doc, name):
    return run(board, name, ["pcb", "list", "--include-bbox", "--include-pads"], doc)


def dump(board, doc, name):
    path = unique_path(OUT / f"{board}-{name}.json")
    response = run(board, name, ["pcb", "dump", "--include-copper", "--out", str(path)], doc)
    return path, response


def apply_board(board, data):
    doc = data["pcbUuid"]
    result = {
        "board": board, "pcbUuid": doc, "projectUuid": PROJECT,
        "scope": "PARTIAL_UNROUTED_CANDIDATE_NOT_FOR_FAB",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "planSha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "placements": [], "offlineFailedPlacements": data["failedPlacements"],
        "requiredButNotPlaced": data["requiredButNotPlaced"],
        "routing": {"tracksViasPoursAuthored": False, "status": "UNROUTED"},
        "status": "IN_PROGRESS",
    }
    result_path = unique_path(OUT / f"{board}-placement-result.json")

    def preserve():
        result["finishedAt"] = datetime.now(timezone.utc).isoformat()
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        run(board, "00-switch", ["doc", "switch", doc], doc)
        before_path, _ = dump(board, doc, "01-before-dump")
        result["beforeDump"] = str(before_path.relative_to(ROOT))
        before = fresh_list(board, doc, "02-before-list")
        existing = components(before)
        expected_refs = {p["ref"] for p in data["placements"]}
        unexpected = [c.get("designator") for c in existing if c.get("designator") not in expected_refs]
        if unexpected:
            raise CommandError(f"Precondition refused: unexpected target components {unexpected}; reconcile actual state")
        existing_by_ref = {}
        for component in existing:
            ref = component.get("designator")
            if ref in existing_by_ref:
                raise CommandError(f"Precondition refused: duplicate designator {ref}")
            existing_by_ref[ref] = component
        result["resumePrecondition"] = {
            "freshExistingCount": len(existing),
            "freshExistingRefs": sorted(existing_by_ref),
            "unexpectedRefs": unexpected,
            "policy": "Reuse only plan refs with exact distinct pads, nets, MPN, layer, rotation and empty uniqueId; center is the only recoverable difference.",
        }
        for index, part in enumerate(data["placements"], 1):
            component = existing_by_ref.get(part["ref"])
            reused = component is not None
            if reused:
                initial_check = check_component(component, part, "resume-precheck")
                non_center_errors = [e for e in initial_check["verificationErrors"] if not e.startswith("bbox center ")]
                if non_center_errors:
                    raise CommandError(f"{part['ref']}: existing candidate differs beyond center: {non_center_errors}")
                after_center = before if initial_check["verified"] else None
            else:
                nets = expected_nets(part)
                receipt = run(board, f"place-{index:02d}-{part['ref']}", [
                    "pcb", "add-component", "--library", part["device"]["libraryUuid"],
                    "--uuid", part["device"]["deviceUuid"], "--designator", part["ref"],
                    "--x", str(part["center"]["x"] * MM), "--y", str(part["center"]["y"] * MM),
                    "--rotation", str(part["rotation"]), "--layer", "1" if part["layer"] == "TOP" else "2",
                    "--nets", json.dumps(nets, separators=(",", ":")),
                ], doc)
                placement_receipt = receipt.get("result", {})
                if placement_receipt.get("bindingVerified") is not True or placement_receipt.get("uniqueId", "") != "":
                    raise CommandError(f"{part['ref']}: binding/device placement receipt not verified")
                after_add = fresh_list(board, doc, f"place-{index:02d}-{part['ref']}-read")
                component = component_by_ref(after_add, part["ref"])
                after_center = None
            if after_center is None:
                run(board, f"center-{index:02d}-{part['ref']}", [
                    "pcb", "modify", "--id", component["primitiveId"], "--center",
                    "--x", str(part["center"]["x"] * MM), "--y", str(part["center"]["y"] * MM),
                ], doc)
                after_center = fresh_list(board, doc, f"center-{index:02d}-{part['ref']}-read")
            verification = check_component(component_by_ref(after_center, part["ref"]), part, "immediate")
            verification["reusedFromFreshReadback"] = reused
            if not reused:
                verification["placementReceipt"] = placement_receipt
            result["placements"].append(verification)
            if not verification["verified"]:
                raise CommandError(f"{part['ref']}: immediate verification failed: {verification['verificationErrors']}")
            print(f"{board} VERIFIED {part['ref']} {part['sourceRef']} ({index}/{len(data['placements'])})", flush=True)
            preserve()
        saved = run(board, "90-save", ["pcb", "save"], doc)
        if saved.get("result", {}).get("saved") is not True:
            raise CommandError(f"{board}: save did not return saved:true")
        result["saved"] = True
        run(board, "91-reload", ["doc", "reload", doc], doc, timeout=180)
        result["reloaded"] = True
        after = fresh_list(board, doc, "92-after-reload-list")
        actual = components(after)
        if len(actual) != len(data["placements"]):
            raise CommandError(f"{board}: post-reload component count {len(actual)} != {len(data['placements'])}")
        final_checks = []
        for part in data["placements"]:
            check = check_component(component_by_ref(after, part["ref"]), part, "saved-reloaded")
            final_checks.append(check)
            if not check["verified"]:
                raise CommandError(f"{part['ref']}: saved/reloaded verification failed: {check['verificationErrors']}")
        result["placements"] = final_checks
        after_path, _ = dump(board, doc, "93-after-reload-dump")
        result["afterDump"] = str(after_path.relative_to(ROOT))
        result["savedReloadedVerified"] = True
        result["candidateComponentCount"] = len(final_checks)
        result["status"] = "PARTIAL_CANDIDATE_LIVE_VERIFIED_UNROUTED"
    except Exception as exc:
        result["status"] = "FAILED_OR_PARTIAL_READBACK_REQUIRED"
        result["error"] = str(exc)
        try:
            recovery = fresh_list(board, doc, "99-failure-recovery-list")
            result["failureReadback"] = [{
                "ref": c.get("designator"), "primitiveId": c.get("primitiveId"),
                "center": c.get("center"), "layer": c.get("layer"), "rotation": c.get("rotation"),
                "uniqueId": c.get("uniqueId"), "padCount": len(c.get("pads", [])),
            } for c in components(recovery)]
        except Exception as recovery_exc:
            result["failureReadbackError"] = str(recovery_exc)
        preserve()
        raise
    preserve()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--boards", nargs="*", choices=["M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"],
                        default=["M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    failures = 0
    for board in args.boards:
        try:
            result = apply_board(board, plan["boards"][board])
            print(f"{board} SAVED/RELOADED {result['candidateComponentCount']} candidates; UNROUTED", flush=True)
        except Exception as exc:
            failures += 1
            print(f"{board} BLOCKED/PARTIAL: {exc}", file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
