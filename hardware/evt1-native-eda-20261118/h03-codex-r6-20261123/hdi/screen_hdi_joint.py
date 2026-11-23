"""Screen second-layer copper and direct through-via fallback on real R5 PCB3."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.strtree import STRtree

LAYERS = (1, 15, 16, 17, 18, 2)
GUARD = 6.05
BOARD_EDGE_TRACE = 11.85
PLANE_CLEARANCE = 10.15
AXIS = 204.7244
V = 0.0254
R = Path(sys.argv[1])
ROOT = R.parent
sys.path.insert(0, str(ROOT / "h03-codex-r4-20261123/u11"))
from audit_r3_u11 import load, records

FILE, = list((R / "native").glob("*.epro2"))
RAW = records(load(FILE).documents["PCB", "1db01a36f669a47a"])
DATA = json.loads((R / "verification/PCB3-restore-copper.json").read_text())
assert DATA["capture"]["identityVerified"]
assert DATA["outline"]["points"] == [[0, 0], [0, 1338.5827], [204.7244, 1338.5827], [204.7244, 0]]
with (ROOT / "h03-codex-r4-20261123/u11/r3-u11-95ball-native.csv").open(encoding="utf-8-sig") as inf:
    BALLS = {r["ball"]: r for r in csv.DictReader(inf)}
OBSTACLES = {i: [] for i in LAYERS}
DRILLS = []
PADS = {}
TREES = {}


def circle(x, y, radius):
    # Conservative 128-edge circumscription.
    return Point(x, y).buffer(radius / math.cos(math.pi / 128), quad_segs=32)


def paths_coords(path):
    return list(zip(*[iter(v for v in path if v != "L")]*2, strict=True))


def shape(pad, ref):
    x, y = pad["x"], pad["y"]
    dims = pad["shape"]
    if ref.startswith("U11."):
        a = BALLS[ref[4:]]
        assert a["native_pcb_net"] == pad["net"]
        x, y = float(a["center_x_mil"]), float(a["center_y_mil"])
        return (x,y), circle(x,y,float(a["land_diameter_mil"])/2)
    if dims[0] == "POLYGON":
        return (x,y), Polygon(paths_coords(dims[1])).buffer(0.12)
    w, h = (d/2 + .12 for d in dims[1:3])
    if dims[0] == "ELLIPSE":
        return (x,y), circle(x,y,max(w,h))
    if dims[0] == "RECT":
        assert pad["rotation"] % 90 == 0
        if pad["rotation"] % 180:
            w,h = h,w
        return (x,y),box(x-w,y-h,x+w,y+h)
    raise ValueError(f"Unsupported native shape {dims}")


def add(layer, geometry, name, net):
    OBSTACLES[layer].append((geometry, name, net))


def rebuild():
    for layer, shapes in OBSTACLES.items():
        TREES[layer] = STRtree([g for g, _, _ in shapes])


for comp in DATA["components"]:
    for pad in comp["pads"]:
        ref = comp["designator"] + "." + pad["padNumber"]
        center, g = shape(pad, ref)
        net = pad["net"]
        assert not pad["specialPadPresent"]
        for layer in (LAYERS if pad.get("hole") else (pad["layer"],)):
            if layer in LAYERS:
                add(layer, g, ref, net)
        PADS[ref] = (center, g, net)
        if pad.get("hole"):
            DRILLS.append((center, max(pad["hole"][1:3])/2, LAYERS, ref, net))

SPANS = {}
for row in RAW["RULE",'["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]:
    a,b = sorted((LAYERS.index(row["staLayerId"]),LAYERS.index(row["endLayerId"])))
    SPANS[row["name"]] = LAYERS[a:b+1]

PLANE = {}
for (kind, uid), row in RAW.items():
    if kind == "LINE":
        a,b = [(row[f"{part}X"],row[f"{part}Y"]) for part in ("start","end")]
        add(row["layerId"], LineString((a,b)).buffer(row["width"]/2), uid, row["netName"])
    elif kind == "VIA":
        center = row["centerX"],row["centerY"]
        span = LAYERS if row["viaType"] == "NORMAL" else SPANS[row["ruleName"]]
        DRILLS.append((center,row["holeDiameter"]/2,span,uid,row["netName"]))
        for layer in span:
            add(layer,circle(*center,row["viaDiameter"]/2),uid,row["netName"])
    elif kind == "LAYER_FILL":
        parts = []
        for fill in row["fill"]:
            if fill["netName"] != "GND":
                raise ValueError("Unexpected inner plane net")
            shell, *cutouts = (paths_coords(p) for p in fill["path"])
            parts.append(shapely.make_valid(Polygon(shell, cutouts)))
        PLANE[int(json.loads(uid)[1])] = shapely.union_all(parts)

rebuild()


def min_dists(g, layer, net, cutoff=32):
    d = []
    for i in TREES[layer].query(g.buffer(cutoff), predicate='intersects'):
        other, sid, per_net = OBSTACLES[layer][i]
        if per_net == net:
            continue
        conservative = 12 if ("BLE_RF" in per_net or "BLE_ANT" in per_net or "DECR" in per_net) else GUARD
        d.append((g.distance(other), sid, conservative))
    return min(d, key=lambda x:x[0]-x[2], default=(100,'',GUARD))


def check_hole(pos,r,layers,net):
    return min(((math.dist(pos,c)-r-h, uid, (0.13 if n == net else 0.24)/V)
               for c, h, spans, uid, n in DRILLS if set(spans) & set(layers)),
               key=lambda x:x[0]-x[2], default=(100,'',0))


def check_via(pos,r,h,layers,net):
    x,y = pos
    edge = min(x,AXIS-x,y,1338.5827-y)
    if edge - r < .35/V or y < 180:
        return False
    cut = circle(x,y,r)
    for layer in layers:
        gap,_,rule = min_dists(cut,layer,net)
        if gap < rule:
            return False
    gap,_,rule = check_hole(pos,h,layers,net)
    return gap >= rule


def variants(a,b):
    x,y=a; tx,ty=b
    ox=math.copysign(1,tx-x); oy=math.copysign(1,ty-y)
    s=min(abs(tx-x),abs(ty-y))
    return ( (a,b), (a,(x+ox*s,y+oy*s),b), (a,(tx-ox*s,ty-oy*s),b), (a,(x,ty),b), (a,(tx,y),b) )


def route(a,b, layer, net, width):
    for raw in variants(a,b):
        path=tuple(dict.fromkeys(raw))
        if len(path)<2:
            continue
        g=LineString(path).buffer(width/2)
        if g.bounds[0]<BOARD_EDGE_TRACE or g.bounds[2]>AXIS-BOARD_EDGE_TRACE or g.bounds[1]<169:
            continue
        gap,sid,req=min_dists(g,layer,net)
        if gap>=req:
            return {"path": path, "width_mil":width, "length_mil":LineString(path).length,
                    "foreign_gap_mil":gap, "foreign_id":sid,"foreign_guard_mil":req}


def plane_antipad(layer,pos,land_radius):
    plane = PLANE[layer]
    r = land_radius+PLANE_CLEARANCE
    c = circle(*pos,r)
    x,y = pos
    lo,_,hi,_ = plane.bounds
    # Remove external ligaments narrower than 6 mil. This cutout is not a
    # thermal or an anti-pad-to-via change. Route the remaining plane edge
    # around the whole via exclusion to avoid a fabrication sliver.
    if 0 <= hi-x-r < 6 or x+r > hi:
        c = shapely.union_all([c,box(x,y-r,hi+2,y+r)])
    elif 0 <= x-lo-r < 6 or x-r < lo:
        c = shapely.union_all([c,box(lo-2,y-r,x,y+r)])
    return c


def plane_return(cuts):
    report = {}
    for layer,p in PLANE.items():
        original_islands = shapely.get_num_geometries(p)
        cut_geom = shapely.union_all([plane_antipad(layer,pos,r) for pos,r,spans in cuts if layer in spans])
        remaining = p.difference(cut_geom)
        minimum = math.inf
        overlap = []
        for g,uid,net in OBSTACLES[layer]:
            if net != "GND":continue
            gap = cut_geom.distance(g)
            minimum = min(minimum, gap)
            if cut_geom.intersects(g):overlap.append(uid)
        report[layer] = { "new_void_area_mil2":p.area-remaining.area,
                         "edge_opening":cut_geom.intersects(p.boundary),
                         "components_before":int(original_islands),
                         "components_after":int(shapely.get_num_geometries(remaining)),
                         "closest_ground_copper_to_cutout_mil":minimum,"ground_contact_overlap":overlap}
    return report


def cells(x0,x1,y0,y1,step):
    for ix in range(round(x0/step),round(x1/step)+1):
        for iy in range(round(y0/step),round(y1/step)+1):
            yield (round(ix*step,5),round(iy*step,5))


def through(source,dest,sweep,alt_source=None):
    a,_,net=PADS[source]
    if alt_source:a=alt_source
    b,_,n=PADS[dest]
    assert n==net
    candidates=[]
    for center in sweep:
        if not check_via(center,6,3,LAYERS,net):continue
        result1=route(a,center,1,net,4)
        if not result1:continue
        result2=route(center,b,2,net,4)
        if not result2:continue
        candidates.append((result1["length_mil"]+result2["length_mil"],center,result1,result2))
    options=[]
    for length,c,u,v in sorted(candidates)[:6]:
        anti=plane_return([(c,6,LAYERS)])
        options.append({"via_center_mil":c,"via_drill_mil":6,"via_land_mil":12,"top":u,"bottom":v,"net":net,
                        "via_min_foreign":{layer:min_dists(circle(*c,6),layer,net) for layer in LAYERS},
                        "hole_wall":check_hole(c,3,LAYERS,net),"anti_pad":anti,"length_mil":length})
    return {"source":source,"destination":dest,"candidate_count":len(candidates),"best":options}


def two_stage(source, dest, search_entry, search_exit, drill_um):
    source_pad, _, net = PADS[source]
    target_pad, _, n = PADS[dest]
    assert net == n
    drill_r = drill_um/2000/V
    land_r = drill_r + 3
    ms = (1, 15, 16)
    entries = []
    for center in cells(*search_entry):
        if not check_via(center, land_r, drill_r, ms, net):
            continue
        a = route(source_pad, center, 1, net, 4)
        if not a:
            continue
        # Preserve soldermask and solderable paste opening. The laser bore must
        # stay entirely outside all existing U11 mask openings with 0.5 mil reserve.
        if any(math.dist(center, c) < drill_r + 2.5 + float(BALLS[ref[4:]]['land_diameter_mil'])/2
               for ref,(c,_,nn) in PADS.items() if ref.startswith('U11.')):
            continue
        entries.append((center,a))
    exits = []
    for center in cells(*search_exit):
        if not check_via(center, 6, 3, LAYERS, net):
            continue
        b = route(center,target_pad,2,net,4)
        if b:
            exits.append((center,b))
    nominations = []
    for c,a in entries:
        for d,b in sorted(exits, key=lambda item: math.dist(item[0],c)+item[1]['length_mil'])[:30]:
            if math.dist(c,d) - (drill_r+3) < 0.13 / V:
                continue
            inner = route(c,d,16,net,4)
            if inner:
                nominations.append((a['length_mil']+b['length_mil']+inner['length_mil'], c,d,a,b,inner))
    output = []
    for total,c,d,a,b,inner in sorted(nominations,key=lambda it: it[:3])[:40]:
        clearance = plane_return([(c,land_r,ms),(d,6,LAYERS)])
        if any(p['ground_contact_overlap'] or p['components_before'] != p['components_after']
               for p in clearance.values()):
            continue
        output.append({"net":net,"entry_microvia":{"center":c,"drill_um":drill_um,"land_mil":2*land_r,
                        "native_new_spans_required": [[1,15],[15,16]]},
                       "exit_through":{"center":d,"drill_mil":6,"land_mil":12},
                       "L1":a,"L3":inner,"L6":b,"antipads":clearance,"length_mil":total,
                       "min_hole_to_baseline":{"entry":check_hole(c,drill_r,ms,net),"exit":check_hole(d,3,LAYERS,net)},
                       "min_capture_copper_to_baseline":{
                           "entry":{l:min_dists(circle(*c,land_r),l,net) for l in ms},
                           "exit":{l:min_dists(circle(*d,6),l,net) for l in LAYERS}}})
        if len(output)>=8:break
    return {"source":source,"destination":dest,"entry_positions":len(entries),"exit_positions":len(exits),
            "inner_route_pairs_nominal":len(nominations),"best":output}


def main():
    trials={}
    for source, dest, search, alt in (
        ("U11.A3","U1.5",(20,34,292,323,0.5),None),
        ("U11.A3","U1.1",(20,35,300,321,0.5),None),
        ("U11.K4","U10.C3",(167,184,320,350,0.5),None),
        ("U11.K4","J1.P12",(167,186,310,347,0.5),None),
    ):
        key=source+"->"+dest
        trials[key]=through(source,dest,cells(*search),alt)
        print(key,trials[key]["candidate_count"],flush=True)
    stacks={}
    for source,dest,search_entry,search_exit in (
        ("U11.D2","U1.5",(62,86,292,322,0.5),(20,54,311,343,0.5)),
        ("U11.D2","U1.1",(62,86,292,322,0.5),(21,64,276,306,0.5)),
        ("U11.K4","U10.C3",(165,184,319,349,0.5),(134,184,341,388,0.5)),
        ("U11.K4","J1.P12",(165,184,319,349,0.5),(28,100,225,279,0.5)),
    ):
        key=source+"->"+dest
        for hole in (75,100):
            k=key+" "+str(hole)
            stacks[k]=two_stage(source,dest,search_entry,search_exit,hole)
            print(k,*(v for x,v in stacks[k].items() if x.endswith("positions") or x.endswith("nominal")),
                  len(stacks[k]["best"]),flush=True)
    Path(sys.argv[2]).write_text(json.dumps({"archive_sha256":hashlib.sha256(FILE.read_bytes()).hexdigest(),
                    "scope":"Nominal R5 copper; no drilling fabrication approval or native writes.",
                    "through_via_fallback":trials,"stacked_option":stacks},indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
