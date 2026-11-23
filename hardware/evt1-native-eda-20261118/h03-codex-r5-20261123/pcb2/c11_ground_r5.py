"""Consolidate and verify the candidate C11.2 to C20.2 return path."""
import argparse
import json
from itertools import combinations
import math
from pathlib import Path

import plan_bridge_r5 as plan


def verify(root, placements):
    _,_,_,shapes,pads,edges,airwires=plan.load_baseline(root)
    loc=placements["best"][0]
    sup,grd=loc["pad_boxes"]
    _, _, donor = pads["C20.2"]
    source_id=pads["C11.2"][2].ref
    moved_ids={pads["C11.1"][2].ref,source_id}
    source=plan.Shape("pad",source_id,"GND",frozenset((2,)),tuple(grd["rectangle"]))
    supply=plan.Shape("pad","new-vsys","VSYS",frozenset((2,)),tuple(sup["rectangle"]))
    obs=[o for o in shapes if o.ref not in moved_ids]+[supply,source]
    assert source_id in airwires and donor.ref not in airwires
    corpus=[o for o in obs if o.net=="GND"]
    parents={o.ref:o.ref for o in corpus}
    def root(ref):
        while ref!=parents[ref]:
            ref=parents[ref]
        return ref
    for a,b in combinations(corpus,2):
        if a.layers&b.layers and plan.close(a,b,.2) and plan.pair_gap(a,b)<=.2:
            parents[root(a.ref)]=root(b.ref)
    assert root(source_id)!=root(donor.ref)
    same_refs={root(source_id), root(donor.ref)}
    # Both point anchors are pad interiors. There is no need to create short solder-pad stubs.
    x0,y0=grd["center"]
    start=(round(x0,1),round(y0,1))
    finish=(28.0,378.0)
    fixed_width=3.6
    def verify_segment(a,b):
        dx,dy=abs(a[0]-b[0]),abs(a[1]-b[1])
        if min(dx,dy,abs(dx-dy)) > .00011:
            return None
        segment=plan.capsule("track","new","GND",frozenset((2,)),a,b,fixed_width)
        gap=min(plan.seg_seg_dist(*a,*b,*x,*y) for x,y in edges)-fixed_width/2
        if gap<12:
            return None
        g={"edge":(gap,None)}
        for o in obs:
            if 2 not in o.layers or not plan.close(o,segment,30):
                continue
            gap=plan.pair_gap(o,segment)
            if o.net=="GND":
                if o.kind=="track" and plan.collinear_overlap(*a,*b,*o.segment[0],*o.segment[1]):
                    return None
                if gap<=.25 and root(o.ref) not in same_refs:
                    return None
                continue
            guard=6.15
            if o.kind=="track":
                guard=max(guard,3.08*max(2*o.radius,fixed_width)-o.radius-fixed_width/2,
                          11.8 if o.net in (plan.SENSITIVE | plan.SENSITIVE_3W_NETS) else 0)
            if gap<guard:
                return None
            current=g.get(o.kind)
            if current is None or gap<current[0]:
                g[o.kind]=(gap,o.ref)
        return g

    def inside(point, pad):
        x,y=point
        x0,y0,x1,y1=pad.bbox
        return x0+.5<x<x1-.5 and y0+.5<y<y1-.5
    assert inside(start,source) and inside(finish,donor)
    base=[start,(74,364),(66,372),(52,372),(50,374),(40,374),
          (38,376),(36,376),(34,378),finish]

    # Try direct and one-jog shortcuts between the proven corridor vertices.
    best={0:(0,0,[base[0]],[])}
    for j in range(1,len(base)):
        ranked=[]
        for i in range(j):
            if i not in best:
                continue
            a,b=base[i],base[j]
            diag=min(abs(b[0]-a[0]),abs(b[1]-a[1]))
            px=math.copysign(diag,b[0]-a[0])
            py=math.copysign(diag,b[1]-a[1])
            points=[(a,b),(a,(a[0]+px,a[1]+py),b),
                    (a,(b[0]-px,b[1]-py),b)]
            for path in points:
                reduced=tuple(dict.fromkeys(tuple(round(u,4) for u in node) for node in path))
                proof=[verify_segment(x,y) for x,y in zip(reduced,reduced[1:])]
                if not proof or any(row is None for row in proof):
                    continue
                count,length,partial,witness=best[i]
                ranked.append((count+len(proof),length+sum(math.dist(x,y) for x,y in zip(reduced,reduced[1:])),
                               [*partial,*reduced[1:]],[*witness,*proof]))
        if ranked:
            best[j]=min(ranked,key=lambda r:r[:2])
    count,length,points,evidence=best[len(base)-1]
    return {"from":"C11.2","to":"C20.2","net":"GND","layer":2,"width_mil":fixed_width,
            "location":loc,"points":points,"count":count,"length_mil":round(length,5),
            "segment_clearances":evidence,
            "limitation":"VSYS loop to U13 power input remains BLOCKED. No EDA operations."}


def main():
    a=argparse.ArgumentParser()
    a.add_argument("package",type=Path)
    a.add_argument("placements",type=Path)
    a.add_argument("output",type=Path)
    opt=a.parse_args()
    plan.load_inherited_geometry(opt.package)
    report=verify(opt.package,json.loads(opt.placements.read_bytes()))
    opt.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
