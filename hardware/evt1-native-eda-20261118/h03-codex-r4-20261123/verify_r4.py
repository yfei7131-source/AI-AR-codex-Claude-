"""Replay the R4 native archive and strict EDA evidence checks."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from u11.audit_r3_u11 import load, records
from verify_pcb1_spur import FEEDBACK_VIA, PCB1, SPUR, measure

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent
LOGS = HERE / "verification"
BOARD = ("PCB", PCB1)
SPUR_KEY = ("LINE", SPUR)
NATIVE_COUNTER = ("ELE_PLACEHOLDER", "placeholder67")
WIDENED_R3 = {
    "380eced212e1089b", "78fc155b0b1a220c", "a81a25f7500053ca",
    "c5c19ccbe177abb7", "cc601d47aeaf5f49", "e7b284a0a40b2141", "f6feb4ca3aa755e5",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(path):
    with ZipFile(path) as archive:
        require(archive.testzip() is None, f"Corrupt native archive: {path}")
        metadata = json.loads(archive.read("project2.json"))
    return metadata, {doc: records(rows) for doc, rows in load(path).documents.items()}


def log(name):
    return json.loads((LOGS / f"{name}.json").read_bytes())


def changes(before, after):
    require(before.keys() == after.keys(), "Archive document identities changed")
    return {
        (doc, key)
        for doc, by_id in before.items()
        for key in by_id.keys() | after[doc].keys()
        if key not in by_id or key not in after[doc] or by_id[key] != after[doc][key]
    }


def line_widths(board):
    return Counter(row["width"] for (kind, _), row in board.items() if kind == "LINE")


def violation_keys(drc):
    # Global indices are editor enumeration order, not a stable violation identity.
    return Counter(json.dumps({k: v for k, v in row.items() if k != "globalIndex"}, sort_keys=True)
                   for row in drc["violations"])


def verify(r3_local_export=None, r4_restore_export=None):
    r2_path, = (NATIVE / "h03-gemini-r2-20261123/native").glob("*.epro2")
    r3_path, = (NATIVE / "h03-codex-r3-handoff-20261123/native").glob("*.epro2")
    r4_path, = (HERE / "native").glob("*.epro2")
    _, r2 = snapshot(r2_path)
    _, r3 = snapshot(r3_path)
    r4_metadata, r4 = snapshot(r4_path)

    require(r4_metadata["editorVersion"] == "4.1.97", "Incorrect R4 EasyEDA Pro export version")
    require(log("import-r3")["result"]["sourceSha256"] == sha256(r3_path), "Incorrect R3 source")
    require(log("export-after")["result"]["sha256"] == sha256(r4_path), "Incorrect R4 export")
    restore = log("restore-r4")["result"]
    require(restore["created"] and restore["sourceSha256"] == sha256(r4_path)
            and restore["uuid"] != log("import-r3")["result"]["uuid"],
            "Restore did not create a separate project from this export")
    require((Counter(kind for kind, _ in r4)["PCB"], Counter(kind for kind, _ in r4)["SCH_PAGE"])
            == (3, 21), "Project scope changed")

    expected_r3_diff = {(BOARD, ("LINE", item)) for item in WIDENED_R3 | {SPUR}}
    expected_r3_diff.add((BOARD, ("ACTIVE_LAYER", "ACTIVE_LAYER")))
    require(changes(r2, r3) == expected_r3_diff, "Unexpected R2-to-R3 native record changes")
    for identifier in WIDENED_R3 | {SPUR}:
        key = "LINE", identifier
        old, new = r2[BOARD][key], r3[BOARD][key]
        require(old["width"] == 1.9685 and new["width"] == (2 if identifier == SPUR else 4)
                and old["netName"] == "GND" and old | {"width": new["width"]} == new,
                f"Unexpected R3 width or route change {identifier}")

    expected_r4_diff = {(BOARD, SPUR_KEY), (BOARD, NATIVE_COUNTER)}
    require(changes(r3, r4) == expected_r4_diff, "Unexpected R3-to-R4 native record changes")
    require(SPUR_KEY not in r4[BOARD], "Ground spur still exists")
    require(r3[BOARD][NATIVE_COUNTER] == {"dataType": "LINE", "max": 2}
            and r4[BOARD][NATIVE_COUNTER] == {"dataType": "LINE", "max": 3},
            "Unexpected automatic LINE counter update")

    proof = measure(log("pcb1-before-copper"))
    require(proof == log("pcb1-spur-geometry"), "Geometry receipt mismatch")
    pre, post = (log(f"pcb1-{stage}-copper") for stage in ("before", "after"))
    for field in ("components", "outline", "rules", "copperLayers"):
        require(pre[field] == post[field], f"Live captured {field} changed")
    for kind in ("arcs", "fills", "pours", "poured", "regions", "vias"):
        require(pre["copper"][kind] == post["copper"][kind], f"Live captured {kind} changed")
    pre_lines = {line["primitiveId"]: line for line in pre["copper"]["lines"]}
    post_lines = {line["primitiveId"]: line for line in post["copper"]["lines"]}
    require(pre_lines.pop(SPUR) == proof["spur"] and pre_lines == post_lines, "Live delta differs")
    require(log("track-delete")["result"]["count"] == 1 and log("pcb1-save")["result"]["saved"],
            "Missing successful edit and save receipts")
    reload = log("pcb1-reload")
    require(reload["saved"] and reload["closed"] and reload["reloaded"] == PCB1, "Reload incomplete")
    require(proof["retained_feedback_via"]["primitiveId"] == FEEDBACK_VIA, "Incorrect feedback via")

    drc_counts, erc_fatals = {}, {}
    for index in (1, 2, 3):
        counts = {"Connection Error": (355, 237, 134)[index - 1]}
        if index == 1:
            counts["Netlist Error"] = 1
        before, after = (log(f"pcb{index}-{stage}") for stage in ("before", "after"))
        require(before["passed"] is False and after["passed"] is False
                and before["counts"] == after["counts"] == counts
                and violation_keys(before) == violation_keys(after), f"PCB{index} DRC mismatch")
        drc_counts[f"PCB{index}"] = counts

        before, after = (log(f"sch{index}-{stage}")["result"] for stage in ("before", "after"))
        fatals = (4, 0, 2)[index - 1]
        require(before == after and after["strict"] and after["fatal"] == fatals,
                f"Schematic {index} ERC mismatch")
        erc_fatals[f"SCH{index}"] = fatals

    restored_drc, after_drc = log("pcb1-restore"), log("pcb1-after")
    require(restored_drc["counts"] == after_drc["counts"]
            and violation_keys(restored_drc) == violation_keys(after_drc), "Restored PCB1 DRC differs")

    for path, receipt, expected in ((r3_local_export, "export-before", r3),
                                     (r4_restore_export, "restore-export", r4)):
        if path is not None:
            require(sha256(path) == log(receipt)["result"]["sha256"], "Re-export receipt mismatch")
            require(not changes(expected, snapshot(path)[1]), "Re-export native payload differs")

    three_mil = [row for (kind, _), row in r4[BOARD].items() if kind == "LINE" and row["width"] == 3]
    require(len(three_mil) == 472, "Unexpected number of 3 mil PCB1 tracks")
    return {
        "r4_sha256": sha256(r4_path),
        "source_document_payload_count": len(r4),
        "pcb1_width_counts_r2": dict(sorted(line_widths(r2[BOARD]).items())),
        "pcb1_width_counts_r3": dict(sorted(line_widths(r3[BOARD]).items())),
        "pcb1_width_counts_r4": dict(sorted(line_widths(r4[BOARD]).items())),
        "pcb1_three_mil_by_layer": dict(sorted(Counter(row["layerId"] for row in three_mil).items())),
        "pcb1_three_mil_by_net": dict(sorted(Counter(row["netName"] for row in three_mil).items())),
        "strict_native_drc_before_and_after": drc_counts,
        "strict_native_erc_fatals_before_and_after": erc_fatals,
        "pcb1_restored_native_drc_violations_equal": True,
        "full_r3_import_export_payload_parity_checked": r3_local_export is not None,
        "full_r4_restore_export_payload_parity_checked": r4_restore_export is not None,
        "manufacturing_status": "NOT FOR FAB",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r3-local-export", type=Path)
    parser.add_argument("--r4-restore-export", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.r3_local_export, args.r4_restore_export), indent=2))
