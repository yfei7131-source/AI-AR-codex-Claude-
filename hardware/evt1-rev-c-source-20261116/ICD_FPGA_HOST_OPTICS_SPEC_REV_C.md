# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) — 双目光机接口、电源时序、QSPI 协议、跨板 FPC 连接表及 JBD 阻断规范

**文档编号**：`ZY-AIAR-V1.0-ICD-REV-C-20261116`  
**适用硬件阶段**：EVT-1 Rev C（继承 `a678be1` 并修复 `CDONE/AVDD` 上电时序占空比缺陷与 `24-Pin BTB` 3 线 I2S 直通映射）  
**协作分工约束**：
- **KIMI**：负责嘉立创 EDA 专业版（EasyEDA Pro）原理图绘制、封装核对与 6 层 Any-Layer HDI 刚柔结合板 PCB 设计。
- **Codex**：负责 GitHub 分支 `handoff/evt1-rev-c-feasibility-20261115`（[PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)）同步与云端 GitHub Actions 原生开源 EDA CI（`iverilog` / `vvp` / `yosys` / `nextpnr-ice40` / `icetime`）执行。

---

## 1. 基于 `a678be1` 的整机原理图深度电气核查与关键修正

1. **修复 `U6_OPT_AVDD` 光机 `AVDD_OPT_BIAS` 上电时序电路（解决 `frame_vsync_1v8` `0.006%` 占空比均值关断缺陷）**：
   - **原 `a678be1` 电气缺陷**：原方案将 `U6_OPT_AVDD` ([TI `TLV75528PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)) 的 `EN` 脚通过无源 RC 滤波器接至 `U2_FPGA Ball D3 (CDONE / frame_vsync_1v8)`。但在进入用户模式后，`Ball D3` 为推挽输出 `frame_vsync_1v8`，每帧 `800,000` 个 `48 MHz` 周期（`16.667 ms`）中仅输出 `48` 个周期（`1.000 μs`）高脉冲，其余 `799,952` 个周期主动拉低至 `0.00V`，占空比仅 **`0.006%`**，RC 平均直流电压仅 **$1.80\text{ V} \times 0.00006 = 0.108\text{ mV} \ll V_{\text{IH(EN)}} (0.95\text{ V})$**，会导致 `U6_OPT_AVDD` 在启动后立即关断！
   - **本轮硬件修正方案（`1V8_OPT_VDD` RC 充电 + `FPGA_CRESET_B` 肖特基钳位复位网络）**：
     - 将 `R_SEQ = 100 kΩ` 上拉源改为常驻直流轨 `1V8_OPT_VDD` (`1.80 V`)，下接延迟电容 `C_SEQ = 220 nF` ($\tau = 22.0\text{ ms}$) 至 `GND`，并从 `OPT_AVDD_EN` 节点接一颗肖特基二极管 `D_SEQ` (`RB521S-30`, $V_F = 0.22\text{ V}$, 阳极接 `OPT_AVDD_EN`，阴极接 `FPGA_CRESET_B`)。
     - **上电与复位锁死阶段 (`FPGA_CRESET_B = 0V`)**：`D_SEQ` 将 `OPT_AVDD_EN` 钳位在 $V_F = 0.22\text{ V} \le V_{\text{IL(EN)}} (0.40\text{ V})$，`U6_OPT_AVDD` 严格关断并通过内部 $120\ \Omega$ 电阻将 `AVDD_OPT_BIAS` 锁定在 `0.00 V`。
     - **配置与延时开启阶段 (`FPGA_CRESET_B` 释放为 `1.80 V`)**：`D_SEQ` 反偏截止，`C_SEQ` 由 `0.22 V` 向 `1.80 V` 指数充电，到达 $V_{\text{IH(EN)}} = 0.95\text{ V}$ 的开启时间为：
       $$t_{\text{EN}} = 22.0\text{ ms} \times \ln\left(\frac{1.80 - 0.22}{1.80 - 0.95}\right) = \mathbf{13.64\text{ ms}}$$
       此时 FPGA 早已完成 `1.20 ms` CRAM 清零 + `2.60 ms` 40MHz SPI 配置（合计 `3.80 ms`），`CDONE=1` 且 `opt_cs_n` 已稳定输出高电平达 **`+9.84 ms`**！
     - **稳态运行与掉电快放阶段**：运行期间 `FPGA_CRESET_B = 1.80 V` 为 100% 直流高电平，`OPT_AVDD_EN` 稳态保持 **`1.80 V` DC**；当系统复位 (`FPGA_CRESET_B = 0V`) 或 `1V8_OPT_VDD` 掉电时，`D_SEQ` 在 **$< 5\ \mu\text{s}$** 内快速泄放 `C_SEQ`，确保 `AVDD_OPT_BIAS` 先于 `1V8_OPT_VDD` 关断并触发 $120\ \Omega$ 主动放电。
2. **修复 `J_BTB_L` / `J_BRIDGE_IN` (24-Pin) 与 `J_BTB_R` (16-Pin) 的跨板 3 线立体声 I2S 映射不一致**：
   - **原 `a678be1` 缺陷**：`J_BTB_L` 仅用单个 `Pin 23 (S3_I2S_MUX_1V8)` 概括 I2S 总线，而右镜腿 `J_BTB_R` 却分配了 `Pins 10..13` 共 4 脚，导致跨板网表无法 1:1 对应。
   - **本轮修正方案**：利用 [Hirose `BM28B0.6-24DS/2-0.35V(53)`](https://www.hirose.com/en/product/document?clcode=CL0673-5043-0-51&productname=BM28B0.6-16DS/2-0.35V(51)&series=BM28&documenttype=Catalog&lang=en&documentid=D49354_en) 自带的 **4 个 `3.0 A` 金属屏蔽接地固定脚 (`MP1..MP4`) + `Pin 5 (GND)`** 连接 `FPC_BRIDGE` 的 L2 完整地平面，将 `J_BTB_L` / `J_BRIDGE_IN` 的 **`Pins 22, 23, 24`** 明确分配给标准 3 线立体声 I2S 总线 **`I2S_BCLK_1V8` (`Pin 22`)、`I2S_LRCLK_1V8` (`Pin 23`)、`I2S_DOUT_1V8` (`Pin 24`)**，与右镜腿 `J_BTB_R` 的 **`Pins 10, 11, 12`** 实现 **100% 1:1 物理直通**！
   - 左右声道功放 `U10_AMP_L` 与 `U10_AMP_R` ([ADI `MAX98357AEWL+T`](https://www.analog.com/media/en/technical-documentation/data-sheets/max98357a-max98357b.pdf)) 共用该 3 线 `1.8V` 立体声 I2S 总线：依据数据手册 Table 5 (p. 16)，`U10_AMP_L` 的 `Ball A2 (SD_MODE)` 直连 `1V8_SYS` 硬件固定提取左声道，而 `U10_AMP_R` 的 `Ball A2 (SD_MODE)` 经 $100\text{ k}\Omega$ 电阻接 `1V8_SYS` 硬件固定提取右声道；`U8_PDM_LS` Bank 2 (`Ch6..8`) 输出端串接 $1\text{ k}\Omega$ 隔离电阻，支持 `ESP32-S3` 混音输出或 `nRF5340-CMAA` 在休眠模式下直接接管驱动。

---

## 2. 双目透明 AR 光机接口 (`J_DISP_L` / `J_DISP_R`) 与 QSPI 协议定义

| BTB 引脚 (`BM28B0.6-10DS`) | 左光机 `J_DISP_L` (`Y=4.20mm`) | 右光机 `J_DISP_R` (`Y=14.80mm`) | 源端器件与引脚 | 电气特性与嘉立创 EDA 布线约束 |
| :--- | :--- | :--- | :--- | :--- |
| **Pin 1** | `1V8_OPT_VDD` | `1V8_OPT_VDD` | `U4_1V8` (`1V8_FPGA_IO`) | **第 1 顺位上电轨 (`1.80V`)**：每座就近放置 `4.7 μF (0402) + 100 nF (0201)` |
| **Pin 2** | `GND` | `GND` | `L2/L5 GND` 平面 | 数字电源与时钟主回流地，紧邻 Pin 3 布置伴随接地微盲孔 |
| **Pin 3** | `OPT_SCK_L` (`24.000 MHz`) | `OPT_SCK_R` (`24.000 MHz`) | `U2_FPGA Ball E3 (IOB_13B)` | 对称 T 型分支（各 `5.30 mm`，$\Delta L = 0.00\text{ mm}$）+ **各串接 `22 Ω` 阻尼电阻** |
| **Pin 4** | `OPT_CS_N_L` | `OPT_CS_N_R` | `U2_FPGA Ball C3 (IOB_10A)` | 对称 T 型分支 + **各串接 `22 Ω` 阻尼电阻** + `10 kΩ` 上拉至 `1V8_OPT_VDD` |
| **Pin 5..8** | `opt_l_qdo[0..3]` | `opt_r_qdo[0..3]` | 左：`A1,A2,A4,E4` / 右：`E5,D5,F5,F4` | 左/右独立 4-bit QSPI 数据 D0..D3，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 9** | `AVDD_OPT_BIAS` | `AVDD_OPT_BIAS` | `U6_OPT_AVDD Pin 1 (OUT)` | **第 2 顺位延时上电轨（`t_EN = 13.64 ms`）**：受 `BLK-JBD-04` 约束，断电 $120\ \Omega$ 主动放电 |
| **Pin 10** | `GND_SHIELD` | `GND_SHIELD` | `GND` | 光机 FPC 电磁屏蔽层单点接地 |

---

## 3. 全板级 BTB 与 T 型跨板 FPC 互连逐针分配表（供 KIMI 直接连线）

### 3.1 `J_BTB_L` (`M-MAIN-L` TOP) $\leftrightarrow$ `J_BRIDGE_IN` (`M-OPT-BRIDGE` BOTTOM) $\leftrightarrow$ `J_BTB_R` (`M-AUD-R` TOP) 逐针映射表

| `J_BTB_L` / `J_BRIDGE_IN` (24P) | 信号网络名 | 电压域 | 流向 | 对应 `J_BTB_R` (16P) 引脚 | 功能与跨板分支去向说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pin 1** | `VBUS_5V` | `5.0V` | `L -> R` | **`J_BTB_R Pin 1`** | 左腿 USB-C/Pogo 5V 直通右腿充电芯片 `U3_R (BQ25170)` |
| **Pin 2** | `VSYS` | `3.5..4.4V` | `L -> B/R` | **`J_BTB_R Pin 2`** | 系统主母线供鼻梁 `U6_OPT_AVDD` 与右腿功放 `U10_AMP_R` |
| **Pin 3** | `VBAT_R_RET` | `3.0..4.2V` | `R -> L` | **`J_BTB_R Pin 3`** | 右电池经 `U3_R` 回传左板理想二极管 `U4_OR (LM66200) VIN2` |
| **Pin 4** | `1V8_SYS` | `1.80V` | `L -> B/R` | **`J_BTB_R Pin 4`** | 供鼻梁 FPGA IO/`U4_1V2`/`Y1_OSC`/`U9_IMU`/`MK2_C` 及右板 `U11_BLE`/`MK3_R` |
| **Pin 5 + MP1..4** | `GND` | `0.0V` | `GND` | **`J_BTB_R Pin 5 + MP1..4`** | `FPC_BRIDGE` L2 完整参考地平面 + 4 个 `3.0A` 金属屏蔽固定脚 |
| **Pin 6** | `host_sck` | `1.8V` | `L -> B` | *(鼻梁终结)* | `U8_LS1 Bank 2 Ch5` $\rightarrow$ `U2_FPGA Ball D1 (SPI_SCK)` (`40.000 MHz`) |
| **Pin 7** | `host_cs_n` | `1.8V` | `L -> B` | *(鼻梁终结)* | `U8_LS1 Bank 2 Ch6` $\rightarrow$ `U2_FPGA Ball C1 (SPI_SS_B)` (`10k` 下拉) |
| **Pin 8** | `FPGA_CRESET_B` | `1.8V` | `L -> B` | *(鼻梁终结)* | `U8_LS1 Bank 2 Ch7` $\rightarrow$ `U2_FPGA Ball F3` 及 `D_SEQ` 阴极 (`10k` 上拉) |
| **Pin 9..12** | `host_qio[0..3]` | `1.8V` | `L <-> B` | *(鼻梁终结)* | `U8_LS1` $\leftrightarrow$ `U2_FPGA Balls E1, F1(SPI_SO), F2, B1` |
| **Pin 13** | `frame_vsync_1v8` | `1.8V` | `B -> L` | *(鼻梁终结)* | `U2_FPGA Ball D3 (CDONE/VSYNC)` $\rightarrow$ `U9_IMU FSYNC` & `U8_PDM_LS Ch1` |
| **Pin 14..15** | `SYS_I2C_SCL/SDA_1V8` | `1.8V` | `L <-> B` | *(鼻梁终结)* | `U8_LS3 (PCA9306)` $\leftrightarrow$ `U9_IMU (ICM-42688-P)` |
| **Pin 16** | `PRIV_LED_ANODE` | `~1.9V` | `L -> B` | *(鼻梁终结)* | `U5_LED2V8 -> R_SENSE (2.20Ω)` $\rightarrow$ 鼻梁隐私指示灯 `D3_PRIV` 阳极 |
| **Pin 17** | `PDM_CLK_1V8` | `1.8V` | `L/R -> B/R` | **`J_BTB_R Pin 6`** | `3.072 MHz` PDM 麦克风时钟（同步驱动 `MK1_L`、`MK2_C`、`MK3_R`） |
| **Pin 18** | `PDM_D0_1V8` | `1.8V` | `B -> L` | *(鼻梁终结)* | 鼻梁 `MK2_C (SELECT=1V8)` 与左腿 `MK1_L (SELECT=GND)` 复用数据线 0 |
| **Pin 19** | `PDM_D1_1V8` | `1.8V` | `R -> L` | **`J_BTB_R Pin 7`** | 右镜腿 `MK3_R (SELECT=GND)` PDM 数据线 1 |
| **Pin 20** | `IPC_S3_TX_1V8` | `1.8V` | `L -> R` | **`J_BTB_R Pin 8`** | `ESP32-S3 GPIO48` $\rightarrow$ `U8_LS1 Ch4` $\rightarrow$ `U11_BLE (nRF5340) UART_RX` |
| **Pin 21** | `IPC_NRF_RX_1V8` | `1.8V` | `R -> L` | **`J_BTB_R Pin 9`** | `U11_BLE (nRF5340) UART_TX` $\rightarrow$ `U8_PDM_LS Ch2` $\rightarrow$ `ESP32-S3 GPIO47` |
| **Pin 22** | `I2S_BCLK_1V8` | `1.8V` | `L/R -> L/R` | **`J_BTB_R Pin 10`** | 立体声 I2S 位时钟 (`1.536 MHz`)，连接 `U10_AMP_L`、`U10_AMP_R`、`U11_BLE` |
| **Pin 23** | `I2S_LRCLK_1V8` | `1.8V` | `L/R -> L/R` | **`J_BTB_R Pin 11`** | 立体声 I2S 帧时钟 (`48.0 kHz`)，连接 `U10_AMP_L`、`U10_AMP_R`、`U11_BLE` |
| **Pin 24** | `I2S_DOUT_1V8` | `1.8V` | `L/R -> L/R` | **`J_BTB_R Pin 12`** | 立体声 I2S 数据线（`U10_AMP_L` 取左声道，`U10_AMP_R` 取右声道） |
| *(右腿尾端)* | `VBAT_R_CELL_P / NTC_TS_R / SPK_R_P / SPK_R_N` | `4.2V / Audio` | `R <-> BAT/SPK` | **`J_BTB_R Pins 13..16`** | 右后电池包 `BAT_R` 正极/NTC 与右扬声器差分输出 (`U10_AMP_R OUTP/OUTN`) |

---

## 4. JBD 原厂 NDA 资料缺失造成的 4 项阻断 (`BLK-JBD-01` ~ `BLK-JBD-04`)

- **`BLK-JBD-01`（FPC 金手指线序与极性未签核）**：鼻梁板已冻结对称 10-Pin `J_DISP_L/R`，线序差异隔离于独立光机转接 FPC，待原厂签章图纸确认后投板转接 FPC。
- **`BLK-JBD-02`（上电初始化寄存器序列 LUT 缺失）**：待获取 JBD 面板解锁、温补与亮度 DAC 寄存器表后，在 $t > 13.64\text{ ms}$（`AVDD_OPT_BIAS` 稳定后）由主控下发。
- **`BLK-JBD-03`（QSPI `0x32` 行写命令格式与 2×2 像素合并指令未核实）**：待获取原厂协议手册后核对 `CMD_HDR_NIBBLES = 12` 编码。
- **`BLK-JBD-04`（`AVDD_OPT_BIAS` 精确电压值与 3D STEP 缺失）**：`U6_OPT_AVDD` 封装兼容 `2.8V` (`TLV75528P`) 与 `3.3V` (`TLV75533P`)，待原厂规格书与 `JBD013VGA_STEP.stp` 确认后选贴并完成光机仓干涉复核。
