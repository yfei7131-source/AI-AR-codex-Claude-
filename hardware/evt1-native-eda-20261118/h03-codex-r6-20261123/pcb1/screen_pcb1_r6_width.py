"""Screen PCB1 retained-centerline widening on the PR53 native archive."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

PCB1 = ("PCB", "8fbc3cae65886fe5")
LAYERS = (1, 15, 16, 17, 18, 2)
MODIFIABLE = {1, 2, 16, 17}
POWER = {"GND", "3V3_SYS", "1V8_SYS", "1V8_FPGA_IO", "CAM_DOVDD_1V8"}
STATIC = {"LS4_VREF2_EN", "LS3_VREF2_EN", "PRIV_WINDOW_OK"}
MIN_GAP = 6.2
EDGE_GAP = 12.0
TARGET_MIL = 4.0

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for a in ("package", "archive", "dump", "out"):
        p.add_argument(a, type=Path)
    args = p.parse_args()
    sys.path[:0] = [str(args.package / "h03-v4-dfm-u11-2n2-route"),
                    str(args.package / "h03-codex-r4-20261123")]
    import plan_local_routes as arc
    from u11.audit_r3_u11 import load

    raw = load(args.archive).documents[PCB1]
    dump = json.loads(args.dump.read_bytes())
    copper = dump["copper"]
    assert dump["capture"]["identityVerified"] and dump["capture"]["documentUuid"] == PCB1[1]
    assert set(copper["availability"].values()) == {"available"} and copper["arcsAvailable"]
    assert all(not copper[k] for k in ("arcs", "pours", "poured", "fills"))
    assert all(r.payload["fill"][0]["layerId"] in {15, 18} for r in raw
               if r.header["type"] == "LAYER_FILL")
    lines = {r.header["id"]:r.payload for r in raw if r.header["type"] == "LINE"}
    vias = {r.header["id"]:r.payload for r in raw if r.header["type"] == "VIA"}
    assert set(lines)=={r["primitiveId"] for r in copper["lines"]}
    assert set(vias)=={r["primitiveId"] for r in copper["vias"]}
    outline = arc.extract_outline_polygon(dump)
    edges = list(zip(outline, outline[1:]+outline[:1]))
    objects = defaultdict(dict)
    for uid,r in lines.items():
        a,b=(r["startX"],r["startY"]),(r["endX"],r["endY"])
        objects[r["layerId"]][uid] = (r["netName"], "track", (a,b,r["width"]/2))
    spans = {"BV_L1_L2": (1,15), "BV_L5_L6":(18,2)}
    for uid,r in vias.items():
        span = LAYERS if r["viaType"] == "NORMAL" else spans[r["ruleName"]]
        for layer in span:
            objects[layer][uid] = (r["netName"],"via",((r["centerX"],r["centerY"]),r["viaDiameter"]/2))
    for component in dump["components"]:
        for pad in component["pads"]:
            assert not pad["specialPadPresent"]
            layer = pad["layer"]
            uid = pad["primitiveId"]
            objects[layer][uid] = (pad["net"],"pad",arc.pad_box(component,pad))
            if "hole" in pad and pad.get("metallization"):
                # Span is unavailable for component-internal holes. Treat their full measured
                # pad box as an obstacle on all other layers to bound any hidden barrel.
                for other in MODIFIABLE - {layer}:
                    objects[other][uid] = ("","embedded-hole",arc.pad_box(component,pad))
    for region in copper["regions"]:
        assert region["geometryAvailable"]
        if "no-wires" in region["ruleTypeNames"]:
            box = region["bbox"]
            objects[region["layer"]][region["primitiveId"]] = (
                "", "keepout", tuple(box[k] for k in ("minX","minY","maxX","maxY")))

    width_trials = []
    blocked=Counter()
    limit = TARGET_MIL / 2
    for uid,r in lines.items():
        if r["width"] != 3:
            continue
        n,layer=r["netName"],r["layerId"]
        if n not in POWER | STATIC or layer not in MODIFIABLE:
            blocked["excluded_net_or_layer"] += 1
            continue
        if r["locked"]:
            blocked["locked"] += 1
            continue
        a,b,_=objects[layer][uid][2]
        if math.dist(a,b)<1:
            blocked["unreliable_short_primitive"] += 1
            continue
        edge_gap=min(arc.seg_seg_dist(*a,*b,*u,*v) for u,v in edges)-limit
        if edge_gap < EDGE_GAP:
            blocked["edge_gap"] += 1
            continue
        nearest={}
        rejected=False
        for oid,(other,typ,d) in objects[layer].items():
            if oid==uid:
                continue
            if typ=="track":
                u,v,radius=d
                gap=arc.seg_seg_dist(*a,*b,*u,*v)-radius-limit
                if other==n:
                    continue
                needed=MIN_GAP
                if {n,other} & arc.SENSITIVE_3W_NETS:
                    extent=2*radius
                    needed=max(needed,3.08*max(TARGET_MIL,extent)-radius-limit)
            elif typ=="via":
                if other==n:
                    continue
                center,radius=d
                gap=arc.pt_seg_dist(*center,*a,*b)-radius-limit
                needed=MIN_GAP
            else:
                gap=arc.segment_box_distance(a,b,d)-limit
                if other==n and n:
                    if typ=="pad" and gap<0 and min(d[2]-d[0],d[3]-d[1])<TARGET_MIL+0.2:
                        blocked["narrow_same_net_pad"] += 1
                        rejected=True
                        break
                    continue
                needed=MIN_GAP
            if gap+1e-8 < needed:
                blocked[f"{typ}_gap"] += 1
                rejected=True
                break
            if typ not in nearest or gap < nearest[typ][0]:
                nearest[typ]=(gap,oid)
        if rejected:
            continue
        width_trials.append({"id":uid,"net":n,"layer":layer,"before_width_mil":3,
                             "after_width_mil":TARGET_MIL,"start":a,"end":b,
                             "edge_copper_gap_mil":round(edge_gap,5),
                             "nearest_foreign_by_type_within_search":{k:{"gap_mil":round(g,5),"id":id}
                                                                       for k,(g,id) in nearest.items()}})
        objects[layer][uid]=(n,"track",(a,b,limit))
    report={"scope":"Geometry of existing 3 mil tracks to be widened in place on PCB1, no rule change",
            "archive_sha256":sha256(args.archive.read_bytes()).hexdigest(),
            "dump_sha256":sha256(args.dump.read_bytes()).hexdigest(),
            "width_candidates":width_trials,"blocked":dict(blocked)}
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("candidates", len(width_trials), Counter((r["net"],r["layer"]) for r in width_trials))
    print("blocked", blocked)
    for r in width_trials[:12]: print(r["id"],r["net"],r["layer"],r["start"],r["end"],r["edge_copper_gap_mil"])

if __name__=="__main__":
    main()
