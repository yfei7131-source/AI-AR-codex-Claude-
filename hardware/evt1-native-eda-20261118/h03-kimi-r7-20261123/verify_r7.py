#!/usr/bin/env python3
"""Independently verify the R7 native archive, limited delta and live evidence.

This checker never converts an expected DRC/ERC failure into manufacturing or
routing completion. It validates only the evidence and scope actually present.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile

R7 = Path(__file__).resolve().parent
PACKAGE = R7.parent
EVIDENCE = R7 / "verification"
sys.path[:0] = [
    str(PACKAGE / "h03-codex-r4-20261123/u11"),
    str(PACKAGE / "h03-v4-dfm-u11-2n2-route"),
    str(PACKAGE / "h02-native"),
    str(R7 / "tools"),
]
from audit_r3_u11 import load as load_native, records
from independent_hdi_dfm_auditor_v4 import audit_board_v4
from prepare_hierarchy import Archive
from verify_h02 import parse_protel
from verify_local_routes import signatures, view
from controlled_sch_audit import controlled_terminal_audit

R6 = PACKAGE / "h03-codex-r6-20261123"
BOARDS = {
    "PCB1": ("8fbc3cae65886fe5", "4d38590959875927", "61", "69", "M-MAIN-L", 4),
    "PCB2": ("9ce45f14cb79dc9d", "e00fbca5c08cc114", "62", "70", "M-OPT-BRIDGE", 0),
    "PCB3": ("1db01a36f669a47a", "e98944c2045546cf", "63", "71", "M-AUD-R", 2),
}
EXPECTED_DRC = {
    "PCB1": {"Connection Error": 340, "Netlist Error": 1},
    "PCB2": {"Connection Error": 236},
    "PCB3": {"Connection Error": 132},
}
WIDTH_IDS = ["381ef9afc47f16a4", "3de2ea0455688422", "b95291d44ac4bb63"]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def erc_signature(result):
    return ({key: value for key, value in result.items() if key != "violations"},
            Counter(json.dumps(item, sort_keys=True) for item in result["violations"]))


def track_view(native, board):
    uid = BOARDS[board][0]
    result = {}
    for (kind, identifier), row in records(native.documents["PCB", uid]).items():
        if kind == "LINE":
            result[identifier] = {
                "startX": row["startX"], "startY": row["startY"],
                "endX": row["endX"], "endY": row["endY"],
                "net": row["netName"], "layer": row["layerId"], "lineWidth": row["width"],
            }
    return result


def verify_scope(baseline, final):
    before = {key: records(value) for key, value in baseline.documents.items()}
    after = {key: records(value) for key, value in final.documents.items()}
    check(before.keys() == after.keys(), "Native document/asset inventory changed")
    delta = {}
    for key in before:
        if key[0] != "PCB":
            check(before[key] == after[key], f"Unscoped schematic/library delta: {key}")
            continue
        old = {r: v for r, v in before[key].items() if r[0] not in {"LINE", "ELE_PLACEHOLDER"}}
        new = {r: v for r, v in after[key].items() if r[0] not in {"LINE", "ELE_PLACEHOLDER"}}
        check(old == new, f"Component/via/plane/rule delta outside R7 line scope: {key}")
        delta[key[1]] = {
            "recordKindsBefore": dict(Counter(kind for (kind, _) in before[key])),
            "recordKindsAfter": dict(Counter(kind for (kind, _) in after[key])),
            "lineRecordsBefore": sum(kind == "LINE" for kind, _ in before[key]),
            "lineRecordsAfter": sum(kind == "LINE" for kind, _ in after[key]),
        }
    # These two boards are carried forward, not silently rerouted or retuned.
    for board in ("PCB1", "PCB3"):
        key = ("PCB", BOARDS[board][0])
        check(before[key] == after[key], f"{board} carried-forward native records changed")
    old = track_view(baseline, "PCB2")
    new = track_view(final, "PCB2")
    from verify_local_routes import compare_routes
    accepted_ids = set(read(EVIDENCE / "56-pcb2-vsys-width-integrated-result.json")["createdPrimitiveIds"])
    check(set(old) - set(new) == set(WIDTH_IDS), "PCB2 removed lines differ from accepted width scope")
    check(set(new) - set(old) == accepted_ids, "PCB2 new archive line IDs differ from typed-create receipts")
    common = {key for key in old.keys() & new.keys() if old[key] == new[key]}
    expected = [row | ({"lineWidth": 4} if key in WIDTH_IDS else {})
                for key, row in old.items() if key not in common]
    observed = [row for key, row in new.items() if key not in common]
    compare_routes(expected, observed, tolerance=0.0001)
    check(len(expected) == len(observed) == 3, "PCB2 archive changed more than the three accepted centerlines")
    return {"changedBoard": "PCB2", "net": "VSYS", "fromWidthMil": 3, "toWidthMil": 4,
            "centerlinePreserved": True, "widenedLines": 3, "carriedForwardBoards": ["PCB1", "PCB3"],
            "documentDeltaSummary": delta, "unchangedCommonLineCount": len(common)}


def verify_reload(board, prefix, doc):
    saved = read(EVIDENCE / f"{prefix}-{board}-final-save.stdout.json")
    check(saved.get("result", {}).get("saved") is True, f"{board} saved:true missing")
    reloaded = read(EVIDENCE / f"{prefix}-{board}-final-reload.stdout.json")
    if reloaded.get("status") == "passed":
        check(reloaded.get("saved") is True and reloaded.get("closed") is True
              and reloaded.get("reloaded") == doc and reloaded.get("activeRestored") == doc
              and reloaded.get("readiness", {}).get("ready") is True, f"{board} reload receipt incomplete")
        return {"initialReloadStatus": "passed", "saved": True, "readiness": True}
    reopened = any(step.get("stage") == "reopen" and step.get("ok") is True
                   and step.get("context", {}).get("documentUuid") == doc
                   for step in reloaded.get("steps", []))
    ready = read(EVIDENCE / f"{prefix}b-{board}-final-ready-after-partial.stdout.json")
    check(reloaded.get("status") == "partial" and reloaded.get("saved") is True
          and reloaded.get("closed") is True and reopened and ready.get("ready") is True
          and ready.get("active", {}).get("documentUuid") == doc,
          f"{board} partial reload recovery was not independently read back")
    return {"initialReloadStatus": "partial-readiness-timeout", "saved": True,
            "reopenObserved": True, "boundedReadOnlyReadyPassed": True,
            "originalFailureRetained": f"{prefix}-{board}-final-reload.stdout.json"}


def verify():
    archive = R7 / "native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2"
    reexport = EVIDENCE / "independent/EVT1-H03-KIMI-R7-REEXPORT-NOT-FOR-FAB.epro2"
    exported = read(EVIDENCE / "65-r7-final-export.stdout.json")["result"]
    imported = read(EVIDENCE / "66-r7-independent-import.stdout.json")["result"]
    reexported = read(EVIDENCE / "68-r7-independent-reexport.stdout.json")["result"]
    check(exported["uuid"] == "37f434ba2161d11e7536f134c776285fbdc9db9c040debca7ccd85f6ebbea46d"
          and exported["sha256"] == digest(archive), "Final export receipt or digest mismatch")
    check(imported["created"] is True and imported["sourceSha256"] == digest(archive)
          and imported["uuid"] == reexported["uuid"] != exported["uuid"], "Independent project identity mismatch")
    check(reexported["sha256"] == digest(reexport), "Independent re-export digest mismatch")
    for path in (archive, reexport):
        with ZipFile(path) as native_zip:
            check(native_zip.testzip() is None, f"Native ZIP CRC failed: {path}")
            if path == archive:
                project = json.loads(native_zip.read("project2.json"))
                check(project["editorVersion"] == "4.1.97" and "NOT-FOR-FAB" in project["title"],
                      "Editor version or NOT-FOR-FAB marking changed")
    baseline = load_native(R7 / "baseline/EVT1-H03-KIMI-R7-INTEGRATED-BASELINE-NOT-FOR-FAB.epro2")
    final = load_native(archive)
    restored = load_native(reexport)
    final_records = {key: records(doc) for key, doc in final.documents.items()}
    restored_records = {key: records(doc) for key, doc in restored.documents.items()}
    check(final_records == restored_records, "Independent re-export document records differ from final native archive")
    forms = Counter(kind for kind, _ in final.documents)
    check([forms[kind] for kind in ("BOARD", "SCH", "SCH_PAGE", "PCB")] == [3, 3, 21, 3],
          "Native board/schematic/page inventory differs")
    r6_native = load_native(R6 / "native/EVT1-H03-CODEX-R6-NOT-FOR-FAB.epro2")
    check({key: records(doc) for key, doc in r6_native.documents.items()}
          == {key: records(doc) for key, doc in baseline.documents.items()},
          "R7 baseline is not the unchanged R6 native design")
    terminal_audit = read(EVIDENCE / "controlled-sch-audit.json")
    integrated_terminals = terminal_audit["integrated"]
    check(terminal_audit["independent"] == integrated_terminals
          and terminal_audit["r7Baseline"] == integrated_terminals,
          "Controlled terminal/NC evidence changed between R6 baseline, R7 and independent import")
    expected_terminal_delta = sorted([["M-MAIN-L", "R10", "1"], ["M-MAIN-L", "R10", "2"],
                                      ["M-MAIN-L", "U12", "4"], ["M-MAIN-L", "U12", "5"],
                                      ["M-MAIN-L", "U12", "6"]])
    check(integrated_terminals["resolvedComponents"] == 252
          and [row["sourceReference"] for row in integrated_terminals["unresolvedComponents"]] == ["R_ESP_BOOT"]
          and integrated_terminals["terminalCount"] == 1076
          and integrated_terminals["controlledTerminalCount"] == 1075
          and sorted(integrated_terminals["terminalDifference"]) == expected_terminal_delta
          and integrated_terminals["explicitNCCount"] == integrated_terminals["controlledNCCount"] == 92
          and integrated_terminals["archiveRawNCMarkers"] == 94,
          "Unexpected controlled terminal/NC delta beyond the inherited R6 evidence")
    terminal_count, nc_count = integrated_terminals["terminalCount"], integrated_terminals["explicitNCCount"]
    scope = verify_scope(baseline, final)
    trial = read(EVIDENCE / "54-pcb2-vsys-width-trial-result.json")
    integration = read(EVIDENCE / "56-pcb2-vsys-width-integrated-result.json")
    for receipt in (trial, integration):
        check(receipt["candidateStatus"] == "live-verified-track-widths" and receipt["ids"] == WIDTH_IDS
              and receipt["saved"] and receipt["reloaded"] and receipt["geometryScopeVerified"]
              and not receipt["addedErrorSignatures"] and receipt["beforeDrcCounts"] == receipt["afterDrcCounts"],
              "Accepted width trial/integration receipt is inconsistent")
    check(trial["project"] != integration["project"], "Width integration did not follow a distinct isolated project")

    report_boards = {}
    net_total = member_total = component_total = 0
    dfm_folder = R7 / "dfm"
    dfm_folder.mkdir(exist_ok=True)
    dfm_native = SimpleNamespace(path=archive, documents={
        key: SimpleNamespace(records=value) for key, value in final.documents.items()})
    for board, (doc, root, prefix, independent_prefix, net_name, fatal) in BOARDS.items():
        final_drc = read(EVIDENCE / f"{prefix}-{board}-final-drc.stdout.json")
        independent_drc = read(EVIDENCE / f"{independent_prefix}-{board}-independent-drc.stdout.json")
        historical_drc = read(R6 / f"verification/{board}-restore-drc.json")
        for result in (final_drc, independent_drc):
            check(result.get("passed") is False and result.get("counts") == EXPECTED_DRC[board]
                  and signatures(result) == signatures(historical_drc), f"{board} unexpected native DRC")
        final_erc = read(EVIDENCE / f"{prefix}-{board}-final-erc.stdout.json")["result"]
        independent_erc = read(EVIDENCE / f"{independent_prefix}-{board}-independent-erc.stdout.json")["result"]
        historical_erc = read(R6 / f"verification/{board}-restore-erc.json")["result"]
        check(final_erc.get("strict") is True and final_erc.get("fatal") == fatal
              and erc_signature(final_erc) == erc_signature(independent_erc) == erc_signature(historical_erc),
              f"{board} strict native ERC changed")
        final_dump = EVIDENCE / f"final/{board}-copper.json"
        independent_dump = EVIDENCE / f"independent/{board}-copper.json"
        lhs, rhs = read(final_dump), read(independent_dump)
        check(view(lhs) == view(rhs), f"{board} live native geometry differs after independent import")
        component_total += len(lhs["components"])
        final_net = EVIDENCE / f"final/{net_name}-r7.net"
        independent_net = EVIDENCE / f"independent/{net_name}-r7.net"
        old_net = R6 / f"verification/netlists/{net_name}-r6.net"
        def membership(path):
            parts, nets = parse_protel(path.read_text(encoding="utf-8-sig"))
            return (Counter((p["designator"], p["convert_to_pcb"]) for p in parts),
                    Counter((net, tuple(sorted(members))) for net, members in nets))
        check(membership(final_net) == membership(independent_net) == membership(old_net),
              f"{board} native compiled netlist changed")
        _, groups = parse_protel(final_net.read_text(encoding="utf-8-sig"))
        net_total += len(groups)
        member_total += sum(len(members) for _, members in groups)
        audit = audit_board_v4(board, dfm_native, final_dump, blind_csv=dfm_folder / f"{board}-blind-vias.csv")
        dfm = audit["v4_official_jlcpcb_hdi_audit"]
        check(dfm["total_blind_vias"] == {"PCB1": 61, "PCB2": 40, "PCB3": 41}[board]
              and dfm["violations"]["total_v4_violations"] == 0,
              f"{board} bounded V4 blind-via rule subset changed")
        report_boards[board] = {
            "components": len(lhs["components"]), "nativeDrc": EXPECTED_DRC[board],
            "strictErcFatal": fatal, "liveGeometryMatchesIndependentImport": True,
            "netlistSha256": digest(final_net), "reload": verify_reload(board, prefix, doc),
            "boundedV4BlindViaSubset": {"blindVias": dfm["total_blind_vias"], "violations": 0},
        }
    check(component_total == 257 and net_total == 207 and member_total == 1013,
          "Device/net-group/member totals differ from controlled baseline")
    python_log = (EVIDENCE / "repository-python-tests.txt").read_text(encoding="utf-8")
    node_log = (EVIDENCE / "repository-node-tests.txt").read_text(encoding="utf-8")
    check("Ran 102 tests" in python_log and "OK (skipped=1)" in python_log
          and "ℹ pass 25" in node_log and "ℹ fail 0" in node_log,
          "Separate Python/Node test evidence is incomplete")
    return {
        "status": "VERIFIED-LIMITED-R7", "manufacturing": "BLOCKED", "notForFab": True,
        "nativeSha256": digest(archive), "independentReexportSha256": digest(reexport),
        "independent_full_reexport_compared": True, "independentDocumentRecordsEqual": True,
        "documentCount": len(final_records), "schematicPages": forms["SCH_PAGE"],
        "components": component_total, "archivedResolvedSchematicTerminals": terminal_count,
        "archivedExplicitControlledNC": nc_count, "archiveRawNCMarkers": 94,
        "controlledTerminalBaseline": {
            "status": "INHERITED-R6-DELTA-NOT-R7-REGRESSION", "historicalH02Terminals": 1075,
            "unresolvedLegacySourceReferences": ["R_ESP_BOOT"],
            "terminalDifference": expected_terminal_delta,
            "r6R7AndIndependentAuditsIdentical": True,
            "note": "The H02 terminal list predates inherited R6 symbol changes; it is not silently rewritten."
        },
        "netGroups": net_total, "netMembers": member_total,
        "totalConnectionErrors": 708, "netlistErrors": 1, "strictErcFatal": 6,
        "boards": report_boards, "acceptedScope": scope,
        "repositoryTests": {"python": {"total": 102, "passed": 101, "skipped": 1},
                            "nodeSeparateExecutable": {"passed": 25, "failed": 0}},
        "excludedClaims": ["U11.K4 complete-net closure", "HDI manufacturer approval", "impedance signoff",
                           "full-board routing", "40 g hardware validation", "physical prototype validation"],
    }


if __name__ == "__main__":
    output = EVIDENCE / "r7-verification.json"
    try:
        report = verify()
    except (KeyError, OSError, ValueError) as error:
        report = {"status": "FAIL", "manufacturing": "BLOCKED", "error": str(error)}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(report["status"] != "VERIFIED-LIMITED-R7")
