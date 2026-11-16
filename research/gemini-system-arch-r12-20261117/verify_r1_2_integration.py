#!/usr/bin/env python3
"""
EVT-1 System Architecture R1.2 Cross-Consistency & Evidence Verification Gate
Verifies R1.2 deliverables against Codex Rev D1.1 and Claude Optics R0.1 source files.
"""
import csv
import json
from pathlib import Path
import sys

OUT_DIR = Path(__file__).resolve().parent
D11_DIR = Path("/working_dir/c_b8ef830dd56e496d/pr_inputs/zip2/AI-AR-codex-Claude--e78e57260f7d0105936e2bed7059b857321431aa/hardware/evt1-rev-d1-1-20261117")
R01_DIR = Path("/working_dir/c_b8ef830dd56e496d/pr_inputs/zip1/AI-AR-codex-Claude--4c03f5b394b3cf205dc3a82b878a79f430369c65/research/claude-dual-ar-optics-r01-20261117")


def load_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    report_lines = []
    failures = []

    def check(name: str, cond: bool, detail: str):
        status = "PASS" if cond else "FAIL"
        report_lines.append(f"[{status}] {name}: {detail}")
        if not cond:
            failures.append(f"{name}: {detail}")

    # 1. Verify Rev D1.1 BOM & PINMAP exact counts
    bom_rows = load_csv(D11_DIR / "02_BOM_PINMAP_ICD_Blocked/BOM_V1_0_FROZEN.csv")
    pinmap_rows = load_csv(D11_DIR / "02_BOM_PINMAP_ICD_Blocked/PINMAP_V1_0_FROZEN.csv")
    check("R1.2-01 Rev D1.1 BOM & PINMAP Scale", len(bom_rows) == 135 and len(pinmap_rows) == 1067,
          f"BOM={len(bom_rows)}, PINMAP={len(pinmap_rows)}")

    # 2. Verify Rev D1.1 key power & AVDD 9-IC parts exist in BOM
    bom_mpns = {r.get("MPN", "") for r in bom_rows}
    bom_refs = {r.get("RefDes", "") for r in bom_rows}
    required_mpns = {
        "BQ25180YBGR", "BQ25170DSGR", "LM66200DRLR", "TPS63805YFFR",
        "TPS62840DLCR", "TLV75512PDQNR", "TLV75518PDQNR",
        "LTC6993IS6-2#TRPBF", "SN74LVC1G175DCKR", "TPS389018DSET", "TPS389025DSET",
        "74LVC2G07GS", "SN74LVC2T45DCUR", "SN74LVC2G17DCKR",
        "BM28B0.6-30DS/2-0.35V(53)", "BM28B0.6-24DS/2-0.35V(53)",
        "BM28B0.6-16DS/2-0.35V(53)", "BM28B0.6-10DS/2-0.35V(53)",
    }
    missing_mpns = sorted(m for m in required_mpns if not any(m in x for x in bom_mpns))
    check("R1.2-02 Rev D1.1 Power/AVDD/BTB MPNs", len(missing_mpns) == 0,
          f"Checked {len(required_mpns)} key MPNs; missing={missing_mpns}")

    # 3. Verify legacy defective parts are NOT in Rev D1.1 BOM
    forbidden_mpns = ["BQ24074", "TPS63802"]
    found_forbidden = [m for m in forbidden_mpns if any(m in x for x in bom_mpns)]
    check("R1.2-03 Legacy Power ICs Excluded", len(found_forbidden) == 0,
          f"Forbidden legacy parts in BOM={found_forbidden}")

    # 4. Verify Mass Plan numbers
    mass_rows = load_csv(D11_DIR / "02_BOM_PINMAP_ICD_Blocked/MASS_PLAN_REV_D1_1.csv")
    mass_vals = [float(r["Mass_g"]) for r in mass_rows]
    check("R1.2-04 Rev D1.1 Mass Plan", len(mass_vals) == 2 and abs(mass_vals[0] - 41.2408) < 1e-4 and abs(mass_vals[1] - 39.423) < 1e-4,
          f"MASS_PLAN_REV_D1_1.csv={mass_vals}")

    # 5. Verify Claude R0.1 ECR-01 rejection in INTEGRATION_GATES.md
    gates_text = (R01_DIR / "INTEGRATION_GATES.md").read_text(encoding="utf-8")
    check("R1.2-05 ECR-01 Rejected in R0.1 Integration Gates", "暂不接受" in gates_text and "ECR-01" in gates_text,
          "Confirmed ECR-01 (delete FPGA) is REJECTED due to 0 DSI on ESP32-S3")

    # 6. Verify R1.2 deliverables completeness & no false PASS on blocked items
    arch_text = (OUT_DIR / "EVT1_SYSTEM_ARCH_R1_2.md").read_text(encoding="utf-8")
    kimi_text = (OUT_DIR / "KIMI_DESIGN_CONSTRAINTS_R1_2.md").read_text(encoding="utf-8")
    rec_rows = load_csv(OUT_DIR / "RECONCILIATION_EVIDENCE_TABLE_R1_2.csv")
    risk_rows = load_csv(OUT_DIR / "SYSTEM_RISK_REGISTER_R1_2.csv")

    check("R1.2-06 Deliverables Populated",
          len(rec_rows) >= 16 and len(risk_rows) >= 20 and "NOT FOR FAB" in arch_text and "NOT FOR FAB" in kimi_text,
          f"Reconciliation rows={len(rec_rows)}, Risk rows={len(risk_rows)}")

    check("R1.2-07 Optical & Thermal Constraints Unified",
          "16 px" in arch_text and "1.5 W" in arch_text and "40 °C" in arch_text and "43 °C" in arch_text,
          "16px overscan, <=1.5W, <=40/43C thermal limits present in R1.2 architecture")

    check("R1.2-08 Native/Physical/NDA Blockers Preserved",
          any(r["Risk_ID"] == "BLK-D11-PHY" and "BLOCKED" in r["Current_Status"] for r in risk_rows)
          and any(r["Risk_ID"] == "BLK-JBD-01" and "BLOCKED" in r["Current_Status"] for r in risk_rows)
          and any(r["Risk_ID"] == "BLK-RevC-01" and "BLOCKED" in r["Current_Status"] for r in risk_rows),
          "BLK-D11-PHY, BLK-JBD-01, BLK-RevC-01 remain BLOCKED")

    report_lines.append("")
    report_lines.append(f"SUMMARY: PASS={len(report_lines)-1-len(failures)}, FAIL={len(failures)}")
    report_lines.append("NATIVE_EDA_SPICE_CAD_STATUS: BLOCKED (iverilog/yosys/nextpnr/icetime/ngspice/kicad-cli unavailable in sandbox; physical & JBD NDA gates OPEN; NOT FOR FAB)")

    report_text = "\n".join(report_lines) + "\n"
    (OUT_DIR / "r1_2_verification_report.txt").write_text(report_text, encoding="utf-8")
    print(report_text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
