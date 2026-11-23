"""Replay R6 saved copper changes, redlined manufacturer scope and native checks."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent
sys.path[:0]=[str(PACKAGE/"h03-codex-r4-20261123/u11"),
              str(PACKAGE/"h03-v4-dfm-u11-2n2-route"), str(PACKAGE/"h02-native")]
from audit_r3_u11 import load, records
from independent_hdi_dfm_auditor_v4 import audit_board_v4
from apply_widths import compare_routes
from verify_h02 import parse_protel

EVIDENCE=HERE/"verification"
BOARDS={"PCB1":"8fbc3cae65886fe5","PCB2":"9ce45f14cb79dc9d","PCB3":"1db01a36f669a47a"}
WIDTHS={"PCB1":"pcb1/width-r6-screen.json","PCB2":"pcb2/decap-ground-widths-r6.json",
        "PCB3":"pcb3/PCB3-width-candidates.json"}
ROUTES=HERE/"pcb1/routes-plane-r6-ready.json"


def check(condition,message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def evidence(file):
    return read(EVIDENCE/file)


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def erc_signature(result):
    return ({key:value for key,value in result.items() if key!="violations"},
            Counter(json.dumps(item,sort_keys=True) for item in result["violations"]))


def track(row):
    return {key:row[key] for key in ("startX","startY","endX","endY")} | {
        "net":row["netName"],"layer":row["layerId"],"lineWidth":row["width"]}


def track_view(board):
    return {uid:track(row) for (kind,uid),row in board.items() if kind=="LINE"}


def actual_scope(base, final, board):
    a,b=track_view(base),track_view(final)
    plan=read(HERE/WIDTHS[board])["width_candidates"]
    candidates={row["id"] for row in plan}
    check(candidates==a.keys()-b.keys(),f"{board} removed any unplanned native line")
    for entry in plan:
        old=a[entry["id"]]
        check(old=={"lineWidth":3,"layer":entry["layer"],"net":entry["net"],
                    "startX":old["startX"],"startY":old["startY"],"endX":old["endX"],"endY":old["endY"]},
              f"{board} invalid source geometry")
    common={key for key in a.keys() & b.keys() if a[key]==b[key]}
    expected=[r | ({"lineWidth":4} if key in candidates else {}) for key,r in a.items() if key not in common]
    if board=="PCB1":
        for route in read(ROUTES)["routes"]:
            for line in route["segments"]:
                ((x1,y1),(x2,y2))=line
                expected.append({"net":route["net"],"layer":route["layer"],"lineWidth":route["width_mil"],
                                 "startX":x1,"startY":y1,"endX":x2,"endY":y2})
    observed=[r for key,r in b.items() if key not in common]
    # The PCB1 editor intersected two new ground branches at a common T point.
    # Allow 0.02 mil of junction-coordinate normalization in this cross-check.
    # The independent width-only checkpoints use exact centerline comparison.
    compare_routes(expected, observed, tolerance=0.02 if board=="PCB1" else 0.0001)
    return len(plan)


def verify_netlist_and_trials():
    catalog=EVIDENCE/"netlists"
    historical=PACKAGE/"h03-v4-dfm-u11-2n2-route/evidence/takeover/independent/board-netlists"
    parity=read(catalog/"compiled-parity.json")
    for board,signature in parity.items():
        new=catalog/f"{board}-r6.net"
        old=historical/f"{board}.net"
        check(digest(new)==signature["r6_sha256"],f"Native Protel artifact hash mismatch {board}")
        def membership(path):
            parts,nets=parse_protel(path.read_text(encoding="utf-8-sig"))
            return (Counter((p["designator"],p["convert_to_pcb"]) for p in parts),
                    Counter((net,tuple(sorted(members))) for net,members in nets))
        check(membership(new)==membership(old),f"Compiled nets drifted {board}")
    check(sum(record["net_groups"] for record in parity.values())==207
          and sum(record["members"] for record in parity.values())==1013,
          "Unexpected netlist group or member totals")
    trial=evidence("trials/hdi-k4-drc.json")
    rejection=evidence("trials/hdi-k4-native-outcome.json")
    check(trial["passed"] is False and trial["counts"]=={"Clearance Error":4,"Connection Error":130}
          and rejection["excluded_from_delivery"]
          and rejection["archive_persisted_design_trial_vias"]==7
          and all(v["objType"]=="Hole to Hole" for v in trial["violations"] if v["rule"]=="Clearance Error"),
          "Rejected HDI trial evidence is not consistent")
    check(all(evidence(f"trials/hdi-k4-path-{dest}.json")["connected"] for dest in ("J1","U10")),
          "Missing isolated K4 receiver paths")


def verify(r5_import=None, restored=None, dfm_folder=None):
    base,=(PACKAGE/"h03-codex-r5-20261123/native").glob("*.epro2")
    final,=(HERE/"native").glob("*.epro2")
    with ZipFile(final) as archive:
        check(archive.testzip() is None,"Native ZIP failed integrity")
        project=json.loads(archive.read("project2.json"))
        check(project["editorVersion"]=="4.1.97" and "NOT-FOR-FAB" in project["title"],
              "Native host version or project marking changed")
    original, final_doc=(load(path).documents for path in (base,final))
    check(original.keys()==final_doc.keys(),"Unexpected project inventory change")
    check(Counter(kind for kind,_ in final_doc)["SCH_PAGE"]==21,"Unexpected schematic page count")
    published=evidence("final-export.json")["result"]
    imported=evidence("restore-r6.json")["result"]
    check(published["sha256"]==imported["sourceSha256"]==digest(final)
          and published["uuid"]!=imported["uuid"] and imported["created"],
          "Native restoration did not use a separate fresh project")
    check(evidence("import-r5.json")["result"]["sourceSha256"]==digest(base),"Wrong R5 source")
    before={doc:records(value) for doc,value in original.items()}
    after={doc:records(value) for doc,value in final_doc.items()}
    for key in before:
        if key[0]!="PCB":
            check(before[key]==after[key],f"Unscoped schematic/library document delta {key}")
        else:
            check({r:v for r,v in before[key].items() if r[0] not in {"LINE","ELE_PLACEHOLDER"}}==
                  {r:v for r,v in after[key].items() if r[0] not in {"LINE","ELE_PLACEHOLDER"}},
                  f"{key} component/plane/via/rules delta leaked into the delivered project")
    results={}
    if dfm_folder:
        dfm_folder.mkdir(parents=True,exist_ok=True)
    dfm_native=SimpleNamespace(path=final,
              documents={key:SimpleNamespace(records=value) for key,value in final_doc.items()})
    dfm_results={}
    for idx,(board,uid) in enumerate(BOARDS.items()):
        key=("PCB",uid)
        wid=actual_scope(before[key],after[key],board)
        open_a,open_b=((352,340),(236,236),(132,132))[idx]
        old,new=(evidence(f"{board}-{stage}-drc.json") for stage in ("before","restore"))
        old_expect={"Connection Error":open_a} | ({"Netlist Error":1} if board=="PCB1" else {})
        new_expect=old_expect | {"Connection Error":open_b}
        check(old["passed"] is False and new["passed"] is False
              and (old["counts"],new["counts"])==(old_expect,new_expect),
              f"{board} unexpected strict DRC counts")
        erc_a,erc_b=(evidence(f"{board}-{stage}-erc.json")["result"] for stage in ("before","restore"))
        count=(4,0,2)[idx]
        check(erc_signature(erc_a)==erc_signature(erc_b) and erc_b["fatal"]==count and erc_b["strict"],
              f"{board} strict native ERC changed")
        widths=[sum(t["lineWidth"]==3 for t in track_view(stage[key]).values())
                for stage in (before,after)]
        dump=EVIDENCE/f"{board}-restore-copper.json"
        all_vias=audit_board_v4(board,dfm_native,dump,
                     blind_csv=dfm_folder/f"{board}-blind-vias.csv" if dfm_folder else None)
        dfm=all_vias["v4_official_jlcpcb_hdi_audit"]
        check(dfm["total_blind_vias"]==(61,40,41)[idx] and dfm["violations"]["total_v4_violations"]==0,
              f"{board} V4 blind-via result changed")
        dfm_results[board]=dfm
        results[board]={"before_drc":old_expect,"after_drc":new_expect,"erc_fatal":count,
                        "widened_centerlines":wid,"three_mil_inventory":widths,
                        "blind_vias":dfm["total_blind_vias"]}
    if dfm_folder:
        (dfm_folder/"geometry-report.json").write_text(json.dumps(dfm_results,indent=2)+"\n",encoding="utf8")
    proofs=list(EVIDENCE.glob("PCB1-ground-*-path.json"))
    check(len(proofs)==6 and all(read(log)["connected"] and read(log)["net"]=="GND" for log in proofs),
          "Need six real PCB1 native ground path witnesses")
    verify_netlist_and_trials()
    for archive,receipt,expected in ((r5_import,"native-baseline-export.json",before),
                                      (restored,"restore-export.json",after)):
        if archive:
            got={key:records(rows) for key,rows in load(archive).documents.items()}
            check(got==expected and digest(archive)==evidence(receipt)["result"]["sha256"],
                  f"Native independent re-export content mismatch in {archive}")
    return {"native_sha256":digest(final),"doc_count":len(after),"boards":results,
            "independent_full_reexport_compared":restored is not None,"status":"NOT FOR FAB"}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r5-import",type=Path)
    parser.add_argument("--restored",type=Path)
    parser.add_argument("--dfm-folder",type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(args.r5_import,args.restored,args.dfm_folder),indent=2))
