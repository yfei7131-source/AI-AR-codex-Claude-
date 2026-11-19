#!/usr/bin/env python3
"""Build a controlled H02 field-repair plan from PR31 evidence only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "hardware/evt1-native-eda-20261118"
EVIDENCE = BASE / "closure/evidence/jlc-import"
OUT = BASE / "kimi-h02-return/repair-plan.json"
SPEC = importlib.util.spec_from_file_location("verify_eda_return", BASE / "closure/verify_eda_return.py")
VERIFY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(VERIFY)


def need_mpn(part):
    return part["pcb_use"] == "BOARD" and part["mpn"] and "TBD" not in part["mpn"].upper()


def main():
    _, parts = VERIFY.baseline(BASE)
    manifest = json.loads((EVIDENCE / "board_pages.json").read_text(encoding="utf-8"))
    page_maps = {}
    locations = {}
    for board, pages in manifest["boards"].items():
        for page in pages:
            raw = json.loads((EVIDENCE / "pins" / f"{page}.json").read_text(encoding="utf-8"))
            page_maps[page] = raw
            for component in raw["result"]["components"]:
                ref = component.get("designator")
                if not ref or component.get("componentType") != "part":
                    continue
                key = (board, ref)
                if key in locations:
                    raise ValueError(f"duplicate native part location: {key}")
                locations[key] = (page, component)
    missing = sorted(set(parts) - set(locations))
    if missing:
        raise ValueError(f"controlled parts missing native locations: {missing}")
    records = []
    for (board, ref), part in sorted(parts.items()):
        page, component = locations[(board, ref)]
        other = component.get("otherProperty") or {}
        expected_mpn = part["mpn"] if need_mpn(part) else ""
        if expected_mpn and other.get("MPN") != expected_mpn:
            raise ValueError(f"custom MPN does not match controlled BOM at {(board, ref)}")
        records.append({
            "board": board,
            "cadReference": ref,
            "sourceReference": part["source_ref"],
            "pageUuid": page,
            "primitiveId": component["primitiveId"],
            "uniqueId": component.get("uniqueId"),
            "current": {
                "manufacturerId": component.get("manufacturerId"),
                "manufacturer": component.get("manufacturer"),
                "supplier": component.get("supplier"),
                "supplierId": component.get("supplierId"),
                "otherProperty": other,
                "addIntoPcb": component.get("addIntoPcb"),
                "footprint": component.get("footprint"),
            },
            "controlled": {
                "mpn": expected_mpn,
                "footprint": part["footprint"],
                "pcbUse": part["pcb_use"],
                "addIntoPcb": part["pcb_use"] == "BOARD",
            },
            "proposedMpnPatch": {"manufacturerId": expected_mpn} if expected_mpn else None,
            "mpnWriteAuthorized": False,
            "footprintWriteAuthorized": False,
            "footprintBlockReason": "Requires an exact real native footprint association and pad audit; a custom text field is not accepted." if part["footprint"] else "",
        })
    report = {
        "status": "PLAN_ONLY_NOT_APPLIED",
        "sourceBaseline": "PR31/8d0609d71529698c1cfe5d984d25dbc2bdca98b8",
        "projectUuid": manifest["project_id"],
        "components": len(records),
        "controlledMpnRequired": sum(bool(r["controlled"]["mpn"]) for r in records),
        "controlledFootprintRequired": sum(bool(r["controlled"]["footprint"]) for r in records),
        "externalPcbFlagRepairsRequired": sum(r["current"]["addIntoPcb"] != r["controlled"]["addIntoPcb"] for r in records),
        "records": records,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
