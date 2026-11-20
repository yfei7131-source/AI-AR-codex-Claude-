#!/usr/bin/env python3
"""End-to-end verification of H03 3-Board MECR-01 Trial (PCB1 118/118, PCB2 86/86 25x4.6mm routed, PCB3 53/53)
against PR #40, while proving PR #40's 22.0x4.2mm Track A baseline remains strictly untouched."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc"), str(PACKAGE / "h02-fp-h03-pcb")]

from prepare_hierarchy import Archive, digest

PR40_DIR = PACKAGE / "h02-fp-h03-pcb"
PR40_TRACK_A = PR40_DIR / "native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2"
PR40_TRACK_B_DRC = PR40_DIR / "evidence/track-b-25x4_6/pcb-drc-post-route.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def summarize_drc(drc_j: dict) -> dict:
    viols = drc_j.get("violations", [])
    by_rule = Counter(f"{v.get('rule')} ({v.get('objType')})" for v in viols)
    clr = sum(1 for v in viols if "Clearance" in str(v.get("rule")) or "Short" in str(v.get("rule")))
    conn = sum(1 for v in viols if "Connection" in str(v.get("rule")))
    plane_conn = sum(1 for v in viols if v.get("rule") == "Connection Error" and "Plane" in str(v.get("objType")))
    mk_slot = sum(1 for v in viols if "Slot" in str(v.get("objType")))
    netl = sum(1 for v in viols if "Netlist" in str(v.get("rule")))
    return {
        "total": len(viols),
        "clearance_or_short": clr,
        "connection_airwires": conn,
        "plane_zone_disconnected": plane_conn,
        "mic_slot_errors": mk_slot,
        "netlist_errors": netl,
        "by_rule": dict(by_rule),
    }


def verify(root_dir: Path, out_path: Path):
    ev_pre = root_dir / "evidence/pre-route"
    ev_post = root_dir / "evidence/post-route"
    arc_path = root_dir / "native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2"

    # 1. Verify exported 3-board .epro2 ZIP & SHA256 against live EasyEDA Pro V4.1.97 receipt
    with ZipFile(arc_path) as zf:
        if zf.testzip() is not None:
            raise ValueError("Exported H03 3-board .epro2 failed ZIP integrity check")
    rec = read_json(ev_post / "archive-response.json")
    arc_sha = digest(arc_path)
    if rec.get("ok") is not True or rec["result"].get("sha256") != arc_sha:
        raise ValueError("Exported H03 3-board .epro2 SHA256 mismatch vs live EasyEDA Pro receipt")

    # 2. Prove PR #40 Track A (22.0x4.2mm baseline) is strictly preserved untouched!
    pr40_report = read_json(PR40_DIR / "verification-report.json")
    ta_sha = digest(PR40_TRACK_A)
    if ta_sha != pr40_report["track_a_22x4_2_baseline"]["archive_sha256"]:
        raise ValueError("PR #40 22.0x4.2mm Track A baseline archive was modified!")
    pr40_pcb2_drc = summarize_drc(read_json(PR40_TRACK_B_DRC))

    # 3. Verify all 3 PCBs (PCB1, PCB2, PCB3) pre-route & post-route live dumps & strict DRCs!
    expected_counts = {"PCB1": 118, "PCB2": 86, "PCB3": 53}
    boards_report = {}
    for name, exp_n in expected_counts.items():
        pre_d = read_json(ev_pre / f"{name}-pre.dump.json")
        post_d = read_json(ev_post / f"{name}-post.dump.json")
        pre_drc = summarize_drc(read_json(ev_pre / f"{name}-drc-pre.json"))
        post_drc = summarize_drc(read_json(ev_post / f"{name}-drc-post.json"))

        if len(post_d["components"]) != exp_n:
            raise ValueError(f"{name}: expected {exp_n} placed components, got {len(post_d['components'])}")
        missing_uid = [c["designator"] for c in post_d["components"] if not c.get("uniqueId")]
        if missing_uid:
            raise ValueError(f"{name}: missing UniqueID on {missing_uid}")
        if pre_drc["clearance_or_short"] != 0:
            raise ValueError(f"{name}: expected 0 pre-route clearance errors, got {pre_drc['clearance_or_short']}")
        if post_drc["clearance_or_short"] != 0:
            raise ValueError(f"{name}: expected 0 post-route clearance errors, got {post_drc['clearance_or_short']}")
        if post_drc["plane_zone_disconnected"] != 0:
            raise ValueError(f"{name}: expected 0 disconnected Plane Zones after live GND stitch, got {post_drc['plane_zone_disconnected']}")
        if post_drc["mic_slot_errors"] != 0:
            raise ValueError(f"{name}: mic acoustic slot clearance regressed: {post_drc['mic_slot_errors']}")
        if post_drc["connection_airwires"] >= pre_drc["connection_airwires"]:
            raise ValueError(f"{name}: expected live copper routing/stitching to reduce airwires")

        copper = post_d.get("copper") or {}
        boards_report[name] = {
            "placed_components": len(post_d["components"]),
            "physical_pads": sum(len(c.get("pads", [])) for c in post_d["components"]),
            "unique_ids_matched": f"{len(post_d['components'])}/{len(post_d['components'])}",
            "persisted_tracks": len(copper.get("lines", [])),
            "persisted_vias": len(copper.get("vias", [])),
            "drc_pre_route": pre_drc,
            "drc_post_route": post_drc,
            "airwires_reduced_vs_pre": pre_drc["connection_airwires"] - post_drc["connection_airwires"],
        }

    # 4. Verify strict PCB2 improvement over PR #40!
    pcb2_post = boards_report["PCB2"]["drc_post_route"]
    if pcb2_post["clearance_or_short"] >= pr40_pcb2_drc["clearance_or_short"]:
        raise ValueError("PCB2 clearance errors did not improve over PR #40")
    if pcb2_post["total"] >= pr40_pcb2_drc["total"]:
        raise ValueError("PCB2 total strict DRC violations did not improve over PR #40")
    if boards_report["PCB2"]["persisted_tracks"] < 300 or boards_report["PCB2"]["persisted_vias"] < 25:
        raise ValueError("PCB2 persisted live copper below threshold")

    # Verify archive parses cleanly
    _ = Archive(arc_path)
    plan = read_json(root_dir / "evidence/pcb2-routing-plan.json")

    report = {
        "status": "VERIFIED_H03_3BOARD_ZERO_CLEARANCE_AND_LIVE_ROUTING",
        "manufacturing": "BLOCKED",
        "baseline_22x4_2_preserved": {
            "archive": str(PR40_TRACK_A.relative_to(PACKAGE.parent).as_posix()),
            "sha256": ta_sha,
            "unchanged_vs_pr40": True,
        },
        "h03_3board_mecr01_archive": {
            "path": str(arc_path.relative_to(PACKAGE.parent).as_posix()),
            "sha256": arc_sha,
            "total_placed_components_3boards": sum(v["placed_components"] for v in boards_report.values()),
            "total_physical_pads_3boards": sum(v["physical_pads"] for v in boards_report.values()),
            "total_persisted_tracks_3boards": sum(v["persisted_tracks"] for v in boards_report.values()),
            "total_persisted_vias_3boards": sum(v["persisted_vias"] for v in boards_report.values()),
            "total_clearance_errors_3boards": sum(v["drc_post_route"]["clearance_or_short"] for v in boards_report.values()),
        },
        "pcb2_progression_vs_pr40": {
            "pr40_total_drc": pr40_pcb2_drc["total"],
            "h03_total_drc": pcb2_post["total"],
            "pr40_clearance_errors": pr40_pcb2_drc["clearance_or_short"],
            "h03_clearance_errors": pcb2_post["clearance_or_short"],
            "routing_plan_summary": plan["summary"],
        },
        "boards": boards_report,
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ALL H03 3-BOARD VERIFICATIONS PASSED (0 CLEARANCE ERRORS ACROSS ALL 3 PCBs)!")
    print(json.dumps(report["h03_3board_mecr01_archive"], indent=2))
    print("PCB2 vs PR #40:", json.dumps(report["pcb2_progression_vs_pr40"], indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    verify(a.root, a.out)


if __name__ == "__main__":
    main()
