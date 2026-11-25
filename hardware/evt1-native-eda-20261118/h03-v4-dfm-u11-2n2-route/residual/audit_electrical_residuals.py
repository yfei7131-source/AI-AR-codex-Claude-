#!/usr/bin/env python3
"""Reconcile the native PCB pad map and investigate inherited decap warnings."""

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from itertools import product
import json
from math import ceil, dist, floor
from pathlib import Path
import re
import sys

PACKAGE = Path(__file__).resolve().parents[2]
INHERITED = Path(__file__).resolve().parents[1] / "evidence"
PR46 = PACKAGE / "h03-u11-wlcsp-v3-dfm-route/evidence"
sys.path.insert(0, str(PACKAGE / "h02-native"))
from verify_h02 import parse_protel


BOARDS = {"PCB1": "M-MAIN-L", "PCB2": "M-OPT-BRIDGE", "PCB3": "M-AUD-R"}
LOCAL_LOOPS = {
    ("PCB1", "C21"): ("C_LDO_DVDD_OUT", "U6_CAM_DVDD", "1", "ldo-output"),
    ("PCB1", "C31"): ("C_U8_CAM_ISO1_A", "U8_CAM_ISO1", "24", "bypass"),
    ("PCB1", "C40"): ("C_U10_AMP_L_HF", "U10_AMP_L", "A2", "bypass"),
    ("PCB2", "C2"): ("C_AVDD_QUAL", "U_AVDD_SCHMITT", "3", "timing-rc"),
    ("PCB2", "C3"): ("C_AVDD_REQ_FILTER", "U_AVDD_SYS_PG", "3", "timing-rc"),
    ("PCB2", "C5"): ("C_AVDD_U_AVDD_EN_OD_V", "U_AVDD_EN_OD", "5", "bypass"),
    ("PCB2", "C8"): ("C_AVDD_U_AVDD_QUAL_V", "U_AVDD_QUAL", "5", "bypass"),
    ("PCB2", "C9"): ("C_AVDD_U_AVDD_SCHMITT_V", "U_AVDD_SCHMITT", "5", "bypass"),
    ("PCB2", "C10"): ("C_AVDD_U_AVDD_SYS_CLAMP_V", "U_AVDD_SYS_CLAMP", "4", "bypass"),
    ("PCB2", "C11"): ("C_AVDD_U_AVDD_SYS_PG_V", "U_AVDD_SYS_PG", "4", "bypass"),
    ("PCB2", "C12"): ("C_AVDD_U_AVDD_WD_V", "U_AVDD_WD", "5", "bypass"),
    ("PCB2", "C31"): ("C_LDO_OPT_IN", "U6_OPT_AVDD", "4", "conditional-optical-ldo"),
    ("PCB2", "C32"): ("C_LDO_OPT_OUT", "U6_OPT_AVDD", "1", "conditional-optical-ldo"),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def block_fields(text, components):
    attributes = {}
    for block in re.findall(r"^\[\n(.*?)^\]$", text, flags=re.MULTILINE | re.DOTALL):
        rows = block.splitlines()
        if rows[0] != "DESIGNATOR" or rows[1] in attributes:
            raise ValueError("unexpected or duplicated component in Protel2 component blocks")
        fields = {"designator": rows[1]}
        for token in ("FOOTPRINT", "Unique ID", "EVT1 Source Ref"):
            indices = [i for i, value in enumerate(rows) if value == token]
            if len(indices) != 1 or indices[0] + 1 >= len(rows):
                raise ValueError(f"ambiguous {token} for {rows[1]}")
            fields[token] = rows[indices[0] + 1]
        attributes[rows[1]] = fields
    if attributes.keys() != {c["designator"] for c in components}:
        raise ValueError("component attributes and Protel2 parser disagree")
    for component in components:
        attributes[component["designator"]].update(component)
    return attributes


def netlist_comparison(netlist, pcb):
    text = netlist.read_text(encoding="utf-8-sig")
    components, groups = parse_protel(text)
    schematic = block_fields(text, components)
    placed = {c["designator"]: c for c in pcb["components"]}
    if len(placed) != len(pcb["components"]):
        raise ValueError("duplicate PCB component designator in this board")
    common = schematic.keys() & placed.keys()
    expected = {}
    for net, members in groups:
        for item in members:
            if item in expected:
                raise ValueError(f"schematic component pin is repeated: {item}")
            expected[item] = net
    actual = defaultdict(set)
    for ref in common:
        for pad in placed[ref]["pads"]:
            if pad["net"]:
                actual[ref, pad["padNumber"]].add(pad["net"])
    diff = [
        {"ref": ref, "pin": pin, "schematicNet": expected.get((ref, pin)), "pcbNets": sorted(actual.get((ref, pin), []))}
        for ref, pin in sorted(expected.keys() | actual.keys())
        if ref in common and actual.get((ref, pin), set()) != ({expected[ref, pin]} if (ref, pin) in expected else set())
    ]
    names = {name for name, _ in groups}
    unknown_copper = {
        kind: sorted(row["primitiveId"] for row in pcb["copper"][kind] if row["net"] not in names)
        for kind in ("lines", "vias")
    }
    return {
        "protelNetGroups": len(groups), "placedComponentCount": len(placed),
        "placedNamedTerminalsCompared": len(actual),
        "schematicOnly": [schematic[ref] for ref in sorted(schematic.keys() - placed.keys())],
        "pcbOnly": sorted(placed.keys() - schematic.keys()),
        "placedUidMismatches": [
            {"ref": ref, "schematicUid": schematic[ref]["Unique ID"], "pcbUid": placed[ref]["uniqueId"]}
            for ref in sorted(common) if schematic[ref]["Unique ID"] != placed[ref]["uniqueId"]
        ],
        "placedPadNetMismatches": diff,
        "copperNetsAbsentFromSchematic": unknown_copper,
    }, schematic


def decap_review(board, checks, pcb, schematic, controlled):
    placed = {c["designator"]: c for c in pcb["components"]}
    source_refs = {v["EVT1 Source Ref"]: k for k, v in schematic.items()}
    findings = [row for row in checks["findings"] if row["type"] == "decap-too-far"]
    expected_refs = {ref for b, ref in LOCAL_LOOPS if b == board}
    if {row["designator"] for row in findings} != expected_refs or len(findings) != checks["summary"]["decapTooFar"]:
        raise ValueError(f"{board} decoupling warnings cannot be reconciled with the reviewed findings")
    reviews = []
    for row in findings:
        reference = row["designator"]
        source, owner, owner_pin, role = LOCAL_LOOPS[board, reference]
        if schematic[reference]["EVT1 Source Ref"] != source:
            raise ValueError(f"{board}/{reference} source identity changed")
        owner_ref = source_refs[owner]
        rail = row["net"]
        cap_pin, = (pad for pad in placed[reference]["pads"] if pad["padNumber"] == "1" and pad["net"] == rail)
        owner_pad, = (pad for pad in placed[owner_ref]["pads"] if pad["padNumber"] == owner_pin and pad["net"] == rail)
        actual_pin = controlled[BOARDS[board], owner, owner_pin]
        if controlled[BOARDS[board], source, "1"]["Net"] != rail or actual_pin["Net"] != rail:
            raise ValueError(f"{board}/{reference} source terminal contract changed")
        reviews.append({
            "ref": reference, "source": source, "net": rail, "role": role,
            "reported": row["message"],
            "actualLoopTarget": {"ref": owner_ref, "source": owner, "pin": owner_pin, "function": actual_pin["Pin_Function"]},
            "capUid": placed[reference]["uniqueId"], "capPrimitiveId": placed[reference]["primitiveId"],
            "capPad": {k: cap_pin[k] for k in ("x", "y", "layer", "primitiveId")},
            "loopTargetPad": {k: owner_pad[k] for k in ("x", "y", "layer", "primitiveId")},
            "ownerEuclideanDistanceMil": round(dist((cap_pin["x"], cap_pin["y"]), (owner_pad["x"], owner_pad["y"])), 2),
        })
    return reviews


def checked_input(path):
    return {"sha256": sha256(path.read_bytes()).hexdigest(), "relativePath": path.relative_to(PACKAGE).as_posix()}


def c11_same_side_screen(pcb, review):
    """Test a direct same-side placement envelope before considering any reroute."""
    cap, = (c for c in pcb["components"] if c["primitiveId"] == review["capPrimitiveId"])
    pad = review["capPad"]
    anchor = review["loopTargetPad"]
    points = pcb["outline"]["points"]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    if set(map(tuple, points)) != set(product((min_x, max_x), (min_y, max_y))) or cap["layer"] != anchor["layer"]:
        raise ValueError("PCB2 outline or same-side C11 placement premise changed")

    bbox = cap["bbox"]
    offsets = list(product((bbox["minX"] - cap["x"], bbox["maxX"] - cap["x"]),
                           (bbox["minY"] - cap["y"], bbox["maxY"] - cap["y"])))
    pad_offset = (pad["x"] - cap["x"], pad["y"] - cap["y"])
    occupied = [c["bbox"] for c in pcb["components"] if c["layer"] == cap["layer"] and c != cap]
    candidate_count = 0
    surviving_candidates = []
    for turn in range(4):
        def rotate(point):
            x, y = point
            return ((x, y), (-y, x), (-x, -y), (y, -x))[turn]

        ax, ay = rotate(pad_offset)
        corners = [rotate(point) for point in offsets]
        left, right = min(x for x, y in corners), max(x for x, y in corners)
        bottom, top = min(y for x, y in corners), max(y for x, y in corners)
        tx, ty = anchor["x"] - ax, anchor["y"] - ay
        for x, y in product(range(ceil(max(min_x - left, tx - 100)), floor(min(max_x - right, tx + 100)) + 1),
                            range(ceil(max(min_y - bottom, ty - 100)), floor(min(max_y - top, ty + 100)) + 1)):
            if dist((x, y), (tx, ty)) > 100:
                continue
            candidate_count += 1
            if any(o["minX"] < x + right and o["maxX"] > x + left and
                   o["minY"] < y + top and o["maxY"] > y + bottom for o in occupied):
                continue
            surviving_candidates.append([x, y, turn * 90])
    return {"gridMil": 1, "powerToVddMaxMil": 100, "candidatesInOutlineAndWithinDistance": candidate_count,
            "componentBboxClearCandidates": surviving_candidates}


def audit():
    with (PACKAGE / "Inputs/effective_netlist.csv").open(encoding="utf-8-sig", newline="") as stream:
        controlled = {(r["Board"], r["RefDes"], r["Pin"]): r for r in csv.DictReader(stream)}
    report = {"verification": "OFFLINE_READBACK_AUDIT", "manufacturing": "BLOCKED", "boards": {}}
    for board, source in BOARDS.items():
        netlist = INHERITED / "erc-3board/board-netlists" / f"{source}.net"
        baseline_netlist = PR46 / "erc-3board/board-netlists" / netlist.name
        dump = INHERITED / "reimport-verify" / f"{board}-reimport.dump.json"
        dfm = INHERITED / "post-route" / f"{board}-dfm-check.json"
        drc = INHERITED / "reimport-verify" / f"{board}-drc-reimport.json"
        baseline_drc = PR46 / "reimport-verify" / drc.name
        pcb = read(dump)
        comparison, schematic = netlist_comparison(netlist, pcb)
        dfm_read = read(dfm)
        reviews = decap_review(board, dfm_read, pcb, schematic, controlled)
        before_drc, after_drc = (read(path) for path in (baseline_drc, drc))
        for item in (before_drc, after_drc):
            if Counter(row["rule"] for row in item["violations"]) != item["counts"] or item["total"] != len(item["violations"]):
                raise ValueError(f"{board} native strict DRC is incomplete")
        report["boards"][board] = {
            "source": source, "protelByteIdenticalToPr46": netlist.read_bytes() == baseline_netlist.read_bytes(),
            "netlistCrosscheck": comparison,
            "strictDrcPr46": before_drc["counts"], "strictDrcInherited": after_drc["counts"],
            "nativeDuplicateSegmentsInherited": dfm_read["summary"]["duplicateSegments"],
            "decouplingReview": reviews,
            "inputs": [checked_input(path) for path in (netlist, baseline_netlist, dump, dfm, drc, baseline_drc)],
        }
        if board == "PCB2":
            c11, = (row for row in reviews if row["ref"] == "C11")
            report["boards"][board]["c11SingleMoveScreen"] = c11_same_side_screen(pcb, c11)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
