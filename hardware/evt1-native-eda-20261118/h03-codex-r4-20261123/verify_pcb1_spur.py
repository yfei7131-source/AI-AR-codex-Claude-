"""Measure the PCB1 bottom-layer GND spur from an identity-verified EasyEDA dump."""

import argparse
import json
import math
from pathlib import Path

PCB1 = "8fbc3cae65886fe5"
SPUR = "3ca748787f4325f4"
UPSTREAM = "cc601d47aeaf5f49"
GROUND_FEED = "5d8242ec900c779f"
GROUND_VIA = "d9ecb5c3d6115fd5"
FEEDBACK_VIA = "cfecd61eed9d9491"


def point_to_segment(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if not length_squared:
        return math.dist(point, start)
    fraction = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    fraction = min(1, max(0, fraction))
    return math.dist(point, (start[0] + fraction * dx, start[1] + fraction * dy))


def line_points(track):
    return (track["startX"], track["startY"]), (track["endX"], track["endY"])


def segment_distance(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    if side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0:
        return 0
    return min(point_to_segment(a, c, d), point_to_segment(b, c, d),
               point_to_segment(c, a, b), point_to_segment(d, a, b))


def pad_circle(pad):
    # An enclosing circle bounds any intersection even at a rotated rectangle corner.
    if pad.get("specialPadPresent"):
        raise ValueError(f"Special pad needs its own copper proof: {pad['primitiveId']}")
    center = pad["x"], pad["y"]
    if "width" in pad and "height" in pad:
        return center, math.hypot(pad["width"], pad["height"]) / 2
    kind, points = pad["shape"]
    if kind != "POLYGON" or any(isinstance(value, str) and value != "L" for value in points):
        raise ValueError(f"Unknown pad geometry: {pad['primitiveId']}")
    points = [value for value in points if value != "L"]
    radius = max(math.dist(center, vertex) for vertex in zip(points[::2], points[1::2], strict=True))
    return center, radius


def measure(board):
    capture = board["capture"]
    copper = board["copper"]
    if capture["documentUuid"] != PCB1 or not capture["identityVerified"]:
        raise ValueError("Expected an identity-verified PCB1 dump")
    if board.get("partial") or board["componentsAvailability"] != "available":
        raise ValueError("Incomplete component or geometry capture")
    if set(copper["availability"].values()) != {"available"} or not copper["arcsAvailable"]:
        raise ValueError("Incomplete copper capture")
    if any(copper[kind] for kind in ("arcs", "fills", "pours", "poured")):
        raise ValueError("Unexpected area or curved copper requires a separate contact proof")

    tracks = {item["primitiveId"]: item for item in copper["lines"] if item["layer"] == 2}
    vias = {item["primitiveId"]: item for item in copper["vias"]}
    spur = tracks.pop(SPUR)
    upstream = tracks[UPSTREAM]
    a, b = line_points(spur)
    via = vias[GROUND_VIA]
    via_center = via["x"], via["y"]
    if spur["net"] != "GND" or spur["lineWidth"] != 2 or spur["locked"]:
        raise ValueError("Unexpected e938 identity or parameters")
    if upstream["net"] != "GND" or line_points(upstream) != (via_center, a):
        raise ValueError("The retained 4 mil segment must connect to the same ground via")

    feed = tracks[GROUND_FEED]
    if feed["net"] != "GND" or via_center not in line_points(feed):
        raise ValueError("The retained ground feed must touch the same via")

    neighbors = []
    for track_id, track in tracks.items():
        gap = segment_distance(a, b, *line_points(track)) - (spur["lineWidth"] + track["lineWidth"]) / 2
        neighbors.append(("track", track_id, track["net"], gap))
    # Treat all blind vias as bottom-layer obstacles here, which can only add contacts.
    for via_id, item in vias.items():
        gap = point_to_segment((item["x"], item["y"]), a, b) - (spur["lineWidth"] + item["diameter"]) / 2
        neighbors.append(("via", via_id, item["net"], gap))
    for component in board["components"]:
        for pad in component["pads"]:
            if pad["layer"] != 2 and not pad.get("hole"):
                continue
            center, radius = pad_circle(pad)
            # Capture pad centers and simple widths round to 0.1 mil. Allow 0.2 mil total.
            gap = point_to_segment(center, a, b) - radius - spur["lineWidth"] / 2 - 0.2
            neighbors.append(("pad", pad["primitiveId"], pad["net"], gap))
    contacts = [(kind, identifier, net) for kind, identifier, net, gap in neighbors if gap <= 0]
    if set(contacts) != {("track", UPSTREAM, "GND"), ("track", GROUND_FEED, "GND"),
                         ("via", GROUND_VIA, "GND")}:
        raise ValueError(f"Unexpected touching copper: {contacts}")

    feedback = vias[FEEDBACK_VIA]
    feedback_center = feedback["x"], feedback["y"]
    if feedback["net"] != "BB_FB" or feedback["diameter"] != 12:
        raise ValueError("Unexpected e85 geometry or net")
    center_gap = point_to_segment(feedback_center, a, b)
    return {
        "source": "EasyEDA Pro PCB1 native copper capture",
        "document_uuid": PCB1,
        "spur": spur,
        "retained_ground_track": upstream,
        "retained_ground_feed": feed,
        "retained_ground_via": via,
        "retained_feedback_via": feedback,
        "touching_copper": [list(contact) for contact in contacts],
        "nearest_pad_lower_bound_gap_mil": round(min(gap for kind, _, _, gap in neighbors if kind == "pad"), 6),
        "e85_board_rule_mil_rounded": board["rules"]["clearanceMil"],
        "e85_copper_edge_gap_mil": {
            str(width): round(center_gap - (width + feedback["diameter"]) / 2, 6) for width in (2, 3.5, 4)
        },
        "e85_to_retained_ground_via_copper_edge_gap_mil":
            round(math.dist(feedback_center, via_center) - (feedback["diameter"] + via["diameter"]) / 2, 6),
        "planned_change": "Delete only the dangling PCB1 bottom-layer GND spur; retain the parent and both vias."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copper_dump", type=Path)
    args = parser.parse_args()
    print(json.dumps(measure(json.loads(args.copper_dump.read_bytes())), indent=2))
