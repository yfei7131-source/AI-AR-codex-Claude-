# `controlled_baseline_eco_h02_to_r7.patch` 真实数据预检、隔离验证与回归报告

- **核验范围**：仓库 [AI-AR-codex-Claude-](https://github.com/yfei7131-source/AI-AR-codex-Claude-) 中 [PR #58](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/58)、[PR #55](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55) 原始审计/网表记录与 [neon-round3 `neon-1`](https://github.com/yfei7131-source/AI-AR-codex-Claude-/tree/hardware/research/neon-round3-20261124/hardware/research/neon-round3-20261124/neon-1)
- **约束遵循**：未重建假 JSON 代替原始输入，不重复 `1075→1076` 理论推导，未修改受控基线，**未上传 GitHub**。

## 1. 真实数据预检与缺陷发现（逐项对照原始仓库文件）

通过远程浏览器直接读取分支 `hardware/kimi-evt1-h03-r7-20261123` 中的真实原始文件（`CAD_TERMINALS.csv`、`catalog-plan.json`、`M-MAIN-L-r7.net`、`M-AUD-R-r7.net`、`controlled_sch_audit.py`、`controlled-sch-audit.json`），并对 `controlled_baseline_eco_h02_to_r7.patch` 执行逐行上下文、网表与 catalog 回归校核，发现 **3 项实质阻断/缺陷**：

| 核查主题 | `neon-1` 原补丁内容 | 仓库真实原始数据核对结果 | 判定与处置 |
| :--- | :--- | :--- | :--- |
| **CSV 上下文与行号预检** | 3 个 hunk（`-231,7`、`-438,6`、`-959,6`） | 与真实 [CAD_TERMINALS.csv](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/kicad/CAD_TERMINALS.csv?plain=1) 第 `231–237`、`438–443`、`959–964` 行逐字节完全一致 | **PASS**（结构可直接 `git apply --check`） |
| **U11.F11 / F12 网络名** | `+LFXO_XL1` / `+LFXO_XL2` | 真实原始网表 `M-AUD-R-r7.net`（第 `3363–3374` 行）中为 **`LFXO_XL1`**（连 `Y3-1`、`C22-1`）与 **`LFXO_XL2`**（连 `Y3-2`、`C23-1`），**无 `+` 前缀** | **FAIL → 已在 v2 补丁修正**为 `LFXO_XL1` / `LFXO_XL2` |
| **U12 引脚 1–6 与网络** | 1:`USB_DP`、2:`GND`、3:`USB_DM`、4:`NC`、5:`VBUS_5V_USB`、6:`NC`（`DRY0006A`, `BLOCKED`） | 真实原始网表 `M-MAIN-L-r7.net` 逐字证实：`U12-1..3` 为 `USB_DP`/`GND`/`USB_DM`、`U12-5` 为 `VBUS_5V_USB`（同网 `U22-4`/`U22-6`/`J3-1`）、`U12-4/6` 无连接，引脚前缀为 `EVT1_U12_U12_ESD_USB_TPD2E001-*` | **PASS**（引脚与网络全部吻合；`FOOTPRINT` 顶部块受步数限制未展开，保持 `BLOCKED`） |
| **R10 退役与 `catalog-plan.json` 一致性** | 原补丁仅删 `CAD_TERMINALS.csv` 中 `R10` 两行，未修改 `catalog-plan.json` | 真实 [catalog-plan.json](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h02-native/catalog-plan.json)（`counts.boardComponents = 253`）仍保留 `R10`（`R_ESP_BOOT`，`captureUniqueId: "41bc0941336b1513"`，第 `3271–3299` 行），且 `U12`（第 `4692–4721` 行）仍为旧 3 脚 `"footprintPins": ["1", "2", "3"]` | **FAIL（catalog 不一致）**：不联动同步 `catalog-plan.json` 将导致 `controlled_sch_audit.py` 继续把 `R10` 报为 `unresolvedComponents` |
| **`controlled_sch_audit.py` 回归 PASS 门禁** | 预期补丁后审计通过 | 真实 [controlled_sch_audit.py](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/tools/controlled_sch_audit.py) 判定条件为 `not unresolved and terminals == controlled and markers == controlled_nc and archive_markers == len(markers)`；实测 [controlled-sch-audit.json](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/controlled-sch-audit.json) 中 `archiveRawNCMarkers = 94` 而 `explicitNCCount = 92` | **BLOCKED**：即便同步 CSV 与 `catalog-plan.json`，归档中 2 处位于 252 器件之外的孤立 `NO_CONNECT` 属性仍会导致 `status == "FAIL"`，需在原生原理图清理或核准 |

## 2. 联动同步 `catalog-plan.json` 的精确变更规范（不改受控基线，仅隔离执行）

在隔离工作树中应用 `controlled_baseline_eco_h02_to_r7_v2_verified.patch` 时，必须对 `hardware/evt1-native-eda-20261118/h02-native/catalog-plan.json` 同步执行以下 3 处精确更新（以消除 `R10` `unresolvedComponents` 并对齐 `U12` 6 脚）：

1. **移除退役器件 `R10`**：删除 `records` 中 `captureUniqueId == "41bc0941336b1513"`（`board: "M-MAIN-L"`, `cadReference: "R10"`, `sourceReference: "R_ESP_BOOT"`, 第 `3271–3299` 行）的条目；
2. **更新计数**：`counts.boardComponents` 由 `253` 更新为 `252`（并同步扣减 `counts.catalogActions.CLEAR_LEGACY_DESCRIPTOR_IF_LIVE_MATCHES` 计数 `-1`）；
3. **对齐 `U12` 引脚列表**：将 `captureUniqueId == "b6112465b0588c80"`（`U12_ESD_USB`，第 `4692–4721` 行）的 `footprintPins` 由 `["1", "2", "3"]` 更新为 `["1", "2", "3", "4", "5", "6"]`（`footprintSourceStatus` 与 `nativeBindingAction` 仍保持 `BLOCKED` / `KEEP_BLOCKED`）。

## 3. 隔离工作树本地实跑命令（严禁直接修改受控基线）

在已拉取仓库的本地环境执行以下命令，完成全量二进制 `.epro2` 隔离应用与 `controlled_sch_audit.py` 回归：

```bash
git worktree add /tmp/h03-eco-isolated hardware/kimi-evt1-h03-r7-20261123
cd /tmp/h03-eco-isolated
git apply --check /path/to/controlled_baseline_eco_h02_to_r7_v2_verified.patch
git apply /path/to/controlled_baseline_eco_h02_to_r7_v2_verified.patch
# 同步按第 2 节在隔离目录更新 h02-native/catalog-plan.json 后执行原生审计：
python3 hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/tools/run_controlled_sch_audit.py
# 验证完成后清理隔离工作树：
git worktree remove --force /tmp/h03-eco-isolated
```

## 4. 明确未闭合项与访问异常（BLOCKED）

1. **`BLOCKED-01`｜离线沙箱无法拉取二进制 `.epro2` 执行全量 `run_controlled_sch_audit.py`**：本轮已在沙箱对真实提取的 CSV 切片与网表真值完成零重建脚本校核（`eco_patch_verification_evidence.json`，全部 3 个 hunk 与 8 条网表真值均 `PASS`），但全量 `.epro2` 回归需在本地克隆仓执行上述隔离命令；另 `run_controlled_sch_audit.py` 与 PR #58 的 `h03-codex-r8-20261124/engineering/verification-summary.json` 在 GitHub 网页端均返回 HTTP 500 错误（且 PR #58 目录下无 `verification/` 子目录）。
2. **`BLOCKED-02`｜2 处孤立 `NO_CONNECT` 属性（`archiveRawNCMarkers: 94` vs `92`）**：未清理前 `controlled_sch_audit.py` 的 `archive_markers == len(markers)` 门禁仍为 `FAIL`。
3. **`BLOCKED-03`｜未上传 GitHub**：按要求仅交付本地验证补丁、原始测试证据与增量 ZIP。
