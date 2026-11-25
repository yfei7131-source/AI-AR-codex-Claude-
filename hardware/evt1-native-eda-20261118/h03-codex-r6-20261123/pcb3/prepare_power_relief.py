"""Build an isolated two-plane relief trial for the PCB3 C1–C8 power bridge."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[2]
R4 = PACKAGE / "h03-codex-r4-20261123"
R5 = PACKAGE / "h03-codex-r5-20261123"
sys.path[:0] = [str(R5 / "u11"), str(R4 / "u11"), str(R4)]

import verify_c1_c8_power as prior
from audit_r3_u11 import load, records
from verify_pcb1_spur import point_to_segment, segment_distance

DOC = ("PCB", "1db01a36f669a47a")
PLANES = {15, 18}
VIA = prior.VIA
APOTHEM_MIL = 12.4
VERTICES = 64
TOP_WITNESS = "00975084d1ffdc7c"


def decode_ring(path):
    if path[2] != "L" or path[:2] != path[-2:]:
        raise ValueError("Unexpected non-closed or non-linear plane boundary")
    values = path[:2] + path[3:]
    return list(zip(values[::2], values[1::2], strict=True))


def inside(point, vertices):
    x, y = point
    return bool(sum((a[1] > y) != (b[1] > y) and
                    x < a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
                    for a,b in zip(vertices, vertices[1:])) % 2)


def boundary_distance(point, vertices):
    return min(point_to_segment(point, a, b) for a,b in zip(vertices, vertices[1:]))


def relief_path():
    radius = (APOTHEM_MIL + 0.001) / math.cos(math.pi / VERTICES)
    rim = [(round(VIA[0] + radius * math.cos(-2*math.pi*i/VERTICES), 6),
            round(VIA[1] + radius * math.sin(-2*math.pi*i/VERTICES), 6)) for i in range(VERTICES)]
    rim.append(rim[0])
    return [*rim[0], "L", *(coord for xy in rim[1:] for coord in xy)]


def controlled_geometry(source, copper):
    prior.geo.load, prior.geo.records = load, records
    prior.geo.point_to_segment, prior.geo.segment_distance = point_to_segment, segment_distance
    board = records(load(source).documents[DOC])
    top, bottom_rows, inner = prior.board_objects(R4, source, board, copper)
    bottom = [(obj,bounds) for obj,bounds in bottom_rows if obj.name not in prior.OLD_MODE]
    removed = [obj for obj,_ in bottom_rows if obj.name in prior.OLD_MODE]
    if len(removed) != len(prior.OLD_MODE) or any(obj.net != prior.MODE_NET for obj in removed):
        raise ValueError("Control branch differs from inherited source")
    contacts = set()
    same_net = [(obj,bounds) for obj,bounds in bottom if obj.net == prior.MODE_NET]
    for obj in removed:
        contacts.update(ref for distance, ref in prior.geo.stroke_gaps(*obj.points, obj.radius, same_net, "", 0)
                        if distance <= 0)
    if contacts != {"U10.A1", prior.RETAINED_MODE}:
        raise ValueError(f"Unexpected native ground or control branch contacts: {contacts}")
    control = [prior.entry(prior.MODE_NET, "new-control", a, b, 4)
               for a,b in zip(prior.MODE_ROUTE, prior.MODE_ROUTE[1:])]
    measured = {"control": min(prior.geo.nearest(*line.points, 2, bottom, prior.MODE_NET, 25) for line in control)}
    bottom += [(line,line.bounds) for line in control]
    measured.update({
        "power_top": prior.geo.nearest(*prior.TOP, 2, top, prior.POWER_NET, 25),
        "power_bottom": prior.geo.nearest(*prior.BOTTOM, 2, bottom, prior.POWER_NET, 25),
        "via_top": prior.geo.nearest(VIA,VIA,6,top,prior.POWER_NET,25),
        "via_bottom": prior.geo.nearest(VIA,VIA,6,bottom,prior.POWER_NET,25),
        "via_inner_signal": prior.geo.nearest(VIA,VIA,6,inner,prior.POWER_NET,25),
    })
    if min(value[0] for value in measured.values()) < 6.15 or measured["via_inner_signal"][0] + 6 <= 12.5:
        raise ValueError(f"R5 copper or reference plane projection blocked the candidate: {measured}")
    via_holes = prior.microvia.hole_objects(board)
    hole_gap = min(math.dist(VIA, xy)-radius-3 for _,net,xy,radius,_ in via_holes if net != prior.POWER_NET)
    if hole_gap < 10:
        raise ValueError("Existing drilled hole is too close to the new plated hole")
    donor = board["LINE", TOP_WITNESS]
    a,b = ((donor[end+"X"],donor[end+"Y"]) for end in ("start", "end"))
    if donor["netName"] != prior.POWER_NET or donor["layerId"] != 1 or point_to_segment(prior.TOP[0],a,b) > 0.001:
        raise ValueError("The top route would not land on the named power donor")
    return board, measured, hole_gap


def make(source, copper, out):
    board, measured, hole_gap = controlled_geometry(source, copper)
    _, record_path = None, relief_path()
    deltas = {}
    closest_existing_plane_via = {}
    for row_id in sorted(PLANES):
        key = "LAYER_FILL", json.dumps(["LAYER_FILL", row_id], separators=(",", ":"))
        original = board[key]
        single, = original["fill"]
        if single["netName"] != "GND" or single["layerId"] != row_id or single["width"] != 0:
            raise ValueError("Unexpected inner-plane representation")
        outline, *openings = [decode_ring(item) for item in single["path"]]
        if not inside(VIA, outline) or any(inside(VIA, item) for item in openings):
            raise ValueError("Prototype via is not in the body of the expected plane")
        max_radius = max(math.dist(VIA, p) for p in decode_ring(record_path))
        neck = min(boundary_distance(VIA, item) for item in (outline, *openings)) - max_radius
        if neck < 7:
            raise ValueError("Relief would leave an inadequate ground bridge or merge into another void")
        plane_vias = [r for (kind,_), r in board.items() if kind=="VIA" and (
            r["viaType"]=="NORMAL" or r["ruleName"]==({15:"BV_L1_L2",18:"BV_L5_L6"}[row_id]))]
        closest = min(math.dist(VIA, (via["centerX"],via["centerY"])) - via["viaDiameter"]/2 - max_radius
                      for via in plane_vias)
        if closest < 6:
            raise ValueError("Relief removal would touch another via's annulus")
        closest_existing_plane_via[str(row_id)] = round(closest,6)
        deltas[key] = original | {"fill":[single | {"path":[*single["path"],record_path]}]}

    with ZipFile(source) as archive:
        member, = [path for path in archive.namelist() if path.endswith(".epru")]
        lines = archive.read(member).splitlines(keepends=True)
        active, seen = False, set()
        for idx, line in enumerate(lines):
            header, payload = line.split(b"||",1)
            info = json.loads(header)
            if info["type"] == "DOCHEAD":
                doc = json.loads(payload.rstrip(b"\r\n").removesuffix(b"|"))
                active = (doc["docType"],doc["uuid"]) == DOC
            key = info["type"],info.get("id")
            if active and key in deltas:
                suffix = b"|\r\n" if line.endswith(b"\r\n") else b"|\n"
                lines[idx] = header+b"||"+json.dumps(deltas[key],separators=(",",":")).encode()+suffix
                seen.add(key)
        if seen != deltas.keys():
            raise ValueError("Could not identify every intended plane record")
        with ZipFile(out,"x") as target:
            target.comment = archive.comment
            for item in archive.infolist():
                target.writestr(item, b"".join(lines) if item.filename==member else archive.read(item))
    prior_docs, candidate = (load(path).documents for path in (source,out))
    if prior_docs.keys()!=candidate.keys():
        raise ValueError("Unexpected project inventory change")
    for key,doc in prior_docs.items():
        expected = records(doc) | (deltas if key==DOC else {})
        if expected!=records(candidate[key]):
            raise ValueError(f"Unexpected unscoped archive edit {key}")
    return {"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "candidate_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
            "via_xy_mil":VIA,"hole_diameter_mil":6,"outer_diameter_mil":12,
            "plane_apothem_mil":APOTHEM_MIL,"plane_to_via_copper_min_mil":round(boundary_distance(VIA,decode_ring(record_path))-6,6),
            "retained_plane_ligament_min_mil":round(neck,6),
            "existing_plane_via_gap_mil":closest_existing_plane_via,"nearest_foreign_existing_hole_wall_mil":round(hole_gap,6),
            "foreign_copper_clearance_mil":{key:(round(value[0],6),value[1]) for key,value in measured.items()},
            "plane_records": [key[1] for key in deltas],
            "scope":"Nominal PCB3 layout trial using native L2/L5 GND topology. Plane records only here; via and routing written in EasyEDA."}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("archive","copper","out"):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    print(json.dumps(make(args.archive,args.copper,args.out),indent=2))
