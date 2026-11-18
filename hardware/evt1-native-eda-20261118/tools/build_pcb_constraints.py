#!/usr/bin/env python3
"""Build an auditable EVT-1 H03 partition and HDI constraint manifest."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "evt1-rev-d1-1-20261117" / "01_Architecture_and_Interfaces" / "SYSTEM_BUDGETS_V1_0.json"
STACK_SECTION = "5_hdi_pcb_and_complete_bom_3d_placement"
CONTACT_SECTION = "7_rev_d_crossboard_power_and_contacts"
PARTITION = {
    "M-MAIN-L": (
        "ESP32-S3 host, Wi-Fi, both-cell ORing and system conversion, left charger, left speaker and microphone",
        "Camera rail isolation, current-window privacy sensing, DVP translation, USB/charge ingress",
    ),
    "M-OPT-BRIDGE": (
        "iCE40UP5K rendering/transport, local power sequencing and independent AVDD inhibit",
        "Two optical branches, center IMU and microphone, physical camera privacy indicator",
    ),
    "M-AUD-R": (
        "nRF5340 LE Audio, antenna and reference clock, right charger, right speaker and microphone",
        "Right protected pack, BTL outputs and SWD access",
    ),
}
IMPLEMENTATION = [
    ("M-MAIN-L", "ESP_RF", ["U1_HOST", "ANT1", "R_ESP_RF", "C_ESP_RF_IN", "C_ESP_RF_OUT"],
     "Keep feed short and controlled to the vendor impedance with a continuous reference up to the antenna launch. Preserve the DNP matching option and the antenna-specific no-copper region."),
    ("M-MAIN-L", "POWER_ENTRY", ["J_CHG", "U12_ESD_USB", "U3_L", "U4_OR", "U4_BB", "U4_1V8"],
     "Put TVS at the exposed interface. Preserve a paired USB return through the connector. Place input and output bypass at the converters and minimize the switching hot loops. Keep the switch node away from camera and RF traces."),
    ("M-MAIN-L", "CAM_PRIVACY", ["R_SENSE", "U7_INA", "U7_WIN", "J_CAM"],
     "Route separate Kelvin sense traces from the R_SENSE terminations. Keep the privacy sense nodes away from switching copper. Preserve camera rail discharge and isolation paths. Freeze the sensor power-up contract before module enable."),
    ("M-OPT-BRIDGE", "FPGA_ESCAPE", ["U2_FPGA", "Y1_OSC", "C_FPGA_OSC_HF"],
     "Place every explicit bypass at the named supply ball with a short ground return. Prove access to the internal balls using supplier-accepted copper-filled and capped stacked VIPPO. Keep the 48 MHz oscillator close to U2_FPGA.B3."),
    ("M-OPT-BRIDGE", "OPTICAL_TRANSPORT", ["J_DISP_L", "J_DISP_R"],
     "Reserve two independent optical branch regions. Keep source damping adjacent to the FPGA and route each SCK/CS/DQ branch over a continuous reference. Geometry, loading and allowable skew are pending the optical interface contract."),
    ("M-OPT-BRIDGE", "AVDD_INHIBIT", ["U_AVDD_IO_PG", "U_AVDD_SYS_PG", "U_AVDD_SYS_CLAMP", "U_AVDD_WD", "U_AVDD_QUAL", "U_AVDD_EN_OD", "TP_AVDD_SAFE"],
     "Keep the independent clamp path short to the candidate LDO enable. Place the qualification RC and all rail bypass locally. Reserve probe clearance and short test return. Confirm loading of watchdog, PG and EN with the actual fixture."),
    ("M-AUD-R", "BLE_RF", ["U11_BLE", "ANT2_BLE", "Y2_BLE", "NRF_L1", "NRF_L2", "NRF_L3", "NRF_L4", "NRF_CT19"],
     "Copy Nordic CMAA configuration 3 RF/DC-DC topology with reference geometry and actual footprints. Keep crystal tracks and return quiet. Maintain antenna feed/keepout and the RF tuning pad. Preserve SWD access."),
    ("M-MAIN-L", "AUDIO_LEFT", ["U10_AMP_L", "SPK_L", "MK1_L"],
     "Route the amplifier outputs as BTL to the speaker. Keep class-D switching copper away from the PDM microphone and RF. Board drawing must include the microphone port and acoustic gasket."),
    ("M-OPT-BRIDGE", "CENTER_ACOUSTIC_MECH", ["MK2_C", "U9_IMU"],
     "Reserve the center microphone acoustic opening and gasket. Keep the IMU away from the hinge flex/stress field and use the physical package orientation in the system axes."),
    ("M-AUD-R", "AUDIO_RIGHT", ["U10_AMP_R", "SPK_R", "MK3_R"],
     "Route the amplifier outputs as BTL to the speaker. Keep class-D switching copper away from the PDM microphone, crystal and RF. Board drawing must include the microphone port and acoustic gasket."),
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def derive(document, ref_keys):
    hdi = document[STACK_SECTION]
    contacts = document[CONTACT_SECTION]["contact_rules"]
    peaks = document[CONTACT_SECTION]["peak_current_estimates_a"]
    stack_total = round(sum(item["thickness_mm"] for item in hdi["layers"]), 3)
    amp_per_contact = round(peaks["VSYS_bridge"] * contacts["derating_factor"] / 2, 5)
    nominal_imbalance = round(contacts["bm28_signal_rating_a"] - amp_per_contact, 5)
    manifest = {
        "baseline": {"pull_request": 25, "system_budget_file": BASE.relative_to(ROOT.parent.parent).as_posix()},
        "design_label": "NOT FOR FAB",
        "status": "BLOCKED",
        "mechanical_envelope_status": "UNVERIFIED",
        "assembly_mass_target_g": 40,
        "stackup": {
            "status": "BLOCKED",
            "type": hdi["selected_stackup"],
            "layers": hdi["layers"],
            "nominal_sum_mm": stack_total,
            "requires": "Separate vendor-approved stack documentation per PCB. Supplier copper/mask datum and impedance model are open, including the thinner bridge.",
        },
        "do_not_relax": {
            "minimum_trace_um": hdi["min_trace_um"],
            "minimum_clearance_um": hdi["min_space_um"],
            "minimum_edge_clearance_mm": hdi["min_edge_clearance_mm"],
            "minimum_courtyard_gap_mm": hdi["min_courtyard_gap_mm"],
            "microvia_nominal_drill_um": hdi["microvia_drill_um"],
            "microvia_nominal_land_um": hdi["microvia_pad_um"],
            "microvia_nominal_annular_ring_um": (hdi["microvia_pad_um"] - hdi["microvia_drill_um"]) / 2,
            "buried_via_nominal_drill_um": hdi["buried_core_via_drill_um"],
            "buried_via_nominal_land_um": hdi["buried_core_via_pad_um"],
            "buried_via_nominal_annular_ring_um": (hdi["buried_core_via_pad_um"] - hdi["buried_core_via_drill_um"]) / 2,
            "btb_fpc_stiffener_mated_allowance_mm": hdi["btb_mated_fpc_stiffener_extra_z_mm"],
        },
        "boards": {},
        "fpc_dynamic_zones": hdi["fpc_dynamic_hinge_zones"],
        "fpc_dynamic_zone_rule": "Keep pads, vias, components and stiffener transitions outside active bending. Verify neutral axis, adhesive stack, cycle load and assembly radii with the FPC vendor.",
        "rf_keepout_candidates": hdi["rf_keepout_zones"],
        "rf_status": "UNVERIFIED",
        "escape_candidates": [],
        "mated_contact_checks": {
            "status": "UNVERIFIED",
            "rating_a": {"signal": contacts["bm28_signal_rating_a"], "power": contacts["bm28_power_rating_a"]},
            "peak_design_a": {"VBAT_R_RET": peaks["VBAT_R_RET"], "GND": peaks["GND"], "VSYS_bridge": peaks["VSYS_bridge"]},
            "derating_factor": contacts["derating_factor"],
            "current_assignment": {"PWR1": "VBAT_R_RET", "PWR2": "GND", "P2/P3 (left and bridge)": "VSYS"},
            "vsys_equal_share_per_contact_a": amp_per_contact,
            "vsys_equal_share_a_below_contact_rating": nominal_imbalance,
            "vsys_max_actual_per_contact_at_design_factor_a": round(contacts["bm28_signal_rating_a"] / contacts["derating_factor"], 5),
            "requires": "Verify mirrored contact numbering, current sharing, FPC copper/round-trip drop and connector temperature. The right-side P2 ground signal contact must not carry the main return on its own.",
        },
        "optical_interface": {
            "status": "BLOCKED",
            "architecture": "Binocular transparent AR",
            "vendor_contract": ["BLK-JBD-01", "BLK-JBD-02", "BLK-JBD-03", "BLK-JBD-04", "BLK-JBD-05"],
        },
        "placement_and_route": [],
    }
    for name, board in hdi["boards"].items():
        manifest["boards"][name] = {
            "status": "UNVERIFIED",
            "functions": PARTITION[name],
            "length_y_mm": board["length_y_mm"],
            "width_zones": board["width_zones"],
            "cavity_max_z_mm": board["cavity_max_z_mm"],
            "pcb_thickness_z_mm": board["pcb_thickness_z_mm"],
            "area_envelope_mm2": round(sum((z["y_end_mm"] - z["y_start_mm"]) * z["width_x_mm"] for z in board["width_zones"]), 3),
        }
    for item in hdi["fine_pitch_escape_audit"]:
        gap = item["pitch_um"] - item["pad_diameter_um"]
        required = item["trace_width_um"] + 2 * item["min_clearance_um"]
        manifest["escape_candidates"].append({
            "ref": item["ref"],
            "status": "UNVERIFIED",
            "nominal_pitch_um": item["pitch_um"],
            "nominal_land_diameter_um": item["pad_diameter_um"],
            "nominal_trace_gap_residual_um": gap - required,
            "minimum_trace_width_um": item["trace_width_um"],
            "minimum_trace_clearance_um": item["min_clearance_um"],
            "requires_stacked_l1_l3_vippo": item["requires_stacked_l1_l3_vippo"],
        })
    for board, rule, refs, text in IMPLEMENTATION:
        if missing := {(board, ref) for ref in refs} - ref_keys:
            raise ValueError(f"{rule} refers to absent source objects: {sorted(missing)}")
        status = "BLOCKED" if rule == "OPTICAL_TRANSPORT" else "UNVERIFIED"
        manifest["placement_and_route"].append({"board": board, "group": rule, "refs": refs,
                                                 "status": status, "constraint": text})
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with (ROOT / "Inputs" / "effective_netlist.csv").open(encoding="utf-8-sig", newline="") as handle:
        by_terminal = {(r["Board"], r["RefDes"], r["Pin"]): r for r in csv.DictReader(handle)}
    for board, ref in (("M-MAIN-L", "J_BTB_L"), ("M-OPT-BRIDGE", "J_BRIDGE_IN"), ("M-AUD-R", "J_BTB_R")):
        assert by_terminal[board, ref, "PWR1"]["Net"] == "VBAT_R_RET"
        assert by_terminal[board, ref, "PWR2"]["Net"] == "GND"
        if board != "M-AUD-R":
            assert by_terminal[board, ref, "P2"]["Net"] == by_terminal[board, ref, "P3"]["Net"] == "VSYS"
    manifest = derive(read_json(BASE), {(board, ref) for board, ref, _ in by_terminal})
    data = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    output = ROOT / "PCB_CONSTRAINTS.json"
    if args.check:
        if not output.exists() or output.read_bytes() != data:
            raise SystemExit("FAIL: PCB_CONSTRAINTS.json differs from audited inputs")
    else:
        output.write_bytes(data)
    print("PASS: PCB partition and constraint manifest reproduced from PR #25; H03 placement/DRC BLOCKED.")


if __name__ == "__main__":
    main()
