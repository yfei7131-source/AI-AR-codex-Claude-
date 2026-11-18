#!/usr/bin/env python3
"""Final independent delivery consistency check and SHA256 manifest."""
from pathlib import Path
import ast
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "layout/review-3"
MM = 1000 / 25.4


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    summary = read(REVIEW / "REVIEW_SUMMARY.json")
    statuses = read(ROOT / "VERIFICATION.json")
    project = read(ROOT / "native/native-project-inspection.json")
    models = read(ROOT / "3d/3D_AND_BINDINGS.json")
    audit = read(ROOT / "evidence/kicad-native-workspace/kicad-verification.json")
    codex = read(ROOT / "evidence/codex-review/KIMI_NATIVE_REVIEW.json")
    assert statuses["overall"] == "BLOCKED" and statuses["fabrication"] == "BLOCKED"
    assert statuses["fabricationAuthorized"] is False
    assert statuses["coreArchitectureChanged"] is False
    assert statuses["fakeKiCadReturnFilesCreated"] is False
    assert codex["native_review"] == "BLOCKED" and codex["manufacturing"] == "BLOCKED"
    assert "ACTUAL_EXIT_CODE=2" in (ROOT / "evidence/codex-review/review-command.log").read_text(encoding="utf-8")
    assert all(b["erc"] == "PASS" and all(v == 0 for v in b["erc_counts"].values())
               for b in audit["board_results"])
    assert project["zipIntegrity"] == "PASS"
    assert (ROOT / project["file"]).is_file()
    assert project["sha256"] == digest(ROOT / project["file"])
    assert project["independentRestoreReadback"]["result"] == "PASS_LIMITED_TO_35_CANDIDATES_AND_EMPTY_SCHEMATICS"
    assert all(b["schematicElectricalComponents"] == 0 for b in project["boards"].values())
    assert not list((ROOT / "native").rglob("*.kicad_pcb"))

    expected_counts = {"M-MAIN-L": 21, "M-OPT-BRIDGE": 10, "M-AUD-R": 4}
    assert sum(d["nativeDrc"]["total"] for d in summary["boards"].values()) == 320
    for board, expected in expected_counts.items():
        data = summary["boards"][board]
        assert data["candidateComponentCount"] == expected
        assert data["nativeDrc"]["passed"] is False
        assert sum(data["nativeDrc"]["counts"].values()) == data["nativeDrc"]["total"]
        assert data["nativeErcOnUnrebuiltSheet"]["status"] == "EMPTY_SHEET_ONLY_NOT_CONTROLLED_ERC_PASS"
        assert data["pcbCheck"]["incomplete"] is True and data["layoutLint"]["incomplete"] is True
        assert all(v == 0 for v in data["authoredRoutingCopperCounts"].values())
        assert (ROOT / data["nativeDrc"]["rawLog"]).is_file()
    assert summary["boards"]["M-OPT-BRIDGE"]["candidateGeometryStatus"] == "FAIL"
    assert len(summary["boards"]["M-OPT-BRIDGE"]["offlineFailedPlacements"]) == 2
    assert summary["boards"]["M-MAIN-L"]["embeddedFootprintViaCount"] == 9
    assert summary["boards"]["M-MAIN-L"]["candidateGeometryStatus"] == "PASS_WITHIN_LIMITED_SCOPE"
    assert summary["boards"]["M-AUD-R"]["candidateGeometryStatus"] == "PASS_WITHIN_LIMITED_SCOPE"

    with (ROOT / "layout/native-candidate-placement.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 35
    for row in rows:
        dump = read(REVIEW / row["board"] / "fresh-board.json")
        component = next(c for c in dump["components"] if c["designator"] == row["ref"])
        expected_x = (component["bbox"]["minX"] + component["bbox"]["maxX"]) / (2 * MM)
        expected_y = (component["bbox"]["minY"] + component["bbox"]["maxY"]) / (2 * MM)
        assert abs(float(row["bboxCenterXmm"]) - expected_x) < 1e-9
        assert abs(float(row["bboxCenterYmm"]) - expected_y) < 1e-9
        assert row["schematicBinding"] == "UNBOUND_CONTROLLED_NETLIST_CANDIDATE"
        assert row["landPatternQualification"] == "UNVERIFIED"

    with (ROOT / "FOOTPRINT_AUDIT.csv").open(encoding="utf-8-sig", newline="") as handle:
        pad_rows = list(csv.DictReader(handle))
    assert len(pad_rows) == 26
    assert all(row["pinPadSetStatus"] == "PASS" for row in pad_rows)
    assert all(row["landPatternQualification"] == "UNVERIFIED" for row in pad_rows)

    for board, data in models["boards"].items():
        assert data["previewVerified"] is False and data["autoGenerateModels"] is False
        assert data["bindingSummary"]["bound"] == expected_counts[board]
        for fmt, artifact in data["exports"].items():
            path = ROOT / artifact["path"]
            assert path.is_file() == artifact["exists"]
            if artifact["exists"]:
                assert artifact["bytes"] == path.stat().st_size
                assert artifact["sha256"] == digest(path)
    main_step = models["boards"]["M-MAIN-L"]["exports"]["step"]
    assert main_step["exists"] is False and main_step["exitCode"] == 1
    assert "20 MiB transport limit" in main_step["error"]

    for name in ["README.md", "BLOCKED.md", "VERIFICATION.json", "FOOTPRINT_AUDIT.csv",
                 "native/ZY_AIAR_EVT1_KIMI_20261118.epro2", "native/archive-restore-verification.json",
                 "3d/3D_AND_BINDINGS.json", "layout/review-3/REVIEW_SUMMARY.json",
                 "evidence/codex-review/review-command.log"]:
        assert (ROOT / name).is_file(), name
    for tool in (ROOT / "tools").glob("*.py"):
        ast.parse(tool.read_text(encoding="utf-8"), filename=str(tool))

    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and p.name != "SHA256SUMS.txt" and "__pycache__" not in p.parts and p.suffix != ".pyc")
    manifest = ROOT / "SHA256SUMS.txt"
    manifest.write_text("".join(f"{digest(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in files),
                        encoding="utf-8")
    print(json.dumps({"status": "PASS_DELIVERY_CONSISTENCY_ONLY",
                      "overall": "BLOCKED", "fabrication": "BLOCKED",
                      "candidateComponents": len(rows), "padAuditTypes": len(pad_rows),
                      "nativeDrcTotal": 320, "filesHashed": len(files),
                      "sha256Manifest": str(manifest)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
