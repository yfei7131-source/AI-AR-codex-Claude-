#!/usr/bin/env python3
"""Inject exact SDF-union L2/L5 anti-pads on ALL 3 boards (PCB1, PCB2, PCB3) preserving PR #41's exact
component placement, import into live EasyEDA Pro V4.1.97, commit ALL real copper tracks & vias live across
PCB1, PCB2, and PCB3, save/reload, capture live 3-board strict DRC + live 3-board strict ERC, and export .epro2."""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
H03_CUR = Path(__file__).resolve().parent
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h02-erc"),
    str(PACKAGE / "h02-reve-h03-bridge"),
    str(PACKAGE / "h02-fp-h03-pcb"),
    str(PACKAGE / "h03-bridge-route-3board"),
]

from bind_murata_l2 import mil
from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards
from prepare_hierarchy import Archive
from prepare_h03_3board_layout import PCB1_KEY, PCB2_KEY, PCB3_KEY, build_h03_3board, make_union_hole_polys

DOCS = [("PCB1", "8fbc3cae65886fe5"), ("PCB2", "9ce45f14cb79dc9d"), ("PCB3", "1db01a36f669a47a")]


def run_cli(args: list[str], allow_nonzero: bool = False) -> tuple[int, str, str]:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"CLI failed ({p.returncode}): {' '.join(args)}\nSTDOUT: {p.stdout}\nSTDERR: {p.stderr}")
    return p.returncode, p.stdout, p.stderr


def wait_hydrated(exe: str, uuid: str, timeout_s: float = 25.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        rc, out, _ = run_cli([exe, "--project", uuid, "doc", "ls"], allow_nonzero=True)
        if rc == 0 and "9ce45f14cb79dc9d" in out and "8fbc3cae65886fe5" in out:
            return
        time.sleep(1.5)
    raise RuntimeError(f"Project {uuid} did not hydrate within {timeout_s}s")


def inject_pcb1_pcb3_antipads(cand_epro: Path, plans_dir: Path):
    """Add exact SDF-union r=15.2 mil anti-pads into PCB1 and PCB3 L2/L5 LAYER_FILL (PCB2 already handled by builder)."""
    arc = Archive(cand_epro)
    cfg = [
        ("PCB1", PCB1_KEY, "MK1", (13.0, 310.0, 178.0, 1798.0)),
        ("PCB3", PCB3_KEY, "MK3", (13.0, 192.0, 170.5, 1325.5)),
    ]
    counts = {}
    for bname, pkey, mref, bounds in cfg:
        ap_path = plans_dir / f"{bname}-antipads.json"
        if not ap_path.exists():
            continue
        ap_list = json.loads(ap_path.read_text(encoding="utf-8"))
        if not ap_list:
            continue
        doc = arc.documents[pkey]
        # Locate mic component world x,y from PCB COMPONENT + ATTR
        by_p = {}
        for r in doc.records:
            if r.header["type"] == "ATTR" and r.payload.get("parentId"):
                by_p.setdefault(r.payload["parentId"], {})[r.payload["key"]] = r.payload.get("value")
        mx, my = None, None
        for r in doc.records:
            if r.header["type"] == "COMPONENT" and by_p.get(r.header["id"], {}).get("Designator") == mref:
                mx = float(r.payload["x"]) - 0.005
                my = float(r.payload["y"]) + 31.89
                break
        circles = [(mx, my, 28.0)] if mx is not None else []
        for vx, vy in ap_list:
            circles.append((float(vx), float(vy), 15.2))
        holes = make_union_hole_polys(circles, *bounds)
        for r in doc.records:
            if r.header["type"] == "LAYER_FILL":
                for it in r.payload.get("fill", []):
                    if it.get("layerId") in (15, 17) and it.get("path"):
                        outer = it["path"][0]
                        it["path"] = [outer, *holes]
        counts[bname] = len(ap_list)
    tmp_out = cand_epro.with_suffix(".tmp.epro2")
    if tmp_out.exists():
        tmp_out.unlink()
    arc.write(tmp_out)
    tmp_out.replace(cand_epro)
    print(f"  Injected L2/L5 SDF-union anti-pads on PCB1/PCB3: {counts}", flush=True)


def summarize_drc(drc_path: Path) -> dict:
    d = json.loads(drc_path.read_text(encoding="utf-8-sig"))
    viols = d.get("violations", [])
    c = Counter(f"{v.get('rule')} ({v.get('objType')})" for v in viols)
    clr = sum(1 for v in viols if "Clearance" in str(v.get("rule")) or "Short" in str(v.get("rule")))
    conn = sum(1 for v in viols if "Connection" in str(v.get("rule")))
    netl = sum(1 for v in viols if "Netlist" in str(v.get("rule")))
    return {"total": len(viols), "clearance": clr, "connection": conn, "netlist": netl, "by_rule": dict(c)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", required=True)
    p.add_argument("--scratch", type=Path, required=True)
    p.add_argument("--team-uuid", required=True)
    p.add_argument("--easyeda", default="easyeda")
    a = p.parse_args()

    plans_dir = (H03_CUR / "evidence/plans").resolve()
    ev_post = (H03_CUR / "evidence/post-route").resolve()
    ev_erc = (H03_CUR / "evidence/erc-3board").resolve()
    ev_post.mkdir(parents=True, exist_ok=True)
    ev_erc.mkdir(parents=True, exist_ok=True)

    # 1. Build clean 3-board candidate with exact PR #41 placement + ALL 3 boards' L2/L5 SDF-union anti-pads!
    print("=== STEP 1: BUILD 3-BOARD ARCHIVE WITH EXACT PR #41 PLACEMENT + ALL-3-BOARD L2/L5 ANTI-PADS ===", flush=True)
    cand = a.scratch / "EVT1_H03_3BOARD_ROUTED_CAND.epro2"
    build_h03_3board(
        PACKAGE / "h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2",
        PACKAGE / "h02-fp-h03-pcb/evidence/track-a-22x4_2/board-netlists",
        cand,
        H03_CUR / "h03-3board-build-report.json",
        plans_dir / "PCB2-antipads.json",
    )
    inject_pcb1_pcb3_antipads(cand, plans_dir)

    # 2. Import into live EasyEDA Pro V4.1.97
    print("\n=== STEP 2: IMPORT INTO LIVE EASYEDA PRO V4.1.97 ===", flush=True)
    _, imp_out, _ = run_cli([
        a.easyeda, "project", "import",
        "--file", str(cand.resolve()),
        "--name", "EVT1-H03-3BOARD-ROUTED-20261121",
        "--team-uuid", a.team_uuid,
        "--window", a.window,
    ])
    uuid = json.loads(imp_out)["result"]["uuid"]
    print(f"  Imported UUID: {uuid}", flush=True)
    wait_hydrated(a.easyeda, uuid)

    # 3. Commit ALL tracks & vias LIVE across PCB2, PCB3, PCB1!
    commits = {}
    post_drcs = {}
    for bname, doc in [("PCB2", "9ce45f14cb79dc9d"), ("PCB3", "1db01a36f669a47a"), ("PCB1", "8fbc3cae65886fe5")]:
        plan = json.loads((plans_dir / f"{bname}-plan.json").read_text(encoding="utf-8"))
        print(f"\n=== STEP 3 ({bname}): COMMITTING {len(plan['tracks'])} TRACKS + {len(plan['vias'])} VIAS LIVE ===", flush=True)
        run_cli([a.easyeda, "--project", uuid, "doc", "switch", doc, "--json"])
        v_ok, t_ok, errs = 0, 0, 0
        for v in plan["vias"]:
            rc, _, _ = run_cli([
                a.easyeda, "--project", uuid, "--doc", doc, "pcb", "via",
                "--x", f"{v['x']:.2f}", "--y", f"{v['y']:.2f}",
                "--hole", f"{v['hole']:.1f}", "--diameter", f"{v['diameter']:.1f}", "--net", v["net"],
            ], allow_nonzero=True)
            if rc == 0:
                v_ok += 1
            else:
                errs += 1
        for idx, t in enumerate(plan["tracks"], 1):
            rc, _, _ = run_cli([
                a.easyeda, "--project", uuid, "--doc", doc, "pcb", "track",
                "--x1", f"{t['x1']:.2f}", "--y1", f"{t['y1']:.2f}",
                "--x2", f"{t['x2']:.2f}", "--y2", f"{t['y2']:.2f}",
                "--layer", str(t["layer"]), "--width", f"{t['width']:.1f}", "--net", t["net"],
            ], allow_nonzero=True)
            if rc == 0:
                t_ok += 1
            else:
                errs += 1
            if idx % 150 == 0:
                print(f"    {bname} progress: {idx}/{len(plan['tracks'])} tracks committed...", flush=True)
        commits[bname] = {"tracks_cmd": t_ok, "vias_cmd": v_ok, "failures": errs}
        print(f"  {bname} Live Commit Complete: tracks={t_ok}, vias={v_ok}, failures={errs}", flush=True)

        run_cli([a.easyeda, "--project", uuid, "--doc", doc, "pcb", "save"])
        run_cli([a.easyeda, "--project", uuid, "doc", "reload", doc, "--json"])
        dump_p = ev_post / f"{bname}-post.dump.json"
        run_cli([a.easyeda, "--project", uuid, "--doc", doc, "pcb", "dump", "--include-copper", "--label", f"{bname}-POST-R2", "--out", str(dump_p)])
        _, drc_out, _ = run_cli([a.easyeda, "--project", uuid, "--doc", doc, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
        drc_p = ev_post / f"{bname}-drc-post.json"
        drc_p.write_text(drc_out, encoding="utf-8")
        post_drcs[bname] = summarize_drc(drc_p)
        print(f"  {bname} POST-DRC: {post_drcs[bname]}", flush=True)

    # 4. Run live 3-board strict ERC + Protel2 netlist export on the live project!
    print("\n=== STEP 4: LIVE 3-BOARD STRICT ERC & PROTEL2 NETLISTS ===", flush=True)
    manifest = json.loads((PACKAGE / "h02-erc/evidence/board_pages.json").read_bytes())
    manifest["project_id"] = uuid
    manifest["project_name"] = "EVT1-H03-3BOARD-ROUTED-20261121"
    write_json(ev_erc / "board_pages.json", manifest)
    probe = Capture(ev_erc, a.easyeda, uuid, 1)
    probe.run("project-info.json", ["project", "info"])
    capture_boards(probe, manifest)

    # 5. Export final editable 3-board .epro2 directly from EasyEDA Pro V4.1.97!
    print("\n=== STEP 5: OFFICIAL .epro2 EXPORT ===", flush=True)
    out_epro = (H03_CUR / "native/ZY_AIAR_EVT1_H03_3BOARD_ROUTED_MECR01_NOT_FOR_FAB.epro2").resolve()
    out_epro.parent.mkdir(parents=True, exist_ok=True)
    if out_epro.exists():
        out_epro.unlink()
    _, exp_out, _ = run_cli([
        a.easyeda, "project", "export",
        "--project-uuid", uuid,
        "--out", str(out_epro),
        "--window", a.window,
    ])
    (ev_post / "archive-response.json").write_text(exp_out, encoding="utf-8")

    receipt = {
        "status": "CAPTURED_LIVE_EASYEDA_4_1_97",
        "manufacturing": "BLOCKED",
        "project_uuid": uuid,
        "commits": commits,
        "post_route_drc": post_drcs,
    }
    (ev_post / "live-pipeline-receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nEXPORTED FINAL 3-BOARD .epro2: {out_epro} ({out_epro.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    main()
