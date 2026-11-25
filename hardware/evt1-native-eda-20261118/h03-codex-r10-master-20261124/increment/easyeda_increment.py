"""Guarded native EasyEDA increment intake for additive, routed PCB copper."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
from zipfile import ZipFile

PCB_IDS = {"PCB1": "8fbc3cae65886fe5", "PCB2": "9ce45f14cb79dc9d", "PCB3": "1db01a36f669a47a"}
REF = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_+\-]+$")
UID = re.compile(r"^[a-f0-9]{12,64}$")

def read(path):
    return json.loads(path.read_bytes())

def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def archive(path):
    documents = {}
    current = None
    with ZipFile(path) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Native archive ZIP CRC failed")
        member, = [name for name in bundle.namelist() if name.endswith(".epru")]
        for row in bundle.read(member).splitlines():
            header, body = row.split(b"||", 1)
            head = json.loads(header)
            payload = None if body == b"|" else json.loads(body.removesuffix(b"|"))
            if head["type"] == "DOCHEAD":
                current = (payload["docType"], payload["uuid"])
                if current in documents:
                    raise ValueError(f"Duplicate native document {current}")
                documents[current] = {}
            elif head["type"] != "PRIMITIVE" or payload is not None:
                documents[current][head["type"], head.get("id")] = payload
    return documents

def call(output, name, *args, verdict=False, partial_reload=False, unknown_path=False):
    cmd = ["easyeda", *args]
    stdout = output / f"{name}.json"
    stderr = output / f"{name}.stderr.txt"
    with stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.run(cmd, stdout=out, stderr=err, timeout=145)
    with (output / "commands.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps({"name": name, "command": cmd, "exitCode": process.returncode}, ensure_ascii=False)+"\n")
    data=read(stdout) if stdout.stat().st_size else {}
    if process.returncode and unknown_path and "unsupported copper geometry" in stderr.read_text(encoding="utf-8",errors="replace"):
        return {}
    if process.returncode and not ((verdict and "nativeResult" in data) or (partial_reload and data.get("status")=="partial")):
        raise RuntimeError(f"{name} exited {process.returncode}, see {stderr.name}")
    return data

def window():
    result = subprocess.run(["easyeda","health"],check=True,capture_output=True,timeout=35)
    windows = json.loads(result.stdout)["found"]["raw"]["windows"]
    if len(windows) != 1:
        raise RuntimeError("This intake requires exactly one connected EasyEDA window")
    return windows[0]["windowId"]

def open_project(output, project, document):
    call(output,"open","--window",window(),"project","open","--project-uuid",project,"--allow-discard-unsaved")
    for _ in range(8):
        listing=subprocess.run(["easyeda","--project",project,"doc","ls"],capture_output=True,timeout=25)
        if listing.returncode==0 and document.encode() in listing.stdout:
            (output/"docs.txt").write_bytes(listing.stdout)
            return
        time.sleep(2)
    raise RuntimeError("Project document tree did not become ready")

def import_snapshot(output, checkpoint, name, document):
    receipt=call(output,"import","--window",window(),"project","import","--file",str(checkpoint),"--name",name)["result"]
    if receipt.get("created") is not True or receipt.get("sourceSha256") != digest(checkpoint):
        raise RuntimeError("Native import receipt did not bind to the intended archive")
    project=receipt["uuid"]
    open_project(output,project,document)
    return project

def export(output,label,project,destination):
    receipt=call(output,label,"--window",window(),"project","export","--project-uuid",project,"--out",str(destination))
    if receipt["result"]["sha256"] != digest(destination):
        raise RuntimeError("Native export changed after readback")
    return archive(destination)

def signatures(report):
    return Counter((item["rule"],item["objType"],item.get("net"),
                    tuple(sorted(item.get("objs") or ())) if item["rule"]!="Netlist Error" else ())
                   for item in report["violations"])

def drc(output, label, scope):
    return call(output,label,*scope,"pcb","drc","--strict","--json","--timeout","105",verdict=True)

def load_plan(path, checkpoint):
    plan=read(path)
    if plan.get("schemaVersion")!=1 or not re.fullmatch(r"[A-Za-z0-9-]{3,75}",plan.get("id","")):
        raise ValueError("Invalid increment schema or ID")
    if plan.get("checkpointSha256")!=digest(checkpoint):
        raise ValueError("Stale or unapproved checkpoint SHA-256")
    if plan.get("board") not in PCB_IDS or not plan.get("routes"):
        raise ValueError("Increment must name exactly one board and at least one route")
    for route in plan["routes"]:
        if (not route.get("net") or route.get("layer") not in (1,2)
                or not 4<=route.get("width",0)<=40
                or any(not (REF.fullmatch(route[key]) or UID.fullmatch(route[key])) for key in ("from","to"))):
            raise ValueError(f"Unrecognized route intent: {route}")
        points=route["points"]
        if len(points)<2 or any(len(p)!=2 or not all(math.isfinite(x) for x in p) for p in points):
            raise ValueError("Invalid route vertices")
        for a,b in zip(points,points[1:]):
            dx,dy=abs(a[0]-b[0]),abs(a[1]-b[1])
            if math.dist(a,b)<.035 or min(dx,dy,abs(dx-dy))>.002:
                raise ValueError(f"Coincident or off-angle route leg: {a}, {b}")
    return plan

def contains_pad_center(pad, point):
    if pad.get("specialPadPresent"):
        return False
    shape=pad["shape"]
    x,y=point
    if shape[0]=="POLYGON":
        coordinates=shape[1]
        if any(isinstance(v,str) and v!="L" for v in coordinates):
            return False
        numbers=[v for v in coordinates if isinstance(v,(int,float))]
        polygon=list(zip(numbers[::2],numbers[1::2],strict=True))
        return bool(sum((a[1]>y)!=(b[1]>y) and x<a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1])
                        for a,b in zip(polygon,polygon[1:]+polygon[:1]))%2)
    if shape[0] not in ("RECT","ELLIPSE","OVAL"):
        return False
    # Only use the inscribed central disk, safely inside the supported pad shapes.
    radius=min(shape[1:3])/2
    return math.dist(point,(pad["x"],pad["y"])) < radius

def endpoint(dump, records, ref, net, layer, at):
    if REF.fullmatch(ref):
        part, pad = ref.rsplit(".",1)
        rows=[p for c in dump["components"] if c["designator"]==part
              for p in c["pads"] if str(p["padNumber"])==pad and p["layer"]==layer and p["net"]==net]
        if len(rows)!=1 or math.dist(at,(rows[0]["x"],rows[0]["y"]))>.18:
            raise ValueError(f"Endpoint no longer matches native pad center: {ref}")
        if not contains_pad_center(rows[0],at):
            raise ValueError(f"Endpoint is outside exact pad copper: {ref}")
        return rows[0]["primitiveId"]
    via=records.get(("VIA",ref))
    line=records.get(("LINE",ref))
    if via and via["netName"]==net and math.dist(at,(via["centerX"],via["centerY"]))<=.015:
        if via["viaType"]=="NORMAL":
            return ref
        spans=records["RULE",'["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
        if any(rule["name"]==via["ruleName"] and layer in (rule["staLayerId"],rule["endLayerId"]) for rule in spans):
            return ref
    if line and line["netName"]==net and line["layerId"]==layer:
        ends=((line["startX"],line["startY"]),(line["endX"],line["endY"]))
        if any(math.dist(at,end)<=.015 for end in ends):
            return ref
    raise ValueError(f"Original via/track anchor is absent, on a different layer, or does not meet the planned junction: {ref}")

def geometry(row):
    return (row["netName"],row["layerId"],row["width"],*sorted(
        ((round(row["startX"],4),round(row["startY"],4)),(round(row["endX"],4),round(row["endY"],4)))))

def segment_covered(segment, candidates, tolerance=.003):
    a,b=segment
    length=math.dist(a,b)
    if length<=tolerance:
        return any(math.dist(a,c)<=tolerance or math.dist(a,d)<=tolerance for c,d in candidates)
    ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    intervals=[]
    for c,d in candidates:
        if any(abs((q[0]-a[0])*uy-(q[1]-a[1])*ux)>tolerance for q in (c,d)):
            continue
        left,right=sorted((q[0]-a[0])*ux+(q[1]-a[1])*uy for q in (c,d))
        if right>=-tolerance and left<=length+tolerance:
            intervals.append((left,right))
    covered=0.0
    for left,right in sorted(intervals):
        if left>covered+tolerance:
            break
        covered=max(covered,right)
        if covered>=length-tolerance:
            return True
    return False

def compare_additions(before, after, board, plan):
    if before.keys()!=after.keys() or any(before[key]!=after[key] for key in before if key!=board):
        raise ValueError("A non-target native document changed")
    old,new=before[board],after[board]
    expected=defaultdict(list)
    observed=defaultdict(list)
    for key in old.keys()|new.keys():
        left,right=old.get(key),new.get(key)
        if left==right:
            continue
        if key[0]=="ELE_PLACEHOLDER" and all(x.get("dataType")=="LINE" for x in (left,right) if x):
            continue
        if key[0]!="LINE" or any(x.get("locked") for x in (left,right) if x):
            raise ValueError(f"Unplanned native modification or locked copper change: {key}")
        for row,destination in ((left,expected),(right,observed)):
            if row:
                net,layer,width,a,b=geometry(row)
                destination[net,layer,width].append((a,b))
    for route in plan["routes"]:
        key=route["net"],route["layer"],route["width"]
        expected[key].extend((tuple(a),tuple(b)) for a,b in zip(route["points"],route["points"][1:]))
    if observed.keys()!=expected.keys():
        raise ValueError("Unplanned change to line network, layer or width")
    for key, planned in expected.items():
        actual=observed[key]
        if not (all(segment_covered(seg,actual) for seg in planned)
                and all(segment_covered(seg,planned) for seg in actual)):
            raise ValueError(f"Unplanned native centerline change: {key}")

def stage(plan_path, checkpoint, output, target=None, acceptance=None):
    plan=load_plan(plan_path,checkpoint)
    baseline=archive(checkpoint)
    document=PCB_IDS[plan["board"]]
    board=("PCB",document)
    if target:
        previous=read(acceptance) if acceptance else {}
        if (previous.get("status")!="accepted" or previous.get("checkpointSha256")!=digest(checkpoint)
                or previous.get("planSha256")!=digest(plan_path) or previous.get("projectUuid")==target):
            raise ValueError("Master replay requires matching prior acceptance from a separate native copy")
    output.mkdir()
    project=target or import_snapshot(output,checkpoint,f'EVT1-{plan["id"]}-TRIAL-NOT-FOR-FAB',document)
    if target:
        open_project(output,target,document)
    captured=export(output,"checkpoint-capture",project,output/"PRE-BATCH.epro2")
    if captured!=baseline:
        raise ValueError("Live project records no longer match the approved checkpoint")
    scope=("--project",project,"--doc",document)
    snapshot=output/"native-before.json"
    call(output,"capture-before",*scope,"pcb","dump","--include-copper","--no-silk","--out",str(snapshot))
    dump=read(snapshot)
    if (not dump["capture"]["identityVerified"] or dump.get("partial")
            or dump["capture"]["documentUuid"]!=document or dump["capture"]["projectUuid"]!=project):
        raise ValueError("Incomplete source geometry")
    for route in plan["routes"]:
        for ref,point in ((route["from"],route["points"][0]),(route["to"],route["points"][-1])):
            endpoint(dump,baseline[board],ref,route["net"],route["layer"],point)
    initial=drc(output,"strict-before",scope)
    for i,route in enumerate(plan["routes"],1):
        for j,(a,b) in enumerate(zip(route["points"],route["points"][1:]),1):
            result=call(output,f"track-{i:02d}-{j:02d}",*scope,"pcb","track","--net",route["net"],
                        "--width",str(route["width"]),"--layer",str(route["layer"]),"--x1",str(a[0]),"--y1",str(a[1]),
                        "--x2",str(b[0]),"--y2",str(b[1]))
            if result["mutationContext"]["projectUuid"]!=project or result["mutationContext"]["documentUuid"]!=document:
                raise RuntimeError("Wrong mutation identity")
    if call(output,"save",*scope,"pcb","save")["result"].get("saved") is not True:
        raise RuntimeError("Native save lacks saved:true")
    call(output,"reload",*scope,"doc","reload","--json",partial_reload=True)
    finish(plan_path,checkpoint,output,master=bool(target))

def finish(plan_path, checkpoint, output, master=False):
    plan=load_plan(plan_path,checkpoint)
    baseline=archive(checkpoint)
    if archive(output/"PRE-BATCH.epro2")!=baseline:
        raise ValueError("Pre-batch archive disagrees with the approved checkpoint")
    document=PCB_IDS[plan["board"]]
    board=("PCB",document)
    captured=read(output/"native-before.json")["capture"]
    project=captured["projectUuid"]
    scope=("--project",project,"--doc",document)
    initial=read(output/"strict-before.json")
    reload=read(output/"reload.json")
    reopened=any(step.get("stage")=="reopen" and step.get("ok") is True
                 and step.get("context",{}).get("documentUuid")==document
                 and step.get("context",{}).get("projectUuid")==project
                 for step in reload.get("steps",[]))
    if reload.get("status")=="partial":
        if reload.get("saved") is not True or reload.get("closed") is not True or not reopened:
            raise RuntimeError("Partial reload did not prove save/close/reopen; writes stopped")
        ready_file=output/"ready-after-partial.json"
        ready=read(ready_file) if ready_file.exists() else call(output,"ready-after-partial",*scope,"doc","ready","--json")
        if (ready.get("ready") is not True or ready["active"]["projectUuid"]!=project
                or ready["active"]["documentUuid"]!=document):
            raise RuntimeError("PCB did not become ready after reopening")
    elif reload.get("status")!="passed" or reload.get("reloaded")!=document:
        raise RuntimeError("Native reload is unconfirmed; inspect project and recover")
    final_file=output/"strict-after.json"
    final=read(final_file) if final_file.exists() and final_file.stat().st_size else drc(output,"strict-after",scope)
    post=output/"POST-BATCH.epro2"
    if post.exists():
        if read(output/"post-export.json")["result"]["sha256"]!=digest(post):
            raise ValueError("Saved post-export digest mismatch")
        current=archive(post)
    else:
        current=export(output,"post-export",project,post)
    compare_additions(baseline,current,board,plan)
    removed=signatures(initial)-signatures(final)
    introduced=signatures(final)-signatures(initial)
    nets={route["net"] for route in plan["routes"]}
    if (final["counts"].get("Connection Error",0)>=initial["counts"].get("Connection Error",0)
            or any(key[0]!="Connection Error" or key[2] not in nets for key in removed)
            or any(key[0]!="Connection Error" or key[2] not in nets for key in introduced)):
        raise ValueError("Native DRC did not improve proposed nets or changed unrelated diagnostics")
    snapshot=output/"native-after.json"
    if not snapshot.exists():
        call(output,"capture-after",*scope,"pcb","dump","--include-copper","--no-silk","--out",str(snapshot))
    dump=read(snapshot)
    if (not dump["capture"]["identityVerified"] or dump.get("partial")
            or dump["capture"]["documentUuid"]!=document or dump["capture"]["projectUuid"]!=project):
        raise ValueError("Incomplete post-save native geometry")
    paths=[]
    direct=[]
    for i,route in enumerate(plan["routes"],1):
        for ref,point in ((route["from"],route["points"][0]),(route["to"],route["points"][-1])):
            endpoint(dump,current[board],ref,route["net"],route["layer"],point)
        if REF.fullmatch(route["from"]) and REF.fullmatch(route["to"]):
            label=f"path-{i:02d}"
            previous=output/f"{label}.json"
            path=(read(previous) if previous.stat().st_size else {}) if previous.exists() else call(
                output,label,*scope,"pcb","net-path","--from",route["from"],"--to",route["to"],
                "--net",route["net"],"--layer",str(route["layer"]),"--json",unknown_path=True)
            if path.get("connected") is True:
                paths.append(i)
            elif path or "unsupported copper geometry" not in (output/f"{label}.stderr.txt").read_text(encoding="utf8",errors="replace"):
                raise ValueError(f"Native net path did not prove direct route {i}")
            else:
                direct.append(i)
        else:
            direct.append(i)
    write(output/"acceptance.json",{"status":"accepted","id":plan["id"],"projectUuid":project,"mode":"master" if master else "isolated",
        "checkpointSha256":digest(checkpoint),"planSha256":digest(plan_path),"exportSha256":digest(output/"POST-BATCH.epro2"),
        "before":initial["counts"],"after":final["counts"],"nativePadPaths":paths,"directGeometryPaths":direct,
        "removedSignatures":[[key,count] for key,count in removed.items()],
        "introducedSignatures":[[key,count] for key,count in introduced.items()]})

def restore(checkpoint,output,name,board):
    output.mkdir()
    document=PCB_IDS[board]
    project=import_snapshot(output,checkpoint,name,document)
    rebuilt=export(output,"restore-export",project,output/"RESTORED.epro2")
    if rebuilt!=archive(checkpoint):
        raise ValueError("Restored archive does not reproduce original native records")
    result=drc(output,"strict-restored",("--project",project,"--doc",document))
    write(output/"restoration.json",{"status":"restored","projectUuid":project,
          "checkpointSha256":digest(checkpoint),"documentRecordsMatch":len(rebuilt),"nativeDRC":result["counts"]})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    apply=sub.add_parser("apply")
    apply.add_argument("checkpoint",type=Path)
    apply.add_argument("plan",type=Path)
    apply.add_argument("output",type=Path)
    apply.add_argument("--target")
    apply.add_argument("--acceptance",type=Path)
    inspect=sub.add_parser("verify")
    inspect.add_argument("checkpoint",type=Path)
    inspect.add_argument("plan",type=Path)
    inspect.add_argument("output",type=Path)
    inspect.add_argument("--master",action="store_true")
    rollback=sub.add_parser("restore")
    rollback.add_argument("checkpoint",type=Path)
    rollback.add_argument("output",type=Path)
    rollback.add_argument("--name",required=True)
    rollback.add_argument("--board",choices=PCB_IDS,default="PCB1")
    args=parser.parse_args()
    if args.command=="apply":
        stage(args.plan.resolve(),args.checkpoint.resolve(),args.output.resolve(),args.target,args.acceptance)
    elif args.command=="verify":
        finish(args.plan.resolve(),args.checkpoint.resolve(),args.output.resolve(),master=args.master)
    else:
        restore(args.checkpoint.resolve(),args.output.resolve(),args.name,args.board)

if __name__=="__main__":
    main()
