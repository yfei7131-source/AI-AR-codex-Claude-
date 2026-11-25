#!/usr/bin/env python3
"""Bounded single-PTH K4 branch screen on immutable R6 native geometry."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

R6 = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(R6 / "hdi"))
import screen_hdi_joint as s

NET = "I2S_LRCLK_1V8"
SOURCE = "U11.K4"
RECEIVERS = ("J1.P12", "U10.C3", "R4.1")
WINDOW = (12, 192, 180, 660, 2)
NATIVE_HOLE_WALL_MIL = 11.85


def main():
    source = s.PADS[SOURCE][0]
    source_rows = []
    cells = 0
    via_ok = 0
    endpoint_counts = {ref: 0 for ref in RECEIVERS}
    for center in s.cells(*WINDOW):
        cells += 1
        if not s.check_via(center, 6, 3, s.LAYERS, NET):
            continue
        wall = s.check_hole(center, 3, s.LAYERS, NET)
        if wall[0] < NATIVE_HOLE_WALL_MIL:
            continue
        via_ok += 1
        top = s.route(source, center, 1, NET, 4)
        if not top:
            continue
        branches = {}
        for ref in RECEIVERS:
            bottom = s.route(center, s.PADS[ref][0], 2, NET, 4)
            if bottom:
                branches[ref] = bottom
                endpoint_counts[ref] += 1
        if branches:
            source_rows.append({"center": center, "top": top, "branches": branches})
    shared = [row for row in source_rows if len(row["branches"]) == len(RECEIVERS)]
    shared.sort(key=lambda row: (row["top"]["length_mil"]
                                 + sum(branch["length_mil"] for branch in row["branches"].values())))
    receiver_pairs = [row for row in source_rows if "J1.P12" in row["branches"] and "U10.C3" in row["branches"]]
    receiver_pairs.sort(key=lambda row: (row["top"]["length_mil"]
                                        + row["branches"]["J1.P12"]["length_mil"]
                                        + row["branches"]["U10.C3"]["length_mil"]))
    def measured(rows):
        output = []
        for row in rows[:12]:
            planes = s.plane_return([(row["center"], 6, s.LAYERS)])
            output.append(row | {
                "hole_wall_to_existing_drill_mil": s.check_hole(row["center"], 3, s.LAYERS, NET),
                "required_hole_wall_mil": NATIVE_HOLE_WALL_MIL,
                "nominal_planes": planes,
                "native_plane_antipad_required": True,
                "status": "offline-candidate-only" if all(
                    v["components_before"] == v["components_after"] and not v["ground_contact_overlap"]
                    for v in planes.values()) else "candidate-rejected-plane-topology",
            })
        return output
    result = {
        "schemaVersion": 1,
        "scope": "One normal 6/12 mil PTH from U11.K4 to Bottom with direct route variants; not a multilayer or multi-via completeness proof.",
        "source": SOURCE,
        "receivers": RECEIVERS,
        "net": NET,
        "nativeArchiveSha256": hashlib.sha256(s.FILE.read_bytes()).hexdigest(),
        "nativeCopperSnapshotSha256": hashlib.sha256((R6 / "verification/PCB3-restore-copper.json").read_bytes()).hexdigest(),
        "searchWindowMil": {"x": WINDOW[:2], "y": WINDOW[2:4], "stepMil": WINDOW[4]},
        "gridPoints": cells,
        "viaAndTopEscapePositions": via_ok,
        "positionsWithAnyTopRoute": len(source_rows),
        "directBottomBranchCounts": endpoint_counts,
        "sharedReceiverPairPositions": len(receiver_pairs),
        "sharedAllThreePositions": len(shared),
        "receiverPairCandidates": measured(receiver_pairs),
        "allThreeCandidates": measured(shared),
        "status": "bounded-search-complete",
        "limitations": [
            "Zero candidates only applies to the declared grid, route variants and single-PTH topology.",
            "Plane-return geometry is not a native antipad write, impedance proof, supplier approval or fabrication release.",
            "Any candidate requires fresh typed native creation, save/reload, full DRC and net-path verification before integration.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if not key.endswith("Candidates")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
