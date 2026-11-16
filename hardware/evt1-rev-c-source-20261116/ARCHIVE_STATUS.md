# EVT-1 Rev C 来源归档（2026-11-16）

- 状态：`ARCHIVED_SOURCE_ONLY` / `NOT_FOR_FAB`
- 基线：`handoff/evt1-v1-arch-kimi-handoff-20261115` @ `be429ea333e51126e7cf92553db56e69095f5927`（PR #18）
- 分支：`handoff/evt1-rev-c-source-20261116`
- 来源提交：`9a302e2c6ce01712b44a746b632b735e31890b57`（bundle HEAD）
- 父提交：`44b860b0c87a798f6ff47552b5171ce9e3d37598`

## 归档内容

- 原 ZIP 的 17 个文件按 ZIP 的实际扁平结构原样保存，文件名和字节未修改。
- 包含 RTL、RTL testbench、SPRAM/EBR 仿真模型、Makefile、UWG30 PCF、BOM、PINMAP、ICD、SOC 对比、系统预算、阻断清单、验证脚本与报告。
- 包含完整 Git bundle `handoff_evt1_rev_c.bundle` 和原始 patch `0001-evt1-rev-c-feasibility.patch`。
- 新增校验元数据：`SOURCE_MANIFEST.json`、`MISSING_FILES.md`、本状态文件。
- 17 个原始文件逐项 SHA-256 见 `SOURCE_MANIFEST.json`。

## 来源与完整性

- bundle：`git bundle verify` 通过，完整历史，HEAD `9a302e2…`，父提交 `44b860b…`，分支引用 `refs/heads/handoff/evt1-rev-c-feasibility-20261115`。
- bundle 提交树 19 个文件；ZIP 的 15 个对应工程文件与 bundle 逐字节一致。
- ZIP 额外包含 patch 和 bundle 本体；bundle 中有 4 个路径未包含在 ZIP 中，已列入 `MISSING_FILES.md`，未从 bundle 回填。
- 用户声明的附件文件名在 Downloads 中不存在；实际使用的新 Rev C 归档文件为 `ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE.zip`，其 bundle 与文件内容均确认属于 Rev C。来源 ZIP 哈希见清单。

## 验证状态（来自源报告，未被本仓库复核）

- 源报告自述：6 PASS、5 BLOCKED、1 UNVERIFIED、0 FAIL。
- `iverilog`、`vvp`、`yosys`、`nextpnr-ice40`、`icetime` 均未安装；原生 RTL 仿真、综合、PnR 与 STA 全部 `NOT_RUN`。
- 物理质量、重心、热、RF/SAR、电池实际特性与光学装配均未实测。
- 隐私 TLV7032 push-pull、板宽/7×7 mm SoC 空间、GRP3911040 11 mm 高度冲突、JBD NDA ICD/FPC 和 3D STEP 仍未闭环。
- 不得将该归档描述为架构冻结、验证通过、可打板或可量产。

## 边界

- 未覆盖 Rev B 文件或 PR #18 历史。
- 未修改 Kimi R9、FPGA V2.2-r1 或 `main`。
- 本轮仅归档，未运行 RTL 仿真、综合、PnR、STA、PCB DRC、Gerber 生成或任何实物测试。
