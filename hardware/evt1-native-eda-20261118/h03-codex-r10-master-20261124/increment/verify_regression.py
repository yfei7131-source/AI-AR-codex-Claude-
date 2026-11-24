"""Compare strict native R10 captures with the source and an independent re-import."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from easyeda_increment import PCB_IDS, archive, compare_additions, digest, endpoint, read, signatures, write

def verify(root, baseline_file, final_file, reexport_file):
    inc=root/"increment"
    logs=root/"logs"
    original=archive(baseline_file)
    target=archive(final_file)
    if target!=archive(reexport_file):
        raise ValueError("Independent native document records differ from the release file")
    steps=[]
    geometry=[]
    checkpoint=baseline_file
    for plan_path in sorted(inc.glob("pcb1-batch-*.json")):
        plan=read(plan_path)
        number=plan_path.stem.rsplit("-",1)[1]
        official=inc/f"master-pcb1-batch-{number}"
        isolated=inc/f"trial-pcb1-batch-{number}"
        receipts=[read(p/"acceptance.json") for p in (isolated,official)]
        if any(r["status"]!="accepted" or r["planSha256"]!=digest(plan_path)
               or r["checkpointSha256"]!=digest(checkpoint) for r in receipts):
            raise ValueError("Master/isolated plan binding does not match")
        if receipts[0]["before"]!=receipts[1]["before"] or receipts[0]["after"]!=receipts[1]["after"]:
            raise ValueError("Master replay changed acceptance counts")
        if receipts[0]["projectUuid"]==receipts[1]["projectUuid"]:
            raise ValueError("Master replay was not isolated")
        next_checkpoint=official/"POST-BATCH.epro2"
        board=("PCB",PCB_IDS[plan["board"]])
        compare_additions(archive(checkpoint),archive(next_checkpoint),board,plan)
        compare_additions(archive(checkpoint),archive(isolated/"POST-BATCH.epro2"),board,plan)
        steps.append({"id":plan["id"],"planSha256":digest(plan_path),"before":receipts[1]["before"],"after":receipts[1]["after"],
                      "isolatedAndMasterSameCounts":True,"nativeLineEndpoints":receipts[1]["nativePadPaths"],
                      "exactNativeGeometryRoutes":receipts[1]["directGeometryPaths"]})
        geometry.extend(plan["routes"])
        checkpoint=next_checkpoint
    if not geometry or archive(checkpoint)!=target:
        raise ValueError("Release does not match the accepted native batches")
    rollback=read(inc/"rollback-drill/restoration.json")
    restored=inc/"rollback-drill/RESTORED.epro2"
    predecessor=inc/"master-pcb1-batch-01/POST-BATCH.epro2"
    if (rollback["status"]!="restored" or rollback["checkpointSha256"]!=digest(predecessor)
            or archive(restored)!=archive(predecessor)):
        raise ValueError("Rollback checkpoint did not restore the exact predecessor")
    reports={}
    net_counts=[0,0]
    total_erc=0
    for board,document in PCB_IDS.items():
        captures=[read(logs/s/f"{board}-copper.json") for s in ("before","after","reimport")]
        for key in ("rules","outline","copperLayers","components"):
            if not captures[0][key]==captures[1][key]==captures[2][key]:
                raise ValueError(f"{board}: unplanned modification to {key}")
        if captures[1]["copper"]!=captures[2]["copper"]:
            raise ValueError(f"{board}: reimport has different copper")
        for j in captures[1:]:
            if j.get("partial") or not j["capture"]["identityVerified"]:
                raise ValueError(f"{board}: incomplete native capture")
        if board=="PCB1":
            for route in geometry:
                for row in captures[1:]:
                    for ref,point in zip((route["from"],route["to"]),(route["points"][0],route["points"][-1])):
                        endpoint(row,target["PCB",document],ref,route["net"],route["layer"],point)
        native_drc=[read(logs/s/f"{board}-drc.json") for s in ("before","after","reimport")]
        a,b,c=list(map(signatures,native_drc))
        if b!=c or any(k[0]!="Connection Error" for k in (a-b)+(b-a)):
            raise ValueError(f"{board}: native DRC regression or differences after import")
        net_digests={digest(logs/s/f"{board}.net") for s in ("before","after","reimport")}
        if len(net_digests)!=1:
            raise ValueError(f"{board}: compiled Protel2 netlist changed")
        erc=[read(logs/s/f"{board}-erc.json")["result"] for s in ("before","after","reimport")]
        def fingerprint(entry):
            summary={k:v for k,v in entry.items() if k!="violations"}
            rows=Counter(json.dumps(x,sort_keys=True) for x in entry["violations"])
            return summary,rows
        if not fingerprint(erc[0])==fingerprint(erc[1])==fingerprint(erc[2]):
            raise ValueError(f"{board}: raw ERC differs after comparison by object")
        before,after=[d["counts"].get("Connection Error",0) for d in native_drc[:2]]
        net_counts[0]+=before
        net_counts[1]+=after
        total_erc+=erc[1]["fatal"]
        reports[board]={"before":native_drc[0]["counts"],"after":native_drc[1]["counts"],"reimport":native_drc[2]["counts"],
                        "ERCFatal":erc[1]["fatal"],"nativeNetlistSha256":next(iter(net_digests))}
    summary={"status":"NOT FOR FAB","nativeArchiveSha256":digest(final_file),"sourceArchiveSha256":digest(baseline_file),
             "independentReexportSha256":digest(reexport_file),"nativeDocumentRecords":len(target),
             "totalConnectionsBeforeAfter":net_counts,"strictERCFatal":total_erc,"boards":reports,
             "acceptedBatches":steps,"rollback":{"restoredNativeDRC":rollback["nativeDRC"],
             "checkpointSha256":rollback["checkpointSha256"],"nativeDocumentRecords":rollback["documentRecordsMatch"]},
             "scope":"Final rule, component, schematic, board-binding, and routed copper audit"}
    write(root/"engineering/final-regression.json",summary)
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("final",type=Path)
    parser.add_argument("reexport",type=Path)
    options=parser.parse_args()
    result=verify(options.root,options.baseline,options.final,options.reexport)
    print("Native documents:",result["nativeDocumentRecords"],"connection errors:",result["totalConnectionsBeforeAfter"],
          "ERC fatal:",result["strictERCFatal"],"archive:",result["nativeArchiveSha256"])

if __name__=="__main__":
    main()
