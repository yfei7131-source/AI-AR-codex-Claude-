"""Find conservative C11 bottom placement windows before assessing new routing."""
import argparse
import json
import math
from itertools import product
from pathlib import Path

import plan_bridge_r5 as plan

BODY_GAP = 4
PAD_GAP = 6.15
CU_EDGE = 12.0
MAX_DISTANCE = 210


def screen(root):
    r4=root/"h03-codex-r4-20261123"
    dump=json.loads((r4/"verification/pcb2-restore-copper.json").read_bytes())
    _,_,_,shapes,pads,edges,airwires=plan.load_baseline(root)
    cap=next(p for p in dump["components"] if p["designator"]=="C11")
    target=pads["U13.4"][0]
    assert cap["layer"]==2
    the_pads={p["padNumber"]:p for p in cap["pads"]}
    assert {p["primitiveId"] for p in the_pads.values()} <= airwires
    cap_ids={p["primitiveId"] for p in the_pads.values()}
    obstacles=[o for o in shapes if 2 in o.layers and o.ref not in cap_ids]
    for p in the_pads.values():
        old=pads[f"C11.{p['padNumber']}"][2]
        assert not any(o.net==p["net"] and plan.close(o,old,0) and plan.pair_gap(o,old)<=0 for o in obstacles)
    boxes=[]
    for comp in dump["components"]:
        if comp["layer"]!=cap["layer"] or comp==cap:
            continue
        b=comp["bbox"]
        boxes.append(tuple(b[k] for k in ("minX","minY","maxX","maxY")))
    orig=cap["bbox"]
    local=(orig["minX"]-cap["x"],orig["minY"]-cap["y"],orig["maxX"]-cap["x"],orig["maxY"]-cap["y"])
    accepted = []
    body_fit = 0
    for turn in range(4):
        def rotate(x,y):
            return ((x,y),(-y,x),(-x,-y),(y,-x))[turn]
        corners=[rotate(x,y) for x,y in product((local[0],local[2]),(local[1],local[3]))]
        e0,e1,e2,e3=min(x for x,y in corners),min(y for x,y in corners),max(x for x,y in corners),max(y for x,y in corners)
        pinfo=[]
        for key in ("1","2"):
            p=the_pads[key]
            dx,dy=rotate(p["x"]-cap["x"],p["y"]-cap["y"])
            hx,hy=p["width"]/2,p["height"]/2
            if turn%2:
                hx,hy=hy,hx
            pinfo.append((p["net"],dx,dy,hx,hy))
        guess=(target[0]-pinfo[0][1],target[1]-pinfo[0][2])
        for x,y in product(range(20,163),range(max(0,round(guess[1]-MAX_DISTANCE)),round(guess[1]+MAX_DISTANCE)+1)):
            dist=math.dist((x,y),guess)
            if dist>MAX_DISTANCE or dist<100:
                continue
            box=x+e0,y+e1,x+e2,y+e3
            if box[0]<BODY_GAP or box[2]>181.1024-BODY_GAP:
                continue
            if any(not (l > box[2]+BODY_GAP or r < box[0]-BODY_GAP or d > box[3]+BODY_GAP or t < box[1]-BODY_GAP)
                   for l,d,r,t in boxes):
                continue
            body_fit+=1
            new_pads=[]
            for net,dx,dy,hx,hy in pinfo:
                cx,cy=x+dx,y+dy
                rect=cx-hx,cy-hy,cx+hx,cy+hy
                if rect[0]<CU_EDGE or rect[2]>181.1024-CU_EDGE or rect[1]<CU_EDGE:
                    break
                new=plan.Shape("pad","candidate",net,frozenset((2,)),rect)
                if any(plan.close(o,new,PAD_GAP) and plan.pair_gap(o,new)<PAD_GAP for o in obstacles):
                    break
                new_pads.append({"net":net,"center":[cx,cy],"rectangle":rect})
            else:
                accepted.append((dist,{"center_mil":[x,y],"current_side":2,"turn_relative_deg":turn*90,
                                       "supply_to_U13_4_mil":round(dist,3),"pad_boxes":new_pads}))
    accepted.sort(key=lambda row:row[0])
    print(len(accepted),body_fit)
    return {"component_body_margin_mil_not_assembly_clearance":BODY_GAP,"pad_to_copper_mil":PAD_GAP,
            "pad_to_edge_mil":CU_EDGE,"search_target":"U13.4","scope":"bottom 100–210 mil radius, no new routing",
            "envelope_fits":body_fit,"isolated_copper_fits":len(accepted),
            "best":[row for _,row in accepted[:15]]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("package",type=Path)
    ap.add_argument("output",type=Path)
    args=ap.parse_args()
    plan.load_inherited_geometry(args.package)
    result=screen(args.package)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result["best"][:2],indent=2))


if __name__=="__main__":
    main()
