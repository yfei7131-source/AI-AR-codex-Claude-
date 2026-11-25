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
HDI_PUBLIC_SOURCE = "https://jlcpcb.com/pcb-fabrication/hdi-pcb"
HIROSE = "https://www.hirose.com/en/product/p/"
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
    ("M-MAIN-L", "POWER_ENTRY", ["J_CHG", "U12_ESD_USB", "U3_L", "U4_OR", "U4_BB", "U4_1V8", "L2_1V8"],
     "Put the selected TVS at the exposed interface with a short direct return. Preserve a paired USB return through the connector. Keep regulator bypass close and switching loops small. Retain the inductor body, terminal lands and under-coil copper/via exclusion except electrode copper; verify DC bias and height. Keep switch copper away from camera and RF traces."),
    ("M-MAIN-L", "CAM_PRIVACY", ["R_SENSE", "U7_INA", "U7_WIN", "J_CAM"],
     "Route separate Kelvin sense traces from the R_SENSE terminations. Keep the privacy sense nodes away from switching copper. Preserve camera rail discharge and isolation paths. Freeze the sensor power-up contract before module enable."),
    ("M-OPT-BRIDGE", "FPGA_ESCAPE", ["U2_FPGA", "Y1_OSC", "C_FPGA_OSC_HF"],
     "Place local 100 nF bypass at D2/A3/C4, the core/PLL/VPP caps at their actual rail balls, with short ground returns. Review separate bulk per supply ball against Lattice TN-02006. Escape inside balls via supplier-approved filled and capped VIPPO and keep the 48 MHz oscillator close to U2_FPGA.B3 with adjacent continuous return."),
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


def board_outline(length, zones):
    points = [[0, 0], [0, length]]
    edge = length
    for z in reversed(zones):
        if z["y_end_mm"] != edge or z["width_x_mm"] <= 0:
            raise ValueError("board zones must tile the board length")
        edge = z["y_start_mm"]
        points += [[z["width_x_mm"], z["y_end_mm"]], [z["width_x_mm"], edge]]
    if edge != 0:
        raise ValueError("board zones must begin at the common datum")
    return points


def check_contacts(terminals):
    left = ("M-MAIN-L", "J_BTB_L")
    mid = ("M-OPT-BRIDGE", "J_BRIDGE_IN")
    right = ("M-AUD-R", "J_BTB_R")
    by_connector = {key: {p: r for (board, ref, p), r in terminals.items() if (board, ref) == key}
                    for key in (left, mid, right)}
    contacts = [f"P{i}" for i in range(1, 31)] + ["PWR1", "PWR2"]
    if any(set(by_connector[key]) != set(contacts) for key in (left, mid)):
        raise ValueError("left/bridge connector pin coverage differs from the scheduled 30+2 contact set")
    right_contacts = [f"P{i}" for i in range(1, 17)] + ["PWR1", "PWR2"]
    if set(by_connector[right]) != set(right_contacts):
        raise ValueError("right connector pin coverage differs from the scheduled 16+2 contact set")
    pairs = []
    for pin in contacts:
        r1, r2 = by_connector[left][pin], by_connector[mid][pin]
        if (r1["Net"], r1["Domain_V"]) != (r2["Net"], r2["Domain_V"]):
            raise ValueError(f"left/bridge trunk mismatch on {pin}")
        if pin in ("PWR1", "P1") or pin in {f"P{i}" for i in range(23, 31)}:
            if r2["Note"] != "NC_TRUNK_PASS":
                raise ValueError(f"bridge FPC-only trunk unexpectedly lands on PCB at {pin}")
        pairs.append({"contact": pin, "net": r1["Net"], "bridge_lands_on_pcb": r2["Note"] != "NC_TRUNK_PASS"})
    for key in by_connector:
        for pin, net in (("PWR1", "VBAT_R_RET"), ("PWR2", "GND")):
            if by_connector[key][pin]["Net"] != net:
                raise ValueError(f"power contact mismatch at {key} {pin}")
    for pin in ("P2", "P3"):
        if by_connector[left][pin]["Net"] != "VSYS":
            raise ValueError(f"VSYS split contact changed at {pin}")
    left_nets = {r["Net"] for r in by_connector[left].values()}
    right_pins = [{"contact": p, "net": by_connector[right][p]["Net"]} for p in right_contacts]
    if not {r["net"] for r in right_pins} <= left_nets:
        raise ValueError("right FPC contact references a net absent from the trunk")
    return {"logical_check": "PASS", "physical_cable": "BLOCKED", "main_and_bridge_contacts": pairs,
            "right_contacts": right_pins, "return": "Confirm mated pin-1, opposing views, branch mapping and continuity."}


def connector_envelopes():
    return {
        "status": "BLOCKED", "numbering": "Confirm opposing-side footprint view and pin-1 after rotation and FPC mating.",
        "left_main": {"ref": "J_BTB_L", "source": HIROSE + "CL0673-5021-0-53", "body_xy_mm": [1.7, 7.85],
                      "old_lengthwise_overhang_mm": 0.325, "body_only_trial_xy_mm": [2.9, 41.8],
                      "rule": "Start the trial at (2.9, 41.8). Reserve the full mating connector/FPC insertion envelope and check local clearance to charge entry. No final position until the FPC and fixture are overlaid."},
        "right_audio": {"ref": "J_BTB_R", "source": HIROSE + "CL0673-5067-0-53", "old_body_xy_mm": [5.4, 1.7],
                        "old_transverse_width_deficit_mm": 0.2, "body_only_trial_xy_mm": [2.6, 30.5],
                        "trial_body_xy_mm": [1.7, 5.4], "trial_delta_rotation_degrees": 90,
                        "rule": "Try the original center with the long axis along +Y. Verify PCB footprint copper, mating plane, strain relief, mic and SWD access in 3D."},
        "bridge": {"refs": ["J_BRIDGE_IN", "J_DISP_L", "J_DISP_R"],
                   "sources": [HIROSE + "CL0673-5021-0-53", HIROSE + "CL0673-5044-0-53"],
                   "rule": "Use revised bridge search and retain both eye interfaces as blocked for vendor confirmation. No released mating or overhang."},
    }


def derive(document, terminals):
    hdi = document[STACK_SECTION]
    ref_keys = {key[:2] for key in terminals}
    contacts = document[CONTACT_SECTION]["contact_rules"]
    peaks = document[CONTACT_SECTION]["peak_current_estimates_a"]
    stack_total = round(sum(item["thickness_mm"] for item in hdi["layers"]), 3)
    amp_per_contact = round(peaks["VSYS_bridge"] / 2, 5)
    contact_actual_limit = round(contacts["bm28_signal_rating_a"] / contacts["derating_factor"], 5)
    stack_route_um = 2.7 * 25.4
    capture_land_um = hdi["microvia_drill_um"] + 6 * 25.4
    layer_count = sum(layer["layer"].startswith("L") for layer in hdi["layers"])
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
        "placement_datum": "Millimeters from the lower-left PCB bounding rectangle in PCB plan coordinates, +X across width and +Y along length. BOTTOM uses the same board coordinates; mirror footprint orientation in EDA and verify against the manufacturer top view.",
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
            "vsys_equal_share_with_design_factor_a": round(amp_per_contact * contacts["derating_factor"], 5),
            "vsys_actual_current_margin_per_contact_a": round(contact_actual_limit - amp_per_contact, 5),
            "vsys_max_actual_per_contact_at_design_factor_a": contact_actual_limit,
            "requires": "Verify mirrored contact numbering, current sharing, FPC copper/round-trip drop and connector temperature. The right-side P2 ground signal contact must not carry the main return on its own.",
        },
        "optical_interface": {
            "status": "BLOCKED",
            "architecture": "Binocular transparent AR",
            "vendor_contract": ["BLK-JBD-01", "BLK-JBD-02", "BLK-JBD-03", "BLK-JBD-04", "BLK-JBD-05"],
        },
        "placement_and_route": [],
        "fpc_contact_schedule": check_contacts(terminals),
        "connector_envelopes": connector_envelopes(),
        "reference_and_impedance": {
            "status": "BLOCKED",
            "reference_planes": ["L2_GND1", "L5_GND2"],
            "via_span_candidates": ["L1-L2", "L2-L3", "L3-L4 buried", "L4-L5", "L5-L6"],
            "rules": "Prove the plane continuity and adjacent ground return at every signal transition. Preserve the approved layer count and copper. Derive trace width, spacing and drill stack from accepted cross sections and coupons, including PCB/FPC connectors separately.",
            "usb": {"board": "M-MAIN-L", "nets": ["USB_DM", "USB_DP"], "target_differential_ohm": 90,
                    "tolerance_percent": 10, "source": "https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html#usb"},
            "rf": {"target_single_ended_ohm": 50, "boards": ["M-MAIN-L", "M-AUD-R"],
                   "rule": "Preserve antenna-specific all-layer copper clearance, approved feed matching reference and antenna launch. Tune in the folded and open finished enclosure."},
            "host_and_optics": {"status": "BLOCKED", "rule": "Keep SCK with adjacent continuous ground across each launch and FPC. Prove return path, damping and skew against voltage/edge-rate/receiver models. JBD thresholds, maximum skew and loading await the controlled contract."},
        },
        "supplier_screening": {
            "source": HDI_PUBLIC_SOURCE, "status": "BLOCKED", "applies_to": "JLCPCB public HDI offer, project DFM required",
            "public_0p50mm_max_layers": 4, "project_layer_count": layer_count,
            "public_order_min_individual_board_side_mm": 5.0,
            "public_buried_via_core_min_mm": 0.30,
            "project_buried_core_candidate_mm": next(l["thickness_mm"] for l in hdi["layers"] if l["layer"] == "CORE"),
            "public_min_laser_via_to_routed_edge_mm": 0.35,
            "public_extreme_trace_space_um": round(stack_route_um, 2),
            "project_laser_capture_land_um": hdi["microvia_pad_um"],
            "public_laser_capture_land_at_project_drill_um": round(capture_land_um, 2),
            "next": "Request a supplier-approved 6-layer cross section, filled vias, fine-line rules and sub-5-mm tab-routed panel. If 0.50 mm is unavailable, use an alternate HDI supplier or mechanically requalify a 6-layer stack at a larger Z; a 4-layer substitution is outside the current constraints.",
        },
    }
    for name, board in hdi["boards"].items():
        manifest["boards"][name] = {
            "status": "UNVERIFIED",
            "functions": PARTITION[name],
            "length_y_mm": board["length_y_mm"],
            "width_zones": board["width_zones"],
            "outline_polygon_mm": board_outline(board["length_y_mm"], board["width_zones"]),
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
            "public_jlc_one_trace_between_capture_pads_optimistic_residual_um": round(item["pitch_um"] - capture_land_um - 3 * stack_route_um, 2),
            "public_jlc_rule": "Use VIPPO/direct escape or change the DFM strategy; even ignoring the stricter via-to-trace spacing, nominal through-gap routing is unavailable at the screened pitch.",
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
    manifest = derive(read_json(BASE), by_terminal)
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
