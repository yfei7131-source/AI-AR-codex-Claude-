#!/usr/bin/env python3
import json, re, sys, collections, pathlib, argparse
ap = argparse.ArgumentParser(); ap.add_argument("out")
ap.add_argument("--selfcheck-before", type=int); ap.add_argument("--selfcheck-after", type=int)
a = ap.parse_args(); out = pathlib.Path(a.out)
drc = json.loads((out/"drc.json").read_text()); erc = json.loads((out/"erc.json").read_text())
by = collections.Counter(v["type"] for v in drc.get("violations", []))
hole = [v for v in drc.get("violations", []) if v["type"] in ("drill_out_of_range","hole_size")
        or "Hole size out of range" in v.get("description","")]
lib = [v for v in drc.get("violations", []) if v["type"] in ("lib_footprint_issues","lib_footprint_mismatch")]
unc = drc.get("unconnected_items", [])
net = (out/"netlist.net").read_text()
m = re.search(r'\(net \(code "?\d+"?\) \(name "([^"]*CHG_PGOOD_N)"\)(.*?)\n\s*\(net ', net, re.S)
nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)) if m else []
pg_unc = [u for u in unc if "CHG_PGOOD_N" in json.dumps(u)]
summary = dict(kicad_version=(out/"kicad_version.txt").read_text().strip(),
  drc_by_type=dict(by), drc_unconnected=len(unc), drc_parity=len(drc.get("schematic_parity", [])),
  hole_size_errors=len(hole), lib_warnings=len(lib),
  erc_by_type=dict(collections.Counter(v["type"] for s in erc.get("sheets",[]) for v in s.get("violations",[]))),
  CHG_PGOOD_N=dict(found=bool(m), net=m.group(1) if m else None, nodes=nodes, unconnected_refs=len(pg_unc)),
  selfcheck_vs_native=dict(selfcheck=[a.selfcheck_before, a.selfcheck_after],
                           native_unconnected=len(unc), note="自检计数≠DRC; 以本文件native值为准"))
(out/"native_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)); print(json.dumps(summary, ensure_ascii=False))
