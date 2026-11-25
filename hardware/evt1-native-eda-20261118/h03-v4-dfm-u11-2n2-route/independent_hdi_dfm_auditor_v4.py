#!/usr/bin/env python3
"""V4 blind-via geometry audit and inherited U11 95-ball classification.

JLCPCB FAQ D measures the hole wall to the routed outline. FAQ F measures
hole wall to hole wall, including relevant unlike spans. EVT-1 separately
screens copper lands at the selected 0.350 mm edge guard and locked 6 mil
via-pair clearance. The audit uses nominal 2D circular geometry and actual
archive span declarations. Stack construction, taper, depth and tolerances
require fabrication engineering approval.
"""

import argparse
from collections import Counter
import csv
from hashlib import sha256
from itertools import combinations
import json
import math
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h03-dfm-p0-closure"),
    str(PACKAGE / "h03-hdi-laser-wlcsp-route"),
    str(PACKAGE / "h03-u11-wlcsp-v3-dfm-route"),
]

from independent_hdi_dfm_auditor import DOCS
from independent_hdi_dfm_auditor_v2 import audit_board_v2
from independent_hdi_dfm_auditor_v3 import center_to_outline_dist, extract_outline_polygon
from prepare_hierarchy import Archive

MM_PER_MIL = 0.0254
JLC_HDI = "https://jlcpcb.com/pcb-fabrication/hdi-pcb"
JLC_HDI_FAQ = "https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq"
JLC_HDI_DIAGRAM = "https://rs.jlcpcb.com/static/image/blog/pcb/jlcpcb-hdi-manufacturing-process.png"
COPPER_LAYER_ORDER = (1, 15, 16, 17, 18, 2)
EXPECTED_BASE_SPANS = {"BV_L1_L2": {1, 15}, "BV_L5_L6": {18, 2}}
MIN_BLIND_EDGE_HOLE_MM = 0.350
MIN_BLIND_EDGE_HOLE_MIL = MIN_BLIND_EDGE_HOLE_MM / MM_PER_MIL
# Retain the more conservative copper-layout guard used by the V4 rectifier.
MIN_BLIND_EDGE_CU_MM = 0.350
MIN_BLIND_EDGE_CU_MIL = MIN_BLIND_EDGE_CU_MM / MM_PER_MIL
MIN_BLIND_VV_HOLE_SAME_NET_MM = 0.130
MIN_BLIND_VV_HOLE_SAME_NET_MIL = MIN_BLIND_VV_HOLE_SAME_NET_MM / MM_PER_MIL
MIN_BLIND_VV_HOLE_DIFF_NET_MM = 0.240
MIN_BLIND_VV_HOLE_DIFF_NET_MIL = MIN_BLIND_VV_HOLE_DIFF_NET_MM / MM_PER_MIL
MIN_MECH_VV_HOLE_DIFF_NET_MM = 0.254
MIN_MECH_VV_HOLE_DIFF_NET_MIL = MIN_MECH_VV_HOLE_DIFF_NET_MM / MM_PER_MIL
MIN_VV_CU_GAP_MIL = 6.0
MIN_BLIND_RING_MIL = 3.0
MIN_BLIND_HOLE_MIL = 0.075 / MM_PER_MIL
MAX_BLIND_HOLE_MIL = 0.150 / MM_PER_MIL
MIN_MECH_HOLE_MIL = 0.150 / MM_PER_MIL
FLOAT_TOL_MIL = 1e-9

RULE_SOURCES = {
    "blind_via_to_board_edge_mm": "EVT-1 V4 conservative copper-land to routed-outline guard >= 0.350 mm",
    "blind_via_hole_to_board_edge_mm": f"JLCPCB HDI FAQ diagram D: laser hole wall to routed outline >= 0.350 mm, {JLC_HDI_FAQ}",
    "blind_via_hole_to_hole_same_net_mm": f"JLCPCB HDI FAQ diagram F: same-net hole wall gap >= 0.130 mm, {JLC_HDI_FAQ}",
    "blind_via_hole_to_hole_diff_net_mm": f"JLCPCB HDI FAQ diagram F: different-net hole wall gap >= 0.240 mm, {JLC_HDI_FAQ}",
    "blind_via_annular_ring": f"JLCPCB HDI capture and target-pad table: 3 mil radial, {JLC_HDI}",
    "blind_via_aperture": f"JLCPCB HDI laser aperture: 0.075–0.150 mm, {JLC_HDI}",
    "same_span_copper_clearance_mil": "EVT-1 Locked EasyEDA Pro 6L HDI DRC Rule (>= 6.0 mil / 0.1524 mm)",
    "through_to_through_different_net_hole_wall": "Inherited EVT-1 V4 through-via guard >= 0.254 mm; outside the HDI FAQ blind-hole scope",
}

# Official Nordic Semiconductor nRF5340 PS WLCSP-95 (CMAA / CLAA) Pin Assignment Table (95 balls)
# Tuple: (official_name, pin_class, config3_requirement, remappable_gpio)
# pin_class in: POWER_VDD, POWER_VDDH, GND_VSS, GND_AVSS, USB_VBUS, USB_DATA, USB_DEC,
#               VREGH_DCCH, REG_DCDC_DEC, RF_ANT, CLK_HFXO, CLK_LFXO, DEBUG_SWD, RESET,
#               GPIO_ACTIVE, GPIO_UNUSED, GPIO_UNUSED_NFC
NORDIC_NRF5340_CMAA_95: dict[str, tuple[str, str, str, bool]] = {
    "A1":  ("XC1",        "CLK_HFXO",        "Mandatory 32 MHz HFXO (Y2)", False),
    "A2":  ("XC2",        "CLK_HFXO",        "Mandatory 32 MHz HFXO (Y2)", False),
    "A3":  ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "A5":  ("VSS",        "GND_VSS",         "Mandatory ground", False),
    "A7":  ("DECD",       "REG_DCDC_DEC",    "Mandatory VREGMAIN DCDC cap C11(1uF) + L4(10uH)", False),
    "A9":  ("DCCD",       "REG_DCDC_DEC",    "Mandatory VREGMAIN DCDC inductor L4(10uH) to DECD", False),
    "A11": ("D-",         "USB_DATA",        "Config #3 USB unused -> Leave NC", False),
    "A12": ("D+",         "USB_DATA",        "Config #3 USB unused -> Leave NC", False),
    "B1":  ("DECRF",      "REG_DCDC_DEC",    "Mandatory VREGRADIO HF cap C10(2.2nF), tied to B4 DECR", False),
    "B2":  ("VSS",        "GND_VSS",         "Mandatory ground", False),
    "B4":  ("DECR",       "REG_DCDC_DEC",    "Mandatory VREGRADIO cap C9(1uF) + L3(10uH), tied to B1", False),
    "B5":  ("DECN",       "REG_DCDC_DEC",    "Mandatory network-core decoupling C12(100nF)", False),
    "B6":  ("DCC",        "REG_DCDC_DEC",    "Mandatory VREGRADIO DCDC inductor L3(10uH) to DECR", False),
    "B7":  ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "B8":  ("DECA",       "REG_DCDC_DEC",    "Mandatory app-core decoupling C13(1uF)", False),
    "B9":  ("VSS",        "GND_VSS",         "Mandatory ground", False),
    "B10": ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "B11": ("VBUS",       "USB_VBUS",        "Config #3 USB unused -> Mandatory tie to GND", False),
    "B12": ("VDDH",       "POWER_VDDH",      "Config #3 Normal voltage -> Mandatory tie to VDD (1V8_SYS)", False),
    "C2":  ("VSS",        "GND_VSS",         "Mandatory ground", False),
    "C4":  ("P0.30/AIN6", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C5":  ("P0.31/AIN7", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C6":  ("P1.11",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C7":  ("P1.12",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C8":  ("P1.13",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C9":  ("P1.14",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C10": ("P1.15",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "C11": ("DECUSB",     "USB_DEC",         "Config #3 USB unused -> Leave NC", False),
    "D1":  ("ANT",        "RF_ANT",          "Mandatory 2.4 GHz RF feed -> L1/C7/L2/ANT2", False),
    "D2":  ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "D10": ("P1.00",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "D11": ("DCCH",       "VREGH_DCCH",      "Config #3 Normal voltage (VREGH off) -> Leave NC", False),
    "D12": ("VSS",        "GND_VSS",         "Mandatory ground", False),
    "E2":  ("P0.29/AIN5", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "E3":  ("P0.28/AIN4", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "E4":  ("P1.10",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "E5":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "E6":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "E7":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "E8":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "E10": ("P1.01",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "E11": ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "F1":  ("SWDIO",      "DEBUG_SWD",       "Mandatory SWD debug/programming (TP6)", False),
    "F2":  ("SWDCLK",     "DEBUG_SWD",       "Mandatory SWD debug/programming (TP6)", False),
    "F3":  ("P1.08",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "F5":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "F6":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "F7":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "F8":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "F10": ("P0.05/AIN1", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "F11": ("P0.00/XL1",  "CLK_LFXO",        "ECO-08 32.768 kHz LFXO (Y3 + C22 12pF)", False),
    "F12": ("P0.01/XL2",  "CLK_LFXO",        "ECO-08 32.768 kHz LFXO (Y3 + C23 12pF)", False),
    "G2":  ("nRESET",     "RESET",           "Mandatory reset pin (internal pull-up, TP6)", False),
    "G3":  ("P1.07",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "G5":  ("AVSS",       "GND_AVSS",        "Mandatory analog ground (center array)", False),
    "G6":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "G7":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "G8":  ("VSS",        "GND_VSS",         "Mandatory ground (center array)", False),
    "G10": ("P0.04/AIN0", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "G11": ("P0.02/NFC1", "GPIO_UNUSED_NFC", "Unused NFC/GPIO -> NC (disable NFC in UICR.NFCPINS)", True),
    "H1":  ("P0.27",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "H2":  ("P1.09",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "H3":  ("P0.23",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "H10": ("P0.06/AIN2", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "H11": ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "H12": ("P0.03/NFC2", "GPIO_UNUSED_NFC", "Unused outer-ring NFC/GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "J2":  ("P0.26/AIN3", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J3":  ("P1.06",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J4":  ("P0.21",      "GPIO_ACTIVE",     "I2S_AMP_DIN_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "J5":  ("P0.19",      "GPIO_ACTIVE",     "I2S_S3_DOUT_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "J6":  ("P0.12",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J7":  ("P0.11",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J8":  ("P0.10",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J9":  ("P0.09",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J10": ("P0.07/AIN3", "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "J11": ("P1.02",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "K1":  ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "K2":  ("P0.24",      "GPIO_ACTIVE",     "AMP_SD_REQ_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "K3":  ("P1.04",      "GPIO_ACTIVE",     "IPC_NRF_TX_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "K4":  ("P0.22",      "GPIO_ACTIVE",     "I2S_LRCLK_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "K5":  ("P0.20",      "GPIO_ACTIVE",     "I2S_BCLK_1V8 (PSEL remappable to outer GPIO in Rev E2)", True),
    "K6":  ("AVSS",       "GND_AVSS",        "Mandatory analog ground", False),
    "K7":  ("P0.18",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "K8":  ("P0.16",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "K9":  ("P0.14",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "K10": ("P0.13",      "GPIO_UNUSED",     "Unused GPIO -> NC (disable input/pulls in FW)", True),
    "K11": ("AVSS",       "GND_AVSS",        "Mandatory analog ground", False),
    "K12": ("P1.03",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "L1":  ("P0.25",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "L3":  ("P1.05",      "GPIO_ACTIVE",     "IPC_S3_TX_1V8 (outer perimeter, already L1 escapable)", True),
    "L5":  ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "L7":  ("P0.17",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "L9":  ("P0.15",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
    "L11": ("VDD",        "POWER_VDD",       "Mandatory 1V8_SYS normal-voltage supply", False),
    "L12": ("P0.08",      "GPIO_UNUSED",     "Unused outer-ring GPIO -> NC (candidate Rev E2 PSEL target)", True),
}


def audit_u11_95ball_official(dump_path: Path, out_csv: Path | None = None) -> dict:
    assert len(NORDIC_NRF5340_CMAA_95) == 95
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    u11 = next((c for c in dump.get("components", []) if c.get("designator") == "U11"), None)
    if u11 is None:
        return {"found": False}
    pads = u11.get("pads", [])

    def cluster(vals: list[float], tol: float = 3.0) -> list[float]:
        gs: list[list[float]] = []
        for v in sorted(vals):
            if not gs or abs(v - gs[-1][-1]) > tol:
                gs.append([v])
            else:
                gs[-1].append(v)
        return [round(sum(g) / len(g), 2) for g in gs]

    ux = cluster([float(p["x"]) for p in pads])
    uy = cluster([float(p["y"]) for p in pads])
    nx, ny = len(ux), len(uy)

    def nidx(v: float, g: list[float]) -> int:
        return min(range(len(g)), key=lambda i: abs(g[i] - v))

    rows = []
    counts_by_class: dict[str, int] = {}
    escape_breakdown = {
        "outer_depth0_active": 0,
        "ring1_depth1_fixed": 0,
        "ring1_depth1_remappable_gpio": 0,
        "deep_depth2plus_fixed_gnd": 0,
        "deep_depth2plus_remappable_gpio": 0,
        "unassigned_usb_vregh_nc": 0,
        "unassigned_gpio_nc": 0,
        "chip_true_nc": 0,
    }
    outer_free_gpios = []
    inner_remappable = []
    inner_fixed = []

    for p in sorted(pads, key=lambda z: (str(z["padNumber"])[0], int(str(z["padNumber"])[1:]))):
        ball = str(p["padNumber"])
        px, py = float(p["x"]), float(p["y"])
        ix, iy = nidx(px, ux), nidx(py, uy)
        depth = min(ix, nx - 1 - ix, iy, ny - 1 - iy)
        pcb_net = (p.get("net") or "").strip()
        off_name, pin_cls, cfg3_req, remappable = NORDIC_NRF5340_CMAA_95[ball]
        counts_by_class[pin_cls] = counts_by_class.get(pin_cls, 0) + 1

        needs_escape = bool(pcb_net)
        if not needs_escape:
            if pin_cls in ("USB_DATA", "USB_DEC", "VREGH_DCCH"):
                escape_breakdown["unassigned_usb_vregh_nc"] += 1
                esc_cat = "NO_ESCAPE_CONFIG3_USB_VREGH_NC"
            else:
                escape_breakdown["unassigned_gpio_nc"] += 1
                esc_cat = "NO_ESCAPE_UNUSED_GPIO"
                if depth == 0 and remappable:
                    outer_free_gpios.append(f"{ball}:{off_name}")
        elif depth == 0:
            escape_breakdown["outer_depth0_active"] += 1
            esc_cat = "ESCAPE_L1_OUTER_PERIMETER"
        elif depth == 1:
            if remappable:
                escape_breakdown["ring1_depth1_remappable_gpio"] += 1
                esc_cat = "ESCAPE_RING1_REMAPPABLE_GPIO"
                inner_remappable.append(f"{ball}:{off_name}->{pcb_net}")
            else:
                escape_breakdown["ring1_depth1_fixed"] += 1
                esc_cat = "ESCAPE_RING1_FIXED_REQUIRES_2N2_VIPPO"
                inner_fixed.append(f"{ball}:{off_name}->{pcb_net}")
        else:
            if remappable:
                escape_breakdown["deep_depth2plus_remappable_gpio"] += 1
                esc_cat = "ESCAPE_DEEP_INNER_REMAPPABLE_GPIO"
                inner_remappable.append(f"{ball}:{off_name}->{pcb_net}")
            else:
                escape_breakdown["deep_depth2plus_fixed_gnd"] += 1
                esc_cat = "ESCAPE_DEEP_INNER_FIXED_GND_VIPPO"
                inner_fixed.append(f"{ball}:{off_name}->{pcb_net}")

        rows.append({
            "ball": ball,
            "official_nordic_pin": off_name,
            "pin_class": pin_cls,
            "pcb3_net": pcb_net or "NC",
            "ring_depth": depth,
            "x_mil": round(px, 2),
            "y_mil": round(py, 2),
            "needs_escape": "YES" if needs_escape else "NO",
            "remappable_via_psel": "YES" if remappable else "NO",
            "escape_category": esc_cat,
            "config3_requirement": cfg3_req,
        })

    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    inner_total = (
        escape_breakdown["ring1_depth1_fixed"]
        + escape_breakdown["ring1_depth1_remappable_gpio"]
        + escape_breakdown["deep_depth2plus_fixed_gnd"]
        + escape_breakdown["deep_depth2plus_remappable_gpio"]
    )
    inner_fixed_total = escape_breakdown["ring1_depth1_fixed"] + escape_breakdown["deep_depth2plus_fixed_gnd"]

    return {
        "found": True,
        "designator": "U11",
        "bom_mpn": "nRF5340-CMAA-R7",
        "package": "WLCSP-95 (3.994 x 4.390 x 0.449 mm, 0.35 mm pitch, 11x12 grid)",
        "nordic_reference_config": "Circuit Configuration #3 (Normal Voltage 1.8V, VDD=VDDH=1V8_SYS, VREGMAIN+VREGRADIO DCDC, USB unused with VBUS=GND)",
        "total_balls": len(rows),
        "chip_true_nc_balls": 0,
        "active_balls_needing_escape": escape_breakdown["outer_depth0_active"] + inner_total,
        "unassigned_balls_no_escape": escape_breakdown["unassigned_usb_vregh_nc"] + escape_breakdown["unassigned_gpio_nc"],
        "counts_by_official_pin_class": counts_by_class,
        "escape_breakdown": escape_breakdown,
        "inner_balls_requiring_vippo_current_rev_e": inner_total,
        "inner_balls_fixed_non_remappable": inner_fixed_total,
        "inner_balls_remappable_to_outer_gpio": len(inner_remappable),
        "inner_remappable_list": inner_remappable,
        "outer_free_gpio_candidates": outer_free_gpios,
        "config3_compliance_audit": {
            "status": "REQUIRES_NATIVE_TERMINAL_AND_PERIPHERAL_AUDIT",
            "scope": "This inherited classifier reads the routed U11 pad map only.",
        },
        "selected_technical_route": "OPTION_1_RETAIN_CMAA_UPGRADE_PCB3_TIER1_2N2_ADVANCED_HDI",
        "fab_approval_status": "BLOCKED_PENDING_TIER1_2N2_HDI_FAB_EQ",
    }


def layer_interval(start, end):
    """Resolve inclusive copper layers in physical order (EasyEDA IDs are unordered)."""
    if start == end or start not in COPPER_LAYER_ORDER or end not in COPPER_LAYER_ORDER:
        return frozenset()
    low, high = sorted((COPPER_LAYER_ORDER.index(start), COPPER_LAYER_ORDER.index(end)))
    return frozenset(COPPER_LAYER_ORDER[low:high + 1])


def read_blind_rule_spans(doc):
    rules = {}
    for r in doc.records:
        if r.header.get("type") != "RULE":
            continue
        for row in r.payload.get("ruleContext", {}).get("blinds", {}).get("content", []):
            name = row["name"]
            if name in rules:
                raise ValueError(f"Duplicate archive blind via rule {name}")
            rules[name] = layer_interval(row["staLayerId"], row["endLayerId"])
    return rules


def read_vias(doc, dump):
    """Use archive type/span and require same via identity and geometry in editor capture."""
    if dump.get("copperLayers") != len(COPPER_LAYER_ORDER):
        raise ValueError("V4 scope requires the observed six-layer build")
    live_rows = dump["copper"]["vias"]
    live = {row["primitiveId"]: row for row in live_rows}
    source_rows = [r for r in doc.records if r.header.get("type") == "VIA"]
    source_ids = {r.header["id"] for r in source_rows}
    if len(live) != len(live_rows) or len(source_ids) != len(source_rows) or source_ids != live.keys():
        raise ValueError("Archive via IDs differ from editor capture")

    rules = read_blind_rule_spans(doc)
    all_vias = []
    for r in source_rows:
        p = r.payload
        ref = r.header["id"]
        via_type = p["viaType"]
        rule_name = p.get("ruleName", "")
        x, y, hole, diam = (float(p[k]) for k in ("centerX", "centerY", "holeDiameter", "viaDiameter"))
        if not all(map(math.isfinite, (x, y, hole, diam))) or not 0 < hole <= diam:
            raise ValueError(f"Invalid archive via geometry for {ref}")
        net = (p.get("netName") or "").strip()
        mirror = live[ref]
        if net != (mirror.get("net") or "").strip() or any(
            not math.isclose(a, float(mirror[k]), rel_tol=0, abs_tol=FLOAT_TOL_MIL)
            for a, k in ((x, "x"), (y, "y"), (hole, "holeDiameter"), (diam, "diameter"))
        ):
            raise ValueError(f"Archive and editor capture differ for via {ref}")
        if via_type == "NORMAL":
            span = frozenset(COPPER_LAYER_ORDER)
        elif via_type == "BLIND":
            span = rules.get(rule_name, frozenset())
        else:
            raise ValueError(f"Unsupported via type for {ref}: {via_type!r}")
        all_vias.append({"id": ref, "net": net, "viaType": via_type, "ruleName": rule_name,
                         "hole_mil": hole, "diam_mil": diam, "ring_mil": (diam - hole) / 2,
                         "x": x, "y": y, "span": span})
    return all_vias


def edge_metrics(via, outline):
    center = center_to_outline_dist(outline, via["x"], via["y"])
    return center, center - via["hole_mil"] / 2, center - via["diam_mil"] / 2


def below_limit(value, limit):
    return value < limit - FLOAT_TOL_MIL


def pair_metrics(va, vb):
    shared = va["span"] & vb["span"]
    if not shared:
        return None
    pitch = math.hypot(va["x"] - vb["x"], va["y"] - vb["y"])
    same_net = bool(va["net"]) and va["net"] == vb["net"]
    has_blind = "BLIND" in (va["viaType"], vb["viaType"])
    equal_span = va["span"] == vb["span"]
    adjacent = len(shared) == 1 and not equal_span
    stack_review = adjacent and pitch <= FLOAT_TOL_MIL and same_net and has_blind
    relation = "same_span" if equal_span else "adjacent_spans" if adjacent else "overlapping_unlike_spans"
    hole_radii = (va["hole_mil"] + vb["hole_mil"]) / 2
    copper_radii = (va["diam_mil"] + vb["diam_mil"]) / 2
    if stack_review:
        hole_limit = None
    elif has_blind:
        hole_limit = MIN_BLIND_VV_HOLE_SAME_NET_MIL if same_net else MIN_BLIND_VV_HOLE_DIFF_NET_MIL
    else:
        hole_limit = None if same_net else MIN_MECH_VV_HOLE_DIFF_NET_MIL
    cu_limit = None if stack_review or (same_net and not has_blind) else MIN_VV_CU_GAP_MIL
    return {"shared_layers": sorted(shared), "span_relation": relation, "stack_review": stack_review,
            "has_blind": has_blind, "same_net": same_net,
            "center_pitch_mil": pitch, "cu_gap_mil": pitch - copper_radii,
            "hole_wall_mil": pitch - hole_radii, "hole_wall_limit_mil": hole_limit,
            "equivalent_hole_pitch_limit_mil": None if hole_limit is None else hole_limit + hole_radii,
            "equivalent_cu_pitch_limit_mil": None if cu_limit is None else cu_limit + copper_radii,
            "cu_gap_limit_mil": cu_limit}


def audit_board_v4(
    board: str,
    arc: Archive,
    dump_path: Path,
    conflict_csv: Path | None = None,
    blind_csv: Path | None = None,
    u11_csv: Path | None = None,
) -> dict:
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    capture = dump.get("capture", {})
    if (capture.get("documentUuid"), capture.get("identityVerified"), dump.get("availability", {}).get("copper")) != (
        DOCS[board], True, "available"
    ):
        raise ValueError(f"Identity-verified editor capture with copper required for {board}")
    doc = arc.documents[("PCB", DOCS[board])]
    outline_poly = extract_outline_polygon(dump)
    all_vias = read_vias(doc, dump)
    base = audit_board_v2(board, arc, dump_path, conflict_csv)

    blinds = [v for v in all_vias if v["viaType"] == "BLIND"]
    bad_hole_edge = []
    bad_copper_edge = []
    bad_ring = []
    bad_hole = []
    bad_hole_high = []
    bad_span = []
    edge_cu_mils = []
    edge_hole_mils = []
    blind_rows = []

    for v in blinds:
        c2e, h2e_mil, cu2e_mil = edge_metrics(v, outline_poly)
        cu2e_mm = round(cu2e_mil * MM_PER_MIL, 6)
        h2e_mm = round(h2e_mil * MM_PER_MIL, 6)
        edge_cu_mils.append(cu2e_mil)
        edge_hole_mils.append(h2e_mil)

        hole_edge_pass = not below_limit(h2e_mil, MIN_BLIND_EDGE_HOLE_MIL)
        copper_guard_pass = not below_limit(cu2e_mil, MIN_BLIND_EDGE_CU_MIL)
        ring_pass = not below_limit(v["ring_mil"], MIN_BLIND_RING_MIL)
        hole_min_pass = not below_limit(v["hole_mil"], MIN_BLIND_HOLE_MIL)
        hole_max_pass = not below_limit(MAX_BLIND_HOLE_MIL, v["hole_mil"])
        span_pass = bool(v["span"]) and EXPECTED_BASE_SPANS.get(v["ruleName"]) == v["span"]
        edge_row = {
            "id": v["id"], "net": v["net"], "ruleName": v["ruleName"],
            "x_mil": v["x"], "y_mil": v["y"],
            "cu_to_edge_mil": round(cu2e_mil, 6), "cu_to_edge_mm": cu2e_mm,
            "hole_to_edge_mil": round(h2e_mil, 6), "hole_to_edge_mm": h2e_mm,
        }
        if not hole_edge_pass:
            bad_hole_edge.append({**edge_row, "required_mm": MIN_BLIND_EDGE_HOLE_MM})
        if not copper_guard_pass:
            bad_copper_edge.append({**edge_row, "required_mm": MIN_BLIND_EDGE_CU_MM})
        if not ring_pass:
            bad_ring.append({"id": v["id"], "net": v["net"], "ring_mil": v["ring_mil"]})
        if not hole_min_pass:
            bad_hole.append({"id": v["id"], "net": v["net"], "hole_mil": v["hole_mil"]})
        if not hole_max_pass:
            bad_hole_high.append({"id": v["id"], "net": v["net"], "hole_mil": v["hole_mil"]})
        if not span_pass:
            bad_span.append({"id": v["id"], "net": v["net"], "ruleName": v["ruleName"], "span": sorted(v["span"])})

        blind_rows.append({
            "board": board,
            "via_id": v["id"],
            "net": v["net"],
            "rule_name": v["ruleName"],
            "span_layer_ids": "/".join(map(str, (lid for lid in COPPER_LAYER_ORDER if lid in v["span"]))),
            "x_mil": v["x"],
            "y_mil": v["y"],
            "hole_mil": v["hole_mil"],
            "diam_mil": v["diam_mil"],
            "ring_mil": v["ring_mil"],
            "center_to_edge_mil": round(c2e, 6),
            "cu_to_edge_mil": round(cu2e_mil, 6),
            "cu_to_edge_mm": cu2e_mm,
            "hole_to_edge_mil": round(h2e_mil, 6),
            "hole_to_edge_mm": h2e_mm,
            "jlc_hole_edge_ge_0p35mm": "PASS" if hole_edge_pass else "FAIL",
            "evt1_copper_edge_ge_0p35mm": "PASS" if copper_guard_pass else "FAIL",
            "laser_aperture_0p075_to_0p150mm": "PASS" if hole_min_pass and hole_max_pass else "FAIL",
            "laser_annular_ring_ge_3mil": "PASS" if ring_pass else "FAIL",
            "span_valid": "PASS" if span_pass else "FAIL",
        })

    if blind_csv is not None and blind_rows:
        blind_csv.parent.mkdir(parents=True, exist_ok=True)
        with blind_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(blind_rows[0].keys()))
            w.writeheader()
            w.writerows(blind_rows)

    # Net-aware & true vertical layer-span via-to-via audit (ALL pairs on shared spans!)
    bad_vv_cu_same = []
    bad_vv_cu_diff = []
    bad_vv_hole_same = []
    bad_vv_hole_diff = []
    vv_same_cu = []
    vv_diff_cu = []
    vv_same_hole = []
    vv_diff_hole = []
    stacked_review = []
    pair_coverage = Counter()
    closest_blind_pairs = {}
    for va, vb in combinations(all_vias, 2):
        metrics = pair_metrics(va, vb)
        if metrics is None:
            pair_coverage["disjoint_spans" if va["span"] and vb["span"] else "unresolved_span"] += 1
            continue
        pair_coverage[metrics["span_relation"]] += 1
        cu_gap, hole_wall = metrics["cu_gap_mil"], metrics["hole_wall_mil"]
        same_net = metrics["same_net"]
        pair_rec = {
            "a": va["id"], "b": vb["id"],
            "a_type": va["ruleName"] or va["viaType"], "b_type": vb["ruleName"] or vb["viaType"],
            "a_net": va["net"], "b_net": vb["net"],
            **{k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()},
            "center_pitch_mm": round(metrics["center_pitch_mil"] * MM_PER_MIL, 6),
            "cu_gap_mm": round(cu_gap * MM_PER_MIL, 6), "hole_wall_mm": round(hole_wall * MM_PER_MIL, 6),
        }
        if metrics["stack_review"]:
            stacked_review.append(pair_rec)
            continue
        (vv_same_cu if same_net else vv_diff_cu).append(cu_gap)
        (vv_same_hole if same_net else vv_diff_hole).append(hole_wall)
        if metrics["has_blind"]:
            category = "same_net" if same_net else "different_or_unknown_net"
            prior_pair = closest_blind_pairs.get(category)
            if prior_pair is None or hole_wall < prior_pair[0]:
                closest_blind_pairs[category] = (hole_wall, pair_rec)
        if metrics["cu_gap_limit_mil"] is not None and below_limit(cu_gap, metrics["cu_gap_limit_mil"]):
            (bad_vv_cu_same if same_net else bad_vv_cu_diff).append(pair_rec)
        if metrics["hole_wall_limit_mil"] is not None and below_limit(hole_wall, metrics["hole_wall_limit_mil"]):
            (bad_vv_hole_same if same_net else bad_vv_hole_diff).append(pair_rec)

    mech_min_ring_mil = 0.075 / MM_PER_MIL
    bad_mech = [{"id": v["id"], "net": v["net"], "hole_mil": v["hole_mil"], "ring_mil": v["ring_mil"]}
                for v in all_vias if v["viaType"] != "BLIND" and (
                    below_limit(v["hole_mil"], MIN_MECH_HOLE_MIL) or below_limit(v["ring_mil"], mech_min_ring_mil)
                )]
    span_counts: dict[str, int] = {}
    for v in blinds:
        k = v["ruleName"] or "UNSPECIFIED"
        span_counts[k] = span_counts.get(k, 0) + 1

    total_v4_viols = (
        len(bad_hole_edge) + len(bad_copper_edge) + len(bad_vv_cu_same) + len(bad_vv_cu_diff)
        + len(bad_vv_hole_same) + len(bad_vv_hole_diff) + len(stacked_review)
        + len(bad_ring) + len(bad_hole) + len(bad_hole_high) + len(bad_span) + len(bad_mech)
    )

    base["v4_official_jlcpcb_hdi_audit"] = {
        "rule_sources": RULE_SOURCES,
        "datum_diagram": JLC_HDI_DIAGRAM,
        "measurement_model": {
            "signed_edge_clearance": "center to nearest routed contour segment minus nominal hole/copper radius",
            "pair_clearances": "center pitch minus the sum of the two nominal hole/copper radii",
            "shared_layers": "inclusive copper span from archive rules; distinct vias checked if their spans share copper",
            "staggered_spans": "check a laterally offset shared-layer pair using nominal drill diameters; actual taper is not modeled",
            "stacked_and_unresolved": "concentric same-net adjacent-span stacks are reported for fab approval; unknown spans fail the stack-scope check",
            "minima": "pair minima cover observed applicable shared-layer pairs; closest_blind_pairs separately identifies FAQ-F pairs",
        },
        "inputs": {
            "archive_sha256": sha256(arc.path.read_bytes()).hexdigest(),
            "dump_sha256": sha256(dump_path.read_bytes()).hexdigest(),
            "editor_archive_via_id_and_pad_hole_xy_parity": "PASS",
        },
        "thresholds": {
            "min_jlc_blind_hole_to_edge_mm": MIN_BLIND_EDGE_HOLE_MM,
            "min_jlc_blind_hole_to_edge_mil": MIN_BLIND_EDGE_HOLE_MIL,
            "min_blind_cu_to_edge_mm": MIN_BLIND_EDGE_CU_MM,
            "min_blind_cu_to_edge_mil": round(MIN_BLIND_EDGE_CU_MIL, 4),
            "min_same_net_blind_hole_wall_mm": MIN_BLIND_VV_HOLE_SAME_NET_MM,
            "min_same_net_blind_hole_wall_mil": round(MIN_BLIND_VV_HOLE_SAME_NET_MIL, 4),
            "min_diff_net_blind_hole_wall_mm": MIN_BLIND_VV_HOLE_DIFF_NET_MM,
            "min_diff_net_blind_hole_wall_mil": round(MIN_BLIND_VV_HOLE_DIFF_NET_MIL, 4),
            "min_diff_net_mech_hole_wall_mm": MIN_MECH_VV_HOLE_DIFF_NET_MM,
            "min_same_span_cu_gap_mil": MIN_VV_CU_GAP_MIL,
            "min_blind_ring_mil": MIN_BLIND_RING_MIL,
            "min_blind_ring_mm": MIN_BLIND_RING_MIL * MM_PER_MIL,
            "min_blind_hole_mil": MIN_BLIND_HOLE_MIL,
            "max_blind_hole_mil": MAX_BLIND_HOLE_MIL,
        },
        "total_vias": len(all_vias),
        "total_blind_vias": len(blinds),
        "span_breakdown": span_counts,
        "pair_coverage": dict(pair_coverage),
        "closest_blind_pairs": {name: pair[1] for name, pair in closest_blind_pairs.items()},
        "jlc_blind_geometry_findings": (len(bad_hole_edge) + len(bad_ring) + len(bad_hole) + len(bad_hole_high)
                                       + len(bad_vv_hole_same) + sum(r["has_blind"] for r in bad_vv_hole_diff)),
        "measured_minimums": {
            "min_blind_cu_to_edge_mil": round(min(edge_cu_mils), 3) if edge_cu_mils else 0.0,
            "min_blind_cu_to_edge_mm": round(min(edge_cu_mils) * MM_PER_MIL, 4) if edge_cu_mils else 0.0,
            "min_blind_hole_to_edge_mil": round(min(edge_hole_mils), 3) if edge_hole_mils else None,
            "min_blind_hole_to_edge_mm": round(min(edge_hole_mils) * MM_PER_MIL, 6) if edge_hole_mils else None,
            "min_blind_ring_mil": round(min((v["ring_mil"] for v in blinds), default=0.0), 3),
            "min_blind_hole_mil": round(min((v["hole_mil"] for v in blinds), default=0.0), 3),
            "min_same_net_vv_cu_gap_mil": round(min(vv_same_cu), 3) if vv_same_cu else 0.0,
            "min_same_net_vv_hole_wall_mil": round(min(vv_same_hole), 3) if vv_same_hole else 0.0,
            "min_same_net_vv_hole_wall_mm": round(min(vv_same_hole) * MM_PER_MIL, 4) if vv_same_hole else 0.0,
            "min_diff_net_vv_cu_gap_mil": round(min(vv_diff_cu), 3) if vv_diff_cu else 0.0,
            "min_diff_net_vv_hole_wall_mil": round(min(vv_diff_hole), 3) if vv_diff_hole else 0.0,
            "min_diff_net_vv_hole_wall_mm": round(min(vv_diff_hole) * MM_PER_MIL, 4) if vv_diff_hole else 0.0,
        },
        "violations": {
            "jlc_blind_hole_edge_below_0p35mm": len(bad_hole_edge),
            "evt1_blind_copper_edge_guard_below_0p35mm": len(bad_copper_edge),
            "same_net_vv_cu_below_6mil": len(bad_vv_cu_same),
            "diff_net_vv_cu_below_6mil": len(bad_vv_cu_diff),
            "same_net_blind_hole_wall_below_0p13mm": len(bad_vv_hole_same),
            "diff_net_via_hole_wall_below_limit": len(bad_vv_hole_diff),
            "blind_under_annular_ring": len(bad_ring),
            "blind_under_hole": len(bad_hole),
            "blind_over_hole": len(bad_hole_high),
            "invalid_blind_layer_span": len(bad_span),
            "unqualified_concentric_stacks": len(stacked_review),
            "illegal_mech_through_vias": len(bad_mech),
            "total_v4_violations": total_v4_viols,
        },
        "violation_details": {
            "jlc_blind_hole_edge_below_0p35mm": bad_hole_edge,
            "evt1_blind_copper_edge_guard_below_0p35mm": bad_copper_edge,
            "same_net_vv_cu": bad_vv_cu_same,
            "diff_net_vv_cu": bad_vv_cu_diff,
            "same_net_vv_hole": bad_vv_hole_same,
            "diff_net_vv_hole": bad_vv_hole_diff,
            "ring": bad_ring,
            "hole_small": bad_hole,
            "hole_large": bad_hole_high,
            "span": bad_span,
            "stacked_review": stacked_review,
            "mechanical": bad_mech,
        },
        "fab_governance_blocked_items": [
            "6L_0p80mm_1plus4plus1_HDI_stackup_and_controlled_impedance_fab_EQ",
            "11_VIPPO_copper_fill_cap_sites_fab_EQ",
            "PCB3_U11_0p35mm_WLCSP_Tier1_2N2_Advanced_HDI_fab_EQ",
            "ANT1_ANT2_keepout_VNA_and_JBD_optical_camera_MECR01_signoff",
        ],
    }
    if board == "PCB3":
        base["u11_nrf5340_cmaa_95ball_audit"] = audit_u11_95ball_official(dump_path, u11_csv)
    return base


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epro", type=Path, required=True)
    p.add_argument("--dump-dir", type=Path, required=True)
    p.add_argument("--dump-suffix", default="-post.dump.json")
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()

    a.out_dir.mkdir(parents=True, exist_ok=True)
    arc = Archive(a.epro)
    full = {}
    for b in ("PCB1", "PCB2", "PCB3"):
        res = audit_board_v4(
            b, arc,
            a.dump_dir / f"{b}{a.dump_suffix}",
            conflict_csv=a.out_dir / f"{b}-conflict-matrix.csv",
            blind_csv=a.out_dir / f"{b}-v4-blind-via-audit.csv",
            u11_csv=(a.out_dir / "u11_nrf5340_cmaa_95ball_audit.csv") if b == "PCB3" else None,
        )
        full[b] = res
        v4 = res["v4_official_jlcpcb_hdi_audit"]
        print(f"\n=== {b} V4 JLCPCB APERTURE & EVT-1 COPPER GEOMETRY AUDIT ===")
        print("  by_classification:", json.dumps(res["by_classification"]))
        print("  v4_violations:", json.dumps(v4["violations"]))
        print("  v4_minimums:", json.dumps(v4["measured_minimums"]))
        if b == "PCB3":
            u11 = res["u11_nrf5340_cmaa_95ball_audit"]
            print("  U11 95-ball:", json.dumps(u11["escape_breakdown"]))
    (a.out_dir / "independent-dfm-v4-summary.json").write_text(
        json.dumps(full, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
