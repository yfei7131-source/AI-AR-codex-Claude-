# 智元跃动 AI/AR V1.0 — R0.2 工程执行交接包
**版本**：AI-HANDOFF-R02-20261117-01  
**基于材料**：用户上传的《Claude研究输出.zip》  
**状态**：研究成果的结构化转译；**不是**已完成的 Rev D1 原理图/PCB、固件、FPGA RTL 或实验验证成果。

## 先看这段
核心产品目标：真实**双目透明** MicroLED + 光波导 AR；整机推进目标 **≤40 g**；轻量、高集成、低功耗、可制造。沿用现有 ESP32-S3 + nRF5340 + iCE40UP 作为**待核对的 Rev D1 研究基线**。不要未经原厂确认就替换 JBD 接口、删除 FPGA、编造引脚/寄存器、投板。

最重要的工程判断：Rev D1 的 10-pin J_DISP、显示帧缓存/连续扫描假设与第三方托管的 JBD 资料存在明显冲突。必须用 **JBD 官方接口确认 + EVK 点亮实测** 闭环；候选方案 P2（FPGA 只做逐眼片选/读回桥）是**提案**，并非批准实施的硬件变更。

## 使用顺序
1. `00_CONTEXT/AI_CANONICAL_CONTEXT.md`：交接时唯一的统一背景、状态与术语；
2. `00_CONTEXT/SOURCE_AUDIT_AND_CONFLICTS.md`：哪些有出处、哪些冲突/未确认；
3. `01_ENGINEERING/ARCHITECTURE_DECISIONS.md` 和 `INTERFACE_DRAFT_DO_NOT_FABRICATE.md`：方案与冻结边界；
4. `02_EXECUTION/WORK_BREAKDOWN.md`：任务依赖、验收标准和交付要求；
5. `02_EXECUTION/ECR_REGISTER.csv`、`BLOCKER_REGISTER.csv`、`EVT_TEST_MATRIX.csv`：机器可读台账；
6. `03_AI_PROMPTS/`：按 AI 分工直接复制执行；`MASTER_NEXT_TURN_PROMPT.txt` 可作为一键入口；
7. `04_QUALITY/RELEASE_GATES.md`：何时允许说“完成”；
8. `05_ORIGINAL_EXTRACTS/`：保留报告与可用对话的原文副本，复核时不要只看摘要。

## 重要限制
- 此次上传只有**一份研究文本和一份内含 HTML 的对话档案**；未直接上传原生 Rev D1 KiCad/FPGA/固件工程，也没有 R0.2 工程 ZIP。**不能声称本包已核对现行 GitHub HEAD、KiCad ERC/DRC 或运行 RTL CI。**
- 原对话档案标称 32 段，其中 **4 段有可读的实际会话，28 段导出失败**。有效会话索引见来源审计。
- 引用标签 `[SRC-R02]` 等代表**用户提交内容**，不是本包重新核查过的原厂文档；任何数字要先看证据级别。
- 用户要求不覆盖 Codex 维护的 Rev D1；所有 ECR 必须走独立分支、评审后再集成。
- 研发目标是 40 g，但用户对 Rev D1 的一次要求为 ≤39.5 g，以作为设计余量；42/43 g 只能是阶段性 EVT 检查点，不能偷换产品目标。
