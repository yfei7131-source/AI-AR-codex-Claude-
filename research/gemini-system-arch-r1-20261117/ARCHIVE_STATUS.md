# EVT-1 系统架构 R1 — 归档状态

## 状态标记

`ARCHITECTURE REVIEW` / `ARCHIVED_SOURCE_ONLY` / `UNVERIFIED` / `NOT FOR FAB`

- R1 与 Codex **Rev D1（PR #21, `ff7ccf93`）**、Claude **光学 R0.1（PR #22）** 的全面对账**尚未完成**。
- 旧版器件、24P/16P 连接器、光机 `AVDD` 五态联锁决策**不得视为已冻结**，不得直接回退或覆盖现行 Rev D1 工程。
- 本目录仅为 Gemini 系统架构 R1 审查资料的独立研究归档，不构成任何投板、生产或电气签核依据。

## 基线与分支

- 基线：`hardware/evt1-rev-d1-20261117` @ `ff7ccf93fb6ebce289e6a262adcea4e77c8d4928`（PR #21）
- 本分支：`research/gemini-system-arch-r1-20261117`
- 独立归档目录：`research/gemini-system-arch-r1-20261117/`
- 不修改 `main`，不修改 PR #19–#23，不修改现行 Rev D1 / Claude R0.1 工程，不合并任何 PR。
- PR #23 已归档的 `94b50cf` 历史资料未被覆盖；本目录中的 `evt1_rev_c_94b50cf/` 仅为 R1 源包自带的上下文附件副本。

## 源包校验

- 原始外层包：`SYSTEM_RISK_AND_CONFLICT_REGISTER_R1.zip`
  - 大小：545,092 bytes；4 entries；CRC 测试通过
  - SHA-256：`758d4938823efdabc87629a120d510f26bcfdeec943bf22c0e9bd9fcebb428ce`
  - 注：执行同步期间该外层包在本地 Downloads 中被更新的 `R1_1` 批次替换；以上哈希为解压时实测值，解压内容已完整保留。
- 内层工程包：`ZY_AIAR_EVT1_SYSTEM_ARCH_R1_PACKAGE.zip`
  - 28 entries；CRC 测试通过；原包随归档保留于 `source_packages/`
- Git bundle：`handoff_evt1_rev_c.bundle`
  - HEAD：`94b50cf66c149f0b5a613edd8e15f18cd2a0eb15`
  - ref：`refs/heads/handoff/evt1-rev-c-feasibility-20261115`
  - `git bundle verify`：完整历史，bundle okay（在仓库上下文中验证）
- 差异补丁：`0001-evt1-rev-c-feasibility.patch`
  - `git apply --stat`：12 files changed, 171 insertions(+), 111 deletions(-)

## 未解决的设计冲突（摘要）

1. **D3 / AVDD 极性冲突**：R1 默认采用 `94b50cf` 的 D3 正脉冲（`1.000 μs` @ 60 Hz）峰值保持五态联锁；Rev D1 的 D3 低脉冲（空闲 1.80 V）会使 `C_HOLD` 死锁在 1.580 V，导致 VSYNC 停振看门狗（State 4）与配置失败联锁（State 2）失效。若强制采用低脉冲，必须改为 `C_AC=10nF` 交流耦合负边沿电荷泵，不得直接接入正向峰值保持电路。
2. **PR #21 / PR #22 文件不可得**：R1 文档记录 `BLOCKED_REPO_INACCESSIBLE`；本次已基于真实远端 `ff7ccf93` 建立分支，但 R1 文档内容本身尚未与 D1 / R0.1 源文件逐项核对。
3. **JBD 光机 NDA 缺失**：`BLK-JBD-01..04`（FPC pinout/极性、初始化寄存器 LUT、QSPI dummy clocks / 2×2 binning、AVDD 电压与 STEP）未签核，光机转接 FPC 与 `U6_OPT_AVDD` 电压选择继续阻断。
4. **连接器 / 电源架构**：R1 沿用 24P/16P BTB 与双电池电源树；与 Rev D1 的连接器及 30Pin/5A 电源触点方案尚未完成对账，不得直接替换。
5. **机械 / CAD / 实物**：无 ID 壳体 STEP、JBD STEP 与原生 DRC；34.75 g 重量、0.36 g 左右偏差、3.24 h 续航、37.2 °C 壳温均为分析估算，待首件实测。
6. **EDA 证据边界**：R1 文档记录生成时 EDA 二进制不可用；本仓库 PR #19 的 CI 已真实完成四项验证，但 R1 自身未在本分支运行新的 EDA 流程。

## 隐私边界

外层 ZIP 中的私人 Gemini 对话导出 Markdown 未上传，详见 `PRIVATE_RECORD_EXCLUSION.md`。
