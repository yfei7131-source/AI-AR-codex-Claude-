"""Continuous Shapely outer copper envelope and refined PCB2 drill search."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import numpy as np
import shapely
from shapely.affinity import rotate, scale
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import plan_bridge_r5 as geometry
import pcb2_gnd_stitches as stitches


def pad_outline(row):
    a = row["shape"]
    center = (row["x"], row["y"])
    if a[0]=="POLYGON":
        poly=Polygon(stitches.parse_polygon(a[1]))
    elif a[0]=="RECT" and a[3]==0:
        poly=rotate(box(center[0]-a[1]/2,center[1]-a[2]/2,center[0]+a[1]/2,center[1]+a[2]/2),row["rotation"],origin=center)
    elif a[0]=="ELLIPSE":
        poly=rotate(scale(Point(*center).buffer(1,quad_segs=32),a[1]/2,a[2]/2),row["rotation"],origin=center)
    else:
        return None
    if not poly.is_valid:
        raise ValueError(f"Invalid outline for {row['primitiveId']}")
    return poly.buffer(.075,quad_segs=16)


def load_package(package):
    geometry.load_inherited_geometry(package)
    archive, dump, drc, shapes, pads, edges, open_ids=geometry.load_baseline(package)
    doc=geometry.read_archive(archive)["PCB",geometry.PCB2]
    return archive,dump,shapes,pads,edges,open_ids,doc


def solve(package,hole,land,plane_margin):
    archive,dump,shapes,pads,edges,open_ids,doc=load_package(package)
    vias=geometry.by_kind(doc,"VIA")
    planes=stitches.load_planes(geometry.by_kind(doc,"LAYER_FILL"))
    plane=planes[15].intersection(planes[18])
    assert plane.geom_type=="Polygon"
    outer_polygon=Polygon([a for a,b in edges])
    actual={row["primitiveId"]: row for c in json.loads(dump.read_bytes())["components"] for row in c["pads"]}
    geo={}
    for s in shapes:
        if s.kind=="pad":
            outline=pad_outline(actual[s.ref])
            g=outline if outline is not None else box(*s.bbox).buffer(.075)
        elif s.kind=="via":
            g=Point(*s.segment[0]).buffer(s.radius+.015,quad_segs=24)
        else:
            g=LineString(s.segment).buffer(s.radius+.015,quad_segs=24)
        geo[s.ref]=g
    np_x,np_y=np.meshgrid(np.arange(20,161,0.5),np.arange(26,956,0.5))
    points=shapely.points(np_x.ravel(),np_y.ravel())
    land_r=land/2
    case=np.ones(len(points),bool)

    counters={}
    for ident,geometries,threshold,operation in [
      ("outline",[outer_polygon.boundary],land_r+14,"distance"),
      ("plane",[plane],land_r+plane_margin,"inner"),
      ("hole_wall",[Point(v["centerX"],v["centerY"]).buffer(v["holeDiameter"]/2,quad_segs=32) for v in vias.values()],hole/2+11.811,"distance"),
      ("foreign_lands",[geo[s.ref] for s in shapes if s.kind=="pad" and s.net!="GND"],land_r+6.2,"distance"),
      ("gnd_pad_drill_to_mask",[geo[s.ref] for s in shapes if s.kind=="pad" and s.net=="GND"],hole/2+1.97+3.55,"distance"),
      ("foreign_copper",[geo[s.ref] for s in shapes if s.kind in ("track","via") and s.net!="GND"],land_r+6.2,"distance"),
      ("sensitive",[geo[s.ref] for s in shapes if s.kind=="track" and s.net in geometry.SENSITIVE|geometry.SENSITIVE_3W_NETS],land_r+11.8,"distance")
    ]:
        g=unary_union(geometries)
        if operation=="inner":
            distances=shapely.distance(points[case],g.boundary)
            distances[np.logical_not(shapely.covers(g,points[case]))]=-np.inf
        else:
            distances=shapely.distance(points[case],g)
        new=np.nonzero(case)[0][distances>=threshold]
        case[:]=False
        case[new]=True
        counters[ident]=len(new)
        if not len(new):
            break
    candidates=list(zip(np_x.ravel()[case],np_y.ravel()[case],strict=True))
    microphone=next(c for c in json.loads(dump.read_bytes())["components"] if c["designator"]=="MK2")
    microphone_bbox=box(*(microphone["bbox"][key] for key in ("minX","minY","maxX","maxY")))
    outside_mk2=[p for p in candidates if Point(*p).distance(microphone_bbox)>land_r]
    checked=[]
    for label,lo,hi,ref in [("lower_input",25,285,(105,210)),("fpga",290,510,(95,420)),
                             ("fpga_transitions",515,735,(95,590)),("decoupling",740,955,(94,830))]:
        match=[xy for xy in candidates if lo<=xy[1]<=hi]
        if not match:continue
        point=min(match,key=lambda xy:math.dist(xy,ref))
        obj=Point(*point)
        best = {}
        for key, collection in [
            ("all_pads",[s for s in shapes if s.kind=="pad"]),
            ("foreign_tracks",[s for s in shapes if s.kind=="track" and s.net!="GND"]),
            ("foreign_vias",[s for s in shapes if s.kind=="via" and s.net!="GND"]),
            ("sensitive_tracks",[s for s in shapes if s.kind=="track" and s.net in geometry.SENSITIVE|geometry.SENSITIVE_3W_NETS])]:
            best[key]=min((round(obj.distance(geo[s.ref])-land_r,5),s.ref,s.net) for s in collection)
        checked.append({"role":label,"point":point,"clearances_mil":best,
                        "native_hole_wall_mil":round(min(math.dist(point,(v["centerX"],v["centerY"]))-hole/2-v["holeDiameter"]/2 for v in vias.values()),5),
                        "outer_copper_edge_mil":round(obj.distance(outer_polygon.boundary)-land_r,5),
                        "plane_boundary_mil":round(obj.distance(plane.boundary)-land_r,5)})
    return {"role":"GND_L2_L5_return_stitch","screen":"0.5 mil grid, positive-data native planes, full copper and pad geometry",
            "native_planar_viability_only":True,"hole_mil":hole,"land_mil":land,"plane_land_to_boundary_min_mil":plane_margin,"checked":checked,
            "partition_counts":counters,"all_passing_grid_points":len(candidates),"passing_sites_outside_MK2_copper_envelope":len(outside_mk2),"outside_preview":outside_mk2[:10]}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--hole",type=float,default=8)
    parser.add_argument("--land",type=float,default=16)
    parser.add_argument("--plane-margin",type=float,default=6.2)
    args=parser.parse_args()
    r=solve(args.package,args.hole,args.land,args.plane_margin)
    args.output.write_text(json.dumps(r,indent=2)+"\n",encoding="utf8")
    print(json.dumps(r,indent=2))
