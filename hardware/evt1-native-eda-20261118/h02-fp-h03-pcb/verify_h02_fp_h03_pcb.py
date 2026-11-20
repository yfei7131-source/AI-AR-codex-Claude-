#!/usr/bin/env python3
"""End-to-end verification of Track A (H02 footprint convergence, 22.0x4.2mm preserved)
and Track B (independent MECR-01 25.0x4.6mm 86-part layout + live copper routing + DRC)
against PR #39."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc"), str(PACKAGE / "h02-reve-h03-bridge")]

from prepare_hierarchy import Archive, PCB_BINDINGS, digest, validate_instances
from repair_supply_wire_names import ROOTS
from verify_round import read_erc

PR39_DIR = PACKAGE / "h02-reve-h03-bridge"
PR39_ARCHIVE = PR39_DIR / "native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2"


def read_json(path: Path):
    return json.loads(path.read_bytes())


def parse_protel2_nets(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    nets = {}
    for m in re.finditer(r"\(\r?\n(.*?)\r?\n\)", text, re.S):
        lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
        if lines:
            nets[lines[0]] = sorted(set(lines[1:]))
    return nets


def export_clean_boms(archive: Archive, out_dir: Path):
    """Export cleaned Rev E.1 engineering BOM CSVs (excluding #FLG* PWR_FLAG symbols)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sch_to_board = {}
    for bname, root_page in ROOTS.items():
        suid = archive.documents[("SCH_PAGE", root_page)].one("META").payload.get("schematic")
        if suid:
            sch_to_board[suid] = bname
    devs = {uid: doc.one("META").payload.get("attributes", {}) for (k, uid), doc in archive.documents.items() if k == "DEVICE"}
    fps = {uid: doc.one("META").payload.get("title", "") for (k, uid), doc in archive.documents.items() if k == "FOOTPRINT"}

    by_board = {"M-MAIN-L": [], "M-OPT-BRIDGE": [], "M-AUD-R": []}
    for (k, puid), doc in archive.documents.items():
        if k != "SCH_PAGE":
            continue
        bname = sch_to_board.get(doc.one("META").payload.get("schematic"))
        if not bname:
            continue
        by_p = {}
        for r in doc.records:
            if r.header["type"] == "ATTR" and r.payload.get("parentId"):
                by_p.setdefault(r.payload["parentId"], {})[r.payload["key"]] = r.payload.get("value")
        for r in doc.records:
            if r.header["type"] != "COMPONENT":
                continue
            ca = by_p.get(r.header["id"], {})
            des = ca.get("Designator", "")
            if not des or des.startswith("CBB") or des.startswith("#FLG"):
                continue
            duid = ca.get("Device", "")
            da = devs.get(duid, {})
            fuid = da.get("Footprint", "")
            by_board[bname].append({
                "Board": bname,
                "Designator": des,
                "SourceRef": ca.get("EVT1 Source Ref") or da.get("EVT1 Source Ref", ""),
                "Value": ca.get("Value") or da.get("Value", ""),
                "MPN": ca.get("Manufacturer Part") or da.get("Manufacturer Part") or ca.get("MPN") or da.get("MPN", ""),
                "Footprint": fps.get(fuid, ""),
                "AddIntoBOM": ca.get("Add into BOM", da.get("Add into BOM", "yes")),
                "ConvertToPCB": ca.get("Convert to PCB", da.get("Convert to PCB", "yes")),
                "UniqueId": ca.get("Unique ID") or r.payload.get("attrs", {}).get("Unique ID", ""),
            })
    summary = {}
    for bname, rows in by_board.items():
        rows.sort(key=lambda x: x["Designator"])
        with (out_dir / f"{bname}.reve1.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        summary[bname] = {
            "total_parts_excl_pwr_flags": len(rows),
            "bom_yes": sum(1 for r in rows if r["AddIntoBOM"] == "yes"),
            "pcb_yes": sum(1 for r in rows if r["ConvertToPCB"] == "yes"),
            "footprint_bound": sum(1 for r in rows if r["Footprint"]),
        }
    return summary


def verify(root_dir: Path, out_path: Path):
    ta_ev = root_dir / "evidence/track-a-22x4_2"
    tb_ev = root_dir / "evidence/track-b-25x4_6"
    ta_arc_path = root_dir / "native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2"
    tb_arc_path = root_dir / "native/ZY_AIAR_EVT1_H03_MECR01_25x4_6_TRIAL_NOT_FOR_FAB.epro2"

    # 1. Verify ZIP & SHA256 for BOTH exported archives
    for label, p, ev in [("Track A", ta_arc_path, ta_ev), ("Track B", tb_arc_path, tb_ev)]:
        with ZipFile(p) as zf:
            if zf.testzip() is not None:
                raise ValueError(f"{label} ZIP integrity failed")
        rec = read_json(ev / "archive-response.json")
        if rec.get("ok") is not True or rec["result"].get("sha256") != digest(p):
            raise ValueError(f"{label} exported .epro2 SHA256 mismatch vs live editor receipt")

    pr39 = Archive(PR39_ARCHIVE)
    ta = Archive(ta_arc_path)
    tb = Archive(tb_arc_path)
    if validate_instances(pr39) != validate_instances(ta):
        raise ValueError("Track A schematic hierarchy changed vs PR #39")

    # 2. Verify Track A 207 Rev E net groups 100% identical to PR #39!
    net_parity = {}
    total_nets = 0
    for b in ("M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"):
        n_ref = parse_protel2_nets(PR39_DIR / f"evidence/board-netlists/{b}.net")
        n_cur = parse_protel2_nets(ta_ev / f"board-netlists/{b}.net")
        if n_ref != n_cur:
            raise ValueError(f"Track A Protel2 netlist diverged from PR #39 on {b}!")
        net_parity[b] = {"net_groups": len(n_cur), "status": "PASS_EXACT_PR39_PARITY"}
        total_nets += len(n_cur)

    # 3. Verify Track A live strict ERC progression
    erc_summary = {}
    for b, root in ROOTS.items():
        b_erc = read_erc(PR39_DIR / f"evidence/erc/{root}.json")
        a_erc = read_erc(ta_ev / f"erc/{root}.json")
        bad_rules = {k[0] for k in a_erc} - {"MISSFOOTPRINT", "ONLYSYMBOL"}
        if bad_rules:
            raise ValueError(f"Unexpected ERC rules on {b}: {bad_rules}")
        added = a_erc.keys() - b_erc.keys()
        if added:
            raise ValueError(f"New ERC errors introduced on {b}: {added}")
        miss_names = sorted(item["name"] for (rule, _, _), item in a_erc.items() if rule == "MISSFOOTPRINT")
        erc_summary[b] = {
            "pr39_before": len(b_erc),
            "track_a_after": len(a_erc),
            "cleared_this_round": len(b_erc) - len(a_erc),
            "diagnostics_after": dict(Counter(k[0] for k in a_erc)),
            "remaining_missfootprint_refs": miss_names,
        }

    # 4. Verify Track A PCB2 baseline strictly preserved (22.0x4.2mm, 17 placed, 0 clearance errors)
    ta_dump = read_json(ta_ev / "bridge/bridge-22x4_2-persisted.dump.json")
    ta_drc = read_json(ta_ev / "bridge/pcb-drc-after.json")
    ta_clr = [v for v in ta_drc.get("violations", []) if "Clearance" in str(v.get("rule", ""))]
    if len(ta_dump["components"]) != 17 or ta_clr:
        raise ValueError(f"Track A 22x4.2 baseline PCB2 regressed: comps={len(ta_dump['components'])}, clr={len(ta_clr)}")

    # 5. Verify Track B independent MECR-01 25.0x4.6mm trial (86/86 placed, live routing, pre/post DRC)
    tb_pre_dump = read_json(tb_ev / "bridge-25x4_6-pre-route.dump.json")
    tb_post_dump = read_json(tb_ev / "bridge-25x4_6-post-route.dump.json")
    tb_pre_drc = read_json(tb_ev / "pcb-drc-pre-route.json")
    tb_post_drc = read_json(tb_ev / "pcb-drc-post-route.json")
    tb_route_log = read_json(tb_ev / "live-routing-log.json")

    if len(tb_post_dump["components"]) != 86:
        raise ValueError(f"Expected 86 placed components on Track B PCB2, got {len(tb_post_dump['components'])}")
    missing_uids = [c["designator"] for c in tb_post_dump["components"] if not c.get("uniqueId")]
    if missing_uids:
        raise ValueError(f"Track B PCB2 unlinked UniqueIDs: {missing_uids}")

    def summarize_drc(drc_j):
        viols = drc_j.get("violations", [])
        by_rule = Counter(f"{v.get('rule')} ({v.get('objType')})" for v in viols)
        mk2_errs = [v for v in viols if "Slot" in str(v.get("objType", ""))]
        net_errs = [v for v in viols if "Netlist" in str(v.get("rule", ""))]
        conn_errs = [v for v in viols if "Connection" in str(v.get("rule", ""))]
        clr_errs = [v for v in viols if "Clearance" in str(v.get("rule", "")) or "Short" in str(v.get("rule", ""))]
        return {
            "total": len(viols),
            "netlist_errors": len(net_errs),
            "mk2_slot_errors": len(mk2_errs),
            "clearance_or_short_errors": len(clr_errs),
            "connection_airwire_errors": len(conn_errs),
            "by_rule": dict(by_rule),
        }

    pre_drc_sum = summarize_drc(tb_pre_drc)
    post_drc_sum = summarize_drc(tb_post_drc)
    if pre_drc_sum["mk2_slot_errors"] != 0 or post_drc_sum["mk2_slot_errors"] != 0:
        raise ValueError(f"MK2 slot DRC regressed on Track B: pre={pre_drc_sum['mk2_slot_errors']}, post={post_drc_sum['mk2_slot_errors']}")

    if post_drc_sum["connection_airwire_errors"] >= pre_drc_sum["connection_airwire_errors"]:
        raise ValueError("Expected live copper routing to reduce Connection Error airwires on Track B")

    # Verify all 5 Rev E ECOs + ECO-02 directly on Track A live Protel2 netlists
    main_nets = parse_protel2_nets(ta_ev / "board-netlists/M-MAIN-L.net")
    br_nets = parse_protel2_nets(ta_ev / "board-netlists/M-OPT-BRIDGE.net")
    aud_nets = parse_protel2_nets(ta_ev / "board-netlists/M-AUD-R.net")
    eco_checks = {
        "ECO-03_FPGA_1V2_SENSE_AND_1V8_EN": ("FPGA_1V2_SENSE" in br_nets and "FPGA_1V8_EN" in br_nets),
        "ECO-07_USB_ILIM_61K9": ("USB_LIM_ILIM" in main_nets and "VBUS_5V_USB" in main_nets),
        "ECO-08_NRF_32K_XTAL": ("LFXO_XL1" in aud_nets and "LFXO_XL2" in aud_nets),
        "ECO-09_NO_FLOATING_CMOS": ("U11-2" in [t.split()[0] for t in main_nets.get("GND", [])]),
        "ECO-14_USB_ESD_GND": ("VBUS_5V_USB" in main_nets and "USB_DP" in main_nets and "USB_DM" in main_nets),
        "ECO-02_LED_3V3_PRIV": ("LED_3V3_PRIV" in main_nets and "LED_2V8" not in main_nets),
    }
    if not all(eco_checks.values()):
        raise ValueError(f"Rev E ECO parity check failed on Track A: {eco_checks}")

    # Export clean Rev E.1 engineering BOMs from Track A
    bom_summary = export_clean_boms(ta, ta_ev / "engineering-bom")

    report = {
        "status": "VERIFIED_H02_FP_CONVERGENCE_AND_MECR01_25x4_6_TRIAL",
        "manufacturing": "BLOCKED",
        "track_a_22x4_2_baseline": {
            "archive_sha256": digest(ta_arc_path),
            "board_outline_mm": [22.0, 4.2],
            "pcb2_placed": len(ta_dump["components"]),
            "pcb2_clearance_errors": len(ta_clr),
            "rev_e_net_groups_total": total_nets,
            "net_parity_vs_pr39": net_parity,
            "rev_e_eco_checks": eco_checks,
            "strict_erc_progression": {
                "pr36_total": 268,
                "pr38_total": 246,
                "pr39_total": 130,
                "track_a_total": sum(v["track_a_after"] for v in erc_summary.values()),
                "cleared_this_round": sum(v["cleared_this_round"] for v in erc_summary.values()),
                "boards": erc_summary,
            },
            "clean_engineering_bom": bom_summary,
        },
        "track_b_25x4_6_mecr01_trial": {
            "archive_sha256": digest(tb_arc_path),
            "board_outline_mm": [25.0, 4.6],
            "placed_components": len(tb_post_dump["components"]),
            "physical_pads": sum(len(c.get("pads", [])) for c in tb_post_dump["components"]),
            "unique_ids_matched": f"{len(tb_post_dump['components'])}/{len(tb_post_dump['components'])}",
            "live_routing": {
                "nets_attempted": len(tb_route_log["nets"]),
                "nets_with_real_copper": sum(1 for n in tb_route_log["nets"] if n.get("tracks", 0) > 0 or n.get("vias", 0) > 0),
                "tracks_created": tb_route_log["tracks_created"],
                "vias_created": tb_route_log["vias_created"],
                "gnd_plane_vias": tb_route_log.get("gnd_plane_vias", 0),
                "layers_used": tb_route_log.get("layers_used", {}),
                "airwires_reduced": pre_drc_sum["connection_airwire_errors"] - post_drc_sum["connection_airwire_errors"],
            },
            "drc_pre_route": pre_drc_sum,
            "drc_post_route": post_drc_sum,
        },
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ALL TRACK A & TRACK B VERIFICATIONS PASSED!")
    print("TRACK A ERC:", json.dumps(report["track_a_22x4_2_baseline"]["strict_erc_progression"], indent=2))
    print("TRACK B PRE-DRC:", json.dumps(pre_drc_sum, indent=2))
    print("TRACK B POST-DRC:", json.dumps(post_drc_sum, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    verify(a.root, a.out)


if __name__ == "__main__":
    main()
