#!/usr/bin/env python3
"""Save/reload the H02 candidate, export it, and capture targeted native evidence."""

import argparse
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "h02-native"))
from capture_native_h02 import Capture, root_map, write_json
from repair_native_power_names import PAGES
from bind_kingbright_d3 import PAGE as D3_PAGE


PRIOR = PACKAGE / "h02-native/evidence/native-C"


def capture_boards(probe, manifest):
    boards = probe.run("lceda-boards.json", ["board", "list"])
    pages = probe.run("lceda-pages.json", ["sch", "pages"])
    probe.run("lceda-pcbs.json", ["pcb", "docs"])
    for response in (boards, pages):
        if response.get("context", {}).get("projectUuid") != probe.project:
            raise ValueError("candidate project identity mismatched")
    roots = root_map(manifest, boards, pages)
    for board, root in roots.items():
        saved = probe.run(f"save/{board}.json", ["--doc", root, "sch", "save"], mutates=True)
        if saved.get("result", {}).get("saved") is not True:
            raise ValueError(f"candidate save unconfirmed: {board}")
        reloaded = probe.run(f"reload/{board}.json", ["doc", "reload", root, "--json"], mutates=True)
        if (reloaded.get("saved") is not True or reloaded.get("reloaded") != root
                or reloaded.get("finalContext", {}).get("projectUuid") != probe.project):
            raise ValueError(f"candidate reload unconfirmed: {board}")
        probe.run(f"root/{board}.json", ["doc", "switch", root, "--json"])
        response = probe.run(f"board-netlists/{board}.response.json", ["sch", "netlist", "--type", "Protel2"])
        context = response.get("context", {})
        if (context.get("projectUuid"), context.get("documentUuid")) != (probe.project, root):
            raise ValueError(f"candidate netlist scope unconfirmed: {board}")
        probe.artifact(response, board, "netlist")
        erc = probe.run(f"erc/{root}.json", ["sch", "drc", "--json", "--strict"], allow_rule_failure=True)
        result = erc.get("result", {})
        if not result.get("strict") or not result.get("detailsAvailable"):
            raise ValueError(f"strict ERC details missing: {board}")
        print(f"{board}: strict ERC passed={result['passed']} {result['summary']}", flush=True)


def capture_archive_and_pages(probe, manifest, archive, window):
    receipt = probe.run("archive-response.json", [
        "project", "export", "--project-uuid", probe.project, "--out", str(archive.resolve())
    ], mutates=True, window=window)
    if receipt.get("result", {}).get("uuid") != probe.project or not archive.is_file():
        raise ValueError("candidate archive export identity unconfirmed")
    parts = json.loads((PACKAGE / "h02-native/catalog-plan.json").read_bytes())["records"]
    l2, = (row for row in parts if row["sourceReference"] == "L2_1V8")
    changed = set(PAGES.values()) | {l2["capturePage"], D3_PAGE[1]}
    targets = [(board, page) for board, contained in manifest["boards"].items() for page in contained
               if page in changed or not (PRIOR / "pins" / f"{page}.json").is_file()]
    page_errors = []
    for board, page in targets:
        try:
            response = probe.run(f"pins/{page}.json", [
                "sch", "list", "--page", page, "--stay", "--include-pins"
            ])
            context = response.get("context", {})
            if (context.get("projectUuid"), context.get("documentUuid")) != (probe.project, page):
                raise ValueError(f"candidate page scope unconfirmed: {page}")
            print(f"Fresh native page capture {board}/{page}", flush=True)
        except (ValueError, RuntimeError) as error:
            page_errors.append(str(error))
            print(f"Page capture blocked {board}/{page}: {error}", flush=True)
    if page_errors:
        raise RuntimeError("; ".join(page_errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--window", required=True, help="exact window id for the native archive export")
    parser.add_argument("--resume-readbacks", action="store_true")
    parser.add_argument("--cli", default="easyeda")
    parser.add_argument("--communication-retries", type=int, choices=(0, 1, 2), default=0)
    args = parser.parse_args()
    manifest = json.loads((PRIOR / "board_pages.json").read_bytes())
    if (args.project == manifest["project_id"] or not args.expected_name.startswith("EVT1-H02-ERC-")):
        parser.error("capture only the new EVT1-H02-ERC candidate; never save the retained baseline project")
    manifest.update(project_id=args.project, project_name=args.expected_name)
    probe = Capture(args.output, args.cli, args.project, args.communication_retries)
    if args.resume_readbacks:
        previous = json.loads((args.output / "board_pages.json").read_bytes())
        if previous != manifest:
            parser.error("resume output manifest describes a different candidate")
        probe.ledger = json.loads((args.output / "command-ledger.json").read_bytes())
        if any(".retry" in item["path"] for item in probe.ledger):
            parser.error("resume with an exhausted communication budget must be handled from the raw captures")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / "board_pages.json", manifest)
    try:
        label = "resume-project-info.json" if args.resume_readbacks else "project-info.json"
        info = probe.run(label, ["project", "info"])
        context = info.get("context", {})
        if (context.get("projectUuid"), context.get("projectName")) != (args.project, args.expected_name):
            raise ValueError("new candidate name/UUID must match the host")
        if not args.resume_readbacks:
            capture_boards(probe, manifest)
        capture_archive_and_pages(probe, manifest, args.archive, args.window)
    except (ValueError, KeyError, RuntimeError, OSError) as error:
        write_json(args.output / "capture-state.json", {"status": "BLOCKED", "error": str(error)})
        print(f"BLOCKED: {error}")
        return 2
    write_json(args.output / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
