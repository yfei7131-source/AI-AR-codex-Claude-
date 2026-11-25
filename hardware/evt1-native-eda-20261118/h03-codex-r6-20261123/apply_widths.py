"""Apply a verified native width manifest and reconcile any exact tee normalization."""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import subprocess

EPS = 0.0001
DOCS = {"PCB1":"8fbc3cae65886fe5","PCB2":"9ce45f14cb79dc9d","PCB3":"1db01a36f669a47a"}


def points(line):
    return ((line["startX"],line["startY"]), (line["endX"],line["endY"]))


def key(line):
    return line["net"], line["layer"], round(line["lineWidth"], 6)


def covered(line, candidates, tolerance=EPS):
    a,b=points(line)
    length=math.dist(a,b)
    if length <= EPS:
        raise ValueError("Cannot prove coverage for a degenerate modified segment")
    ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    intervals=[]
    for other in candidates:
        p,q=points(other)
        if max(abs((s[0]-a[0])*uy-(s[1]-a[1])*ux) for s in (p,q)) > tolerance:
            continue
        low,high=sorted((s[0]-a[0])*ux+(s[1]-a[1])*uy for s in (p,q))
        if low <= length+tolerance and high >= -tolerance:
            intervals.append((max(0,low),min(length,high)))
    if not intervals:
        return False
    reach=0
    for low,high in sorted(intervals):
        if low > reach+tolerance:
            break
        reach=max(reach,high)
    return reach >= length-tolerance


def compare_routes(expected, actual, tolerance=EPS):
    groups = [defaultdict(list),defaultdict(list)]
    for by_key, route in zip(groups,(expected,actual),strict=True):
        for line in route:
            by_key[key(line)].append(line)
    if groups[0].keys()!=groups[1].keys():
        raise ValueError("Unexpected changed net, layer or track width")
    for identity in groups[0]:
        a,b=(group[identity] for group in groups)
        # Detect duplicate geometric copper separately. A tee split is allowed.
        for selected in (a,b):
            shapes=Counter(tuple(sorted(points(line))) for line in selected)
            if any(count>1 for count in shapes.values()):
                raise ValueError(f"Duplicate geometry near {identity}")
        if not all(covered(line,b,tolerance) for line in a) or not all(covered(line,a,tolerance) for line in b):
            raise ValueError(f"Native copper union differs on {identity}")


def run(project, board, source, report_folder):
    report_folder.mkdir()
    doc=DOCS[board]
    scope=["easyeda","--project",project]
    pinned=scope+["--doc",doc]

    def cli(name,args,args_scope=scope, allow_rule_failure=False):
        result=subprocess.run([*args_scope,*args],capture_output=True,timeout=100)
        (report_folder/f"{name}.json").write_bytes(result.stdout)
        if result.stderr:
            (report_folder/f"{name}.stderr.txt").write_bytes(result.stderr)
        if result.returncode and not allow_rule_failure:
            raise RuntimeError(f"EasyEDA {name} failed with exit {result.returncode}")
        return json.loads(result.stdout)

    def dump(name):
        path=(report_folder/f"{name}.json").resolve()
        result=subprocess.run([*scope,"pcb","dump","--include-copper","--no-silk","--out",str(path)],
                              timeout=100,check=True,capture_output=True)
        (report_folder/f"{name}-console.log").write_bytes(result.stdout+result.stderr)
        data=json.loads(path.read_bytes())
        if (not data["capture"]["identityVerified"] or (data["capture"]["documentUuid"],
                data["capture"]["projectUuid"])!=(doc,project)):
            raise ValueError("Wrong document context in native capture")
        return data

    cli("switch",["doc","switch",doc,"--json"])
    before=dump("before-copper")
    originals={item["primitiveId"]:item for item in before["copper"]["lines"]}
    proposal=json.loads(source.read_bytes())["width_candidates"]
    wanted={}
    for row in proposal:
        line=originals[row["id"]]
        if key(line)!=(row["net"],row["layer"],3) or line["locked"] or row["after_width_mil"]!=4:
            raise ValueError(f"Candidate base state differs on {row['id']}")
        if any(math.dist(a,b)>EPS for a,b in zip(points(line),(row["start"],row["end"]),strict=True)):
            raise ValueError(f"Candidate centerline differs on {row['id']}")
        wanted[row["id"]]=line | {"lineWidth":4}
    if len(wanted)!=len(proposal):
        raise ValueError("Width manifest contains a repeated primitive")
    receipts=[]
    for index,line in enumerate(wanted.values(),1):
        (x1,y1),(x2,y2)=points(line)
        response=cli(f"create-{index:03}",["pcb","track","--net",line["net"],"--layer",str(line["layer"]),
                     "--width","4","--x1",str(x1),"--y1",str(y1),"--x2",str(x2),"--y2",str(y2)],pinned)
        if not response["ok"] or (response["mutationContext"]["projectUuid"],
                 response["mutationContext"]["documentUuid"])!=(project,doc):
            raise ValueError("Native create did not confirm the requested target")
        receipts.append(response["result"]["primitiveId"])
        if index%20==0:
            print(board,index,"of",len(wanted),"created",flush=True)
    post_create=dump("after-create-copper")
    old_present = wanted.keys() & {t["primitiveId"] for t in post_create["copper"]["lines"]}
    if old_present:
        remaining=sorted(old_present)
        response=cli("remove-old",["pcb","track-delete","--ids",",".join(remaining)],pinned)
        if {entry["primitiveId"] for entry in response["result"]["removed"]} != set(remaining):
            raise ValueError("Explicit native replacement cleanup differed from the requested IDs")
    if cli("save",["pcb","save"],pinned)["result"]["saved"] is not True:
        raise ValueError("Positive native save receipt required")
    reload=cli("reload",["doc","reload",doc,"--json"])
    if not reload["closed"] or reload["reloaded"]!=doc or reload["saved"] is not True:
        raise ValueError("Native reload did not complete after save")
    after=dump("after-copper")
    for name in ("components","rules","outline","copperLayers"):
        if before[name]!=after[name]:
            raise ValueError(f"Out-of-scope {name} update")
    for name in ("vias","arcs","fills","pours","poured","regions"):
        if before["copper"][name]!=after["copper"][name]:
            raise ValueError(f"Out-of-scope {name} update")
    ending={item["primitiveId"]:item for item in after["copper"]["lines"]}
    common = {ident for ident in originals.keys() & ending.keys() - wanted.keys()
              if originals[ident]==ending[ident]}
    expected = [wanted.get(ident,line) for ident,line in originals.items() if ident not in common]
    observed = [line for ident,line in ending.items() if ident not in common]
    compare_routes(expected,observed)
    drc=cli("drc",["pcb","drc","--strict","--json","--timeout","48"],allow_rule_failure=True)
    summary={"board":board,"widened_centerlines":len(wanted),"typed_receipt_ids":receipts,
             "removed_ids":sorted(originals.keys()-ending.keys()),
             "new_ids":sorted(ending.keys()-originals.keys()),"drc":drc["counts"]}
    (report_folder/"result.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(board,"widened",len(wanted),drc["counts"],flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("board",choices=DOCS)
    parser.add_argument("source",type=Path)
    parser.add_argument("evidence",type=Path)
    args=parser.parse_args()
    run(args.project,args.board,args.source,args.evidence)
