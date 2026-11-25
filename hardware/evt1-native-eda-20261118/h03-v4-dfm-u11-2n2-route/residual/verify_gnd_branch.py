#!/usr/bin/env python3
"""Plan and verify removal of one redundant PCB3 GND branch from scoped readbacks."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE / "h03-dfm-p0-closure"))
from independent_hdi_dfm_auditor import DOCS, pt_seg_dist, seg_seg_dist


RETAINED = {
    "7a5a454f3904462c": ((62.6, 260.8), (60, 276)),
    "3a126422406fbe38": ((60, 276), (60, 294)),
    "49a8b31b25f672b4": ((60, 294), (61, 300.2)),
}
REDUNDANT = {
    "2d02a47206d7014f": ((61, 300.2), (63, 292.5)),
    "248452904b1b15c9": ((63, 292.5), (61.5, 291)),
    "745f87472f6e79c1": ((61.5, 291), (61.5, 282)),
    "d1d29279e63eabbc": ((61.5, 282), (63, 280.5)),
    "e46b6c305882ff2f": ((63, 280.5), (63, 276)),
    "c5a4ee5b7638fa61": ((63, 276), (62.6, 260.8)),
}
ENDPOINTS = {
    "72ed1be1d38eee9fre5p110": ("C5", "2", (62.6, 260.8)),
    "fb9a90e154948529nrfp130": ("U11", "C2", (61, 300.2)),
}
EXISTING_TAPS = {
    "4ee2561071bbf4b1": ((54, 302), (61, 300.2)),
    "03c55d4281f45505": ((62.6, 260.8), (73.5, 246)),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def coordinates(line):
    return tuple(tuple(round(line[f"{end}{axis}"], 4) for axis in ("X", "Y")) for end in ("start", "end"))


def by_id(items):
    keyed = {item["primitiveId"]: item for item in items}
    if len(keyed) != len(items):
        raise ValueError("duplicate primitive ID in the live readback")
    return keyed


def scoped_dump(path, project):
    dump = read(path)
    capture = dump["capture"]
    if (capture["projectUuid"], capture["documentUuid"], capture["documentType"], capture["identityVerified"]) != (
        project, DOCS["PCB3"], "pcb", True
    ):
        raise ValueError("PCB3 readback is not bound to the requested isolated project")
    return dump


def guard_plan(dump):
    copper = dump["copper"]
    if not copper["arcsAvailable"] or any(copper[k] for k in ("arcs", "fills", "pours", "poured")):
        raise ValueError("unexpected copper geometry class or incomplete arc readback on PCB3")
    if any(copper["availability"].get(k) != "available" for k in ("routing", "vias", "regions", "fills")):
        raise ValueError("incomplete PCB3 copper readback")
    lines = by_id(copper["lines"])
    for identifier, expected in (RETAINED | REDUNDANT | EXISTING_TAPS).items():
        actual = lines.get(identifier)
        if not actual or (actual["layer"], actual["net"], actual["lineWidth"], actual["locked"]) != (1, "GND", 3, False):
            raise ValueError(f"stale or unexpected PCB3 GND line {identifier}")
        if coordinates(actual) != expected:
            raise ValueError(f"PCB3 GND path geometry changed: {identifier}")

    for board_component in dump["components"]:
        for pad in board_component["pads"]:
            if pad["primitiveId"] in ENDPOINTS:
                ref, pin, xy = ENDPOINTS[pad["primitiveId"]]
                if (board_component["designator"], pad["padNumber"], (pad["x"], pad["y"]), pad["layer"], pad["net"]) != (
                    ref, pin, xy, 1, "GND"
                ):
                    raise ValueError(f"GND endpoint identity changed: {ref}.{pin}")
            elif pad["layer"] == 1 and pad["net"] == "GND":
                radius = hypot(pad["width"], pad["height"]) / 2 + 1.5
                if any(pt_seg_dist(pad["x"], pad["y"], *a, *b) <= radius for a, b in REDUNDANT.values()):
                    raise ValueError(f"third-party GND pad may touch branch: {pad['primitiveId']}")
    all_pads = {pad["primitiveId"] for c in dump["components"] for pad in c["pads"]}
    if ENDPOINTS.keys() - all_pads:
        raise ValueError("GND endpoint missing from current readback")

    for via in copper["vias"]:
        if via["net"] == "GND" and any(
            pt_seg_dist(via["x"], via["y"], *a, *b) <= via["diameter"] / 2 + 1.5
            for a, b in REDUNDANT.values()
        ):
            raise ValueError(f"GND via may touch redundant branch: {via['primitiveId']}")
    for identifier in lines.keys() - RETAINED.keys() - REDUNDANT.keys() - EXISTING_TAPS.keys():
        other = lines[identifier]
        if other["layer"] == 1 and other["net"] == "GND" and any(
            seg_seg_dist(*a, *b, *coordinates(other)[0], *coordinates(other)[1]) <= (other["lineWidth"] + 3) / 2
            for a, b in REDUNDANT.values()
        ):
            raise ValueError(f"additional GND track may touch redundant branch: {identifier}")


def drc_profile(path):
    result = read(path)
    if result["binding"]["pcbUuid"] != DOCS["PCB3"] or result["total"] != len(result["violations"]):
        raise ValueError("incomplete DRC or DRC from another PCB")
    totals = Counter(row["rule"] for row in result["violations"])
    if totals != result["counts"]:
        raise ValueError("DRC category and finding count mismatch")
    return totals, Counter((row["rule"], row.get("net", "")) for row in result["violations"])


def guard_postimage(before, after, drc_before, drc_after, dfm_after):
    left, right = (by_id(dump["copper"]["lines"]) for dump in (before, after))
    if left.keys() - right.keys() != REDUNDANT.keys() or right.keys() - left.keys():
        raise ValueError("native line difference is not exactly the six planned removals")
    if any(left[key] != item for key, item in right.items()):
        raise ValueError("a retained line has changed")
    for key in before["copper"].keys() - {"lines"}:
        if before["copper"][key] != after["copper"][key]:
            raise ValueError(f"PCB copper readback changed outside the deletion: {key}")
    for key in ("components", "outline", "copperLayers", "rules", "silk"):
        if before[key] != after[key]:
            raise ValueError(f"PCB readback changed outside copper: {key}")
    if drc_profile(drc_before) != drc_profile(drc_after):
        raise ValueError("strict DRC counts changed by rule or net")
    if read(dfm_after)["summary"]["duplicateSegments"] != 0:
        raise ValueError("PCB3 duplicate line warning persisted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--drc-before", type=Path)
    parser.add_argument("--drc-after", type=Path)
    parser.add_argument("--dfm-after", type=Path)
    args = parser.parse_args()
    if any((args.after, args.drc_before, args.drc_after, args.dfm_after)) and not all(
        (args.after, args.drc_before, args.drc_after, args.dfm_after)
    ):
        parser.error("verification requires --after, --drc-before, --drc-after and --dfm-after")
    before = scoped_dump(args.before, args.project)
    guard_plan(before)
    report = {"status": "PLAN_VERIFIED", "projectUuid": args.project, "pcbUuid": DOCS["PCB3"],
              "beforeSha256": sha256(args.before.read_bytes()).hexdigest(),
              "endpoints": ENDPOINTS, "deleteGndLines": REDUNDANT, "preserveGndLines": RETAINED | EXISTING_TAPS}
    if args.after:
        after = scoped_dump(args.after, args.project)
        guard_postimage(before, after, args.drc_before, args.drc_after, args.dfm_after)
        report.update(status="POSTIMAGE_VERIFIED", afterSha256=sha256(args.after.read_bytes()).hexdigest(),
                      strictDrcCounts=dict(drc_profile(args.drc_after)[0]), remainingDuplicateSegments=0)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
