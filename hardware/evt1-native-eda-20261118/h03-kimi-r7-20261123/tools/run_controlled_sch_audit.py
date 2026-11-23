#!/usr/bin/env python3
"""Compare final and independent native controlled schematic identity audits."""
import json
from pathlib import Path
import sys

R7 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R7.parent / "h03-codex-r4-20261123/u11"), str(R7 / "tools")]
from audit_r3_u11 import load
from controlled_sch_audit import controlled_terminal_audit


def main():
    catalog = json.loads((R7.parent / "h02-native/catalog-plan.json").read_bytes())["records"]
    paths = {
        "integrated": R7 / "native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2",
        "independent": R7 / "verification/independent/EVT1-H03-KIMI-R7-REEXPORT-NOT-FOR-FAB.epro2",
        "r7Baseline": R7 / "baseline/EVT1-H03-KIMI-R7-INTEGRATED-BASELINE-NOT-FOR-FAB.epro2",
    }
    result = {name: controlled_terminal_audit(load(path), catalog, strict=False)
              for name, path in paths.items()}
    output = R7 / "verification/controlled-sch-audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in report.items()
                             if key not in {"resolvedIdentities", "terminalDifference", "ncDifference"}}
                      for name, report in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
