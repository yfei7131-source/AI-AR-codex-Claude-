# Rev C P0 缺失文件与未提供资料清单

状态：`NOT_FOR_FAB`。本文件区分“源 ZIP 未携带、已由完整 bundle 恢复”和“外部资料仍缺失”。

## 已从完整 bundle 恢复

源 ZIP 只有 18 个文件；完整 bundle 的提交树为 20 个文件。以下 4 个 ZIP 未携带的文件已从 bundle HEAD `8697069…` 原样恢复，未自行编写：

1. `GITHUB_DRAFT_PR_INSTRUCTIONS.md`
2. `build_handoff_package.py`
3. `evidence/v1_0_verification_log.json`
4. `evidence/v1_0_verification_report.txt`

恢复后，bundle 提交树的 20 个文件均已进入仓库；其中 `.github/workflows/fpga_eda_ci.yml` 位于仓库根目录，其余 19 个位于 `hardware/evt1-rev-c-source-20261116/`。

## 已存在，不属于缺失

- `rtl/tb_evt1_ar_display_fpga_bridge_rev_c.v`（RTL testbench）
- `rtl/Makefile`
- `handoff_evt1_rev_c.bundle`（完整历史）
- `evidence/eda_toolchain_execution.log`（EDA 执行日志）
- RTL、SPRAM/EBR 模型、UWG30 PCF、BOM、PINMAP、ICD、验证脚本和验证报告

## 等待 CI 产生的原生输出

本地 EDA 日志仍记录 `iverilog`、`yosys`、`nextpnr-ice40`、`icetime` 未安装。GitHub Actions 已配置运行这些工具，但真实结果只能以 Actions 日志为准：

- `iverilog_sim.log`
- `yosys_synth.log`
- `nextpnr_uwg30.log`
- `evt1_ar_display_fpga_bridge_rev_c_sta.rpt`
- 综合 JSON 与 PnR ASC

在这些文件由 CI 实际生成并检查之前，不标记仿真、综合、PnR 或 STA 通过。

## 仍缺失的外部资料

- `EVT1_ID_TEMPLE_SHELL.stp`
- `JBD013VGA_STEP.stp`
- 原生 KiCad/EasyEDA 板文件、Gerber 和原生 CAD/DRC 结果
- JBD QSPI 初始化序列和受控 FPC 物理引脚定义
- 实物质量/重心、热、RF/SAR、电池脉冲压降和续航测试数据
- 量产 DFM、装配、测试夹具和认证资料

以上内容没有在本次同步中虚构或补造。
