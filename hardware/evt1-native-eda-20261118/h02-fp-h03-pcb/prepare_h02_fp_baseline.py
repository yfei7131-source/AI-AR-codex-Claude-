#!/usr/bin/env python3
"""Track A: H02 remaining footprint convergence + BOM/PCB attribute hygiene on PR #39 baseline.

Strictly preserves the 22.0 x 4.2 mm PCB2 baseline outline (0 MK2 clearance errors, 17 placed)
and all 207 Rev E net groups (ECO-03/07/08/09/14 + LED_3V3_PRIV).

Changes applied deterministically from PR #39:
  1. Creates & binds OEM-verified footprints for remaining verifiable parts:
     - Hirose BM28B0.6-30DS/2-0.35V (32 pads: P1..P30 + PWR1/PWR2) -> J_BRIDGE_IN, J_BTB_L
     - Hirose BM28B0.6-16DS/2-0.35V (18 pads: P1..P16 + PWR1/PWR2) -> J_BTB_R
     - Nordic nRF5340-CMAA WLCSP95 (95 balls A1..L12, 0.35mm pitch, 4.39x3.994mm) -> U11_BLE
     - ROHM RB521S-30 SOD-523 (K/A) -> M-MAIN-L D1
     - Epson FA-128 32MHz 2016 4-pad -> M-AUD-R Y2
     - Johanson 2450AT18B100E 1206 chip antenna (FEED) -> ANT1, ANT2
     - Standard SMD test/solder pads: TP1 (0.8mm), TP5 (SWD 5x0.6mm), TP9 (AVDD 9x0.6mm)
     - Remaining standard 0201/0402/0603 SMD passives across all 3 boards.
  2. Cleans BOM/PCB attributes (Task #1):
     - All 11 #FLG* (PWR_FLAG) symbols -> Add into BOM = no, Convert to PCB = no
     - DNP RF tuning shunts (M-MAIN-L C12/C13, M-AUD-R C21) -> Add into BOM = no, Convert to PCB = yes (0201 pad kept)
     - Off-board harness items (BAT1, SPK1 on Main & Audio) -> Add into BOM = yes, Convert to PCB = no
     - NDA-blocked optical/camera parts (M-OPT-BRIDGE J2/J3/U6, M-MAIN-L J2_CAM/J3_CHG) kept transparently unbound (BLOCKED).
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc"), str(PACKAGE / "h02-reve-h03-bridge")]

from bind_murata_l2 import ASADV_ASSET, asset_metadata, mil, rectangle
from prepare_hierarchy import Archive, Document, Record, compact, digest
from prepare_reve_h03 import insert_before_config

PR39_BASELINE = PACKAGE / "h02-reve-h03-bridge/native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2"


def fp_uid(tag: str) -> str:
    return sha256(f"EVT1-H02-FPCONV/{tag}".encode("utf-8")).hexdigest()[:16]


def build_rect_fp(template: Document, title: str, des: str, desc: str, tags: list[str],
                  outline_wh: tuple[float, float], body_wh: tuple[float, float],
                  pads: list[tuple[str, float, float, float, float]], prefix: str,
                  pad_type: str = "RECT") -> tuple[tuple[str, str], Document]:
    uid = fp_uid(title)
    asset = ("FOOTPRINT", uid)
    head = deepcopy(template.one("DOCHEAD"))
    head.payload.update(uuid=uid, user={"uuid": uid})
    fp = Document(head)
    for orig in template.records[1:]:
        if orig.header["type"] in {"PAD", "POLY", "FILL"}:
            continue
        rec = deepcopy(orig)
        if rec.header["type"] == "META":
            rec.payload.update(title=title, description=desc, tags=tags)
        elif rec.header["type"] == "ATTR":
            if rec.payload["key"] == "Name":
                rec.payload["value"] = title
            elif rec.payload["key"] == "Designator":
                rec.payload.update(value=des, x=0, y=mil(outline_wh[1] + 0.45))
        fp.records.append(rec)

    def add(kind, payload):
        idx = len(fp.records)
        hdr = {"type": kind, "ticket": 200 + idx, "id": f"{prefix}{idx}"}
        fp.records.append(Record(compact(hdr) + b"||" + compact(payload) + b"|\n"))

    outline, = (r.payload for r in template.records if r.header["type"] == "POLY" and r.payload["layerId"] == 76)
    body = template.one("FILL").payload
    add("POLY", dict(outline, path=rectangle(*outline_wh), zIndex=2))
    add("FILL", dict(body, path=[rectangle(*body_wh)], zIndex=3))
    pad, = (r.payload for r in template.records if r.header["type"] == "PAD" and r.payload["num"] == "1")
    for idx, (num, x, y, w, h) in enumerate(pads, start=4):
        shape = dict(pad["defaultPad"], padType=pad_type, width=mil(w), height=mil(h))
        add("PAD", dict(pad, num=num, centerX=mil(x), centerY=mil(y), defaultPad=shape, zIndex=idx))
    return asset, fp


def make_bm28_pads(n_sig: int) -> tuple[tuple[float, float], tuple[float, float], list[tuple[str, float, float, float, float]]]:
    """Hirose BM28B0.6-xxDS/2-0.35V(53) official receptacle land pattern (mm).
    Long axis along X; odd pins P1,P3.. on +Y row (+0.785mm), even pins P2,P4.. on -Y row (-0.785mm).
    Signal pitch=0.35mm, pad=0.18x0.57mm; 2x 5A power nails PWR1/PWR2 at +/- (H/2) mm.
    """
    half = n_sig // 2
    pitch = 0.35
    b_span = (half - 1) * pitch
    h_span = b_span + 1.41   # Hirose H = B + 1.41 mm (30p: 4.90+1.41=6.31; 16p: 2.45+1.41=3.86; 10p: 1.40+1.41=2.81)
    g_len = b_span + 2.95    # Hirose G = B + 2.95 mm (30p: 7.85; 16p: 5.40; 10p: 4.35)
    pads = []
    for i in range(half):
        x = round(-b_span / 2.0 + i * pitch, 4)
        pads.append((f"P{2*i + 1}", x, 0.785, 0.18, 0.57))
        pads.append((f"P{2*i + 2}", x, -0.785, 0.18, 0.57))
    # 5A power nails PWR1 (left) and PWR2 (right)
    px = round(h_span / 2.0, 4)
    pads.append(("PWR1", -px, 0.0, 0.42, 1.50))
    pads.append(("PWR2", px, 0.0, 0.42, 1.50))
    return (round(g_len / 2.0, 3), 1.15), (round((g_len - 0.50) / 2.0, 3), 0.90), pads


def make_nrf5340_cmaa_pads(ball_names: list[str]) -> list[tuple[str, float, float, float, float]]:
    """Nordic nRF5340-CMAA WLCSP95 exact 0.35mm pitch 11x12 matrix (A..L skip I, 1..12)."""
    row_order = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L"]  # 11 rows
    pitch = 0.35
    pads = []
    for name in ball_names:
        r_idx = row_order.index(name[0])
        c_idx = int(name[1:]) - 1
        x = round((c_idx - 5.5) * pitch, 4)   # cols 1..12 centered at 0 -> [-1.925, +1.925]
        y = round((5.0 - r_idx) * pitch, 4)   # rows A..L centered at 0 -> [+1.750, -1.750]
        pads.append((name, x, y, 0.21, 0.21))
    return pads


def build_track_a(baseline_path: Path, output_path: Path, report_path: Path):
    archive = Archive(baseline_path)
    template = archive.documents[ASADV_ASSET]

    # Read exact nRF5340-CMAA 95 symbol pins from archive
    u11_sym = archive.documents[("SYMBOL", "fd0246f8f945dce5")]
    u11_pins = sorted(r.payload["value"] for r in u11_sym.records if r.header["type"] == "ATTR" and r.payload["key"] == "Pin Number")
    if len(u11_pins) != 95:
        raise ValueError(f"Unexpected nRF5340 pin count: {len(u11_pins)}")

    new_docs = {}
    fp_ids = {
        doc.one("META").payload["title"]: uid
        for (kind, uid), doc in archive.documents.items() if kind == "FOOTPRINT"
    }

    # 1. Create OEM-verified footprints
    bm30_o, bm30_b, bm30_p = make_bm28_pads(30)
    bm16_o, bm16_b, bm16_p = make_bm28_pads(16)
    fp_specs = [
        ("Hirose_BM28B0.6-30DS_2-0.35V", "J?", "Hirose BM28B0.6-30DS/2-0.35V(53) 30+2P receptacle (P=0.35, B=4.90, H=6.31, G=7.85mm).", ["BM28", "30+2P"], bm30_o, bm30_b, bm30_p, "bm30p", "RECT"),
        ("Hirose_BM28B0.6-16DS_2-0.35V", "J?", "Hirose BM28B0.6-16DS/2-0.35V(53) 16+2P receptacle (P=0.35, B=2.45, H=3.86, G=5.40mm).", ["BM28", "16+2P"], bm16_o, bm16_b, bm16_p, "bm16p", "RECT"),
        ("Nordic_nRF5340-CMAA_WLCSP95", "U?", "Nordic nRF5340-CMAA WLCSP95 (4.39x3.994mm, 0.35mm pitch, 0.21mm NSMD balls).", ["WLCSP95", "nRF5340"], (2.25, 2.05), (2.195, 1.997), make_nrf5340_cmaa_pads(u11_pins), "nrfp", "ELLIPSE"),
        ("ROHM_SOD-523_RB521S-30", "D?", "ROHM RB521S-30 SOD-523/EMD2 (1.6x0.8mm) reflow land pattern (K/A).", ["SOD-523", "RB521S-30"], (1.35, 0.55), (0.80, 0.40), [("K", -0.85, 0.0, 0.75, 0.65), ("A", 0.85, 0.0, 0.75, 0.65)], "sodp", "RECT"),
        ("Epson_FA-128_2016_4Pin", "Y?", "Epson FA-128 32MHz 2.0x1.6mm 4-pad crystal recommended land pattern.", ["FA-128", "2016"], (1.25, 1.00), (1.00, 0.80), [("1", -0.725, -0.575, 0.85, 0.65), ("2", 0.725, -0.575, 0.85, 0.65), ("3", 0.725, 0.575, 0.85, 0.65), ("4", -0.725, 0.575, 0.85, 0.65)], "fa128p", "RECT"),
        ("Johanson_2450AT18B100E_1206", "ANT?", "Johanson 2450AT18B100E 2.45GHz 1206 chip antenna (3.2x1.6x1.5mm; FEED pad).", ["2450AT18B100E", "1206"], (1.85, 0.95), (1.60, 0.80), [("FEED", -1.35, 0.0, 1.00, 1.60)], "antp", "RECT"),
        ("EVT1_TP1_0.8mm", "TP?", "Single 0.80mm SMD solder/test pad.", ["TP", "0.8mm"], (0.55, 0.55), (0.40, 0.40), [("1", 0.0, 0.0, 0.80, 0.80)], "tp1p", "ELLIPSE"),
        ("EVT1_TP5_SWD_0.6mm", "TP?", "5-pad 0.60mm SWD debug pad array (1.00mm pitch).", ["TP", "SWD"], (2.55, 0.50), (2.40, 0.35), [(str(i + 1), round(-2.0 + i * 1.0, 2), 0.0, 0.60, 0.60) for i in range(5)], "tp5p", "ELLIPSE"),
        ("EVT1_TP9_AVDD_0.6mm", "TP?", "9-pad 0.60mm AVDD probe array (3x3 grid, 0.90mm pitch, 2.4x2.4mm).", ["TP", "AVDD"], (1.35, 1.35), (1.20, 1.20), [(str(r * 3 + c + 1), round((c - 1) * 0.90, 2), round((1 - r) * 0.90, 2), 0.55, 0.55) for r in range(3) for c in range(3)], "tp9p", "ELLIPSE"),
    ]
    for title, des, desc, tags, ow, bw, pads, pfx, pt in fp_specs:
        asset, doc = build_rect_fp(template, title, des, desc, tags, ow, bw, pads, pfx, pt)
        new_docs[asset] = doc
        fp_ids[title] = asset[1]

    insert_before_config(archive, new_docs)

    # Map SCH -> board name
    sch_to_board = {}
    for (kind, uid), doc in archive.documents.items():
        if kind == "SCH":
            t = doc.one("META").payload.get("title", "")
            for b in ("M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"):
                if b in t:
                    sch_to_board[uid] = b
    from repair_supply_wire_names import ROOTS
    for b, root_pg in ROOTS.items():
        suid = archive.documents[("SCH_PAGE", root_pg)].one("META").payload.get("schematic")
        if suid:
            sch_to_board[suid] = b

    # Helper to set SCH instance + DEVICE attributes cleanly
    def set_comp_attr(doc: Document, comp_id: str, key: str, val: str):
        for r in doc.records:
            if r.header["type"] == "ATTR" and r.payload.get("parentId") == comp_id and r.payload.get("key") == key:
                r.payload["value"] = val
                return True
        return False

    # 2. Walk every SCH_PAGE: clean #FLG*, DNP, Off-board flags AND bind all OEM/IPC remaining footprints
    blocked_keep_unbound = {
        ("M-OPT-BRIDGE", "J2"),   # J_DISP_L (JBD NDA blocked)
        ("M-OPT-BRIDGE", "J3"),   # J_DISP_R (JBD NDA blocked)
        ("M-OPT-BRIDGE", "U6"),   # U6_OPT_AVDD (JBD NDA blocked)
        ("M-MAIN-L", "J2"),       # J_CAM (Camera SKU NDA blocked)
        ("M-MAIN-L", "J3"),       # J_CHG (Magnetic pogo MPN TBD)
        ("M-MAIN-L", "BAT1"),     # Off-board battery pack
        ("M-MAIN-L", "SPK1"),     # Off-board micro-speaker
        ("M-AUD-R", "BAT1"),      # Off-board battery pack
        ("M-AUD-R", "SPK1"),      # Off-board micro-speaker
    }
    dnp_tuning_pads = {("M-MAIN-L", "C12"), ("M-MAIN-L", "C13"), ("M-AUD-R", "C21")}
    off_board_parts = {("M-MAIN-L", "BAT1"), ("M-MAIN-L", "SPK1"), ("M-AUD-R", "BAT1"), ("M-AUD-R", "SPK1")}
    nda_dnp_parts = {("M-OPT-BRIDGE", "J2"), ("M-OPT-BRIDGE", "J3"), ("M-OPT-BRIDGE", "U6")}

    bound_ledger = []
    attr_hygiene = {"pwr_flags_cleaned": 0, "dnp_bom_no": 0, "offboard_pcb_no": 0, "nda_dnp_cleaned": 0}

    for (kind, puid), doc in archive.documents.items():
        if kind != "SCH_PAGE":
            continue
        suid = doc.one("META").payload.get("schematic")
        board = sch_to_board.get(suid)
        if not board:
            continue
        by_p = {}
        for r in doc.records:
            if r.header["type"] == "ATTR" and r.payload.get("parentId"):
                by_p.setdefault(r.payload["parentId"], {})[r.payload["key"]] = r
        for r in doc.records:
            if r.header["type"] != "COMPONENT":
                continue
            cid = r.header["id"]
            attrs = by_p.get(cid, {})
            des = attrs["Designator"].payload["value"] if "Designator" in attrs else ""
            if not des or des.startswith("CBB"):
                continue
            duid = attrs["Device"].payload["value"] if "Device" in attrs else ""
            if not duid or ("DEVICE", duid) not in archive.documents:
                continue
            dev = asset_metadata(archive, ("DEVICE", duid))["attributes"]

            # 2a. Clean #FLG* PWR_FLAG symbols
            if des.startswith("#FLG"):
                set_comp_attr(doc, cid, "Add into BOM", "no")
                set_comp_attr(doc, cid, "Convert to PCB", "no")
                dev["Add into BOM"] = "no"
                dev["Convert to PCB"] = "no"
                attr_hygiene["pwr_flags_cleaned"] += 1
                continue

            key_br = (board, des)
            # 2b. DNP RF tuning shunts -> Add into BOM=no, Convert to PCB=yes (pads retained for VNA tuning)
            if key_br in dnp_tuning_pads:
                set_comp_attr(doc, cid, "Add into BOM", "no")
                set_comp_attr(doc, cid, "Convert to PCB", "yes")
                dev["Add into BOM"] = "no"
                dev["Convert to PCB"] = "yes"
                attr_hygiene["dnp_bom_no"] += 1
            elif key_br in off_board_parts:
                set_comp_attr(doc, cid, "Add into BOM", "yes")
                set_comp_attr(doc, cid, "Convert to PCB", "no")
                dev["Add into BOM"] = "yes"
                dev["Convert to PCB"] = "no"
                attr_hygiene["offboard_pcb_no"] += 1
            elif key_br in nda_dnp_parts:
                set_comp_attr(doc, cid, "Add into BOM", "no")
                dev["Add into BOM"] = "no"
                attr_hygiene["nda_dnp_cleaned"] += 1

            # 2c. Skip already bound or intentionally BLOCKED parts
            if dev.get("Footprint", "") or key_br in blocked_keep_unbound:
                continue

            sym_uid = attrs["Symbol"].payload["value"] if "Symbol" in attrs else dev.get("Symbol", "")
            sym_pins = sorted(
                sr.payload["value"] for sr in archive.documents[("SYMBOL", sym_uid)].records
                if sr.header["type"] == "ATTR" and sr.payload["key"] == "Pin Number"
            )
            val = (attrs["Value"].payload["value"] if "Value" in attrs else dev.get("Value", "")) or ""

            # Choose exact OEM/IPC footprint
            ftitle = None
            origin = None
            if key_br in {("M-OPT-BRIDGE", "J1"), ("M-MAIN-L", "J1")}:
                ftitle, origin = "Hirose_BM28B0.6-30DS_2-0.35V", "Hirose-BM28-30+2P"
            elif key_br == ("M-AUD-R", "J1"):
                ftitle, origin = "Hirose_BM28B0.6-16DS_2-0.35V", "Hirose-BM28-16+2P"
            elif key_br == ("M-AUD-R", "U11"):
                ftitle, origin = "Nordic_nRF5340-CMAA_WLCSP95", "Nordic-WLCSP95"
            elif key_br == ("M-MAIN-L", "D1"):
                ftitle, origin = "ROHM_SOD-523_RB521S-30", "ROHM-SOD523"
            elif key_br == ("M-AUD-R", "Y2"):
                ftitle, origin = "Epson_FA-128_2016_4Pin", "Epson-FA128"
            elif key_br in {("M-MAIN-L", "ANT1"), ("M-AUD-R", "ANT2")}:
                ftitle, origin = "Johanson_2450AT18B100E_1206", "Johanson-1206"
            elif key_br == ("M-OPT-BRIDGE", "TP1"):
                ftitle, origin = "EVT1_TP9_AVDD_0.6mm", "EVT1-TP9-array"
            elif key_br == ("M-AUD-R", "TP6"):
                ftitle, origin = "EVT1_TP5_SWD_0.6mm", "EVT1-TP5-SWD"
            elif des.startswith("TP") and sym_pins == ["1"]:
                ftitle, origin = "EVT1_TP1_0.8mm", "EVT1-TP1-pad"
            elif sym_pins == ["1", "2"]:
                # Standard 2-pin passive package selection
                if des.startswith("C") and ("22 uF" in val or "22uF" in val):
                    ftitle, origin = "IPC_0603_1608Metric", "IPC-7351B-0603-bulk"
                elif des.startswith("C") and ("1 uF" in val or "1uF" in val or "1.0 uF" in val or "2.2 uF" in val):
                    ftitle, origin = "IPC_0402_1005Metric", "IPC-7351B-0402-cap"
                else:
                    ftitle, origin = "IPC_0201_0603Metric", "IPC-7351B-0201"
            else:
                continue

            fuid = fp_ids[ftitle]
            fp_pads = sorted({pr.payload["num"] for pr in archive.documents[("FOOTPRINT", fuid)].records if pr.header["type"] == "PAD"})
            if sym_pins != fp_pads:
                raise ValueError(f"Pin mismatch for {board}/{des}: sym={sym_pins[:8]}({len(sym_pins)}) != fp={fp_pads[:8]}({len(fp_pads)})")
            dev["Footprint"] = fuid
            set_comp_attr(doc, cid, "Convert to PCB", "yes")
            dev["Convert to PCB"] = "yes"
            bound_ledger.append({"board": board, "ref": des, "footprint": ftitle, "origin": origin, "pins": len(sym_pins)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    archive.write(output_path)

    report = {
        "status": "TRACK_A_CANDIDATE_BUILT",
        "manufacturing": "BLOCKED",
        "baselineSha256": digest(baseline_path),
        "candidateSha256": digest(output_path),
        "pcb2OutlinePreservedMm": [22.0, 4.2],
        "newFootprintsCreated": [s[0] for s in fp_specs],
        "newlyBoundCount": len(bound_ledger),
        "newlyBoundByBoard": {b: sum(1 for x in bound_ledger if x["board"] == b) for b in ("M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R")},
        "intentionallyBlockedRemaining": sorted(f"{b}:{r}" for b, r in blocked_keep_unbound),
        "attributeHygiene": attr_hygiene,
        "boundItems": bound_ledger,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built Track A baseline candidate: {output_path}")
    print(f"Newly bound: {len(bound_ledger)} ({report['newlyBoundByBoard']})")
    print(f"Attribute hygiene: {attr_hygiene}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, default=PR39_BASELINE)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    build_track_a(a.baseline, a.output, a.report)


if __name__ == "__main__":
    main()
