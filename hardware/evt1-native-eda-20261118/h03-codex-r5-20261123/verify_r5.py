"""Replay the R5 native scope, strict results, and V4 blind-via geometry."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
EVIDENCE = HERE / "verification"
sys.path[:0] = [str(PACKAGE / "h03-codex-r4-20261123/u11"),
                str(PACKAGE / "h03-v4-dfm-u11-2n2-route")]

from audit_r3_u11 import load, records
from independent_hdi_dfm_auditor_v4 import audit_board_v4

BOARDS = {"PCB1": "8fbc3cae65886fe5", "PCB2": "9ce45f14cb79dc9d", "PCB3": "1db01a36f669a47a"}
A5_PAD = "fb9a90e154948529nrfp114"
A5_VIA = "9b1de4f8a526c7d3"


def require(predicate, message):
    if not predicate:
        raise ValueError(message)


def read(name):
    return json.loads((EVIDENCE / f"{name}.json").read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def ids(group):
    return {item["result"]["primitiveId"] for item in read(group + "/creation-receipts")
            if item["ok"]}


def delta(record_before, record_after):
    return (record_after.keys() - record_before.keys(),
            record_before.keys() - record_after.keys(),
            {key for key in record_before.keys() & record_after.keys() if record_before[key] != record_after[key]})


def inventories(log):
    return {key[1] for key in log if key[0] == "LINE"}


def check(saved_baseline=None, restored=None, dfm_output=None):
    base, = (PACKAGE / "h03-codex-r4-20261123/native").glob("*.epro2")
    current, = (HERE / "native").glob("*.epro2")
    with ZipFile(current) as archive:
        require(archive.testzip() is None, "Native export ZIP failed integrity")
        metadata = json.loads(archive.read("project2.json"))
        require(metadata["editorVersion"] == "4.1.97" and "NOT-FOR-FAB" in metadata["title"],
                "Incorrect native project/version marking")
    before_doc, after_doc = (load(path).documents for path in (base, current))
    before, after = ({key: records(value) for key, value in table.items()} for table in (before_doc, after_doc))
    require(before.keys() == after.keys(), "Project document identity changed")
    require(Counter(kind for kind, _ in after)["SCH_PAGE"] == 21, "Expected 21 schematic pages")
    require(read("import-r4")["result"]["sourceSha256"] == digest(base), "Wrong R4 import")
    native_receipt = read("final-export")["result"]
    restore = read("restore-r5")["result"]
    require(native_receipt["sha256"] == restore["sourceSha256"] == digest(current)
            and native_receipt["uuid"] != restore["uuid"] and restore["created"],
            "Restore failed to identify the delivered editable archive")

    paths = (
        ("PCB1-pilot/path-R20.2-R22.2", "GND"),
        ("PCB1-pilot/path-R19.2-R20.1", "CHG_ISO_GATE"),
        ("PCB2-apply/path-C16.2-C28.2", "GND"),
        ("PCB3-apply-local/path-R4.2-C4.2", "GND"),
        ("PCB3-u11-b2-c2-path-reloaded", "GND"),
    )
    for name, net in paths:
        item = read(name)
        require(item["connected"] and item["net"] == net, f"Native copper path was not verified for {name}")

    width1 = {row["id"] for item in ("PCB1-apply-pilot", "PCB1-apply-width-rest")
              for row in read(item)["replacements"]}
    width2 = {row["id"] for row in read("PCB2-apply-pilot")["replacements"]}
    split1 = read("PCB1-width-batch/split-reviewed")
    split3 = read("PCB3-apply-local/split-reviewed")
    expected_new = {
        "PCB1": ids("PCB1-pilot") | (ids("PCB1-width-batch") - {split1["unpersisted_creation_id"]})
                | {row["primitiveId"] for row in split1["native_split"]},
        "PCB2": ids("PCB2-apply"),
        "PCB3": (ids("PCB3-apply-local") - {split3["source_4mil_creation_id"]})
                | {row["primitiveId"] for row in split3["normalized_segments"]}
                | {read(f"{name}-track")["result"]["primitiveId"] for name in ("PCB3-u11-b2-c2", "PCB3-a5")},
    }
    expected_gone = {
        "PCB1": width1, "PCB2": width2,
        "PCB3": {split3["source_3mil_track"]["primitiveId"]} |
                set(read("PCB3-u11-b2-c2-replacement-screen")["removed_dogleg_ids"]),
    }

    edited_pcb_keys = {("PCB", board) for board in BOARDS.values()}
    for key in before:
        if key not in edited_pcb_keys:
            require(before[key] == after[key], f"Unscoped native document change {key}")

    report = {}
    dfm_report = {}
    dfm_archive = SimpleNamespace(path=current,
             documents={key: SimpleNamespace(records=value) for key, value in after_doc.items()})
    if dfm_output is not None:
        dfm_output.mkdir(parents=True, exist_ok=True)
    for index, (board, uid) in enumerate(BOARDS.items()):
        key = "PCB", uid
        a, b = before[key], after[key]
        added, removed, modified = delta(a, b)
        require(inventories(b) - inventories(a) == expected_new[board]
                and inventories(a) - inventories(b) == expected_gone[board],
                f"{board} persisted tracks differ from typed receipts and reviewed splits")
        require(all(kind == "ELE_PLACEHOLDER" for kind, _ in modified)
                and all(kind in {"LINE", "VIA", "ELE_PLACEHOLDER"} for kind, _ in added)
                and all(kind == "LINE" for kind, _ in removed),
                f"{board} unscoped native rule, schematic or copper object change")
        new_vias = {entry for kind, entry in added if kind == "VIA"}
        require(new_vias == ({A5_VIA} if board == "PCB3" else set()), f"{board} unexpected via")
        width_counts = [Counter(value["width"] for (kind, _), value in doc.items() if kind == "LINE")
                        for doc in (a, b)]
        require(tuple(count[3] for count in width_counts) == ((472, 366), (218, 208), (162, 161))[index],
                f"{board} residual 3 mil inventory differs")
        pre, post = (read(f"{board}-{stage}-drc") for stage in ("before", "restore"))
        require(pre["passed"] is False and post["passed"] is False
                and post["counts"] == ({"Connection Error": 352, "Netlist Error": 1},
                                       {"Connection Error": 236}, {"Connection Error": 132})[index],
                f"{board} strict DRC result differs")
        erc_a, erc_b = (read(f"{board}-{stage}-erc")["result"] for stage in ("before", "restore"))
        require(erc_a == erc_b and erc_b["strict"] and erc_b["fatal"] == (4, 0, 2)[index],
                f"{board} strict ERC changed")
        pcb_capture = EVIDENCE / f"{board}-restore-copper.json"
        dfm = audit_board_v4(board, dfm_archive, pcb_capture,
                             blind_csv=dfm_output / f"{board}-blind-vias.csv" if dfm_output else None)
        test = dfm["v4_official_jlcpcb_hdi_audit"]
        require(test["total_blind_vias"] == (61, 40, 41)[index], f"{board} blind via inventory differs")
        require(test["violations"]["total_v4_violations"] == 0, f"{board} V4 geometry findings")
        dfm_report[board] = test
        report[board] = {"added_tracks": len(expected_new[board]), "removed_tracks": len(expected_gone[board]),
                         "before_drc": pre["counts"], "after_drc": post["counts"], "erc_fatal": erc_b["fatal"],
                         "three_mil_before_and_after": [count[3] for count in width_counts],
                         "blind_vias": test["total_blind_vias"]}
    if dfm_output:
        (dfm_output / "geometry-report.json").write_text(json.dumps(dfm_report, indent=2) + "\n", encoding="utf8")

    require(after["PCB", BOARDS["PCB3"]]["VIA", A5_VIA] == read("a5-archive-delta")["via"],
            "A5 native blind-via geometry differs")
    has_a5 = [any(A5_PAD in item["objs"] for item in read(f"PCB3-{stage}-drc")["violations"])
              for stage in ("before", "restore")]
    require(has_a5 == [True, False], "A5 native DRC did not clear")
    for artifact, receipt, expected in ((saved_baseline, "baseline-export", before),
                                        (restored, "restore-export", after)):
        if artifact is not None:
            actual = {key: records(value) for key, value in load(artifact).documents.items()}
            require(actual == expected and digest(artifact) == read(receipt)["result"]["sha256"],
                    f"Independent native archive comparison failed: {artifact}")
    return {"sha256": digest(current), "board_verified": report,
            "project_document_count": len(after), "independent_restore_archive_compared": restored is not None,
            "r4_import_reexport_compared": saved_baseline is not None, "status": "NOT FOR FAB"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-baseline", type=Path)
    parser.add_argument("--restored", type=Path)
    parser.add_argument("--dfm-output", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.saved_baseline, args.restored, args.dfm_output), indent=2))
