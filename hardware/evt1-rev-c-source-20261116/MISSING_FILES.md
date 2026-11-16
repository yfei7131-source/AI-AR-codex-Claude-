# Rev C 最新工程缺失资料清单

状态：`NOT_FOR_FAB`。本文件只记录未提供或尚未产生的资料，不虚构补齐。

## 工程源文件完整性

- 本次内层 ZIP 含 22 个文件：20 个完整工程树文件、1 个 patch、1 个完整 Git bundle。
- bundle 提交树 20 个文件与 ZIP 中对应文件全部一致，无内部源码缺失。
- 已存在且不属于缺失：
  - `rtl/evt1_ar_display_fpga_bridge_rev_c.v`
  - `rtl/tb_evt1_ar_display_fpga_bridge_rev_c.v`
  - `rtl/Makefile`
  - `rtl/ice40_spram_ebr_sim.v`
  - `rtl/ice40up5k_uwg30_rev_c.pcf`
  - `handoff_evt1_rev_c.bundle`
  - `evidence/eda_toolchain_execution.log`

## 待 GitHub Actions 产生的原生结果

本地没有 `iverilog`、`yosys`、`nextpnr-ice40`、`icetime`。以下结果只能以实际 CI 日志为准：

- Icarus Verilog 编译与仿真日志
- Yosys 综合日志与资源占用
- nextpnr-ice40 PnR 日志、ASC 和频率
- icetime STA 报告与 48 MHz 约束判定

在 CI 完成前不宣称任何一项通过。

## 仍缺失的外部资料

- `EVT1_ID_TEMPLE_SHELL.stp`
- `JBD013VGA_STEP.stp`
- 原生 KiCad/EasyEDA 板文件、Gerber 与原生 CAD/DRC 结果
- JBD QSPI 初始化序列与受控 FPC 物理引脚定义
- 实物质量/重心、热、RF/SAR、电池脉冲压降与续航测试数据
- 量产 DFM、装配、测试夹具与认证资料

以上内容没有在本次同步中虚构或补造。
