# Rev C 缺失文件与未提供资料清单

状态：`NOT_FOR_FAB`。本文件只记录实际缺口，不从 Git bundle 补造、填充或推断缺失内容。

## ZIP 缺失但 Git bundle 中存在

Rev C ZIP 实际包含 17 个文件；bundle 提交树 `9a302e2c6ce01712b44a746b632b735e31890b57` 包含 19 个文件。按原路径比较，以下 4 个路径未包含在 ZIP 中：

1. `hardware/evt1-v1-kimi-handoff/GITHUB_DRAFT_PR_INSTRUCTIONS.md`
2. `hardware/evt1-v1-kimi-handoff/build_handoff_package.py`
3. `hardware/evt1-v1-kimi-handoff/evidence/v1_0_verification_log.json`
4. `hardware/evt1-v1-kimi-handoff/evidence/v1_0_verification_report.txt`

说明：

- ZIP 中存在 `v1_0_verification_report.txt`，但其内容哈希为 `d4d878b4…`，对应 bundle 根目录版本；
- bundle 的 `evidence/v1_0_verification_report.txt` 是另一份旧报告（`fbf15485…`），ZIP 未提供该路径；
- 上述 4 个文件没有用 bundle 内容回填到归档目录，只在本清单中标记缺失。

## ZIP 与 bundle 一致的部分

- ZIP 中 15 个工程文件与 bundle 提交树逐字节一致。
- `0001-evt1-rev-c-feasibility.patch` 和 `handoff_evt1_rev_c.bundle` 是 ZIP 额外提供的来源材料，不属于 bundle 提交树中的普通工程文件。
- 已存在，**不属于缺失文件**：
  - `tb_evt1_ar_display_fpga_bridge_rev_c.v`（RTL 测试台）
  - `Makefile`
  - `handoff_evt1_rev_c.bundle`（完整 Git bundle）
  - `eda_toolchain_execution.log`（EDA 执行日志）

## 原生工具输出缺失

`eda_toolchain_execution.log` 明确记录 `iverilog`、`vvp`、`yosys`、`nextpnr-ice40`、`icetime` 均未安装（exit 127）。因此以下原生输出不存在，不能伪造：

- `*_sim.vvp`、`iverilog_sim.log`
- `yosys_synth.log`、综合 JSON
- `nextpnr_uwg30.log`、`.asc`
- `*_sta.rpt` 与原生时序报告

RTL 仿真、综合、PnR 与 STA 均未完成。

## 外部依赖与实物资料缺失

源报告明确以下内容未提供：

- `EVT1_ID_TEMPLE_SHELL.stp`
- `JBD013VGA_STEP.stp`
- 原生 KiCad/EasyEDA 板文件、Gerber 与 3D DRC 结果
- 物理样机的质量、重心、热、RF/SAR、电池脉冲压降与续航实测数据
- 供应商 JBD QSPI 初始化序列和 FPC 物理引脚定义
- 量产 DFM、Gerber、装配和测试夹具资料

## 元数据说明

- 原 ZIP 没有 README 或正式文件清单；本归档新增 `SOURCE_MANIFEST.json`、`MISSING_FILES.md` 和 `ARCHIVE_STATUS.md` 作为校验记录，不改变 17 个原始文件的字节。
- 原始 Git 仓库目录未提供，仅提供完整 bundle；bundle 已验证通过，HEAD 为 `9a302e2…`。
