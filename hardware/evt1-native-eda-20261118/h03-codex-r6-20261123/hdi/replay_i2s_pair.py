"""Replay two different I2S candidate nets against each other and both planes."""

from itertools import product
import json
import math
from pathlib import Path
import sys

import screen_hdi_joint as geometry


def candidate_objects(plan):
    copper = []
    drills = []
    cutouts = []
    portals = {
        "ball_escape_top": (1, 15, 16),
        "ball_escape_bottom": (2, 18, 17),
        "buried_xy": (16, 17),
    }
    for name, span in portals.items():
        center = plan[name]
        buried = name == "buried_xy"
        hole = 3.0 if buried else plan["blind_diameter_um"] / (2000 * geometry.V)
        drills.append((name, tuple(center), hole, span))
        circle = geometry.circle(*center, hole + 3)
        copper.extend((layer, name, circle) for layer in span)
        if not buried:
            cutouts.append((center, hole + 3, span))
    for layer, route in zip((1, 16, 17, 2), plan["paths"], strict=True):
        area = geometry.LineString(route["path"]).buffer(route["width_mil"] / 2)
        copper.append((layer, "trace", area))
    return copper, drills, cutouts


def replay_pair(left, right):
    copper_a, drills_a, cutouts_a = candidate_objects(left)
    copper_b, drills_b, cutouts_b = candidate_objects(right)
    copper_gap = min((shape_a.distance(shape_b), layer_a, name_a, name_b)
                     for layer_a, name_a, shape_a in copper_a
                     for layer_b, name_b, shape_b in copper_b if layer_a == layer_b)
    hole_gap = min((math.dist(pt_a, pt_b) - radius_a - radius_b, name_a, name_b)
                   for name_a, pt_a, radius_a, span_a in drills_a
                   for name_b, pt_b, radius_b, span_b in drills_b if set(span_a) & set(span_b))
    overlap = {}
    for a, radius_a, span_a in cutouts_a:
        for b, radius_b, span_b in cutouts_b:
            for layer in set(span_a) & set(span_b) & geometry.PLANE.keys():
                void_a = geometry.plane_antipad(layer, a, radius_a)
                void_b = geometry.plane_antipad(layer, b, radius_b)
                overlap[layer] = void_a.intersection(void_b).area
    return_planes = geometry.plane_return(cutouts_a + cutouts_b)
    connected = all(item["components_before"] == item["components_after"]
                    and not item["ground_contact_overlap"] for item in return_planes.values())
    guard = max(9.5, 0.24 / geometry.V)
    return {
        "copper_gap": copper_gap,
        "hole_wall_gap": hole_gap,
        "cutout_overlap_area_by_layer": overlap,
        "combined_planes": return_planes,
        "no_nominal_cross_route_collision": copper_gap[0] >= geometry.GUARD and hole_gap[0] >= guard,
        "nominal_plane_topology_preserved": connected and all(area == 0 for area in overlap.values()),
        "min_plane_void_to_existing_ground_land": min(
            value["closest_ground_copper_to_cutout_mil"] for value in return_planes.values()),
        "fabrication_released": False,
    }


def run(lrck_archive, bclk_archive):
    lrck = json.loads(lrck_archive.read_bytes())["U11.K4->J1.P12 100"]["plans"]
    bclk = json.loads(bclk_archive.read_bytes())["U11.L9"]["symmetric"]["plans"]
    return {"scope": "Nominal, two different routes. No approval or native write.",
            "lrck": "U11.K4/P0.22 to J1.P12. U10.C3 and R4.1 remain open.",
            "bclk": "U11.L9/P0.15 to U10.C1, requiring SCK PSEL ECO from K5/P0.20. J1.P11 and R3.1 remain open.",
            "pairs": [{"indices": [i, j], **replay_pair(a, b)}
                      for (i, a), (j, b) in product(enumerate(lrck), enumerate(bclk))]}


if __name__ == "__main__":
    _, source_r5, lrck, bclk, out = sys.argv
    result = run(Path(lrck), Path(bclk))
    Path(out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
