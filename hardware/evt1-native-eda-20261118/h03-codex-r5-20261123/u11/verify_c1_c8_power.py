"""Check an optional PCB3 1V8 top-to-bottom bridge and companion control reroute."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import screen_escape as geo
import screen_u11_microvias as microvia


OLD_MODE = (
    "e67f07f9e1cd9a15", "08206b74b4f92358", "5738bff9eac3704c",
    "0e63ca2eae1a0132", "555dbcb468243d8f", "6f42f942f7d389ff",
)
RETAINED_MODE = "a25306357993a8e6"
MODE_NET = "AMP_R_SD_MODE"
POWER_NET = "1V8_SYS"
MODE_ROUTE = ((182.3,398.8), (191,409), (191,434), (181,444), (176,444))
VIA = (174.5, 417.5)
TOP = ((174.5, 424.2), VIA)
BOTTOM = (VIA, (158.5, 424.8))


def entry(net, identity, a, b, width):
    return geo.Copper(identity, "line", net, (a, b), width / 2)


def board_objects(r4, native, board, dump):
    _, top = geo.archive_copper(native, dump, r4 / "u11/r3-u11-95ball-native.csv")
    top = [(obj, obj.bounds) for obj in top]
    bottom = []
    cached = json.loads(dump.read_bytes())
    for comp in cached["components"]:
        for pad in comp["pads"]:
            if pad["layer"] != 2 or not 320 <= pad["y"] < 560:
                continue
            ident = f'{comp["designator"]}.{pad["padNumber"]}'
            x, y = pad["x"], pad["y"]
            w, h = pad["width"]/2 + 0.11, pad["height"]/2 + 0.11
            if pad["shape"][0] == "ELLIPSE":
                bottom.append(geo.Copper(ident, "circle", pad["net"], ((x, y),), max(w,h)))
            elif pad["shape"][0] == "RECT" and pad["rotation"] % 90 == 0:
                if pad["rotation"] % 180:
                    w,h = h,w
                bottom.append(geo.Copper(ident, "rect", pad["net"],
                    ((x-w,y-h),(x+w,y-h),(x+w,y+h),(x-w,y+h)), 0))
            else:
                raise ValueError(f"Unsupported bottom geometry {ident}")
    inner_signal = []
    for (kind, identity), row in board.items():
        if kind == "LINE" and row["layerId"] in (2,16,17):
            segment = entry(row["netName"],identity,(row["startX"],row["startY"]),
                            (row["endX"],row["endY"]),row["width"])
            if row["layerId"] == 2:
                bottom.append(segment)
            else:
                inner_signal.append(segment)
        elif kind == "VIA" and (row["ruleName"] == "BV_L5_L6" or row["viaType"] == "NORMAL"):
            bottom.append(geo.Copper(identity,"via",row["netName"],
                ((row["centerX"],row["centerY"]),),row["viaDiameter"]/2))
    return top, [(o,o.bounds) for o in bottom], [(o,o.bounds) for o in inner_signal]


def verify(r4):
    sys.path.insert(0, str(r4 / "u11"))
    sys.path.insert(0, str(r4))
    from audit_r3_u11 import load, records
    from verify_pcb1_spur import point_to_segment, segment_distance
    geo.load, geo.records = load, records
    geo.point_to_segment, geo.segment_distance = point_to_segment, segment_distance

    native, = (r4 / "native").glob("*.epro2")
    dump = r4 / "verification/pcb3-restore-copper.json"
    board = records(load(native).documents[microvia.PCB])
    top, bottom_all, inner = board_objects(r4, native, board, dump)
    bottom = [(o,b) for o,b in bottom_all if o.name not in OLD_MODE]
    removed = [o for o,_ in bottom_all if o.name in OLD_MODE]
    if len(removed) != len(OLD_MODE) or any(o.net != MODE_NET for o in removed):
        raise ValueError("Unexpected removed control segments")
    joins = set()
    # A nonmatching net sees all retained same-net MODE objects as obstacles.
    same_net = [(o,b) for o,b in bottom if o.net == MODE_NET]
    for old in removed:
        joins.update(identity for gap, identity in
                     geo.stroke_gaps(*old.points, old.radius, same_net, "", 0)
                     if gap <= 0)
    if joins != {"U10.A1", RETAINED_MODE}:
        raise ValueError(f"Removal has unexpected same-net contacts: {joins}")

    new_control = tuple(zip(MODE_ROUTE,MODE_ROUTE[1:]))
    control_gap = [
        geo.nearest(a,b,2,bottom,MODE_NET,25) for a,b in new_control]
    bottom += [(obj, obj.bounds) for obj in
               [entry(MODE_NET, "mode_r5_path",a,b,4) for a,b in new_control]]
    gaps = {
        "mode_bottom": min(control_gap),
        "power_top_trace": geo.nearest(*TOP,2,top,POWER_NET,25),
        "power_bottom_trace": geo.nearest(*BOTTOM,2,bottom,POWER_NET,25),
        "power_via_top": geo.nearest(VIA,VIA,6,top,POWER_NET,25),
        "power_via_bottom": geo.nearest(VIA,VIA,6,bottom,POWER_NET,25),
        "power_via_inner_signal": geo.nearest(VIA,VIA,6,inner,POWER_NET,25),
    }
    holes = microvia.hole_objects(board)
    hole_wall = min((math.dist(VIA,p)-r-3,identity) for identity,net,p,r,_ in holes
                    if net != POWER_NET)
    if min(x[0] for x in gaps.values()) < 6 or hole_wall[0] < 10:
        raise ValueError("Copper or hole separation is below guard")
    if math.dist(TOP[0],TOP[1]) < 3 or math.dist(*BOTTOM) < 3:
        raise ValueError("Unexpectedly short route")
    if 204.7244-max(p[0] for p in MODE_ROUTE)-2 < 10 or 204.7244-VIA[0]-6 < 14:
        raise ValueError("Board edge guard failed")

    return {
        "scope": "Offline nominal geometry only. Requires physical continuity and both GND inner-plane antipads "
                 "to be regenerated and checked in the native editor.",
        "r4_sha256":hashlib.sha256(native.read_bytes()).hexdigest(),
        "mode_route":MODE_ROUTE,
        "mode_remove":OLD_MODE,
        "mode_retained_connected_endpoints":sorted(joins),
        "new_width_mil":4,
        "new_mode_extra_length_mil":round(sum(math.dist(a,b) for a,b in new_control)
                                -sum(math.dist(*line.points) for line in removed),6),
        "power": {"net":POWER_NET, "via_xy":VIA, "via_type":"NORMAL","via_outer_mil":12,
                  "via_drill_mil":6, "top":TOP,"bottom":BOTTOM},
        "nearest_foreign_gap_mil": {k: [round(v[0],6),v[1]] for k,v in gaps.items()},
        "nearest_foreign_hole_wall_gap_mil": [round(hole_wall[0],6),hole_wall[1]],
        "min_control_copper_to_edge_mil": round(204.7244-191-2,6),
        "via_copper_to_edge_mil": round(204.7244-VIA[0]-6,6),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r4", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.r4),indent=2))
