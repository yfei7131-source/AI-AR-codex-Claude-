# EVT-1 FPGA V2.0 工程归档（2026-11-14）

- 状态：`ARCHIVED_SOURCE_ONLY` / `SOURCE_CLAIMS_NOT_ACCEPTED_AS_VERIFIED` / `NOT_FOR_FAB`
- 仓库基线：`handoff/evt1-fpga-20261114` @ `1e3100bd39754ed58c61a008b4e6ed3a4a0e651b`（PR #13）
- 归档分支：`handoff/evt1-fpga-v2-20261114`
- 工程根目录：`evt1_ar_display_fpga_bridge_v2/`

## 归档范围

- 完整保留内层工程 ZIP 中的 20 个文件，包括 RTL、testbench、firmware driver、约束、脚本、证据和 Kimi 硬件交接表。
- 原始内层 ZIP：`source/evt1_ar_display_fpga_bridge_v2.zip`
- 原始 DOCX：`source/2026-11-14 21_19_56.docx`
- 所有工程文件按 ZIP 内原始相对路径保存，未修改源码、证据、失败日志或未验证标记。
- 逐文件 SHA-256 见 `SOURCE_MANIFEST.json`。

## 原样保留的未验证与失败证据

- `evidence/rtl_dual_clock_test_log.txt` 为 **0 字节空文件**，已原样保留。它不能作为测试通过证据。
- `evidence/EDA_AND_RTL_VERIFICATION_REPORT.txt` 明确记录：
  - `iverilog`、`yosys`、`nextpnr` 均为 `NOT_INSTALLED (BLOCKED_ENV)`；
  - 原生综合、PnR 和 post-route STA 未执行；
  - 报告中的 Fmax、资源占用和关键路径属于 AST/分析估算，不是原生 EDA 结果。
- `kimi_hw_handoff/BLOCKED_VS_VERIFIED_MATRIX.csv` 中：
  - B06 JBD 私有寄存器、初始化序列和 FPC 线序仍为 `BLOCKED_EXTERNAL_NDA`；
  - B07 结构 STEP、双波导对准和真机热成像仍为 `BLOCKED_PHYSICAL_SAMPLE`；
  - B01–B05 的 `VERIFIED_SOLVED` / `VERIFIED_CORRECTED` 是来源文档声明，本轮没有独立复现，不升级为仓库级验证结论。
- `PINMAP_EVT1_BRIDGE.csv` 中 `VERIFIED_RTL_AND_PINMAP` 和 `VERIFIED_RTL_TIMING` 同样属于来源声明；没有做板级连通性、信号完整性或实物验证。

## 本轮实际执行范围

- 仅执行 ZIP CRC、DOCX 可读性、文件哈希、路径隔离和 Git 归档检查。
- 未运行 Verilog lint、仿真、综合、PnR 或 STA。
- 未编译 C 模型或固件驱动。
- 未连接 JBD 光机、未获取 NDA 接口文件、未验证 FPC。
- 未进行电源、双电池、隐私互锁、热、EMC 或结构测试。

## 明确不宣称

- 不宣称 RTL 可综合或时序收敛。
- 不宣称 C testbench、RLE4 压缩率、总线占用率或双目 0 cycle 偏差已通过。
- 不宣称 JBD 光机兼容、PINMAP 可投板或硬件功能正常。
- 不宣称 EVT-1 V2.0 达到 40 g、可打样、可量产或通过任何认证。

## 边界

- 未修改 Kimi R8 工程或 R8 分支。
- 未修改 PR #13 既有文件。
- 未修改 `main`，未合并任何 PR。
