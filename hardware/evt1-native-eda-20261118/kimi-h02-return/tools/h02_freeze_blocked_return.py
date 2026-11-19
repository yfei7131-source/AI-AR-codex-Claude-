#!/usr/bin/env python3
"""Freeze the latest valid per-page evidence after two connector failures.

No EasyEDA calls are made. Mixed point-in-time page evidence is explicitly partial.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / "hardware/evt1-native-eda-20261118"
RETURN = PACKAGE / "kimi-h02-return"
OUT = RETURN / "partial-current-coherent"
PROJECT = "1f475f192d4be7445a42ac79ebc824fcc4a803375837a9318c923e3aa35fe737"
RUNS = [RETURN / "field-repair" / name for name in
        ("batch-20261119-221345", "batch-20261119-214834", "batch-20261119-213933",
         "batch-20261119-212811", "batch-20261119-212400")]
OUT.mkdir(parents=True, exist_ok=False)
for directory in ("pins", "connectivity", "bom", "verification"):
    (OUT / directory).mkdir()
manifest = json.loads((RETURN / "working-before/board_pages.json").read_text(encoding="utf-8"))
plan = json.loads((RETURN / "repair-plan.json").read_text(encoding="utf-8"))
pages = [(board, page) for board, values in manifest["boards"].items() for page in values]
selected = {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_json(path, predicate):
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        return predicate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError):
        return False


def copy_evidence(board, page, list_path, conn_path, bom_path, source, saved):
    targets = {"pins": list_path, "connectivity": conn_path}
    for kind, path in targets.items():
        shutil.copyfile(path, OUT / kind / f"{page}.stdout.json")
    bom_copied = False
    if bom_path is not None:
        shutil.copyfile(bom_path, OUT / "bom" / f"{page}.csv")
        bom_copied = True
    selected[page] = {"board": board, "source": source, "sourceListSha256": sha(list_path),
                      "sourceConnectivitySha256": sha(conn_path), "nativeBomCopied": bom_copied,
                      "savedTrueEvidence": saved}


for board, page in pages:
    chosen = None
    for run in RUNS:
        summary_path = run / "summary.json"
        if not summary_path.is_file():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if page not in summary.get("pageResults", {}):
            continue
        list_path = run / "after" / f"{page}.stdout.json"
        conn_path = run / "connectivity" / f"{page}.stdout.json"
        bom_path = run / "bom" / f"{page}.csv"
        if valid_json(list_path, lambda d: d.get("ok") is True and isinstance(d.get("result", {}).get("components"), list)) and \
           valid_json(conn_path, lambda d: d.get("documentId") == page and not d.get("captureErrors")) and bom_path.is_file():
            chosen = (list_path, conn_path, bom_path, str(run.relative_to(RETURN)), True)
            break
    if chosen is None and page == "d643a0611d67a31a":
        list_path = RETURN / "field-repair/recovery-d643/preflight" / f"{page}.stdout.json"
        conn_path = RETURN / "field-repair/recovery-d643/connectivity" / f"{page}.stdout.json"
        saved_path = RETURN / "field-repair/batch-20261119-214834/save" / f"{page}.stdout.json"
        saved = valid_json(saved_path, lambda d: d.get("result", {}).get("saved") is True)
        if valid_json(list_path, lambda d: d.get("ok") is True) and valid_json(conn_path, lambda d: d.get("documentId") == page):
            chosen = (list_path, conn_path, None, "field-repair/recovery-d643", saved)
    if chosen is None:
        chosen = (RETURN / "working-before/pins" / f"{page}.stdout.json",
                  RETURN / "working-before/connectivity" / f"{page}.stdout.json",
                  RETURN / "working-before/bom" / f"{page}.csv", "working-before", True)
    copy_evidence(board, page, *chosen)

# A native BOM export is board-scoped, not strictly single-page. For boards with
# post-repair exports, reuse one coherent board snapshot verbatim on each of its
# verifier page inputs instead of mixing different MPN states. Bridge d643 has
# no post-repair BOM, so its missing export remains visible rather than backfilled.
coherent_boms = {
    "M-AUD-R": RETURN / "field-repair/batch-20261119-221345/bom/07dc7dde94c1bf76.csv",
    "M-MAIN-L": RETURN / "field-repair/batch-20261119-214834/bom/35d0bca337813128.csv",
}
for board, source in coherent_boms.items():
    content = source.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    lines = content.decode(encoding).splitlines()
    rows = list(csv.DictReader(lines, delimiter="\t" if "\t" in lines[0] else ","))
    observed_refs = {ref.strip() for row in rows for ref in row["Designator"].replace(";", ",").split(",") if ref.strip()}
    allowed_refs = {r["cadReference"] for r in plan["records"] if r["board"] == board}
    if observed_refs - allowed_refs:
        raise RuntimeError(f"BOM is not board-scoped for {board}: {sorted(observed_refs - allowed_refs)}")
    for page in manifest["boards"][board]:
        target = OUT / "bom" / f"{page}.csv"
        shutil.copyfile(source, target)
        selected[page].update({"nativeBomCopied": True, "nativeBomSource": str(source.relative_to(RETURN)),
                               "nativeBomSha256": sha(source), "nativeBomReuse": "same board-scoped snapshot, bytes unchanged"})
for name in ("lceda-boards", "lceda-pages"):
    shutil.copyfile(RETURN / "working-before" / f"{name}.stdout.json", OUT / f"{name}.stdout.json")
shutil.copyfile(RETURN / "working-before/board_pages.json", OUT / "board_pages.json")

spec = importlib.util.spec_from_file_location("compare", RETURN / "tools/h02_compare_restoration.py")
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)
terminal_differences = []
terminal_counts = {}
nc_differences = []
nc_expected = 0
for board, page in pages:
    before_conn = json.loads((RETURN / "working-before/connectivity" / f"{page}.stdout.json").read_text(encoding="utf-8"))
    current_conn = json.loads((OUT / "connectivity" / f"{page}.stdout.json").read_text(encoding="utf-8"))
    before_terms = compare.terminal_map(before_conn)
    current_terms = compare.terminal_map(current_conn)
    terminal_counts[board] = terminal_counts.get(board, 0) + len(current_terms)
    for difference in compare.differences(before_terms, current_terms):
        terminal_differences.append({"board": board, "pageUuid": page, **difference})
    before_list = json.loads((RETURN / "working-before/pins" / f"{page}.stdout.json").read_text(encoding="utf-8"))["result"]
    current_list = json.loads((OUT / "pins" / f"{page}.stdout.json").read_text(encoding="utf-8"))["result"]
    def nc_map(result):
        return {(c.get("designator"), str(p.get("pinNumber"))): p.get("noConnected")
                for c in result["components"] for p in c.get("pins", [])}
    before_nc = nc_map(before_list)
    current_nc = nc_map(current_list)
    nc_expected += sum(value is True for value in before_nc.values())
    if before_nc != current_nc:
        nc_differences.append({"board": board, "pageUuid": page})

components_by_page = {}
for _, page in pages:
    raw = json.loads((OUT / "pins" / f"{page}.stdout.json").read_text(encoding="utf-8"))
    components_by_page[page] = {c.get("primitiveId"): c for c in raw["result"]["components"]}
mpn_missing = []
mpn_matches = 0
flag_mismatches = []
for record in plan["records"]:
    component = components_by_page[record["pageUuid"]].get(record["primitiveId"], {})
    expected_mpn = record["controlled"]["mpn"]
    if expected_mpn:
        if component.get("manufacturerId") == expected_mpn:
            mpn_matches += 1
        else:
            mpn_missing.append({"board": record["board"], "cadReference": record["cadReference"],
                                "pageUuid": record["pageUuid"], "primitiveId": record["primitiveId"],
                                "expectedLength": len(expected_mpn), "observed": component.get("manufacturerId"),
                                "source": selected[record["pageUuid"]]["source"]})
    if component.get("addIntoPcb") is not record["controlled"]["addIntoPcb"]:
        flag_mismatches.append({"board": record["board"], "cadReference": record["cadReference"],
                                "expected": record["controlled"]["addIntoPcb"],
                                "observed": component.get("addIntoPcb")})

communication = {
    "status": "BLOCKED_TWO_ATTEMPTS_FAILED", "projectUuid": PROJECT,
    "pageUuid": "bbbca101b360e299", "operation": "read-only full sch list preflight",
    "attemptCount": 2, "retryCount": 1,
    "attempts": [
        {"response": "field-repair/batch-20261119-221345/preflight/bbbca101b360e299.stdout.json",
         "id": "req_1302", "createdAt": "2026-11-19T14:19:13.5858401Z"},
        {"response": "field-repair/recovery-bbb-list.stdout.json", "id": "req_1309",
         "createdAt": "2026-11-19T14:30:21.0425735Z"},
    ],
    "error": {"code": "DISPATCH_FAILED", "message": "connector did not respond", "detail": "context deadline exceeded"},
    "healthAndConnectorLogs": ["field-repair/recovery-bbb-health.json", "field-repair/recovery-bbb-connector-logs.json"],
    "actionTaken": "Stopped all EDA-dependent work. No board binding, ERC, reload, final capture or final archive export was attempted after this block.",
    "newWriteOnFailedPageInLastRun": False,
}
(RETURN / "COMMUNICATION_BLOCKED.json").write_text(json.dumps(communication, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

commands = [
    ["python", str(RETURN / "tools/h02_materialize_verification_tree.py"), str(OUT)],
    ["python", str(PACKAGE / "closure/verify_eda_return.py"), "--source", str(PACKAGE),
     "--schematic", str(OUT), "--output", str(OUT / "verification/pr31-partial-verification.json")],
]
ledger = []
for command in commands:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
    ledger.append({"command": command, "exitCode": completed.returncode,
                   "stdout": completed.stdout, "stderr": completed.stderr})
(OUT / "verification/command-ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
verification = json.loads((OUT / "verification/pr31-partial-verification.json").read_text(encoding="utf-8"))
summary = {
    "status": "BLOCKED_PARTIAL_NOT_H02_ACCEPTANCE", "projectUuid": PROJECT,
    "captureModel": "Latest valid available native readback per page; not a simultaneous final capture and not save/reload-qualified.",
    "selectedPages": selected, "terminalCounts": terminal_counts, "terminalTotal": sum(terminal_counts.values()),
    "terminalDifferencesFromInitiallyVerifiedRestoration": terminal_differences,
    "expectedNcFromInitiallyVerifiedRestoration": nc_expected, "ncDifferences": nc_differences,
    "controlledMpnRequired": 233, "directNativeListMpnExactMatches": mpn_matches,
    "directNativeListMpnMissingOrMismatch": mpn_missing,
    "externalPcbFlagMismatches": flag_mismatches,
    "footprintStatus": "BLOCKED_NOT_FULLY_RECHECKED_AFTER_COMMUNICATION_FAILURE",
    "strictErcStatus": "BLOCKED_NOT_RUN_THIS_ROUND", "boardBindingStatus": "BLOCKED_NOT_ATTEMPTED_AFTER_COMMUNICATION_FAILURE",
    "finalSaveReloadStatus": "BLOCKED_NOT_RUN", "modifiedNativeArchiveExported": False,
    "partialVerifierStatus": verification["status"], "partialVerifierExitCode": ledger[-1]["exitCode"],
}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
blocked = {
    "status": "BLOCKED_H02_NOT_CLOSED", "communication": communication,
    "hierarchy": json.loads((RETURN / "hierarchy/hierarchy-capability.json").read_text(encoding="utf-8")),
    "remainingMpnFromLatestAvailableLists": mpn_missing,
    "footprints": {"status": "BLOCKED", "initiallyMissing": 114,
                   "finalCountUnavailable": True, "reason": "No final full BOM capture or native footprint rebind/pad qualification was possible after the communication stop."},
    "strictErc": {"status": "BLOCKED", "reason": "No new native strict ERC was run before the communication stop."},
    "boardBinding": {"status": "BLOCKED", "reason": "No SCH/PCB binding mutation was attempted after the communication stop."},
    "finalPersistenceAndArchive": {"status": "BLOCKED", "modifiedArchiveExported": False,
                                   "saveReloadAllModifiedPages": False},
    "formalPcb": {"status": "OUT_OF_SCOPE_NOT_RUN", "layoutRoutingDrc": False},
}
(RETURN / "BLOCKED.json").write_text(json.dumps(blocked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
backup = json.loads((RETURN / "backup/backup-summary.json").read_text(encoding="utf-8"))
lines = [
    "# EVT-1 H02 部分回件（通信阻断，未闭环）", "",
    "**状态：BLOCKED。此回件不是 H02 验收通过，也不是修改后最终原生工程归档。**", "",
    "## 阻断", "",
    "右板页面 `bbbca101b360e299` 的只读完整预检连续两次返回 `DISPATCH_FAILED: connector did not respond / context deadline exceeded`。按任务规则，两次后已停止所有 EDA 依赖操作，未继续板关联、ERC、保存重载或最终导出。原始回执见 `COMMUNICATION_BLOCKED.json` 所列文件。", "",
    "## 真实保留成果", "",
    f"- 原工程原生备份：`backup/{backup['archive']}`，{backup['archiveBytes']} bytes，SHA-256 `{backup['archiveSha256']}`；这是修改前备份，不含本轮修复。",
    f"- 工作副本 UUID：`{PROJECT}`；修改后 `.epro2` 因通信阻断未导出。",
    f"- 最新可用逐页原生清单直接对账：233 项受控 MPN 中 {mpn_matches} 项精确匹配，其余 {len(mpn_missing)} 项仍未恢复或所在页尚未处理。",
    f"- 外部器件入板标志：当前所选原生清单差异 {len(flag_mismatches)} 项。",
    f"- 端子：{sum(terminal_counts.values())}；相对最初已验证恢复状态的差异 {len(terminal_differences)}；NC 基线 {nc_expected}，差异 {len(nc_differences)}。",
    "- 上述是各页最新可用证据的组合，不是同一时刻全工程回读，也未完成修改页 save→reload 验收。", "",
    "## 明确未完成", "",
    "- 21 页正确层级、跨页板级连接与 BAT1 三板隔离仍 BLOCKED；没有安全 typed page-move，BAT1 未改名。",
    "- 三板 SCH／PCB 新关联未在本轮执行；原有关联合错误仍未修复。",
    "- 本轮 21 页原生严格 ERC 未运行；不得引用旧检查代替。",
    "- 114 项封装字段的最终数量未重新全量确认；未使用文本伪造封装或批量重铸器件。",
    "- 修改后原生工程归档、最终三板网表、现状 PCB dump 和保存重载后全量对账均未生成。",
    "- 正式 PCB 布局、布线、DRC、制造与实物验证不在本轮完成范围内。", "",
    "## 证据结构", "",
    "- `backup/`：真实原工程 `.epro2` 备份与原始保存／导出回执。",
    "- `working-before/`：21 页修改前完整采集和 PR31 基线对账。",
    "- `field-repair/`：逐项真实 typed 修改、保存、BOM、失败及恢复记录；所有失败目录保留。",
    "- `partial-current-coherent/`：最新可用页面证据、来源 SHA-256、部分 PR31 校验及真实退出码。",
    "- `hierarchy/`：18 个游离子页和接口缺失证据。",
    "- `COMMUNICATION_BLOCKED.json`、`BLOCKED.json`：通信停止及剩余工作清单。",
]
(RETURN / "H02_RETURN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"status": summary["status"], "mpnMatches": mpn_matches, "mpnRemaining": len(mpn_missing),
                  "terminalTotal": sum(terminal_counts.values()), "terminalDifferences": len(terminal_differences),
                  "ncExpected": nc_expected, "ncDifferences": len(nc_differences),
                  "flagMismatches": len(flag_mismatches), "partialVerifier": verification["status"],
                  "partialVerifierExitCode": ledger[-1]["exitCode"]}, ensure_ascii=False, indent=2))
