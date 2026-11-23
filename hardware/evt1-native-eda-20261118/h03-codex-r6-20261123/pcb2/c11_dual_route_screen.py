"""Bounded same-face C11 supply/return-and-placement screen with no new drill."""
import argparse
from c11_route_tree import RouteTree
from itertools import product
import json
import math
from pathlib import Path

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import ground_stitch_refine as refined
import plan_bridge_r5 as geometry


WIDTH = 3.6
GUARD = 6.2
EDGE = 12


def length(pts):
    return sum(math.dist(x,y) for x,y in zip(pts,pts[1:]))


def bevel_lines(a,b):
    dx,dy = b[0]-a[0],b[1]-a[1]
    diag = min(abs(dx),abs(dy))
    ux,uy = math.copysign(diag,dx),math.copysign(diag,dy)
    bends = [(a[0]+ux,a[1]+uy),(b[0]-ux,b[1]-uy)]
    for t in (.25,.5,.75):
        offset_x=(dx-ux)*t
        offset_y=(dy-uy)*t
        bends.append(((a[0]+offset_x,a[1]+offset_y),(a[0]+offset_x+ux,a[1]+offset_y+uy)))
    for bend in bends:
        interior=bend if isinstance(bend[0],tuple) else (bend,)
        pts=tuple(dict.fromkeys((a,*interior,b)))
        yield pts


def pad_shape(p):
    outline=refined.pad_outline(p)
    if outline is None:
        return box(p["x"]-p["width"]/2,p["y"]-p["height"]/2,
                   p["x"]+p["width"]/2,p["y"]+p["height"]/2).buffer(.075)
    return outline


def native_component_bbox(c):
    b=c["bbox"]
    return box(*(b[key] for key in ("minX","minY","maxX","maxY")))


def solve(package,route_tree=False):
    archive,dump,shapes,pads,edges,open_ids,doc=refined.load_package(package)
    items=json.loads(dump.read_bytes())["components"]
    idx={q["primitiveId"]: q for c in items for q in c["pads"]}
    cap=next(c for c in items if c["designator"]=="C11")
    old_anchor=cap["x"],cap["y"]
    assert cap["layer"]==2 and all(q["primitiveId"] in open_ids for q in cap["pads"])
    assert len(cap["pads"])==2
    movables={q["primitiveId"] for q in cap["pads"]}
    outline=Polygon([a for a,b in edges])
    landing=outline.buffer(-EDGE)
    guards={}
    scopes={}
    screened_layer=(2,)
    targets={
        "VSYS":[("U13.1",pads["U13.1"][0]),("U13.4",pads["U13.4"][0])],
        "GND":[("U13.2",pads["U13.2"][0]),("GND via a72d849708c0d56e",(126.0,212.0)),
               ("GND via 10f21b62526a4b35",(60.0,198.0))],
    }
    for layer in screened_layer:
        geometry_rows=[]
        for item in shapes:
            if item.ref in movables or layer not in item.layers:
                continue
            if item.kind=="pad":
                g=pad_shape(idx[item.ref])
            elif item.kind=="via":
                g=Point(*item.segment[0]).buffer(item.radius+.025,quad_segs=24)
            else:
                g=LineString(item.segment).buffer(item.radius+.025,quad_segs=24)
            boundary=11.8 if item.kind=="track" and item.net in geometry.SENSITIVE|geometry.SENSITIVE_3W_NETS else GUARD
            geometry_rows.append((item.net,g,boundary,item.ref))
        scopes[layer]={net:[(g,r,uid) for n,g,r,uid in geometry_rows if n!=net] for net in targets}
        for net in targets:
            guards[net]=unary_union([g.buffer(r+WIDTH/2,quad_segs=16) for g,r,_ in scopes[layer][net]])
    pad_forbidden={net:unary_union([g.buffer(clearance,quad_segs=16) for g,clearance,_ in scopes[2][net]]) for net in targets}
    trees={net:RouteTree(guards[net],targets[net],bevel_lines) for net in guards} if route_tree else {}
    cap_body=native_component_bbox(cap)
    other_components={c["designator"]:native_component_bbox(c) for c in items if c["layer"]==2 and c!=cap}
    component_cells=unary_union([g.buffer(6,quad_segs=16) for g in other_components.values()])
    tested=0
    assembly_screened=0
    pad_screened=0
    supply_direct=0
    paired=[]
    for turn,x,y in product(range(0,360,90),range(24,159,2),range(104,379,2)):
        dx,dy=x-old_anchor[0],y-old_anchor[1]
        metal=translate(rotate(cap_body,turn,origin=old_anchor),dx,dy)
        if component_cells.intersects(metal) or not outline.covers(metal):
            continue
        assembly_screened+=1
        group={}
        for p in cap["pads"]:
            g=translate(rotate(pad_shape(p),turn,origin=old_anchor),dx,dy)
            if not landing.covers(g) or pad_forbidden[p["net"]].intersects(g):
                break
            move_xy=translate(rotate(Point(p["x"],p["y"]),turn,origin=old_anchor),dx,dy)
            group[p["net"]]=(g,tuple(round(v,4) for v in (move_xy.x,move_xy.y)))
        else:
            pad_screened+=1
            variants={}
            for net,(g,launch) in group.items():
                other=group["GND" if net=="VSYS" else "VSYS"][0]
                complete=[]
                for target,end in targets[net]:
                    if math.dist(launch,end)>160:
                        continue
                    for path in bevel_lines(launch,end):
                        line=LineString(path)
                        tested+=1
                        if (line.distance(other)<GUARD+WIDTH/2 or line.intersects(guards[net])
                            or not outline.buffer(-(EDGE+WIDTH/2)).covers(line)):
                            continue
                        complete.append((length(path),path,line,target))
                if route_tree:
                    for cost,path,line,target in trees[net].path(launch):
                        tested+=1
                        if (line.distance(other)>=GUARD+WIDTH/2 and cost<165
                                and outline.buffer(-(EDGE+WIDTH/2)).covers(line)):
                            complete.append((cost,path,line,target))
                variants[net]=sorted(complete,key=lambda r:r[0])
            if variants["VSYS"]:
                supply_direct+=1
            for vsys,gnd in product(variants["VSYS"],variants["GND"]):
                if vsys[2].distance(gnd[2])<GUARD+WIDTH:
                    continue
                if vsys[3]=="U13.4" and gnd[3]=="GND via 10f21b62526a4b35":
                    continue
                pair={"anchor_mil": [x,y],"turn_deg":turn,"vsys": {"target":vsys[3],"points":vsys[1],"length_mil":vsys[0]},
                      "gnd":{"target":gnd[3],"points":gnd[1],"length_mil":gnd[0]},
                      "nearest_envelope":min((metal.distance(g),n) for n,g in other_components.items())}
                paired.append((vsys[0]+gnd[0],pair))
                break
    return {"scope":"Bounded current bottom-face alternate placement with two same-layer paths; no FPGA/AVDD reroute and new blind not allowed",
            "octilinear_grid_added":route_tree,"outline_contained_body_and_6mil_envelope_pass":assembly_screened,"new_pads_pass":pad_screened,
            "path_geometries_tested":tested,"vsys_routes_found":supply_direct,
            "two_path_placement_candidates":len(paired),"best":[p for _,p in sorted(paired,key=lambda k:k[0])[:8]]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--route-tree",action="store_true")
    a=parser.parse_args()
    report=solve(a.package,a.route_tree)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))
