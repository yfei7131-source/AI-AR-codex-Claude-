#!/usr/bin/env python3
"""Compare native EasyEDA archives without modifying either archive."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def load(path: Path):
    documents = {}
    with ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".epru")]
        if len(members) != 1:
            raise ValueError(f"Expected one .epru in {path}")
        for raw_line in archive.read(members[0]).splitlines():
            header_raw, payload_raw = raw_line.split(b"||", 1)
            header = json.loads(header_raw)
            payload = None if payload_raw == b"|" else json.loads(payload_raw.removesuffix(b"|"))
            if header["type"] == "DOCHEAD":
                key = (payload["docType"], payload["uuid"])
                if key in documents:
                    raise ValueError(f"Duplicate document {key}")
                documents[key] = {}
                active = key
            elif header["type"] != "PRIMITIVE" or payload is not None:
                documents[active][(header["type"], header.get("id"))] = payload
    return documents


def key_text(key):
    return [key[0], key[1]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--document", required=True, help="Target document UUID")
    parser.add_argument("--out", required=True, type=Path)
    ns = parser.parse_args()
    before = load(ns.baseline)
    after = load(ns.candidate)
    if before.keys() != after.keys():
        raise ValueError("Document inventory differs")
    summaries = {}
    for key in before:
        left, right = before[key], after[key]
        kinds = Counter()
        for record_key in left.keys() | right.keys():
            if record_key not in left:
                kinds[f"added:{record_key[0]}"] += 1
            elif record_key not in right:
                kinds[f"removed:{record_key[0]}"] += 1
            elif left[record_key] != right[record_key]:
                kinds[f"changed:{record_key[0]}"] += 1
        if kinds:
            summaries[":".join(key)] = dict(sorted(kinds.items()))
    target_key = next((key for key in before if key[1] == ns.document), None)
    if target_key is None:
        raise ValueError(f"Unknown document UUID: {ns.document}")
    left, right = before[target_key], after[target_key]
    added = {json.dumps(key_text(k), ensure_ascii=False): right[k] for k in sorted(right.keys() - left.keys())}
    removed = {json.dumps(key_text(k), ensure_ascii=False): left[k] for k in sorted(left.keys() - right.keys())}
    changed = {
        json.dumps(key_text(k), ensure_ascii=False): {"before": left[k], "after": right[k]}
        for k in sorted(left.keys() & right.keys()) if left[k] != right[k]
    }
    rule_key = ("RULE", '["RULE","BLIND","blindVia"]')
    rules = right.get(rule_key, {}).get("ruleContext", {}).get("blinds", {}).get("content", [])
    report = {
        "baseline": str(ns.baseline.resolve()),
        "candidate": str(ns.candidate.resolve()),
        "baselineSha256": hashlib.sha256(ns.baseline.read_bytes()).hexdigest(),
        "candidateSha256": hashlib.sha256(ns.candidate.read_bytes()).hexdigest(),
        "document": ns.document,
        "allDocumentDeltaCounts": summaries,
        "added": added,
        "removed": removed,
        "changed": changed,
        "blindViaRules": rules,
        "status": "archive-read-only-diff",
    }
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(ns.out), "allDocumentDeltaCounts": summaries,
                      "addedVias": [v for k, v in added.items() if json.loads(k)[0] == "VIA"],
                      "blindViaRules": rules}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
