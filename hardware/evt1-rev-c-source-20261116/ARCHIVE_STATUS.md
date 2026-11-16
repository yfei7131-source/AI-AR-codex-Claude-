# EVT-1 Rev C 最新工程归档（2026-11-16）

- 状态：`ARCHIVED_SOURCE_ONLY` / `NOT_FOR_FAB`
- 分支：`handoff/evt1-rev-c-source-20261116`（PR #19）
- 外层 ZIP：`ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE gemini新输出.zip`，538,904 bytes；SHA-256 `0ea8ddc0489a42f95b62109b2bcc91af0794501b0415793a4e99333206cf8b01`
- 内层工程 ZIP：`ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE (1).zip`，486,375 bytes；SHA-256 `d41ceed708bb2e5c8bb0be2f1f30dce65a06b6cf866042194d7d15bc15831753`
- 指定校验提交：`bb876238fd25ac6be7c8f706b3d273b05d85a847`
- bundle HEAD：`bb876238fd25ac6be7c8f706b3d273b05d85a847`，其直接父提交为 `a678be1437b965ac83874138f28792202e0901a9`
- bundle SHA-256：`f5abcca84d1216015e329250b10d1c130a55c9c3d938c28b55a954dbb2b69886`

## 完整性

- `git bundle verify` 通过，bundle 记录完整历史；指定提交 `bb87623` 与其父提交 `a678be1` 均实际存在。
- 内层工程 ZIP 共 24 个条目：22 个 bundle 树文件（21 个工程文件与 1 个源 CI）、1 个 patch、1 个 bundle。
- 21 个工程文件与 bundle 树逐字节一致（Git blob 完全匹配，0 处不一致）。
- 源 CI 不重复落入归档目录：仓库根 `.github/workflows/fpga_eda_ci.yml` 使用适配后的归档路径，并保留显式 48 MHz PnR/STA 门槛。
- 外层 5 个有效 CSV/日志视图与内层工程内容在 CRLF 归一化后全部一致；Gemini 对话导出不纳入版本库。
- 23 个工程/来源文件的 SHA-256 见 `SOURCE_MANIFEST.json`。

## 本次更新

- 同步 `bb87623` 的光机 `U6_OPT_AVDD` 上电时序修复：改用 `1V8_OPT_VDD` 经 `R_SEQ=100kΩ + C_SEQ=220nF` 充电，并由 `D_SEQ (RB521S-30)` 肖特基钳位至 `FPGA_CRESET_B`，消除 0.006% 占空比 VSYNC 平均 0.108 mV 导致运行期 AVDD 关断的缺陷；`t_EN=13.64 ms`。
- 同步 `J_BTB_L` / `J_BRIDGE_IN` Pins 22..24 与 `J_BTB_R` Pins 10..12 的 3 线 I2S 1:1 直通映射，移除单脚截断。
- 同步 44 行 PINMAP、45 位号 BOM、5 总线 ICD、系统预算、KIMI 交接手册、验证脚本与 19/19 反向故障注入。
- RTL、PCF、测试台与 Makefile 相对 `a678be1` 未变化（Git blob 相同）。
- 保留 PR #19 既有归档目录、`ARCHIVE_STATUS.md`、`SOURCE_MANIFEST.json`、`MISSING_FILES.md` 及全部 Git 历史。

## 本次本地验证边界

- `python verify_v1_0_engineering.py`：6 PASS、5 BLOCKED、1 UNVERIFIED、0 FAIL；这些静态/模型结果不替代原生 EDA、CAD 或实物验收。
- 本地没有原生 EDA 工具；Icarus/Yosys/nextpnr/STA 结果只以 GitHub Actions 实际日志和 artifact 为准。
- 物理样机、3D STEP、原生 PCB DRC、JBD NDA ICD/FPC 与光学装配仍未验证。
- 工程仍为 `NOT_FOR_FAB`，不可据此投板或量产。

## 边界

- 保留 PR #19 全部历史，未覆盖其他分支。
- 未修改 `main`、Kimi R9 或其他独立研发分支。
- 未合并 PR。
