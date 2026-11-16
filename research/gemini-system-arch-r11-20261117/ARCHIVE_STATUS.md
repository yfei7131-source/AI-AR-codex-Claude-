# EVT-1 系统架构 R1.1 — 归档状态

## 状态标记

`ARCHITECTURE REVIEW` / `ARCHIVED_SOURCE_ONLY` / `UNVERIFIED` / `NOT FOR FAB`

- 本目录是 Gemini EVT-1 系统架构 **R1.1** 审查资料的独立研究归档，**不是最终冻结设计**。
- R1.1 文档明确声明：生成时**未能实际读取 PR #21（Rev D1）与 PR #22（Claude 光学 R0.1）源文件**，多处状态记录为 `BLOCKED_REPO_INACCESSIBLE`，因此**部分状态已过时**；本次同步不改变该事实，仅原样归档并标注。
- 本次同步在真实可访问的仓库中基于 PR #21 当前头 `ff7ccf93fb6ebce289e6a262adcea4e77c8d4928` 建立分支，但**未用 R1.1 文件覆盖 Rev D1**，也未修改 PR #19–#23 或 `main`。

## 基线与分支

- 基线：`hardware/evt1-rev-d1-20261117` @ `ff7ccf93fb6ebce289e6a262adcea4e77c8d4928`（PR #21，复核仍为 open/draft）
- 本分支：`research/gemini-system-arch-r11-20261117`
- 归档目录：`research/gemini-system-arch-r11-20261117/`
- 不合并任何 PR。

## 源包校验

- 外层 ZIP：`gemini新一轮输出.zip`
  - 大小：417,426 bytes；4 entries；CRC 测试通过
  - SHA-256：`253a014e956871574666d746e64c2df84069e0a234decc6d3fc06ba3cf4b4b7b`
  - 成员：1 份私人 Gemini 对话导出（已排除）、2 份 CSV、1 个内层工程 ZIP
- 内层 ZIP：`ZY_AIAR_EVT1_SYSTEM_ARCH_R1_1_PACKAGE.zip`
  - 7 entries；CRC 测试通过；原包保存在 `source_packages/`
- Git bundle：`handoff_evt1_rev_c.bundle`
  - HEAD：`94b50cf66c149f0b5a613edd8e15f18cd2a0eb15`
  - ref：`refs/heads/handoff/evt1-rev-c-feasibility-20261115`
  - `git bundle verify`：完整历史，bundle okay
- 差异补丁：`0001-evt1-rev-c-feasibility.patch`
  - `git apply --stat`：12 files changed, 171 insertions(+), 111 deletions(-)

## R1.1 相对 R1 的关键变化（文档声明）

- 撤销旧 `BQ24074RGTR`、`TPS63802DLAR`、`24-Pin BTB`、`34.75 g` 质量预算等项目的 `FROZEN` 标识，标记为 `DEPRECATED_IN_R1_1` 或 `RETRACTED_SUPERSEDED`，禁止回退到旧 Rev C 方案。
- FPGA 核心桥接标记为 `VALIDATED_SIM_ONLY__PENDING_CI`，不得覆盖 Rev D1。
- D3 极性与 AVDD 五态联锁仍为 `CONFLICT_IDENTIFIED`；若 Rev D1 保持低脉冲，需 `C_AC=10nF` 交流耦合负边沿电荷泵，并通过 6 项安全测试（当前均为 `UNVERIFIED_AWAITING_PROTOTYPE`）。
- JBD `BLK-JBD-01..04` 继续 `BLOCKED`。

## 未解决的设计冲突 / 阻断

1. R1.1 未读取 PR #21 / PR #22，BOM、PINMAP、NETLIST、FPC、光机与质量预算三方对账未完成，部分状态可能过时。
2. 旧器件、连接器、AVDD 联锁决策**未冻结**，且 R1.1 已明确撤销多项旧 `FROZEN` 标识。
3. D3 正脉冲 vs `Rev D1` 低脉冲与 AVDD 五态联锁不兼容，尚未定版。
4. JBD NDA 资料与 STEP 缺失，光机 FPC 与 AVDD 电压选择继续阻断。
5. 无 ID 壳体 STEP 与原生 CAD/Gerber DRC；重量、重心、功耗、RF、温升均为分析估算，待首件实测。
6. R1.1 文档记录本地 EDA 二进制不可用；本分支未运行新的 EDA 流程，不宣称新的 PASS。

## 隐私边界

外层 ZIP 中的私人 Gemini 对话导出 Markdown 未上传，详见 `PRIVATE_RECORD_EXCLUSION.md`。
