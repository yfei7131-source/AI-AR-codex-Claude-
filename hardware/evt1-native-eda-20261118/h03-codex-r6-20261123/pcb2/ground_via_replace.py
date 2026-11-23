"""Probe exact-center GND drill replacements rather than crowding existing holes."""
import argparse
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box

import ground_stitch_refine as refn
import plan_bridge_r5 as geometry
import pcb2_gnd_stitches as stitches


def solve(package):
    archive,dump,shapes,pads,edges,opens,doc=refn.load_package(package)
    vias=geometry.by_kind(doc,"VIA")
    plane=stitches.load_planes(geometry.by_kind(doc,"LAYER_FILL"))
    native=json.loads(dump.read_bytes())
    padlist={q["primitiveId"]:(c["designator"],q) for c in native["components"] for q in c["pads"]}
    outer=Polygon([a for a,b in edges])
    geos={}
    for s in shapes:
        if s.kind=="via":
            g=Point(*s.segment[0]).buffer(s.radius+.02,quad_segs=32)
        elif s.kind=="track":
            g=LineString(s.segment).buffer(s.radius+.02,quad_segs=32)
        else:
            g=refn.pad_outline(padlist[s.ref][1])
            if g is None:
                g=box(*s.bbox).buffer(.075)
        geos[s.ref]=g
    reviewed=[]
    for uid,v in vias.items():
        if v["viaType"]!="BLIND" or v["netName"]!="GND":
            continue
        point=v["centerX"],v["centerY"]
        P=Point(*point)
        hole,land=6.0,12.0
        fits_plane={str(k): round(P.distance(g.boundary)-land/2,6) if g.contains(P) else -1
                    for k,g in plane.items()}
        edge=P.distance(outer.boundary)-land/2
        holes=min((math.dist(point,(o["centerX"],o["centerY"]))-hole/2-o["holeDiameter"]/2,k)
                  for k,o in vias.items() if k!=uid)
        exterior=[]
        for s in shapes:
            if s.ref==uid:
                continue
            gap=P.distance(geos[s.ref])-land/2
            if s.kind=="pad":
                if s.net=="GND":
                    # Drill-to-neighbor mask clearance, not a copper clearance on this same net.
                    exterior.append((P.distance(geos[s.ref])-hole/2-1.97,3.55,s.ref,s.net,"gnd_pad_drill_vs_opening"))
                else:
                    exterior.append((gap,6.2,s.ref,s.net,"foreign_pad"))
            elif s.net!="GND":
                g=11.8 if s.kind=="track" and s.net in geometry.SENSITIVE|geometry.SENSITIVE_3W_NETS else 6.2
                exterior.append((gap,g,s.ref,s.net,"foreign_"+s.kind))
        checks = ([(v,6.2,None,"GND","plane_"+k) for k,v in fits_plane.items()]
                  +[(edge,14,None,"","outer_copper_edge"),
                    (holes[0],11.811,holes[1],vias[holes[1]]["netName"],"hole_wall")]+exterior)
        sorted_limits=sorted(checks,key=lambda row:row[0]-row[1])
        result={"prior_primitive_id":uid,"prior_span":v["ruleName"],"coordinate_mil":point,
                "new_drill_mil":hole,"new_land_mil":land,
                "viable":sorted_limits[0][0]>=sorted_limits[0][1],"margin_mil":round(sorted_limits[0][0]-sorted_limits[0][1],6),
                "limiting":[{"gap_mil":round(g,6),"limit_mil":lim,"primitive":oid,"net":net,"type":kind}
                            for g,lim,oid,net,kind in sorted_limits[:5]]}
        reviewed.append(result)
    return {"scope":"Same XY replace archived blind with 6/12 mil through GND. Preserves both planes and checks both outer layers, 11.811 mil native hole wall, and actual copper outlines.",
            "candidates":sorted(reviewed,key=lambda r:r["margin_mil"],reverse=True)}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    a=parser.parse_args()
    report=solve(a.package)
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report["candidates"][:5],indent=2))
