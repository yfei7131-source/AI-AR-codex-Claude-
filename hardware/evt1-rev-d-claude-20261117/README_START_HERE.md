# 智元跃动 AI/AR 智能眼镜 V1.0 — EVT-1 Rev D 工程包（继承 Rev C `bb87623`）

**状态：`NOT_FOR_FAB`**。本包为原理图/PCB 前的电气网表与 RTL 级修复，不含可编辑原理图、PCB、Gerber、STEP 或实测数据。

## 先读
1. `00_Rev_D_Change_Record/REV_D_DEFECT_AND_FIX_LEDGER.md` — 21 项缺陷 → 修复 → 证据
2. `01_Architecture_and_Interfaces/KIMI_ENGINEERING_HANDOFF_V1_1_REV_D.md` — KIMI / Codex / 固件执行项
3. `04_Verification_Evidence/rev_d_verification_report.txt` — 本轮实际执行结果

## 目录
- `00_Rev_D_Change_Record/`：缺陷台账、数据手册证据台账（含未验证假设清单）、`DIFF_RevC_to_RevD.patch`
- `01_Architecture_and_Interfaces/`：ICD Rev D、KIMI 手册 V1.1、系统预算 JSON（含质量账目）、CHANGELOG、SoC 方案对比（未改动）
- `02_BOM_PINMAP_ICD_Blocked/`：BOM（54 行）、PINMAP、**NETLIST 电气连接表**、连接器逐针表、转换器分组表、ICD 表、阻断清单
- `03_FPGA_RTL/`：RTL、测试台（R1–R4）、PCF、仿真模型、Makefile（文件名和模块名不变，保证 CI 连续）
- `04_Verification_Evidence/`：Rev D 验证报告与 JSON 日志
- `05_Verification_Scripts/`：`verify_rev_d_electrical.py`（权威检查）、`rev_d_optctrl_protocol_model.py`
- `99_RevC_Baseline/`：Rev C 原始文件逐字保留，供追溯

## 验证摘要（本环境实际运行）
17 项通过 / 1 项阻断（RTL-03：iverilog、yosys、nextpnr、icetime 不可用，**Rev D Verilog 未编译、未仿真**）/ 1 项未关闭（MASS-01：41.0 g > 40 g）；故障注入 16/16 全部捕获。
这里的"通过"仅指对交付文件做的计算或结构检查，不代表实物测量结果。

## 同步说明
本包可直接覆盖仓库对应目录。修改说明见 CHANGELOG；改动明细见 `DIFF_RevC_to_RevD.patch`。
