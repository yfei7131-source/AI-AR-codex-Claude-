#!/usr/bin/env python3
"""Build an offline, board-scoped H02 catalog and footprint reconciliation."""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
import json


HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PR33 = BASE / "kimi-h02-return"
CAPTURE = PR33 / "partial-current-coherent"

# Keep only individually assigned manufacturer identifiers from the effective BOM.
# New values need review, even when they look syntactically like a part number.
EXACT = frozenset("""
    2450AT18B100E APHD1608LCGCK ASADV-48.000MHZ-LC-T
    BM28B0.6-10DS/2-0.35V(53) BM28B0.6-16DS/2-0.35V(53)
    BM28B0.6-24DS/2-0.35V(53) BM28B0.6-30DS/2-0.35V(53)
    BQ25170DSGR BQ25180YBGR DFE21CCN2R2MELL ESP32-S3-PICO-1-N8R8
    ICM-42688-P IM69D130V01XTSA1 INA185A4IDRLR LM66200DRLR LTC6993IS6-2#TRPBF
    MAX98357AEWL+T PCA9306DQER SN74AXC4T245RSVR SN74AXC8T245RJWR
    SN74LVC1G07DPWR SN74LVC1G175DCKR SN74LVC1G3157DSFR SN74LVC2G17DCKR
    SN74LVC2T45DCUR TLV7042DSGR TLV75512PDQNR TLV75518PDQNR TLV75528PDQNR
    TPS389018DSET TPS389025DSET TPS62840DLCR TPS63805YFFR
    iCE40UP5K-UWG30ITR nRF5340-CMAA-R7
""".split())
PACKAGED_TYPES = {
    "PMV65XP": "Nexperia; public packaging example PMV65XP,215. Controlled BOM selects the device type.",
    "74LVC2G07GS": "Nexperia SOT1202. Public orderable code 74LVC2G07GS,132; no packaging edit in this plan.",
}
INDIVIDUAL_BLOCKERS = {
    "R_SENSE": "Panasonic ERA2AEB range starts at 47 ohms; inherited 2R2 token is not an accepted 2.20-ohm order code.",
    "D_XREQ": "Inherited ROHM RB521S-30 is a type; orderable RB521S-30TE61 is Last Time Buy. Approved exact part and A/K mapping pending.",
    "Y2_BLE": "Epson FA-128 candidate descriptor; final orderable suffix, load, ESR and tolerance await confirmation.",
    "Q_CHG_MUTE_R": "2N7002 is a multi-manufacturer designation; selected maker and ordering package are absent.",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def group(rows, key):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped


def unique(rows, key):
    grouped = group(rows, key)
    duplicates = [identity for identity, items in grouped.items() if len(items) != 1]
    if duplicates:
        raise ValueError(f"duplicate identities: {duplicates}")
    return {identity: items[0] for identity, items in grouped.items()}


def classification(part, ref, pcb_use):
    value = part["MPN"]
    if pcb_use == "EXTERNAL" or pcb_use == "SCHEMATIC_ONLY":
        return "EXTERNAL", "", "Assembly or logical boundary; do not map into the PCB catalog."
    if ref.startswith("TP_"):
        return "PCB_COPPER", "", "Copper or probe fixture description; no manufacturer ID."
    if ref in INDIVIDUAL_BLOCKERS:
        return "ORDERING_BLOCKED", "", INDIVIDUAL_BLOCKERS[ref]
    if value in EXACT:
        return "EXACT_ID", value, "Individually assigned manufacturer identifier from the effective BOM."
    if value in PACKAGED_TYPES:
        return "PACKAGED_TYPE", value, PACKAGED_TYPES[value]
    if "MPN_TBD" in value:
        return "SELECTION_BLOCKED", "", "Effective BOM still needs part selection."
    if ref.startswith(("C_", "R_", "NRF_C", "NRF_L", "NRF_CT")):
        return "PASSIVE_DESCRIPTOR", "", "Value, tolerance, size, or cluster recipe to preserve as design data."
    raise ValueError(f"unreviewed effective BOM value for {ref} ({pcb_use}): {value}")


def read_capture(path):
    manifest = read_json(path / "board_pages.json")
    observed = {}
    for board, pages in manifest["boards"].items():
        for page in pages:
            raw = read_json(path / "pins" / f"{page}.json")
            context = raw["context"]
            if not raw["ok"] or context.get("projectUuid") != manifest["project_id"] or context.get("documentUuid") != page:
                raise ValueError(f"raw capture context does not match manifest: {board}/{page}")
            for part in raw["result"]["components"]:
                if part.get("componentType") != "part" or not part.get("designator"):
                    continue
                key = board, part["designator"]
                if key in observed:
                    raise ValueError(f"duplicate designator within a board: {key}")
                observed[key] = (page, part)
    return manifest["project_id"], observed


def build(path):
    bom = unique(read_csv(BASE / "Inputs/effective_bom.csv"), lambda r: r["Item_ID"])
    fp_map = unique(read_csv(BASE / "FOOTPRINT_MAP.csv"), lambda r: (r["Board"], r["RefDes"]))
    board_terms = group(read_csv(BASE / "kicad/CAD_TERMINALS.csv"), lambda r: (r["Board"], r["CAD_Reference"]))
    source_terms = group(read_csv(BASE / "Inputs/effective_netlist.csv"), lambda r: (r["Board"], r["RefDes"]))
    legacy = unique(read_json(PR33 / "repair-plan.json")["records"], lambda r: (r["board"], r["cadReference"]))
    capture_project, observed = read_capture(path)
    # The native capture has other graphical part objects too; select the controlled references.
    if board_terms.keys() - observed.keys():
        raise ValueError(f"board-scoped components absent from capture: {sorted(board_terms.keys() - observed.keys())}")
    if board_terms.keys() != legacy.keys() or fp_map.keys() != source_terms.keys():
        raise ValueError("catalog, native repair plan or source footprint coverage differs")

    records = []
    for (board, cad_ref), pins in sorted(board_terms.items()):
        key = board, cad_ref
        first = pins[0]
        ref = first["Source_RefDes"]
        part = bom[first["BOM_Line"]]
        fp = fp_map[(board, ref)]
        if any((r["Source_RefDes"], r["BOM_Line"], r["PCB_Use"], r["Footprint"]) !=
               (ref, first["BOM_Line"], first["PCB_Use"], first["Footprint"]) for r in pins):
            raise ValueError(f"unstable controlled identity: {key}")
        if {r["Pin"] for r in pins} != set(fp["Pin_Identifiers"].split()):
            raise ValueError(f"controlled footprint pin list differs: {key}")
        if fp["Footprint"] != first["Footprint"] or bool(fp["Footprint"]) != (fp["Status"] == "PASS"):
            raise ValueError(f"controlled footprint assignment differs: {key}")
        pcb_use = first["PCB_Use"]
        category, manufacturer_id, reason = classification(part, ref, pcb_use)
        old_id = legacy[key]["controlled"]["mpn"]
        if legacy[key]["sourceReference"] != ref:
            raise ValueError(f"historical and current source references differ: {key}")
        page, native = observed[key]
        actual_id = native.get("manufacturerId") or ""
        if manufacturer_id and manufacturer_id == actual_id:
            action = "KEEP_ID"
        elif manufacturer_id:
            action = "RECONCILE_CONTROLLED_ID"
        elif old_id and actual_id == old_id:
            action = "CLEAR_LEGACY_DESCRIPTOR_IF_LIVE_MATCHES"
        elif actual_id:
            action = "REVIEW_OTHER_NATIVE_ID"
        else:
            action = "KEEP_ID_EMPTY"

        dnp = any("DNP" in r["Pin_Function"] for r in source_terms[board, ref])
        records.append({
            "board": board, "cadReference": cad_ref, "sourceReference": ref,
            "bomLine": first["BOM_Line"], "category": category, "reason": reason,
            "controlledValue": part["MPN"], "source": part["Datasheet_URL"],
            "controlledManufacturerId": manufacturer_id, "legacyManufacturerIdTarget": old_id,
            "observedManufacturerId": actual_id, "catalogReviewAction": action,
            "capturePage": page, "captureUniqueId": native.get("uniqueId"),
            "capturePrimitiveId": native["primitiveId"], "sourceDnp": dnp, "pcbUse": pcb_use,
            "kicadFootprint": fp["Footprint"], "footprintSourceStatus": fp["Status"],
            "footprintPins": fp["Pin_Identifiers"].split(),
            "observedNativeFootprint": native.get("footprint"),
            "nativeBindingAction": "RESOLVE_AND_COMPARE_NUMBERED_COPPER" if fp["Footprint"] else "KEEP_BLOCKED",
        })

    legacy_matched = [r for r in records if r["legacyManufacturerIdTarget"] and
                      r["observedManufacturerId"] == r["legacyManufacturerIdTarget"]]
    legacy_non_catalog = [r for r in legacy_matched if not r["controlledManufacturerId"]]
    return {
        "scope": "Offline reconciliation. Historical observations are mixed-page evidence and require live preflight.",
        "status": "PASS",
        "nativeWriteAuthorized": False,
        "captureProject": capture_project,
        "counts": {
            "boardComponents": len(records), "categories": dict(sorted(Counter(r["category"] for r in records).items())),
            "catalogActions": dict(sorted(Counter(r["catalogReviewAction"] for r in records).items())),
            "legacyControlled": sum(bool(r["legacyManufacturerIdTarget"]) for r in records),
            "legacyTextMatches": len(legacy_matched), "legacyNonCatalogMatches": len(legacy_non_catalog),
            "legacyNonCatalogUniqueStrings": len({r["legacyManufacturerIdTarget"] for r in legacy_non_catalog}),
            "kicadPopulatedPadAudited": sum(bool(r["kicadFootprint"]) for r in records),
            "kicadBlocked": sum(not r["kicadFootprint"] for r in records),
            "externalUnmappedCamera": len(fp_map) - len(records),
            "nativeBindingsVerified": 0,
        },
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=CAPTURE, help="Board-scoped normalized pins capture")
    parser.add_argument("--output", type=Path, default=HERE / "catalog-plan.json", help="Write or verify this plan")
    parser.add_argument("--check", action="store_true", help="Require the checked-in output to match")
    args = parser.parse_args()
    plan = build(args.capture)
    data = (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != data:
            raise SystemExit(f"FAIL: {args.output.name} differs from the controlled inputs")
    else:
        args.output.write_bytes(data)
    print(json.dumps(plan["counts"], indent=2))


if __name__ == "__main__":
    main()
