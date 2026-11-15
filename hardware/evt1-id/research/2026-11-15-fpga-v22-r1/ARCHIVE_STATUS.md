# EVT-1 FPGA V2.2-r1 工程归档（2026-11-15）

- 状态：`ARCHIVED_SOURCE_ONLY` / `CLAIMS_NOT_VERIFIED` / `NOT_FOR_FAB`
- 基线：`handoff/evt1-fpga-v21-20261114` @ `65a9c32ee1e611270efc184b1e611364a2c8c2cd`（PR #15）
- 归档分支：`handoff/evt1-fpga-v22-r1-20261115`
- 上传目录：`evt1_ar_display_fpga_bridge_v2_2/`

## 归档来源

| 项目 | 值 |
| --- | --- |
| 交接 ZIP | `Gemini V2.2-r1 的 GitHub 同步交接包.zip` |
| 交接 ZIP 大小 | 100,291 bytes |
| 交接 ZIP SHA-256 | `3eb5602d0e07fae0f648247f0739e2d4a2b39c1f9caef190f7b201e964f79124` |
| 原始 Git HEAD | `77befa01d597d515d23368b5c89d4084e567ed73` |
| 原始 Git parent | `14d0a4ba58543d054f00af02cb872453c3e2accd` |
| 工程 bundle | `dist/evt1-ar-display-fpga-bridge-v2_2.bundle` |
| bundle 大小 | 49,272 bytes |
| bundle SHA-256 | `195ffa9f7db9c43d971c7bdd05c640bf82d24cdf0ece6e2ebcbd3c6d7f6f9611` |

交接包声明源文件名为 `gemini新输出.zip`，但该 ZIP 本体未包含在本次附件中。原始两提交历史和对应源码由完整 Git bundle 保留。

## 完整性校验

- ZIP CRC：通过。
- `MANIFEST_V2_2.json`：27 个文件的字节数和 SHA-256 全部匹配。
- payload 共 28 个文件，等于 27 个受控文件加 `MANIFEST_V2_2.json` 本身。
- `git bundle verify`：通过，bundle 记录完整历史，SHA-1 对象格式。
- bundle HEAD：`77befa01d597d515d23368b5c89d4084e567ed73`。
- bundle parent：`14d0a4ba58543d054f00af02cb872453c3e2accd`。
- bundle 提交树中 26 个源文件与 payload 逐字节一致；payload 额外文件仅为 `MANIFEST_V2_2.json` 和原始 bundle。
- 未遗漏任何 manifest 列出的源码、测试、Makefile、约束或证据文件。

## 保留的失败和验证证据

- `evidence/original_failures_v2_0/failure_1_c_sim_line520_drain_timeout.log`
- `evidence/original_failures_v2_0/failure_2_c_sim_line568_spram_pipeline_skew.log`
- `evidence/original_failures_v2_0/failure_3_rtl_and_tb_5_defects_audit.md`
- `evidence/EDA_AND_RTL_VERIFICATION_REPORT.txt`
- `evidence/rtl_dual_clock_test_log.txt`
- `evidence/tb_jbd_dual_bridge.vcd`
- `kimi_hw_handoff/BLOCKED_VS_VERIFIED_MATRIX.csv`
- `kimi_hw_handoff/EVT1_INTERFACE_FREEZE_DRAFT.csv`
- `kimi_hw_handoff/PINMAP_EVT1_BRIDGE.csv`
- `kimi_hw_handoff/R8_VS_EVT1_CONFLICT_LIST.csv`

## 验证边界

- 本轮只做 ZIP、清单、Git bundle、文件路径和 GitHub 同步校验。
- 没有运行 RTL 仿真、综合、PnR、STA、Verilog lint 或 C 模型重新编译。
- 来源 `rtl_dual_clock_test_log.txt` 是 `OFFLINE C99 RTL MODEL SELF-CHECK REPORT`，其中 `PASS` 属于来源声明；报告同时注明原生 Icarus/Yosys/nextpnr 为 `BLOCKED_NO_LOCAL_EDA_BINARY`。
- 原生 EDA 结果、时序收敛、硬件兼容性和可制造性均未验证。
- `VERIFIED_*` 和 `PASS` 标签原样保留，但不升级为本仓库验证结论。

## 已知剩余问题

1. RTL 仿真、综合、PnR 与 STA 仍未完成。
2. Makefile 管道退出码问题尚未在原生工具链下验证。
3. 40 g 结构/布局冲突和 JBD NDA ICD/FPC 引脚定义仍未闭环。
4. 原始 V2.0 缺陷日志仅作为历史证据保存，不表示 V2.2-r1 已由本仓库复现修复。
5. 本工程 `NOT_FOR_FAB`，不得用于投板或量产。

## 边界

- 未修改 Kimi R8 工程或 R8 分支。
- 未修改 PR #15、V2.1 或更早基线。
- 未修改 `main`，未合并任何 PR。
