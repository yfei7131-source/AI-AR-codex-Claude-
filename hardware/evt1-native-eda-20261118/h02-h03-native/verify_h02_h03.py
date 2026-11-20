#!/usr/bin/env python3
"""Check current native archive evidence against PR #35 and its electrical baseline."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]
from prepare_hierarchy import Archive, PCB_BINDINGS, digest, validate_instances
from repair_native_fields import attr_value, part_attrs
from repair_supply_wire_names import ROOTS, classify_proxies
from verify_h02 import PR31, board_membership, context_ok, inventory
from verify_persisted_archive import without_record_order, verify_pins_and_nc
from verify_round import read_erc


PR35 = PACKAGE / "h02-erc"
BRIDGE = ("PCB", "9ce45f14cb79dc9d")
L2_FIELDS = {
    "MPN": "DFE21CCN2R2MELL",
    "UserDocLink": "https://search.murata.co.jp/Ceramy/image/img/P02/JETE243A-0052.pdf",
}


def read(path):
    return json.loads(path.read_bytes())


def stable_document_diff(old, new, kind):
    lhs, rhs = (without_record_order(archive, kind) for archive in (old, new))
    return sorted(lhs.keys() ^ rhs.keys() | {key for key in lhs.keys() & rhs.keys() if lhs[key] != rhs[key]})


def record_delta(before, after, kind, key):
    lhs, rhs = (without_record_order(archive, kind)[key] for archive in (before, after))
    return lhs - rhs, rhs - lhs


def verify_delta(baseline, current, catalog):
    l2, = (part for part in catalog if part["sourceReference"] == "L2_1V8")
    page = ("SCH_PAGE", l2["capturePage"])
    _, attrs = part_attrs(current, l2)
    _, old_attrs = part_attrs(baseline, l2)
    for field, expected in L2_FIELDS.items():
        if attr_value(attrs, field) != expected:
            raise ValueError(f"L2 field did not persist: {field}")
    # This host normalizes two null supplier values to empty strings in its SDK merge.
    supplier_fields = {"Supplier", "Supplier Part"}
    def observed(values):
        return {key: (attr_value(values, key) or "") if key in supplier_fields else attr_value(values, key)
                for key in values}
    if observed(attrs) != {**observed(old_attrs), **L2_FIELDS}:
        raise ValueError("L2 metadata diverges beyond the two requested field corrections")
    if baseline.documents.keys() != current.documents.keys():
        raise ValueError("Document/asset inventory changed unexpectedly")
    for kind in {kind for kind, _ in baseline.documents}:
        expected = [page] if kind == "SCH_PAGE" else [BRIDGE] if kind == "PCB" else []
        if stable_document_diff(baseline, current, kind) != expected:
            raise ValueError(f"Unexpected persisted {kind} document changes")
    pcb_removed, pcb_added = record_delta(baseline, current, "PCB", BRIDGE)
    if pcb_removed or pcb_added.total() != 2 or any(kind != "REGION" for kind, _, _ in pcb_added):
        raise ValueError(f"Bridge PCB differed beyond the two new regions: removed={pcb_removed}; added={pcb_added}")
    sch_removed, sch_added = record_delta(baseline, current, "SCH_PAGE", page)
    allowed_attrs = {attrs[field].header["id"] for field in L2_FIELDS.keys() | supplier_fields}
    for delta in (sch_removed, sch_added):
        if ({key for _, key, _ in delta} != allowed_attrs or delta.total() != len(allowed_attrs)
                or any(kind != "ATTR" or json.loads(payload)["parentId"] != l2["capturePrimitiveId"]
                       for kind, _, payload in delta)):
            raise ValueError("Native L2 page changed outside the four scoped attribute records")
    def summarize(delta):
        return [{"type": kind, "id": key, "field": json.loads(payload).get("key")}
                for kind, key, payload in sorted(delta.elements())]
    return {
        "schematic_records_out": summarize(sch_removed),
        "schematic_records_in": summarize(sch_added),
        "bridge_regions": sorted(key for _, key, _ in pcb_added),
    }


def verify(args):
    capture = args.capture
    manifest = read(capture / "board_pages.json")
    project = manifest["project_id"]
    result = read(capture / "archive-response.json")
    with ZipFile(args.archive) as file:
        if file.testzip() is not None:
            raise ValueError("Native archive ZIP checksum failed")
    if (result["ok"] is not True or result["result"]["uuid"] != project
            or result["result"].get("sha256") != digest(args.archive)):
        raise ValueError("Native archive does not match its editor receipt")
    baseline = Archive(PR35 / "native/ZY_AIAR_EVT1_H02_ERC_L2_D3_NOT_FOR_FAB.epro2")
    current = Archive(args.archive)
    if validate_instances(baseline) != validate_instances(current):
        raise ValueError("Native hierarchy topology changed")
    for uuid, owner in PCB_BINDINGS.items():
        if current.documents["PCB", uuid].one("META").payload["board"] != owner:
            raise ValueError(f"PCB association changed: {uuid}")
    catalog = read(PACKAGE / "h02-native/catalog-plan.json")["records"]
    terms, _ = PR31.baseline(PACKAGE)
    bindings, registry = inventory(capture, manifest)
    nets = board_membership(capture, manifest, terms, bindings)
    if (registry["status"] != "PASS" or registry["pcb_document_inventory"]["status"] != "PASS"
            or any(item["status"] != "PASS" for item in nets.values())):
        raise ValueError("Board identity, net group names or connected pad membership differ")
    terminal_count, nc_count = verify_pins_and_nc(current, catalog)
    erc = {}
    for board, root in ROOTS.items():
        expected_context = (project, root)
        reloaded = read(capture / "reload" / f"{board}.json")
        final = reloaded["finalContext"]
        if (reloaded["saved"] is not True or reloaded["closed"] is not True or reloaded["reloaded"] != root
                or (final["projectUuid"], final["documentUuid"]) != expected_context):
            raise ValueError(f"Native schematic root reload not verified: {board}")
        first, last = (read_erc(folder / f"{root}.json") for folder in
                       (PR35 / "evidence/erc", capture / "erc"))
        if first != last:
            raise ValueError(f"Strict ERC findings changed: {board}")
        proxies = {(page, key): item["name"] for (rule, page, key), item in last.items() if rule == "ONLYSYMBOL"}
        erc[board] = {"strict": "FAIL", "diagnostics": dict(Counter(key[0] for key in last)),
                      "hierarchy_proxies": classify_proxies(current, board, proxies)}
    pin_receipt = read(capture / "l2-pins.json")
    if not context_ok(pin_receipt, project, "3fdc6001a068d82e"):
        raise ValueError("L2 pin receipt has the wrong project or document")
    l2, = (part for part in pin_receipt["result"]["components"] if part["designator"] == "L2")
    terminal_contract = {pin["pinNumber"]: pin["net"] for pin in l2["pins"]}
    if (l2["primitiveId"] != "ie537" or l2["uniqueId"] != "3f6ee2b1a34b017f"
            or l2["footprint"]["uuid"] != "7391112ac3d1c151"
            or terminal_contract != {"1": "BK_SW", "2": "1V8_SYS"}
            or any(l2["otherProperty"].get(key) != value for key, value in L2_FIELDS.items())):
        raise ValueError("L2 fields, identity, footprint or named pin nets changed after reopen")
    delta = verify_delta(baseline, current, catalog)
    return {
        "status": "VERIFIED", "manufacturing": "BLOCKED", "project_uuid": project,
        "archive_sha256": digest(args.archive), "registry": registry, "board_netlists": nets,
        "archived_schematic_terminals": terminal_count, "archived_explicit_nc": nc_count,
        "strict_erc": erc, "l2_terminal_contract": terminal_contract, "archive_delta": delta,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "capture", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args)
    except (KeyError, OSError, ValueError) as error:
        result = {"status": "FAIL", "manufacturing": "BLOCKED", "error": str(error)}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{result['status']}: {args.output}")
    return int(result["status"] != "VERIFIED")


if __name__ == "__main__":
    sys.exit(main())
