"""Verify either PCB3 U11.A5 ground dogbone from the PR52 native baseline."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import screen_escape as geo
import screen_u11_microvias as alternatives


def verify(source, spot):
    sys.path.insert(0, str(source / "u11"))
    sys.path.insert(0, str(source))
    from audit_r3_u11 import load, records
    from verify_pcb1_spur import point_to_segment, segment_distance

    geo.load, geo.records = load, records
    geo.point_to_segment, geo.segment_distance = point_to_segment, segment_distance

    native, = (source / "native").glob("*.epro2")
    dump = source / "verification/pcb3-restore-copper.json"
    rows, objects = geo.archive_copper(native, dump, source / "u11/r3-u11-95ball-native.csv")
    bounds = [(item, item.bounds) for item in objects]
    pcb = records(load(native).documents[alternatives.PCB])
    center = rows["A5"]["center"]
    expansion = pcb["RULE", '["RULE","SOLDER","solderMaskExpansion"]']["ruleContext"]

    if expansion["viaTopExpan"] != -1000 or expansion["padTopExpan"] != 2:
        raise ValueError("A5 calculation requires inherited ball mask and tented via defaults")
    plane_margin = alternatives.ground_plane_margin(alternatives.plane_shapes(pcb), spot)
    holes = alternatives.hole_objects(pcb)
    via = alternatives.make(spot, 4, (1, 15), bounds, holes, "GND")
    wire = geo.nearest(center, spot, 2, bounds, "GND", 25)
    mask_center_gap = min((math.dist(spot, pad["center"]) - pad["radius"] -
                           expansion["padTopExpan"], key) for key, pad in rows.items())
    inner_tracks = [(identity, item["netName"]) for (kind, identity), item in pcb.items()
                    if kind == "LINE" and item["layerId"] == 15]
    if not via["independent_nominal_screen"] or wire[0] < 6.02 or plane_margin < 11:
        raise ValueError("Proposed A5 geometry failed the independent copper screen")
    if mask_center_gap[0] - 2 < 0.5 or inner_tracks:
        raise ValueError("Proposed A5 geometry needs a more complete L2 or mask analysis")
    preset_blind_rule = pcb["RULE", '["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
    span, = [row for row in preset_blind_rule if row["name"] == "BV_L1_L2"]
    if (span["staLayerId"], span["endLayerId"]) != (1, 15):
        raise ValueError("Unexpected blind-via span")

    return {
        "scope": "Nominal geometry derived from PR52 top native archive and copper dump. "
                 "Requires native DRC, L2 connectivity and assembly/stackup EQ.",
        "r4_native_sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
        "r4_top_dump_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
        "ref": "U11.A5",
        "net": "GND",
        "start": center,
        "end": spot,
        "layer": 1,
        "width_mil": 4,
        "top_trace_gap_mil": round(wire[0], 6),
        "top_trace_nearest": wire[1],
        "via": {"drill_mil": 4, "diameter_mil": 10, "rule": span, **via},
        "l2_native_ground_pad_edge_to_fill_boundary_mil": round(plane_margin-5, 6),
        "closest_ball_mask": mask_center_gap[1],
        "hole_edge_to_mask_mil": round(mask_center_gap[0]-2, 6),
        "capture_copper_edge_to_mask_mil": round(mask_center_gap[0]-5, 6),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r4", type=Path)
    parser.add_argument("x", type=float)
    parser.add_argument("y", type=float)
    args = parser.parse_args()
    print(json.dumps(verify(args.r4, (args.x, args.y)), indent=2))
