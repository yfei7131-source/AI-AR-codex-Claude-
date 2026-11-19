#!/usr/bin/env python3
"""Bounded offline fit trial for bridge connector islands and AVDD co-placement."""

import argparse
import csv
from dataclasses import dataclass
from functools import cached_property
import hashlib
from itertools import combinations, product
import json
from math import hypot
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(PACKAGE / "closure"))
import check_bridge_placement as prior


GRID = 0.10
BRIDGE_AUDIT = PACKAGE / "closure" / "evidence" / "bridge_placement.json"
PIN_MAP = PACKAGE / "Inputs" / "effective_pinmap.csv"
EVIDENCE = HERE / "bridge_island_trial.json"
SOURCES = {
    "U8": "U_AVDD_LS",
    "U10": "U_AVDD_QUAL",
    "U14": "U_AVDD_WD",
    "U13": "U_AVDD_SYS_PG",
}
SIDES = {1: "TOP", 2: "BOTTOM"}
CATALOG = "https://www.hirose.com/en/product/series/BM28/documents?path=%2Fapi%2Fv1%2Fseries%2FBM28%2Fdocuments%2Fproduct_series_catalog%2Fcontent%3Flang%3DEN"
TI_DATASHEET = "https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf"
LED_DATASHEET = "https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf"


@dataclass(frozen=True)
class Pose:
    ref: str
    side: int
    angle: int
    anchor: tuple
    body: prior.Box
    copper: prior.Box
    observed_orientation: bool

    @cached_property
    def occupied(self):
        return prior.bbox_union((self.body, self.copper))


def native_pose(ref, row):
    return Pose(ref, row["layer"], row["rotation"], (row["x"] * prior.MIL, row["y"] * prior.MIL),
                prior.mm_box(row["bbox"], prior.MIL),
                prior.bbox_union([prior.pad_box(pad) for pad in row["pads"]]), True)


def rounded(box):
    return prior.rounded(box)


def gap_ok(a, b, clearance):
    return a.side != b.side or a.occupied.gap(b.occupied) >= clearance


def pose_clearance(candidate, outline, fixed, reserves, edge, gap):
    if outline.inset(candidate.body) < 0 or outline.inset(candidate.copper) < edge:
        return False
    if any(not gap_ok(candidate, item, gap) for item in fixed):
        return False
    return all(label == "Y1_CLOCK_SEARCH_RESERVE" and candidate.ref == "Y1"
               or not candidate.occupied.intersect_keepout(box, gap)
               for label, box in reserves[candidate.side])


def support_islands(outline, edge, clearance):
    box = prior.Box
    rows = (
        # Long connector axis is Y. Off-board positions use the same flat datum as the bridge.
        ("J_DISP_L", box(-5.70, 1.45, -2.50, 6.95), 4.55, box(-2.50, 3.03, 0.70, 5.37)),
        ("J_DISP_R", box(6.70, 12.05, 9.90, 17.55), 4.55, box(3.50, 13.63, 6.70, 15.97)),
        ("J_BRIDGE_IN", box(0.50, -11.50, 3.70, -2.50), 8.05, box(0, -2.50, 4.20, 1.30)),
    )
    catalog = json.loads(prior.CONNECTOR_BODIES.read_bytes())["connectors"]
    with PIN_MAP.open(encoding="utf-8", newline="") as handle:
        pins = [row for row in csv.DictReader(handle) if row["Board"] == "M-OPT-BRIDGE"]
    result = []
    for ref, support, plug_e, transition in rows:
        part = catalog[ref]
        contacts = [p for p in pins if p["Chip_Ref"] == ref]
        contact_count = 32 if ref == "J_BRIDGE_IN" else 12
        if len(contacts) != contact_count or len({p["Pin_ID"] for p in contacts}) != contact_count:
            raise ValueError(f"Unexpected contact contract at {ref}")
        x, y = center(support)
        half_width, half_length = part["bodyWidthMm"] / 2, part["bodyLengthMm"] / 2
        body = box(x - half_width, y - half_length, x + half_width, y + half_length)
        # Hirose p. 7 shows 1.90 +0.05 mm for the receptacle land span.
        # Page 6 lists the plug's longitudinal E insulation minimum. The
        # planning guard adds 0.05 mm to those values on both axes overall.
        guarded_y = (plug_e + 0.05) / 2
        guard = box(x - 1.00, y - guarded_y, x + 1.00, y + guarded_y)
        guard_edge = support.inset(guard)
        bridge_gap = support.gap(outline)
        if guard_edge < edge or support.inset(body) < 0 or bridge_gap < clearance:
            raise ValueError(f"{ref} exceeds its trial stiffener envelope")
        result.append({"ref": ref, "supportMm": rounded(support), "connectorCenterMm": [round(x, 3), round(y, 3)],
                       "longAxis": "Y", "receptacleMpn": part["mpn"], "receptacleSource": part["source"],
                       "receptacleBodyMm": rounded(body), "catalogPlugInsulationMinEMm": plug_e,
                       "catalogMatedHeightMm": 0.60, "boardSideContactCount": contact_count,
                       "connectorPlanningGuardMm": rounded(guard),
                       "minGuardToSupportEdgeMm": round(guard_edge, 6),
                       "flatGapToBridgeMm": round(bridge_gap, 6),
                       "flatFlexTransitionMm": rounded(transition), "mountedAssembly": "BLOCKED"})
    return result


def center(box):
    return ((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)


def distance(a, b):
    x, y = center(a)
    u, v = center(b)
    return hypot(x - u, y - v)


def read_sources():
    raw = {}
    for key, rel in prior.INPUTS.items():
        if key != "original_archive":
            raw[key] = json.loads((prior.RETURN / rel).read_bytes())
    return raw


def rank_poses(ref, templates, outline, fixed, reserve, edge, gap):
    # The D3 translator is biased toward U2_FPGA. U10 and U14 use the same
    # target for a bounded search, then are scored together with the translator.
    fpga = next(item for item in fixed if item.ref == "U2")
    candidates = []
    for source, body, copper in templates:
        for xi, yi in product(range(1, 42), range(1, 220)):
            x, y = round(xi * GRID, 3), round(yi * GRID, 3)
            if ref == "U13" and not 4.0 <= y <= 9.5:
                continue
            pose = Pose(ref, source["layer"], source["rotation"], (x, y),
                        body.translated(x, y), copper.translated(x, y), source["nativeOrientationObserved"])
            if pose_clearance(pose, outline, fixed, reserve, edge, gap):
                candidates.append(pose)
    candidates.sort(key=lambda p: (round(distance(p.body, fpga.body), 9),
                                   not p.observed_orientation, p.side, p.angle, p.anchor))
    return candidates


def with_reverse_angles(templates):
    return [*templates, *[
        ({**source, "rotation": (source["rotation"] + 180) % 360, "nativeOrientationObserved": False},
         body.rotated().rotated(), copper.rotated().rotated())
        for source, body, copper in templates
    ]]


def yzpr_templates():
    # TI drawing 4223082/A. Origin at package center. 2 x 4, 0.50 mm pitch,
    # 0.23 mm NSMD example lands. Body axes E x D in the trial's 0-degree pose.
    body = prior.Box(-0.459, -0.959, 0.459, 0.959)
    copper = prior.Box(-0.365, -0.865, 0.365, 0.865)
    return [({"layer": side, "rotation": angle, "nativeOrientationObserved": False}, b, c)
            for side in SIDES for angle, b, c in ((0, body, copper), (90, body.rotated(), copper.rotated()))]


def compatibility(a, poses, gap):
    return sum(1 << index for index, b in enumerate(poses) if gap_ok(a, b, gap))


def set_bits(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def choose_group(ranks, fixed, gap):
    # Every generated pair remains eligible. Bit sets avoid a grid Cartesian
    # product. Return the first reproducible witness in nearest-to-FPGA U8
    # order. Centre distances are diagnostics, not a routing-cost estimate.
    fpga = next(p for p in fixed if p.ref == "U2")
    watchdog = ranks["U14"]
    qualifier = ranks["U10"]
    power_good = ranks.get("U13", [])
    if "U13" in ranks and not power_good:
        return None
    qualifier_wd = [compatibility(p, watchdog, gap) for p in qualifier]
    qualifier_pg = [compatibility(p, power_good, gap) for p in qualifier]
    watchdog_pg = [compatibility(p, power_good, gap) for p in watchdog]
    for u8 in ranks["U8"]:
        u8_wd = compatibility(u8, watchdog, gap)
        u8_pg = compatibility(u8, power_good, gap)
        u8_dist = distance(fpga.body, u8.body)
        for i in set_bits(compatibility(u8, qualifier, gap)):
            active_pg = u8_pg & qualifier_pg[i]
            if power_good and not active_pg:
                continue
            u10 = qualifier[i]
            u10_dist = distance(u8.body, u10.body)
            for j in set_bits(u8_wd & qualifier_wd[i]):
                pg_options = active_pg & watchdog_pg[j]
                if power_good and not pg_options:
                    continue
                u14 = watchdog[j]
                group = (u8, u10, u14)
                pieces = (u8_dist, u10_dist, distance(u8.body, u14.body))
                if pg_options:
                    pg = min((power_good[k] for k in set_bits(pg_options)), key=lambda p: distance(u8.body, p.body))
                    group += (pg,)
                    pieces += (distance(u8.body, pg.body),)
                return group, pieces
    return None


def screen_case(templates, outline, fixed, reserves, edge, clearance):
    ranks = {ref: rank_poses(ref, variants, outline, fixed, reserves, edge, clearance)
             for ref, variants in templates.items()}
    measured = {ref: len(poses) for ref, poses in ranks.items()}
    best = choose_group(ranks, fixed, clearance)
    report = {"coPlacement": "PASS" if best else "FAIL", "independentClearPoses": measured}
    if best:
        group, distances = best
        placements = [*fixed, *group]
        if not all(gap_ok(a, b, clearance) for a, b in combinations(placements, 2)):
            raise ValueError("Generated group violates a same-side placement clearance")
        report["candidateGroup"] = [describe(p, outline, reserves, [q for q in placements if q.ref != p.ref])
                                    for p in group]
        report["centreDistanceProxiesMm"] = dict(zip(("U2_to_U8", "U8_to_U10", "U8_to_U14", "U8_to_U13"),
                                                    (round(d, 4) for d in distances)))
    return report


def audited_layout():
    data = read_sources()
    contract_path = PACKAGE / "PCB_CONSTRAINTS.json"
    contract = json.loads(contract_path.read_bytes())
    outline = prior.validate_outline(data["restored"], contract["boards"]["M-OPT-BRIDGE"])
    edge = max(contract["do_not_relax"]["minimum_edge_clearance_mm"], data["restored"]["rules"]["copperToEdgeMil"] * prior.MIL)
    clearance = contract["do_not_relax"]["minimum_courtyard_gap_mm"]
    if edge < 0.254 or clearance < 0.20:
        raise ValueError("Bridge preservation rule regressed")
    reserves = {1: [], 2: []}
    ret = json.loads(BRIDGE_AUDIT.read_bytes())
    actual = prior.components(data["restored"])
    if prior.static_geometry(actual) != prior.static_geometry(prior.components(data["review3"])):
        raise ValueError("Previously verified Review-3 and restored placements disagree")
    for row in ret["reservations"]:
        if row["ref"] in {"U6_OPT_AVDD", "Y1_CLOCK_SEARCH_RESERVE"}:
            reserves[row["layer"]].append((row["ref"], prior.Box(*row["boxMm"])))
    nominal_privacy = prior.Box(*ret["privacyNominalBodyBoxMm"])
    led_x, led_y = center(nominal_privacy)
    # The inherited D3 axis is Y. Kingbright V.4B p. 1 gives 0.70 x 0.80 mm
    # lands 1.50 mm center to center. Search keepout adds 0.10 mm per side.
    led_copper = prior.Box(led_x - 0.40, led_y - 1.10, led_x + 0.40, led_y + 1.10)
    led_guard = prior.Box(led_x - 0.50, led_y - 1.20, led_x + 0.50, led_y + 1.20)
    if led_guard.inset(nominal_privacy) < 0 or outline.inset(led_copper) < edge:
        raise ValueError("D3 projection conflicts with the inherited location or copper edge")
    reserves[1].append(("D3_PRIV_BODY_AND_LAND_GUARD", led_guard))
    # Repartition the connector mounting areas to remote stiffeners. Keep
    # the inherited optical y ranges at the changed flex transition edges.
    for side, ref, bounds in (
        (1, "J_DISP_L_EDGE_LAUNCH", (0, 3.03, .70, 5.37)),
        (1, "J_DISP_R_EDGE_LAUNCH", (3.50, 13.63, 4.20, 15.97)),
        (2, "J_BRIDGE_IN_EDGE_LAUNCH", (0, 0, 4.20, 1.30)),
    ):
        reserves[side].append((ref, prior.Box(*bounds)))
    fixed = [native_pose(ref, c) for ref, c in sorted(actual.items()) if ref != "U8"]
    fixed_conflicts = [p.ref for p in fixed
                       if not pose_clearance(p, outline, [q for q in fixed if q.ref != p.ref], reserves, edge, clearance)]
    if fixed_conflicts:
        raise ValueError(f"Fixed geometry conflicts with the inherited clearances: {fixed_conflicts}")
    templates = {ref: with_reverse_angles(variants) for ref, variants in prior.templates(data).items()}
    current = screen_case(templates, outline, fixed, reserves, edge, clearance)
    supervisor = next(p for p in fixed if p.ref == "U13")
    x, y = supervisor.anchor
    supervisor_templates = [({"layer": supervisor.side, "rotation": supervisor.angle, "nativeOrientationObserved": True},
                             supervisor.body.translated(-x, -y), supervisor.copper.translated(-x, -y))]
    moved_u13 = screen_case({**templates, "U13": supervisor_templates}, outline,
                            [p for p in fixed if p.ref != "U13"], reserves, edge, clearance)
    alternate = screen_case({**templates, "U8": yzpr_templates()}, outline, fixed, reserves, edge, clearance)
    islands = support_islands(outline, edge, clearance)
    if any(prior.Box(*a["supportMm"]).gap(prior.Box(*b["supportMm"])) < clearance
           for a, b in combinations(islands, 2)):
        raise ValueError("Connector support islands collide")
    native_files = {f"kimi-return/{rel}": hashlib.sha256((prior.RETURN / rel).read_bytes()).hexdigest()
                    for key, rel in prior.INPUTS.items() if key != "original_archive"}
    return {
        "baseline": "PR #34 source tree; uses independently verified PR #30/32 PCB geometry",
        "trial_status": "CONDITIONAL_FIT" if alternate["coPlacement"] == "PASS" else "NO_WITNESS",
        "h03_placement": "BLOCKED", "fabrication": "BLOCKED", "label": "NOT FOR FAB",
        "scope": "Simultaneous AABB and copper-edge grid fit for three AVDD ICs and original fixed objects. Remote connectors use conditional flat envelopes. Full AVDD group, local bypasses, all copper routing and mated installation are unverified.",
        "source_sha256": {**native_files,
                           **{path.relative_to(PACKAGE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in (contract_path, BRIDGE_AUDIT, prior.CONNECTOR_BODIES, PIN_MAP)}},
        "bridge_outline_mm": rounded(outline), "manufacturer_reference": CATALOG,
        "min_copper_edge_mm": edge, "min_same_side_aabb_gap_mm": clearance,
        "unchanged_manufacturing_rules": contract["do_not_relax"],
        "fixed_native": [describe(p, outline, reserves, [q for q in fixed if q.ref != p.ref]) for p in fixed],
        "privacyLedProjection": {
            "mpn": "APHD1608LCGCK", "source": LED_DATASHEET, "reference": "V.4B p. 1", "longAxis": "Y",
            "originalNominalBodyMm": rounded(nominal_privacy), "nominalCopperBoxMm": rounded(led_copper),
            "guardMm": rounded(led_guard), "minProjectedNominalCopperEdgeMm": round(outline.inset(led_copper), 6),
            "lightGuideAndMountedAssembly": "BLOCKED",
        },
        "reserves_on_rigid_bridge": [{"ref": ref, "side": SIDES[side], "boxMm": rounded(box)}
                                     for side, rows in reserves.items() for ref, box in rows],
        "remote_connector_islands": islands,
        "flat_union_extent_mm": rounded(prior.bbox_union([outline] + [prior.Box(*i["supportMm"]) for i in islands])),
        "search_grid_mm": GRID,
        "cases": {
            "SN74LVC2T45DCUR_U13_fixed": current,
            "SN74LVC2T45DCUR_U13_repacked": {
                "U13SearchDomain": "Original side and rotation. Anchor Y from 4.0 to 9.5 mm.", **moved_u13,
            },
            "SN74LVC2T45YZPR_U13_fixed": {
                "source": TI_DATASHEET,
                "drawing": "4223082/A YZP0008 max body and 8 x 0.23 mm example land on 0.50 mm pitch",
                "maxBodyMm": [0.918, 1.918, 0.50], "landBoundingSpanMm": [0.73, 1.73],
                "DCUtoYZPPins": {"1": "A1", "2": "B1", "3": "C1", "4": "D1", "5": "D2", "6": "C2", "7": "B2", "8": "A2"},
                "anchorMeaning": "U8 package center; remaining coordinates use the captured native footprint origins",
                **alternate,
            },
        },
        "releaseBlockers": [
            "ID model, lens placement and shell/hinge clearance for all three support islands and service access.",
            "Qualified alternate flex/stiffener and termination on the central bridge. Existing optical y corridors only retained locally at the shifted launches.",
            "Approved YZPR substitution, native A1/pad and actual copper/mask/paste validation, solder and inspection approvals, installed fit, AVDD electrical and power-off behavior.",
            "Native footprints, mating and assembly access tolerances; microphone port and privacy light guide fit; JBD vendor pin/sequence/AVDD.",
            "Placement of other AVDD safety/RC parts, local bypass loops, verified manufacturer courtyard and full native design, route and DRC.",
            "Supplier-approved 0.50 mm bridge/6L/VIPPO/50 μm process, SI/PI, trunk contact/current/IR/thermal, 40 g mass budget and all hardware validation.",
        ],
    }


def describe(pose, outline, reserves, peers):
    same_side = [pose.occupied.gap(p.occupied) for p in peers if p.side == pose.side]
    reserved = [pose.occupied.gap(box) for ref, box in reserves[pose.side]
                if (pose.ref, ref) != ("Y1", "Y1_CLOCK_SEARCH_RESERVE")]
    return {"ref": pose.ref, "sourceRef": SOURCES.get(pose.ref), "side": SIDES[pose.side], "rotationDegrees": pose.angle,
            "nativeOrientationObserved": pose.observed_orientation,
            "anchorMm": [round(value, 6) for value in pose.anchor],
            "bodyBoxMm": rounded(pose.body), "copperBoxMm": rounded(pose.copper),
            "minCopperEdgeMm": round(outline.inset(pose.copper), 6),
            "minSameSideAabbGapMm": round(min(same_side), 6) if same_side else None,
            "minReservationGapMm": round(min(reserved), 6) if reserved else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audited_layout()
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        if not EVIDENCE.is_file() or EVIDENCE.read_bytes() != encoded:
            raise SystemExit("FAIL: alternative bridge evidence differs")
    else:
        EVIDENCE.write_bytes(encoded)
    print(f"{report['trial_status']}: bounded connector-island fit trial. H03 and fabrication BLOCKED.")
    for name, case in report["cases"].items():
        print(f"{name}: {case['coPlacement']} {case['independentClearPoses']}")
    return 0 if report["trial_status"] == "CONDITIONAL_FIT" else 1


if __name__ == "__main__":
    sys.exit(main())
