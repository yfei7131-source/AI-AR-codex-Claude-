"""Replay one K4 trunk with two receiver branches and a bounded pull-down screen."""

import json
import math
from pathlib import Path
import sys

import symmetric_stack as candidate

g = candidate.s

TOP_SITE = 177.5, 328
CORE_SITE = 180, 318
LASER_UM = 100
LASER_COPPER_RADIUS = LASER_UM / (2000 * g.V) + 3
PLANE_LIGAMENT_GUARD = 6


def preserves_plane(report):
    return all(row["components_before"] == row["components_after"]
               and not row["ground_contact_overlap"]
               and row["closest_ground_copper_to_cutout_mil"] >= PLANE_LIGAMENT_GUARD
               for row in report.values())


def screen():
    net = candidate.NET
    start = g.PADS["U11.K4"][0]
    assert g.check_via(TOP_SITE, LASER_COPPER_RADIUS, LASER_COPPER_RADIUS - 3,
                       candidate.TOP, net) and g.check_via(CORE_SITE, 6, 3, candidate.PTH_LAYERS, net)
    paths = {"top": TOP_SITE, "core": CORE_SITE,
             "ltop": g.route(start, TOP_SITE, 1, net, 4),
             "l3": g.route(TOP_SITE, CORE_SITE, 16, net, 4)}
    assert paths["ltop"] and paths["l3"]
    cuts = [(TOP_SITE, LASER_COPPER_RADIUS, candidate.TOP)]
    found = []
    unfinished = {}
    targets = {
        "J1.P12": (101, 115, 301, 317, 1),
        "U10.C3": (130, 146, 376, 392, 1),
        "R4.1": (126, 185, 553, 648, 1),
    }
    for ref, window in targets.items():
        options = []
        for p, outer in candidate.endpoints(ref, 2, candidate.BOTTOM, window, LASER_UM):
            hole_wall = math.dist(p, CORE_SITE) - LASER_COPPER_RADIUS
            if hole_wall < 0.13 / g.V:
                continue
            if any(g.plane_antipad(18, p, LASER_COPPER_RADIUS).intersects(g.plane_antipad(18, q, r))
                   for q, r, span in cuts if 18 in span):
                continue
            candidate_cuts = cuts + [(p, LASER_COPPER_RADIUS, candidate.BOTTOM)]
            plane_after = g.plane_return(candidate_cuts)
            if not preserves_plane(plane_after):
                continue
            inner = g.route(CORE_SITE, p, 17, net, 4)
            if inner:
                options.append((outer["length_mil"] + inner["length_mil"], p, outer, inner,
                                plane_after[18]["closest_ground_copper_to_cutout_mil"]))
        if not options:
            unfinished[ref] = "No mask-clear route in the bounded search"
            continue
        cost, p, outer, inner, margin = min(options)
        cuts.append((p, LASER_COPPER_RADIUS, candidate.BOTTOM))
        found.append({"name": ref, "via": p, "net": net, "bottom_route": outer, "l4_route": inner,
                      "length": cost, "plane_guard_to_ground_copper": margin, "candidates": len(options)})
    nearest_returns = sorted((round(math.dist(CORE_SITE, c), 4), name, c)
                             for c, _, layers, name, net in g.DRILLS
                             if net == "GND" and 15 in layers and 18 in layers)[:6]
    return {
        "scope": "R5 nominal copper search. No approved stackup, native design change or fabrication.",
        "main": paths,
        "destinations": found,
        "unresolved": unfinished,
        "plane_after": g.plane_return(cuts),
        "width": 4,
        "laser_um": LASER_UM,
        "buried_mil": [6, 12],
        "rules": {"ground_margin": PLANE_LIGAMENT_GUARD,
                  "clearance_plane": g.PLANE_CLEARANCE, "trace_edge": g.BOARD_EDGE_TRACE},
        "ground_transfer_near_buried_core": nearest_returns,
    }


if __name__ == "__main__":
    output = Path(sys.argv[2])
    output.write_text(json.dumps(screen(), indent=2) + "\n", encoding="utf-8")
