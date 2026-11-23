#!/usr/bin/env python3
"""Reuse the inherited PCB2 geometry screen on fresh R7 native evidence.

Only screening is offline. Candidate geometry requires isolated typed native writes,
save/reload, strict DRC and endpoint connectivity before integration.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

R7 = Path(__file__).resolve().parents[1]
PACKAGE = R7.parent
SOURCE = PACKAGE / "h03-codex-r6-20261123/pcb2/plan_pcb2_r6.py"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("dump", type=Path)
    parser.add_argument("drc", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("r7_pcb2_inherited_screen", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load inherited PCB2 screen")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SIGNAL_WIDTH = 4.0
    module.RAIL_WIDTH = 4.0
    sys.argv = [str(SOURCE), str(PACKAGE), str(args.archive), str(args.dump), str(args.drc), str(args.out)]
    module.main()


if __name__ == "__main__":
    main()
