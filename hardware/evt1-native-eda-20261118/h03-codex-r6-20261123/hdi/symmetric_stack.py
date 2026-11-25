"""Bounded symmetric 2+2+2 search for a complete R5 K4/PSEL LRCK path."""
from itertools import product
import json
import math
from pathlib import Path
import sys

import screen_hdi_joint as s


NET = "I2S_LRCLK_1V8"
PTH_LAYERS = (16, 17)
TOP = (1, 15, 16)
BOTTOM = (2, 18, 17)
GUARD = s.GUARD
PLANE_CLEARANCE = s.PLANE_CLEARANCE


def update_assignment(ref, net):
    pt, g, _ = s.PADS[ref]
    s.PADS[ref] = (pt,g,net)
    s.OBSTACLES[1] = [(g, identity, net if identity==ref else prev)
                       for g,identity,prev in s.OBSTACLES[1]]


def endpoints(ref, board_layer, span, window, diameter_um):
    hole_r = diameter_um/2000/s.V
    copper_r = hole_r+3
    p = s.PADS[ref][0]
    accepted = []
    for q in s.cells(*window):
        if not s.check_via(q,copper_r,hole_r,span,NET):
            continue
        path = s.route(p,q,board_layer,NET,4)
        if path is None:
            continue
        if board_layer==1 and any(math.dist(q,c) < hole_r+2.5+float(s.BALLS[pin[4:]]["land_diameter_mil"])/2
                                  for pin,(c,_,_) in s.PADS.items() if pin.startswith('U11.')):
            continue
        if board_layer==2:
            # The bottom-side trial keeps the laser aperture outside every
            # existing solderable pad opening (2mil rule + 0.5mil reserve).
            bore = s.circle(*q,hole_r)
            if any(bore.distance(g) < 2.5 for g,ident,_ in s.OBSTACLES[2]
                   if ident in s.PADS and abs(g.centroid.x-q[0])<36 and abs(g.centroid.y-q[1])<36):
                continue
        accepted.append((q,path))
    return accepted


def geometric_stack(source,dest,views,um):
    q1 = endpoints(source,1,TOP,views[0],um)
    q6 = endpoints(dest,2,BOTTOM,views[1],um)
    radius = um / 2000/s.V + 3
    cands=[]
    for p in s.cells(*views[2]):
        if not s.check_via(p,6,3,PTH_LAYERS,NET):
            continue
        near_top = sorted(q1, key=lambda q: math.dist(p,q[0])+q[1]['length_mil'])[:12]
        near_bottom = sorted(q6, key=lambda q: math.dist(p,q[0])+q[1]['length_mil'])[:12]
        top_paths=[]
        bottom_paths=[]
        for coord,outer in near_top:
            if math.dist(p,coord) - 3 - (radius-3) < 0.13/s.V:
                continue
            inner = s.route(coord,p,16,NET,4)
            if inner:
                top_paths.append((coord,outer,inner))
        for coord,outer in near_bottom:
            if math.dist(p,coord) - 3 - (radius-3) < 0.13/s.V:
                continue
            inner = s.route(p,coord,17,NET,4)
            if inner:
                bottom_paths.append((coord,outer,inner))
        for (a, a_outer,a_inner),(b,b_outer,b_inner) in product(top_paths,bottom_paths):
            length = sum(item["length_mil"] for item in (a_outer,a_inner,b_outer,b_inner))
            cands.append((length,a,b,p,a_outer,a_inner,b_outer,b_inner))
    plans=[]
    for length,a,b,p,a_outer,a_inner,b_outer,b_inner in sorted(cands,key=lambda item:item[:4])[:80]:
        p_return=s.plane_return([(a,radius,TOP),(b,radius,BOTTOM)])
        if any(t["components_before"]!=t["components_after"] or t["ground_contact_overlap"] for t in p_return.values()):
            continue
        planes={l:{
             "cutout_to_nearest_plane_boundary_mil":s.plane_antipad(l,a if l==15 else b,radius).distance(s.PLANE[l].boundary),
            "minimum_cutout_radius_mil":radius+PLANE_CLEARANCE,**stat} for l,stat in p_return.items()}
        plans.append(dict(source=source,destination=dest,
                          ball_escape_top=a,ball_escape_bottom=b,native_top_layers=TOP,native_bottom_layers=BOTTOM,
                          blind_diameter_um=um,blind_annulus_mil=3,buried_xy=p,buried_hole_mil=6,
                          buried_land_mil=12,buried_layers=PTH_LAYERS,trace_mil=4,
                          paths=[a_outer,a_inner,b_inner,b_outer],antipads=planes,total_length_mil=length))
        if len(plans)>=3:break
    return dict(start_sites=len(q1),destination_sites=len(q6),route_pairs=len(cands),plans=plans)


def main():
    layouts = {"U11.K4":(165,184,319,349,0.5)}
    if len(sys.argv) > 3:
        layouts = {sys.argv[3]:(171,184,346,389,0.75)}
    results={}
    for ref, src_window in layouts.items():
        if ref != 'U11.K4':
            assert s.PADS[ref][2]==''
            update_assignment('U11.K4','')
            update_assignment(ref,NET)
        for receiver,target_window in (
          ("U10.C3",(125,184,336,405,1)),
          ("J1.P12",(25,94,245,320,1)),
        ):
            for size in (100,75):
                key=ref+'->'+receiver+' '+str(size)
                result=geometric_stack(ref,receiver,(src_window,target_window,(24,184,260,418,3)),size)
                results[key]=result
                Path(sys.argv[2]).write_text(json.dumps(results,indent=2,default=int)+"\n",encoding="utf-8")
                print(key,result['start_sites'],result['destination_sites'],result['route_pairs'],len(result['plans']),flush=True)
        if ref!='U11.K4':
            update_assignment('U11.K4',NET)
            update_assignment(ref,'')
    Path(sys.argv[2]).write_text(json.dumps(results,indent=2,default=int)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
