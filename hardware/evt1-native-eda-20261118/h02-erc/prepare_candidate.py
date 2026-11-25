#!/usr/bin/env python3
"""Build the isolated H02 ERC candidate from the pinned PR #34 editor archive."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from bind_kingbright_d3 import bind_d3, validate_d3_postimage
from bind_murata_l2 import Archive, BASELINE, BASELINE_SHA, bind_l2, digest, validate_postimage
from repair_supply_wire_names import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists() or args.report.resolve() == args.output.resolve():
        parser.error("archive and report must be separate new paths")
    if digest(BASELINE) != BASELINE_SHA:
        raise ValueError("The PR #34 editor archive hash differs from the pinned baseline")

    archive = Archive(BASELINE)
    binding = bind_l2(archive)
    with TemporaryDirectory() as folder:
        l2_archive = Path(folder) / "l2.epro2"
        d3_archive = Path(folder) / "l2-d3.epro2"
        archive.write(l2_archive)
        validate_postimage(Archive(BASELINE), Archive(l2_archive))
        d3_binding = bind_d3(archive)
        archive.write(d3_archive)
        validate_d3_postimage(Archive(l2_archive), Archive(d3_archive))
    wires, proxies = prepare(archive)
    archive.write(args.output)
    if digest(BASELINE) != BASELINE_SHA or Archive(args.output).encode() != archive.encode():
        raise ValueError("Combined candidate failed the archive round trip")
    report = {
        "status": "OFFLINE_VERIFIED",
        "manufacturing": "BLOCKED",
        "baseline_sha256": BASELINE_SHA,
        "candidate_sha256": digest(args.output),
        "wire_net_attribute_edits": wires,
        "hierarchy_proxies": proxies,
        "footprint_binding": binding,
        "additional_footprint_bindings": [d3_binding],
    }
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
