"""R4 isolated DC experiment; never writes R3 or changes footprint geometry.

Starts from the documented R3 final board, removes six identified ground
loop segments that close the QFN fanout, and attempts three known DC
connections. The endpoint interfaces J3/J4/J7 and all DNP settings stay intact.
Native DRC remains mandatory. This script does not grant manufacturing release.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as k

from advance_pcb import route_drc, Router, vec, add_track
from verify_pcb import copper_signature


HERE = Path(__file__).resolve().parents[1]
REMOVE_UUIDS = {
    "83e519f3-f8d7-4a9b-ac76-d677cb81f5dd",
    "3ece93f9-399b-4025-a836-aa37f139029b",
    "a5895f19-dc2b-427a-b368-fdfd668420f2",
    "b93f6155-d74d-4817-b623-abd119b85e71",
    "216eafaa-97d9-4f9d-b063-2b8f9a254570",
    "afd64246-6a8d-4c72-82bf-7385ac968e09",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def footprint_geometry(board):
    return {
        f.GetReference(): {
            "uuid": f.m_Uuid.AsString(),
            "position": [f.GetPosition().x, f.GetPosition().y],
            "angle": f.GetOrientationDegrees(),
            "layer": f.GetLayer(), "dnp": f.IsDNP(),
            "pads": sorted((p.m_Uuid.AsString(), p.GetNumber(), p.GetPosition().x,
                            p.GetPosition().y, p.GetSize().x, p.GetSize().y,
                            p.GetDrillSize().x, p.GetDrillSize().y, p.GetNetname())
                           for p in f.Pads()),
        } for f in board.GetFootprints()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE.parents[2] /
                        "evt0-r3/H02/evt0_core/evt0_core.kicad_pcb")
    parser.add_argument("--drc", type=Path, default=HERE.parents[2] /
                        "evt0-r3/H02/evt0_core/evidence/pcb-drc-final.json")
    parser.add_argument("--out", type=Path, default=HERE / "evt0_core.kicad_pcb")
    args = parser.parse_args()
    args.source, args.drc, args.out = args.source.resolve(), args.drc.resolve(), args.out.resolve()
    if args.source == args.out or not args.out.is_relative_to(HERE.parents[1]):
        parser.error("Output must be inside the independent R4 review directory")
    original_hash = digest(args.source)
    board = k.LoadBoard(str(args.source))
    before_geometry = footprint_geometry(board)
    before = {t.m_Uuid.AsString(): copper_signature(t) for t in board.GetTracks()}
    targets = [t for t in board.GetTracks() if t.m_Uuid.AsString() in REMOVE_UUIDS]
    if len(targets) != len(REMOVE_UUIDS):
        raise ValueError("Reviewed ground-loop UUID absent from source")
    for target in targets:
        if target.GetNetname() != "/GND" or target.GetLayer() != k.F_Cu or isinstance(target, k.PCB_VIA):
            raise ValueError("Removal target is not a reviewed F.Cu ground segment")
        board.Remove(target)
    print("Removed six R4-only QFN GND loop segments; retained USB ground bridge", flush=True)
    route_drc(board, args.drc, {"CHG_EN1", "CHG_PGOOD_N"})
    # Short, checked connector supply fanout, with the via outside J1's solder pad.
    router = Router(board)
    net = board.FindNet("/VBUS").GetNetCode()
    via_at = vec(122.7, 121.05)
    front_end = vec(122.55, 122.055)
    back_end = vec(122.75, 121.0)
    disk = k.SHAPE_CIRCLE(via_at, k.FromMM(.3))
    valid = (router.clear(net, disk, 0) and router.clear(net, disk, 1)
             and router.clear(net, k.SHAPE_SEGMENT(via_at, front_end, k.FromMM(.3)), 0)
             and router.clear(net, k.SHAPE_SEGMENT(back_end, via_at, k.FromMM(.3)), 1)
             and all((pos-via_at).EuclideanNorm() > (k.FromMM(.3)+drill)/2+k.FromMM(.26)
                     for pos, drill in router.holes))
    if valid:
        add_track(board, net, via_at, front_end, k.F_Cu, .3)
        add_track(board, net, back_end, via_at, k.B_Cu, .3)
        via = k.PCB_VIA(board)
        via.SetPosition(via_at)
        via.SetWidth(k.FromMM(.6))
        via.SetDrill(k.FromMM(.3))
        via.SetNetCode(net)
        board.Add(via)
        print("Added checked VBUS short fanout and 0.3mm-drill via", flush=True)
    else:
        print("VBUS manual candidate rejected by collision/drill checks", flush=True)
    board.GetTitleBlock().SetRevision("R4-DC-review")
    board.GetTitleBlock().SetComment(0, "Isolated DC routing experiment; DRC and safety gates remain open")
    if footprint_geometry(board) != before_geometry:
        raise ValueError("Footprint/pad placement, DNP, or geometry changed")
    k.ZONE_FILLER(board).Fill(board.Zones())
    k.SaveBoard(str(args.out), board)
    reloaded = k.LoadBoard(str(args.out))
    after = {t.m_Uuid.AsString(): copper_signature(t) for t in reloaded.GetTracks()}
    removed = sorted(before.keys() - after.keys())
    changed = {uid: {"before": before[uid], "after": after[uid]}
               for uid in before.keys() & after.keys() if before[uid] != after[uid]}
    added = {uid: after[uid] for uid in sorted(after.keys() - before.keys())}
    geometry_unchanged = footprint_geometry(reloaded) == before_geometry
    info = {
        "kind": "isolated_R4_DC_experiment_not_manufacturing_release",
        "source_r3_sha256": original_hash,
        "source_r3_unchanged": digest(args.source) == original_hash,
        "r4_board_sha256": digest(args.out),
        "source_drc_sha256": digest(args.drc),
        "allowed_route_nets": ["/CHG_EN1", "/CHG_PGOOD_N", "/VBUS"],
        "reason_for_ground_loop_removal": "Open U3 south fanout; ground pads retain plane access, subject to native DRC connectivity verification. USB ground bridge retained after rejected experiment.",
        "removed_copper": {uid: before[uid] for uid in removed},
        "changed_existing_copper": changed,
        "added_copper": added,
        "counts": {"before": len(before), "removed": len(removed), "changed": len(changed),
                   "added": len(added), "after": len(after)},
        "footprints_pads_positions_dnp_unchanged": geometry_unchanged,
        "manufacturing_release": False,
        "native_drc_required": True,
    }
    output = HERE.parents[1] / "evidence/dc-change-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    if set(removed) != REMOVE_UUIDS or changed or not geometry_unchanged or not info["source_r3_unchanged"]:
        raise ValueError("Unexpected R4 mutation; see audit")
    print(json.dumps(info["counts"]), flush=True)


if __name__ == "__main__":
    main()
