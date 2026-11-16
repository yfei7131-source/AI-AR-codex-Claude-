# 智元跃动 AI/AR 智能眼镜 V1.0 — EVT-1 Rev C 审查资料包

**基线**：Gemini 提供的完整 Git bundle HEAD `bb876238fd25ac6be7c8f706b3d273b05d85a847`（简称 `bb87623`），后续于 `a678be1`。

**用途**：上传给无法连接 GitHub / 无法读取本地文件夹的 Claude，供其独立审查电气架构、供电与复位时序、BTB/FPC、双目光机接口、BOM/引脚映射、FPGA 和可制造性。

## 包内目录
- `01_Architecture_and_Interfaces/`：架构、光机 ICD、重量功耗、变更记录与 KIMI 交接说明。
- `02_BOM_PINMAP_ICD_Blocked/`：BOM、全器件 PINMAP、ICD、关键阻断清单。
- `03_FPGA_RTL/`：FPGA Verilog、测试台、管脚约束和构建文件。
- `04_Verification_Evidence/`：Gemini 原始自检报告和工具环境日志。
- `05_Verification_Scripts/`：工程一致性检查脚本。
- `SHA256SUMS.txt`：本压缩包内原始资料的哈希值。

## 审查警戒线
- 源文件中带 `FROZEN` 的命名仅是 Gemini 的版本标签，**不等于原理图/PCB 通过制造放行**。
- 原始 EDA 工具日志提示 Gemini 所在环境缺少原生 EDA 命令；GitHub 对更早 RTL 版本有 CI PASS 记录，但**这些不能证明本轮新增光机供电和跨板电气连线通过实物验证**。
- JBD 光机的完整 FPC 引脚、初始化/QSPI 与模拟偏置要求存在原厂资料阻断。
- 本包未包含真实可编辑的 EVT-1 原理图/PCB、Gerber、STEP 或实物测试结果。
- 当前工程属于 `NOT_FOR_FAB`，禁止把模型结果当作打样放行。
- 原始 Gemini 文档中的 Git 分支名可能与 PR #19 实际远端分支不一致，审查只以本包文件为输入，不应执行上传或分支修改。

## 给 Claude 的审查任务
请只基于这批可见源文件，以 P0/P1/P2 分级报告具体缺陷；每项附**文件路径、网络/位号、原因、可执行修复方案及尚需原厂验证的参数**。优先审查 FPGA CRESET_B/CDONE 与光机 AVDD 的先后关系、RC/肖特基钳位逻辑、复位/配置失败/掉电边界、JBD 未公开接口、BTB/FPC I2S 三线连通、双电池与 40g 结构预算。不得把资料中的公式及 PASS 声称当作实测证据。
