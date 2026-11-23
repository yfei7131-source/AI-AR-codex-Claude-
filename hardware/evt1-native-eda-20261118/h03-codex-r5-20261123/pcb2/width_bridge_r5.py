"""Screen 3 mil tracks at PCB2 decoupling pads and FPGA reset/CDONE x-y window."""
import argparse
import json
from pathlib import Path

import plan_bridge_r5 as plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    plan.load_inherited_geometry(args.package)
    _,_,_,shapes,pads,edges,_ = plan.load_baseline(args.package)
    names_by_id={p.ref: ref for ref, row in pads.items() if row for _,_,p in (row,)}
    caps={k:p[2] for k,p in pads.items() if p and k.split(".")[0] in plan.CAPS}
    selected=[]
    evaluated=[]
    for i,old in enumerate(shapes):
        if old.kind!="track" or old.radius!=1.5 or old.layers not in {frozenset({1}),frozenset({2})}:
            continue
        layer,=old.layers
        a,b=old.segment
        direct_caps=[name for name,p in caps.items() if p.net==old.net and layer in p.layers
                     and plan.close(old,p,0) and plan.pair_gap(old,p)<=0]
        in_window = old.net.startswith("FPGA_C") and layer==2 and min(a[1],b[1]) >= 460 and max(a[1],b[1]) <= 850
        if not (direct_caps or in_window):
            continue
        record={"track_id":old.ref,"net":old.net,"layer":layer,"from":a,"to":b,
                "touches_caps":direct_caps,"fpga_c_window":in_window,"old_mil":3.0}
        evaluated.append(record)
        for w in (4.0,3.6):
            new=plan.capsule("track",old.ref,old.net,old.layers,a,b,w)
            edge=min(plan.seg_seg_dist(*a,*b,*u,*v) for u,v in edges)-new.radius
            if edge<12:
                record["blocked_by_edge_mil"]=round(edge,4)
                continue
            gaps=[]
            for other in shapes:
                if other.ref == old.ref or other.net==old.net or layer not in other.layers or not plan.close(new,other,30):
                    continue
                new_gap=plan.pair_gap(new,other)
                requirement=plan.FOREIGN_COPPER
                if other.kind=="track":
                    requirement=max(requirement,3.08*max(w,2*other.radius)-new.radius-other.radius,
                                    11.8 if {old.net,other.net} & (plan.SENSITIVE | plan.SENSITIVE_3W_NETS) else 0)
                gaps.append((new_gap - requirement,new_gap,requirement,other.kind,other.ref))
            if gaps:
                margin,gap,requirement,kind,ref=min(gaps)
                limiting={"kind":kind,"object":names_by_id.get(ref,ref),"gap_mil":round(gap,4),
                          "required_mil":round(requirement,4),"margin_mil":round(margin,4)}
            else:
                margin=float("inf")
                limiting=None
            if margin<0:
                record["blocked_by_copper"]=limiting
                continue
            record.pop("blocked_by_copper",None)
            record["new_mil"]=w
            record["limiting_foreign_copper"]=limiting
            record["edge_gap_mil"]=round(edge,4)
            selected.append(record)
            shapes[i]=new
            break
    report={"evaluated":evaluated,"select":selected}
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(selected,indent=2))


if __name__=="__main__":
    main()
