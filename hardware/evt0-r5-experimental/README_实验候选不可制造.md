# EVT-0 R5 /CHG_PGOOD_N 实验性布线候选 — NOT FOR FAB

**它不是正式的 R5 PCB，也没有通过原生 KiCad ERC/DRC。严禁用于投板/生产。**

- 依据：Codex R4 (`hardware/evt0-r4-review/`) 原生 DRC 的 58 未连接、12 孔径错误、3 封装库警告。
- 在 R4 备份上运行从 Claude 23:05 对话恢复的试布线器，经 ChatGPT 修复两处 NumPy 布尔量兼容问题后新增 9 段走线/1 个过孔，`/CHG_PGOOD_N` 自定义连接缺口 58→57；此数字**不是** KiCad DRC 结果。
- 试布线 PCB 放于 `evt0_core/evt0_core.kicad_pcb`，**绝不替换** `hardware/evt0-r4-review/H02/evt0_core/evt0_core.kicad_pcb`。
- 本目录含生成器原始恢复版本、补丁版本、分析工具与 Claude 23:40 的 `run_native_checks.sh`、`summarize_native.py`（后两者尚未在 KiCad 环境执行）。
- 后续工程师先运行官方 KiCad ERC/DRC，审查网络连通、跨层和工艺孔径，再决定是否将部分正确布线重新集成至新一轮正式工程。
- 禁止放松 DRU、修改 DNP/相机隐私门禁、直接输出生产 Gerber 作为验证替代。
