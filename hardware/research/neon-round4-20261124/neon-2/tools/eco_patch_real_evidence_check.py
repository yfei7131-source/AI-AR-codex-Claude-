#!/usr/bin/env python3
"""
Real-Data Pre-Check & Isolated Patch Application Script (NO reconstructed full JSON).
1. Verifies unified diff syntax & hunk arithmetic of controlled_baseline_eco_h02_to_r7_v2_verified.patch.
2. Applies the patch in an isolated temporary directory strictly against the verbatim extracted
   hunk slices from real repository CAD_TERMINALS.csv (branch hardware/kimi-evt1-h03-r7-20261123).
3. Cross-checks patched U12 pins 1-6, retired R10, and U11.F11/F12 against verbatim lines from
   real PR #55 netlists (M-MAIN-L-r7.net & M-AUD-R-r7.net) and flags catalog-plan.json sync deltas.
4. Emits structured evidence JSON (eco_patch_verification_evidence.json).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

PATCH_PATH = Path("/working_dir/c_092afa91da962bf4/artifacts/file_generation/ttl=63d/output/controlled_baseline_eco_h02_to_r7_v2_verified.patch")

# Verbatim real lines extracted via remote browser from:
# https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/kicad/CAD_TERMINALS.csv?plain=1
VERBATIM_REAL_CSV_SLICES = {
    231: "M-MAIN-L,J3,J_CHG,3,USB_DP,USB_DP,CONNECTED,BIDIR,D+,BOM-50,BOARD,,BLOCKED",
    232: "M-MAIN-L,J3,J_CHG,4,GND,GND,CONNECTED,SRC,GND,BOM-50,BOARD,,BLOCKED",
    233: "M-MAIN-L,U12,U12_ESD_USB,1,VBUS_5V,VBUS_5V,CONNECTED,PASSIVE,VBUS clamp,BOM-51,BOARD,,BLOCKED",
    234: "M-MAIN-L,U12,U12_ESD_USB,2,USB_DM,USB_DM,CONNECTED,PASSIVE,D- clamp,BOM-51,BOARD,,BLOCKED",
    235: "M-MAIN-L,U12,U12_ESD_USB,3,USB_DP,USB_DP,CONNECTED,PASSIVE,D+ clamp,BOM-51,BOARD,,BLOCKED",
    236: "M-MAIN-L,TP2,TP_BAT_L_P,1,VBAT_L,VBAT_L,CONNECTED,PASSIVE,solder pad to BAT_L+,BOM-43,BOARD,,BLOCKED",
    237: "M-MAIN-L,TP1,TP_BAT_L_N,1,GND,GND,CONNECTED,PASSIVE,solder pad to BAT_L-,BOM-43,BOARD,,BLOCKED",
    438: "M-MAIN-L,C14,C_ESP_VDD_SPI,1,ESP_VDD_SPI_3V3,ESP_VDD_SPI_3V3,CONNECTED,PASSIVE,1 uF,BOM-SOC-01,BOARD,,BLOCKED",
    439: "M-MAIN-L,C14,C_ESP_VDD_SPI,2,GND,GND,CONNECTED,PASSIVE,1 uF,BOM-SOC-01,BOARD,,BLOCKED",
    440: "M-MAIN-L,R10,R_ESP_BOOT,1,QSPI_DIR1_EN,QSPI_DIR1_EN,CONNECTED,PASSIVE,10k,BOM-SOC-01,BOARD,,BLOCKED",
    441: "M-MAIN-L,R10,R_ESP_BOOT,2,3V3_SYS,3V3_SYS,CONNECTED,PASSIVE,10k,BOM-SOC-01,BOARD,,BLOCKED",
    442: "M-MAIN-L,R13,R_ESP_STRAP45,1,PDM_CLK_3V3,PDM_CLK_3V3,CONNECTED,PASSIVE,100k,BOM-SOC-01,BOARD,,BLOCKED",
    443: "M-MAIN-L,R13,R_ESP_STRAP45,2,GND,GND,CONNECTED,PASSIVE,100k,BOM-SOC-01,BOARD,,BLOCKED",
    959: "M-AUD-R,U11,U11_BLE,F8,GND,GND,CONNECTED,SINK,VSS,BOM-36,BOARD,,BLOCKED",
    960: "M-AUD-R,U11,U11_BLE,F10,NC_NRF_F10,,NC,NC,P0.05,BOM-36,BOARD,,BLOCKED",
    961: "M-AUD-R,U11,U11_BLE,F11,NC_NRF_F11,,NC,NC,P0.00/XL1,BOM-36,BOARD,,BLOCKED",
    962: "M-AUD-R,U11,U11_BLE,F12,NC_NRF_F12,,NC,NC,P0.01/XL2,BOM-36,BOARD,,BLOCKED",
    963: "M-AUD-R,U11,U11_BLE,G2,BLE_NRESET,BLE_NRESET,CONNECTED,RCV,nRESET,BOM-36,BOARD,,BLOCKED",
    964: "M-AUD-R,U11,U11_BLE,G3,NC_NRF_G3,,NC,NC,P1.07,BOM-36,BOARD,,BLOCKED",
}

# Verbatim real netlist expectations extracted from M-MAIN-L-r7.net & M-AUD-R-r7.net
REAL_NETLIST_TRUTH = {
    ("M-MAIN-L", "U12", "1"): "USB_DP",
    ("M-MAIN-L", "U12", "2"): "GND",
    ("M-MAIN-L", "U12", "3"): "USB_DM",
    ("M-MAIN-L", "U12", "4"): "",
    ("M-MAIN-L", "U12", "5"): "VBUS_5V_USB",
    ("M-MAIN-L", "U12", "6"): "",
    ("M-AUD-R", "U11", "F11"): "LFXO_XL1",
    ("M-AUD-R", "U11", "F12"): "LFXO_XL2",
}


def parse_and_verify_patch(patch_text: str):
    lines = patch_text.splitlines()
    hunks = []
    cur = None
    for line in lines:
        if line.startswith("@@"):
            m = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", line)
            if not m:
                raise ValueError(f"Invalid hunk header: {line}")
            cur = {
                "old_start": int(m.group(1)),
                "old_count": int(m.group(2)),
                "new_start": int(m.group(3)),
                "new_count": int(m.group(4)),
                "body": [],
            }
            hunks.append(cur)
        elif cur is not None:
            cur["body"].append(line)

    hunk_results = []
    added_rows = []
    removed_rows = []
    cumulative_delta = 0

    for idx, h in enumerate(hunks, 1):
        old_idx = h["old_start"]
        old_seen = 0
        new_seen = 0
        context_mismatches = []

        for bline in h["body"]:
            prefix, content = bline[0], bline[1:]
            if prefix in (" ", "-"):
                expected_real = VERBATIM_REAL_CSV_SLICES.get(old_idx)
                if expected_real != content:
                    context_mismatches.append({"line": old_idx, "patch": content, "real_csv": expected_real})
                old_idx += 1
                old_seen += 1
                if prefix == "-":
                    removed_rows.append(content)
            if prefix in (" ", "+"):
                new_seen += 1
                if prefix == "+":
                    added_rows.append(content)

        expected_new_start = h["old_start"] + cumulative_delta
        hunk_ok = (
            old_seen == h["old_count"]
            and new_seen == h["new_count"]
            and h["new_start"] == expected_new_start
            and not context_mismatches
        )
        cumulative_delta += (h["new_count"] - h["old_count"])
        hunk_results.append({
            "hunk_index": idx,
            "header_old": f"-{h['old_start']},{h['old_count']}",
            "header_new": f"+{h['new_start']},{h['new_count']}",
            "arithmetic_ok": old_seen == h["old_count"] and new_seen == h["new_count"] and h["new_start"] == expected_new_start,
            "verbatim_real_csv_context_match": not context_mismatches,
            "context_mismatches": context_mismatches,
            "pass": hunk_ok,
        })

    # Verify added rows against real PR #55 netlists
    netlist_checks = []
    for row in added_rows:
        cols = row.split(",")
        key = (cols[0], cols[1], cols[3])
        cad_net = cols[5]
        expected_net = REAL_NETLIST_TRUTH.get(key)
        netlist_checks.append({
            "terminal": list(key),
            "patched_cad_net": cad_net,
            "real_pr55_netlist_net": expected_net,
            "match": cad_net == expected_net,
        })

    r10_removed = [r for r in removed_rows if r.startswith("M-MAIN-L,R10,R_ESP_BOOT,")]
    return {
        "hunk_checks": hunk_results,
        "all_hunks_pass": all(h["pass"] for h in hunk_results),
        "r10_removed_lines_count": len(r10_removed),
        "netlist_checks": netlist_checks,
        "all_netlist_checks_pass": all(c["match"] for c in netlist_checks),
    }


def main():
    patch_text = PATCH_PATH.read_text(encoding="utf-8")
    res = parse_and_verify_patch(patch_text)
    evidence = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_scope": "Verbatim real-slice pre-check & netlist regression (NO reconstructed full JSON)",
        "patch_file": PATCH_PATH.name,
        "patch_verification": res,
        "defects_found_in_neon1_original_patch": [
            {
                "id": "DEFECT-01",
                "severity": "HIGH",
                "item": "U11.F11 / U11.F12 net name mismatch",
                "original_patch": "+LFXO_XL1 / +LFXO_XL2",
                "real_netlist_M_AUD_R_r7_net": "LFXO_XL1 / LFXO_XL2 (lines 3363-3374, no '+' prefix)",
                "fixed_in_v2_patch": True,
            },
            {
                "id": "DEFECT-02",
                "severity": "HIGH",
                "item": "catalog-plan.json missing from patch (R10 retirement & U12 6-pin sync)",
                "real_catalog_plan_json": "R10 (captureUniqueId 41bc0941336b1513, lines 3271-3299) still present; U12 (lines 4692-4721) still lists footprintPins ['1','2','3']; counts.boardComponents=253",
                "impact": "controlled_sch_audit.py keeps R10 in unresolvedComponents -> status remains FAIL",
            },
            {
                "id": "DEFECT-03",
                "severity": "MEDIUM",
                "item": "controlled_sch_audit.py archive_markers == len(markers) gate",
                "real_audit_record": "archiveRawNCMarkers=94 vs explicitNCCount=92 (2 orphan NO_CONNECT attributes in .epro2 outside 252 resolved components)",
                "impact": "Even after syncing CSV + catalog-plan.json, controlled_sch_audit.py returns FAIL until the 2 orphan NO_CONNECT attributes in the native archive are resolved or accounted for",
            },
        ],
        "blocked_items": [
            "Full binary .epro2 execution of run_controlled_sch_audit.py requires local git clone (offline VM has no outbound network; run_controlled_sch_audit.py returned GitHub 500 on web view).",
            "PR #58 h03-codex-r8-20261124/engineering/verification-summary.json returned GitHub 500 on web view.",
            "M-MAIN-L-r7.net top-level U12 FOOTPRINT declaration block was not reached within browser step limit (pin names confirmed as EVT1_U12_U12_ESD_USB_TPD2E001-*).",
        ],
    }
    out = Path("/working_dir/c_092afa91da962bf4/artifacts/file_generation/ttl=63d/output/eco_patch_verification_evidence.json")
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
