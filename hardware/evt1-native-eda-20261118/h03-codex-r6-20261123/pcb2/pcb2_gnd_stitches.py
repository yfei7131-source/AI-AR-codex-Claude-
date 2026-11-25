"""Screen manufacturable all-layer GND through stitching for PCB2."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from shapely.geometry import Point, Polygon

import plan_bridge_r5 as geometry


def parse_polygon(raw):
    if not all(x == "L" for x in raw if isinstance(x, str)):
        raise ValueError("Unsupported plane boundary")
    coords = [x for x in raw if not isinstance(x, str)]
    return list(zip(coords[::2], coords[1::2], strict=True))


def load_planes(records):
    result = {}
    for layer in (15, 18):
        fill, = records[f'["LAYER_FILL",{layer}]']["fill"]
        if fill["netName"] != "GND":
            raise ValueError("Layer not assigned to GND")
        outer, *cutouts = map(parse_polygon, fill["path"])
        plane = Polygon(outer, cutouts)
        if not plane.is_valid:
            raise ValueError("Invalid native plane polygon")
        result[layer] = plane
    return result


def distance_to_outline(edges, pt):
    return min(geometry.seg_seg_dist(*pt, *pt, *a, *b) for a,b in edges)


def solve(package,hole,land):
    geometry.load_inherited_geometry(package)
    archive, dump, drc, shapes, pads, edges, _ = geometry.load_baseline(package)
    doc = geometry.read_archive(archive)["PCB",geometry.PCB2]
    vias = geometry.by_kind(doc, "VIA")
    planes = load_planes(geometry.by_kind(doc, "LAYER_FILL"))
    assert not any(v["netName"] == "GND" for v in vias.values() if v["viaType"] == "NORMAL")
    sys.path.insert(0,str(package / "h03-codex-r4-20261123/u11"))
    from audit_r3_u11 import load, records
    native=load(archive)
    bindings=geometry.by_kind(doc,"ATTR")
    used={row["value"] for row in bindings.values() if row["key"]=="Footprint" and row["value"]}
    plated_ground_pads=[(uid,key[1]) for uid in used
                       for key,p in records(native.documents["FOOTPRINT",uid]).items()
                       if key[0]=="PAD" and p["hole"] and p["plated"] and min(p["hole"]["width"],p["hole"]["height"])>0]
    # The list API gives a nominal ROUND hole for some POLYGON SMT pads.
    # The source template's explicit hole field is authoritative.
    assert not plated_ground_pads
    thresholds = {"outer_diameter":land,"drill":hole,"foreign_copper":6.2,"sensitive_track_copper":11.8,
                  "plane_land_boundary":6.2,"copper_to_edge":14,"hole_wall":11.81,"pad_clearance_even_if_same_net":6.2}
    candidates = []
    rejected=Counter()
    for x in range(24,159,2):
        for y in range(28,956,2):
            point=(x,y)
            edge_gap=distance_to_outline(edges,point)-land/2
            if edge_gap<thresholds["copper_to_edge"]:
                rejected["board_edge"]+=1
                continue
            p=Point(x,y)
            if any(not plane.covers(p) for plane in planes.values()):
                rejected["outside_plane"]+=1
                continue
            plane_gap=min(p.distance(plane.boundary) for plane in planes.values())-land/2
            if plane_gap<thresholds["plane_land_boundary"]:
                rejected["plane_land_boundary"]+=1
                continue
            # Compare new through drill to the existing drilled apertures on any shared layer.
            hole_gap, hole_id=min((math.dist(point,(v["centerX"],v["centerY"]))-hole/2-v["holeDiameter"]/2,uid)
                                  for uid,v in vias.items())
            if hole_gap<thresholds["hole_wall"]:
                rejected["hole_wall"]+=1
                continue
            candidate=geometry.capsule("via","","GND",geometry.VIA_LAYERS[""],point,point,land)
            meters={}
            for s in shapes:
                if (s.net=="GND" and s.kind!="pad") or not geometry.close(candidate,s,26):
                    continue
                rule=thresholds["sensitive_track_copper"] if s.kind=="track" and s.net in geometry.SENSITIVE|geometry.SENSITIVE_3W_NETS else thresholds["foreign_copper"]
                gap=geometry.pair_gap(candidate,s)
                if gap<rule:
                    rejected[s.kind]+=1
                    break
                key="paste_pad" if s.kind=="pad" else "foreign_track" if s.kind=="track" else "foreign_via"
                best=meters.get(key)
                if best is None or gap < best[0]:
                    meters[key]=(gap,s.ref,s.net)
            else:
                candidates.append({"point_mil":point,"edge_land_mil":round(edge_gap,5),"plane_land_mil":round(plane_gap,5),
                                   "existing_hole_wall_mil":round(hole_gap,5),"existing_hole":hole_id,
                                   "nearby_limits":{k:{"edge_gap_mil":round(m[0],5),"primitive_id":m[1],"net":m[2]}
                                                    for k,m in sorted(meters.items())}})
    chosen = []
    for label, lo, hi, reference in [
        ("VSYS protection return",125,285,(105,210)),
        ("FPGA reference plane",340,510,(95,420)),
        ("FPGA layer transitions",520,690,(95,590)),
        ("target decoupling return",750,935,(94,830)),
    ]:
        scoped=[r for r in candidates if lo<=r["point_mil"][1]<=hi]
        if scoped:
            nearest=min(scoped,key=lambda row:(math.dist(row["point_mil"],reference),-row["plane_land_mil"]))
            chosen.append(dict(role=label,span="L1–L6 through",net="GND",hole_diameter_mil=hole,
                               land_diameter_mil=land,feasible_grid_points=len(scoped),**nearest))
    for a,b in zip(chosen,chosen[1:]):
        assert math.dist(a["point_mil"],b["point_mil"])-hole>=thresholds["hole_wall"]
    return {"scope":"Offline candidate using actual archived stack records and fully materialized GND fills",
            "native_sha256":sha256(archive.read_bytes()).hexdigest(),
            "capture_sha256":sha256(dump.read_bytes()).hexdigest(),
            "prior_normal_via_by_net":{k:sum(v["netName"]==k and v["viaType"]=="NORMAL" for v in vias.values())
                                       for k in sorted({v["netName"] for v in vias.values() if v["viaType"]=="NORMAL"})},
            "prior_through_plated_gnd_pad_count":len(plated_ground_pads),"ground_plane_ids":[15,18],
            "thresholds_mil":thresholds,"candidates":chosen,"feasible_grid_points":len(candidates),"rej":dict(rejected)}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--hole", type=float, default=8)
    parser.add_argument("--land", type=float, default=16)
    args=parser.parse_args()
    result=solve(args.package,args.hole,args.land)
    print(result["rej"])
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result["candidates"],indent=2))
