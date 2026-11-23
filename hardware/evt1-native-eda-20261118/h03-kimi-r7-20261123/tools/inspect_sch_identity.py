#!/usr/bin/env python3
"""Read-only diagnostic for controlled identities in the current native archive."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

R7 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R7.parent / "h03-codex-r4-20261123/u11")]
from audit_r3_u11 import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_references", nargs="+")
    args = parser.parse_args()
    catalog = json.loads((R7.parent / "h02-native/catalog-plan.json").read_bytes())["records"]
    wanted = {row["sourceReference"]: row for row in catalog if row["sourceReference"] in args.source_references}
    native = load(R7 / "native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2")
    report = {}
    for name, row in wanted.items():
        candidates = []
        for key, page in native.documents.items():
            if key[0] != "SCH_PAGE":
                continue
            attrs = defaultdict(dict)
            for record in page:
                if record.header["type"] == "ATTR":
                    payload = record.payload
                    attrs[payload["parentId"]][payload.get("key")] = payload.get("value")
            for primitive, fields in attrs.items():
                if (fields.get("Unique ID") == row["captureUniqueId"]
                        or fields.get("EVT1 Source Ref") == name
                        or fields.get("BOM Line") == row["bomLine"]):
                    candidates.append({"page": key[1], "primitiveId": primitive,
                                       "attrs": {k: fields.get(k) for k in
                                                 ("Designator", "Unique ID", "EVT1 Source Ref", "BOM Line", "Symbol")}})
        report[name] = {"catalog": {k: row[k] for k in
                                    ("board", "cadReference", "capturePage", "capturePrimitiveId", "captureUniqueId", "bomLine")},
                        "candidates": candidates}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
