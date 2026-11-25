#!/usr/bin/env python3
"""Preserve native DRC evidence and attribute trial-related violations by ID."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(violation: dict) -> tuple:
    return (violation.get("rule"), violation.get("objType"),
            tuple(sorted(violation.get("objs") or [])), violation.get("layer"),
            violation.get("message"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--trial-ids", required=True,
                        help="JSON array of primitive IDs introduced by this candidate")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    baseline = read_json(args.baseline)
    candidate = read_json(args.candidate)
    trial_ids = set(json.loads(args.trial_ids))
    baseline_keys = Counter(key(v) for v in baseline["violations"])
    candidate_keys = Counter(key(v) for v in candidate["violations"])
    introduced_counts = candidate_keys - baseline_keys
    removed_counts = baseline_keys - candidate_keys
    introduced, removed = [], []
    for violation in candidate["violations"]:
        k = key(violation)
        if introduced_counts[k] > 0:
            introduced.append(violation)
            introduced_counts[k] -= 1
    for violation in baseline["violations"]:
        k = key(violation)
        if removed_counts[k] > 0:
            removed.append(violation)
            removed_counts[k] -= 1
    trial = [v for v in candidate["violations"] if trial_ids.intersection(v.get("objs") or [])]
    by_via = {}
    for via_id in sorted(trial_ids):
        violations = [v for v in trial if via_id in (v.get("objs") or [])]
        by_via[via_id] = {
            "count": len(violations),
            "byObjectPair": dict(sorted(Counter(v["objType"] for v in violations).items())),
            "byLayer": dict(sorted(Counter(v.get("layer") or "unspecified" for v in violations).items())),
            "violations": violations,
        }
    output = {
        "schemaVersion": 1,
        "source": {
            "baseline": str(args.baseline.resolve()),
            "baselineSha256": digest(args.baseline),
            "candidate": str(args.candidate.resolve()),
            "candidateSha256": digest(args.candidate),
        },
        "baseline": {"passed": baseline.get("passed"), "counts": baseline.get("counts")},
        "candidate": {"passed": candidate.get("passed"), "counts": candidate.get("counts")},
        "comparisonMethod": "Multiset difference of native normalized rule/object-pair/objects/layer/message; not a globalIndex comparison.",
        "introducedCount": len(introduced),
        "removedCount": len(removed),
        "introducedByRule": dict(sorted(Counter(v["rule"] for v in introduced).items())),
        "removedByRule": dict(sorted(Counter(v["rule"] for v in removed).items())),
        "introduced": introduced,
        "removed": removed,
        "trial": {
            "primitiveIds": sorted(trial_ids),
            "status": "candidate-rejected" if trial else "requires-review",
            "violationsTouchingTrial": len(trial),
            "byObjectPair": dict(sorted(Counter(v["objType"] for v in trial).items())),
            "byLayer": dict(sorted(Counter(v.get("layer") or "unspecified" for v in trial).items())),
            "byVia": by_via,
        },
        "limitations": [
            "Native DRC only; does not prove manufacturer capability, impedance or hardware performance.",
            "Trial IDs identify candidate copper, not authorization to merge it into the integrated project.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in (
        "baseline", "candidate", "introducedCount", "removedCount", "introducedByRule",
        "removedByRule", "trial") if k != "trial"}, ensure_ascii=False, indent=2))
    print(json.dumps({"trial": {k: v for k, v in output["trial"].items() if k != "byVia"}},
                     ensure_ascii=False, indent=2))
    return 1 if trial else 0


if __name__ == "__main__":
    raise SystemExit(main())
