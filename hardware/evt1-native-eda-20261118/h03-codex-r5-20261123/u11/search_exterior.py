"""Search isolated U11 top-layer copper islands. Requires numpy and shapely >=2."""

import argparse
from collections import defaultdict
import heapq
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import screen_escape as screen

PCB_ID = ("PCB", "1db01a36f669a47a")
GROUND = "GND"
POWER = "1V8_SYS"
STEP = 0.5
GRID_X = np.arange(12, 193, STEP)
GRID_Y = np.arange(200, 720, STEP)
WRAP = 1 / math.cos(math.pi / 128)
DIRS = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
CONNECT_RADIUS = 1.25


def shape(copper):
    if copper.kind == "rect":
        return Polygon(copper.points)
    centerline = LineString(copper.points) if copper.kind == "line" else Point(copper.points[0])
    return centerline.buffer(copper.radius * WRAP, quad_segs=32)


def path_polygon(raw):
    points = [p for p in raw if p != "L"]
    if any(isinstance(p, str) for p in points):
        raise ValueError("Unrecognized adaptive polygon drawing path")
    return list(zip(points[::2], points[1::2], strict=True))


def ground_vias_connected_to_l2(data):
    layer = data["LAYER_FILL", '["LAYER_FILL",15]']
    fills = []
    for entry in layer["fill"]:
        if entry["netName"] == GROUND:
            shell, *holes = map(path_polygon, entry["path"])
            forms = Polygon(shell, holes=holes)
            if not forms.is_valid:
                raise ValueError("Malformed GND L2 polygon")
            fills.append(forms)
    connected = set()
    for (kind, name), item in data.items():
        if kind != "VIA" or item["netName"] != GROUND or item["ruleName"] != "BV_L1_L2":
            continue
        point = Point(item["centerX"], item["centerY"])
        if any(fill.covers(point) for fill in fills):
            connected.add(name)
    return connected


def islands(shapes, copper, plane_connected):
    parent = {item.name: item.name for item in copper}

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def join(a, b):
        parent[find(a)] = find(b)

    groups = defaultdict(list)
    for item in copper:
        if item.net:
            groups[item.net].append(item.name)
    for group in groups.values():
        for a, b in itertools.combinations(group, 2):
            if shapes[a].distance(shapes[b]) <= 1e-6:
                join(a, b)
    for a, b in zip(sorted(plane_connected), sorted(plane_connected)[1:]):
        join(a, b)
    return {k: find(k) for k in parent}


def neighbors(point):
    x, y = point
    i, j = round((x-GRID_X[0])/STEP), round((y-GRID_Y[0])/STEP)
    n = int(math.ceil(CONNECT_RADIUS / STEP))
    for u in range(max(0, i-n), min(len(GRID_X), i+n+1)):
        for v in range(max(0, j-n), min(len(GRID_Y), j+n+1)):
            if math.dist(point, (GRID_X[u], GRID_Y[v])) <= CONNECT_RADIUS:
                yield u, v


def actual(cell):
    return tuple(float(arr[i]) for arr, i in zip((GRID_X, GRID_Y), cell))


def search(origin, targets, free, clear):
    starts = [cell for cell in neighbors(origin) if free[cell] and clear(origin, actual(cell))]
    endpoints = {}
    for dest, name in targets:
        for cell in neighbors(dest):
            if free[cell] and clear(actual(cell), dest):
                endpoints[cell] = dest, name
    if not starts or not endpoints:
        return None
    # Exact end clearance is checked before Dijkstra. A conservative sampling dilation
    # around every center ensures adjacent grid points can be joined without crossing copper.
    queue, previous, costs = [], {}, {}
    for cell in starts:
        cost = math.dist(origin, actual(cell))
        heapq.heappush(queue, (cost, cell))
        previous[cell] = None
        costs[cell] = cost
    while queue:
        cost, cell = heapq.heappop(queue)
        if costs[cell] < cost:
            continue
        if cell in endpoints:
            dest, name = endpoints[cell]
            chain = [dest]
            while cell is not None:
                chain.append(actual(cell))
                cell = previous[cell]
            path = [origin, *reversed(chain)]
            result = [path[0]]
            for index in range(2, len(path)):
                if not clear(result[-1], path[index]):
                    result.append(path[index - 1])
            if result[-1] != dest:
                result.append(dest)
            if not all(clear(a, b) for a, b in zip(result, result[1:])):
                raise ValueError("Independent final chain geometry failed")
            return result, name
        for dx, dy in DIRS:
            u, v = cell[0]+dx, cell[1]+dy
            nxt = (u, v)
            if not (0 <= u < len(GRID_X) and 0 <= v < len(GRID_Y) and free[nxt]):
                continue
            edge_cost = (math.sqrt(2) if dx and dy else 1) * STEP
            trial = cost + edge_cost
            if trial >= costs.get(nxt, float("inf")):
                continue
            costs[nxt] = trial
            previous[nxt] = cell
            heapq.heappush(queue, (trial, nxt))
    return None


def analyze(balls, copper, data):
    all_shapes = {obj.name: shape(obj) for obj in copper}
    via_set = ground_vias_connected_to_l2(data)
    island = islands(all_shapes, copper, via_set)
    cells_x, cells_y = np.meshgrid(GRID_X, GRID_Y, indexing="ij")
    outcomes = {}
    for net in {row["native_pcb_net"] for row in balls.values()} - {""}:
        width = 4 if net in {GROUND, POWER} else 3.5
        min_copper = width/2 + screen.GUARD + screen.REPORT_GUARD
        obstacles = unary_union([all_shapes[obj.name] for obj in copper if obj.net != net])
        board = box(10+width/2, 200, 204.7244-10-width/2, 720)
        allowed = board.difference(obstacles.buffer((min_copper+STEP/math.sqrt(2))*WRAP, quad_segs=32))
        valid = shapely.contains_xy(allowed, cells_x, cells_y)

        def clear(a, b):
            line = Point(a) if a == b else LineString((a, b))
            return board.covers(line) and obstacles.distance(line) >= min_copper

        for row in balls.values():
            if row["native_pcb_net"] != net:
                continue
            ball = row["ball"]
            start = "U11." + ball
            origin = row["center"]
            targets = []
            for obj in copper:
                if obj.net != net or island[obj.name] == island[start]:
                    continue
                coords = obj.points if obj.kind == "line" else (obj.center,)
                if obj.kind == "line":
                    seg = LineString(coords)
                    nearest = seg.interpolate(seg.project(Point(origin)))
                    coords = (*coords, tuple(nearest.coords[0]))
                for dest in coords:
                    if GRID_X[0] <= dest[0] <= GRID_X[-1] and GRID_Y[0] <= dest[1] <= GRID_Y[-1]:
                        targets.append((dest, obj.name))
            answer = search(origin, targets, valid, clear)
            if not answer:
                continue
            points, target = answer
            trace = LineString(points)
            h = all_shapes[target]
            outcomes[ball] = {"net": net, "width_mil": width, "points": points, "target": target,
                              "length_mil": round(trace.length, 5),
                              "closest_foreign_gap_mil": round(obstacles.distance(trace)-width/2, 5),
                              "target_connected_l2": target in via_set,
                              "target_geometry_gap_mil": round(h.distance(trace)-width/2, 5)}
    return outcomes, len(via_set)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("r4", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.r4 / "u11"))
    sys.path.insert(0, str(args.r4))
    from audit_r3_u11 import load, records
    from verify_pcb1_spur import segment_distance, point_to_segment
    screen.load, screen.records = load, records
    screen.segment_distance, screen.point_to_segment = segment_distance, point_to_segment
    archive, = (args.r4 / "native").glob("*.epro2")
    balls, copper = screen.archive_copper(archive, args.r4 / "verification/pcb3-restore-copper.json",
                                         args.r4 / "u11/r3-u11-95ball-native.csv")
    # The R5 B2-C2 independent 4 mil replacement stays inside the prior GND island.
    copper.append(screen.Copper("R5_B2_C2", "line", GROUND, (balls["B2"]["center"], balls["C2"]["center"]), 2))
    data = records(load(archive).documents[PCB_ID])
    routes, vias = analyze(balls, copper, data)
    result = {"scope": "Independently compared candidates; conservative top geometry and L2 ground via overlap. "
                        "Native electrical connectivity, fabrication and combinations require separate checks.",
              "ground_vias_overlapping_l2_fill": vias,
              "branches": routes}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(routes, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
