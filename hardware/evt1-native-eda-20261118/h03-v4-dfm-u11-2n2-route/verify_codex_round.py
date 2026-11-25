#!/usr/bin/env python3
"""Verify the bounded copper changes, native evidence, and independent archive round trip."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "h02-native"))
from prepare_hierarchy import Archive, digest
from verify_persisted_archive import without_record_order


BOARDS = {"PCB1": "8fbc3cae65886fe5", "PCB2": "9ce45f14cb79dc9d", "PCB3": "1db01a36f669a47a"}
SCHEMATICS = {"M-MAIN-L": "4d38590959875927", "M-OPT-BRIDGE": "e00fbca5c08cc114", "M-AUD-R": "e98944c2045546cf"}
REMOVED = {
    "2d02a47206d7014f", "248452904b1b15c9", "745f87472f6e79c1",
    "d1d29279e63eabbc", "e46b6c305882ff2f", "c5a4ee5b7638fa61",
}
ADDED = "f6f086804273d161"


def read(path):
    return json.loads(path.read_bytes())


def archive_digest(stage, archive):
    receipt = read(stage / "archive-response.json")["result"]
    project = read(stage / "board_pages.json")["project_id"]
    if (receipt.get("uuid") != project or receipt.get("sha256") != digest(archive)
            or receipt.get("zipIntegrityVerified") is not True):
        raise ValueError(f"Archive does not match editor export receipt: {stage}")
    return project


def design_changes(before, after, restored):
    if before.documents.keys() != after.documents.keys() or after.documents.keys() != restored.documents.keys():
        raise ValueError("Native document/asset inventory changed")
    kinds = {kind for kind, _ in before.documents}
    for kind in kinds:
        baseline, changed, test = (without_record_order(archive, kind) for archive in (before, after, restored))
        if changed != test:
            raise ValueError(f"Independent archive differs from saved editor {kind} payload")
        for key, old in baseline.items():
            added = changed[key] - old
            removed = old - changed[key]
            if key not in {("PCB", BOARDS[name]) for name in ("PCB2", "PCB3")}:
                if added or removed:
                    raise ValueError(f"Unexpected native change outside selected PCB copper: {key}")
                continue
            if key[1] == BOARDS["PCB2"]:
                if removed or added.total() != 1:
                    raise ValueError("Expected exactly one new PCB2 track")
                rec, = added
                payload = json.loads(rec[2])
                expected = {
                    "netName": "AVDD_WD_Q", "layerId": 2, "width": 3.5,
                    "startX": 129.7, "startY": 899.2, "endX": 129.7, "endY": 920.9,
                }
                if rec[:2] != ("LINE", ADDED) or any(payload[field] != value for field, value in expected.items()):
                    raise ValueError("Persisted AVDD_WD_Q track does not match its route plan")
            elif (added or removed.total() != len(REMOVED)
                  or {rec[1] for rec in removed} != REMOVED
                  or any(rec[0] != "LINE" or json.loads(rec[2]).get("netName") != "GND" for rec in removed)):
                raise ValueError("PCB3 delta is not exactly the six proven redundant GND segments")


def drc_rows(raw):
    if type(raw["passed"]) is not bool or raw["total"] != len(raw["violations"]):
        raise ValueError("Incomplete or unavailable native DRC")
    return Counter(json.dumps({k: v for k, v in finding.items() if k != "globalIndex"}, sort_keys=True)
                   for finding in raw["violations"])


def verify(root, before_capture, live, restored):
    folders = {stage: root / stage for stage in ("after", "independent")}
    if not (folders["independent"] / "archive-response.json").is_file():
        folders["independent"] = root / "independent-ready"
    active = archive_digest(folders["after"], live.path)
    test = archive_digest(folders["independent"], restored.path)
    receipt = read(root / "independent-import.json")["result"]
    if (active == test or receipt["uuid"] != test or receipt["sourceSha256"] != digest(live.path)
            or receipt.get("verified") is not True):
        raise ValueError("Re-import does not prove an independent editor project for the saved bytes")
    inherited = Archive(next((ROOT / "native").glob("*MECR01_NOT_FOR_FAB.epro2")))
    design_changes(inherited, live, restored)
    board_result = {}
    for board, document in BOARDS.items():
        raw_before = read(before_capture / f"{board}-drc.json")
        after, reopened = (read(folder / f"{board}-drc.json") for folder in folders.values())
        before_rows, after_rows, reopened_rows = map(drc_rows, (raw_before, after, reopened))
        if after_rows != reopened_rows or after["passed"] != reopened["passed"]:
            raise ValueError(f"Native DRC differs on independently imported {board}")
        delta = {"Connection Error": -1} if board == "PCB2" else {}
        changes = {key: after["counts"].get(key, 0) - count for key, count in raw_before["counts"].items()}
        if ({key: value for key, value in changes.items() if value} != delta
                or after["counts"].keys() != raw_before["counts"].keys()):
            raise ValueError(f"Unexpected native DRC rule delta on {board}: {changes}")
        if board != "PCB2" and before_rows != after_rows:
            raise ValueError(f"Unexpected DRC finding movement on {board}")
        for stage, folder in folders.items():
            reload = read(folder / f"{board}-reload.json")
            project = active if stage == "after" else test
            if (reload.get("saved") is not True or reload.get("closed") is not True
                    or reload.get("reloaded") != document or reload["targetContext"]["projectUuid"] != project):
                raise ValueError(f"Missing native save/reopen receipt for {board}")
        dfm = read(folders["after"] / f"{board}-dfm.json")["summary"]
        duplicate_count = dfm["duplicateSegments"]
        if duplicate_count != 0:
            raise ValueError(f"New duplicate copper detected on {board}")
        board_result[board] = {
            "strict_verdict": "PASS" if after["passed"] else "FAIL",
            "before": raw_before["counts"], "after": after["counts"],
            "independent_reimport_exact": True, "dfm_summary": dfm,
        }
    groups = {}
    erc = {}
    for board, page in SCHEMATICS.items():
        expected = ROOT / "evidence/erc-3board/board-netlists" / f"{board}.net"
        for folder in folders.values():
            if expected.read_bytes() != (folder / "board-netlists" / expected.name).read_bytes():
                raise ValueError(f"Native Protel2 netlist differs on {board}")
        contents = expected.read_text(encoding="utf-8-sig")
        groups[board] = sum(line.strip() == "(" for line in contents.splitlines())
        src = ROOT / "evidence/erc-3board/erc"
        checks = [read(folder / f"{page}.json")["result"] for folder in
                  (src, *(stage / "erc" for stage in folders.values()))]
        if (any(item.get("strict") is not True or item.get("detailsAvailable") is not True for item in checks)
                or any(item["violations"] != checks[0]["violations"] for item in checks[1:])):
            raise ValueError(f"Native strict ERC differs or is missing on {board}")
        erc[board] = checks[1]["summary"]
    return {
        "status": "VERIFIED", "manufacturing": "BLOCKED", "archive_sha256": digest(live.path),
        "independent_archive_sha256": digest(restored.path), "board_drc": board_result,
        "erc": erc, "verified_named_protel2_groups": groups,
        "exact_archive_change": {"new_pcb2_track": ADDED, "removed_pcb3_redundant_gnd": sorted(REMOVED)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("capture", "before", "live", "restored", "output"):
        parser.add_argument(f"--{field}", required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.capture, args.before, Archive(args.live), Archive(args.restored))
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['status']}: {args.output}")


if __name__ == "__main__":
    main()
