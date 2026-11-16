# EVT-1 Rev C 最新工程归档（2026-11-16）

- 状态：`ARCHIVED_SOURCE_ONLY` / `NOT_FOR_FAB`
- 分支：`handoff/evt1-rev-c-source-20261116`（PR #19）
- 外层 ZIP：`BLOCKED_ITEMS_CHECKLIST-gemini新输出.zip`，520,106 bytes；SHA-256 `f5c540eee1d27c57bc914fee2e88a6e2629470cd2ab29e23c4197c6f171cc6f9`
- 工程 ZIP：`ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE.zip`，468,858 bytes；SHA-256 `1f60591b06bd9973fb90805c45882031940b45fdaacaacba127b027f75778701`
- 指定校验提交：`dfcf8e113e1a67eb876eb6534ead04d4b3b382b5`
- bundle HEAD：`a678be1437b965ac83874138f28792202e0901a9`，其直接父提交为上述 `dfcf8e1`
- bundle SHA-256：`795230ebd56ca424249d89b31ddab40519af75be1d7bd1cab58c7cc86916c3b2`

## 完整性

- `git bundle verify` 通过，bundle 包含完整历史；`dfcf8e1` 与最新头 `a678be1` 均实际存在。
- 工程 ZIP 共 24 个文件：22 个 bundle 树文件（21 个工程文件与 1 个源 CI）、1 个 patch、1 个 bundle。
- 22 个树文件与 ZIP 逐项逐字节一致；`a678be1` 未再修改 `dfcf8e1` 的 RTL 或源 CI。
- 外层 4 个有效 CSV 视图与内层工程内容一致，其中 BOM 仅行尾不同；重复 ICD 副本和 Gemini 对话导出不纳入版本库。
- 23 个工程/来源文件与 PR 归档树比较为 22 个原始字节匹配、1 个仅行尾匹配、0 个内容差异。
- 23 个工程/来源文件的 SHA-256 见 `SOURCE_MANIFEST.json`。

## 本次更新

- 同步 `dfcf8e1` 的 48 MHz RTL 时序加固、测试台和 `ICD_FPGA_HOST_OPTICS_SPEC_REV_C.md`。
- 同步 `a678be1` 的 45 位号 BOM、40 行 PINMAP、5 总线 ICD、24-pin BTB、光机上电时序和跨表检查。
- 同步 KIMI 交接手册、变更记录、系统预算、阻断清单、验证脚本、原始报告、patch 与完整 bundle。
- 保留 PR #19 既有归档目录、`ARCHIVE_STATUS.md`、`SOURCE_MANIFEST.json`、`MISSING_FILES.md` 及全部 Git 历史。
- 根 `.github/workflows/fpga_eda_ci.yml` 使用实际目录 `hardware/evt1-rev-c-source-20261116`，分步运行四项原生工具，并显式拒绝低于 48 MHz 的 PnR/STA 结果。

## 本次本地验证边界

- `python -m unittest discover -s tests -v`：102 项通过，1 项因 Node.js 条件跳过。
- `python verify_v1_0_engineering.py`：6 PASS、5 BLOCKED、1 UNVERIFIED、0 FAIL；这些静态/模型结果不替代原生 EDA、CAD 或实物验收。
- 本地没有原生 EDA 工具；Icarus/Yosys/nextpnr/STA 结果只以 GitHub Actions 实际日志和 artifact 为准。
- 原始交付证据已恢复为与 bundle 一致的字节内容，本地验证不会伪写为上游原生 PASS。
- 物理样机、3D STEP、原生 PCB DRC、JBD NDA ICD/FPC 与光学装配仍未验证。
- 工程仍为 `NOT_FOR_FAB`，不可据此投板或量产。

## 边界

- 保留 PR #19 全部历史，未覆盖其他分支。
- 未修改 `main`、Kimi R9 或其他独立研发分支。
- 未合并 PR。
