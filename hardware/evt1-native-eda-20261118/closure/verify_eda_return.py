#!/usr/bin/env python3
"""Compare board-scoped EasyEDA readback against the controlled EVT-1 tables."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
BOARDS = {"M-MAIN-L": "evt1-main-left", "M-OPT-BRIDGE": "evt1-optical-bridge", "M-AUD-R": "evt1-audio-right"}
EXIT_CODES = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def read_native_bom(path):
    content = path.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    lines = content.decode(encoding).splitlines(keepends=True)
    if not lines:
        raise ValueError(f"empty BOM export: {path.name}")
    delimiter = "\t" if "\t" in lines[0] else ","
    rows = csv.DictReader(lines, delimiter=delimiter)
    if not {"Designator", "Manufacturer Part", "Footprint"}.issubset(rows.fieldnames or []):
        raise ValueError(f"required native BOM columns missing: {path.name}")
    return list(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def index(rows, key):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise ValueError(f"duplicate record {identity!r}")
        result[identity] = row
    return result


def baseline(package):
    terminal_rows = read_csv(package / "kicad/CAD_TERMINALS.csv")
    terminals = index(terminal_rows, lambda r: (r["Board"], r["CAD_Reference"], r["Pin"]))
    logical = index(read_csv(package / "Inputs/effective_netlist.csv"), lambda r: (r["Board"], r["RefDes"], r["Pin"]))
    pinmap = index(read_csv(package / "Inputs/effective_pinmap.csv"), lambda r: (r["Board"], r["Chip_Ref"], r["Pin_ID"]))
    bom = index(read_csv(package / "Inputs/effective_bom.csv"), lambda r: r["Item_ID"])
    footprints = index(read_csv(package / "FOOTPRINT_MAP.csv"), lambda r: (r["Board"], r["RefDes"]))
    if logical.keys() != pinmap.keys():
        raise ValueError("source PINMAP and NETLIST cover different terminals")
    board_terminals = {key for key in logical if key[0] in BOARDS}
    if board_terminals != {(r["Board"], r["Source_RefDes"], r["Pin"]) for r in terminal_rows}:
        raise ValueError("source NETLIST and CAD terminal manifest cover different board terminals")
    if {key[:2] for key in logical} != footprints.keys():
        raise ValueError("source NETLIST and footprint map cover different objects")
    for key, row in logical.items():
        pin = pinmap[key]
        if (row["Net"], row["BOM_Line"], row["Pin_Function"]) != (pin["Signal_Net_Name"], pin["BOM_Line"], pin["Pin_Name"]):
            raise ValueError(f"source PINMAP and NETLIST disagree at {key!r}")
        if row["BOM_Line"] not in bom:
            raise ValueError(f"missing BOM owner for {key!r}")
    parts = {}
    for (board, cad_ref, pin), terminal in terminals.items():
        source = (board, terminal["Source_RefDes"], pin)
        fp = footprints[source[:2]]
        if (terminal["Source_Net"], terminal["BOM_Line"]) != (logical[source]["Net"], logical[source]["BOM_Line"]):
            raise ValueError(f"source CAD and NETLIST disagree at {source!r}")
        if terminal["Footprint"] != (fp["Footprint"] if terminal["PCB_Use"] == "BOARD" else ""):
            raise ValueError(f"source CAD and footprint map disagree at {source!r}")
        part = {"source_ref": source[1], "mpn": bom[terminal["BOM_Line"]]["MPN"],
                "footprint": terminal["Footprint"], "pcb_use": terminal["PCB_Use"]}
        if parts.setdefault((board, cad_ref), part) != part:
            raise ValueError(f"inconsistent designator {(board, cad_ref)!r}")
    return terminals, parts


def read_connectivity(path, page, project):
    data = read_json(path)
    if (data.get("schemaVersion"), data.get("projectId"), data.get("documentId")) != ("1.4", project, page):
        raise ValueError(f"unexpected connector project, page or schema in {path.name}")
    nets = index(data["nets"], lambda r: r["id"])
    components = index(data["components"], lambda r: r["id"])
    pins = {}
    for identifier, component in components.items():
        for number, pin in index(component["pins"], lambda p: str(p["number"])).items():
            pins[(identifier, number)] = {"ref": component["ref"], "name": pin["name"], "net": ""}
    for key, connection in index(data["connections"], lambda r: (r["componentId"], str(r["pinNumber"]))).items():
        pins[key]["net"] = nets[connection["netId"]]["name"]
    return index((dict(pin, number=number) for (_, number), pin in pins.items()),
                 lambda pin: (pin["ref"], pin["number"]))


def add_observations(target, board, observed):
    for (designator, pin), item in observed.items():
        identity = (board, designator, pin)
        if identity in target:
            raise ValueError(f"same designator/pin appears on multiple pages of one board: {identity!r}")
        target[identity] = item


def load_schematic(schematic):
    manifest = read_json(schematic / "board_pages.json")
    project = manifest["project_id"]
    if set(manifest["boards"]) != set(BOARDS):
        raise ValueError("manifest must declare all three boards")
    page_ids = set()
    terms, bom, pcb_flags, missing, marker_files = {}, {}, {}, [], set()
    for board, pages in manifest["boards"].items():
        if not pages:
            raise ValueError(f"no page IDs declared for {board}")
        for page in pages:
            if not page.isalnum() or page in page_ids:
                raise ValueError(f"invalid or duplicate page ID: {page!r}")
            page_ids.add(page)
            path = schematic / "sch" / f"{page}.json"
            if not path.is_file():
                missing.append(f"sch/{page}.json")
                continue
            observed = read_connectivity(path, page, project)
            markers = schematic / "pins" / f"{page}.json"
            if markers.is_file():
                raw = read_json(markers)
                if not raw.get("ok") or (raw["context"]["projectUuid"], raw["context"]["documentUuid"]) != (project, page):
                    raise ValueError(f"wrong context in {markers.name}")
                refs = {designator for designator, _ in observed}
                for component in raw["result"]["components"]:
                    if component.get("designator") in refs:
                        pcb_flags[(board, component["designator"])] = component.get("addIntoPcb")
                    for pin in component.get("pins", []):
                        key = (component.get("designator"), str(pin.get("pinNumber")))
                        if key in observed:
                            observed[key]["no_connect"] = pin.get("noConnected")
                marker_files.add(page)
            add_observations(terms, board, observed)
            bom_path = schematic / "bom" / f"{page}.csv"
            if not bom_path.is_file():
                missing.append(f"bom/{page}.csv")
                continue
            # The SDK raw CSV uses tab delimiters. Preserve its MPN field;
            # the Value/Comment text is not a manufacturer part number.
            for line in read_native_bom(bom_path):
                for designator in line["Designator"].replace(";", ",").split(","):
                    key = (board, designator.strip())
                    if not key[1]:
                        continue
                    record = (line["Manufacturer Part"].strip(), line["Footprint"].strip())
                    if bom.setdefault(key, record) != record:
                        raise ValueError(f"conflicting native BOM rows at {key!r}")
    return terms, bom, pcb_flags, missing, len(marker_files)


def compare_bindings(schematic):
    files = [schematic / name for name in ("lceda-boards.json", "lceda-pages.json")]
    if not all(path.is_file() for path in files):
        return {"status": "BLOCKED", "reason": "native board/page registries unavailable"}
    manifest = read_json(schematic / "board_pages.json")
    boards, pages = map(read_json, files)
    for evidence in (boards, pages):
        if not evidence.get("ok") or evidence["context"]["projectUuid"] != manifest["project_id"]:
            raise ValueError("native registry points to a different project")
    by_name = index(boards["result"]["boards"], lambda row: row["name"])
    by_page = index(pages["result"]["pages"], lambda row: row["uuid"])
    per_board = {}
    for board, name in BOARDS.items():
        item = by_name.get(name, {})
        expected_parent = item.get("schematicUuid")
        declared = manifest["boards"][board]
        foreign = [page for page in declared if not expected_parent or
                   by_page.get(page, {}).get("parentSchematicUuid") != expected_parent]
        per_board[board] = {"status": "FAIL" if foreign else "PASS" if item.get("pcbUuid") else "BLOCKED",
                            "pages_outside_bound_schematic": foreign, "pcb_bound": bool(item.get("pcbUuid"))}
    extra = sorted(by_name.keys() - set(BOARDS.values()))
    states = {b["status"] for b in per_board.values()}
    return {"status": "FAIL" if extra or "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS",
            "boards": per_board, "unexpected_board_groups": extra}


def strict_erc(schematic):
    directory = schematic / "erc"
    if not directory.is_dir():
        return {"status": "BLOCKED", "reason": "strict native reports unavailable"}
    manifest = read_json(schematic / "board_pages.json")
    pages = {page for board in manifest["boards"].values() for page in board}
    per_page, missing = {}, []
    rules = defaultdict(int)
    for page in sorted(pages):
        report = directory / f"{page}.json"
        if not report.is_file():
            missing.append(page)
            continue
        data = read_json(report)
        result = data.get("result", {})
        if data.get("ok") is not True or result.get("strict") is not True or type(result.get("passed")) is not bool:
            missing.append(page)
            continue
        per_page[page] = {"passed": result["passed"], "reported": result.get("summary"), "sha256": sha256(report)}
        for finding in result.get("violations", []):
            rules[finding["rule"]] += 1
    fail = sum(not result["passed"] for result in per_page.values())
    return {"status": "FAIL" if fail else "BLOCKED" if missing else "PASS", "reported_calls": len(per_page),
            "failed_calls": fail, "missing_or_unusable_reports": missing,
            "reported_findings_by_rule": dict(sorted(rules.items())),
            "count_scope": "Per-call findings may overlap between root and child checks.", "reports": per_page}


def compare_schematic(terms, parts, schematic):
    observed, bom, pcb_flags, missing, marker_files = load_schematic(schematic)
    errors = []
    unverified_nc = 0
    for key in sorted(terms.keys() & observed.keys()):
        wanted, actual = terms[key], observed[key]
        if wanted["CAD_Net"] != actual["net"]:
            errors.append({"terminal": key, "expected_net": wanted["CAD_Net"], "observed_net": actual["net"]})
        marker_required = wanted["Local_State"] in ("NC", "LOCAL_NC")
        marker_observed = actual.get("no_connect")
        if type(marker_observed) is not bool:
            unverified_nc += 1
        elif marker_observed != marker_required:
            errors.append({"terminal": key, "expected_nc_marker": marker_required, "observed_nc_marker": marker_observed})
    def need_mpn(part):
        return part["pcb_use"] == "BOARD" and part["mpn"] and "TBD" not in part["mpn"].upper()

    bom_missing, bom_mismatch, fp_missing, fp_mismatch = [], [], [], []
    flags_missing, flags_mismatch = [], []
    for key, part in sorted(parts.items()):
        actual_mpn, actual_fp = bom.get(key, ("", ""))
        expected_flag = part["pcb_use"] == "BOARD"
        actual_flag = pcb_flags.get(key)
        if type(actual_flag) is not bool:
            flags_missing.append(key)
        elif actual_flag != expected_flag:
            flags_mismatch.append({"component": key, "source_ref": part["source_ref"],
                                   "expected_add_into_pcb": expected_flag, "observed_add_into_pcb": actual_flag})
        if need_mpn(part):
            if not actual_mpn:
                bom_missing.append(key)
            elif actual_mpn != part["mpn"]:
                bom_mismatch.append({"component": key, "expected": part["mpn"], "observed": actual_mpn})
        if part["footprint"]:
            if not actual_fp:
                fp_missing.append(key)
            elif actual_fp != part["footprint"]:
                fp_mismatch.append({"component": key, "expected": part["footprint"], "observed": actual_fp})
    absent, extra = sorted(terms.keys() - observed.keys()), sorted(observed.keys() - terms.keys())
    has_missing_pages = any(name.startswith("sch/") for name in missing)
    counts = {board: {"expected": sum(key[0] == board for key in terms),
                      "observed": sum(key[0] == board for key in observed)} for board in BOARDS}
    return {
        "named_terminal_parity": "FAIL" if errors or extra or (absent and not has_missing_pages) else "BLOCKED" if has_missing_pages or unverified_nc else "PASS",
        "board_counts": counts, "marker_files": marker_files, "unverified_nc_markers": unverified_nc,
        "expected_nc_markers": sum(r["Local_State"] in ("NC", "LOCAL_NC") for r in terms.values()),
        "missing_exports": missing, "missing_terminals": absent, "unexpected_terminals": extra,
        "net_or_nc_mismatches": errors,
        "bom": {"status": "FAIL" if bom_mismatch else "BLOCKED" if bom_missing else "PASS",
                "missing_mpn": bom_missing, "mpn_mismatches": bom_mismatch},
        "schematic_footprints": {"status": "FAIL" if fp_mismatch else "BLOCKED" if fp_missing else "PASS",
                                 "missing": fp_missing, "mismatches": fp_mismatch},
        "schematic_pcb_flags": {"status": "FAIL" if flags_mismatch else "BLOCKED" if flags_missing else "PASS",
                                "missing_flags": flags_missing, "mismatches": flags_mismatch},
    }


def compare_pcb(terms, parts, path):
    boards = {}
    for board in BOARDS:
        file = path / f"{board}.json"
        if not file.is_file():
            boards[board] = {"status": "BLOCKED", "reason": "native PCB readback unavailable"}
            continue
        raw = read_json(file)
        components = index(raw["components"], lambda c: c["designator"])
        expected = {ref: value for (b, ref), value in parts.items() if b == board and value["pcb_use"] == "BOARD"}
        missing = sorted(expected.keys() - components.keys())
        extra = sorted(components.keys() - expected.keys())
        differences, terminal_count = [], 0
        for ref in sorted(expected.keys() & components.keys()):
            component = components[ref]
            pads = defaultdict(set)
            for pad in component["pads"]:
                if pad["padNumber"]:
                    pads[str(pad["padNumber"])].add(str(pad["net"] or "").casefold())
            want = {key[2]: row["CAD_Net"].casefold() for key, row in terms.items() if key[:2] == (board, ref)}
            terminal_count += len(want.keys() & pads.keys())
            missing_pads = sorted(want.keys() - pads.keys())
            additional_pads = sorted(pads.keys() - want.keys())
            mismatched_nets = [{"pin": pin, "expected": want[pin], "observed": sorted(pads[pin])}
                               for pin in sorted(want.keys() & pads.keys()) if pads[pin] != {want[pin]}]
            if missing_pads or additional_pads or mismatched_nets:
                differences.append({"component": ref, "missing_pads": missing_pads,
                                    "additional_pads": additional_pads, "net_mismatches": mismatched_nets})
        # Missing placements are not equivalent to a net/pad discrepancy on a placed part.
        boards[board] = {"status": "FAIL" if differences or extra else "BLOCKED" if missing else "PASS",
                         "observed_components": len(components), "expected_components": len(expected),
                         "overlapping_terminal_identifiers": terminal_count, "missing_components": missing,
                         "unexpected_components": extra, "discrepancies_on_placed_components": differences,
                         "readback_sha256": sha256(file),
                         "scope": "Pad number and assigned net on supplied PCB candidate; excludes library identity, native binding and DRC."}
    return boards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PACKAGE, help="controlled input package root")
    parser.add_argument("--schematic", type=Path, help="board-scoped EasyEDA schematic/BOM export folder")
    parser.add_argument("--pcb", type=Path, help="EasyEDA PCB readback folder with <board>.json files")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        terms, parts = baseline(args.source)
        report = {"source_coherence": "PASS", "source_board_terminals": len(terms), "manufacturing": "BLOCKED"}
        if args.schematic:
            report["schematic"] = compare_schematic(terms, parts, args.schematic)
            report["native_board_binding"] = compare_bindings(args.schematic)
            report["native_strict_erc"] = strict_erc(args.schematic)
        if args.pcb:
            report["pcb"] = compare_pcb(terms, parts, args.pcb)
        states = []
        if args.schematic:
            schematic = report["schematic"]
            states += [schematic["named_terminal_parity"]]
            states += [schematic[key]["status"] for key in ("bom", "schematic_footprints", "schematic_pcb_flags")]
            states += [report["native_board_binding"]["status"], report["native_strict_erc"]["status"]]
        if args.pcb:
            states += [entry["status"] for entry in report["pcb"].values()]
        if args.schematic or args.pcb:
            states += ["BLOCKED"] if not (args.schematic and args.pcb) else []
        report["status"] = max(states, key={"PASS": 0, "BLOCKED": 1, "FAIL": 2}.get, default="BLOCKED")
    except (KeyError, TypeError, ValueError, OSError) as error:
        report = {"status": "FAIL", "error": str(error), "manufacturing": "BLOCKED"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['status']}: {args.output}")
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
