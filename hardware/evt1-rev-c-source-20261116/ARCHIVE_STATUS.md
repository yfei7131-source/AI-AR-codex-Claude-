# EVT-1 Rev C 最新工程归档（2026-11-16）

- 状态：`ARCHIVED_SOURCE_ONLY` / `NOT_FOR_FAB`
- 分支：`handoff/evt1-rev-c-source-20261116`（PR #19）
- 源外层 ZIP：`BLOCKED_ITEMS_CHECKLIST.zip`，408,777 bytes；SHA-256 `9d1cd89e…`
- 内层工程 ZIP：`ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE.zip`，379,025 bytes；SHA-256 `420c6c6f…`
- bundle HEAD：`d15cc6f841282664be7dda37bb0111d83ad42e3d`
- bundle 父提交：`8697069b189aab419433639e4ea8c70baef05182`
- bundle SHA-256：`10cd6fcc…`

## 完整性

- `git bundle verify` 通过，bundle 为完整历史。
- bundle 提交树和工程 ZIP 均为 20 个文件，逐项内容一致，无缺失。
- ZIP 另有原始 patch 和完整 bundle。
- 21 个工程/来源文件的 SHA-256 见 `SOURCE_MANIFEST.json`。

## 本次更新

相对 PR #19 上一版本，更新 10 个文件，包括：

- `rtl/evt1_ar_display_fpga_bridge_rev_c.v`
- `rtl/tb_evt1_ar_display_fpga_bridge_rev_c.v`
- `verify_v1_0_engineering.py`
- `build_handoff_package.py`
- `GITHUB_DRAFT_PR_INSTRUCTIONS.md`
- 两处验证报告与日志
- 最新完整 bundle
- 源 CI 工作流

仓库根 `.github/workflows/fpga_eda_ci.yml` 保留分步执行逻辑，路径修正为 `hardware/evt1-rev-c-source-20261116/rtl`，48 MHz 约束未降低。

## 验证边界

- 原生 Icarus/Yosys/nextpnr/STA 由 GitHub Actions 真实执行；结果以 CI 日志为准。
- 本地未运行 EDA，也不以静态模型代替原生工具。
- 物理样机、3D STEP、原生 PCB DRC、JBD NDA ICD/FPC 与光学装配仍未验证。
- 工程仍为 `NOT_FOR_FAB`，不可据此投板或量产。

## 边界

- 保留 PR #19 全部历史，未覆盖其他分支。
- 未修改 `main`、Kimi R9 或其他独立研发分支。
- 未合并 PR。
