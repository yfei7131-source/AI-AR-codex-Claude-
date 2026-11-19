#!/usr/bin/env python3
"""Capture a newly imported H02 candidate via the typed EasyEDA connector."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "closure/evidence/jlc-import/board_pages.json"
COMMUNICATION_MARKERS = ("dispatch_failed", "did not respond", "deadline exceeded", "connection refused",
                         "connector unavailable", "timed out", "timeout", "connection reset")


class Capture:
    def __init__(self, folder, cli, project, retries):
        self.folder = folder
        self.cli = cli
        self.project = project
        self.ledger = []
        self.retries_left = retries

    def run(self, path, args, *, allow_rule_failure=False, mutates=False, window=None):
        route = ["--project", self.project] if window is None else ["--window", window]
        command = [self.cli, *route, *args]
        target = self.folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        attempt = 1
        while True:
            try:
                proc = subprocess.run(command, capture_output=True, timeout=100)
                stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, code = exc.stdout or b"", exc.stderr or b"command timed out", 124
            try:
                data = json.loads(stdout)
            except (UnicodeError, ValueError):
                data = None
            accepted = (isinstance(data, dict) and data.get("ok", True) is True
                        and (code == 0 or (allow_rule_failure and data.get("ok") is True)))
            output = target if accepted else self.folder / "failures" / path
            if not accepted and attempt > 1:
                output = output.with_suffix(f".retry{attempt - 1}.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(stdout)
            output.with_suffix(".stderr.log").write_bytes(stderr)
            self.ledger.append({"path": str(output.relative_to(self.folder).as_posix()),
                                "command": command, "exit_code": code})
            self.log()
            if accepted:
                return data
            message = (stdout + stderr).decode("utf-8", errors="replace").lower()
            failed_link = code == 124 or any(mark in message for mark in COMMUNICATION_MARKERS)
            if failed_link and self.retries_left and not mutates:
                self.retries_left -= 1
                attempt += 1
                continue
            raise RuntimeError(f"{path}: exit {code}; communication_failure={failed_link}. See raw capture.")

    def log(self):
        write_json(self.folder / "command-ledger.json", self.ledger)

    def artifact(self, response, board, kind):
        item = response.get("result", {})
        source = Path(item.get("artifactPath", ""))
        if not source.is_file():
            raise ValueError(f"{board}: native {kind} export lacks a readable artifact file")
        name = f"board-netlists/{board}.net" if kind == "netlist" else f"board-boms/{board}.csv"
        shutil.copyfile(source, self.folder / name)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def root_map(manifest, boards, pages):
    expected_names = {"M-MAIN-L": "evt1-main-left", "M-OPT-BRIDGE": "evt1-optical-bridge", "M-AUD-R": "evt1-audio-right"}
    by_name = {row["name"]: row for row in boards["result"]["boards"]}
    by_page = {row["uuid"]: row for row in pages["result"]["pages"]}
    roots = {}
    for board, name in expected_names.items():
        row = by_name[name]
        contained = manifest["boards"][board]
        roots[board], = [uuid for uuid in contained if by_page[uuid]["name"] == name]
        if not row["pcbUuid"] or any(by_page[uuid]["parentSchematicUuid"] != row["schematicUuid"] for uuid in contained):
            raise ValueError(f"{board}: imported root/page/PCB grouping failed")
    if len(by_name) != 3 or len(by_page) != 21:
        raise ValueError("candidate board and page count must be 3 / 21")
    return roots


def capture_run(probe, manifest, page_reads, export_bom):
    boards = probe.run("lceda-boards.json", ["board", "list"])
    pages = probe.run("lceda-pages.json", ["sch", "pages"])
    probe.run("lceda-pcbs.json", ["pcb", "docs"])
    for result in (boards, pages):
        if result.get("context", {}).get("projectUuid") != probe.project:
            raise ValueError("candidate project identity mismatched")
    roots = root_map(manifest, boards, pages)
    for board, root in roots.items():
        save = probe.run(f"save/{board}.json", ["--doc", root, "sch", "save"], mutates=True)
        if save.get("result", {}).get("saved") is not True:
            raise ValueError(f"candidate save unconfirmed: {board}")
        probe.run(f"reload/{board}.json", ["doc", "reload", root, "--json"], mutates=True)
        probe.run(f"root/{board}.json", ["doc", "switch", root, "--json"])
        response = probe.run(f"board-netlists/{board}.response.json", ["sch", "netlist", "--type", "Protel2"])
        if response.get("context", {}).get("documentUuid") != root:
            raise ValueError(f"candidate netlist scope unconfirmed: {board}")
        probe.artifact(response, board, "netlist")
        probe.run(f"erc/{root}.json", ["sch", "drc", "--json", "--strict"], allow_rule_failure=True)
        if export_bom:
            response = probe.run(f"board-boms/{board}.response.json", ["bom", "export", "--type", "csv", "--enrich=false"])
            if response.get("context", {}).get("documentUuid") != root:
                raise ValueError(f"candidate BOM scope unconfirmed: {board}")
            probe.artifact(response, board, "bom")
    if page_reads:
        for board, ids in manifest["boards"].items():
            for page in ids:
                data = probe.run(f"sch/{page}.json", ["sch", "connectivity", "--page", page])
                if data.get("projectId") != probe.project or data.get("documentId") != page:
                    raise ValueError(f"incorrect connectivity scope: {page}")
                pins = probe.run(f"pins/{page}.json", ["sch", "list", "--page", page, "--stay", "--include-pins"])
                if (pins.get("context", {}).get("projectUuid"), pins.get("context", {}).get("documentUuid")) != (probe.project, page):
                    raise ValueError(f"incorrect pin marker scope: {page}")
                if page != roots[board]:
                    probe.run(f"erc/{page}.json", ["sch", "drc", "--json", "--strict"], allow_rule_failure=True)
                print(f"Captured {board}/{page}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-project", required=True, help="exact UUID of a NEW imported candidate")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cli", default="easyeda")
    parser.add_argument("--board-only", action="store_true")
    parser.add_argument("--skip-bom", action="store_true", help="avoid a known export timeout; preserve BOM BLOCKED")
    parser.add_argument("--communication-retries", type=int, choices=(0, 1, 2), default=2)
    args = parser.parse_args()
    manifest = json.loads(SOURCE.read_bytes())
    protected = {manifest["project_id"], "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"}
    if args.candidate_project in protected:
        parser.error("the original and KIMI project must remain read-only")
    args.output.mkdir(parents=True, exist_ok=False)
    manifest["project_id"] = args.candidate_project
    write_json(args.output / "board_pages.json", manifest)
    probe = Capture(args.output, args.cli, args.candidate_project, args.communication_retries)
    try:
        capture_run(probe, manifest, not args.board_only, not args.skip_bom)
    except (ValueError, KeyError, RuntimeError, OSError) as error:
        write_json(args.output / "capture-state.json", {"status": "BLOCKED", "error": str(error), "manufacturing": "BLOCKED"})
        print(f"BLOCKED: {error}")
        return 2
    write_json(args.output / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
