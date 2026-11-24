# 智元跃动 EVT-1 H03 — `controlled_baseline_eco_h02_to_r7.patch` 真实数据预检与修正证据（PR #58 / #55 / neon-round3）

> **审核范围**：PR #58（`hardware/evt1-h03-r8-codex-20261124`，Commit `1b69c06`）、PR #55（`hardware/kimi-evt1-h03-r7-20261123`，Commit `ac38a71`）原始网表/审计文件，以及 `hardware/research/neon-round3-20261124/neon-1`（位于 PR #59 源分支 `hardware/research/neon-round3-20261124`）。  
> **红线遵守**：**未使用任何重建 JSON 代替原始输入**，不重复 1075→1076 理论分析，不直接修改受控基线，不上传 GitHub，保持 `NOT FOR FAB`。

## 1. 对旧版补丁（`neon-round3/neon-1`）的 3 项真实缺陷检出与 v2 修正

通过远程浏览器直接核对 PR #55 原始文件 [`M-MAIN-L-r7.net`](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/final/M-MAIN-L-r7.net)、[`M-AUD-R-r7.net`](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/final/M-AUD-R-r7.net) 及 [`h02-native/catalog-plan.json`](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h02-native/catalog-plan.json)，检出旧版补丁存在以下 **3 项实质问题**并已在 `controlled_baseline_eco_h02_to_r7_v2.patch` 中修正：

| 核查项 | 旧版补丁（`neon-round3/neon-1`）状态 | PR #55 原始文件实测证据 | v2 修正动作 |
| :--- | :--- | :--- | :--- |
| **1. `U11.F11` / `F12` 网络名** | **错误**：误带 `+` 前缀（`+LFXO_XL1` / `+LFXO_XL2`） | `M-AUD-R-r7.net`（第 3363–3372 行）原始网络名为 **`LFXO_XL1`** 与 **`LFXO_XL2`**（无 `+` 号） | v2 补丁 Hunk 3 已修正为 **`LFXO_XL1`** / **`LFXO_XL2`** |
| **2. `U12` 六引脚网络与封装** | 封装简写为 `DRY0006A`、状态写 `BLOCKED` | `M-MAIN-L-r7.net` 实测 `U12` 完整封装为 **`TI_DRY0006A_USON-6_1.45x1.0mm`**、`MPN=TPD2E001DRYR`、`Footprint Status=PASS`；6 脚精确网络：`1=USB_DP (IO1)`、`2=GND`、`3=USB_DM (IO2)`、`4=NC`、`5=VBUS_5V_USB (VCC)`（非 `VBUS_5V`）、`6=NC` | v2 补丁 Hunk 1 已按 `M-MAIN-L-r7.net` 逐字对齐 6 脚网络与封装名 |
| **3. `R10` 退役与 `catalog-plan.json` 一致性** | **缺口**：仅修改 `CAD_TERMINALS.csv`，未同步处理 `catalog-plan.json` | `run_controlled_sch_audit.py` 直接读取 `h02-native/catalog-plan.json`；该文件第 3271–3299 行仍含已删除的 `R10 (R_ESP_BOOT, 41bc0941336b1513)`（`M-MAIN-L-r7.net` 搜索 `R10-`/`R10_` 为 **0 匹配**），且第 4692–4721 行 `U12` 仍为 3 脚 `footprintPins: ["1","2","3"]` | 仅打 `CAD_TERMINALS.csv` 补丁仍会在 `run_controlled_sch_audit.py` 中报 `unresolvedComponents: [R_ESP_BOOT]`；已在 `run_isolated_patch_regression.sh` 中配套提供隔离 worktree 的 `catalog-plan.json` 同步逻辑（退役 `R10` + 更新 `U12` 6 脚） |

## 2. 补丁 Hunk 语法校验与隔离回归边界说明

- **Unified Diff 数学校验（已通过）**：`controlled_baseline_eco_h02_to_r7_v2.patch` 共 3 个 Hunk（`-231,7 +231,10`、`+3`；`-438,6 +441,4`、`-2`；`-959,6 +960,6`、`0`），行号计数与净行数增量（`+1`）100% 校验通过。
- **未能在离线沙箱内直接跑通全量 `.epro2` 回归的真实原因（如实报告，绝不用重建 JSON 替代）**：
  1. 本执行沙箱无外网且未挂载本地 Git 仓库及 `.epro2` 二进制归档，远程浏览器下载目录亦与沙箱隔离；
  2. 为严守“禁止使用重建 JSON 代替原始输入”，本次**未**用重建数据伪造 `run_controlled_sch_audit.py` 的回归通过结果；
  3. 请在本地仓库根目录下直接执行随包附带的 **`bash run_isolated_patch_regression.sh`**，脚本会自动创建临时 `git worktree`（**零触碰任何受控分支**）、执行 `git apply --check` + 隔离应用 + `catalog-plan.json` 同步 + 运行 PR #55 原生 `run_controlled_sch_audit.py` 对 3 份真实 `.epro2` 归档执行回归测试，并输出真实 `controlled-sch-audit.json` 对比（注：预期 `unresolvedComponents=[]`、`terminalDifference=[]`、`ncDifference=[]`，若 `archiveRawNCMarkers=94` vs `explicitNCCount=92` 仍存在 2 处归档原始 NC 标记差，将直接暴露以便定位具体图页对象）。
