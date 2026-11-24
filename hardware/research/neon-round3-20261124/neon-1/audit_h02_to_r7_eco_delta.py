#!/usr/bin/env python3
"""
H02 -> R7 Schematic ECO Delta & MISSFOOTPRINT Reconcile Auditor (Read-Only).

Complements `h03-kimi-r7-20261123/tools/controlled_sch_audit.py` without
modifying any controlled baseline files. Verifies that all schematic deltas
between H02 `CAD_TERMINALS.csv` (1075 terminals) and R7 native archive
(1076 terminals) are 100% explained by approved ECO-08, ECO-09, and ECO-14,
and classifies the 6 strict ERC MISSFOOTPRINT fatal items.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_UNRESOLVED = {("M-MAIN-L", "R10", "R_ESP_BOOT")}

EXPECTED_TERMINAL_DIFF = {
    ("M-MAIN-L", "R10", "1"),   # ECO-09: removed duplicate pull-up R10 (-2)
    ("M-MAIN-L", "R10", "2"),
    ("M-MAIN-L", "U12", "4"),   # ECO-14: 3-pin -> 6-pin TPD2E001DRYR (+3)
    ("M-MAIN-L", "U12", "5"),
    ("M-MAIN-L", "U12", "6"),
}

EXPECTED_NC_DIFF = {
    ("M-AUD-R", "U11", "F11"),  # ECO-08: LFXO XL1 removed NC (-2)
    ("M-AUD-R", "U11", "F12"),  # ECO-08: LFXO XL2 removed NC
    ("M-MAIN-L", "U12", "4"),   # ECO-14: TPD2E001DRYR Pin 4 NC (+2)
    ("M-MAIN-L", "U12", "6"),   # ECO-14: TPD2E001DRYR Pin 6 NC
}

EXPECTED_MISSFOOTPRINT_BOARD_BLOCKED = {("PCB1", "J2"), ("PCB1", "J3")}
EXPECTED_MISSFOOTPRINT_EXTERNAL_ASSY = {
    ("PCB1", "SPK1"),
    ("PCB1", "BAT1"),
    ("PCB3", "SPK1"),
    ("PCB3", "BAT1"),
}


def audit_controlled_sch(audit_data: dict[str, Any]) -> dict[str, Any]:
    integrated = audit_data.get("integrated", audit_data)
    findings: list[str] = []

    term_count = integrated.get("terminalCount")
    ctrl_term_count = integrated.get("controlledTerminalCount")
    net_delta = (term_count - ctrl_term_count) if (
        isinstance(term_count, int) and isinstance(ctrl_term_count, int)
    ) else None

    if net_delta != 1:
        findings.append(
            f"Unexpected terminal net delta: {term_count} - {ctrl_term_count} = {net_delta} (expected +1 from ECO-09 -2 and ECO-14 +3)"
        )

    actual_unresolved = {
        (c.get("board"), c.get("designator"), c.get("sourceReference"))
        for c in integrated.get("unresolvedComponents", [])
    }
    if actual_unresolved != EXPECTED_UNRESOLVED:
        findings.append(
            f"Unexpected unresolvedComponents: extra={sorted(actual_unresolved - EXPECTED_UNRESOLVED)}, "
            f"missing={sorted(EXPECTED_UNRESOLVED - actual_unresolved)}"
        )

    actual_term_diff = {tuple(x) for x in integrated.get("terminalDifference", [])}
    if actual_term_diff != EXPECTED_TERMINAL_DIFF:
        findings.append(
            f"Unexpected terminalDifference: extra={sorted(actual_term_diff - EXPECTED_TERMINAL_DIFF)}, "
            f"missing={sorted(EXPECTED_TERMINAL_DIFF - actual_term_diff)}"
        )

    actual_nc_diff = {tuple(x) for x in integrated.get("ncDifference", [])}
    if actual_nc_diff != EXPECTED_NC_DIFF:
        findings.append(
            f"Unexpected ncDifference: extra={sorted(actual_nc_diff - EXPECTED_NC_DIFF)}, "
            f"missing={sorted(EXPECTED_NC_DIFF - actual_nc_diff)}"
        )

    explicit_nc = integrated.get("explicitNCCount")
    ctrl_nc = integrated.get("controlledNCCount")
    raw_nc = integrated.get("archiveRawNCMarkers")
    nc_marker_gap = (raw_nc - explicit_nc) if (
        isinstance(raw_nc, int) and isinstance(explicit_nc, int)
    ) else None

    if explicit_nc != ctrl_nc:
        findings.append(
            f"explicitNCCount ({explicit_nc}) != controlledNCCount ({ctrl_nc}); ECO-08 (-2) and ECO-14 (+2) should cancel out."
        )

    return {
        "status": "PASS_WITH_APPROVED_ECO_DELTA" if not findings else "FAIL_UNEXPECTED_DELTA",
        "terminalCount": term_count,
        "controlledTerminalCount": ctrl_term_count,
        "netTerminalDelta": net_delta,
        "explicitNCCount": explicit_nc,
        "controlledNCCount": ctrl_nc,
        "archiveRawNCMarkers": raw_nc,
        "rawVsExplicitNCGap": nc_marker_gap,
        "unexpectedFindings": findings,
    }


def extract_missfootprint_designators(erc_payload: Any) -> list[str]:
    """Recursively extract designators from EasyEDA Pro ERC stdout JSON."""
    hits: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            rule = str(node.get("rule") or node.get("type") or node.get("code") or "")
            msg = str(node.get("message") or node.get("msg") or "")
            if "MISSFOOTPRINT" in rule.upper() or "MISSFOOTPRINT" in msg.upper():
                des = node.get("designator") or node.get("name") or node.get("objName")
                if des:
                    hits.append(str(des))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(erc_payload)
    return hits


def audit_missfootprint(erc_files: dict[str, Path]) -> dict[str, Any]:
    found: set[tuple[str, str]] = set()
    for board, path in erc_files.items():
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for des in extract_missfootprint_designators(payload):
            found.add((board, des))

    expected_all = EXPECTED_MISSFOOTPRINT_BOARD_BLOCKED | EXPECTED_MISSFOOTPRINT_EXTERNAL_ASSY
    unexpected = sorted(found - expected_all)
    missing = sorted(expected_all - found)

    return {
        "status": "PASS_CLASSIFIED" if (not unexpected and not missing) else "CHECK_REQUIRED",
        "totalFound": len(found),
        "boardInterfaceBlocked": sorted(found & EXPECTED_MISSFOOTPRINT_BOARD_BLOCKED),
        "externalAssembly": sorted(found & EXPECTED_MISSFOOTPRINT_EXTERNAL_ASSY),
        "unexpected": unexpected,
        "missing": missing,
    }


def run_self_test() -> int:
    sample_audit = {
        "integrated": {
            "status": "FAIL",
            "resolvedComponents": 252,
            "unresolvedComponents": [
                {
                    "sourceReference": "R_ESP_BOOT",
                    "board": "M-MAIN-L",
                    "designator": "R10",
                    "capturePage": "3e7683d1ed324ce9",
                    "captureUniqueId": "41bc0941336b1513",
                    "candidateIdentities": [],
                }
            ],
            "terminalCount": 1076,
            "controlledTerminalCount": 1075,
            "terminalDifference": [list(x) for x in sorted(EXPECTED_TERMINAL_DIFF)],
            "explicitNCCount": 92,
            "controlledNCCount": 92,
            "ncDifference": [list(x) for x in sorted(EXPECTED_NC_DIFF)],
            "archiveRawNCMarkers": 94,
        }
    }
    res = audit_controlled_sch(sample_audit)
    assert res["status"] == "PASS_WITH_APPROVED_ECO_DELTA", f"Self-test failed: {res}"
    assert res["netTerminalDelta"] == 1
    assert res["rawVsExplicitNCGap"] == 2
    print(json.dumps({"selfTest": "PASS", "result": res}, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit H02 -> R7 ECO schematic delta (read-only).")
    parser.add_argument(
        "--audit-json",
        type=Path,
        help="Path to h03-kimi-r7-20261123/verification/controlled-sch-audit.json",
    )
    parser.add_argument("--pcb1-erc", type=Path, help="Optional path to 69-PCB1-independent-erc.stdout.json")
    parser.add_argument("--pcb2-erc", type=Path, help="Optional path to PCB2 ERC JSON")
    parser.add_argument("--pcb3-erc", type=Path, help="Optional path to 63-PCB3-final-erc.stdout.json")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test against R7 verified schema.")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.audit_json:
        parser.error("Provide --audit-json or --self-test")

    audit_data = json.loads(args.audit_json.read_text(encoding="utf-8"))
    report: dict[str, Any] = {"schematicEcoAudit": audit_controlled_sch(audit_data)}

    erc_map = {
        k: v
        for k, v in [("PCB1", args.pcb1_erc), ("PCB2", args.pcb2_erc), ("PCB3", args.pcb3_erc)]
        if v is not None
    }
    if erc_map:
        report["missfootprintAudit"] = audit_missfootprint(erc_map)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sch_ok = report["schematicEcoAudit"]["status"] == "PASS_WITH_APPROVED_ECO_DELTA"
    fp_ok = (
        "missfootprintAudit" not in report
        or report["missfootprintAudit"]["status"] == "PASS_CLASSIFIED"
    )
    return 0 if (sch_ok and fp_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
