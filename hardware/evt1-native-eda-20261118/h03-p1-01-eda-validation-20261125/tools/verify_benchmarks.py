"""Verify a controlled gap and typed restoration from unchanged native evidence."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json

import batch_gate as gate

native = gate.native
BENCHMARKS = {
    "ground-dogbone": {
        "board": "PCB3", "final": "typed-ground-restoration",
        "old": (("LINE", "1cf40bd16e827fe5"), ("LINE", "4196f39ae665d6a3"), ("VIA", "c32ffe36b61f0ea9")),
        "drc": "restored-drc",
    },
    "signal-link": {
        "board": "PCB1", "final": "repaired",
        "old": (("LINE", "5c1daaeb6eb16d7b"),),
        "drc": "repaired-drc",
    },
}


def canonical(row):
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_export(folder, stem, project):
    path = folder / f"{stem}.epro2"
    response = native.read(folder / f"{stem}-export.json")
    gate.require(response.get("ok") is True and response["result"]["uuid"] == project
                 and response["result"]["sha256"] == native.digest(path), f"{stem}: invalid native export receipt")
    return path, native.archive(path)


def placeholders(rows, expected):
    counts = Counter()
    for (kind, uid), row in rows.items():
        if kind in ("LINE", "VIA"):
            continue
        gate.require(kind == "ELE_PLACEHOLDER" and uid.startswith("placeholder") and uid[11:].isdigit()
                     and set(row) == {"dataType", "max"} and row["dataType"] in ("LINE", "VIA")
                     and type(row["max"]) is int and row["max"] > 0,
                     f"Unexpected native archive metadata {kind}/{uid}")
        counts[row["dataType"]] += row["max"]
    gate.require(all(expected[typ] == count for typ, count in counts.items()),
                 "Native placeholder count does not match the controlled copper additions/removals")
    return dict(counts)


def benchmark(source, folder, baseline, scene):
    plan = BENCHMARKS[scene]
    doc = ("PCB", native.PCB_IDS[plan["board"]])
    target = native.archive(source)[doc]
    reference = plan["old"][0]
    stem = plan["final"]
    rr = native.read(folder / f"{stem}-reload.json")
    project = rr["finalContext"]["projectUuid"]
    gate.require(rr["finalContext"]["projectName"].startswith("P1-ISOLATED-"),
                 "Target project is outside the approved bench")
    gate.load_reload(folder / f"{stem}-reload.json", plan["board"], project)
    cut_path, cut = read_export(folder, "cut", project)
    auto_path, auto = read_export(folder, "auto-result", project)
    post_path, post = read_export(folder, stem, project)
    gate.require(cut.keys() == auto.keys() == post.keys(), "PCB documents changed")
    gate.require(auto == cut, "Automatic experiment modified the trial beyond the intentionally cut gap")
    if scene == "signal-link":
        _, configured = read_export(folder, "rules", project)
        before_cut = configured[doc]
        gate.require(before_cut[reference] == target[reference], "Bench gap does not use the intended R11 trace")
        gate.require(all(row == configured[doc][key] for key, row in target.items()
                         if key[0] in {"RULE", "LINE", "VIA", "PAD_NET", "LAYER", "LAYER_PHYS", "LAYER_FILL", "REGION"}),
                     "The bench changed inherited rule/copper records")
        gate.require(all(cut[k] == configured[k] for k in cut if k != doc), "Rule-to-cut boundary changed an unrelated document")
    else:
        before_cut = target
    old = set(plan["old"])
    gate.require(set(before_cut) - set(cut[doc]) == old and all(cut[doc][k] == row for k, row in before_cut.items() if k not in old),
                 "Controlled removal must match exactly the selected primitives")
    removed_types = Counter(kind for kind, _ in old)
    cut_metadata = {k: row for k, row in cut[doc].items() if k not in before_cut}
    gate.require(all(kind == "ELE_PLACEHOLDER" for kind, _ in cut_metadata), "Gap opening inserted new non-metadata objects")
    cut_counts = placeholders(cut_metadata, removed_types)
    actual = {k: row for k, row in post[doc].items() if k not in cut[doc]}
    expect_payload = Counter((kind, canonical(target[kind, uid])) for kind, uid in old)
    obs_payload = Counter((kind, canonical(row)) for (kind, _), row in actual.items() if kind in ("LINE", "VIA"))
    gate.require(obs_payload == expect_payload, "Restored line/via full payload differs from R11")
    old_ids = {uid for _, uid in old}
    new_ids = {uid for (kind, uid) in actual if kind in ("LINE", "VIA")}
    gate.require(old_ids.isdisjoint(new_ids), "New writes must be attested by new primitive IDs")
    gate.require(all(post[k] == cut[k] for k in post if k != doc) and all(post[doc].get(k) == row for k, row in cut[doc].items()),
                 "Unrelated native records changed")
    meta = placeholders(actual, removed_types)
    if scene == "ground-dogbone":
        via = next(row for (kind, _), row in actual.items() if kind == "VIA")
        gate.require(gate.blind_span(post[doc], via["ruleName"]) == {1, 15}
                     and gate.plane_containment(post[doc], 15, "GND", (via["centerX"], via["centerY"]), via["viaDiameter"]/2),
                     "Restored blind via does not touch intended native reference plane")
        created = {native.read(folder / f"ground-line-{i}.json")["result"]["primitiveId"] for i in (1, 2)}
        created.add(native.read(folder / "create-blind-via.json")["value"]["id"])
    else:
        created = {native.read(folder / "typed-restoration.json")["result"]["primitiveId"]}
    gate.require(created == new_ids, "Native write receipts differ from archive delta")
    restored_drc = folder / f"{plan['drc']}.json"
    gate.require(gate.project_metadata(cut_path) == gate.project_metadata(auto_path) == gate.project_metadata(post_path),
                 "Bench archive project metadata changed")
    prior_drc = native.read(baseline / f"{plan['board']}-drc.json")
    auto_drc = native.read(folder / "auto-drc.json")
    cut_drc = native.read(folder / "cut-drc.json")
    gate.require(gate.signatures(auto_drc) == gate.signatures(cut_drc)
                 and cut_drc["counts"].get("Connection Error", 0) > prior_drc["counts"].get("Connection Error", 0),
                 "Controlled gap and no-op native DRC receipts do not reproduce")
    if restored_drc.is_file():
        verified = gate.signatures(native.read(restored_drc)) == gate.signatures(prior_drc)
        gate.require(verified, "Restored DRC does not reproduce original native objects")
    else:
        verified = False
    return {"board": plan["board"], "scene": scene, "project": project, "strictDRCVerified": verified,
            "status": "native-geometry-and-drc-verified" if verified else "native-geometry-verified-drc-not-run",
            "automaticCopperDelta": 0, "cutHash": native.digest(cut_path), "automaticHash": native.digest(auto_path),
            "restoredHash": native.digest(post_path), "restoredPrimitiveIds": sorted(new_ids),
            "nativePlaceholderCounts": meta, "cutPlaceholderCounts": cut_counts, "knownBaselineCounts": prior_drc["counts"],
            "controlledGapCounts": cut_drc["counts"], "automaticCounts": auto_drc["counts"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("source", "logs", "baseline", "out"):
        p.add_argument(f"--{flag}", type=Path, required=True)
    p.add_argument("--scene", choices=tuple(BENCHMARKS), required=True)
    a = p.parse_args()
    gate.require(not a.out.exists(), "Output exists")
    report = benchmark(a.source, a.logs, a.baseline, a.scene)
    native.write(a.out, report)
    print(report["status"], report["board"], report["nativePlaceholderCounts"])


if __name__ == "__main__":
    main()
