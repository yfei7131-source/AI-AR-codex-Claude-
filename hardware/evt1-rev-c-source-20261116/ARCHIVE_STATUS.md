# EVT-1 Rev C P0 完整源码归档（2026-11-16）

- 状态：`ARCHIVED_SOURCE_ONLY` / `CI_PENDING` / `NOT_FOR_FAB`
- 基线：`handoff/evt1-rev-c-source-20261116` 上一提交 `c344f63d31c2a3e5bf78a58b4eeb08c8ebf6f687`（PR #19）
- 分支：`handoff/evt1-rev-c-source-20261116`
- 源 ZIP：`ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE.zip`（392,389 bytes；SHA-256 `513b6c99…`）
- bundle HEAD：`8697069b189aab419433639e4ea8c70baef05182`
- 用户指定提交：`43f2960979ff2e3f3906ac2ca3471a605ee1943e`（bundle HEAD 的父提交）
- bundle 父提交：`43f296…`，完整历史已验证。

## 版本关系

- ZIP 的 16 个对应工程文件与 bundle HEAD `8697069…` 在统一换行后逐字节一致。
- bundle HEAD 比用户指定的 `43f296…` 多一个 PR #19 TB/FIFO 修复提交；完整 bundle 同时保留这两个提交。
- 因此归档完整 bundle 与最新源码树，不丢失 `43f296…` 历史，也不静默降级到父提交。

## 导入结果

- 完整 bundle 的 20 文件树全部导入；其中 19 个进入 `hardware/evt1-rev-c-source-20261116/`，工作流进入仓库根 `.github/workflows/fpga_eda_ci.yml`。
- 源 ZIP 未携带的 4 个文件已从 bundle 原样恢复，见 `MISSING_FILES.md`。
- 原有扁平层构建文件已由 `rtl/` 与 `evidence/` 结构化目录取代；上一提交仍完整保留在 Git 历史中。
- 原始 patch 与最新完整 bundle 保留在归档根目录。
- 21 个工程/来源文件和 3 个校验元数据文件的 SHA-256 见 `SOURCE_MANIFEST.json`。

## CI 配置

- 工作流：`.github/workflows/fpga_eda_ci.yml`
- 实际工程路径：`hardware/evt1-rev-c-source-20261116/rtl`
- 使用 `YosysHQ/setup-oss-cad-suite@v3` 安装原生工具链。
- 依次执行 `make clean` 与 `make all`，即 iverilog/vvp、Yosys、nextpnr-ice40 和 icetime。
- 只在 GitHub Actions 真实执行日志产生后报告 PASS/FAIL；本文件不预判通过。

## 不可宣称

- 本地未安装 EDA 工具，未在本地完成 RTL 仿真、综合、PnR 或 STA。
- 物理质量/重心、热、RF/SAR、电池和光学装配仍未实测。
- 隐私联锁、板宽/SoC 空间、电池高度、JBD NDA ICD/FPC 和 3D STEP 仍未闭环。
- 工程仍为 `NOT_FOR_FAB`，不得据此投板、冻结 BOM 或量产。

## 边界

- 未修改 `main`、Rev B、Kimi R9 或 FPGA V2.2-r1。
- 未合并任何 PR。
- 本轮只做源码恢复、路径修正和 CI 配置，未修改 RTL/PCB 设计。
