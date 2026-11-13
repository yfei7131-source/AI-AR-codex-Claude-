# CHANGELOG R1 → R2（2026-11-12）

## 实际输入
- `Claude_硬件_R1___R2_续话包.zip`（R1 工程、审查记录）
- `Codex_软件与固件交接包.zip`：**是打包工具 + 接口摘要 + board.c/.h 节选，不是源码包**（`AIAR_Codex_Software_Context_*.zip` 未生成）。`SOFTWARE_PATHS.txt` 列出的 100 个源码文件本轮一个也没读到（节选两个文件除外）。

## 修改
| ID | 文件 | 改动 |
|---|---|---|
| R2-F1 (P0) | `H02/evt0_core/gen/design.py` → 重生成 sch/sym/netlist/BOM | U3 BQ24072RGTR 15 脚 `SYSOFF`→`TD`；网络 `SYSOFF`→`CHG_TD`；R6 100k→**0R 接 GND**（终止使能）；TP8 `SYSOFF`→`CHG_ISET`（充电电流监测点）；删除运输模式说法 |
| R2-F2 | 同上 | 新增 R30/R31 4.7k（DNP）：GPIO43/44 预留为常电传感器 I2C 上拉位 |
| R2-F3 | 同上 | 新增 JP2 + R32 1k：台架强制 CAM_PWR_EN（默认开路）。原因：固件 `gl_board` 无 cam_pwr_en 字段，未改固件时相机不上电 |
| R2-F4 | `gen/gen_kicad.py` | 新增守卫：BQ2407x 料号与 15 脚功能必须对应、TD 不得悬空、不得出现 SYSOFF 网络；标题栏 R2 |
| R2-F5 (P1) | `tools/check_fw_compat.py` | 重写：解析 board.h 结构体槽位 + board.c 位置初始化（含 `{…}` 数组、`#if/#else` 分支）；退出码 0/2/1；输出 `fw_compat_report.md`、`pinmap_fw_crosscheck.csv` |
| R2-F6 | `H01/*` | 架构 R2、`HW_SW_COMPAT_MATRIX.csv`（新）、`F01_F22_trace.csv`（新，仅填有依据的行）、ICR-08…12（新）、功耗表、候选 BOM |
| R2-F7 | `H03/*`、`H05/*` | 布局规划表（新，非已放置封装）；T15 改为电池断开，新增 T16/T24/T30/T31/T32，T01 记录部分结果 |

## 数据手册核对（本轮在线读取 TI 文档查看器）
- BQ24072/73/74/75/79 引脚表：BAT 2,3｜CE 4｜EN2 5｜EN1 6｜PGOOD 7｜VSS 8｜CHG 9｜OUT 10,11｜ILIM 12｜IN 13｜TMR 14｜**15 = TD('72,'73) / ITERM('74) / SYSOFF('75,'79)**｜ISET 16｜TS 1 —— 与 R2 符号一致。
- TD：接 VSS 使能终止；仅启动时采样；内部约 285 kΩ 下拉；不得悬空。SYSOFF 仅 '75/'79，内部约 5 MΩ 上拉至 BAT。
- TI 应用笔记 SLUA947（BQ2407x pin 15 可选功能）结论相同。
- 来源：https://www.ti.com/lit/ds/symlink/bq24072.pdf （SLUS810）第 7 节、9.3.5.3、9.3.5.5。
- **未在线复核**：K_ISET、K_ILIM、OUT 跟随电压、TLV757P 压差、ESP32-S3 峰值电流等数值，沿用 R1 的 VERIFY 标记。

## 网表差异（R1→R2）
- 删除网络 `SYSOFF`（U3.15, R6.1, TP8.1）
- 新增 `CHG_TD`（U3.15, R6.1；R6.2=GND）
- `CHG_ISET` 增加 TP8.1
- `3V3`/`U0TXD`/`U0RXD` 增加 R30、R31（DNP）
- 新增 `CAM_PWR_FORCE`（JP2.2, R32.1）；`3V3` 增加 JP2.1；`CAM_PWR_EN` 增加 R32.2
- 器件 83→87，网络 63→64

## 命令与真实输出
见 `VERIFICATION_R2.json`。KiCad ERC / DRC / 实机：**NOT RUN**（环境无 KiCad、bash 无网络）。
