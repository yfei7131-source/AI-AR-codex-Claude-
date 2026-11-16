# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) — 双目光机接口、电源时序、QSPI 协议、跨板 FPC 连接表及 JBD 阻断规范

**文档编号**：`ZY-AIAR-V1.0-ICD-REV-C-20261116`  
**适用硬件阶段**：EVT-1 Rev C（45 位号全量 BOM / 40 行完整 PINMAP / 5 总线 ICD 100% 交叉验证版）  
**协作分工约束**：
- **KIMI**：负责嘉立创 EDA 专业版（EasyEDA Pro）原理图绘制、封装核对与 6 层 Any-Layer HDI 刚柔结合板 PCB 设计。
- **Codex**：负责 GitHub 分支 `handoff/evt1-rev-c-feasibility-20261115`（[PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)）同步与云端 GitHub Actions 原生开源 EDA CI（`iverilog` / `vvp` / `yosys` / `nextpnr-ice40` / `icetime`）执行。

---

## 1. 全系统三板三柔硬件架构与跨表一致性修正总览

为实现 **34.75 g**（$\le 40.0\text{ g}$ 目标）整机质量预算与零信号溢出的真实可制造设计，本轮跨表一致性审查发现并修复了以下 4 项工程问题（已全部纳入 `verify_v1_0_engineering.py` 的 `CHK-07` 自动一致性门禁与第 17 项故障注入测试）：

1. **修正 `J_CAM`（左前摄像头 BTB）与 `J_BTB_L` / `J_BRIDGE_IN`（主控$\leftrightarrow$鼻梁跨板 BTB）16-Pin 引脚数不足缺陷**：
   - 原 `BM28B0.6-16DS/2-0.35V(53)`（16-Pin）无法容纳 8-bit DVP 摄像头的 19 路有效信号+地屏蔽（8 数据 + 4 同步/时钟 + 2 控制 + 2 SCCB + 3 门控电源 + 5 地 = **24 脚**），亦无法容纳跨鼻梁干线的 24 路信号（8 路 FPGA QSPI/配置/VSYNC + 2 路 I2C + 1 路隐私 LED 阳极 + 8 路右腿音频/IPC + 5 路电源/地 = **24 脚**）。
   - 统一升级 `BOM-05 (J_CAM)`、`BOM-15 (J_BTB_L)`、`BOM-31 (J_BRIDGE_IN)` 为 [Hirose `BM28B0.6-24DS/2-0.35V(53)`](https://www.hirose.com/en/product/document?clcode=CL0673-5043-0-51&productname=BM28B0.6-16DS/2-0.35V(51)&series=BM28&documenttype=Catalog&lang=en&documentid=D49354_en)（**24-Pin**，`0.35 mm` pitch，尺寸 `1.50 × 5.50 × 0.60 mm`），沿镜腿/鼻梁长度方向顺置，完全满足 `0.25 mm` 板边净空与 `0.20 mm` 器件间距 DRC。
2. **新增双目光机模拟偏置硬件上电时序门控 LDO `U6_OPT_AVDD` (`BOM-45`)**：
   - 在鼻梁板背面 (`M-OPT-BRIDGE` `BOTTOM`, `X=2.10, Y=12.20 mm`) 新增 [TI `TLV75528PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)（或按 `BLK-JBD-04` 贴装 `TLV75533PDQNR`，`X2SON-4` `1.0×1.0×0.40 mm`，带内部 $120\ \Omega$ 主动放电）。
   - 其 `EN` 脚由 `U2_FPGA Ball D3 (CDONE / frame_vsync_1v8)` 经 RC 包络检测网络（$R_{\text{EN}}=100\text{ k}\Omega, C_{\text{EN}}=100\text{ nF}, \tau=10\text{ ms}$）驱动：保证上电及 FPGA 配置期间 `AVDD_OPT_BIAS = 0.00V`，仅在 `1V8_OPT_VDD` 稳定且 `CDONE=1` 后延时 $\ge 3.5\text{ ms}$ 才开启 `AVDD_OPT_BIAS`；断电时由内部 $120\ \Omega$ 快速泄放，从硬件底层杜绝 MicroLED 背板闩锁。
3. **固化 `nRF5340-CMAA` 单主 I2S 数字混音拓扑，消除双主控 I2S 总线冲突**：
   - 由右镜腿 [Nordic `nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) 作为全系统唯一的 `1.8V` 功放 I2S Master 驱动左右声道 [ADI `MAX98357AEWL+T`](https://www.analog.com/media/en/technical-documentation/data-sheets/max98357a-max98357b.pdf)（`U10_AMP_L` / `U10_AMP_R`）；左镜腿 `ESP32-S3` 的本地提示音/TTS 经 `U8_PDM_LS` Bank 2 (`3.3V -> 1.8V`) 接入 `nRF5340` I2S RX 引脚进行数字混音，彻底消除 `U8_PDM_LS` 与 `nRF5340` 输出顶牛风险。
4. **补齐 `PINMAP_V1_0_FROZEN.csv` 全部 40 行完整映射**：
   - 100% 覆盖 `U1_HOST` 全部 **57 个引脚**（10 电源/RF + 14 禁用 + 33 外部 GPIO）、`U2_FPGA` 全部 **30 个焊球**（8 电源/地 + 1 专用配置 + 3 开漏未用 + 18 标准 CMOS PIO）、`4x SN74AXC8T245` 全部 **32 个通道**、以及 **6 颗 BTB 连接器（`J_DISP_L`、`J_DISP_R`、`J_CAM`、`J_BTB_L`、`J_BRIDGE_IN`、`J_BTB_R`）逐针信号表**。

---

## 2. 双目透明 AR 光机接口、电源时序、QSPI 协议与对称 FPC 方案

### 2.1 鼻梁刚柔结合板 (`M-OPT-BRIDGE`) 对称双翼拓扑与 `J_DISP_L` / `J_DISP_R` 逐针定义

- **几何对称性**：`M-OPT-BRIDGE` 尺寸 `4.20 × 22.00 × 0.50 mm`；中心 `Y = 9.50 mm` 放置 `U2_FPGA` ([`iCE40UP5K-UWG30ITR`](https://www.micro-semiconductor.com/datasheet/10-ICE40UP5K-MDP-EVN.pdf))，左翼 `Y = 4.20 mm` 放置 `J_DISP_L`，右翼 `Y = 14.80 mm` 放置 `J_DISP_R`。左右光机走线长度严格对称（均为 **`5.30 mm`**，等长差 $\Delta L = 0.00\text{ mm} \le 0.20\text{ mm}$），零 FPC 交叉跨越。

| BTB 引脚 (`BM28B0.6-10DS`) | 左光机 `J_DISP_L` (`Y=4.20mm`) | 右光机 `J_DISP_R` (`Y=14.80mm`) | 源端器件与引脚 | 电气特性与嘉立创 EDA 布线约束 |
| :--- | :--- | :--- | :--- | :--- |
| **Pin 1** | `1V8_OPT_VDD` | `1V8_OPT_VDD` | `U4_1V8` (`1V8_FPGA_IO`) | **第 1 顺位上电轨 (`1.80V`)**：每座就近放置 `4.7 μF (0402) + 100 nF (0201)` |
| **Pin 2** | `GND` | `GND` | `L2/L5 GND` 平面 | 数字电源与时钟主回流地，紧邻 Pin 3 布置伴随接地微盲孔 |
| **Pin 3** | `OPT_SCK_L` (`24.000 MHz`) | `OPT_SCK_R` (`24.000 MHz`) | `U2_FPGA Ball E3 (IOB_13B)` | 对称 T 型分支 + **靠近 FPGA 端各串接 1 颗 `22 Ω` (`0201`) 阻尼电阻** |
| **Pin 4** | `OPT_CS_N_L` | `OPT_CS_N_R` | `U2_FPGA Ball C3 (IOB_10A)` | 对称 T 型分支 + **各串接 `22 Ω` 阻尼电阻** + `10 kΩ` 上拉至 `1V8_OPT_VDD` |
| **Pin 5** | `opt_l_qdo[0]` | `opt_r_qdo[0]` | 左：`Ball A1` / 右：`Ball E5` | 左/右独立 4-bit QSPI 数据 D0，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 6** | `opt_l_qdo[1]` | `opt_r_qdo[1]` | 左：`Ball A2` / 右：`Ball D5` | 左/右独立 4-bit QSPI 数据 D1，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 7** | `opt_l_qdo[2]` | `opt_r_qdo[2]` | 左：`Ball A4` / 右：`Ball F5` | 左/右独立 4-bit QSPI 数据 D2，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 8** | `opt_l_qdo[3]` | `opt_r_qdo[3]` | 左：`Ball E4` / 右：`Ball F4` | 左/右独立 4-bit QSPI 数据 D3，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 9** | `AVDD_OPT_BIAS` | `AVDD_OPT_BIAS` | `U6_OPT_AVDD Pin 1 (OUT)` | **第 2 顺位延时上电轨（受 `BLK-JBD-04` 约束）**：由 `CDONE` RC 延时开启，断电 $120\ \Omega$ 主动放电 |
| **Pin 10** | `GND_SHIELD` | `GND_SHIELD` | `GND` | 光机 FPC 电磁屏蔽层单点接地 |

### 2.2 光机与 FPGA 四级硬件上电/断电时序链

1. **T1 (`t = 0.0 ms`)**：`U4_1V2` (`TLV75512`) 输出 `1V2_FPGA_CORE (Ball C2)` 与经 `$100\ \Omega + 4.7\ \mu\text{F} + 100\text{ nF}$` 滤波的 `1V2_FPGA_PLL (Ball B2)` 最先建立（满足 [`FPGA-TN-02006-2.3` Checklist Item 1.4](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf)）。
2. **T2 (`t = 0.8 ms`)**：`U4_1V8` (`TPS62840`) 输出 `1V8_FPGA_IO`（供 `Ball D2 SPI_VCCIO1`、`Balls A3/C4 VCCIO_0/2` 及光机 `1V8_OPT_VDD`），同时经 `$10\ \Omega + 4.7\ \mu\text{F}$` RC 网络延时为 `Ball D4 (VPP_2V5 = 1.80V)` 供电；此时 `OPT_CS_N` 被 `10 kΩ` 上拉电阻锁定为高电平，`CDONE = 0V` 使 `U6_OPT_AVDD` 保持关闭（`AVDD_OPT_BIAS = 0.00V`）。
3. **T3 (`t = 5.0 ms`)**：`ESP32-S3` 在 `GPIO0 (QSPI_DIR1_EN) = 0` 下完成 Target SPI 比特流加载，`Ball D3 (CDONE)` 变高并输出 60Hz VSYNC，主控发送 49 个时钟后置 `QSPI_DIR1_EN = 1`。
4. **T4 (`t = 8.5 ms`)**：`CDONE` 经 `$100\text{ k}\Omega + 100\text{ nF}$` RC 充电超过 `U6_OPT_AVDD` 开启阈值（$V_{\text{IH}} = 0.95\text{ V}$），`AVDD_OPT_BIAS` 平滑开启，随后由主控/FPGA 下发 JBD 初始化命令（`BLK-JBD-02`）并启动 60.000 Hz 双目刷新。

---

## 3. 全板级 BTB 与柔性 FPC 互连逐针分配表（供 KIMI 直接连线）

### 3.1 `J_BTB_L` (`M-MAIN-L` TOP) $\leftrightarrow$ `FPC_BRIDGE` $\leftrightarrow$ `J_BRIDGE_IN` (`M-OPT-BRIDGE` BOTTOM) 24-Pin 逐针表

| Pin | 信号名 | 电压域 | 流向 | 功能说明与走线要求 | Pin | 信号名 | 电压域 | 流向 | 功能说明与走线要求 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `VBUS_5V` | `5.0V` | `L -> R` | 右镜腿 `U3_R (BQ25170)` 充电输入（线宽 $\ge 0.25\text{ mm}$） | **13** | `host_qio[3]` | `1.8V` | `L -> B` | FPGA `Ball B1` (`U8_LS1` Bank 1 `Ch3`) |
| **2** | `VSYS` | `3.5..4.4V` | `L -> B/R` | 供鼻梁 `U6_OPT_AVDD` 与右镜腿 `U10_AMP_R`（线宽 $\ge 0.25\text{ mm}$） | **14** | `frame_vsync_1v8` | `1.8V` | `B -> L` | FPGA `Ball D3 (CDONE/VSYNC)` $\rightarrow$ `U8_PDM_LS Ch1` & `U9_IMU FSYNC` |
| **3** | `VBAT_R_RET` | `3.0..4.2V` | `R -> L` | 右电池经 `U3_R` 回传左板 `U4_OR (LM66200)` `VIN2` | **15** | `SYS_I2C_SCL_1V8` | `1.8V` | `L -> B` | 鼻梁 `U9_IMU (ICM-42688-P)` I2C 时钟 |
| **4** | `1V8_SYS` | `1.80V` | `L -> B/R` | 供鼻梁 FPGA IO/`U4_1V2`/`Y1_OSC`/`U9_IMU` 及右板 `U11_BLE` | **16** | `SYS_I2C_SDA_1V8` | `1.8V` | `L <-> B` | 鼻梁 `U9_IMU (ICM-42688-P)` I2C 数据 |
| **5** | `GND` | `0.0V` | `GND` | 电源与高速时钟主地屏蔽脚 | **17** | `PRIV_LED_ANODE` | `~1.9V` | `L -> B` | 左板 `R_SENSE (2.20Ω)` 输出至鼻梁隐私灯 `D3_PRIV` 阳极 |
| **6** | `host_sck` | `1.8V` | `L -> B` | `40.000 MHz` QSPI 时钟 $\rightarrow$ FPGA `Ball D1`（两侧 Pin 5/7 包地） | **18** | `PDM_CLK_1V8` | `1.8V` | `L/R -> B` | `3.072 MHz` 数字麦克风时钟（供 `MK2_C` / `MK3_R`） |
| **7** | `GND` | `0.0V` | `GND` | `host_sck` 专用伴随屏蔽地 | **19** | `PDM_D0_1V8` | `1.8V` | `B -> L/R` | 鼻梁麦克风 `MK2_C` 与左前麦克风 `MK1_L` 立体声 PDM 数据 0 |
| **8** | `host_cs_n` | `1.8V` | `L -> B` | QSPI 片选 $\rightarrow$ FPGA `Ball C1 (SPI_SS_B)`（鼻梁接 `10k` 下拉） | **20** | `PDM_D1_1V8` | `1.8V` | `R -> L` | 右镜腿麦克风 `MK3_R` PDM 数据 1 |
| **9** | `FPGA_CRESET_B` | `1.8V` | `L -> B` | FPGA 配置复位 $\rightarrow$ `Ball F3`（鼻梁接 `10k` 上拉） | **21** | `IPC_S3_TX_1V8` | `1.8V` | `L -> R` | `ESP32-S3 GPIO48` $\rightarrow$ `U8_LS1 Ch4` $\rightarrow$ `nRF5340 UART_RX` |
| **10** | `host_qio[0]` | `1.8V` | `L -> B` | FPGA `Ball E1 (SPI_SI)`（`U8_LS1` Bank 2 `Ch8`） | **22** | `IPC_NRF_RX_1V8` | `1.8V` | `R -> L` | `nRF5340 UART_TX` $\rightarrow$ `U8_PDM_LS Ch2` $\rightarrow$ `ESP32-S3 GPIO47` |
| **11** | `host_qio[1]` | `1.8V` | `L <-> B` | FPGA `Ball F1 (SPI_SO)`（`U8_LS1` Bank 1 `Ch1`，`DIR1` 受控） | **23** | `I2S_AMP_L_DOUT_1V8`| `1.8V` | `R <-> L` | `nRF5340` 混音后左声道 I2S/TDM 数据回传 `U10_AMP_L`（伴随 BCLK/LRCLK） |
| **12** | `host_qio[2]` | `1.8V` | `L -> B` | FPGA `Ball F2`（`U8_LS1` Bank 1 `Ch2`） | **24** | `GND` | `0.0V` | `GND` | 音频与高速信号参考地 |

### 3.2 `J_CAM` (`M-MAIN-L` TOP, `BM28B0.6-24DS`) 24-Pin 摄像头与防倒灌连接表

| Pin | 信号名 | 连接目标 | Pin | 信号名 | 连接目标 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `CAM_AVDD_2V8` | `U6_CAM_AVDD`（受 `PRIV_WINDOW_OK` 门控 + $120\ \Omega$ 放电） | **13** | `CAM_HREF_1V8` | `U8_CAM_ISO2` Bank 1 `A3 -> B3` $\rightarrow$ `U1_HOST Pin 8 (GPIO3)` |
| **2** | `AGND` | 模拟地单点汇接 `L2_GND1` | **14** | `CAM_DVDD_1V2` | `U6_CAM_DVDD`（受 `PRIV_WINDOW_OK` 门控 + $120\ \Omega$ 放电） |
| **3** | `CAM_I2C_SCL_1V8` | `U8_LS3 (PCA9306)` 1.8V 侧（上拉至门控 `CAM_DOVDD_1V8`） | **15** | `CAM_DOVDD_1V8` | `U6_CAM_DOVDD`（受 `PRIV_WINDOW_OK` 门控 + 供 `U8_CAM_ISO1/2 VCCA`） |
| **4** | `CAM_I2C_SDA_1V8` | `U8_LS3 (PCA9306)` 1.8V 侧（上拉至门控 `CAM_DOVDD_1V8`） | **16** | `CAM_D0_1V8` | `U8_CAM_ISO1` Bank 1 `A1 -> B1` $\rightarrow$ `U1_HOST Pin 9 (GPIO4)` |
| **5** | `CAM_RESET_N_1V8` | `U8_CAM_ISO2` Bank 2 `A6 <- B6`（`10k` 下拉） | **17** | `CAM_D1_1V8` | `U8_CAM_ISO1` Bank 1 `A2 -> B2` $\rightarrow$ `U1_HOST Pin 10 (GPIO5)` |
| **6** | `CAM_PWDN_1V8` | `U8_CAM_ISO2` Bank 2 `A7 <- B7`（`10k` 上拉） | **18** | `CAM_D2_1V8` | `U8_CAM_ISO1` Bank 1 `A3 -> B3` $\rightarrow$ `U1_HOST Pin 11 (GPIO6)` |
| **7** | `GND` | `CAM_XCLK` 左屏蔽地 | **19** | `CAM_D3_1V8` | `U8_CAM_ISO1` Bank 1 `A4 -> B4` $\rightarrow$ `U1_HOST Pin 12 (GPIO7)` |
| **8** | `CAM_XCLK_1V8` | `U8_CAM_ISO2` Bank 2 `A5 <- B5` $\leftarrow$ `U1_HOST Pin 52 (GPIO46, 20MHz)` | **20** | `CAM_D4_1V8` | `U8_CAM_ISO1` Bank 2 `A5 -> B5` $\rightarrow$ `U1_HOST Pin 13 (GPIO8)` |
| **9** | `GND` | `CAM_XCLK` / `CAM_PCLK` 隔离地 | **21** | `CAM_D5_1V8` | `U8_CAM_ISO1` Bank 2 `A6 -> B6` $\rightarrow$ `U1_HOST Pin 43 (GPIO38)` |
| **10** | `CAM_PCLK_1V8` | `U8_CAM_ISO2` Bank 1 `A1 -> B1` $\rightarrow$ `U1_HOST Pin 47 (GPIO41)` | **22** | `CAM_D6_1V8` | `U8_CAM_ISO1` Bank 2 `A7 -> B7` $\rightarrow$ `U1_HOST Pin 44 (GPIO39)` |
| **11** | `GND` | `CAM_PCLK` 右屏蔽地 | **23** | `CAM_D7_1V8` | `U8_CAM_ISO1` Bank 2 `A8 -> B8` $\rightarrow$ `U1_HOST Pin 45 (GPIO40)` |
| **12** | `CAM_VSYNC_1V8` | `U8_CAM_ISO2` Bank 1 `A2 -> B2` $\rightarrow$ `U1_HOST Pin 48 (GPIO42)` | **24** | `GND` | 数字返回地 |

---

## 4. JBD 原厂 NDA 资料缺失造成的 4 项阻断 (`BLK-JBD-01` ~ `BLK-JBD-04`)

| 阻断编号 | 阻断项名称 | 缺失的具体 JBD 原厂资料 | 已完成的硬件防呆与解耦措施 | 解阻路径 |
| :--- | :--- | :--- | :--- | :--- |
| **`BLK-JBD-01`** | **光机 FPC 金手指线序与极性未签核** | `JBD013VGA-G` 原厂签章图纸中的 FPC 金手指 Pin 1..10（或面板 24-pin 原始接口）精确线序及正反面接触方向 | 鼻梁主板 `M-OPT-BRIDGE` 已冻结对称 10-Pin BTB (`J_DISP_L` / `J_DISP_R`) 标准接口，将线序映射隔离在独立的光机转接软板 (`FPC_OPT_L/R`) | 获取 JBD 签章图纸后定版 `FPC_OPT_L/R` 线序，**鼻梁刚柔主板无需改版** |
| **`BLK-JBD-02`** | **上电初始化寄存器序列 (Init LUT) 缺失** | 面板解锁码、温度漂移补偿、峰值电流增益 DAC、睡眠唤醒及自检寄存器地址表 | FPGA 已支持主机 SPI/QSPI 命令扩展，且 `ESP32-S3` 预留初始化表存储空间 | 取得 JBD FAE 初始化 C 数组后写入 `ESP32-S3` 固件在 T4 阶段下发 |
| **`BLK-JBD-03`** | **QSPI 行写命令格式与 2×2 像素合并模式未核实** | `0x32` 行写指令后的行地址位偏移、Dummy 时钟数及 `640×480` 至 `320×240` 像素合并命令码 | RTL 中 `CMD_HDR_NIBBLES = 12` 与 `hdr_nibble_q` 独立模块化封装 | 核对 JBD QSPI 时序图后更新 `hdr_nibble_q` 常量 |
| **`BLK-JBD-04`** | **阴极/模拟偏置电压 (`AVDD_OPT_BIAS`) 与 3D STEP 缺失** | `AVDD` 精确电压值（`2.8V` / `3.3V`）、最大电流及光机+波导总成 3D STEP (`JBD013VGA_STEP.stp`) | 已在鼻梁板配置 `U6_OPT_AVDD` (`X2SON-4` 兼容 `TLV75528P`/`TLV75533P` 共封装) 与 `CDONE` RC 延时电路 | 根据原厂规格选贴 `2.8V` 或 `3.3V` LDO 料号，并导入 STEP 完成前框光机仓干涉检查 |
