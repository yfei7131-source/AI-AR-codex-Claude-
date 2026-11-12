# AI/AR 眼镜 — Claude R1/R2 独立审查及 GitHub 交接

日期：2026-11-12。工程状态：**EVT-0 原理图草稿 R2；不能直接打样**。

## 1. 来源与可复现性
- 用户原始两次交付：`AIAR_HW_R1_20261111.zip`、`AIAR_HW_R2_20261112.zip`，从 `Claude输出内容.zip` 提取。
- R1: 83 件、63 网络；R2: 87 件、64 网络、23 种符号。
- 在隔离环境执行 R2 `H02/evt0_core/gen/gen_kicad.py`：退出码 0、自检 0 errors/0 warnings；`.kicad_sch`、`.kicad_sym`、netlist、BOM、pinmap、selfcheck SHA256 与交付版**逐字节一致**。
- 上述只是 Claude 自定义生成器的检查；**不是 KiCad ERC**。当前运行环境没有 `kicad-cli`，所以 ERC/DRC 未执行。
- R2 `.kicad_pcb` 只有 50×70mm 4 层外框及指导标注，**0 footprint、0 track/via**，不得称作布局完成。

## 2. 已改善
- BQ24072RGTR 的 15 脚已从 R1 错误 `SYSOFF` 改为 `TD`，经 R6=0 Ω 到 GND，用于启用终止充电。TI 参考：https://www.ti.com/lit/ds/symlink/bq24072.pdf
- R2 增加了台架 JP2/R32 摄像电源使能、R30/R31 DNP 以及固件 GPIO 对照工具；这并不等于实机验证通过。
- R2 对 `board.c/.h` **节选**的相机与按键 15 个定义核对均匹配 Espressif EYE v2.2 参考 profile；未审核其他硬件功能的 GPIO。

## 3. P0 阻断项
**P0-A 隐私与真实采集：** GitHub `main` 和在途硬件 PR #1 的 EYE / S3-CARRIER-A profile 均保留 `privacy_interlock_verified=false`。当前 `camera_adapter.c` 将拒绝真实摄像。R2 H05 `T21` 原文“Codex firmware unmodified, JP2 closed”无法达到拍摄目标；JP2 只是供电强制跳线，不等于固件隐私门禁通过。验证前禁止置 true 或绕过。

**P0-B 音频接口：** R2 J7 只有 VSYS、3V3、GND、BT_AUD_EN，未包含与经典蓝牙 HFP/A2DP SoC 的控制/状态、音频数据连接；F03 未闭环。应先选 SoC、明确 UART/I2C/I2S/PCM 引脚与供电/地，再改原理图。

**P0-C 光学 AR：** J4 QSPI 是暂定光机接口，没有具体 microLED 光机/驱动板规格书、FPC 引脚、电平、刷新/上电时序、波导匹配。F15/F17/F19/F20/F22 的真实光学显示仍阻断。不得用手机屏幕代替验收。

**P0-D KiCad 与制造：** 未运行 ERC/DRC、未选定所有封装/物料、尚未摆放封装；不得生成正式投板文件或宣称可制造。

**P0-E 安全电源：** 电池 NTC/保护、充电设定电流、3V3 LDO 欠压、充电与 Wi-Fi 并发峰值、模拟器件各脚、相机 FPC 接点方向仍需厂商资料/实测审查。GPIO0/3/45/46 启动绑带与 GPIO43/44 串口拟转 I2C 方案需核对复位行为与固件占用。

## 4. 软件现状与重复开发风险
- 仓库 `main` 为 `e4e85b0a794e599f413b4987534e7999942e5373`，软件有 Sprint03 固件、BLE V1/V2、Wi-Fi JPEG、iOS CoreBluetooth 等源文件。
- GitHub 原有硬件 PR #1（`hardware/h01-h05-v1-kicad`，核查时 SHA `9f7be074c1b0faf7f1e11017a255d6aa01b9ea86`）已增加 DevKitC-1 `S3-CARRIER-A` profile、构建脚本和报告，**仍锁住摄像**。不要重复实现；必须区分它与 Claude 的 EVT-0 自研板草稿。
- Claude R2 自认没有读到完整 Codex 软件，`F01_F22_trace.csv` 仅不完整骨架；必须从 `docs/FEATURES_F01_F22.md` 真实映射全部 22 项。F21 为预研。

## 5. 阶段验收
| 阶段 | 当前评估 | 下一道 Gate |
|---|---|---|
| H01 架构/BOM | 草稿未冻结 | 光机/音频/电源与 22 功能追踪、完整 GPIO 复核 |
| H02 KiCad | R2 草稿，可复现 | 实际 KiCad ERC、逐器件数据手册/封装核查 |
| H03 PCB | 外框 + 布局计划 | 封装导入、布局布线、DRC/DFM |
| H04 结构光学 | 约束清单 | 厂商光机/波导、结构尺寸与配镜方案 |
| H05 验证 | 测试计划 | 台架实测及可追溯测试证据 |

## 6. 文件与版本完整性
- `PAYLOAD/R1/` 保留原始 R1 全部交付源文件；`PAYLOAD/R2/` 保留原始 R2 全部交付源文件（排除 Python 运行产生的 `__pycache__`）。
- 两轮源文件不能混用：R2 作为设计基线、R1 仅用于溯源和差异审查。
- `sha256_manifest.json` 提供逐文件哈希，供 Codex 和 GitHub 同步后核验。

审查人：ChatGPT；独立运行了 Python 自检，但未运行 KiCad 或真实硬件；任何供应商标称数值都不能代替实测。
