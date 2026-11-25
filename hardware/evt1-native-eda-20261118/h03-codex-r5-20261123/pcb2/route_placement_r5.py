"""Check same-layer C11 supply and ground reachability at screened locations."""
import argparse
import json
from pathlib import Path

import grid_bridge_r5 as grid
import plan_bridge_r5 as plan


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("package",type=Path)
    parser.add_argument("placements",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    plan.load_inherited_geometry(args.package)
    baseline=plan.load_baseline(args.package)
    grid.CANDIDATES = [
        ("C11.1","U13.4"),("C11.1","U13.1"),("C11.1","U3.5"),("C11.1","U5.5"),
        ("C11.2","U13.2"),("C11.2","U3.2"),("C11.2","U5.2"),("C11.2","C20.2"),
    ]
    reviewed=[]
    for loc in json.loads(args.placements.read_bytes())["best"][::4]:
        archive,dump,drc,shapes,pads,edges,open_ids=baseline
        edited=pads.copy()
        identities={pads[f"C11.{n}"][2].ref for n in ("1","2")}
        moved=[s for s in shapes if s.ref not in identities]
        for number,p in enumerate(loc["pad_boxes"],1):
            key=f"C11.{number}"
            orig=pads[key][2]
            shape=plan.Shape("pad",orig.ref,orig.net,orig.layers,tuple(p["rectangle"]))
            moved.append(shape)
            edited[key]=(tuple(round(c,4) for c in p["center"]),2,shape)
        plan.load_baseline=lambda path:(archive,dump,drc,moved,edited,edges,open_ids)
        reviewed.append({"anchor_mil":loc["center_mil"],"routes":grid.candidates(args.package)})
    args.output.write_text(json.dumps(reviewed,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
