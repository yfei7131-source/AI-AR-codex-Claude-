#!/usr/bin/env python3
"""Read-only comparison of native archive primitives and a live PCB copper capture."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

R7 = Path(__file__).resolve().parents[1]
PACKAGE = R7.parent
sys.path.insert(0, str(PACKAGE / "h03-codex-r4-20261123/u11"))
from audit_r3_u11 import load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--document", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    dump = json.loads(args.dump.read_text(encoding="utf-8"))
    records = load(args.archive).documents["PCB", args.document]
    archived = {row.header["id"]: row.payload for row in records if row.header["type"] == "LINE"}
    live = {row["primitiveId"]: row for row in dump.get("copper", {}).get("lines", [])}
    missing = sorted(archived.keys() - live.keys())
    extra = sorted(live.keys() - archived.keys())
    result = {
        "archive": str(args.archive.resolve()),
        "dump": str(args.dump.resolve()),
        "document": args.document,
        "capture": dump.get("capture"),
        "availability": dump.get("availability"),
        "copperAvailability": dump.get("copper", {}).get("availability"),
        "archiveLineCount": len(archived),
        "liveLineCount": len(live),
        "missingFromLive": [{"id": key, **archived[key]} for key in missing],
        "absentFromArchive": [{"id": key, **live[key]} for key in extra],
        "missingLayerCounts": dict(Counter(archived[key].get("layerId") for key in missing)),
        "liveLayerCounts": dict(Counter(row.get("layer") for row in live.values())),
        "archiveLayerCounts": dict(Counter(row.get("layerId") for row in archived.values())),
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"capture", "missingFromLive", "absentFromArchive"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
