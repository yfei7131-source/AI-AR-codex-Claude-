# EVT-1 FPGA V2.1 工程归档（2026-11-14）

- 状态：`ARCHIVED_SOURCE_ONLY` / `SOURCE_CLAIMS_NOT_ACCEPTED_AS_VERIFIED` / `NOT_FOR_FAB`
- 仓库基线：`handoff/evt1-fpga-v2-20261114` @ `8d65c53a5320bf2e6b90b469828e565a71d4d7c7`（PR #14）
- 归档分支：`handoff/evt1-fpga-v21-20261114`
- 工程根目录：`evt1_ar_display_fpga_bridge_v2/`

## 归档范围

- 完整保留 V2.1 内层工程的 20 个文件，原始相对路径不变。
- 原始工程 ZIP：`source/evt1_ar_display_fpga_bridge_v2.zip`
- Gemini 交接正文：`source/gemini-export-..._2026-11-14 22_13_15.md`
- V2.0 保留在原路径，未覆盖：`hardware/evt1-id/research/2026-11-14-fpga-v2/`
- V2.0→V2.1 逐文件比较：`V2_0_TO_V2_1_DIFF.csv`
- 逐文件 SHA-256：`SOURCE_MANIFEST.json`

## V2.0→V2.1 差异

20 个工程文件中：

- `changed`：6
- `unchanged`：14
- `added`：0
- `removed`：0

变化的 6 个文件：

1. `rtl/binocular_scanline_engine.v`：11,080 → 11,226 bytes
2. `rtl/spram_framebuffer_ctrl.v`：4,154 → 4,118 bytes
3. `tb/dual_clock_rtl_event_sim.c`：24,532 → 24,677 bytes
4. `evidence/ast_resource_breakdown.json`：1,181 → 1,181 bytes，内容哈希变化
5. `evidence/evt1-ar-display-fpga-bridge-v2.bundle`：32,753 → 66,103 bytes
6. `evidence/rtl_dual_clock_test_log.txt`：0 → 657 bytes

## 原样保留的验证状态

- V2.1 测试日志现在包含 6 条 `[PASS]`，但它是来源附带的日志，不是本仓库重新执行的结果。
- `evidence/EDA_AND_RTL_VERIFICATION_REPORT.txt` 仍以 **V2.0** 为标题，并记录：
  - `iverilog`、`yosys`、`nextpnr` 均为 `NOT_INSTALLED (BLOCKED_ENV)`；
  - 原生综合、PnR、post-route STA 未运行；
  - 资源占用和 Fmax 为 AST/分析模型估算。
- `kimi_hw_handoff/BLOCKED_VS_VERIFIED_MATRIX.csv` 原样保留：
  - B06 JBD 私有寄存器、初始化序列和 FPC 线序仍为 `BLOCKED_EXTERNAL_NDA`；
  - B07 结构 STEP、双波导对准和真机热成像仍为 `BLOCKED_PHYSICAL_SAMPLE`；
  - B01–B05 的 `VERIFIED_*` 是来源声明，本轮没有独立复现。
- `PINMAP_EVT1_BRIDGE.csv` 原样保留；`VERIFIED_RTL_AND_PINMAP` / `VERIFIED_RTL_TIMING` 不等于板级或实物验证。

## 本轮实际执行范围

- 仅执行外层/内层 ZIP CRC、文件路径、交接 Markdown 可读性、文件哈希和 Git 隔离检查。
- 未运行 Verilog lint、仿真、综合、PnR、STA 或 C 模型编译。
- 未连接 JBD 光机，未取得 NDA ICD，未验证 FPC 或 PINMAP。
- 未进行电源、双电池、隐私互锁、热、EMC 或结构测试。

## 明确不宣称

- 不宣称 RTL 可综合、时序收敛或 6 个 `[PASS]` 已由本仓库复现。
- 不宣称 V2.1 已解决帧存、带宽、双目同步或 CRC 的所有工程问题。
- 不宣称 JBD 兼容、PINMAP 可投板、硬件功能正常、达到 40 g、可打样或可量产。
- V2.1 只作为来源成果归档，不能作为设计放行或制造依据。

## 边界

- 未修改 Kimi R8 工程或 R8 分支。
- 未修改 PR #14 及 V2.0 文件。
- 未修改 `main`，未合并任何 PR。
