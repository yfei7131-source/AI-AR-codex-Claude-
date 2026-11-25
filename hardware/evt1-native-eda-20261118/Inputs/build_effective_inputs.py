#!/usr/bin/env python3
"""Apply the audited EVT-1 source overlay to the read-only PR #25 tables."""

import argparse
import csv
import io
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent / "evt1-rev-d1-1-20261117" / "02_BOM_PINMAP_ICD_Blocked"
BRIDGE = "M-OPT-BRIDGE"
AVDD_BLOCK = "BLOCKED_VENDOR"
LATTICE_CHECKLIST = "https://www.latticesemi.com/api/document/download?id=47779"
ABRACON_ASADV = "https://abracon.com/datasheets/ASADV.pdf"
OSCILLATOR = "ASADV-48.000MHZ-LC-T"
SPEAKER_ZONES = {"L": ("M-MAIN-L", "4.4"), "R": ("M-AUD-R", "4.2")}
UNRESOLVED_INTERFACES = {
    "CAM1", "D3_PRIV", "J_CAM", "J_CHG", "U12_ESD_USB", "J_DISP_L", "J_DISP_R", "U4_1V8F", "U6_OPT_AVDD",
}
OPTICAL_DNP_PINS = {"U6_OPT_AVDD": "1", "J_DISP_L": "PWR1", "J_DISP_R": "PWR1"}
BM28_RECEPTACLES = (
    ("BOM-15", "5021", "30+2", "1.70", "7.85"),
    ("BOM-31", "5021", "30+2", "1.70", "7.85"),
    ("BOM-26", "5044", "10+2", "4.35", "1.70"),
    ("BOM-29", "5044", "10+2", "4.35", "1.70"),
    ("BOM-40", "5067", "16+2", "5.40", "1.70"),
)
MURATA_L2 = "https://search.murata.co.jp/Ceramy/image/img/P02/JETE243A-0052.pdf"
PRIVACY_LED = "https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf"
LEFT_BATTERY_POR = "U3_L battery-only rising POR is 3.08/3.21/3.46V min/typ/max; running UVLO is separate."
FPGA_SEQUENCE_BLOCK = (
    "BLOCKED: TLV755P EN has only 0.3V low and 1.0V high guarantees. Direct PLL sensing "
    "does not establish the 0.5V minimum before SPI VCCIO1 is applied."
)
DOCK_SOURCE_BLOCK = (
    "BLOCKED: 498mA left input-limit upper characteristic at VIN=5V plus 60.72mA "
    "right charge-current corner already exceeds 500mA before right input overhead/inrush. "
    "No consumer USB source approval, no independent source selection/current gate."
)
DQN = {"U4_1V2", "U4_1V8F", "U5_LED2V8", "U6_CAM_AVDD", "U6_CAM_DOVDD",
       "U6_CAM_DVDD", "U6_OPT_AVDD"}
DSG = {"U3_R", "U7_WIN"}
CAPACITORS = (
    ("C_FPGA_PLL_BULK", "1V2_FPGA_PLL", "1.2", "4.7uF", "U2_FPGA.B2"),
    ("C_FPGA_PLL_HF", "1V2_FPGA_PLL", "1.2", "100nF", "U2_FPGA.B2"),
    ("C_FPGA_VPP_BULK", "1V8_FPGA_VPP", "1.8", "4.7uF", "U2_FPGA.D4"),
    ("C_FPGA_VPP_HF", "1V8_FPGA_VPP", "1.8", "100nF", "U2_FPGA.D4"),
    ("C_FPGA_CORE_BULK", "1V2_FPGA_CORE", "1.2", "4.7uF", "U2_FPGA.C2"),
    ("C_FPGA_CORE_HF", "1V2_FPGA_CORE", "1.2", "100nF", "U2_FPGA.C2"),
    ("C_FPGA_IO_BULK", "1V8_FPGA_IO", "1.8", "4.7uF", "U2_FPGA.D2/A3/C4"),
    ("C_FPGA_IO_HF0", "1V8_FPGA_IO", "1.8", "100nF", "U2_FPGA.A3"),
    ("C_FPGA_IO_HF1", "1V8_FPGA_IO", "1.8", "100nF", "U2_FPGA.D2"),
    ("C_FPGA_IO_HF2", "1V8_FPGA_IO", "1.8", "100nF", "U2_FPGA.C4"),
    ("C_FPGA_OSC_HF", "1V8_FPGA_IO", "1.8", "10nF", "Y1_OSC.4"),
)
POWER_FIELDS = (
    "Board", "RefDes", "Input_Pin", "Input_Net", "Output_Pin", "Output_Net",
    "Nominal_or_Contract", "Control", "Qualification", "Status",
)
POWER_TREE = (
    ("M-MAIN-L", "U3_L", "A2", "VBUS_5V", "B2", "VOUT_L_PPATH",
     "4.50V default regulated when adapter present", "BQ25180 SYS_REG via I2C",
     "Measure input limit, pass-through exclusion, thermal behavior and supplement on source loss", "UNVERIFIED"),
    ("M-MAIN-L", "U3_L", "A2", "VBUS_5V", "C2", "VBAT_L",
     "4.20V candidate; 10mA after POR, 50mA configured", "I2C/TS, qualified protected pack",
     "Pack/NTC spec must accept reset and watchdog profile", "BLOCKED"),
    ("M-MAIN-L", "U3_L", "C2", "VBAT_L", "B2", "VOUT_L_PPATH",
     "Battery-derived when adapter absent or in supplement", "U3_L power-path FET",
     LEFT_BATTERY_POR + " Confirm pack sag and cold start without the right OR input.", "BLOCKED"),
    ("M-AUD-R", "U3_R", "1", "VBUS_5V", "8", "VBAT_R_RET",
     "4.20V candidate; 54.64mA nominal", "27k VSET; 5.49k ISET; TS",
     "Protected pack/NTC vendor approval, termination and current with right amplifier muted", "BLOCKED"),
    ("M-MAIN-L", "Q_CHG_ISO_R", "2", "VBAT_R_RET", "3", "VBAT_R_ISOLATED",
     "Battery-derived, reverse-current path requires test", "CHG_ISO_GATE from VBUS",
     "No direct battery paralleling. Measure reverse and fault currents on VBUS edges", "UNVERIFIED"),
    ("M-MAIN-L", "U4_OR", "3", "VOUT_L_PPATH", "2", "VSYS",
     "Variable; 4.50V default nominal charger mode", "/ON tied low; LM66200 highest available input",
     "Measure differential, transition and peak current; board/flex drop is unverified", "UNVERIFIED"),
    ("M-MAIN-L", "U4_OR", "6", "VBAT_R_ISOLATED", "7", "VSYS",
     "Variable with pack and load", "/ON tied low; LM66200 highest available input",
     "Measure both source and current direction through charger transitions", "UNVERIFIED"),
    ("M-MAIN-L", "U4_BB", "A2", "VSYS", "E2", "3V3_SYS",
     "3.30V", "EN follows VSYS",
     "ESP32-S3 burst/reboot/strap capture; fit, copper and external parts per TI design curves", "UNVERIFIED"),
    ("M-MAIN-L", "U4_1V8", "2", "VSYS", "8", "1V8_SYS",
     "1.80V sense at COUT, not SW pad", "EN follows VSYS",
     "Verify nRF5340, ICM42688, microphones, translator IO and distribution to all three boards", "UNVERIFIED"),
    ("M-OPT-BRIDGE", "U4_1V2", "4", "VSYS", "1", "1V2_FPGA_CORE",
     "1.20V", "EN follows VSYS",
     "Scope 1V2_FPGA_CORE and 1V2_FPGA_PLL simultaneously through all ramps", "UNVERIFIED"),
    ("M-OPT-BRIDGE", "R_PLL", "1", "1V2_FPGA_CORE", "2", "1V2_FPGA_PLL",
     "1.20V source via 100R; filtered", "Passive local filter",
     "Lattice FPGA-TN-02006. Verify voltage and ramp at B2 and qualify LDO enable sourcing", "UNVERIFIED"),
    ("M-OPT-BRIDGE", "U4_1V8F", "4", "VSYS", "1", "1V8_FPGA_IO",
     "1.80V", "EN senses 1V2_FPGA_PLL",
     FPGA_SEQUENCE_BLOCK + " Qualify a guaranteed sequence and verify ramp/partial-power recovery.", "BLOCKED"),
    ("M-OPT-BRIDGE", "R_VPP", "1", "1V8_FPGA_IO", "2", "1V8_FPGA_VPP",
     "1.80V source via 10R; Slave SPI conditional", "Passive local filter",
     "Verify VPP at D4 within device limits and retain no oscillator/RGB IP requirement", "UNVERIFIED"),
    ("M-OPT-BRIDGE", "U6_OPT_AVDD", "4", "VSYS", "1", "AVDD_OPT_BIAS",
     "", "Population held DNP; Rev D1.1 OPT_AVDD_EN remains available for no-panel measurement",
     "Populate only after JBD rail/load/order and measured discharge/backfeed close; both panel connectors DNP as well", "BLOCKED"),
    ("M-MAIN-L", "U5_LED2V8", "4", "3V3_SYS", "1", "LED_2V8",
     "2.80V", "CAM_PWR_REQ",
     "APHD1608LCGCK candidate. Verify the full current and luminance window, supply ramps and fault latching.", "BLOCKED"),
    ("M-MAIN-L", "U6_CAM_DOVDD", "4", "3V3_SYS", "1", "CAM_DOVDD_1V8",
     "1.80V candidate", "PRIV_WINDOW_OK_F",
     "Camera module, vendor power sequencing and partial-power IO are open", "BLOCKED"),
    ("M-MAIN-L", "U6_CAM_DVDD", "4", "3V3_SYS", "1", "CAM_DVDD_1V2",
     "1.20V candidate", "PRIV_WINDOW_OK_F",
     "Camera module, vendor power sequencing and partial-power IO are open", "BLOCKED"),
    ("M-MAIN-L", "U6_CAM_AVDD", "4", "3V3_SYS", "1", "CAM_AVDD_2V8",
     "2.80V candidate", "PRIV_WINDOW_OK_F",
     "Camera module, vendor power sequencing and partial-power IO are open", "BLOCKED"),
)


def read_table(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def encoded_table(fields, rows):
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return result.getvalue().encode("utf-8")


def update_row(row, **values):
    row.update(values)
    return row


def terminal(ref, pin, net, voltage, function, bom, role="PASSIVE", note="", board=BRIDGE):
    return {
        "Net": net, "Domain_V": voltage, "Board": board, "RefDes": ref,
        "Pin": pin, "Pin_Function": function, "Role": role, "BOM_Line": bom,
        "I_Peak_A": "", "Note": note,
    }


def apply_overlay(netlist, bom_fields, bom):
    by_part = {row["Item_ID"]: row for row in bom}
    for row in netlist:
        ref = row["RefDes"]
        if row["Net"] == "AVDD_OPT_BIAS":
            row.update(
                Domain_V=AVDD_BLOCK, I_Peak_A="",
                Note="Board-side candidate only. JBD voltage, load, capacitance and sequencing remain BLK-JBD-04.",
            )
        if ref in DQN | DSG and row["Pin"] == "EP":
            assert row["Net"] == "GND", row
            row.update(Pin="5" if ref in DQN else "9", Pin_Function="EP_GND")
        if ref == "U4_1V8F" and row["Pin"] == "3":
            row.update(Domain_V="1.2", Note=FPGA_SEQUENCE_BLOCK)
        if ref == "U3_L" and row["Pin"] == "C2":
            row.update(Note="1uF at BAT. " + LEFT_BATTERY_POR)
        if ref == "U4_1V2" and row["Pin"] == "3":
            row.update(Domain_V="4.4", Note="EN is tied to VSYS. 4.4 V is the nominal input contract, not a rail limit.")
        if ref == "U6_OPT_AVDD" and row["Pin"] in {"2", "4"}:
            row.update(Note="Output requirement and fitted regulator are BLK-JBD-04.")
        if ref in {"J_BTB_L", "J_BRIDGE_IN"} and row["Net"] == "VSYS":
            row.update(Note="0.45 A is the total VSYS branch peak across P2/P3, not per contact. Sharing and derating remain unverified.")
        if row["Net"] == "PRIV_WINDOW_OK_F":
            row.update(Domain_V="3.3", Note="Analog node in 3V3_SYS domain. High is derived from V_INA_OUT through R_PRIV_PU/R_PRIV_RC.")
        if ref == "J_CHG" and row["Net"] == "VBUS_5V":
            row.update(I_Peak_A="", Note=DOCK_SOURCE_BLOCK)
        if ref in OPTICAL_DNP_PINS and row["Pin"] == OPTICAL_DNP_PINS[ref]:
            row.update(
                Pin_Function=row["Pin_Function"] + " (DNP)",
                Note=row["Note"] + " Default engineering assembly DNP. Optical variant BLOCKED.",
            )
        if ref == "L2_1V8":
            row["Note"] = (
                "Candidate Murata DFE21CCN2R2MELL. Vendor 2012 land geometry; "
                "effective L across current/temperature and assembly clearance open."
            )
        if ref == "D3_PRIV":
            row["Note"] = (
                "APHD1608LCGCK green AlGaInP candidate; current window, visibility and lens alignment BLOCKED pending qualification."
            )
        if ref == "Y1_OSC":
            row["Pin_Function"] = {"1": "TRISTATE", "3": "OUT", "4": "VDD"}[row["Pin"]]
        if ref in {"R_PLL", "R_VPP"} and row["Pin"] == "2":
            row["Pin_Function"] = "100R" if ref == "R_PLL" else "10R"
            row["Note"] = "See explicit C_FPGA bypass parts on this net."

    netlist.append(terminal(
        "Y1_OSC", "2", "GND", "0", "GND", "BOM-27", "SINK",
        "Abracon ASADV mechanical drawing pin 2. Place C_FPGA_OSC_HF between pins 4 and 2.",
    ))
    by_part["BOM-27"].update(
        MPN=OSCILLATOR, Manufacturer="Abracon", Side="TBD", Center_X_mm="",
        Center_Y_mm="", Body_Width_X_mm="1.60", Body_Length_Y_mm="2.00", Unit_Mass_g="",
        Body_Height_Z_mm="0.80", Pad_Pitch_mm="",
        Package_Footprint="2016 4-pad SMD per ASADV mechanical drawing",
        Key_Electrical_Specs=(
            "48 MHz CMOS, 1.6–3.63 V, ±50 ppm, −40 to 85 °C; "
            "1 TRISTATE tied high, 2 GND, 3 OUT to U2 B3, 4 VDD at 1V8_FPGA_IO; "
            "10 nF local bypass. Source current 3.5 mA at 1.8 V/48 MHz/15 pF "
            "and 25 °C condition in series data sheet."
        ),
        Datasheet_URL=ABRACON_ASADV,
        Verification_Status="UNVERIFIED — source/pin checked; procurement, layout and clock startup open",
        Rev_D1_Change="EVT-1 native overlay replaces 5032 ASFLMB with 2016 ASADV and restores missing ground.",
    )
    by_part["BOM-33"].update(
        MPN="R_PLL(100R)+R_VPP(10R)+R_SS_PD(10k)+R_CRST_PD(10k)+R_CDONE_PU(4.7k)+10xR_DAMP(22R)+2xR_OPTCS_PU(10k)",
        Key_Electrical_Specs="FPGA configuration and damping passives. All bypass capacitors are separate explicit BOM-CAD entries.",
    )
    by_part["BOM-09"].update(
        MPN="DFE21CCN2R2MELL", Manufacturer="Murata", Body_Width_X_mm="1.20",
        Body_Length_Y_mm="2.00", Body_Height_Z_mm="0.80", Unit_Mass_g="0.013",
        Side="TBD", Center_X_mm="", Center_Y_mm="", Pad_Pitch_mm="1.60",
        Package_Footprint="2012 (0805); Murata DFE21CCN §12.1 land pattern, 0.80×1.40 mm at 1.60 mm pitch",
        Key_Electrical_Specs=(
            "2.2uH ±20%; 138mOhm max DCR; Isat 2.10A min at 30% delta L, "
            "Itemp 1.80A min at +40C rise; 0.013g vendor typical. "
            "TPS62840 effective L=1.51–2.90uH across DC bias/current and temperature required."
        ),
        Verification_Status="UNVERIFIED — candidate source checked; exact lands/layout and L at load/thermal/pulse check open",
        Datasheet_URL=MURATA_L2,
        Rev_D1_Change="Replaces undocumented DFE161212U-2R2M; clear inherited placement for larger envelope.",
    )
    by_part["BOM-20"]["Key_Electrical_Specs"] += " " + LEFT_BATTERY_POR
    by_part["BOM-06"]["Rev_C_Engineering_Notes"] = "3.30V from qualified VSYS. PMIC regulation range does not define battery-only system POR."
    by_part["BOM-25"].update(
        MPN="APHD1608LCGCK", Body_Height_Z_mm="0.65", Unit_Mass_g="",
        Package_Footprint="1608 (0603) 1.60×0.80×0.65mm dome SMT; Kingbright V.4B",
        Key_Electrical_Specs=(
            "Green 570nm AlGaInP. Vf min/typ/max=1.5/1.9/2.1V at 2mA, 25C; "
            "datasheet Vf tolerance ±0.1V. Intensity min/typ=2/8mcd at 2mA. "
            "A from trunk P19 after sense and current-limit resistors, K to bridge GND."
        ),
        Verification_Status="BLOCKED — lower-Vf candidate; guarantee current window and visible indication in mounted assembly",
        Datasheet_URL=PRIVACY_LED,
        Rev_D1_Change="Replace high-Vf green APHD1608LZGCK and dissimilar red THT alternate. Retain window and isolation topology.",
    )
    by_part["BOM-46"]["Verification_Status"] = "BLOCKED — FPGA rail-order guarantee and hardware qualification required"
    by_part["BOM-45"]["Verification_Status"] = "BLOCKED — DNP by default; BLK-JBD-04, no regulator voltage assigned"
    by_part["BOM-50"].update(
        Key_Electrical_Specs="Board-side dock candidate only. " + DOCK_SOURCE_BLOCK,
        Verification_Status="BLOCKED — dock source boundary, boot/reset draw, data modes and connector mechanics open",
    )
    by_part["BOM-51"]["Verification_Status"] = "BLOCKED — logical TVS position only; exact topology, ground return and MPN open"
    for item_id, drawing_id, contacts, width, length in BM28_RECEPTACLES:
        by_part[item_id].update(
            Center_X_mm="", Center_Y_mm="", Body_Width_X_mm=width, Body_Length_Y_mm=length,
            Body_Height_Z_mm="0.60",
            Package_Footprint=f"BM28 {contacts} receptacle, body X/Y={width}/{length}mm as oriented; 0.60mm nominal mated stack",
            Datasheet_URL=f"https://www.hirose.com/en/product/p/CL0673-{drawing_id}-0-53",
            Verification_Status="BLOCKED — source dimensions corrected; placement and mated/FPC envelope open",
        )
    for item_id in {"BOM-26", "BOM-29"}:
        by_part[item_id]["Verification_Status"] = (
            "BLOCKED — DNP by default; placement, mated envelope and JBD FPC assignment open"
        )

    for index, (ref, net, voltage, capacitance, near) in enumerate(CAPACITORS, start=1):
        bom_id = f"BOM-CAD-{index:02d}"
        bulk = capacitance == "4.7uF"
        package = "0603 (1608 metric)" if bulk else "0402 (1005 metric)"
        dielectric = "X7R" if capacitance != "10nF" else "C0G"
        nominal = f"{capacitance} 6.3V {dielectric}"
        source = ABRACON_ASADV if ref == "C_FPGA_OSC_HF" else LATTICE_CHECKLIST
        place_note = f"Place directly at {near}; shortest supply/ground loop. Bias, tolerance and actual MPN open."
        bom.append(update_row(
            dict.fromkeys(bom_fields, ""), Item_ID=bom_id, RefDes=ref, Board_Zone=BRIDGE,
            Side="TBD", Body_Width_X_mm="0.80" if bulk else "0.50",
            Body_Length_Y_mm="1.60" if bulk else "1.00",
            Body_Height_Z_mm="TBD", Category="FPGA_Decoupling",
            MPN=f"{nominal} ({package}); exact MPN TBD", Manufacturer="TBD",
            Package_Footprint=package, Key_Electrical_Specs=place_note,
            Qty="1", Unit_Mass_g="", Verification_Status="UNVERIFIED — value/connection reviewed; exact MPN, DC bias and fit open",
            Datasheet_URL=source, Rev_D1_Change="Native schematic overlay adds explicit capacitor terminals.",
        ))
        netlist.extend([
            terminal(ref, "1", net, voltage, nominal, bom_id, note=place_note),
            terminal(ref, "2", "GND", "0", nominal, bom_id, note=place_note),
        ])

    # Keep the external speaker as a load and add the missing board-side terminations.
    for eye, (board, voltage) in SPEAKER_ZONES.items():
        for phase in ("P", "N"):
            net = f"SPK_{eye}_{phase}"
            ref = f"TP_{net}"
            bom_id = f"BOM-CAD-{ref}"
            note = "On-board speaker lead termination per BOM-52. Floating class-D BTL; never tie to ground."
            bom.append(update_row(
                dict.fromkeys(bom_fields, ""), Item_ID=bom_id, RefDes=ref, Board_Zone=board,
                Side="TBD", Category="Speaker_Wire_Solder_Pad", MPN="PCB copper pad",
                Package_Footprint="1-pin wire solder pad; wire gauge and strain relief TBD",
                Key_Electrical_Specs=note, Qty="1",
                Verification_Status="UNVERIFIED — pad geometry, wire gauge and strain relief open",
                Rev_D1_Change="Adds the explicit board-side terminal for the existing speaker lead.",
            ))
            netlist.append(terminal(ref, "1", net, voltage, "SPK_LEAD_PAD", bom_id, note=note, board=board))


def validate(netlist, bom):
    terminals = {(r["Board"], r["RefDes"], r["Pin"]): r for r in netlist}
    ids = {r["Item_ID"] for r in bom}
    assert len(terminals) == len(netlist), "Duplicate terminal"
    assert len(ids) == len(bom), "Duplicate BOM item"
    assert {r["BOM_Line"] for r in netlist} <= ids, "Pin with missing BOM item"
    for ref, net, voltage, _, _ in CAPACITORS:
        assert terminals[BRIDGE, ref, "1"]["Net"] == net
        assert terminals[BRIDGE, ref, "1"]["Domain_V"] == voltage
        assert terminals[BRIDGE, ref, "2"]["Net"] == "GND"
    for pin, net in {"1": "1V8_FPGA_IO", "2": "GND", "3": "clk_48m", "4": "1V8_FPGA_IO"}.items():
        assert terminals[BRIDGE, "Y1_OSC", pin]["Net"] == net
    assert len([r for r in netlist if r["RefDes"] == "U2_FPGA"]) == 30
    for ref in DQN | DSG:
        pads = [r for r in netlist if r["RefDes"] == ref and r["Pin_Function"] == "EP_GND"]
        assert len(pads) == 1 and pads[0]["Pin"] == ("5" if ref in DQN else "9"), ref
        assert pads[0]["Net"] == "GND"
    for row in netlist:
        if row["Net"] == "AVDD_OPT_BIAS":
            assert row["Domain_V"] == AVDD_BLOCK and row["I_Peak_A"] == "", row
    for ref, pin in OPTICAL_DNP_PINS.items():
        row = terminals[BRIDGE, ref, pin]
        assert row["Net"] == "AVDD_OPT_BIAS" and row["Pin_Function"].endswith(" (DNP)"), row
        assert any(r["Item_ID"] == row["BOM_Line"] and r["Verification_Status"].startswith("BLOCKED — DNP") for r in bom)
    for eye, (board, _) in SPEAKER_ZONES.items():
        for phase in ("P", "N"):
            net = f"SPK_{eye}_{phase}"
            assert terminals[board, f"TP_{net}", "1"]["Net"] == net
            assert terminals[board, f"SPK_{eye}", "+" if phase == "P" else "-"]["Net"] == net
            assert terminals[board, f"U10_AMP_{eye}", "A3" if phase == "P" else "B3"]["Net"] == net
    for board, ref, in_pin, in_net, out_pin, out_net, _, _, _, _ in POWER_TREE:
        assert terminals[board, ref, in_pin]["Net"] == in_net, (board, ref, in_pin)
        assert terminals[board, ref, out_pin]["Net"] == out_net, (board, ref, out_pin)


def build():
    net_fields, netlist = read_table(BASE / "NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv")
    bom_fields, bom = read_table(BASE / "BOM_V1_0_FROZEN.csv")
    before = {(r["Board"], r["RefDes"], r["Pin"], r["Net"]) for r in netlist}
    apply_overlay(netlist, bom_fields, bom)
    validate(netlist, bom)
    after = {(r["Board"], r["RefDes"], r["Pin"], r["Net"]) for r in netlist}
    removed = {(board, ref, pin, net) for board, ref, pin, net in before if ref in DQN | DSG and pin == "EP"}
    added = {(board, ref, "5" if ref in DQN else "9", net) for board, ref, _, net in removed}
    added |= {(BRIDGE, "Y1_OSC", "2", "GND")}
    for ref, net, _, _, _ in CAPACITORS:
        added |= {(BRIDGE, ref, "1", net), (BRIDGE, ref, "2", "GND")}
    for eye, (board, _) in SPEAKER_ZONES.items():
        for phase in ("P", "N"):
            net = f"SPK_{eye}_{phase}"
            added.add((board, f"TP_{net}", "1", net))
    assert after == before.difference(removed).union(added), "Unexpected topology or pin changes"

    pin_fields = ["Chip_Ref", "Pin_ID", "Pin_Name", "Signal_Net_Name", "Direction",
                  "Voltage_Domain", "Board", "BOM_Line", "Datasheet_Verification_Note",
                  "Native_Status"]
    pins = [dict(zip(pin_fields, [
        row["RefDes"], row["Pin"], row["Pin_Function"], row["Net"], row["Role"],
        row["Domain_V"], row["Board"], row["BOM_Line"], row["Note"],
        "BLOCKED" if row["RefDes"] in UNRESOLVED_INTERFACES or row["Net"] == "AVDD_OPT_BIAS" else "UNVERIFIED",
    ])) for row in netlist]
    return {
        "effective_netlist.csv": encoded_table(net_fields, netlist),
        "effective_bom.csv": encoded_table(bom_fields, bom),
        "effective_pinmap.csv": encoded_table(pin_fields, pins),
        "effective_power_tree.csv": encoded_table(
            POWER_FIELDS, [dict(zip(POWER_FIELDS, edge)) for edge in POWER_TREE],
        ),
    }, len(netlist), len(bom)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, pin_count, bom_count = build()
    for name, data in files.items():
        path = HERE / name
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit(f"FAIL: generated source differs from {path}")
        else:
            path.write_bytes(data)
    print(f"PASS: audited input topology {pin_count} terminals / {bom_count} BOM rows; baseline untouched")


if __name__ == "__main__":
    main()
