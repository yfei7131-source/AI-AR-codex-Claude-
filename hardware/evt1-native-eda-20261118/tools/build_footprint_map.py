#!/usr/bin/env python3
"""Generate and verify EVT-1 source-to-KiCad footprint assignments."""

import argparse
from collections import Counter, defaultdict
import csv
import io
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("Board", "RefDes", "MPN", "Footprint", "Status", "Pin_Identifiers", "Source", "Notes")
REVIEWED = "EVT1_Reviewed"
SON = "Package_SON:"
SOT = "Package_TO_SOT_SMD:"
DSG = SON + "Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm"
SUPERVISOR = SON + "WSON-6_1.5x1.5mm_P0.5mm"
PARTS = {
    "ASADV-48.000MHZ-LC-T": (REVIEWED + ":Abracon_ASADV_2016-4Pin_2.0x1.6mm",
                            "Abracon ASADV p.5 recommended copper lands: 0.88 x 0.78 mm, 1.28 x 0.98 mm center spacing, pin 1 at bottom left in top view."),
    "PCA9306DQER": (SON + "X2SON-8_1.4x1mm_P0.35mm", "TI DQE0008A. Standard land variant. Check stencil and DQE pin-1 elongation."),
    "TLV75512PDQNR": (SON + "Texas_X2SON-4_1x1mm_P0.65mm", "TI DQN0004A. Numbered ground pad 5."),
    "TLV75518PDQNR": (SON + "Texas_X2SON-4_1x1mm_P0.65mm", "TI DQN0004A. Numbered ground pad 5."),
    "TLV75528PDQNR": (SON + "Texas_X2SON-4_1x1mm_P0.65mm", "TI DQN0004A. Numbered ground pad 5."),
    "BQ25170DSGR": (DSG, "TI DSG0008A. Numbered ground pad 9."),
    "TLV7042DSGR": (DSG, "TI DSG0008A. Numbered ground pad 9."),
    "INA185A4IDRLR": (SOT + "Texas_R-PDSO-N6_DRL-6", "TI DRL-6. Confirm supplier paste and mask against DRL drawing."),
    "SN74LVC1G07DPWR": (SON + "Texas_X2SON-5_0.8x0.8mm_P0.48mm", "TI DPW0005A, including NC pad 1."),
    "SN74LVC2T45DCUR": ("Package_SO:VSSOP-8_2.3x2mm_P0.5mm", "TI DCU0008A."),
    "LTC6993IS6-2#TRPBF": (SOT + "TSOT-23-6", "ADI/Linear Technology S6."),
    "SN74LVC1G175DCKR": (SOT + "SOT-363_SC-70-6", "TI DCK0006A, SC70-6."),
    "SN74LVC2G17DCKR": (SOT + "SOT-363_SC-70-6", "TI DCK0006A, SC70-6."),
    "TPS389018DSET": (SUPERVISOR, "TI DSE0006A. Standard land variant. Confirm mask and stencil against TI drawing."),
    "TPS389025DSET": (SUPERVISOR, "TI DSE0006A. Standard land variant. Confirm mask and stencil against TI drawing."),
    "PMV65XP": (SOT + "SOT-23", "SOT23, pins 1 G / 2 S / 3 D."),
    "2N7002": (SOT + "SOT-23", "SOT23, pins 1 G / 2 S / 3 D. BOM manufacturer selection remains open."),
}
PASSIVE_SIZES = {"01005": "0402", "0201": "0603", "0402": "1005", "0603": "1608"}
# Avoid using a metric equivalent in parentheses as a second imperial candidate.
SIZE = re.compile(r"(?<![.\w])(?:01005|0201|0402|0603)(?![\w] *metric|[\w])", re.I)
COPPER_PAD = re.compile(r'\(pad\s+"([^"]+)"\s+(?:smd|thru_hole|connect)\s+\w+\s+(.*?)(?=\n\s*\(pad |\Z)', re.S)
SPECIAL_BLOCKS = {
    "ANT1": "Reconcile FEED and mechanical/other termination with exact antenna drawing and keepout geometry.",
    "ANT2_BLE": "Reconcile FEED and mechanical/other termination with exact antenna drawing and keepout geometry.",
    "D3_PRIV": "Select a single LED package and verify land orientation against named anode and cathode.",
    "D_XREQ": "Confirm exact SOD-523 land and map named A/K to physical pad numbers.",
    "J_CHG": "ID-controlled magnetic pogo connector and mating geometry are pending.",
    "U1_HOST": "Build and independently check Espressif LGA56+EP57 land pattern and EP construction.",
    "U2_FPGA": "Build and independently check Lattice UWG30 drawing, A1 orientation and actual 30-ball set.",
    "U3_L": "Build and independently check TI YBG0008-C01 geometry and indexed ball map.",
    "U4_BB": "Build and independently check TI YFF0015 land geometry and ball orientation.",
    "U9_IMU": "Check DS-000347 numbered land and orientation against assembly axes and board flex/stress constraints.",
    "U11_BLE": "Build and independently check Nordic CMAA 95-ball land and escape, including unpopulated sites.",
    "U12_ESD_USB": "Freeze TVS MPN, package, standoff and capacitance with J_CHG and VBUS requirements.",
    "U6_OPT_AVDD": "BLK-JBD-04. Voltage, regulator and optical load/sequence are open. Leave footprint blank.",
    "C_LDO_OPT_OUT": "BLK-JBD-04. Output capacitance depends on approved AVDD voltage, load and bias.",
    "Y2_BLE": "FA-128 ordering suffix and controlled frequency tolerance/ESR/load selection remain open.",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def passive_candidate(ref, terminals, bom):
    if {row["Pin"] for row in terminals} != {"1", "2"}:
        return None
    identified = re.fullmatch(r"NRF_L([1-4])", ref)
    if identified and "L1/L2=0201; L3/L4=0603 per Nordic config3" in terminals[0]["Note"]:
        return ("Inductor_SMD:L_0201_0603Metric" if identified[1] in "12" else "Inductor_SMD:L_0603_1608Metric",
                "Nordic config 3 nominal body class. Freeze exact series and Q/DCR/current derating.")
    if not re.match(r"^[CR]_", ref):
        return None
    body_description = re.sub(r"\([^()]*\)", "", bom["Package_Footprint"])
    package_sizes = set(SIZE.findall(body_description))
    terminal_sizes = {size for row in terminals for size in SIZE.findall(row["Pin_Function"])}
    sizes = terminal_sizes or package_sizes
    if len(sizes) != 1 or (terminal_sizes and package_sizes and not terminal_sizes <= package_sizes):
        return None
    imperial = next(iter(sizes))
    family = "Capacitor" if ref.startswith("C_") else "Resistor"
    return (f"{family}_SMD:{ref[0]}_{imperial}_{PASSIVE_SIZES[imperial]}Metric",
            f"Explicit {imperial} two-terminal body class. Exact MPN, electrical derating and assembly remain open.")


def decide(board, ref, terminals, part):
    if board == "CAM_MODULE":
        return "", "BLOCKED", "External camera module. Obtain exact sensor/FPC pinout and power-up requirements."
    if ref.startswith("J_DISP_"):
        return "", "BLOCKED", "BLK-JBD-01/04. Freeze vendor FPC mapping and mating orientation before assigning any footprint."
    if ref in SPECIAL_BLOCKS:
        return "", "BLOCKED", SPECIAL_BLOCKS[ref]
    candidate = PARTS.get(part["MPN"]) or passive_candidate(ref, terminals, part)
    if candidate:
        return candidate[0], "PASS", candidate[1]
    if ref.startswith("J_"):
        return "", "BLOCKED", "Check manufacturer drawing, pin-1 convention, power contacts and opposing mated view."
    if ref.startswith("BAT_"):
        return "", "BLOCKED", "Freeze protected pack, NTC return, pack contacts and ID-approved strain relief."
    if ref.startswith("SPK_"):
        return "", "BLOCKED", "Freeze speaker and wire/land mechanics. Preserve floating BTL connection."
    if ref.startswith("TP_SPK_"):
        return "", "BLOCKED", "Speaker solder land. Wire gauge, strain relief and assembly pad geometry are pending."
    if ref.startswith("TP_"):
        return "", "BLOCKED", "Probe fixture coordinates, access and loading remain open."
    return "", "BLOCKED", "Exact individual land pattern and package selection remain open."


def library_pads(libraries, footprint):
    library, name = footprint.split(":")
    root = ROOT / "footprints" if library == REVIEWED else libraries
    path = root / f"{library}.pretty" / f"{name}.kicad_mod"
    source = path.read_text(encoding="utf-8")
    return {pin for pin, item in COPPER_PAD.findall(source) if pin and
            re.search(r'\(layers[^\r\n]*"(?:F|B|\*)\.Cu"', item)}


def mapping(netlist, bom, libraries):
    parts = {row["Item_ID"]: row for row in bom}
    by_ref = defaultdict(list)
    for row in netlist:
        by_ref[row["Board"], row["RefDes"]].append(row)

    rows = []
    for (board, ref), terminals in sorted(by_ref.items()):
        pins = {row["Pin"] for row in terminals}
        bom_ids = {row["BOM_Line"] for row in terminals}
        if len(pins) != len(terminals) or len(bom_ids) != 1:
            raise ValueError(f"{board}/{ref}: duplicate pins or ambiguous BOM line {bom_ids}")
        part = parts[next(iter(bom_ids))]
        footprint, status, note = decide(board, ref, terminals, part)
        if footprint:
            physical_pads = library_pads(libraries, footprint)
            if physical_pads != pins:
                reason = f"FAIL: {board}/{ref} {footprint}: schematic {sorted(pins)} vs copper {sorted(physical_pads)}"
                raise ValueError(reason)
        source = part["Datasheet_URL"]
        if not source.startswith("https://"):
            source = f"Inputs/effective_bom.csv {part['Item_ID']}; Inputs/effective_netlist.csv {board}/{ref}"
        elif ref.startswith(("C_", "R_")):
            source = f"Inputs/effective_bom.csv {part['Item_ID']}; {source}"
        rows.append(dict(zip(
            FIELDS, (board, ref, part["MPN"], footprint, status, " ".join(sorted(pins)),
                     source, note)
        )))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libraries", required=True, type=Path, help="KiCad standard footprints directory")
    parser.add_argument("--netlist", type=Path, default=ROOT / "Inputs" / "effective_netlist.csv")
    parser.add_argument("--bom", type=Path, default=ROOT / "Inputs" / "effective_bom.csv")
    parser.add_argument("--check", action="store_true", help="Verify committed output without rewriting")
    args = parser.parse_args()
    rows = mapping(read_csv(args.netlist), read_csv(args.bom), args.libraries)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode("utf-8")
    output = ROOT / "FOOTPRINT_MAP.csv"
    if args.check:
        if not output.exists() or output.read_bytes() != data:
            raise SystemExit("FAIL: FOOTPRINT_MAP.csv differs from audited input")
    else:
        output.write_bytes(data)
    for board, counts in sorted(grouped_counts(rows).items()):
        print(f"{board} | mapped and pad-checked PASS={counts['PASS']}, BLOCKED={counts['BLOCKED']}")
    print("PASS: exact populated copper-pad identifiers and complete source-instance coverage.")


def grouped_counts(rows):
    counts = defaultdict(Counter)
    for row in rows:
        counts[row["Board"]][row["Status"]] += 1
    return counts


if __name__ == "__main__":
    main()
