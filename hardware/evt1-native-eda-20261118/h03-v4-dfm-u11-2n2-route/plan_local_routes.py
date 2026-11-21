#!/usr/bin/env python3
"""Bounded same-layer routing from named native pads. Adds no via or plane copper."""

import argparse
import json
import math
from pathlib import Path

from rectify_v4_edge_and_route_pr47 import (
    Archive,
    DOCS,
    LID_TO_LI,
    SENSITIVE_3W_NETS,
    extract_outline_polygon,
    pt_seg_dist,
    seg_seg_dist,
    via_touches_layer,
)


TARGETS = {
    "PCB1": [
        ("CHG_ISO_GATE", 1, "R19.2", "R20.1"),
        ("PRIV_WINDOW_OK", 2, "R28.1", "U14.7"),
        ("PRIV_WINDOW_OK_F", 2, "C28.1", "U13.3"),
        ("ESP_CHIP_PU", 2, "C10.1", "TP4.1"),
        ("CAM_PWR_REQ", 2, "D1.K", "U5.3"),
    ],
    "PCB2": [
        ("AVDD_WD_Q", 2, "R3.1", "R6.1"),
        ("OPT_AVDD_EN", 2, "U5.4", "U5.6"),
        ("AVDD_D3_VSYS", 1, "R2.1", "R7.1"),
        ("AVDD_PG_OK", 2, "U3.3", "U5.1"),
        ("AVDD_WD_Q", 2, "U3.1", "U14.6"),
        ("AVDD_REQ_FILTER", 1, "C3.1", "R7.2"),
        ("OPT_AVDD_EN", 2, "U6.3", "U5.4"),
        ("OPT_AVDD_EN", 2, "U6.3", "U5.6"),
    ],
    "PCB3": [
        ("AMP_R_SD_MODE", 2, "Q1.3", "U10.A1"),
        ("CHG_R_ISET", 2, "R6.1", "U3.2"),
        ("CHG_R_VSET", 2, "R10.1", "U3.7"),
    ],
}
WIDTH = 3.5
MARGIN = 12.0
PAD_GAP = 6.15
CORRIDOR_MARGIN = 6.15


def point(pad):
    return pad["x"], pad["y"]


def box_edges(rect):
    x0, y0, x1, y1 = rect
    return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
            ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]


def pad_box(component, pad):
    x, y = point(pad)
    shape = pad.get("shape", [])
    if shape and shape[0] == "POLYGON":
        path = shape[1]
        coords = [*path[:2], *path[3:]]
        if (len(path) >= 9 and path[2] == "L" and len(coords) % 2 == 0
                and all(type(v) in {int, float} for v in coords)
                and path[:2] == path[-2:]):
            return min(coords[::2]), min(coords[1::2]), max(coords[::2]), max(coords[1::2])
    if shape and shape[0] in {"RECT", "OVAL", "ELLIPSE"} and len(shape) >= 3:
        w, h = shape[1:3]
        angle = math.radians(pad["rotation"])
        c, s = abs(math.cos(angle)), abs(math.sin(angle))
        w, h = max(w*c + h*s, pad["width"]), max(w*s + h*c, pad["height"])
        return x - w/2, y - h/2, x + w/2, y + h/2
    b = component["bbox"]
    return b["minX"], b["minY"], b["maxX"], b["maxY"]


def segment_box_distance(a, b, rect):
    x0, y0, x1, y1 = rect
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in (a, b)):
        return 0.0
    return min(seg_seg_dist(*a, *b, *u, *v) for u, v in box_edges(rect))


def diagonal_paths(a, b):
    dx, dy = (b[0] - a[0], b[1] - a[1])
    diagonal = min(abs(dx), abs(dy))
    ox, oy = math.copysign(diagonal, dx), math.copysign(diagonal, dy)
    bends = [(a[0]+ox, a[1]+oy), (b[0]-ox, b[1]-oy)]
    # Try brief orthogonal detours while keeping each transition at 45 degrees.
    for offset in (8.0, -8.0, 14.0, -14.0, 22.0, -22.0):
        if abs(dx) >= abs(dy):
            p = (a[0] + math.copysign(abs(offset), dx), a[1] + offset)
            q = (b[0] - math.copysign(abs(p[1]-b[1]), dx), p[1])
        else:
            p = (a[0] + offset, a[1] + math.copysign(abs(offset), dy))
            q = (p[0], b[1] - math.copysign(abs(p[0]-b[0]), dy))
        if math.dist(p, q) > math.dist(a, b):
            continue
        yield [a, p, q, b]
    for bend in bends:
        yield [a, bend, b]


def plan(board, dump, drc, archive):
    copper = dump["copper"]
    if (any(state != "available" for state in copper["availability"].values())
            or not copper["arcsAvailable"] or copper["arcs"]):
        raise ValueError("Local plan requires complete line, pad, via and region readback without arcs")
    if any(item["layer"] in {1, 2} for kind in ("fills", "pours", "poured") for item in copper[kind]):
        raise ValueError("Unmodelled outer copper or rule regions")
    regions = []
    for item in copper["regions"]:
        if item["layer"] not in {1, 2}:
            continue
        names = item["ruleTypeNames"]
        if not item["geometryAvailable"] or any(rule not in {"no-wires", "no-pours", "no-components"} for rule in names):
            raise ValueError("Unmodelled native board region")
        if "no-wires" in names:
            rect = item["bbox"]
            regions.append((item["layer"], (rect["minX"], rect["minY"], rect["maxX"], rect["maxY"])))
    pcb = archive.documents["PCB", DOCS[board]]
    vias_by_id = {row.header["id"]: row.payload for row in pcb.records if row.header["type"] == "VIA"}
    vias = copper["vias"]
    if {row["primitiveId"] for row in vias} != vias_by_id.keys():
        raise ValueError("Via readback ID differs from the archived layer-span source")
    span = {}
    for via in vias:
        identifier = via["primitiveId"]
        row = vias_by_id[identifier]
        if abs(via["x"]-row["centerX"]) > 0.001 or abs(via["y"]-row["centerY"]) > 0.001:
            raise ValueError("Native via coordinates differ from the archived layer-span source")
        shape = row["viaType"], row["ruleName"]
        if shape not in {("NORMAL", ""), ("BLIND", "BV_L1_L2"), ("BLIND", "BV_L5_L6")}:
            raise ValueError(f"Unknown via construction for {identifier}: {shape}")
        span[identifier] = shape
    outline = extract_outline_polygon(dump)
    edges = list(zip(outline, outline[1:] + outline[:1]))
    airwires = {key for item in drc["violations"] if item["rule"] == "Connection Error" for key in item["objs"]}
    annotated_pads = [(f"{part['designator']}.{pad['padNumber']}", pad, pad_box(part, pad))
                      for part in dump["components"] for pad in part["pads"]]
    existing = [(line["layer"], (line["startX"], line["startY"]), (line["endX"], line["endY"]),
                 line["lineWidth"], line["net"]) for line in copper["lines"]]
    accepted = []
    for net, layer, source, dest in TARGETS[board]:
        a, = [p for ref, p, _ in annotated_pads if ref == source]
        b, = [p for ref, p, _ in annotated_pads if ref == dest]
        if any(p["net"] != net or p["layer"] != layer for p in (a, b)):
            raise ValueError(f"Unexpected native pad contract for {source} / {dest}")
        if not {a["primitiveId"], b["primitiveId"]} & airwires:
            continue
        routes = []
        for path in diagonal_paths(point(a), point(b)):
            path = list(dict.fromkeys(tuple(round(v, 4) for v in p) for p in path))
            segments = list(zip(path, path[1:]))
            if not segments or sum(math.dist(*seg) for seg in segments) > math.dist(path[0], path[-1]) + 36:
                continue
            ok = True
            for u, v in segments:
                dx, dy = abs(u[0]-v[0]), abs(u[1]-v[1])
                edge_gap = min(seg_seg_dist(*u, *v, *e, *f) for e, f in edges) - WIDTH/2
                if min(dx, dy, abs(dx-dy)) > 0.00011 or edge_gap < MARGIN:
                    ok = False
                    break
                # Unknown pad geometry is guarded by the whole measured component envelope.
                for ref, pad, rect in annotated_pads:
                    if ref in {source, dest} or pad["layer"] not in {layer, 12}:
                        continue
                    gap = CORRIDOR_MARGIN if pad["net"] == net else PAD_GAP
                    if segment_box_distance(u, v, rect) < gap + WIDTH/2:
                        ok = False
                        break
                if not ok:
                    break
                if any(segment_box_distance(u, v, rect) < WIDTH/2 + CORRIDOR_MARGIN
                       for restricted_layer, rect in regions if restricted_layer == layer):
                    ok = False
                    break
                if any(pt_seg_dist(via["x"], via["y"], *u, *v) < (via["diameter"] + WIDTH)/2 + PAD_GAP
                       for via in vias if via_touches_layer(*span[via["primitiveId"]], LID_TO_LI[layer])):
                    ok = False
                    break
                for other_layer, e, f, width, other_net in existing:
                    if other_layer != layer:
                        continue
                    distance = seg_seg_dist(*u, *v, *e, *f)
                    if other_net == net:
                        # Permit only a point join at a named target center, with no overlapping segment.
                        shared = {u, v} & {e, f} & {point(a), point(b)}
                        if distance <= 0.01 and (not shared or
                                any(pt_seg_dist(*p, *e, *f) <= 0.01 for p in {u, v} - shared) or
                                any(pt_seg_dist(*p, *u, *v) <= 0.01 for p in {e, f} - shared)):
                            ok = False
                            break
                    elif distance < (WIDTH + width)/2 + max(
                        PAD_GAP, 3.08*max(WIDTH, width) - (WIDTH+width)/2,
                        11.8 if {net, other_net} & SENSITIVE_3W_NETS else 0.0,
                    ):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                routes.append((sum(math.dist(*s) for s in segments), segments))
        if routes:
            length, segments = min(routes)
            accepted.append({"net": net, "layer": layer, "from": source, "to": dest,
                             "native_pad_ids": [a["primitiveId"], b["primitiveId"]],
                             "length_mil": round(length, 4), "width_mil": WIDTH, "segments": segments})
            existing.extend((layer, u, v, WIDTH, net) for u, v in segments)
    return accepted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", choices=TARGETS, required=True)
    for word in ("dump", "drc", "archive", "out"):
        parser.add_argument(f"--{word}", type=Path, required=True)
    args = parser.parse_args()
    dump, drc = (json.loads(path.read_bytes()) for path in (args.dump, args.drc))
    routes = plan(args.board, dump, drc, Archive(args.archive))
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"board": args.board, "routes": routes}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
