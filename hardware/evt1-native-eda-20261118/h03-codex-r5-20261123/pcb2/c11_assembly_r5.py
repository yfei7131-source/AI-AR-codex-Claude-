"""Compare the C11 physical-body estimate and original footprint envelopes."""
import argparse
import json
import math
from pathlib import Path

MM_PER_MIL = 0.0254

# Nominal bodies, not tolerance-qualified chip procurement dimensions.
BODY_XY_MM = {"C11": (0.6, 0.3), "C20": (0.5, 1.0), "C22": (0.5, 1.0),
              "U3": (1.0, 1.0), "U5": (1.0, 1.0), "U6": (1.0, 1.0),
              "U14": (2.9, 1.6)}
CLASSES = {"C11": "EIA 0201", "C20": "EIA 0402", "C22": "EIA 0402",
           "U3": "XSON6", "U5": "XSON6", "U6": "X2SON4", "U14": "TSOT-23-6"}


def box_gap(a, b):
    return math.hypot(max(a[0]-b[2], b[0]-a[2], 0), max(a[1]-b[3], b[1]-a[3], 0))


def body_box(ref, x, y):
    w, h = (mm / (2*MM_PER_MIL) for mm in BODY_XY_MM[ref])
    return x-w, y-h, x+w, y+h


def as_bbox(component):
    return tuple(component["bbox"][k] for k in ("minX", "minY", "maxX", "maxY"))


def run(dump, loc):
    comps={c["designator"]:c for c in dump["components"]}
    cap=comps["C11"]
    cap_body=body_box("C11",*loc)
    l,d,r,t=as_bbox(cap)
    x,y=loc
    cap_envelope=(x+cap["x"]-r, y+cap["y"]-t, x+cap["x"]-l, y+cap["y"]-d)
    results=[]
    for ref in BODY_XY_MM.keys() - {"C11"}:
        neighbor=comps[ref]
        physically=box_gap(cap_body,body_box(ref,neighbor["x"],neighbor["y"]))
        swept=box_gap(cap_envelope,as_bbox(neighbor))
        rule={"EIA 0402":6,"TSOT-23-6":8}.get(CLASSES[ref])
        results.append({"reference":ref,"package":CLASSES[ref],"nominal_body_to_body_mil":round(physically,4),
                        "native_envelope_gap_mil":round(swept,4),"recommended_spacing_mil":rule,
                        "leadless_screen_at_qfn_proxy_40mil":physically>=40 if rule is None else None})
    return {"proposed_anchor_mil":loc,"cap_package":CLASSES["C11"],
            "scope":"Nominal body in placement coordinates. Verify selected MLCC dimensions and SMT class with manufacturer.",
            "distance_method":"Minimum axis-aligned body-to-body edge distance, physical package bounds distinct from native footprint envelope.",
            "scoped_neighbors":sorted(results,key=lambda r:r["nominal_body_to_body_mil"]),
            "sources":["https://jlcpcb.com/help/article/minimum-spacing-for-smd-components",
                       "https://www.nexperia.com/packages/SOT1202.html",
                       "https://www.analog.com/media/en/technical-documentation/data-sheets/LTC6993-6993-1-6993-2-6993-3-6993-4.pdf"],
            "release_state":"BLOCKED. Leadless package class, part tolerances, connector assembly and complete VSYS routing need validation."}


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dump",type=Path)
    ap.add_argument("output",type=Path)
    args=ap.parse_args()
    report=run(json.loads(args.dump.read_bytes()),(93,364))
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))
