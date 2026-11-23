"""Create an isolated native K4→J1.P12 logical HDI trial from a clearance-screened plan."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

from shapely.geometry import Point, Polygon, box

PACKAGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE / "h03-codex-r4-20261123/u11"))
from audit_r3_u11 import load, records

BOARD = ("PCB", "1db01a36f669a47a")
NET = "I2S_LRCLK_1V8"
STAGES = {"BV_L2_L3": (15,16), "BV_L3_L4_BURIED": (16,17), "BV_L4_L5": (17,18)}
CLEARANCE_MIL = 10.15
RULE = ("RULE",'["RULE","BLIND","blindVia"]')
BASELINE = "84b99c1c60fd03aca74e19f025c3a37b421342d79de7c068009543e6b2e9b070"


def encoded(path):
    vertices=list(path)
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(vertices,vertices[1:]))
    if area>0:
        vertices.reverse()
    vertices=[(round(x,8),round(y,8)) for x,y in vertices]
    return [*vertices[0],"L",*(coord for pt in vertices[1:] for coord in pt)]


def decode(ring):
    values=ring[:2]+ring[3:]
    if ring[2]!="L" or values[:2]!=values[-2:]:
        raise ValueError("Unsupported plane path format")
    return list(zip(values[::2],values[1::2],strict=True))


def relief(record, center, outer):
    plane,=record["fill"]
    shell,*holes=map(decode,plane["path"])
    prior=Polygon(shell,holes)
    x,y=center
    required=outer/2+CLEARANCE_MIL
    radius=(required+0.002)/math.cos(math.pi/128)
    circle=Point(x,y).buffer(radius,quad_segs=32)
    right=max(point[0] for point in shell)
    cutout=circle if right-x-radius>=6 else circle.union(box(x,y-radius,right+2,y+radius))
    after=prior.difference(cutout)
    if not prior.is_valid or not after.is_valid or after.geom_type!="Polygon":
        raise ValueError("The proposed antipad splits or invalidates the GND reference")
    if any(Polygon(hole).distance(cutout)<=0 for hole in holes):
        raise ValueError("The proposed relief overlaps a retained internal opening")
    if after.distance(Point(x,y))+1e-6<required:
        raise ValueError("The real cutout copper distance fails the native plane guard")
    trails=[encoded(after.exterior.coords),*plane["path"][1:]]
    if not cutout.intersects(prior.boundary):
        trails.append(encoded(circle.exterior.coords))
    return record | {"fill":[plane | {"path":trails}]}, {
        "old_area_mil2":prior.area,"retained_area_mil2":after.area,"plane_to_via_copper_mil":after.distance(Point(x,y))-outer/2,
        "edge_opening":cutout.intersects(prior.boundary),"one_connected_polygon":True}


def make(source, proposal, destination):
    if hashlib.sha256(source.read_bytes()).hexdigest()!=BASELINE:
        raise ValueError("HDI trial requires the exact PR #53 native file")
    old=load(source).documents
    rows=records(old[BOARD])
    candidate=json.loads(proposal.read_bytes())
    top=candidate["main"]["top"]
    bottoms=[item["via"] for item in candidate["destinations"]]
    buried=candidate["main"]["core"]
    hole=round(candidate["laser_um"]/25.4,6)
    outer=hole+6
    board_rule=rows[RULE]
    context=board_rule["ruleContext"]
    blinds=context["blinds"]
    if any(rule["name"] in STAGES for rule in blinds["content"]):
        raise ValueError("The new via spans must be absent from the controlled baseline")
    additions=[{"name":name,"staLayerId":a,"endLayerId":b,"viaSizeRule":""}
               for name,(a,b) in STAGES.items()]
    updates={RULE:board_rule | {"ruleContext":context | {"blinds":blinds | {"content":[*blinds["content"],*additions]}}}}
    measurements={}
    for layer,center in ((15,top), *((18,point) for point in bottoms)):
        key=("LAYER_FILL",f'["LAYER_FILL",{layer}]')
        updates[key],measurement=relief(updates.get(key,rows[key]),center,outer)
        measurements.setdefault(str(layer),[]).append(measurement)

    donor=rows["VIA","9b1de4f8a526c7d3"]
    trial=((top,"BV_L1_L2",hole,outer),(top,"BV_L2_L3",hole,outer),
           (buried,"BV_L3_L4_BURIED",6,12),*((bottom,span,hole,outer)
           for bottom in bottoms for span in ("BV_L4_L5","BV_L5_L6")))
    if ("BLIND", "GND")!=(donor["viaType"],donor["netName"]):
        raise ValueError("Baseline blind-via primitive schema differs")
    created={}
    for index, ((x,y), rule, drill, copper) in enumerate(trial):
        identifier=hashlib.sha256(f"H03-R6-K4-hdi/{index}/{rule}/{x}/{y}".encode()).hexdigest()[:16]
        created["VIA",identifier]=donor | {"centerX":x,"centerY":y,"ruleName":rule,
                                           "netName":NET,"holeDiameter":drill,"viaDiameter":copper}
    if rows.keys() & created.keys():
        raise ValueError("New native identities collide with existing geometry")
    ticket=max(row.header.get("ticket",0) for row in old[BOARD])
    new_lines=[]
    for (kind,identifier),payload in created.items():
        ticket+=1
        header={"type":kind,"id":identifier,"ticket":ticket}
        new_lines.append(("||".join(json.dumps(item,separators=(",",":")) for item in (header,payload))+"|\n").encode())
    with ZipFile(source) as archive:
        member,=[n for n in archive.namelist() if n.endswith(".epru")]
        output=[]
        active=False
        changed=set()
        for line in archive.read(member).splitlines(keepends=True):
            header,raw=line.split(b"||",1)
            h=json.loads(header)
            if h["type"]=="DOCHEAD":
                if active:
                    output.extend(new_lines)
                data=json.loads(raw.rstrip(b"\r\n").removesuffix(b"|"))
                active=(data["docType"],data["uuid"])==BOARD
            key=h["type"],h.get("id")
            if active and key in updates:
                line=header+b"||"+json.dumps(updates[key],separators=(",",":")).encode()+b"|\n"
                changed.add(key)
            output.append(line)
        if active:
            if not output[-1].endswith(b"\n"):
                output[-1]+=b"\n"
            output.extend(new_lines)
        if changed!=updates.keys():
            raise ValueError("Native PCB3 trial could not prove the exact plane and rule changes")
        with ZipFile(destination,"x") as target:
            for item in archive.infolist():
                target.writestr(item,b"".join(output) if item.filename==member else archive.read(item))

    actual=load(destination).documents
    if actual.keys()!=old.keys() or any(records(actual[key])!=records(old[key]) | (updates|created if key==BOARD else {})
                                       for key in old):
        raise ValueError("Unplanned native HDI trial delta")
    routes=[candidate["main"]["ltop"] | {"layer":1,"net":NET},
            candidate["main"]["l3"] | {"layer":16,"net":NET}]
    for item in candidate["destinations"]:
        routes.extend((item["l4_route"] | {"layer":17,"net":NET},
                       item["bottom_route"] | {"layer":2,"net":NET}))
    return {"scope":"Isolated logical via span and copper trial. Physical LAYER_PHYS retained; no qualified 0.80 mm manufacturing claim.",
            "sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
            "slots":[payload | {"id":key[1]} for key,payload in created.items()],
            "added_via_spans":additions,"plane_measurement":measurements,"routes":routes}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("source","proposal","destination"):
        parser.add_argument(key,type=Path)
    args=parser.parse_args()
    print(json.dumps(make(args.source,args.proposal,args.destination),indent=2))
