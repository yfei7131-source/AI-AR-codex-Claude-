#!/usr/bin/env python3
"""Build the EVT1 H02->H03 R&D native candidate archive from the PR #36 baseline.

Applies:
  - Real P0 ECO-01: U4_OR (U9) LM66200DRLR -> TPS2116DRLR (Auto-Switchover 2.5A,
    MODE=GND, PR1=GND exact 8-pin drop-in) + C_OR_OUT (C27) 1uF -> 22uF 10V X5R.
  - Real P0 ECO-02 (full-PVT corrected beyond PR #37): U5_LED2V8 (U5) TLV75528PDQNR ->
    TLV75533PDQNR (5-pin DQN0004A drop-in, <15mV dropout @ <=10mA) + R_LIMIT 150R 1% 0402
    100mW + R_SENSE 1.10R 0.1% Kelvin + R_WIN 20.0k / 56.2k / 24.9k 1%.
  - Real P1 ECO-13 (EVT1 bench candidate): L1_BB (L1) -> Murata DFE201612E-R47M=P2
    with exact Murata land pattern (a=0.8, b=2.4, c=1.6 mm).
  - 22 OEM-verified H02 native footprint bindings (all 3 PRIMARY_LAND_READY +
    all 17 PRIMARY_LAND_PENDING + U9 TPS2116DRLR + L1 DFE201612E), verified
    pad-for-pad against official manufacturer drawings with zero net/terminal/NC delta.
"""

import argparse
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]

from bind_murata_l2 import ASADV_ASSET, asset_metadata, mil, rectangle
from prepare_hierarchy import Archive, Document, Record, compact, digest
from repair_native_fields import attr_value, part_attrs

PR36_BASELINE = PACKAGE / "h02-h03-native/native/ZY_AIAR_EVT1_H02_H03_NATIVE_NOT_FOR_FAB.epro2"
PR36_BASELINE_SHA = "8d4025db711e620374155c702decab2d9b9e68bf8a7bc87cb3eeac97ca5f4586"


def fp_uuid(title: str) -> str:
    return sha256(f"EVT1-reviewed/{title}".encode("utf-8")).hexdigest()[:16]


# 8 new OEM-reviewed footprints created from official manufacturer land patterns (mm).
# Format: title -> {designator, desc, tags, outline(w,h), body(w,h), pads: [(num, x, y, w, h), ...]}
NEW_FOOTPRINTS = {
    "TI_DCK0006A_SC70-6": {
        "designator": "U?",
        "desc": "TI DCK0006A SC-70-6 land pattern (PR #36 ti-dck0006a.geometry.json). https://www.ti.com/lit/ml/mpds148h/mpds148h.pdf",
        "tags": ["SC-70-6", "DCK0006A"],
        "outline": (1.60, 1.35),
        "body": (0.625, 1.00),
        "pads": [
            ("1", -1.10, 0.65, 0.90, 0.40),
            ("2", -1.10, 0.00, 0.90, 0.40),
            ("3", -1.10, -0.65, 0.90, 0.40),
            ("4", 1.10, -0.65, 0.90, 0.40),
            ("5", 1.10, 0.00, 0.90, 0.40),
            ("6", 1.10, 0.65, 0.90, 0.40),
        ],
    },
    "ADI_TSOT23_6_S6": {
        "designator": "U?",
        "desc": "ADI/LTC TSOT-23-6 S6 land pattern (PR #36 adi-ltc-s6.geometry.json). https://www.analog.com/media/en/technical-documentation/data-sheets/69931234fc.pdf",
        "tags": ["TSOT-23-6", "S6"],
        "outline": (2.00, 1.80),
        "body": (0.80, 1.45),
        "pads": [
            ("1", -1.31, 0.95, 1.22, 0.62),
            ("2", -1.31, 0.00, 1.22, 0.62),
            ("3", -1.31, -0.95, 1.22, 0.62),
            ("4", 1.31, -0.95, 1.22, 0.62),
            ("5", 1.31, 0.00, 1.22, 0.62),
            ("6", 1.31, 0.95, 1.22, 0.62),
        ],
    },
    "TI_DSE0006A_WSON-6_1.5x1.5mm": {
        "designator": "U?",
        "desc": "TI DSE0006A WSON-6 1.5x1.5mm P0.50mm land pattern (TPS3890 datasheet). https://www.ti.com/lit/ds/symlink/tps3890.pdf",
        "tags": ["WSON-6", "DSE0006A"],
        "outline": (1.15, 0.95),
        "body": (0.75, 0.75),
        "pads": [
            ("1", -0.60, 0.50, 0.70, 0.25),
            ("2", -0.60, 0.00, 0.70, 0.25),
            ("3", -0.60, -0.50, 0.70, 0.25),
            ("4", 0.60, -0.50, 0.70, 0.25),
            ("5", 0.60, 0.00, 0.70, 0.25),
            ("6", 0.60, 0.50, 0.70, 0.25),
        ],
    },
    "TI_DCU0008A_VSSOP-8_2.3x2.0mm": {
        "designator": "U?",
        "desc": "TI DCU0008A VSSOP-8 2.3x2.0mm P0.50mm land pattern (SN74LVC2T45 datasheet). https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf",
        "tags": ["VSSOP-8", "DCU0008A"],
        "outline": (2.15, 1.25),
        "body": (1.15, 1.00),
        "pads": [
            ("1", -1.55, 0.75, 0.85, 0.30),
            ("2", -1.55, 0.25, 0.85, 0.30),
            ("3", -1.55, -0.25, 0.85, 0.30),
            ("4", -1.55, -0.75, 0.85, 0.30),
            ("5", 1.55, -0.75, 0.85, 0.30),
            ("6", 1.55, -0.25, 0.85, 0.30),
            ("7", 1.55, 0.25, 0.85, 0.30),
            ("8", 1.55, 0.75, 0.85, 0.30),
        ],
    },
    "TI_DRL0006A_SOT-563-6_1.6x1.2mm": {
        "designator": "U?",
        "desc": "TI DRL0006A SOT-563-6 1.6x1.2mm P0.50mm land pattern (Drawing 4223266, INA185). https://www.ti.com/lit/ds/symlink/ina185.pdf",
        "tags": ["SOT-563-6", "DRL0006A"],
        "outline": (1.00, 1.25),
        "body": (0.80, 0.60),
        "pads": [
            ("1", -0.50, -0.74, 0.30, 0.67),
            ("2", 0.00, -0.74, 0.30, 0.67),
            ("3", 0.50, -0.74, 0.30, 0.67),
            ("4", 0.50, 0.74, 0.30, 0.67),
            ("5", 0.00, 0.74, 0.30, 0.67),
            ("6", -0.50, 0.74, 0.30, 0.67),
        ],
    },
    "TI_DRL0008A_SOT-583-8_2.1x1.2mm": {
        "designator": "U?",
        "desc": "TI DRL0008A SOT-583-8 2.1x1.2mm P0.50mm land pattern (Drawing 4224486, TPS2116). https://www.ti.com/lit/ds/symlink/tps2116.pdf",
        "tags": ["SOT-583-8", "DRL0008A"],
        "outline": (1.25, 1.25),
        "body": (1.05, 0.60),
        "pads": [
            ("1", -0.75, -0.74, 0.30, 0.67),
            ("2", -0.25, -0.74, 0.30, 0.67),
            ("3", 0.25, -0.74, 0.30, 0.67),
            ("4", 0.75, -0.74, 0.30, 0.67),
            ("5", 0.75, 0.74, 0.30, 0.67),
            ("6", 0.25, 0.74, 0.30, 0.67),
            ("7", -0.25, 0.74, 0.30, 0.67),
            ("8", -0.75, 0.74, 0.30, 0.67),
        ],
    },
    "Nexperia_SOT23_TO-236AB": {
        "designator": "Q?",
        "desc": "Nexperia SOT23 (TO-236AB) reflow land pattern (PMV65XP datasheet). https://assets.nexperia.com/documents/data-sheet/PMV65XP.pdf",
        "tags": ["SOT-23", "TO-236AB"],
        "outline": (1.65, 1.70),
        "body": (1.45, 0.65),
        "pads": [
            ("1", -0.95, -1.00, 0.80, 1.00),
            ("2", 0.95, -1.00, 0.80, 1.00),
            ("3", 0.00, 1.00, 0.80, 1.00),
        ],
    },
    "Murata_DFE201612E_2016_2.0x1.6mm": {
        "designator": "L?",
        "desc": "Murata DFE201612E-R47M=P2 recommended land pattern (a=0.8, b=2.4, c=1.6 mm). https://www.murata.com/en-us/products/productdetail?partno=DFE201612E-R47M%3DP2",
        "tags": ["2016", "DFE201612E"],
        "outline": (1.40, 1.00),
        "body": (1.00, 0.80),
        "pads": [
            ("1", -0.80, 0.00, 0.80, 1.60),
            ("2", 0.80, 0.00, 0.80, 1.60),
        ],
    },
}

# 4 OEM-audited embedded native footprints already inside PR #36 .epro2
AUDITED_EMBEDDED_FOOTPRINTS = {
    "TI_DSG0008A": ("500cb0da72c86ae0", "WSON-8_L2.0-W2.0-P0.50-TL-EP", ["1", "2", "3", "4", "5", "6", "7", "8", "9"]),
    "TI_DQN0004A": ("7fc3ca1940b32b12", "X2SON-4_L1.0-W1.0-P0.65-TL-EP", ["1", "2", "3", "4", "5"]),
    "TI_DQE0008A": ("92b62afaf009333a", "X2SON-8_L1.4-W1.0-P0.35-BL", ["1", "2", "3", "4", "5", "6", "7", "8"]),
    "TI_DPW0005A": ("2f8d631073922488", "X2SON-5_L0.8-W0.8-P0.48-BL-EP", ["1", "2", "3", "4", "5"]),
}

# 22 OEM-verified footprint bindings: (board, sourceRef, cadRef, fp_key_or_title, expected_pins)
FOOTPRINT_BINDINGS = [
    # M-OPT-BRIDGE (9 bindings — clears ALL PRIMARY_LAND_READY + PRIMARY_LAND_PENDING on bridge!)
    ("M-OPT-BRIDGE", "U_AVDD_QUAL", "U10", "NEW:TI_DCK0006A_SC70-6", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_SCHMITT", "U11", "NEW:TI_DCK0006A_SC70-6", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_WD", "U14", "NEW:ADI_TSOT23_6_S6", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_IO_PG", "U7", "NEW:TI_DSE0006A_WSON-6_1.5x1.5mm", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_SYS_CLAMP", "U12", "NEW:TI_DSE0006A_WSON-6_1.5x1.5mm", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_SYS_PG", "U13", "NEW:TI_DSE0006A_WSON-6_1.5x1.5mm", ["1", "2", "3", "4", "5", "6"]),
    ("M-OPT-BRIDGE", "U_AVDD_LS", "U8", "NEW:TI_DCU0008A_VSSOP-8_2.3x2.0mm", ["1", "2", "3", "4", "5", "6", "7", "8"]),
    ("M-OPT-BRIDGE", "U4_1V8F", "U1", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    ("M-OPT-BRIDGE", "U4_1V2", "U4", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    # M-MAIN-L (12 bindings — clears ALL PRIMARY_LAND_PENDING + ECO-01 U9 + ECO-13 L1!)
    ("M-MAIN-L", "U4_OR", "U9", "NEW:TI_DRL0008A_SOT-583-8_2.1x1.2mm", ["1", "2", "3", "4", "5", "6", "7", "8"]),
    ("M-MAIN-L", "U7_INA", "U7", "NEW:TI_DRL0006A_SOT-563-6_1.6x1.2mm", ["1", "2", "3", "4", "5", "6"]),
    ("M-MAIN-L", "Q_CHG_ISO_R", "Q1", "NEW:Nexperia_SOT23_TO-236AB", ["1", "2", "3"]),
    ("M-MAIN-L", "L1_BB", "L1", "NEW:Murata_DFE201612E_2016_2.0x1.6mm", ["1", "2"]),
    ("M-MAIN-L", "U7_WIN", "U14", "EMB:TI_DSG0008A", ["1", "2", "3", "4", "5", "6", "7", "8", "9"]),
    ("M-MAIN-L", "U5_LED2V8", "U5", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    ("M-MAIN-L", "U6_CAM_AVDD", "U6", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    ("M-MAIN-L", "U6_CAM_DOVDD", "U11", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    ("M-MAIN-L", "U6_CAM_DVDD", "U13", "EMB:TI_DQN0004A", ["1", "2", "3", "4", "5"]),
    ("M-MAIN-L", "U8_LS3", "U19", "EMB:TI_DQE0008A", ["1", "2", "3", "4", "5", "6", "7", "8"]),
    ("M-MAIN-L", "U8_LS4", "U20", "EMB:TI_DQE0008A", ["1", "2", "3", "4", "5", "6", "7", "8"]),
    ("M-MAIN-L", "U8_CAM_SCCB_EN", "U17", "EMB:TI_DPW0005A", ["1", "2", "3", "4", "5"]),
    # M-AUD-R (1 binding — clears ALL PRIMARY_LAND_PENDING on right audio board!)
    ("M-AUD-R", "U3_R", "U3", "EMB:TI_DSG0008A", ["1", "2", "3", "4", "5", "6", "7", "8", "9"]),
]

# Guarded ECO schematic/device attribute edits:
# (board, sourceRef, cadRef, eco_id, {field: (expected_old, desired_new)})
ECO_EDITS = [
    (
        "M-MAIN-L", "U4_OR", "U9", "ECO-01",
        {
            "MPN": ("LM66200DRLR", "TPS2116DRLR"),
            "Manufacturer Part": ("LM66200DRLR", "TPS2116DRLR"),
            "Value": ("U4_OR | LM66200DRLR", "U4_OR | TPS2116DRLR (Auto-Switchover 2.5A, ECO-01)"),
            "UserDocLink": ("https://www.ti.com/lit/ds/symlink/lm66200.pdf", "https://www.ti.com/lit/ds/symlink/tps2116.pdf"),
        },
    ),
    (
        "M-MAIN-L", "C_OR_OUT", "C27", "ECO-01",
        {
            "MPN": ("1uF 10V X7R", "22uF 10V X5R 0603 (ECO-01 bulk; >=30uF effective VSYS)"),
            "Value": ("C_OR_OUT | 1uF 10V X7R", "C_OR_OUT | 22uF 10V X5R (ECO-01)"),
        },
    ),
    (
        "M-MAIN-L", "U5_LED2V8", "U5", "ECO-02",
        {
            "MPN": ("TLV75528PDQNR", "TLV75533PDQNR"),
            "Manufacturer Part": ("TLV75528PDQNR", "TLV75533PDQNR"),
            "Value": ("U5_LED2V8 | TLV75528PDQNR", "U5_LED2V8 | TLV75533PDQNR (3.3V, ECO-02)"),
        },
    ),
    (
        "M-MAIN-L", "R_LIMIT", "R21", "ECO-02",
        {
            "Value": ("R_LIMIT | 249R (Rev D: high side, left board)", "R_LIMIT | 150R 1% 0402 100mW (ECO-02)"),
            "MPN": (
                "R_SENSE ERA-2AEB2R2X (2.20R 0.1%) + R_LIMIT 249R (high side) + window divider R1=33.2k/R2=32.4k/R3=32.4k + R_PRIV_PU 10k + 1ms RC + R_CRST_A_PD 100k + R_DIR1_PU 10k + R_LS1_A4/B4 100k + 4x I2C 2.2k + R_LS3_EN 200k + R_BB_FB1 560k/R_BB_FB2 100k + R_VSET_1V8 + R_CHIP_PU 10k/C_CHIP_PU 1uF",
                "RC0402FR-07150RL (150R 1% 0402 100mW, ECO-02)",
            ),
        },
    ),
    (
        "M-MAIN-L", "R_SENSE", "R31", "ECO-02",
        {
            "Value": ("R_SENSE | 2.20R 0.1% (Kelvin)", "R_SENSE | 1.10R 0.1% 0402 Kelvin (ECO-02)"),
            "MPN": (
                "R_SENSE ERA-2AEB2R2X (2.20R 0.1%) + R_LIMIT 249R (high side) + window divider R1=33.2k/R2=32.4k/R3=32.4k + R_PRIV_PU 10k + 1ms RC + R_CRST_A_PD 100k + R_DIR1_PU 10k + R_LS1_A4/B4 100k + 4x I2C 2.2k + R_LS3_EN 200k + R_BB_FB1 560k/R_BB_FB2 100k + R_VSET_1V8 + R_CHIP_PU 10k/C_CHIP_PU 1uF",
                "1.10R 0.1% 0402 Kelvin (ECO-02)",
            ),
        },
    ),
    (
        "M-MAIN-L", "R_WIN_TOP", "R35", "ECO-02",
        {
            "Value": ("R_WIN_TOP | 33.2k 1%", "R_WIN_TOP | 20.0k 1% (ECO-02)"),
            "MPN": ("33.2k 1%", "20.0k 1%"),
        },
    ),
    (
        "M-MAIN-L", "R_WIN_MID", "R34", "ECO-02",
        {
            "Value": ("R_WIN_MID | 32.4k 1%", "R_WIN_MID | 56.2k 1% (ECO-02)"),
            "MPN": ("32.4k 1%", "56.2k 1%"),
        },
    ),
    (
        "M-MAIN-L", "R_WIN_BOT", "R33", "ECO-02",
        {
            "Value": ("R_WIN_BOT | 32.4k 1%", "R_WIN_BOT | 24.9k 1% (ECO-02)"),
            "MPN": ("32.4k 1%", "24.9k 1%"),
        },
    ),
    (
        "M-MAIN-L", "L1_BB", "L1", "ECO-13",
        {
            "MPN": (
                "MPN_TBD (0.47uH effective0.37..0.57uH over temperature/DC current)",
                "DFE201612E-R47M=P2",
            ),
            "Value": (
                "L1_BB | BLOCKED | 0.47 uH",
                "L1_BB | CONDITIONAL | DFE201612E-R47M=P2 (0.47uH, Z=1.2mm, Isat=5.5A)",
            ),
            "UserDocLink": (
                "URL_TBD (Murata; Rev C linked the TPS63802 datasheet)",
                "https://www.murata.com/en-us/products/productdetail?partno=DFE201612E-R47M%3DP2",
            ),
        },
    ),
]


def create_footprint(template: Document, title: str, spec: dict, prefix: str) -> tuple[tuple[str, str], Document]:
    if template.one("META").payload["title"] != "Abracon_ASADV_2016-4Pin_2.0x1.6mm":
        raise ValueError("native SMT template identity changed")
    uid = fp_uuid(title)
    asset = ("FOOTPRINT", uid)
    head = deepcopy(template.one("DOCHEAD"))
    head.payload.update(uuid=uid, user={"uuid": uid})
    footprint = Document(head)
    for original in template.records[1:]:
        if original.header["type"] in {"PAD", "POLY", "FILL"}:
            continue
        record = deepcopy(original)
        if record.header["type"] == "META":
            record.payload.update(title=title, description=spec["desc"], tags=spec["tags"])
        elif record.header["type"] == "ATTR":
            if record.payload["key"] == "Name":
                record.payload["value"] = title
            elif record.payload["key"] == "Designator":
                record.payload.update(value=spec["designator"], x=0, y=mil(spec["outline"][1] + 0.50))
            else:
                raise ValueError("unreviewed native footprint template attribute")
        footprint.records.append(record)

    def add(kind, payload):
        index = len(footprint.records)
        header = {"type": kind, "ticket": 200 + index, "id": f"{prefix}{index}"}
        footprint.records.append(Record(compact(header) + b"||" + compact(payload) + b"|\n"))

    outline, = (r.payload for r in template.records if r.header["type"] == "POLY" and r.payload["layerId"] == 76)
    body = template.one("FILL").payload
    if body["layerId"] != 9 or body["isBridgingCopper"]:
        raise ValueError("native non-copper body template changed")
    ow, oh = spec["outline"]
    bw, bh = spec["body"]
    add("POLY", dict(outline, path=rectangle(ow, oh), zIndex=2))
    add("FILL", dict(body, path=[rectangle(bw, bh)], zIndex=3))
    pad, = (r.payload for r in template.records if r.header["type"] == "PAD" and r.payload["num"] == "1")
    if pad["layerId"] != 1 or pad["padAngle"] != 0 or pad["defaultPad"]["padType"] != "RECT":
        raise ValueError("native rectangular SMT pad template changed")
    for index, (number, x, y, width, height) in enumerate(spec["pads"], start=4):
        shape = dict(pad["defaultPad"], width=mil(width), height=mil(height))
        add("PAD", dict(pad, num=number, centerX=mil(x), centerY=mil(y), defaultPad=shape, zIndex=index))
    return asset, footprint


def build_candidate(baseline_path: Path, output_path: Path, report_path: Path):
    actual_sha = digest(baseline_path)
    if actual_sha != PR36_BASELINE_SHA:
        raise ValueError(f"Unexpected baseline SHA256: {actual_sha} != {PR36_BASELINE_SHA}")

    archive = Archive(baseline_path)
    plan = json.loads((PACKAGE / "h02-native/catalog-plan.json").read_text(encoding="utf-8"))
    by_key = {(r["board"], r["sourceReference"]): r for r in plan["records"]}

    # Load effective netlist for pin-contract assertions
    net_by_part = {}
    with (PACKAGE / "Inputs/effective_netlist.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            net_by_part.setdefault((row["Board"], row["RefDes"]), {})[row["Pin"]] = row["Net"]

    # 1. Create and insert 8 new OEM-reviewed footprints right before ("CONFIG", "CONFIG")
    template = archive.documents[ASADV_ASSET]
    new_fp_docs = {}
    new_fp_ids = {}
    for idx, (title, spec) in enumerate(NEW_FOOTPRINTS.items(), start=1):
        asset, doc = create_footprint(template, title, spec, f"rd{idx}p")
        if asset in archive.documents:
            raise ValueError(f"Footprint asset already exists: {title}")
        new_fp_docs[asset] = doc
        new_fp_ids[title] = asset[1]

    ordered = {}
    inserted = False
    for key, doc in archive.documents.items():
        if key == ("CONFIG", "CONFIG"):
            for asset, fp_doc in new_fp_docs.items():
                ordered[asset] = fp_doc
            inserted = True
        ordered[key] = doc
    if not inserted:
        raise ValueError("CONFIG ordering anchor absent")
    archive.documents = ordered

    # 2. Verify all 4 audited embedded footprints exist and have exact expected pad sets
    emb_fp_ids = {}
    for key, (uid, expected_title, expected_pads) in AUDITED_EMBEDDED_FOOTPRINTS.items():
        doc = archive.documents[("FOOTPRINT", uid)]
        actual_title = doc.one("META").payload["title"]
        actual_pads = sorted({r.payload["num"] for r in doc.records if r.header["type"] == "PAD"})
        if actual_title != expected_title or actual_pads != sorted(expected_pads):
            raise ValueError(f"Embedded footprint mismatch for {key}: {actual_title}, {actual_pads}")
        emb_fp_ids[key] = uid

    # 3. Apply guarded ECO schematic/device edits
    eco_ledger = []
    for board, src_ref, cad_ref, eco_id, field_edits in ECO_EDITS:
        row = by_key[(board, src_ref)]
        if row["cadReference"] != cad_ref:
            raise ValueError(f"CAD reference mismatch for {board}/{src_ref}: {row['cadReference']}")
        _, attrs = part_attrs(archive, row)
        duid = attr_value(attrs, "Device")
        device = asset_metadata(archive, ("DEVICE", duid))["attributes"]
        applied = {}
        for field, (expected_old, desired_new) in field_edits.items():
            # Verify schematic instance attribute if present
            if field in attrs:
                obs_sch = attr_value(attrs, field)
                if obs_sch != expected_old:
                    raise ValueError(f"{eco_id} {src_ref} SCH {field}: {obs_sch!r} != {expected_old!r}")
                attrs[field].payload["value"] = desired_new
            # Verify device attribute if present
            if field in device:
                obs_dev = device[field]
                if obs_dev != expected_old:
                    raise ValueError(f"{eco_id} {src_ref} DEV {field}: {obs_dev!r} != {expected_old!r}")
                device[field] = desired_new
            elif field == "Manufacturer Part":
                device[field] = desired_new
            applied[field] = {"old": expected_old, "new": desired_new}
        eco_ledger.append({
            "eco": eco_id,
            "board": board,
            "cadReference": cad_ref,
            "sourceReference": src_ref,
            "pageUuid": row["capturePage"],
            "primitiveId": row["capturePrimitiveId"],
            "deviceUuid": duid,
            "fields": applied,
            "terminalContract": net_by_part.get((board, src_ref), {}),
        })

    # 4. Apply 22 OEM-verified footprint bindings (guarding exact symbol pins == footprint pads == netlist pins)
    binding_ledger = []
    for board, src_ref, cad_ref, fp_ref, expected_pins in FOOTPRINT_BINDINGS:
        row = by_key[(board, src_ref)]
        if row["cadReference"] != cad_ref:
            raise ValueError(f"Binding CAD ref mismatch: {board}/{src_ref}")
        _, attrs = part_attrs(archive, row)
        duid = attr_value(attrs, "Device")
        suid = attr_value(attrs, "Symbol")
        device = asset_metadata(archive, ("DEVICE", duid))["attributes"]
        if device.get("Footprint", "") != "":
            raise ValueError(f"Device already bound: {board}/{cad_ref} -> {device.get('Footprint')}")
        # Verify single placement ownership
        placements = sum(
            r.header["type"] == "ATTR" and r.payload.get("key") == "Device" and r.payload.get("value") == duid
            for (kind, _), d in archive.documents.items() if kind == "SCH_PAGE" for r in d.records
        )
        if placements != 1:
            raise ValueError(f"Device {duid} ({board}/{cad_ref}) shared across {placements} placements")
        # Verify symbol pin set
        sym_pins = sorted(
            r.payload["value"] for r in archive.documents[("SYMBOL", suid)].records
            if r.header["type"] == "ATTR" and r.payload["key"] == "Pin Number"
        )
        if sym_pins != sorted(expected_pins):
            raise ValueError(f"Symbol pins mismatch for {board}/{cad_ref}: {sym_pins} != {expected_pins}")
        # Verify effective netlist pins
        nl_pins = sorted(net_by_part[(board, src_ref)].keys())
        if nl_pins != sorted(expected_pins):
            raise ValueError(f"Netlist pins mismatch for {board}/{cad_ref}: {nl_pins} != {expected_pins}")

        if fp_ref.startswith("NEW:"):
            title = fp_ref[4:]
            fuid = new_fp_ids[title]
            origin = "EVT1-reviewed-OEM-new"
        elif fp_ref.startswith("EMB:"):
            key = fp_ref[4:]
            fuid = emb_fp_ids[key]
            title = AUDITED_EMBEDDED_FOOTPRINTS[key][1]
            origin = "PR36-embedded-OEM-audited"
        else:
            raise ValueError(f"Bad fp_ref: {fp_ref}")

        # Verify footprint pad set == symbol pin set
        fp_pads = sorted({
            r.payload["num"] for r in archive.documents[("FOOTPRINT", fuid)].records
            if r.header["type"] == "PAD"
        })
        if fp_pads != sorted(expected_pins):
            raise ValueError(f"Footprint pads mismatch for {board}/{cad_ref}: {fp_pads} != {expected_pins}")

        device["Footprint"] = fuid
        binding_ledger.append({
            "board": board,
            "cadReference": cad_ref,
            "sourceReference": src_ref,
            "pageUuid": row["capturePage"],
            "primitiveId": row["capturePrimitiveId"],
            "deviceUuid": duid,
            "symbolUuid": suid,
            "footprintUuid": fuid,
            "footprintTitle": title,
            "origin": origin,
            "pins": sym_pins,
            "terminalContract": net_by_part[(board, src_ref)],
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    archive.write(output_path)

    report = {
        "status": "CANDIDATE_BUILT",
        "manufacturing": "BLOCKED",
        "baselinePath": str(baseline_path.relative_to(PACKAGE)),
        "baselineSha256": actual_sha,
        "candidateSha256": digest(output_path),
        "newFootprintsCreated": {k: new_fp_ids[k] for k in NEW_FOOTPRINTS},
        "auditedEmbeddedFootprintsUsed": {k: v[0] for k, v in AUDITED_EMBEDDED_FOOTPRINTS.items()},
        "ecoEditsCount": len(eco_ledger),
        "footprintBindingsCount": len(binding_ledger),
        "footprintBindingsByBoard": {
            b: sum(1 for x in binding_ledger if x["board"] == b)
            for b in ("M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R")
        },
        "ecoEdits": eco_ledger,
        "footprintBindings": binding_ledger,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built candidate: {output_path}")
    print(f"Candidate SHA256: {report['candidateSha256']}")
    print(f"ECO edits: {len(eco_ledger)}, Footprint bindings: {len(binding_ledger)} ({report['footprintBindingsByBoard']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=PR36_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    build_candidate(args.baseline, args.output, args.report)


if __name__ == "__main__":
    main()
