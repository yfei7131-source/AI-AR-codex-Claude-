"""Evaluate PCB3 U11 copper escape candidates from PR52 native geometry."""

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys


MM = 0.0254
GUARD = 6.0
REPORT_GUARD = 0.02
DRILL = 0.075 / MM
VIA_R = DRILL / 2 + 3
HOLE_R = DRILL / 2


@dataclass(frozen=True)
class Copper:
    name: str
    kind: str
    net: str
    points: tuple
    radius: float

    @property
    def bounds(self):
        return (min(p[0] for p in self.points) - self.radius,
                min(p[1] for p in self.points) - self.radius,
                max(p[0] for p in self.points) + self.radius,
                max(p[1] for p in self.points) + self.radius)

    @property
    def center(self):
        return tuple(sum(p[i] for p in self.points) / len(self.points) for i in range(2))


def stroke_gaps(start, end, radius, obstacles, net, limit):
    xmin, xmax = sorted((start[0], end[0]))
    ymin, ymax = sorted((start[1], end[1]))
    reach = radius + limit
    for body, (l, b, r, t) in obstacles:
        if body.net == net or r < xmin - reach or xmax + reach < l or t < ymin - reach or ymax + reach < b:
            continue
        if body.kind == "rect":
            edges = tuple(zip(body.points, body.points[1:] + body.points[:1]))
            if any(l < point[0] < r and b < point[1] < t for point in (start, end)):
                distance = 0
            else:
                distance = min(segment_distance(start, end, a, b) for a, b in edges)
        elif body.kind == "line":
            distance = segment_distance(start, end, *body.points)
        else:
            distance = point_to_segment(body.points[0], start, end)
        yield distance - radius - body.radius, body.name


def nearest(start, end, radius, obstacles, net, limit):
    return min(stroke_gaps(start, end, radius, obstacles, net, limit), default=(limit, "outside window"))


def archive_copper(archive, dump, pad_csv):
    documents = load(archive).documents
    data = records(documents[("PCB", "1db01a36f669a47a")])
    with pad_csv.open(newline="", encoding="utf-8-sig") as source:
        balls = {row["ball"]: row for row in csv.DictReader(source)}
    for name in balls:
        row = balls[name]
        row["center"] = float(row["center_x_mil"]), float(row["center_y_mil"])
        row["radius"] = float(row["land_diameter_mil"]) / 2
    board = json.loads(dump.read_bytes())
    avail = board["copper"]["availability"]
    if (board["capture"]["documentUuid"] != "1db01a36f669a47a"
            or not board["capture"]["identityVerified"]
            or any(status != "available" for status in avail.values())
            or not board["copper"]["arcsAvailable"]
            or any(board["copper"][name] for name in ("arcs", "fills", "pours", "poured"))):
        raise ValueError("Unexpected PCB3 top-copper coverage")

    objects = []
    for comp in board["components"]:
        for pad in comp["pads"]:
            if pad["layer"] != 1:
                if pad.get("hole") and (pad["shape"][0] != "POLYGON" or pad["y"] < 750):
                    raise ValueError("Unaccounted through pad")
                continue
            name = f'{comp["designator"]}.{pad["padNumber"]}'
            x, y = pad["x"], pad["y"]
            net = pad["net"]
            if pad["specialPadPresent"]:
                raise ValueError(f"Unsupported pad {name}")
            if comp["designator"] == "U11":
                ball = balls[pad["padNumber"]]
                if ball["native_pcb_net"] != net:
                    raise ValueError(f"Unexpected U11 net {name}")
                body = Copper(name, "circle", net, (ball["center"],), ball["radius"])
            elif pad["shape"][0] == "ELLIPSE":
                body = Copper(name, "circle", net, ((x, y),), max(pad["width"], pad["height"]) / 2 + 0.11)
            elif pad["shape"][0] == "RECT":
                if pad["rotation"] % 90:
                    raise ValueError(f"Unsupported rectangle rotation {name}")
                w, h = pad["width"] / 2 + 0.11, pad["height"] / 2 + 0.11
                if pad["rotation"] % 180:
                    w, h = h, w
                body = Copper(name, "rect", net, ((x-w, y-h), (x+w, y-h), (x+w, y+h), (x-w, y+h)), 0)
            else:
                raise ValueError(f"Unsupported pad {name}")
            objects.append(body)
    for (kind, identity), item in data.items():
        if kind == "LINE" and item["layerId"] == 1:
            points = tuple((item[key+"X"], item[key+"Y"]) for key in ("start", "end"))
            objects.append(Copper(identity, "line", item["netName"], points, item["width"] / 2))
        if kind == "VIA" and (item["viaType"] == "NORMAL" or item["ruleName"] == "BV_L1_L2"):
            if item["unusedInnerLayers"] and 1 in item["unusedInnerLayers"]:
                raise ValueError(f"Unexpected top layer decision {identity}")
            center = item["centerX"], item["centerY"]
            objects.append(Copper(identity, "via", item["netName"], (center,), item["viaDiameter"] / 2))
    outline = board["outline"]["points"]
    zones = [r for r in board["copper"]["regions"] if r["layer"] == 1]
    if outline != [[0, 0], [0, 1338.5827], [204.7244, 1338.5827], [204.7244, 0]] or len(zones) != 1:
        raise ValueError("Review outline/regions before using route window")
    if "no-wires" not in zones[0]["ruleTypeNames"] or zones[0]["bbox"]["maxY"] > 160:
        raise ValueError("Review top exclusion before using route window")
    return balls, objects


def branch_candidates(ball, objects, extra):
    origin = ball["center"]
    net = ball["native_pcb_net"]
    width = 4 if net in ("GND", "1V8_SYS") else 3.5
    obstacles = [(obj, obj.bounds) for obj in objects + extra]
    left, right = 10 + width/2, 204.7244-10-width/2

    def edge_gap(a, b):
        return min(a[0] - left, b[0] - left, right - a[0], right - b[0], a[1]-160, b[1]-160)

    def path(points):
        compact = tuple(p for i, p in enumerate(points) if not i or p != points[i - 1])
        if len(compact) < 2 or any(edge_gap(a, b) < 0 for a, b in zip(compact, compact[1:])):
            return None
        distances = [nearest(a, b, width/2, obstacles, net, GUARD + REPORT_GUARD)
                     for a, b in zip(compact, compact[1:])]
        if min(distances)[0] >= GUARD + REPORT_GUARD:
            return sum(math.dist(a, b) for a, b in zip(compact, compact[1:])), compact
        return None

    targets = defaultdict(list)
    for obj in objects:
        if obj.net != net or obj.name == "U11." + ball["ball"]:
            continue
        if obj.kind == "line":
            a, b = obj.points
            dx, dy = b[0] - a[0], b[1] - a[1]
            length_sq = dx*dx + dy*dy
            u = min(1, max(0, ((origin[0]-a[0])*dx + (origin[1]-a[1])*dy)/length_sq)) if length_sq else 0
            ends = [a, b, (a[0] + u*dx, a[1] + u*dy)]
        else:
            ends = [obj.center]
        for v in ends:
            if 5 < math.dist(origin, v) < 220:
                targets[tuple(round(k, 5) for k in v)].append(obj.name)
    routes = []
    for target, names in sorted(targets.items(), key=lambda item: math.dist(origin, item[0])):
        x, y = origin
        tx, ty = target
        ox, oy = (1 if tx > x else -1), (1 if ty > y else -1)
        short = min(abs(tx - x), abs(ty - y))
        paths = [(origin, target), (origin, (x, ty), target), (origin, (tx, y), target),
                 (origin, (x+ox*short,y+oy*short), target),
                 (origin, (tx-ox*short,ty-oy*short), target)]
        candidates = [result for points in paths if (result := path(points))]
        if candidates:
            length, shortest = min(candidates)
            gap, obstacle = min(nearest(a, b, width/2, obstacles, net, 30)
                                for a, b in zip(shortest, shortest[1:]))
            routes.append({"ball": ball["ball"], "net": net, "width_mil": width, "points": shortest,
                           "to": names, "length_mil": round(length, 5), "gap_mil": round(gap, 5),
                           "closest_foreign": obstacle})
    return sorted(routes, key=lambda p: p["length_mil"])


def eccentric_screen(balls, objects, previously_blocked):
    obstacles = [(obj, obj.bounds) for obj in objects]
    matrix = []
    max_offset = min(row["radius"] for row in balls.values()) - HOLE_R
    # 0.1 mil scan plus containment grid tolerance. Hole stays inside existing copper land.
    steps = [i/10 for i in range(-math.floor(max_offset*10), math.floor(max_offset*10)+1)]
    for ball in balls.values():
        if ball["ball"] not in previously_blocked:
            continue
        x, y = ball["center"]
        net = ball["native_pcb_net"]
        positions = []
        for dx in steps:
            for dy in steps:
                offset = math.hypot(dx, dy)
                if offset > max_offset:
                    continue
                center = x + dx, y + dy
                nearest_copper = nearest(center, center, VIA_R, obstacles, net, 15)
                if nearest_copper[0] >= GUARD + REPORT_GUARD:
                    positions.append((offset, -nearest_copper[0], dx, dy, nearest_copper[1]))
        best = min(positions, default=None)
        matrix.append({"ball": ball["ball"], "net": net, "candidate_grid_positions": len(positions),
                       "minimum_shift_x_mil": best[2] if best else None,
                       "minimum_shift_y_mil": best[3] if best else None,
                       "nearest_foreign_gap_mil": round(-best[1], 5) if best else None,
                       "nearest_foreign": best[4] if best else None})
    return matrix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r4", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.r4 / "u11"))
    sys.path.insert(0, str(args.r4))
    from audit_r3_u11 import load as load_archive, records as document_records
    from verify_pcb1_spur import segment_distance as seg_dist, point_to_segment as point_seg
    global load, records, segment_distance, point_to_segment
    load, records = load_archive, document_records
    segment_distance, point_to_segment = seg_dist, point_seg
    archive, = (args.r4 / "native").glob("*.epro2")
    balls, objects = archive_copper(archive, args.r4 / "verification/pcb3-restore-copper.json",
                                   args.r4 / "u11/r3-u11-95ball-native.csv")
    reference = json.loads((args.r4 / "u11/r3-u11-native-audit.json").read_bytes())
    blocked = reference["inner_balls_failing_locked_6mil_clearance_with_0p2274mm_centered_via"]
    extra = [Copper("R5_B2_C2", "line", "GND", (balls["B2"]["center"], balls["C2"]["center"]), 2)]
    routes = {}
    for key, ball in balls.items():
        if not ball["native_pcb_net"] or ball["same_net_top_line_contacts"] or ball["same_net_top_via_contacts"]:
            continue
        limited = [r for r in branch_candidates(ball, objects, extra) if not all(n.startswith("U11.") for n in r["to"])]
        routes[key] = limited[:3]
    report = {
        "guard_mil": GUARD, "geometric_margin_mil": REPORT_GUARD,
        "top_copper_routes_to_external_objects": routes,
        "eccentric_top_copper_pad_screen": eccentric_screen(balls, objects, blocked),
        "drill_mil": DRILL, "capture_diameter_mil": 2*VIA_R,
        "scope": "Top-copper geometry only. Each route/position is an independent candidate. Validate combinations, native connectivity and DRC, drilling wall spacing, target plane/trace, stackup and mask before manufacturing.",
    }
    args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    for name, r in routes.items():
        if r:
            print(name, r[0])


if __name__ == "__main__":
    main()
