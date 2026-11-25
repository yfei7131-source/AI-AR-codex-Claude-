"""Verify the fresh P2 payload against the prior R11 normalization."""
from argparse import ArgumentParser
from copy import deepcopy
import json
from pathlib import Path

from extract_p2 import BOARDS, read_json, require, write_json


def design_payload(dataset):
    clean = deepcopy(dataset)
    for name in ("coverage", "sources"):
        clean.pop(name)
    clean["nativeConstraints"].pop("editorRuleSummary")
    clean["nativeConstraints"].pop("editorNetRuleConfiguration", None)
    clean["layers"].pop("editorLogicalCopperLayers", None)
    for component in clean["components"]:
        for pad in component["pads"]:
            for key in ("editorHoleGeometry", "editorShapeBBox", "editorHoleReadback"):
                pad.pop(key, None)
    return clean


def compare(previous_root, fresh_root):
    old_manifest = read_json(previous_root / "manifest.json")
    new_manifest = read_json(fresh_root / "manifest.json")
    for key in ("nativeArchiveSha256", "sourceCommit", "boardCounts"):
        require(old_manifest[key] == new_manifest[key], f"P2 {key} differs")
    require(new_manifest["captureClass"] == "fresh-native-import", "Expected the fresh capture bundle")
    require(new_manifest["captureProjectUuid"] != old_manifest["captureProjectUuid"], "Fresh project must differ")
    result = {}
    for board in BOARDS:
        previous = read_json(previous_root / f"{board}.json")
        fresh = read_json(fresh_root / f"{board}.json")
        old_design, new_design = design_payload(previous), design_payload(fresh)
        old_drc = old_design.pop("nativeDRCObjects")
        new_drc = new_design.pop("nativeDRCObjects")
        require(old_design == new_design, f"{board} P2 geometry or native rules changed")
        signature = lambda rows: sorted((r["rule"], r["objType"], r.get("net") or "",
                                         tuple(sorted(r.get("objs") or [])) if r["rule"] != "Netlist Error" else ())
                                        for r in rows)
        require(signature(old_drc) == signature(new_drc), f"{board} DRC object signatures changed")
        summary = fresh["nativeConstraints"]["editorRuleSummary"]
        pads = [pad for component in fresh["components"] for pad in component["pads"]]
        result[board] = {
            "archiveGeometryAndRulesMatch": True, "drcObjectSignaturesMatch": True,
            "captureAddsSpacingMatrix": bool(summary.get("spacingMil")),
            "capturePadsWithShapeBBox": sum(bool(pad.get("editorShapeBBox")) for pad in pads),
            "capturePadsWithHoleGeometry": sum(bool(pad.get("editorHoleGeometry")) for pad in pads),
            "reportedArchivedOnlyTracks": fresh["coverage"]["copperArchiveVersusEditor"]["lines"]["archiveOnlyIds"],
        }
    return {"source": new_manifest["sourceCommit"], "freshProjectUuid": new_manifest["captureProjectUuid"],
            "boards": result}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--fresh", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    compared = compare(args.prior, args.fresh)
    write_json(args.out, compared)
    print(json.dumps(compared))
