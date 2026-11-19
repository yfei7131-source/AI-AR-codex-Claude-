#!/usr/bin/env python3
"""Check the effective electrical boundaries and reproduce the corner calculations."""

import csv
import json
from pathlib import Path


INPUTS = Path(__file__).resolve().parents[1] / "Inputs"


def rows(name):
    with (INPUTS / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def check_inputs():
    netlist = rows("effective_netlist.csv")
    bom = {row["RefDes"]: row for row in rows("effective_bom.csv")}
    bench = rows("bench_gates.csv")
    assert len({row["Test_ID"] for row in bench}) == len(bench)
    assert all(row["Status"] in {"BLOCKED", "UNVERIFIED"} for row in bench)
    probes = {net for row in bench for net in row["Probe_Nets"].split("|")}
    assert probes <= {row["Net"] for row in netlist}

    optical_hold = {
        row["RefDes"] for row in netlist
        if row["Net"] == "AVDD_OPT_BIAS" and row["Pin_Function"].endswith(" (DNP)")
    }
    assert optical_hold == {"J_DISP_L", "J_DISP_R", "U6_OPT_AVDD"}
    assert all(bom[ref]["Verification_Status"].startswith("BLOCKED — DNP") for ref in optical_hold)
    avdd_rows = [row for row in netlist if row["Net"] == "AVDD_OPT_BIAS"]
    assert all(row["Domain_V"] == "BLOCKED_VENDOR" and not row["I_Peak_A"] for row in avdd_rows)

    series_current_factor = 200 * 2.20
    low_led_a = 1.09102 / series_current_factor
    high_led_a = 2.18204 / series_current_factor
    vf_upper_v = 2.80 - low_led_a * (249 + 2.20)
    vf_lower_v = 2.80 - high_led_a * (249 + 2.20)
    assert vf_upper_v < 2.20  # APHD1608LZGCK minimum at 2 mA and 25 C
    assert vf_lower_v < 1.90 < vf_upper_v
    assert bom["D3_PRIV"]["MPN"] == "APHD1608LCGCK"

    right_charge_max_ma = 1000 * 330 / (5490 * 0.99)
    dock_additive_case_ma = 498 + right_charge_max_ma
    assert dock_additive_case_ma > 500
    assert bom["J_CHG"]["Verification_Status"].startswith("BLOCKED")
    assert bom["U4_1V8F"]["Verification_Status"].startswith("BLOCKED")
    assert bom["L2_1V8"]["MPN"] == "DFE21CCN2R2MELL"
    return {
        "scope": "effective inputs and nominal/characteristic arithmetic",
        "status": "PASS",
        "physical_execution": "UNVERIFIED",
        "probe_nets_resolved": len(probes),
        "unexecuted_bench_gates": {status: sum(row["Status"] == status for row in bench)
                                  for status in ("BLOCKED", "UNVERIFIED")},
        "default_optical_dnp": sorted(optical_hold),
        "privacy_nominal_window_ma": [round(value * 1000, 4) for value in (low_led_a, high_led_a)],
        "privacy_nominal_diode_vf_window_v": [round(value, 4) for value in (vf_lower_v, vf_upper_v)],
        "dock_500ma_additive_corner_ma_excluding_overhead_inrush": round(dock_additive_case_ma, 4),
    }


if __name__ == "__main__":
    print(json.dumps(check_inputs(), indent=2))
