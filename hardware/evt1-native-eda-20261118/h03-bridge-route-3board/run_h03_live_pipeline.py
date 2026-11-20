#!/usr/bin/env python3
"""End-to-end live EasyEDA Pro V4.1.97 H03 3-Board Pipeline:
  1. Build 3-board pre-route layout (PCB1 118/118, PCB2 86/86 MECR-01 25x4.6, PCB3 53/53) -> capture live pre-route dumps & DRCs.
  2. Plan All-58-Nets 4-layer pad-escape + U2 BGA VIPPO routing on PCB2 -> compute exact L2/L5 SDF-union anti-pads.
  3. Rebuild 3-board archive with exact L2/L5 anti-pads -> import fresh into EasyEDA Pro V4.1.97.
  4. Commit ALL real copper tracks & vias LIVE across PCB2 (signals/power/BGA/QSPI/AVDD/GND), PCB1 (9x U1 EPAD thermal GND vias + GND stitch),
     and PCB3 (GND L2/L5 plane stitch) -> save -> reload -> capture post-route dumps & strict DRCs -> export official editable .epro2!
"""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
H03_DIR = Path(__file__).resolve().parent
DOCS = [("PCB1", "8fbc3cae65886fe5"), ("PCB2", "9ce45f14cb79dc9d"), ("PCB3", "1db01a36f669a47a")]


def run_cli(args: list[str], allow_nonzero: bool = False) -> tuple[int, str, str]:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(args)}\nSTDOUT: {p.stdout}\nSTDERR: {p.stderr}")
    return p.returncode, p.stdout, p.stderr


def wait_hydrated(exe: str, uuid: str, timeout_s: float = 20.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        rc, out, _ = run_cli([exe, "--project", uuid, "doc", "ls"], allow_nonzero=True)
        if rc == 0 and "9ce45f14cb79dc9d" in out and "8fbc3cae65886fe5" in out:
            return
        time.sleep(1.5)
    raise RuntimeError(f"Project {uuid} did not hydrate within {timeout_s}s")


def import_project(exe: str, epro2: Path, name: str, team_uuid: str, window: str) -> str:
    _, out, _ = run_cli([
        exe, "project", "import",
        "--file", str(epro2.resolve()),
        "--name", name,
        "--team-uuid", team_uuid,
        "--window", window,
    ])
    res = json.loads(out)
    uuid = res["result"]["uuid"]
    print(f"  Imported {name} -> UUID {uuid}", flush=True)
    wait_hydrated(exe, uuid)
    return uuid


def summarize_drc(drc_path: Path) -> dict:
    d = json.loads(drc_path.read_text(encoding="utf-8-sig"))
    viols = d.get("violations", [])
    c = Counter(f"{v.get('rule')} ({v.get('objType')})" for v in viols)
    clr = sum(1 for v in viols if "Clearance" in str(v.get("rule")) or "Short" in str(v.get("rule")))
    conn = sum(1 for v in viols if "Connection" in str(v.get("rule")))
    netl = sum(1 for v in viols if "Netlist" in str(v.get("rule")))
    return {"total": len(viols), "clearance": clr, "connection": conn, "netlist": netl, "by_rule": dict(c)}


def stitch_board_gnd_live(exe: str, uuid: str, doc_uuid: str, dump_path: Path, rf_y_min_mil: float, max_vias: int = 16, extra_fixed_vias: list | None = None):
    """Commit collision-free GND stitching vias (and optional fixed thermal vias) live on PCB1/PCB3."""
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    all_pads = []
    gnd_pads = []
    mic_holes = []
    for c in dump["components"]:
        ref, cx, cy, crot = c["designator"], float(c["x"]), float(c["y"]), float(c.get("rotation") or 0.0)
        if ref in ("MK1", "MK2", "MK3"):
            mic_holes.append((cx - 0.005, cy + 31.89))
        for p in c.get("pads", []):
            net = p.get("net") or ""
            pw, ph = float(p.get("width") or 16.0), float(p.get("height") or 16.0)
            rad = math.radians(crot + float(p.get("rotation") or 0.0))
            hw = 0.5 * (pw * abs(math.cos(rad)) + ph * abs(math.sin(rad))) + 0.5
            hh = 0.5 * (pw * abs(math.sin(rad)) + ph * abs(math.cos(rad))) + 0.5
            rec = {"x": float(p["x"]), "y": float(p["y"]), "hw": hw, "hh": hh, "layer": int(p.get("layer", c["layer"])), "net": net, "ref": ref}
            all_pads.append(rec)
            if net == "GND" and ref not in ("MK1", "MK2", "MK3", "U1"):
                gnd_pads.append(rec)

    placed = []
    vias_ok = 0
    tracks_ok = 0

    for vx, vy, h_mil, d_mil in (extra_fixed_vias or []):
        rc, _, _ = run_cli([
            exe, "--project", uuid, "--doc", doc_uuid, "pcb", "via",
            "--x", f"{vx:.2f}", "--y", f"{vy:.2f}", "--hole", f"{h_mil:.1f}", "--diameter", f"{d_mil:.1f}", "--net", "GND",
        ], allow_nonzero=True)
        if rc == 0:
            placed.append((vx, vy))
            vias_ok += 1

    # Bounding limits from dump pads (safe margin inside board outline)
    max_x = max(p["x"] for p in all_pads) - 10.0
    max_y = max(p["y"] for p in all_pads) - 10.0

    def via_ok(vx: float, vy: float) -> bool:
        if vx < 20.0 or vx > max_x or vy < rf_y_min_mil or vy > max_y:
            return False
        for hx, hy in mic_holes:
            if math.hypot(vx - hx, vy - hy) < 40.0:
                return False
        for ox, oy in placed:
            if math.hypot(vx - ox, vy - oy) < 20.0:
                return False
        for p in all_pads:
            if p["net"] == "GND":
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            if math.hypot(dx, dy) < 12.0:
                return False
        return True

    def seg_ok(layer: int, x1: float, y1: float, x2: float, y2: float) -> bool:
        if min(y1, y2) < rf_y_min_mil:
            return False
        steps = 8
        for p in all_pads:
            if p["layer"] != layer or p["net"] == "GND":
                continue
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                dx = max(0.0, abs(cx - p["x"]) - p["hw"])
                dy = max(0.0, abs(cy - p["y"]) - p["hh"])
                if math.hypot(dx, dy) < 9.0:
                    return False
        return True

    stitched = 0
    for gp in gnd_pads:
        if stitched >= max_vias:
            break
        px, py, lyr = gp["x"], gp["y"], gp["layer"]
        if py < rf_y_min_mil + 4.0:
            continue
        found = None
        for r_mil in (10.0, 14.0, 18.0, 22.0):
            for ang in range(0, 360, 30):
                vx = round(px + r_mil * math.cos(math.radians(ang)), 2)
                vy = round(py + r_mil * math.sin(math.radians(ang)), 2)
                if via_ok(vx, vy) and seg_ok(lyr, px, py, vx, vy):
                    found = (vx, vy)
                    break
            if found:
                break
        if found:
            vx, vy = found
            rc1, _, _ = run_cli([
                exe, "--project", uuid, "--doc", doc_uuid, "pcb", "via",
                "--x", f"{vx:.2f}", "--y", f"{vy:.2f}", "--hole", "4", "--diameter", "8", "--net", "GND",
            ], allow_nonzero=True)
            rc2, _, _ = run_cli([
                exe, "--project", uuid, "--doc", doc_uuid, "pcb", "track",
                "--x1", f"{px:.2f}", "--y1", f"{py:.2f}", "--x2", f"{vx:.2f}", "--y2", f"{vy:.2f}",
                "--layer", str(lyr), "--width", "4.0", "--net", "GND",
            ], allow_nonzero=True)
            if rc1 == 0 and rc2 == 0:
                placed.append((vx, vy))
                vias_ok += 1
                tracks_ok += 1
                stitched += 1
    return {"vias": vias_ok, "tracks": tracks_ok, "gnd_pads_stitched": stitched}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", required=True)
    p.add_argument("--scratch", type=Path, required=True)
    p.add_argument("--team-uuid", required=True)
    p.add_argument("--easyeda", default="easyeda")
    a = p.parse_args()

    ev_pre = (H03_DIR / "evidence/pre-route").resolve()
    ev_post = (H03_DIR / "evidence/post-route").resolve()
    ev_pre.mkdir(parents=True, exist_ok=True)
    ev_post.mkdir(parents=True, exist_ok=True)

    # 1. Build V3 pre-route candidate & capture live pre-route dumps + DRCs across ALL 3 BOARDS!
    print("=== STEP 1: BUILD V3 PRE-ROUTE 3-BOARD CANDIDATE ===", flush=True)
    pre_epro = a.scratch / "EVT1_H03_3BOARD_PRE_V3.epro2"
    run_cli([
        sys.executable, "-B", str(H03_DIR / "prepare_h03_3board_layout.py"),
        "--output", str(pre_epro),
        "--report", str(H03_DIR / "h03-3board-build-report.json"),
    ])
    pre_uuid = import_project(a.easyeda, pre_epro, "EVT1-H03-3BOARD-PRE-V3-20261120", a.team_uuid, a.window)

    pre_summary = {}
    for name, doc in DOCS:
        run_cli([a.easyeda, "--project", pre_uuid, "doc", "switch", doc, "--json"])
        dump_p = ev_pre / f"{name}-pre.dump.json"
        run_cli([a.easyeda, "--project", pre_uuid, "--doc", doc, "pcb", "dump", "--include-copper", "--label", f"{name}-PRE", "--out", str(dump_p)])
        _, drc_out, _ = run_cli([a.easyeda, "--project", pre_uuid, "--doc", doc, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
        drc_p = ev_pre / f"{name}-drc-pre.json"
        drc_p.write_text(drc_out, encoding="utf-8")
        pre_summary[name] = summarize_drc(drc_p)
        print(f"  {name} PRE-DRC: clearance={pre_summary[name]['clearance']}, connection={pre_summary[name]['connection']}, netlist={pre_summary[name]['netlist']}", flush=True)

    # 2. Plan All-58-Nets 4-layer pad-escape + BGA VIPPO routing on PCB2!
    print("\n=== STEP 2: PLAN ALL-58-NETS 4-LAYER ROUTING + L2/L5 ANTI-PADS FOR PCB2 ===", flush=True)
    plan_p = H03_DIR / "evidence/pcb2-routing-plan.json"
    antipads_p = H03_DIR / "evidence/pcb2-antipads.json"
    run_cli([
        sys.executable, "-B", str(H03_DIR / "route_h03_bridge_plan.py"),
        "--dump", str(ev_pre / "PCB2-pre.dump.json"),
        "--plan-out", str(plan_p),
        "--antipads-out", str(antipads_p),
    ])
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    print("  Routing Plan Summary:", json.dumps(plan["summary"]), flush=True)

    # 3. Rebuild 3-board archive with exact SDF-union L2/L5 anti-pads -> import fresh into EasyEDA Pro!
    print("\n=== STEP 3: REBUILD WITH EXACT L2/L5 SDF-UNION ANTI-PADS & IMPORT LIVE ===", flush=True)
    final_cand = a.scratch / "EVT1_H03_3BOARD_FINAL_CAND.epro2"
    run_cli([
        sys.executable, "-B", str(H03_DIR / "prepare_h03_3board_layout.py"),
        "--output", str(final_cand),
        "--report", str(H03_DIR / "h03-3board-build-report.json"),
        "--pcb2-antipads", str(antipads_p),
    ])
    live_uuid = import_project(a.easyeda, final_cand, "EVT1-H03-3BOARD-FINAL-20261120", a.team_uuid, a.window)

    # 4A. Commit ALL PCB2 tracks & vias LIVE in EasyEDA Pro V4.1.97!
    print(f"\n=== STEP 4A: COMMITTING {len(plan['tracks'])} TRACKS + {len(plan['vias'])} VIAS LIVE ON PCB2 ===", flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "doc", "switch", "9ce45f14cb79dc9d", "--json"])
    t_ok, v_ok, errs = 0, 0, 0
    for v in plan["vias"]:
        rc, _, _ = run_cli([
            a.easyeda, "--project", live_uuid, "--doc", "9ce45f14cb79dc9d", "pcb", "via",
            "--x", f"{v['x']:.2f}", "--y", f"{v['y']:.2f}",
            "--hole", f"{v['hole']:.1f}", "--diameter", f"{v['diameter']:.1f}", "--net", v["net"],
        ], allow_nonzero=True)
        if rc == 0:
            v_ok += 1
        else:
            errs += 1
    for t in plan["tracks"]:
        rc, _, _ = run_cli([
            a.easyeda, "--project", live_uuid, "--doc", "9ce45f14cb79dc9d", "pcb", "track",
            "--x1", f"{t['x1']:.2f}", "--y1", f"{t['y1']:.2f}",
            "--x2", f"{t['x2']:.2f}", "--y2", f"{t['y2']:.2f}",
            "--layer", str(t["layer"]), "--width", f"{t['width']:.1f}", "--net", t["net"],
        ], allow_nonzero=True)
        if rc == 0:
            t_ok += 1
        else:
            errs += 1
    print(f"  PCB2 Live Commit: tracks={t_ok}, vias={v_ok}, failures={errs}", flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "--doc", "9ce45f14cb79dc9d", "pcb", "save"])
    run_cli([a.easyeda, "--project", live_uuid, "doc", "reload", "9ce45f14cb79dc9d", "--json"])

    # 4B. Commit 9 persisted GND thermal vias in U1 EPAD + 12 GND plane-stitching vias LIVE on PCB1!
    print("\n=== STEP 4B: COMMITTING U1 9x GND THERMAL VIAS + GND STITCH LIVE ON PCB1 ===", flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "doc", "switch", "8fbc3cae65886fe5", "--json"])
    # U1 centered at (4.10 mm, 9.10 mm) = (161.42 mil, 358.27 mil); 3x3 thermal array at 39.37 mil (1.0 mm) pitch!
    u1_x, u1_y = 4.10 / 0.0254, 9.10 / 0.0254
    u1_vias = [(u1_x + dx * 39.37, u1_y + dy * 39.37, 8.0, 14.0) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    p1_commit = stitch_board_gnd_live(a.easyeda, live_uuid, "8fbc3cae65886fe5", ev_pre / "PCB1-pre.dump.json", rf_y_min_mil=195.0, max_vias=12, extra_fixed_vias=u1_vias)
    print("  PCB1 Live Commit:", p1_commit, flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "--doc", "8fbc3cae65886fe5", "pcb", "save"])
    run_cli([a.easyeda, "--project", live_uuid, "doc", "reload", "8fbc3cae65886fe5", "--json"])

    # 4C. Commit 12 GND plane-stitching vias LIVE on PCB3!
    print("\n=== STEP 4C: COMMITTING GND L2/L5 PLANE STITCH LIVE ON PCB3 ===", flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "doc", "switch", "1db01a36f669a47a", "--json"])
    p3_commit = stitch_board_gnd_live(a.easyeda, live_uuid, "1db01a36f669a47a", ev_pre / "PCB3-pre.dump.json", rf_y_min_mil=185.0, max_vias=12)
    print("  PCB3 Live Commit:", p3_commit, flush=True)
    run_cli([a.easyeda, "--project", live_uuid, "--doc", "1db01a36f669a47a", "pcb", "save"])
    run_cli([a.easyeda, "--project", live_uuid, "doc", "reload", "1db01a36f669a47a", "--json"])

    # 5. Capture fresh post-route dumps & strict DRCs across ALL 3 BOARDS + Export official editable .epro2!
    print("\n=== STEP 5: POST-ROUTE LIVE STRICT DRC ACROSS ALL 3 BOARDS + .epro2 EXPORT ===", flush=True)
    post_summary = {}
    for name, doc in DOCS:
        run_cli([a.easyeda, "--project", live_uuid, "doc", "switch", doc, "--json"])
        dump_p = ev_post / f"{name}-post.dump.json"
        run_cli([a.easyeda, "--project", live_uuid, "--doc", doc, "pcb", "dump", "--include-copper", "--label", f"{name}-POST", "--out", str(dump_p)])
        _, drc_out, _ = run_cli([a.easyeda, "--project", live_uuid, "--doc", doc, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
        drc_p = ev_post / f"{name}-drc-post.json"
        drc_p.write_text(drc_out, encoding="utf-8")
        post_summary[name] = summarize_drc(drc_p)
        print(f"  {name} POST-DRC: {post_summary[name]}", flush=True)

    out_epro = (H03_DIR / "native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2").resolve()
    out_epro.parent.mkdir(parents=True, exist_ok=True)
    if out_epro.exists():
        out_epro.unlink()
    _, exp_out, _ = run_cli([
        a.easyeda, "project", "export",
        "--project-uuid", live_uuid,
        "--out", str(out_epro),
        "--window", a.window,
    ])
    (ev_post / "archive-response.json").write_text(exp_out, encoding="utf-8")

    live_receipt = {
        "status": "CAPTURED_LIVE_EASYEDA_4_1_97",
        "manufacturing": "BLOCKED",
        "project_uuid": live_uuid,
        "commits": {
            "PCB1": p1_commit,
            "PCB2": {"tracks": t_ok, "vias": v_ok, "failures": errs},
            "PCB3": p3_commit,
        },
        "pre_route_drc": pre_summary,
        "post_route_drc": post_summary,
    }
    (ev_post / "live-pipeline-receipt.json").write_text(json.dumps(live_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nEXPORTED FINAL 3-BOARD .epro2: {out_epro} ({out_epro.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    main()
