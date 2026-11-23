"""Screen independently disconnected PCB2 endpoints with archived copper."""
from collections import defaultdict, Counter
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
import sys

WIDTH = 4.0
EDGE = 12.0
FOREIGN_COPPER = 6.15
PCB2 = "9ce45f14cb79dc9d"
CAPS = frozenset(("C5", "C8", "C9", "C10", "C11", "C12", "C31", "C32"))
PRIORITY = frozenset(("1V2_FPGA_CORE", "1V2_FPGA_PLL", "1V8_FPGA_IO", "1V8_FPGA_VPP", "1V8_SYS",
                      "FPGA_CRESET_B", "FPGA_CDONE_VSYNC_N", "FPGA_1V2_SENSE", "VSYS", "GND"))
VIA_LAYERS = {"": frozenset((1,15,16,17,18,2)), "BV_L1_L2": frozenset((1,15)),
              "BV_L5_L6": frozenset((18,2))}
SENSITIVE = frozenset(("host_sck", "opt_sck", "OPT_SCK_L", "OPT_SCK_R", "clk_48m",
                       "FPGA_CDONE_VSYNC_N", "FPGA_CRESET_B"))


@dataclass
class Shape:
    kind: str
    ref: str
    net: str
    layers: frozenset
    bbox: tuple
    # Tracks and vias have a two-point capsule, with coincident points for vias.
    segment: tuple | None = None
    radius: float = 0


def pair_gap(a, b):
    if a.segment and b.segment:
        return seg_seg_dist(*a.segment[0], *a.segment[1], *b.segment[0], *b.segment[1]) - a.radius - b.radius
    if a.segment or b.segment:
        if b.segment:
            a,b = b,a
        return segment_box_distance(*a.segment,b.bbox) - a.radius
    l, t, r, d = a.bbox
    x, y, x1, y1 = b.bbox
    return math.hypot(max(l - x1, x - r, 0), max(t - y1, y - d, 0))


def close(a,b,margin):
    return not (a.bbox[0] > b.bbox[2] + margin or a.bbox[2] < b.bbox[0] - margin
                or a.bbox[1] > b.bbox[3] + margin or a.bbox[3] < b.bbox[1] - margin)


def capsule(kind, ref, net, layers, a, b, width):
    xmin, xmax = sorted((a[0], b[0]))
    ymin, ymax = sorted((a[1], b[1]))
    radius = width / 2
    return Shape(kind,ref,net,layers,(xmin-radius,ymin-radius,xmax+radius,ymax+radius),(a,b),radius)


def parse_targets(path):
    return None if path is None else [tuple(row) for row in json.loads(path.read_bytes())]


def load_inherited_geometry(package):
    """Share the inherited archive decoder and native geometry functions."""
    sys.path.insert(0, str(package / "h03-codex-r4-20261123/bridge"))
    sys.path.insert(0, str(package / "h03-v4-dfm-u11-2n2-route"))
    from audit_bridge_decap import by_kind, read_archive
    from plan_local_routes import diagonal_paths, pad_box, segment_box_distance
    from rectify_v4_edge_and_route_pr47 import (
        SENSITIVE_3W_NETS,
        collinear_overlap,
        extract_outline_polygon,
        seg_seg_dist,
    )

    globals().update({
        "by_kind": by_kind, "read_archive": read_archive, "diagonal_paths": diagonal_paths,
        "pad_box": pad_box, "segment_box_distance": segment_box_distance,
        "SENSITIVE_3W_NETS": SENSITIVE_3W_NETS, "collinear_overlap": collinear_overlap,
        "extract_outline_polygon": extract_outline_polygon, "seg_seg_dist": seg_seg_dist,
    })


def load_baseline(package):
    r4 = package / "h03-codex-r4-20261123"
    archive, = (r4 / "native").glob("*.epro2")
    dump_path = r4 / "verification/pcb2-restore-copper.json"
    drc_path = r4 / "verification/pcb2-after.json"
    dump = json.loads(dump_path.read_bytes())
    drc = json.loads(drc_path.read_bytes())
    assert dump["capture"]["documentUuid"] == PCB2 and dump["capture"]["identityVerified"]
    assert not dump.get("partial") and not (drc.get("passed") or "Connection Error" not in drc["counts"])
    copper = dump["copper"]
    assert set(copper["availability"].values()) == {"available"} and copper["arcsAvailable"]
    assert not any(copper[k] for k in ("arcs","pours","poured","regions","fills"))
    docs = read_archive(archive)
    pcb = docs["PCB",PCB2]
    assert by_kind(pcb,"POLY") and not any(by_kind(pcb,k) for k in ("ARC","FILL","REGION","POUR"))
    outline = extract_outline_polygon(dump)
    edges = list(zip(outline,outline[1:]+outline[:1]))
    shapes = []
    pads = {}
    for part in dump["components"]:
        for pad in part["pads"]:
            tag = f"{part['designator']}.{pad['padNumber']}"
            rectangle = pad_box(part,pad)
            layers = VIA_LAYERS[""] if pad.get("hole") and pad.get("metallization") else frozenset((pad["layer"],))
            shape = Shape("pad",pad["primitiveId"],pad["net"],layers,rectangle)
            shapes.append(shape)
            # Duplicate physical pads for one logical terminal still participate in clearance.
            if tag in pads:
                pads[tag] = None
            else:
                pads[tag] = (pad["x"],pad["y"]), pad["layer"], shape
    archive_lines = by_kind(pcb,"LINE")
    for line in copper["lines"]:
        l = archive_lines[line["primitiveId"]]
        assert max(abs(line[a]-l[b]) for a,b in zip(("startX","startY","endX","endY","lineWidth"),
                                                   ("startX","startY","endX","endY","width"))) < 0.001
        assert (line["net"],line["layer"]) == (l["netName"],l["layerId"])
    for ref,l in archive_lines.items():
        shapes.append(capsule("track",ref,l["netName"],frozenset((l["layerId"],)),
                              (l["startX"],l["startY"]),(l["endX"],l["endY"]),l["width"]))
    archive_vias = by_kind(pcb,"VIA")
    assert set(archive_vias) == {v["primitiveId"] for v in copper["vias"]}
    for live in copper["vias"]:
        ref = live["primitiveId"]
        v = archive_vias[ref]
        point = (v["centerX"],v["centerY"])
        assert math.dist(point,(live["x"],live["y"])) < .001
        assert (live["net"],live["diameter"],live["holeDiameter"]) == (
                v["netName"],v["viaDiameter"],v["holeDiameter"])
        assert (v["viaType"],v["ruleName"]) in {("NORMAL",""),("BLIND","BV_L1_L2"),("BLIND","BV_L5_L6")}
        shapes.append(capsule("via",ref,v["netName"],VIA_LAYERS[v["ruleName"]],point,point,v["viaDiameter"]))
    airwires = {item for row in drc["violations"] if row["rule"]=="Connection Error" for item in row["objs"]}
    return archive, dump_path, drc_path, shapes, pads, edges, airwires


def solve(paths, targets=None, width=WIDTH):
    archive, dump_path, drc_path, shapes, pads, edges, airwires = load_baseline(paths)
    parents = {c.ref:c.ref for c in shapes}
    buckets = defaultdict(list)
    by_net = defaultdict(list)
    def find(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    for c in shapes:
        if c.net:
            by_net[c.net].append(c)
        for layer in c.layers:
            buckets[layer].append(c)
    for cluster in by_net.values():
        for a,b in combinations(cluster,2):
            if a.layers & b.layers and close(a,b,.2) and pair_gap(a,b) <= .2:
                parents[find(a.ref)] = find(b.ref)

    candidates = []
    for qa,qb in combinations(sorted(k for k,v in pads.items() if v),2):
        a,layer,p = pads[qa]
        b,other_layer,q = pads[qb]
        if targets is not None and (qa,qb) not in targets and (qb,qa) not in targets:
            continue
        if (p.net!=q.net or layer!=other_layer or layer not in (1,2)
                or not p.net or not ({p.ref,q.ref} & airwires)):
            continue
        same = find(p.ref)==find(q.ref)
        if same or math.dist(a,b)>105:
            continue
        cap_count = sum(k.split(".")[0] in CAPS for k in (qa,qb))
        control = p.net.startswith("AVDD_") or p.net=="OPT_AVDD_EN"
        if not (cap_count or p.net in PRIORITY or control):
            continue
        candidates.append((-bool(cap_count),p.net not in PRIORITY, p.ref in airwires and q.ref in airwires,
                            math.dist(a,b),qa,qb))
    accepted = []
    for _,_,_,_,qa,qb in sorted(candidates):
        a,layer,p = pads[qa]
        b,_,q = pads[qb]
        if find(p.ref)==find(q.ref):
            continue
        paths = set()
        for points in diagonal_paths(a,b):
            cleaned = tuple(dict.fromkeys(tuple(round(c,4) for c in point) for point in points))
            paths.add(cleaned)
        # Simple monotonic 45-degree jogs with one orthogonal segment before and/or after.
        dx,dy = b[0]-a[0],b[1]-a[1]
        for fraction in (0,.25,.5,.75,1):
            diag = min(abs(dx),abs(dy))
            ix,iy = math.copysign(diag,dx), math.copysign(diag,dy)
            for sx,sy in ((a[0]+(dx-ix)*fraction,a[1]),(a[0],a[1]+(dy-iy)*fraction)):
                paths.add(tuple(dict.fromkeys(tuple(round(c,4) for c in coord)
                                              for coord in (a,(sx,sy),(sx+ix,sy+iy),b))))
        good = []
        for path in sorted(paths,key=lambda path:(sum(math.dist(x,y) for x,y in zip(path,path[1:])),path)):
            leg = list(zip(path,path[1:]))
            length = sum(math.dist(x,y) for x,y in leg)
            if not leg or length > math.dist(a,b)+35:
                continue
            bounds = []
            for x,y in leg:
                dx,dy = abs(x[0]-y[0]),abs(x[1]-y[1])
                edge = min(seg_seg_dist(*x,*y,*e,*f) for e,f in edges)-width/2
                if min(dx,dy,abs(dx-dy)) > .0002 or edge < EDGE:
                    break
                candidate = capsule("track","",p.net,frozenset((layer,)),x,y,width)
                flag = False
                nearest = {k:(9999,None) for k in ("pad","track","via")}
                for o in buckets[layer]:
                    if o.ref in (p.ref,q.ref) or not close(candidate,o,30):
                        continue
                    gap=pair_gap(candidate,o)
                    if o.net==p.net:
                        if (o.segment and o.kind=="track" and
                                collinear_overlap(*x,*y,*o.segment[0],*o.segment[1])):
                            flag=True
                            break
                        # Prevent incidental joins outside the two targeted physical copper islands.
                        if gap <= .25 and (not o.ref or find(o.ref) not in (find(p.ref),find(q.ref))):
                            flag=True
                            break
                        continue
                    nearest[o.kind]= min(nearest[o.kind],(gap,o.ref),key=lambda r:r[0])
                    clearance = FOREIGN_COPPER
                    if o.kind=="track":
                        clearance = max(clearance,3.08*max(width,o.radius*2)-width/2-o.radius,
                                        11.8 if {p.net,o.net} & (SENSITIVE | SENSITIVE_3W_NETS) else 0)
                    if gap < clearance:
                        flag=True
                        break
                if flag:
                    break
                bounds.append((edge,nearest))
            else:
                good = (path,length,bounds)
                break
        if not good:
            continue
        path,length,bounds = good
        num=len(accepted)
        clearance = {kind:min((ranges[kind] for _,ranges in bounds),key=lambda row:row[0])
                     for kind in ("track","via","pad")}
        clearance["edge"] = (min(edge for edge,_ in bounds),None)
        accepted.append({"net":p.net,"from":qa,"to":qb,"layer":layer,"width_mil":width,
                         "endpoint_ids":[p.ref,q.ref],"endpoint_drc_open":[r in airwires for r in (p.ref,q.ref)],
                         "length_mil":round(length,4),"points":path,"limiting_copper":[
                             {"kind":k,"gap_mil":round(item[0],4),"id":item[1]}
                             for k,item in clearance.items() if item[0]<9999]})
        for idx,(x,y) in enumerate(zip(path,path[1:])):
            ref=f"new-{num}-{idx}"
            parents[ref]=find(p.ref)
            buckets[layer].append(capsule("track",ref,p.net,frozenset((layer,)),x,y,width))
        parents[find(q.ref)] = find(p.ref)
    return {"board_uuid":PCB2,"route_scope":"offline conservative copper, no native verification",
            "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
            "dump_sha256":hashlib.sha256(dump_path.read_bytes()).hexdigest(),
            "drc_sha256":hashlib.sha256(drc_path.read_bytes()).hexdigest(),
            "geometry_inputs":dict(Counter(c.kind for c in shapes)), "routes":accepted}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--targets",type=Path)
    parser.add_argument("--width",type=float, default=WIDTH)
    args=parser.parse_args()
    load_inherited_geometry(args.package)
    report=solve(args.package,parse_targets(args.targets),width=args.width)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["routes"],indent=2))
