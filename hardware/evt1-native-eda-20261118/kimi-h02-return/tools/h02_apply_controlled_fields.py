#!/usr/bin/env python3
"""Apply PR31-controlled MPN and external-part flags with per-page guards."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / "hardware/evt1-native-eda-20261118"
RETURN = PACKAGE / "kimi-h02-return"
BEFORE = RETURN / "working-before"
PROJECT = "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"
EDA = Path(r"C:\Users\Admin（无密码）\.local\bin\easyeda.exe")
RUN = RETURN / "field-repair" / ("batch-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
LEDGER: list[dict] = []
AUDITS: dict[str, dict] = {}
SUMMARY: dict = {}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_summary() -> None:
    write_json(RUN / "summary.json", SUMMARY)
    write_json(RUN / "command-ledger.json", LEDGER)


def run(label: str, args: list[str], timeout: int = 240) -> dict:
    command = [str(EDA), *args, "--project", PROJECT]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        code = 124
        timed_out = True
    stdout_path = RUN / f"{label}.stdout.json"
    stderr_path = RUN / f"{label}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8", newline="")
    stderr_path.write_text(stderr, encoding="utf-8", newline="")
    LEDGER.append({"label": label, "command": command, "exitCode": code, "timedOut": timed_out})
    save_summary()
    if code:
        raise RuntimeError(f"{label}: exit {code}; timeout={timed_out}; raw output preserved")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label}: non-JSON response: {exc}") from exc


def read_native_bom(path: Path):
    content = path.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    lines = content.decode(encoding).splitlines(keepends=True)
    delimiter = "\t" if "\t" in lines[0] else ","
    return list(csv.DictReader(lines, delimiter=delimiter))


def audit_device(record: dict, component: dict, before_component: dict, label: str) -> dict | None:
    before_device = before_component.get("device") or {}
    device = component.get("device") or {}
    before_local = before_component.get("component") or {}
    current_local = component.get("component") or {}
    # A modify response may expose only the project-local 16-hex identity, while a
    # fresh list resolves the same instance to a system device through its new MPN.
    # The stable component/symbol IDs distinguish owner representation from replacement.
    if (current_local.get("uuid"), current_local.get("name")) != (before_local.get("uuid"), before_local.get("name")):
        raise RuntimeError(f"Local component identity changed at {label}")
    if (component.get("symbol") or {}) != (before_component.get("symbol") or {}):
        raise RuntimeError(f"Symbol identity changed at {label}")
    local_id = device.get("uuid")
    if local_id and local_id == before_local.get("uuid"):
        return None
    if (device.get("libraryUuid"), local_id) == (before_device.get("libraryUuid"), before_device.get("uuid")):
        return None
    if not record["controlled"]["mpn"]:
        raise RuntimeError(f"Unexpected device identity change on non-MPN target {label}")
    if not device.get("libraryUuid") or not local_id:
        raise RuntimeError(f"Resolved device identity is incomplete at {label}: {device}")
    key = f"{device.get('libraryUuid')}/{local_id}"
    if key in AUDITS:
        audit = AUDITS[key]
    else:
        response = run(f"library/{label}", ["lib", "device", "get",
                       "--library", device["libraryUuid"], "--uuid", local_id])
        native = response.get("result", {}).get("device", {})
        audit = {
            "libraryUuid": device["libraryUuid"], "deviceUuid": local_id,
            "placedNamePreserved": device.get("name") == before_device.get("name"),
            "libraryName": native.get("name"),
            "libraryMpn": native.get("property", {}).get("manufacturerId"),
            "expectedMpn": record["controlled"]["mpn"],
            "footprintAssociation": native.get("association", {}).get("footprint"),
            "status": "PASS" if response.get("ok") is True and
                      native.get("property", {}).get("manufacturerId") == record["controlled"]["mpn"] and
                      device.get("name") == before_device.get("name") else "FAIL",
        }
        AUDITS[key] = audit
        write_json(RUN / "device-audits.json", AUDITS)
    if audit["status"] != "PASS":
        raise RuntimeError(f"Device resolution is not exact controlled MPN at {label}: {audit}")
    return audit


def canonical_list(result: dict, original: dict, targets: list[dict]) -> dict:
    result = json.loads(json.dumps(result))
    original_by_id = {c.get("primitiveId"): c for c in original["components"]}
    for record in targets:
        primitive = record["primitiveId"]
        component = next((c for c in result["components"] if c.get("primitiveId") == primitive), None)
        old = original_by_id.get(primitive)
        if component is None or old is None:
            raise RuntimeError(f"Missing guarded component {record['board']}/{record['cadReference']}")
        for key in ("manufacturerId", "supplier", "supplierId", "addIntoPcb",
                    "deviceResolution", "deviceIdentityCompatibilityError", "deviceIdentityCandidates",
                    "deviceIdentityError", "device", "placedDevice"):
            if key in old:
                component[key] = old[key]
            else:
                component.pop(key, None)
    return result


def canonical_conn(result: dict, original: dict, targets: list[dict]) -> dict:
    result = json.loads(json.dumps(result))
    target_ids = {record["uniqueId"] for record in targets}
    old_by_uid = {c.get("uniqueId"): c for c in original["components"]}
    for component in result["components"]:
        if component.get("uniqueId") in target_ids:
            component["device"] = old_by_uid[component.get("uniqueId")].get("device")
    return result


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=False)
    plan = json.loads((RETURN / "repair-plan.json").read_text(encoding="utf-8"))
    records = [r for r in plan["records"] if r["controlled"]["mpn"] or
               r["current"]["addIntoPcb"] != r["controlled"]["addIntoPcb"]]
    if len(records) != 237:
        raise RuntimeError(f"Expected 233 MPN + 4 external records, got {len(records)}")
    # PR31 BOM-24 stores a 286-character multi-part design expression in MPN.
    # Do not truncate it or invent atomic orderable parts; C10 already proved that
    # the native Manufacturer Part field does not retain this controlled text.
    blocked_mpn = {(r["pageUuid"], r["primitiveId"]): r for r in records if len(r["controlled"]["mpn"]) > 255}
    pages: dict[str, list[dict]] = {}
    for record in records:
        pages.setdefault(record["pageUuid"], []).append(record)
    SUMMARY.update({
        "status": "IN_PROGRESS", "projectUuid": PROJECT,
        "controlledMpnTargets": sum(bool(r["controlled"]["mpn"]) for r in records),
        "controlledMpnBlocked": len(blocked_mpn),
        "blockedMpnRecords": [{"board": r["board"], "cadReference": r["cadReference"],
                               "pageUuid": r["pageUuid"], "uniqueId": r["uniqueId"],
                               "controlledLength": len(r["controlled"]["mpn"]),
                               "reason": "Over-255-character multi-part design expression in the controlled MPN cell; atomic MPN correction required."}
                              for r in blocked_mpn.values()],
        "externalFlagTargets": sum(r["current"]["addIntoPcb"] != r["controlled"]["addIntoPcb"] for r in records),
        "pagesTotal": len(pages), "pagesCompleted": 0, "modified": 0, "alreadySatisfied": 0,
        "blockedSkipped": 0, "verifiedMpn": 0,
        "deviceAudits": 0, "pageResults": {}, "failure": None,
    })
    save_summary()
    for page, targets in pages.items():
        print(f"PAGE {page}: {len(targets)} controlled targets", flush=True)
        preflight = run(f"preflight/{page}", ["sch", "list", "--page", page, "--stay",
                        "--include-pins", "--include-bbox", "--include-wires", "--include-device-identity"])
        if preflight.get("ok") is not True:
            raise RuntimeError(f"Preflight not ok at {page}")
        current_result = preflight["result"]
        original_list = json.loads((BEFORE / f"pins/{page}.stdout.json").read_text(encoding="utf-8"))["result"]
        if canonical_list(current_result, original_list, targets) != original_list:
            raise RuntimeError(f"Uncontrolled preflight difference at {page}")
        current_by_id = {c.get("primitiveId"): c for c in current_result["components"]}
        original_by_id = {c.get("primitiveId"): c for c in original_list["components"]}
        for record in targets:
            label = f"{record['board']}-{record['cadReference']}"
            component = current_by_id.get(record["primitiveId"])
            if not component or component.get("uniqueId") != record["uniqueId"]:
                raise RuntimeError(f"Identity guard failed at {label}")
            audit_device(record, component, original_by_id[record["primitiveId"]], f"preflight-{label}")
            patch = {}
            is_blocked = (record["pageUuid"], record["primitiveId"]) in blocked_mpn
            if record["controlled"]["mpn"] and not is_blocked and component.get("manufacturerId") != record["controlled"]["mpn"]:
                patch["manufacturerId"] = record["controlled"]["mpn"]
            if component.get("addIntoPcb") != record["controlled"]["addIntoPcb"]:
                patch["addIntoPcb"] = record["controlled"]["addIntoPcb"]
            if not patch:
                if is_blocked:
                    SUMMARY["blockedSkipped"] += 1
                    print(f"  {label}: BLOCKED controlled MPN; no write", flush=True)
                else:
                    SUMMARY["alreadySatisfied"] += 1
                continue
            patch_path = RUN / "patches" / f"{label}.json"
            write_json(patch_path, patch)
            response = run(f"modify/{label}", ["sch", "modify", "--doc", page,
                           "--id", record["primitiveId"], "--patch-file", str(patch_path)])
            changed = response.get("result", {}).get("component", {})
            if response.get("ok") is not True or not changed:
                raise RuntimeError(f"Modify readback missing at {label}")
            for key, expected in patch.items():
                if changed.get(key) != expected:
                    raise RuntimeError(f"Modify did not apply {key} at {label}")
            if changed.get("uniqueId") != record["uniqueId"]:
                raise RuntimeError(f"uniqueId changed at {label}")
            # Count the confirmed mutation before any later audit can interrupt the run.
            SUMMARY["modified"] += 1
            save_summary()
            audit_device(record, changed, original_by_id[record["primitiveId"]], label)
            print(f"  {label}: applied and read back", flush=True)
        saved = run(f"save/{page}", ["sch", "save", "--doc", page])
        if saved.get("result", {}).get("saved") is not True:
            raise RuntimeError(f"saved:true missing at {page}")
        after = run(f"after/{page}", ["sch", "list", "--page", page, "--stay",
                    "--include-pins", "--include-bbox", "--include-wires", "--include-device-identity"])
        after_conn = run(f"connectivity/{page}", ["sch", "connectivity", "--page", page])
        original_conn = json.loads((BEFORE / f"connectivity/{page}.stdout.json").read_text(encoding="utf-8"))
        if canonical_list(after["result"], original_list, targets) != original_list:
            raise RuntimeError(f"Uncontrolled component/pin/geometry difference after {page}")
        if canonical_conn(after_conn, original_conn, targets) != original_conn:
            raise RuntimeError(f"Connectivity or placement difference after {page}")
        after_by_id = {c.get("primitiveId"): c for c in after["result"]["components"]}
        for record in targets:
            component = after_by_id[record["primitiveId"]]
            if component.get("addIntoPcb") != record["controlled"]["addIntoPcb"]:
                raise RuntimeError(f"Final addIntoPcb mismatch at {record['cadReference']}")
            if record["controlled"]["mpn"] and (record["pageUuid"], record["primitiveId"]) not in blocked_mpn:
                if component.get("manufacturerId") != record["controlled"]["mpn"]:
                    raise RuntimeError(f"Final manufacturerId mismatch at {record['cadReference']}")
                SUMMARY["verifiedMpn"] += 1
            audit_device(record, component, original_by_id[record["primitiveId"]], f"after-{record['board']}-{record['cadReference']}")
        bom_response = run(f"bom/{page}", ["bom", "export", "--type", "csv", "--enrich=false", "--doc", page])
        artifact = Path(bom_response["result"]["artifactPath"])
        bom_path = RUN / "bom" / f"{page}.csv"
        bom_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact, bom_path)
        digest = hashlib.sha256(bom_path.read_bytes()).hexdigest()
        metadata = next((a for a in bom_response.get("artifacts", []) if a.get("path") == str(artifact)), None)
        if metadata and (metadata.get("sha256") != digest or metadata.get("size") != bom_path.stat().st_size):
            raise RuntimeError(f"BOM artifact hash/size mismatch at {page}")
        bom_rows = read_native_bom(bom_path)
        for record in targets:
            if not record["controlled"]["mpn"] or (record["pageUuid"], record["primitiveId"]) in blocked_mpn:
                continue
            matched = [row for row in bom_rows if record["cadReference"] in
                       [item.strip() for item in row["Designator"].replace(";", ",").split(",")]]
            if len(matched) != 1 or matched[0]["Manufacturer Part"].strip() != record["controlled"]["mpn"]:
                raise RuntimeError(f"Native BOM MPN mismatch at {record['board']}/{record['cadReference']}")
        blocked_here = [r["cadReference"] for r in targets if (r["pageUuid"], r["primitiveId"]) in blocked_mpn]
        SUMMARY["pageResults"][page] = {"status": "PASS_WITH_BLOCKED_MPN" if blocked_here else "PASS",
                                        "targets": len(targets), "blockedMpn": blocked_here,
                                        "saved": True, "bomSha256": digest,
                                        "terminalAndGeometryPreserved": True}
        SUMMARY["pagesCompleted"] += 1
        SUMMARY["deviceAudits"] = len(AUDITS)
        save_summary()
    SUMMARY["status"] = "PASS_WITH_BLOCKED_MPN" if blocked_mpn else "PASS"
    SUMMARY["deviceAudits"] = len(AUDITS)
    SUMMARY["scope"] = "Controlled native manufacturerId and addIntoPcb only. Over-255-character non-atomic controlled MPN cells and all unqualified footprint fields remain BLOCKED. Final project-wide save/reload is a separate gate."
    save_summary()
    print(json.dumps(SUMMARY, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if RUN.is_dir():
            SUMMARY.setdefault("status", "FAIL")
            SUMMARY["status"] = "FAIL"
            SUMMARY["failure"] = str(exc)
            SUMMARY["deviceAudits"] = len(AUDITS)
            save_summary()
        print(f"FAIL: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
