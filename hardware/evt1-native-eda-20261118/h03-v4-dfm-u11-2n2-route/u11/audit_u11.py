#!/usr/bin/env python3
"""Reproduce the 95-ball Nordic Config 3 audit from PR #46 and the V4 PCB readbacks."""

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
V4 = HERE.parent
EVT1 = V4.parent
PR46 = EVT1 / "h03-u11-wlcsp-v3-dfm-route"
sys.path.insert(0, str(EVT1 / "h02-native"))

from prepare_hierarchy import Archive, digest
from verify_h02 import parse_protel


BOARD = "M-AUD-R"
REF = "U11"
SCHEMATIC = "07dc7dde94c1bf76"
PCB = "1db01a36f669a47a"
MPN = "nRF5340-CMAA-R7"
GRID_ROWS = "ABCDEFGHJKL"
GRID_COLUMNS = 12
PIN_SOURCE = "https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html"
CONFIG_SOURCE = "https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ref_circuitry.html"
REF_ZIP_URL = "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/reference-layouts/nrf5340/nrf5340-xxaa-reference-layout-1_3.zip"
OSC_SOURCE = "https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/oscillators/doc/oscillators.html"

# Product Specification, WLCSP pin assignments Table 3. Each pair names a physical ball and
# its primary pin name. Documented alternate functions relevant to unused inputs are below.
PIN_MAP = dict(pair.split(":") for pair in """
    A1:XC1 A2:XC2 A3:VDD A5:VSS A7:DECD A9:DCCD A11:D- A12:D+
    B1:DECRF B2:VSS B4:DECR B5:DECN B6:DCC B7:VDD B8:DECA B9:VSS B10:VDD B11:VBUS B12:VDDH
    C2:VSS C4:P0.30 C5:P0.31 C6:P1.11 C7:P1.12 C8:P1.13 C9:P1.14 C10:P1.15 C11:DECUSB
    D1:ANT D2:VDD D10:P1.00 D11:DCCH D12:VSS
    E2:P0.29 E3:P0.28 E4:P1.10 E5:VSS E6:VSS E7:VSS E8:VSS E10:P1.01 E11:VDD
    F1:SWDIO F2:SWDCLK F3:P1.08 F5:VSS F6:VSS F7:VSS F8:VSS F10:P0.05 F11:P0.00 F12:P0.01
    G2:nRESET G3:P1.07 G5:AVSS G6:VSS G7:VSS G8:VSS G10:P0.04 G11:P0.02
    H1:P0.27 H2:P1.09 H3:P0.23 H10:P0.06 H11:VDD H12:P0.03
    J2:P0.26 J3:P1.06 J4:P0.21 J5:P0.19 J6:P0.12 J7:P0.11 J8:P0.10 J9:P0.09 J10:P0.07 J11:P1.02
    K1:VDD K2:P0.24 K3:P1.04 K4:P0.22 K5:P0.20 K6:AVSS K7:P0.18 K8:P0.16 K9:P0.14 K10:P0.13 K11:AVSS K12:P1.03
    L1:P0.25 L3:P1.05 L5:VDD L7:P0.17 L9:P0.15 L11:VDD L12:P0.08
""".split())
ALIASES = {
    "E3": "AIN7", "F10": "AIN1", "F11": "XL1", "F12": "XL2", "G10": "AIN0", "G11": "NFC1",
    "H1": "AIN6", "H10": "AIN2", "H12": "NFC2", "J2": "AIN5", "J6": "TRACECLK;SPIM4.DCX",
    "J7": "TRACEDATA0;SPIM4.CSN", "J8": "TRACEDATA1;SPIM4.MISO", "J9": "TRACEDATA2;SPIM4.MOSI",
    "J10": "AIN3", "J11": "TWI_1MBPS", "K7": "QSPI.CSN", "K8": "QSPI.IO3", "K9": "QSPI.IO1",
    "K10": "QSPI.IO0", "K12": "TWI_1MBPS", "L1": "AIN4", "L7": "QSPI.SCK", "L9": "QSPI.IO2",
    "L12": "TRACEDATA3;SPIM4.SCK",
}
FUNCTIONS = {
    "VSS": ("GROUND", "GND", "Connect every ground ball to the local continuous GND reference."),
    "AVSS": ("ANALOG_GROUND", "GND", "Connect to GND. Preserve short return for analog and RF."),
    "VDD": ("NORMAL_SUPPLY", "1V8_SYS", "All VDD inputs and VDDH share the external VDD rail."),
    "VDDH": ("NORMAL_SUPPLY", "1V8_SYS", "Tie to VDD for normal-voltage mode. VREGH inactive."),
    "VBUS": ("USB_DISABLED_TIE", "GND", "Ground B11 for the selected no-USB reference circuit."),
    "D-": ("USB_DISABLED_NC", "", "Leave USB data open; this remains a physical solder ball."),
    "D+": ("USB_DISABLED_NC", "", "Leave USB data open; this remains a physical solder ball."),
    "DECUSB": ("USB_DISABLED_NC", "", "Leave USB regulator decoupling pin open in Config 3."),
    "DCCH": ("VREGH_DISABLED_NC", "", "Leave high-voltage regulator switch node open in Config 3."),
    "DECD": ("DCDC_FILTER", "NRF_DECD", "L4 from DCCD, Nordic C5 1.0 uF to GND (EVT C11)."),
    "DCCD": ("DCDC_SWITCH", "NRF_DCCD", "Short switch-node path to Nordic/EVT L4 10 uH; no unrelated loads."),
    "DECRF": ("DCDC_FILTER_RF", "NRF_DECR_RF", "Share DECR with Nordic C3 1.0 uF and C4 2.2 nF (EVT C9/C10)."),
    "DECR": ("DCDC_FILTER_RF", "NRF_DECR_RF", "Return L3 from DCC. Shared node with DECRF and local C3/C4."),
    "DECN": ("REG_DECAP", "NRF_DECN", "Nordic C6 100 nF to GND (EVT C12), short loop."),
    "DCC": ("DCDC_SWITCH", "NRF_DCC", "Nordic/EVT L3 10 uH to DECR/DECRF; short switch-node loop."),
    "DECA": ("REG_DECAP", "NRF_DECA", "Nordic C7 1.0 uF to GND (EVT C13), short loop."),
    "XC1": ("HFXO_FIXED", "BLE_XC1", "Dedicated 32 MHz crystal terminal Y2. Keep short and quiet."),
    "XC2": ("HFXO_FIXED", "BLE_XC2", "Dedicated 32 MHz crystal terminal Y2. Keep short and quiet."),
    "ANT": ("RF_FIXED", "BLE_RF_ANT", "Keep reference L1/C1/L2 RF matching; VNA/OTA still pending."),
    "SWDIO": ("DEBUG_FIXED", "BLE_SWDIO", "Dedicated SWD data to fixture TP6-1."),
    "SWDCLK": ("DEBUG_FIXED", "BLE_SWDCLK", "Dedicated SWD clock to fixture TP6-2."),
    "nRESET": ("RESET_FIXED", "BLE_NRESET", "Dedicated active-low reset to fixture TP6-3; internal pull-up."),
}
ECO08 = {
    "F11": ("LFXO_FIXED_WHEN_USED", "LFXO_XL1", "ECO-08 crystal Y3-1 and 12 pF C22 to GND."),
    "F12": ("LFXO_FIXED_WHEN_USED", "LFXO_XL2", "ECO-08 crystal Y3-2 and 12 pF C23 to GND."),
}
APPLICATION = {
    "J4": ("I2S_PSEL", "I2S_AMP_DIN_1V8", "I2S SDOUT"),
    "J5": ("I2S_PSEL", "I2S_S3_DOUT_1V8", "I2S SDIN"),
    "K2": ("GPIO", "AMP_SD_REQ_1V8", "Amplifier shutdown request GPIO"),
    "K3": ("UARTE_PSEL", "IPC_NRF_TX_1V8", "UARTE TXD"),
    "K4": ("I2S_PSEL", "I2S_LRCLK_1V8", "I2S LRCK"),
    "K5": ("I2S_PSEL", "I2S_BCLK_1V8", "I2S SCK"),
    "L3": ("UARTE_PSEL", "IPC_S3_TX_1V8", "UARTE RXD"),
}
SUPPORT = {
    "C7": ("C1", "0.7 pF", "BLE_RF_MID", "GND"),
    "C8": ("C2", "1.0 uF", "1V8_SYS", "GND"),
    "C9": ("C3", "1.0 uF", "NRF_DECR_RF", "GND"),
    "C10": ("C4", "2.2 nF", "NRF_DECR_RF", "GND"),
    "C11": ("C5", "1.0 uF", "NRF_DECD", "GND"),
    "C12": ("C6", "100 nF", "NRF_DECN", "GND"),
    "C13": ("C7", "1.0 uF", "NRF_DECA", "GND"),
    "C14": ("C8", "100 nF", "1V8_SYS", "GND"),
    "C15": ("C9", "100 nF", "1V8_SYS", "GND"),
    "C16": ("C10", "1.0 uF", "1V8_SYS", "GND"),
    "C17": ("C11", "100 nF", "1V8_SYS", "GND"),
    "C18": ("C12", "100 nF", "1V8_SYS", "GND"),
    "C19": ("C13", "100 nF", "1V8_SYS", "GND"),
    "C20": ("C14", "1.0 uF", "1V8_SYS", "GND"),
    "C21": ("C19", "DNP", "BLE_ANT_FEED", "GND"),
    "L1": ("L1", "2.2 nH", "BLE_RF_MID", "BLE_RF_ANT"),
    "L2": ("L2", "2.2 nH", "BLE_ANT_FEED", "BLE_RF_MID"),
    "L3": ("L3", "10 uH", "NRF_DECR_RF", "NRF_DCC"),
    "L4": ("L4", "10 uH", "NRF_DECD", "NRF_DCCD"),
    "Y2": ("X1", "32 MHz", "BLE_XC1", "GND", "BLE_XC2", "GND"),
    "Y3": ("X2", "32.768kHz", "LFXO_XL1", "LFXO_XL2"),
    "C22": ("ECO-08", "12pF", "LFXO_XL1", "GND"),
    "C23": ("ECO-08", "12pF", "LFXO_XL2", "GND"),
    "TP6": ("debug interface", "", "BLE_SWDIO", "BLE_SWDCLK", "BLE_NRESET", "1V8_SYS", "GND"),
}
PITCH_MM = 0.350
CLEARANCE_MM = 0.1524
LASER_DRILL_MM = 0.075
MIN_RING_MM = 0.0762


def table(path):
    return json.loads(path.read_bytes())


def symbol_inventory(archive):
    attrs = defaultdict(dict)
    page = archive.documents["SCH_PAGE", SCHEMATIC]
    for record in page.records:
        if record.header["type"] == "ATTR":
            attrs[record.payload["parentId"]][record.payload["key"]] = record.payload["value"]
    parts = {row["Designator"]: (primitive, row) for primitive, row in attrs.items() if row.get("Designator")}
    primitive, u11 = parts[REF]
    symbol = archive.documents["SYMBOL", u11["Symbol"]]
    if u11.get("Manufacturer Part") != MPN:
        raise ValueError("Unexpected manufacturer part in U11")
    numbers = {record.payload["parentId"]: record.payload["value"] for record in symbol.records
               if record.header["type"] == "ATTR" and record.payload["key"] == "Pin Number"}
    names = {record.payload["parentId"]: record.payload["value"] for record in symbol.records
             if record.header["type"] == "ATTR" and record.payload["key"] == "Pin Name"}
    prefix = f"{primitive}-"
    marked = [id_.removeprefix(prefix) for id_, row in attrs.items()
              if id_.startswith(prefix) and row.get("NO_CONNECT") == "yes"]
    if len(numbers) != 95 or len(set(numbers.values())) != 95 or set(numbers) != set(names):
        raise ValueError("Native SCH pin names/numbers do not form a 95-ball inventory")
    return u11, {number: names[id_] for id_, number in numbers.items()}, {numbers[id_] for id_ in marked}, parts


def net_inventory(path):
    _, groups = parse_protel(path.read_text(encoding="utf-8-sig"))
    nets = {}
    for net, nodes in groups:
        for node in nodes:
            if node in nets:
                raise ValueError(f"Duplicate Protel2 terminal {node}")
            nets[node] = net
    return nets


def contract(ball, name):
    if ball in APPLICATION:
        kind, net, function = APPLICATION[ball]
        return kind, net, f"{function}; design pin assignment retained; separate board/firmware ECO required."
    if ball in ECO08:
        return ECO08[ball]
    if name in FUNCTIONS:
        return FUNCTIONS[name]
    requirement = "Unused GPIO in the current design; no route, disable input and pulls when appropriate."
    if ball in {"G11", "H12"}:
        requirement = "NFC unused in Config 3; no antenna circuit. Preserve the existing open state."
    if not name.startswith(("P0.", "P1.")):
        raise ValueError(f"Unhandled official pin function {ball} {name}")
    return "UNUSED_GPIO", "", requirement


def position(ball):
    return GRID_ROWS.index(ball[0]), int(ball[1:]) - 1


def clearance(ball, footprint_pad_diameter):
    row, column = position(ball)
    _, net, _ = contract(ball, PIN_MAP[ball])
    if not net:
        return "", ""
    outsiders = []
    for neighbor, pin in PIN_MAP.items():
        _, other_net, _ = contract(neighbor, pin)
        if other_net == net:
            continue
        r, c = position(neighbor)
        outsiders.append((PITCH_MM * math.hypot(row - r, column - c), neighbor))
    distance, nearest = min(outsiders)
    via_diameter = LASER_DRILL_MM + 2 * MIN_RING_MM
    return nearest, round(distance - (via_diameter + footprint_pad_diameter) / 2, 5)


def support_inventory(parts, nets):
    result = []
    for designator, (vendor_ref, value, *expected) in SUPPORT.items():
        _, native = parts[designator]
        actual = [nets.get((designator, str(pin)), "") for pin in range(1, len(expected) + 1)]
        native_value = native.get("Value", "")
        if actual != expected or value.casefold() not in native_value.casefold():
            raise ValueError(f"Config 3 support circuit differs: {designator} {actual} {native_value}")
        if designator == "C21" and native.get("Add into BOM") != "no":
            raise ValueError("DNP RF shunt C21 has been returned to the schematic BOM")
        result.append({"reference_ref": vendor_ref, "board_ref": designator, "board_value": native_value,
                       "ordered_pin_nets": actual, "native_add_into_bom": native.get("Add into BOM")})
    return result


def audit(archive_path, dump_path, net_path):
    archive = Archive(archive_path)
    u11, names, nc, parts = symbol_inventory(archive)
    dump = table(dump_path)
    if not dump["capture"]["identityVerified"] or dump["capture"]["documentUuid"] != PCB:
        raise ValueError("Expected identity-verified PCB3 readback")
    component, = [c for c in dump["components"] if c["designator"] == REF]
    if (component["uniqueId"], component["layer"], component["rotation"]) != (u11["Unique ID"], 1, 90):
        raise ValueError("PCB identity, side or orientation drift")
    pads = {pad["padNumber"]: pad for pad in component["pads"]}
    if len(pads) != len(component["pads"]) or set(pads) != set(names) or set(pads) != set(PIN_MAP):
        raise ValueError("Nordic, SCH and PCB physical ball inventories differ")
    pcb = archive.documents["PCB", PCB]
    footprint_uuid, = [r.payload["value"] for r in pcb.records if r.header["type"] == "ATTR"
                       and r.payload["parentId"] == component["primitiveId"] and r.payload["key"] == "Footprint"]
    footprint = archive.documents["FOOTPRINT", footprint_uuid]
    lands = {r.payload["num"]: r.payload for r in footprint.records if r.header["type"] == "PAD"}
    if set(lands) != set(PIN_MAP):
        raise ValueError("Archived footprint does not contain all 95 balls")
    diameters = {r["defaultPad"]["width"] for r in lands.values()
                 if r["defaultPad"]["padType"] == "ELLIPSE" and r["defaultPad"]["width"] == r["defaultPad"]["height"]}
    diameter, = diameters
    diameter_mm = round(diameter * 0.0254, 3)
    if not all(r["defaultPad"]["width"] == r["defaultPad"]["height"] == diameter
               and r["defaultPad"]["padType"] == "ELLIPSE" for r in lands.values()):
        raise ValueError("Mixed or unexpected archived U11 land geometry")
    if diameter_mm != 0.195:
        raise ValueError("U11 land diameter no longer agrees with the audited geometry")
    nets = net_inventory(net_path)
    pr46_net = PR46 / "evidence/erc-3board/board-netlists/M-AUD-R.net"
    with (EVT1 / "kicad/CAD_TERMINALS.csv").open(encoding="utf-8-sig", newline="") as stream:
        rev_d = {r["Pin"]: r for r in csv.DictReader(stream) if r["Board"] == BOARD and r["CAD_Reference"] == REF}

    rows = []
    for ball, name in PIN_MAP.items():
        group, expected, requirement = contract(ball, name)
        pcb_pad = pads[ball]
        observed_net = nets.get((REF, ball), "")
        local_nc = ball in nc
        if (observed_net, pcb_pad["net"], not local_nc) != (expected, expected, bool(expected)):
            raise ValueError(f"Ball {ball}: native SCH/PCB net or explicit NC differs from contract")
        if names[ball].split("/")[0] != name or rev_d[ball]["Pin_Function"].split("/")[0] != name:
            raise ValueError(f"Ball {ball}: physical pin-function label drift")
        altered = rev_d[ball]["CAD_Net"] != observed_net
        if altered != (ball in ECO08):
            raise ValueError(f"Ball {ball}: unexpected delta against the pre-ECO CSV")
        r, c = position(ball)
        local = lands[ball]
        px = local["centerX"] * 0.0254
        py = local["centerY"] * 0.0254
        if abs(px - (c - 5.5) * PITCH_MM) > 0.0002 or abs(py - (5 - r) * PITCH_MM) > 0.0002:
            raise ValueError(f"Ball {ball}: native footprint pad is outside its vendor-labelled top-view position")
        # This capture rotation is +90 degrees; pcb dump pad centers are rounded to 0.1 mil.
        if abs(pcb_pad["x"] - (component["x"] - local["centerY"])) > 0.06 or abs(
                pcb_pad["y"] - (component["y"] + local["centerX"])) > 0.06:
            raise ValueError(f"Ball {ball}: PCB pad orientation does not match the archived land")
        if (pcb_pad["layer"] != component["layer"] or pcb_pad["shape"][0] != "ELLIPSE"
                or any(abs(pcb_pad[key] - diameter) > 0.06 for key in ("width", "height"))):
            raise ValueError(f"Ball {ball}: PCB pad shape or copper dimensions drifted")
        depth = min(r, len(GRID_ROWS) - 1 - r, c, GRID_COLUMNS - 1 - c)
        nearest, gap = clearance(ball, diameter_mm)
        rows.append({
            "ball": ball, "nordic_pin": name, "alternate_function": ALIASES.get(ball, ""),
            "config3_role": group, "expected_evt_net": expected, "rev_d_net": rev_d[ball]["CAD_Net"],
            "current_native_sch_net": observed_net, "native_sch_explicit_nc": local_nc,
            "current_native_pcb_net": pcb_pad["net"], "pcb_pad_id": pcb_pad["primitiveId"],
            "pcb_x_mil": pcb_pad["x"], "pcb_y_mil": pcb_pad["y"], "ring_depth": depth,
            "gpio_reassignment_possible_in_silicon": ball in APPLICATION,
            "change_control": "ECO-08" if altered else "current assignment",
            "nearest_foreign_or_unassigned_land_for_centered_via": nearest,
            "single_centered_via_copper_gap_mm": gap,
            "single_centered_via_top_clearance": "FAIL" if expected and gap < CLEARANCE_MM else ("PASS" if expected else "N/A"),
            "layout_requirement": requirement, "primary_source": PIN_SOURCE,
        })
    if len(rows) != 95 or len(nc) != 43:
        raise ValueError("95-ball or explicit NC total differs")
    active_rings = Counter("outer" if r["ring_depth"] == 0 else "ring1" if r["ring_depth"] == 1 else "deep"
                           for r in rows if r["expected_evt_net"])
    failed = [r["ball"] for r in rows if r["ring_depth"] and r["single_centered_via_top_clearance"] == "FAIL"]
    report = {
        "scope": "PCB3 U11 footprint and pin-level native net identities; local copper geometry is not net completion",
        "status": "95_BALL_IDENTITIES_AGREE",
        "manufacturing": "BLOCKED",
        "native_archive_sha256": digest(archive_path),
        "native_pcb3_dump_sha256": digest(dump_path),
        "native_schematic_protel2_sha256": digest(net_path),
        "pr46_schematic_protel2_sha256": digest(pr46_net),
        "unchanged_pr46_schematic_export": digest(net_path) == digest(pr46_net),
        "schematic_footprint": footprint_uuid,
        "native_footprint_description": footprint.one("META").payload.get("description"),
        "native_nrf_schematic_design_notes": u11.get("Design Notes"),
        "balls_physical": len(rows),
        "balls_connected_in_schematic": len(rows) - len(nc),
        "balls_explicit_nc_in_schematic": len(nc),
        "active_balls_by_geometric_ring": dict(active_rings),
        "role_counts": dict(sorted(Counter(r["config3_role"] for r in rows).items())),
        "retained_eco08_balls": list(ECO08),
        "pin_reassignment_requires_eco": list(APPLICATION),
        "copper_escape": {
            "nominal_pitch_mm": PITCH_MM, "archived_land_diameter_mm": diameter_mm,
            "live_dump_clearance_mil": dump["rules"]["clearanceMil"],
            "required_clearance_mm": CLEARANCE_MM,
            "trial_drill_mm": LASER_DRILL_MM, "required_radial_ring_mm": MIN_RING_MM,
            "needed_trial_via_diameter_mm": round(LASER_DRILL_MM + 2 * MIN_RING_MM, 5),
            "max_single_via_adjacent_to_nominal_foreign_land_mm": round(2 * (PITCH_MM - CLEARANCE_MM) - diameter_mm, 5),
            "max_equal_adjacent_via_diameter_mm": round(PITCH_MM - CLEARANCE_MM, 5),
            "inner_balls_failing_centered_single_via_top_clearance": failed,
            "scope": "Necessary circular-copper clearance only; treats empty-net lands as physical copper and equal-net lands as same net. Excludes mask, off-center escape, connection completeness and layer stack.",
        },
        "nordic_reference_revision": {
            "pinout": PIN_SOURCE, "manufacturer_config3": CONFIG_SOURCE, "layout_archive_url": REF_ZIP_URL,
            "layout_archive_sha256": "c6cc5cf123afa0ac2e2609b5793a3deecdfe33ecdbaaf44a4a7d0b78c065f60d",
            "config3_schematic_pdf_sha256": "efd696d6f662552371c27ef80dd3a8527e8f1c066ddee42a11c210144b5bf6ba",
            "config3_drill_report_sha256": "cf3bb275d7146e8269f11789137e01e47f639acc8629ab2175c83caac8960376",
            "config3_copper_files": ["GTL", "G1", "G2", "GBL"],
            "config3_reported_blind_drills": {"layer_pair": "Top to Mid Layer 1", "plated_count": 30, "hole_mm": 0.079},
            "config3_reported_through_drills": {"layer_pair": "Top to Bottom", "plated_count": 58, "hole_mm": 0.249},
            "oscillator": OSC_SOURCE,
        },
        "support_components": support_inventory(parts, nets),
    }
    return rows, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=V4 / "native/ZY_AIAR_EVT1_H03_3BOARD_V4_DFM_U11_2N2_MECR01_NOT_FOR_FAB.epro2")
    parser.add_argument("--pcb-dump", type=Path, default=V4 / "evidence/reimport-verify/PCB3-reimport.dump.json")
    parser.add_argument("--netlist", type=Path, default=V4 / "evidence/erc-3board/board-netlists/M-AUD-R.net")
    parser.add_argument("--output-dir", type=Path, default=HERE, help="Use a new directory for other candidates")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows, report = audit(args.archive, args.pcb_dump, args.netlist)
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    outputs = {"u11-cmaa-config3-ball-matrix.csv": text.getvalue(),
               "u11-cmaa-config3-verification.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n"}
    if not args.check:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        path = args.output_dir / name
        if args.check:
            if path.read_text(encoding="utf-8") != value:
                raise ValueError(f"Committed result drifted: {name}")
        else:
            path.write_text(value, encoding="utf-8", newline="\n")
    print(f"{len(rows)} balls checked; 52 assigned, 43 explicit NC; "
          f"{len(report['copper_escape']['inner_balls_failing_centered_single_via_top_clearance'])} "
          "inner balls fail the tested centered-via clearance; manufacturing BLOCKED")


if __name__ == "__main__":
    main()
