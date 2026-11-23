#!/usr/bin/env python3
"""Find short pad-to-pad PCB3 routes on R4 copper using conservative native geometry."""

import argparse
from collections import defaultdict
from hashlib import sha256
from itertools import combinations
import json
import math
from pathlib import Path
import sys

SIGNAL_WIDTH = 4.0
RAIL_WIDTH = 6.0
MAX_SPAN = 165.0
MIN_FOREIGN_GAP = 6.2
MIN_EDGE_GAP = 12.0

RAILS = {"GND", "1V8_SYS", "VBUS_5V", "VBAT_R_RET"}
CONTROLS = {"AMP_SD_MODE_1V8", "AMP_SD_REQ_1V8", "CHG_MUTE_GATE", "AMP_R_SD_MODE",
            "BLE_NRESET","CHG_R_ISET","CHG_R_VSET","NTC_TS_R"}
WIDENABLE = RAILS
RF_NETS = {"BLE_ANT_FEED", "BLE_RF_ANT", "BLE_RF_MID", "NRF_DECR_RF"}
BOARD = ("PCB", "1db01a36f669a47a")

def near_segment(obj_box, a, b, margin):
    return (min(a[0], b[0]) - margin <= obj_box[2] and max(a[0], b[0]) + margin >= obj_box[0]
            and min(a[1], b[1]) - margin <= obj_box[3] and max(a[1], b[1]) + margin >= obj_box[1])


def extended_box(a, b, radius):
    return (min(a[0], b[0]) - radius, min(a[1], b[1]) - radius,
            max(a[0], b[0]) + radius, max(a[1], b[1]) + radius)


def inspect_code(package):
    sys.path.insert(0, str(package / "h03-v4-dfm-u11-2n2-route"))
    sys.path.insert(0, str(package / "h03-codex-r4-20261123"))
    import plan_local_routes as inherited
    from u11.audit_r3_u11 import load
    return inherited, load


def path_options(source, dest, inherited):
    paths = list(inherited.diagonal_paths(source, dest))
    for index in (0,1):
        for offset in (0, 7, -7, 12, -12, 20, -20, 30, -30, 42, -42):
            for value in (source[index]+offset,dest[index]+offset):
                joints=[source,(value,source[1]) if index==0 else (source[0],value),
                        (value,dest[1]) if index==0 else (dest[0],value),dest]
                joints=list(dict.fromkeys(joints))
                chamfer=[source]
                for a,b,c in zip(joints,joints[1:],joints[2:]):
                    pre,post=math.dist(a,b),math.dist(b,c)
                    turn=min(4.0,pre/2,post/2)
                    if not turn:
                        continue
                    chamfer.extend([(b[0]+(a[0]-b[0])*turn/pre,b[1]+(a[1]-b[1])*turn/pre),
                                    (b[0]+(c[0]-b[0])*turn/post,b[1]+(c[1]-b[1])*turn/post)])
                chamfer.append(dest)
                paths.append(chamfer)
    for path in paths:
        points = list(dict.fromkeys(tuple(round(v, 4) for v in point) for point in path))
        for a, b in zip(points, points[1:]):
            dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
            if min(dx, dy, abs(dx - dy)) > 0.00011:
                break
        else:
            # Reject reversal at a bend and allow at most 45-degree changes of direction.
            legs = [(b[0]-a[0], b[1]-a[1]) for a,b in zip(points, points[1:])]
            if any(a[0]*b[0]+a[1]*b[1] < math.hypot(*a)*math.hypot(*b)*0.707 - 1e-4
                   for a,b in zip(legs, legs[1:])):
                continue
            if sum(math.hypot(*leg) for leg in legs) <= math.dist(source, dest) + 95:
                yield points


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path)
    ap.add_argument("archive", type=Path)
    ap.add_argument("dump", type=Path)
    ap.add_argument("drc", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    inherited, load = inspect_code(args.package)
    from shapely.geometry import LineString, Point, box
    from shapely.affinity import rotate, scale
    from shapely.ops import unary_union
    dump, drc = (json.loads(p.read_bytes()) for p in (args.dump, args.drc))
    copper = dump["copper"]
    if (not dump["capture"]["identityVerified"] or dump["capture"]["documentUuid"] != BOARD[1]
            or set(copper["availability"].values()) != {"available"}
            or not copper["arcsAvailable"] or any(copper[k] for k in ("arcs", "pours", "poured", "fills"))):
        raise ValueError("Expected identity-verified PCB3 capture with complete supported outer copper")
    pcb = load(args.archive).documents[BOARD]
    vias = {r.header["id"]: r.payload for r in pcb if r.header["type"] == "VIA"}
    if vias.keys() != {v["primitiveId"] for v in copper["vias"]}:
        raise ValueError("Via ID parity failed")
    lines = {r.header["id"]: r.payload for r in pcb if r.header["type"] == "LINE"}
    if lines.keys() != {v["primitiveId"] for v in copper["lines"]}:
        raise ValueError("Track ID parity failed")

    shape_by_layer = {1: [], 2: []}
    pads_by_net_layer = defaultdict(list)
    refs = {}
    anchored_copper = {}
    disconnected = {identifier for row in drc["violations"] if row["rule"] == "Connection Error"
                    for identifier in row["objs"]}
    for component in dump["components"]:
        rf_passive = any(pad["net"] in RF_NETS for pad in component["pads"])
        for pad in component["pads"]:
            center = pad["x"], pad["y"]
            ref = f'{component["designator"]}.{pad["padNumber"]}'
            uid, layer, net = pad["primitiveId"], pad["layer"], pad["net"]
            bounds = inherited.pad_box(component, pad)
            if pad["specialPadPresent"]:
                raise ValueError(f"Unsupported special pad {uid}")
            span = (1, 2) if layer == 12 else (layer,)
            if any(layer not in shape_by_layer for layer in span):
                raise ValueError("Unexpected pad layer")
            for covered_layer in span:
                shape_by_layer[covered_layer].append((uid, net, "pad", bounds, bounds))
            if net not in RAILS | CONTROLS or layer == 12 or "width" not in pad or rf_passive:
                continue
            # Only subtract conservatively inscribed copper under an intended pad entry.
            x, y = center
            w, h = (min(float(pad["shape"][n]), float(pad[k])) - 0.36
                    for n,k in ((1,"width"),(2,"height")))
            if min(w,h)<=0:
                continue
            if pad["shape"][0] == "RECT" and pad["shape"][3]==0:
                footprint = box(x-w/2,y-h/2,x+w/2,y+h/2)
            elif pad["shape"][0]=="ELLIPSE":
                footprint = scale(Point(x,y).buffer(1,quad_segs=32),w/2,h/2)
            else:
                continue
            anchored_copper[uid] = rotate(footprint,pad["rotation"],origin=center)
            pads_by_net_layer[net, layer].append(uid)
            refs[uid] = ref, center, bounds, layer, net

    for row in copper["lines"]:
        uid, layer, net = row["primitiveId"], row["layer"], row["net"]
        a, b = (row["startX"], row["startY"]), (row["endX"], row["endY"])
        radius = row["lineWidth"]/2
        if layer in shape_by_layer:
            shape_by_layer[layer].append((uid, net, "track", extended_box(a,b,radius), (a,b,radius)))
            anchored_copper[uid] = LineString([a,b]).buffer(radius-0.03,quad_segs=32)
        src = lines[uid]
        if (src["layerId"] != layer or src["netName"] != net or src["width"] != row["lineWidth"]
                or math.dist(a, (src["startX"],src["startY"])) > 0.001
                or math.dist(b, (src["endX"],src["endY"])) > 0.001):
            raise ValueError(f"Native track mismatch {uid}")

    for row in copper["vias"]:
        uid, net = row["primitiveId"], row["net"]
        center = row["x"], row["y"]
        radius = row["diameter"]/2
        src = vias[uid]
        if src["viaType"] == "NORMAL":
            span = (1, 2)
        elif (src["viaType"], src["ruleName"]) == ("BLIND", "BV_L1_L2"):
            span = (1,)
        elif (src["viaType"], src["ruleName"]) == ("BLIND", "BV_L5_L6"):
            span = (2,)
        else:
            raise ValueError(f"Unexpected via span: {uid}")
        if (math.dist(center,(src["centerX"],src["centerY"]))>0.001 or net!=src["netName"]
                or row["diameter"]!=src["viaDiameter"] or row["holeDiameter"]!=src["holeDiameter"]):
            raise ValueError(f"Native via mismatch {uid}")
        for layer in span:
            shape_by_layer[layer].append((uid, net, "via", extended_box(center,center,radius), (center,radius)))
        anchored_copper[uid] = Point(*center).buffer(radius-0.03,quad_segs=32)

    for row in copper["regions"]:
        layer = row["layer"]
        if layer not in shape_by_layer:
            continue
        if not row["geometryAvailable"] or set(row["ruleTypeNames"])-{"no-wires","no-pours","no-components"}:
            raise ValueError("Unexpected keepout")
        if "no-wires" in row["ruleTypeNames"]:
            bb = row["bbox"]
            bounds = bb["minX"], bb["minY"], bb["maxX"], bb["maxY"]
            shape_by_layer[layer].append((row["primitiveId"], "", "keepout", bounds, bounds))

    u11, = [part for part in dump["components"] if part["designator"]=="U11"]
    guard = u11["bbox"]
    u11_keepout = guard["minX"]-10, guard["minY"]-10, guard["maxX"]+10, guard["maxY"]+10
    outline = inherited.extract_outline_polygon(dump)
    edges = list(zip(outline, outline[1:]+outline[:1]))

    def distance(a, b, kind, data):
        if kind == "track":
            p,q,radius = data
            return inherited.seg_seg_dist(*a, *b, *p, *q)-radius
        if kind == "via":
            center,radius = data
            return inherited.pt_seg_dist(*center,*a,*b)-radius
        return inherited.segment_box_distance(a,b,data)

    def obstacle(kind,data):
        if kind=="track":
            p,q,radius=data
            return LineString([p,q]).buffer(radius+0.03,quad_segs=32)
        if kind=="via":
            center,radius=data
            return Point(*center).buffer(radius+0.03,quad_segs=32)
        return box(data[0]-0.15,data[1]-0.15,data[2]+0.15,data[3]+0.15)

    obstacles = {uid: obstacle(kind,data)
                 for pool in shape_by_layer.values() for uid,_,kind,_,data in pool}

    roots = {}
    def root(uid):
        parent=roots.setdefault(uid,uid)
        while roots[parent]!=parent:
            parent=roots[parent]
        roots[uid]=parent
        return parent

    for pool in shape_by_layer.values():
        per_net = defaultdict(list)
        for item in pool:
            per_net[item[1]].append(item)
        for net in RAILS | CONTROLS:
            for (u,_,_,ub,_),(v,_,_,vb,_) in combinations(per_net[net],2):
                if u==v or root(u)==root(v) or not near_segment(ub,vb[:2],vb[2:],0.2):
                    continue
                if obstacles[u].distance(obstacles[v])<0.05:
                    roots[root(v)]=root(u)

    isolated = {uid for uid in refs if uid in disconnected}
    candidate_pairs = []
    for (net,layer), pads in pads_by_net_layer.items():
        for u,v in combinations(pads,2):
            if not {u,v}&isolated or root(u)==root(v):
                continue
            if not (refs[u][1] != refs[v][1] and math.dist(refs[u][1],refs[v][1]) <= MAX_SPAN):
                continue
            if refs[u][0].split('.')[0]==refs[v][0].split('.')[0]:
                continue
            candidate_pairs.append((math.dist(refs[u][1],refs[v][1]), net, layer, u, v, refs[v][1]))

    # Existing via/line copper can be the receiving trunk for a disconnected pad.
    # Restrict to short branches, and prefer precise via centers or line endpoints.
    for u in isolated:
        _, a, _, layer, net = refs[u]
        choices = []
        for v, other_net, kind, bounds, data in shape_by_layer[layer]:
            if (other_net != net or kind not in {"via", "track"} or root(u)==root(v)
                    or not near_segment(bounds,a,a,MAX_SPAN)):
                continue
            anchors = [data[0]] if kind=="via" else list(data[:2])
            for b in anchors:
                length=math.dist(a,b)
                if 5 < length <= MAX_SPAN:
                    choices.append((length,net,layer,u,v,b))
        candidate_pairs.extend(sorted(choices)[:18])

    results = []
    occupied_endpoints = set()
    for _,net,layer,u,v,b in sorted(candidate_pairs):
        if {u,v}&occupied_endpoints or root(u)==root(v):
            continue
        from_ref,a,_,_,_ = refs[u]
        to_ref = refs[v][0] if v in refs else f"copper:{v}"
        width = RAIL_WIDTH if net in RAILS and net!="GND" else SIGNAL_WIDTH
        candidates = []
        anchor_roots={root(u),root(v)}
        old_net_copper = [anchored_copper[uid] for uid,on,kind,bb,data in shape_by_layer[layer]
                          if on==net and uid in anchored_copper and root(uid) in anchor_roots
                          and near_segment(bb,a,b,100)]
        anchor_copper = unary_union(old_net_copper)
        for pts in path_options(a,b,inherited):
            nearest = {"pad": (1000, None), "via": (1000, None), "track": (1000, None),
                       "keepout":(1000,None)}
            edge_gap = 1000
            for p,q in zip(pts,pts[1:]):
                if inherited.segment_box_distance(p,q,u11_keepout) < width/2+MIN_FOREIGN_GAP:
                    edge_gap = -1
                    break
                edge_gap = min(edge_gap, min(inherited.seg_seg_dist(*p,*q,*k,*l) for k,l in edges)-width/2)
                new_copper = LineString([p,q]).buffer(width/2+0.03,quad_segs=32).difference(anchor_copper)
                for uid,other_net,kind,bounds,data in shape_by_layer[layer]:
                    if uid in (u,v) or not near_segment(bounds,p,q,40):
                        continue
                    gap = distance(p,q,kind,data)-width/2
                    if other_net == net:
                        # Avoid stripping the electrical meaning of the two explicit pad anchors.
                        if gap < 0.4 and root(uid) not in anchor_roots:
                            edge_gap = -1
                        continue
                    threshold = MIN_FOREIGN_GAP
                    if kind == "track":
                        other_width = data[-1]*2
                        threshold = max(threshold,3.08*max(width,other_width)-(width+other_width)/2
                                        if {net,other_net}&inherited.SENSITIVE_3W_NETS else 0)
                    if gap < threshold + 0.25:
                        gap = new_copper.distance(obstacles[uid])
                    if gap < threshold:
                        edge_gap = -1
                    if gap < nearest[kind][0]:
                        nearest[kind] = gap,uid
            if edge_gap >= MIN_EDGE_GAP:
                path_length = sum(math.dist(p,q) for p,q in zip(pts,pts[1:]))
                candidates.append((path_length,pts,edge_gap,nearest))
        if not candidates:
            continue
        length,pts,edge_gap,nearest = min(candidates)
        segments = list(zip(pts,pts[1:]))
        results.append({"net":net,"layer":layer,"from":from_ref,"to":to_ref,"pad_ids":[u,v],
                        "isolated_drc_anchors":[uid for uid in (u,v) if uid in isolated],
                        "endpoint_kind":"pad" if v in refs else lines[v]["netName"]+" track" if v in lines else "via",
                        "width_mil":width,"length_mil":round(length,4),"segments":segments,
                        "edge_copper_gap_mil":round(edge_gap,4),
                        "nearest_foreign_by_type_within_search":{k:{"gap_mil":round(g,4),"id":uid}
                                                                  for k,(g,uid) in nearest.items() if uid}})
        occupied_endpoints.update((u,v))
        roots[root(v)]=root(u)
        for idx,(p,q) in enumerate(segments):
            uid=f"candidate_{len(results)}_{idx}"
            shape_by_layer[layer].append((uid,net,"track",extended_box(p,q,width/2),(p,q,width/2)))
            obstacles[uid] = obstacle("track",(p,q,width/2))
            roots[uid] = root(u)
    widen = []
    for layer in (1,2):
        pool = shape_by_layer[layer]
        for idx,(uid,net,kind,bounds,data) in enumerate(pool):
            if net not in WIDENABLE or kind != "track" or data[-1] != 1.5:
                continue
            if lines[uid]["locked"] or math.dist(*data[:2]) < 5:
                continue
            a,b = data[:2]
            width = 4
            gap_to_edge = min(inherited.seg_seg_dist(*a,*b,*p,*q) for p,q in edges)-width/2
            if gap_to_edge < MIN_EDGE_GAP or inherited.segment_box_distance(a,b,u11_keepout) < width/2+MIN_FOREIGN_GAP:
                continue
            nearest = {"pad": (1000,None), "via": (1000,None), "track": (1000,None),
                       "keepout": (1000,None)}
            ok = True
            for oid,on,okind,obounds,odata in pool:
                if uid==oid or not near_segment(obounds,a,b,40):
                    continue
                gap=distance(a,b,okind,odata)-width/2
                if on==net:
                    if okind=="pad" and gap<0 and min(obounds[2]-obounds[0],obounds[3]-obounds[1])<width+0.2:
                        ok=False
                    continue
                margin=MIN_FOREIGN_GAP
                if okind=="track" and {net,on}&inherited.SENSITIVE_3W_NETS:
                    other=odata[-1]*2
                    margin=max(margin,3.08*max(width,other)-(width+other)/2)
                if gap<margin:
                    ok=False
                    break
                if gap<nearest[okind][0]:
                    nearest[okind]=gap,oid
            if ok:
                widen.append({"id":uid,"net":net,"layer":layer,"before_width_mil":3,
                              "after_width_mil":width,"start":a,"end":b,
                              "edge_copper_gap_mil":round(gap_to_edge,4),
                              "nearest_foreign_by_type_within_search":{k:{"gap_mil":round(g,4),"id":uid}
                                                                       for k,(g,uid) in nearest.items() if uid}})
                pool[idx]=uid,net,kind,extended_box(a,b,width/2),(a,b,width/2)
    report = {"scope":"Offline local route candidate screen. Native DRC required after typed apply.",
              "archive_sha256":sha256(args.archive.read_bytes()).hexdigest(),
              "dump_sha256":sha256(args.dump.read_bytes()).hexdigest(),
              "drc_sha256":sha256(args.drc.read_bytes()).hexdigest(),
              "airwire_matched_isolated_anchors":len(isolated),"pairs_screened":len(candidate_pairs),
              "routes":results,"width_candidates":widen}
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    for idx,row in enumerate(results):
        print(idx,row["net"],row["layer"],row["from"],row["to"],row["width_mil"],row["segments"])
    for row in widen[:8]:
        print("WIDEN",row["id"],row["net"],row["layer"],row["start"],row["end"],row["nearest_foreign_by_type_within_search"])


if __name__ == "__main__":
    main()
