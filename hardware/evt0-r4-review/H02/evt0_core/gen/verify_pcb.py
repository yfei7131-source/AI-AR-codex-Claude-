"""Verify the existing PCB without regenerating, editing, or saving it.

Run with KiCad 10's bundled Python. Native DRC failures remain failures; the
JSON verification record is written even when mapping, preservation, or DRC
checks fail. A passing static check never grants manufacturing release.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pcbnew as k


HERE = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xy(point):
    return [point.x, point.y]


def copper_signature(item):
    """Integer geometry and logical net identity, independent of net-code order."""
    result = {
        "kind": type(item).__name__,
        "net": item.GetNetname(),
        "start_iu": xy(item.GetStart()),
        "end_iu": xy(item.GetEnd()),
        "width_iu": item.GetWidth(k.F_Cu) if isinstance(item, k.PCB_VIA) else item.GetWidth(),
        "layer": item.GetLayer(),
        "layer_set": item.GetLayerSet().FmtBin(),
        "locked": item.IsLocked(),
    }
    if isinstance(item, k.PCB_VIA):
        result.update(drill_iu=item.GetDrillValue(),
                      via_type=int(item.GetViaType()),
                      top_layer=item.TopLayer(), bottom_layer=item.BottomLayer())
        result["copper_widths_iu"] = {
            str(layer): item.GetWidth(layer)
            for layer in (k.F_Cu, k.In1_Cu, k.In2_Cu, k.B_Cu)
        }
    elif isinstance(item, k.PCB_ARC):
        result["mid_iu"] = xy(item.GetMid())
    return result


def mapping_check(board, xml_path):
    tree = ET.parse(xml_path)
    components = {c.get("ref"): c for c in tree.findall("./components/comp")}
    expected = {}
    problems = []
    for net in tree.findall("./nets/net"):
        for node in net.findall("node"):
            key = (node.get("ref"), node.get("pin"))
            if key in expected:
                problems.append("Duplicate XML pin assignment: " + str(key))
            expected[key] = net.get("name")
    footprints = list(board.GetFootprints())
    reference_counts = Counter(f.GetReference() for f in footprints)
    for ref, count in reference_counts.items():
        if count != 1:
            problems.append(f"PCB has {count} footprints with reference {ref}")
    if set(reference_counts) != set(components):
        problems.append("Component/reference difference: " + str(sorted(
            set(reference_counts) ^ set(components))))
    seen = set()
    physical_numbered_pads = 0
    dnp_refs = []
    for footprint in footprints:
        ref = footprint.GetReference()
        component = components.get(ref)
        if component is None:
            continue
        declared = component.findtext("footprint")
        if footprint.GetFPIDAsString() != declared:
            problems.append(f"{ref}: footprint {footprint.GetFPIDAsString()} != {declared}")
        expected_dnp = component.find("property[@name='dnp']") is not None
        if footprint.IsDNP() != expected_dnp:
            problems.append(f"{ref}: DNP mismatch PCB={footprint.IsDNP()} XML={expected_dnp}")
        if footprint.IsDNP():
            dnp_refs.append(ref)
        expected_bom_exclusion = component.find("property[@name='exclude_from_bom']") is not None
        if footprint.IsExcludedFromBOM() != expected_bom_exclusion:
            problems.append(f"{ref}: BOM-exclusion mismatch")
        for pad in footprint.Pads():
            number = pad.GetNumber()
            if not number:
                if pad.GetNetname():
                    problems.append(f"{ref}: unnumbered pad has net {pad.GetNetname()}")
                continue
            physical_numbered_pads += 1
            key = (ref, number)
            seen.add(key)
            if key not in expected:
                problems.append(f"{ref}.{number}: physical pad absent from XML")
            elif pad.GetNetname() != expected[key]:
                problems.append(f"{ref}.{number}: net {pad.GetNetname()} != {expected[key]}")
    for key in sorted(expected.keys() - seen):
        problems.append("XML pin absent from PCB: " + str(key))
    return {
        "xml_components": len(components),
        "physical_numbered_pads_checked": physical_numbered_pads,
        "unique_numbered_pins_checked": len(seen),
        "xml_numbered_pins": len(expected),
        "dnp_references": sorted(dnp_refs),
        "matches": not problems,
        "problems": problems,
    }


def preservation_check(board, baseline_path):
    baseline = k.LoadBoard(str(baseline_path))
    old = {t.m_Uuid.AsString(): copper_signature(t) for t in baseline.GetTracks()}
    new = {t.m_Uuid.AsString(): copper_signature(t) for t in board.GetTracks()}
    missing = sorted(old.keys() - new.keys())
    changed = sorted(key for key in old.keys() & new.keys() if old[key] != new[key])
    return {
        "baseline_sha256": sha256(baseline_path),
        "baseline_copper_items": len(old),
        "retained_copper_items": len(old.keys() & new.keys()),
        "added_copper_items": len(new.keys() - old.keys()),
        "missing_uuids": missing,
        "changed_geometry_or_net_uuids": changed,
        "all_original_copper_unchanged": not missing and not changed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, default=Path(sys.executable).with_name(
        "kicad-cli.exe" if os.name == "nt" else "kicad-cli"))
    parser.add_argument("--share", type=Path, default=Path(sys.executable).resolve().parents[1] / "share/kicad")
    parser.add_argument("--pcb", type=Path, default=HERE / "evt0_core.kicad_pcb")
    parser.add_argument("--xml", type=Path, default=HERE / "evidence/evt0_core.xml")
    parser.add_argument("--baseline", type=Path, help="Existing PCB snapshot whose copper UUIDs and geometry must be retained")
    parser.add_argument("--output-dir", type=Path, default=HERE / "evidence")
    parser.add_argument("--verification", type=Path,
                        default=HERE.parents[1] / "evidence/pcb-verification.json")
    args = parser.parse_args()
    for name in ("cli", "share", "pcb", "xml", "output_dir", "verification"):
        setattr(args, name, getattr(args, name).resolve())
    if args.baseline:
        args.baseline = args.baseline.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.verification.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "manufacturing_release": False,
        "hardware_tested": False,
        "source_board_saved_by_checker": False,
        "refill_zones_in_memory": True,
        "issues": [],
        "commands": [],
    }
    exit_code = 1
    board_hash_before = None
    try:
        board_hash_before = sha256(args.pcb)
        inputs = [args.pcb, args.xml, args.pcb.with_suffix(".kicad_sch"),
                  args.pcb.with_suffix(".kicad_pro"), args.pcb.with_suffix(".kicad_dru"),
                  args.pcb.parent / "fp-lib-table", args.pcb.parent / "sym-lib-table",
                  Path(__file__).resolve()]
        report["inputs_sha256"] = {str(p.relative_to(HERE)) if p.is_relative_to(HERE) else p.name:
                                   sha256(p) for p in inputs if p.is_file()}
        version = subprocess.check_output([str(args.cli), "version"], text=True).strip()
        report["kicad_cli_version"] = version
        board = k.LoadBoard(str(args.pcb))
        copper = list(board.GetTracks())
        vias = [t for t in copper if isinstance(t, k.PCB_VIA)]
        footprints = list(board.GetFootprints())
        report["board"] = {
            "footprints": len(footprints),
            "top_footprints": sum(f.GetLayer() == k.F_Cu for f in footprints),
            "bottom_footprints": sum(f.GetLayer() == k.B_Cu for f in footprints),
            "track_segments_and_arcs": len(copper) - len(vias),
            "vias": len(vias),
            "copper_items": len(copper),
            "copper_layers": board.GetCopperLayerCount(),
            "zones": len(list(board.Zones())),
            "board_thickness_mm": k.ToMM(board.GetDesignSettings().GetBoardThickness()),
            "min_through_drill_mm": k.ToMM(board.GetDesignSettings().m_MinThroughDrill),
        }
        report["netlist_mapping"] = mapping_check(board, args.xml)
        if not report["netlist_mapping"]["matches"]:
            report["issues"].append("PCB/netlist mapping mismatch")
        if args.baseline:
            report["preservation"] = preservation_check(board, args.baseline)
            if not report["preservation"]["all_original_copper_unchanged"]:
                report["issues"].append("Baseline copper was removed or changed")
        with tempfile.TemporaryDirectory(prefix="evt0-pcb-drc-") as temp:
            conf = Path(temp) / (version.split(".")[0] + ".0")
            conf.mkdir()
            for table in ("fp-lib-table", "sym-lib-table"):
                shutil.copyfile(args.share / "template" / table, conf / table)
            env = dict(os.environ, KICAD_CONFIG_HOME=temp)
            env["KICAD" + version.split(".")[0] + "_FOOTPRINT_DIR"] = str(args.share / "footprints")
            env["KICAD" + version.split(".")[0] + "_SYMBOL_DIR"] = str(args.share / "symbols")
            for format_name, suffix in (("json", "json"), ("report", "rpt")):
                output = args.output_dir / ("pcb-drc-final." + suffix)
                # Do not accept a stale report after a failed native command.
                if output.exists():
                    output.unlink()
                command = [str(args.cli), "pcb", "drc", "--severity-all", "--schematic-parity",
                           "--exit-code-violations", "--refill-zones", "--format", format_name,
                           "-o", str(output), str(args.pcb)]
                completed = subprocess.run(command, cwd=args.pcb.parent, env=env,
                                           text=True, encoding="utf-8", errors="replace",
                                           capture_output=True, timeout=240)
                report["commands"].append({"argv": command, "exit_code": completed.returncode,
                                            "stdout": completed.stdout, "stderr": completed.stderr})
                print(f"Native DRC ({format_name}) exit={completed.returncode}")
                if not output.is_file():
                    report["issues"].append("Missing native DRC output: " + output.name)
        json_path = args.output_dir / "pcb-drc-final.json"
        native = json.loads(json_path.read_text(encoding="utf-8-sig"))
        drc = {}
        for group in ("violations", "unconnected_items", "schematic_parity"):
            rows = native.get(group, [])
            drc[group] = {
                "count": len(rows),
                "by_type": dict(sorted(Counter(row.get("type", "unknown") for row in rows).items())),
                "by_severity": dict(sorted(Counter(row.get("severity", "unknown") for row in rows).items())),
            }
        drc["remaining_unconnected_items"] = drc["unconnected_items"]["count"]
        drc["ignored_checks"] = native.get("ignored_checks", [])
        drc["included_severities"] = native.get("included_severities", [])
        report["drc"] = drc
        if any(drc[group]["count"] for group in ("violations", "unconnected_items", "schematic_parity")):
            report["issues"].append("Native DRC contains violations, unconnected items, or parity issues")
        native_failures = [c["exit_code"] for c in report["commands"] if c["exit_code"] != 0]
        if native_failures:
            report["issues"].append("Native DRC returned nonzero")
        exit_code = 0 if not report["issues"] else (native_failures[0] if native_failures else 1)
        report["outputs_sha256"] = {
            path.name: sha256(path) for path in (args.output_dir / "pcb-drc-final.json",
                                                args.output_dir / "pcb-drc-final.rpt") if path.is_file()
        }
    except Exception as error:
        report["issues"].append(type(error).__name__ + ": " + str(error))
        exit_code = 1
    finally:
        if board_hash_before is not None:
            unchanged = args.pcb.is_file() and sha256(args.pcb) == board_hash_before
            report["source_board_unchanged"] = unchanged
            if not unchanged:
                report["issues"].append("PCB changed during verification; rerun after edits finish")
                exit_code = 1
        report["static_checks_passed"] = exit_code == 0
        report["script_exit_code"] = exit_code
        args.verification.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"verification": str(args.verification), "exit_code": exit_code,
                      "manufacturing_release": False, "issues": report["issues"]}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
