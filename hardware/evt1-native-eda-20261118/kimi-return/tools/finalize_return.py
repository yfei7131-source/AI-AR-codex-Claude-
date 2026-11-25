#!/usr/bin/env python3
"""Derive final handoff evidence from actual readbacks and exported files.

This script does not call EasyEDA, change rules, repair DRC, or convert formats.
It intentionally retains FAIL/BLOCKED/UNVERIFIED outcomes for Codex review.
"""
from pathlib import Path
from datetime import datetime, timezone
import collections
import csv
import hashlib
import itertools
import json
import math
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "layout/review-3"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"
ARCHIVE = ROOT / "native/ZY_AIAR_EVT1_KIMI_20261118.epro2"
MM = 1000 / 25.4
IDS = {
    "M-MAIN-L": {"pcb": "8fbc3cae65886fe5", "sch": "dff3a8fe270050d6"},
    "M-OPT-BRIDGE": {"pcb": "9ce45f14cb79dc9d", "sch": "43a42f20d31f8062"},
    "M-AUD-R": {"pcb": "1db01a36f669a47a", "sch": "388fb7a3b1e5f2d6"},
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_log(path):
    text = path.read_text(encoding="utf-8")
    start = text.find("{")
    return json.JSONDecoder().raw_decode(text[start:])[0] if start >= 0 else None


def response(operation):
    value = operation.get("response") or {}
    if not isinstance(value, dict):
        return {}
    result = value.get("result", value)
    return result if isinstance(result, dict) else {}


def export_path(operation):
    command = operation["command"]
    out = Path(command[command.index("--out") + 1])
    result = response(operation)
    return out / result["file"] if result.get("file") else out


def main():
    manifest = read(REVIEW / "manifest.json")
    geometry = read(REVIEW / "geometric-audit.json")
    source = read(ROOT / "evidence/kicad-source-audit.json")
    kicad = read(ROOT / "evidence/kicad-native-workspace/kicad-verification.json")
    pad_audit = read(ROOT / "evidence/pad-audit/native-pad-audit.json")
    assert manifest["windowId"] and geometry["round"] == 3
    assert all((REVIEW / b / "fresh-board.json").is_file() for b in IDS)
    assert not any(operation["exitCode"] is None for board in manifest["boards"].values()
                   for operation in board["operations"].values())

    archive_inspection = {"file": str(ARCHIVE.relative_to(ROOT)),
                          "bytes": ARCHIVE.stat().st_size, "sha256": sha(ARCHIVE),
                          "projectUuid": PROJECT, "documents": {}, "boards": {}}
    with zipfile.ZipFile(ARCHIVE) as package:
        assert package.testzip() is None, "Native archive CRC failed"
        archive_inspection["zipIntegrity"] = "PASS"
        archive_inspection["members"] = [{"name": i.filename, "bytes": i.file_size}
                                        for i in package.infolist()]
        epru_name = next(i.filename for i in package.infolist() if i.filename.endswith(".epru"))
        project_header = json.loads(package.read("project2.json"))
        archive_inspection["projectHeader"] = project_header
        records = []
        for line in package.read(epru_name).decode("utf-8").splitlines():
            header_text, data_text = line.rstrip("|").split("||", 1)
            records.append((json.loads(header_text), json.loads(data_text)))
    docs = {}
    current = None
    for header, data in records:
        if header.get("type") == "DOCHEAD":
            current = data.copy()
            current["records"] = []
            docs[(data["docType"], data["uuid"])] = current
        assert current is not None
        current["records"].append((header, data))
    for board, ids in IDS.items():
        pcb = docs[("PCB", ids["pcb"])]
        sch = docs[("SCH_PAGE", ids["sch"])]
        components = [d for h, d in pcb["records"] if h.get("type") == "COMPONENT"]
        electrical = []
        frames = []
        for header, data in sch["records"]:
            if header.get("type") != "COMPONENT":
                continue
            device = json.loads(data["attrs"]["DeviceName"])
            (frames if device["name"].startswith("Drawing-Symbol_") else electrical).append(device)
        archive_inspection["boards"][board] = {
            "pcbUuid": ids["pcb"], "schematicUuid": ids["sch"],
            "exportedPcbComponents": len(components),
            "uniqueIdNonempty": sum(bool(c.get("attrs", {}).get("Unique ID")) for c in components),
            "nativePcbRecordTypes": dict(collections.Counter(h.get("type") for h, d in pcb["records"])),
            "schematicElectricalComponents": len(electrical),
            "schematicDrawingFrames": len(frames),
            "schematicRecordTypes": dict(collections.Counter(h.get("type") for h, d in sch["records"])),
            "schematicScope": "Drawing frame only; no controlled electrical schematic; native zero ERC is not controlled-design ERC PASS",
        }
        assert not electrical, f"{board}: unexpected electrical schematic, update scope review"
    assert sum(v["exportedPcbComponents"] for v in archive_inspection["boards"].values()) == 35
    archive_inspection["auditPcbPresent"] = ("PCB", "271a28697816c22b") in docs
    archive_inspection["documentTypeCounts"] = dict(collections.Counter(t for t, u in docs))
    archive_inspection["archiveStatus"] = "PASS_PARTIAL_NATIVE_PROJECT_NOT_COMPLETE_SCHEMATICS"
    export_receipt = json_log(REVIEW / "91-project-export-corrected.log")["result"]
    assert export_receipt["sha256"] == archive_inspection["sha256"]
    archive_inspection["nativeExportReceipt"] = export_receipt
    archive_inspection["priorExportArgumentFailure"] = "layout/review-3/90-project-export.log"
    restore = read(ROOT / "native/archive-restore-verification.json")
    assert restore["importedProjectUuid"] != PROJECT
    assert all(b["componentPadsAndBboxParity"] == "PASS" and b["outlineParity"] == "PASS"
               and b["rulesParity"] == "PASS" for b in restore["boards"].values())
    archive_inspection["independentRestoreReadback"] = {
        "projectUuid": restore["importedProjectUuid"], "librariesExtracted": False,
        "sourceProjectOverwritten": False, "result": restore["nativeEditableRestoreReadback"],
        "evidence": "native/archive-restore-verification.json",
        "scope": "35 candidate components, pad/bbox, outline and scalar-rule parity; no complete schematic or routing parity",
    }
    write(ROOT / "native/native-project-inspection.json", archive_inspection)

    plan = read(ROOT / "layout/candidate-placement-plan.json")
    summary = {"round": 3, "scope": "PARTIAL_UNROUTED_CANDIDATE_NOT_FOR_FAB",
               "createdAt": datetime.now(timezone.utc).isoformat(),
               "sourceProjectUuid": PROJECT, "boards": {}, "overall": "BLOCKED"}
    model_report = {"scope": "Native model binding and export inspection only; no installed assembly or visual approval",
                    "projectUuid": PROJECT, "boards": {}}
    placement_rows = []
    for board, ids in IDS.items():
        ops = manifest["boards"][board]["operations"]
        dump = read(REVIEW / board / "fresh-board.json")
        components = dump["components"]
        drc = response(ops["drc"])
        check = response(ops["check"])
        lint = response(ops["lint"]).get("report", {})
        erc = response(ops["nativeErc"])
        models = response(ops["models"])
        assert len(components) == manifest["boards"][board]["candidateComponentCount"]
        assert not response(ops["list"]).get("incomplete"), f"{board}: list coverage incomplete"
        assert not drc["passed"]
        violations = drc.get("violations", [])
        assert len(violations) == drc["total"], f"{board}: missing raw DRC rows"
        assert collections.Counter(v["rule"] for v in violations) == collections.Counter(drc["counts"])
        assert len(models["components"]) == len(components)
        clock_pads = [(c["designator"], p) for c in components for p in c["pads"] if p.get("net") == "clk_48m"]
        clock_distances = []
        for (ref_a, a), (ref_b, b) in itertools.combinations(clock_pads, 2):
            clock_distances.append({"a": f"{ref_a}.{a['padNumber']}", "b": f"{ref_b}.{b['padNumber']}",
                                    "centerDistanceMm": math.hypot(a["x"] - b["x"], a["y"] - b["y"]) / MM})
        board_summary = {
            "pcbUuid": ids["pcb"], "schematicUuid": ids["sch"],
            "candidateComponentCount": len(components),
            "nonemptyUniqueIdCount": sum(bool(c.get("uniqueId")) for c in components),
            "schematicBindingStatus": "BLOCKED: no controlled schematic; nonempty unique IDs do not prove schematic binding",
            "nativeDrc": {"passed": drc["passed"], "total": drc["total"], "counts": drc["counts"],
                          "clearanceByObjectType": dict(collections.Counter(v["objType"] for v in violations
                                                                             if v["rule"].startswith("Clearance"))),
                          "binding": drc.get("binding"), "rawLog": ops["drc"]["log"]},
            "pcbCheck": {"passed": check["passed"], "summary": check["summary"],
                         "incomplete": check["incomplete"], "coverage": check["coverage"],
                         "limitations": check["limitations"], "rawLog": ops["check"]["log"]},
            "layoutLint": {"ok": lint.get("ok"), "incomplete": lint.get("incomplete"),
                           "summary": lint.get("summary"), "rawLog": ops["lint"]["log"]},
            "nativeErcOnUnrebuiltSheet": {"passed": erc["passed"], "summary": erc["summary"],
                                          "status": "EMPTY_SHEET_ONLY_NOT_CONTROLLED_ERC_PASS",
                                          "rawLog": ops["nativeErc"]["log"]},
            "outlineMm": [[x / MM, y / MM] for x, y in dump["outline"]["points"]],
            "rules": dump["rules"], "copperLayers": dump["copperLayers"],
            "authoredRoutingCopperCounts": geometry["boards"][board]["authoredRoutingCopperCounts"],
            "embeddedFootprintViaCount": len(geometry["boards"][board]["embeddedFootprintVias"]),
            "requiredButNotPlaced": geometry["boards"][board]["requiredButNotPlaced"],
            "offlineFailedPlacements": geometry["boards"][board]["offlineFailedPlacements"],
            "candidateGeometryStatus": geometry["boards"][board]["candidateGeometryStatus"],
            "reserveIntersections": geometry["boards"][board]["reserveIntersectionsWithin0_20Mm"],
            "minimumObservedSameSideBboxGapMm": geometry["boards"][board]["minimumObservedSameSideBboxGapMm"],
            "clockPadDistances": clock_distances,
            "auxiliaryActualSvg": ops["actualRender"]["log"].replace("07-actual-render.log", "actual-both.svg"),
            "officialStageSnapshot": {"imageValid": response(ops["stageSnapshot"]).get("imageValid", False),
                                      "rawLog": ops["stageSnapshot"]["log"],
                                      "status": "UNAVAILABLE_OR_HIDDEN_TAB; SVG is auxiliary readback rendering, not official canvas screenshot"},
            "mechanicalQualification": "BLOCKED", "rfQualification": "UNVERIFIED",
            "stackupAndImpedance": "BLOCKED", "manufacturing": "BLOCKED",
        }
        summary["boards"][board] = board_summary
        expected = {p["ref"]: p for p in plan["boards"][board]["placements"]}
        for component in components:
            source_ref = expected[component["designator"]]["sourceRef"]
            placement_rows.append({"board": board, "ref": component["designator"], "sourceRef": source_ref,
                "mpn": expected[component["designator"]]["mpn"],
                "bboxCenterXmm": (component["bbox"]["minX"] + component["bbox"]["maxX"]) / (2 * MM),
                "bboxCenterYmm": (component["bbox"]["minY"] + component["bbox"]["maxY"]) / (2 * MM),
                "layer": "TOP" if component["layer"] == 1 else "BOTTOM",
                "rotationDegrees": component.get("rotation"), "primitiveId": component["primitiveId"],
                "uniqueId": component.get("uniqueId", ""),
                "schematicBinding": "UNBOUND_CONTROLLED_NETLIST_CANDIDATE",
                "landPatternQualification": "UNVERIFIED",
                "placementScope": "PARTIAL_CANDIDATE_NOT_FOR_FAB"})
        model_board = {"bindingSummary": models["summary"], "autoGenerateModels": False,
                       "components": models["components"], "exports": {},
                       "assemblyFit": "BLOCKED", "previewVerified": False}
        for fmt, operation in manifest["boards"][board]["exports3d"].items():
            result = response(operation)
            path = export_path(operation)
            exists = path.is_file()
            entry = {"format": fmt, "exitCode": operation["exitCode"],
                     "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                     "exists": exists, "rawLog": operation["log"],
                     "status": result.get("status", "BLOCKED" if not exists else "UNVERIFIED"),
                     "modelCoverage": result.get("modelCoverage", "binding-only"),
                     "previewVerified": result.get("previewVerified", False)}
            if exists:
                entry.update({"bytes": path.stat().st_size, "sha256": sha(path)})
                assert entry["bytes"] == result["artifactSize"]
                assert entry["sha256"] == result["artifactSha256"]
                if fmt == "obj":
                    with zipfile.ZipFile(path) as package:
                        assert package.testzip() is None
                        entry["zipIntegrity"] = "PASS"
                        entry["members"] = [{"name": i.filename, "bytes": i.file_size} for i in package.infolist()]
            else:
                log = (ROOT / operation["log"]).read_text(encoding="utf-8")
                entry["error"] = next((line for line in log.splitlines() if "failed:" in line), "Native export failed")
                if board == "M-MAIN-L" and fmt == "step":
                    assert "exceeding the 20 MiB transport limit" in entry["error"]
            model_board["exports"][fmt] = entry
        model_report["boards"][board] = model_board
    summary["candidateTotal"] = len(placement_rows)
    assert summary["candidateTotal"] == 35
    summary["sourceInputAudit"] = {"baseline": source["baseline_commit"],
        "sourceTerminals": source["source_terminal_count"], "cadTerminals": source["cad_terminal_count"],
        "bomRows": source["bom_row_count"], "footprintStatusCounts": source["footprint_status_counts"],
        "evidence": "evidence/kicad-source-audit.json"}
    summary["controlledKicadErc"] = {"toolVersion": kicad["kicad"],
        "scope": "Actual controlled KiCad schematics, not EasyEDA empty sheets", "boards": kicad["board_results"]}
    summary["padAudit"] = {"exactSystemDeviceTypes": len(pad_audit["devices"]),
        "passed": pad_audit["passed"], "failed": pad_audit["failed"],
        "scope": "Pin-number/pad-number sets only; supplier land pattern, mask/paste, stock and assembly remain UNVERIFIED"}
    summary["nativeProject"] = "native/native-project-inspection.json"
    codex = read(ROOT / "evidence/codex-review/KIMI_NATIVE_REVIEW.json")
    summary["codexReview"] = {"evidence": "evidence/codex-review/KIMI_NATIVE_REVIEW.json",
                              "nativeReview": codex["native_review"], "manufacturing": codex["manufacturing"],
                              "commandTranscript": "evidence/codex-review/review-command.log"}
    summary["fabricationStatus"] = "BLOCKED"
    write(REVIEW / "REVIEW_SUMMARY.json", summary)
    write(ROOT / "3d/3D_AND_BINDINGS.json", model_report)
    with (ROOT / "layout/native-candidate-placement.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(placement_rows[0]))
        writer.writeheader()
        writer.writerows(placement_rows)
    pad_rows = []
    for device in pad_audit["devices"]:
        pad_rows.append({"auditReference": device["auditReference"], "mpn": device["mpn"],
            "padCount": device["padCount"], "pinPadSetStatus": device["pinPadSetStatus"],
            "nativePadGeometryAvailable": device["nativePadGeometryAvailable"],
            "cadReferences": ";".join(f"{r['board']}:{r['ref']}:{r['sourceRef']}" for r in device["cadReferences"]),
            "expectedPinNumbers": ";".join(device["expectedPinNumbers"]),
            "observedPadNumbers": ";".join(device["observedPadNumbers"]),
            "landPatternQualification": "UNVERIFIED",
            "scope": "Pin/pad number sets only; NOT supplier land-pattern, mask/paste, stock or assembly approval"})
    with (ROOT / "FOOTPRINT_AUDIT.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pad_rows[0]))
        writer.writeheader()
        writer.writerows(pad_rows)

    statuses = [
        {"id": "PASS-01", "status": "PASS", "item": "指定基线与源输入审计", "evidence": "evidence/kicad-source-audit.json"},
        {"id": "PASS-02", "status": "PASS", "item": "受控 KiCad 三板 ERC：每板 error/warning/exclusion 均为 0", "evidence": "evidence/kicad-native-workspace/kicad-verification.json"},
        {"id": "PASS-03", "status": "PASS", "item": "26 种精确系统 Device 的脚号集合与原生焊盘编号集合", "evidence": "evidence/pad-audit/native-pad-audit.json"},
        {"id": "PASS-04", "status": "PASS", "item": "35 件候选器件原生写入、保存、回读及有限几何审查；主板21、桥板10、右板4", "evidence": "layout/review-3/REVIEW_SUMMARY.json"},
        {"id": "PASS-05", "status": "PASS", "item": "原生工程 ZIP 与三板 PCB 文档；独立导入项目后35件器件、焊盘、包围盒、板框、基础规则回读一致", "evidence": "native/native-project-inspection.json"},
        {"id": "PASS-06", "status": "PASS", "item": "三板 OBJ、桥板与右板 STEP 的实际文件与 SHA256；仅已有模型绑定覆盖", "evidence": "3d/3D_AND_BINDINGS.json"},
        {"id": "FAIL-01", "status": "FAIL", "item": "原生 DRC：主板229、桥板66、右板25；Connection/Netlist/Clearance 均未清零", "evidence": "layout/review-3/REVIEW_SUMMARY.json"},
        {"id": "FAIL-02", "status": "FAIL", "item": "桥板 U8 与 J_BRIDGE_IN 底层预留区冲突；不得通过缩小预留区或降低0.20mm规则消除", "evidence": "layout/review-3/geometric-audit.json"},
        {"id": "FAIL-03", "status": "FAIL", "item": "pcb check 与 layout-lint：丝印、嵌入过孔、铺铜及不完整几何覆盖；未作为整板通过", "evidence": "layout/review-3/REVIEW_SUMMARY.json"},
        {"id": "BLOCK-01", "status": "BLOCKED", "item": "KiCad .kicad_sch 不能直接导入；受控网表原生重建因符号构建失败而未完成；未改版本号伪装转换", "evidence": "evidence/native-library/09a965e44457e53c-retry-01-symbol-build.log"},
        {"id": "BLOCK-02", "status": "BLOCKED", "item": "三板嘉立创 SCH 仅有图框；空页 ERC=0 绝不能替代受控 KiCad ERC；没有完整 SCH↔PCB 绑定", "evidence": "native/native-project-inspection.json"},
        {"id": "BLOCK-03", "status": "BLOCKED", "item": "桥板 U14/U_AVDD_WD、U10/U_AVDD_QUAL 在有界0.20mm全bbox搜索内无合法候选", "evidence": "layout/candidate-placement-plan.json"},
        {"id": "BLOCK-04", "status": "BLOCKED", "item": "140项封装映射未解决；26种焊盘编号 PASS 不等于供应商 land pattern、mask/paste 或装配资格", "evidence": "evidence/kicad-source-audit.json"},
        {"id": "BLOCK-05", "status": "BLOCKED", "item": "JBD 原厂显示/FPC资料、连接器实物与光机装配资料未齐；双目透明显示架构保留但未验证", "evidence": "../H03_PCB_INPUTS.md"},
        {"id": "BLOCK-06", "status": "BLOCKED", "item": "板厂6层2+2+2叠层、介质、阻抗、盲埋孔层跨、VIPPO、桥板0.50mm目标；未降低制造规则", "evidence": "evidence/board-rule-limitations.json"},
        {"id": "BLOCK-07", "status": "BLOCKED", "item": "主板 STEP 22,150,672 bytes 超过20MiB传输上限；保留OBJ，不删模型伪造STEP", "evidence": "3d/3D_AND_BINDINGS.json"},
        {"id": "BLOCK-08", "status": "BLOCKED", "item": "未编写信号/电源走线或独立过孔/铺铜；仅保留9个ESP32封装嵌入GND过孔；无合法布线或连通性完成声明", "evidence": "layout/review-3/geometric-audit.json"},
        {"id": "BLOCK-09", "status": "BLOCKED", "item": "40g未证明；镜腿内腔、铰链折叠、双电池、配重、鼻梁/耳后/太阳穴、近视/散光镜片适配、散热、RF、FPC弯折与声学孔未验证", "evidence": "../H03_PCB_INPUTS.md"},
        {"id": "BLOCK-10", "status": "BLOCKED", "item": "Codex review_kimi_return.py 的真实审核结论与制造状态；不得伪造.kicad_pcb/.kicad_sch回件", "evidence": "evidence/codex-review/KIMI_NATIVE_REVIEW.json"},
        {"id": "UNVERIFIED-01", "status": "UNVERIFIED", "item": "nRF5340、天线、馈线、匹配、USB/RF阻抗、SI/PI、热、功耗与结构实装；没有物理样机验证", "evidence": "layout/review-3/REVIEW_SUMMARY.json"},
        {"id": "UNVERIFIED-02", "status": "UNVERIFIED", "item": "官方画布截图受隐藏标签页限制；actual-both.svg 为辅助回读渲染，3D previewVerified=false", "evidence": "layout/review-3/REVIEW_SUMMARY.json"},
    ]
    write(ROOT / "VERIFICATION.json", {"baseline": source["baseline_commit"], "projectUuid": PROJECT,
        "scope": "EVT-1 native partial candidate handoff; dual transparent AR and 40g are retained targets, not achieved qualifications",
        "overall": "BLOCKED", "fabrication": "BLOCKED", "checks": statuses,
        "coreArchitectureChanged": False, "fabricationAuthorized": False,
        "rawLogsRetained": True, "fakeKiCadReturnFilesCreated": False})
    print(json.dumps({"candidateComponents": summary["candidateTotal"],
                      "drc": {b: d["nativeDrc"]["counts"] for b, d in summary["boards"].items()},
                      "geometry": {b: d["candidateGeometryStatus"] for b, d in summary["boards"].items()},
                      "archiveRestore": restore["nativeEditableRestoreReadback"],
                      "overall": "BLOCKED"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
