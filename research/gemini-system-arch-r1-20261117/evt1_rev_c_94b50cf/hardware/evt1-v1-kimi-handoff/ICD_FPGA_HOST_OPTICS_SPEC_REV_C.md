# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) — 双目光机接口、5 态配置/电源安全联锁、QSPI 协议、跨板 FPC 连接表及 JBD 阻断规范

**文档编号**：`ZY-AIAR-V1.0-ICD-REV-C-20261116`  
**适用硬件阶段**：EVT-1 Rev C（继承 `bb87623` 完成 FPGA 配置状态与光机 `AVDD` 5 态安全联锁闭环）  
**协作分工约束**：
- **KIMI**：负责嘉立创 EDA 专业版（EasyEDA Pro）原理图绘制、封装核对与 6 层 Any-Layer HDI 刚柔结合板 PCB 设计。
- **Codex**：负责 GitHub 分支 `handoff/evt1-rev-c-feasibility-20261115`（[PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)）同步与云端 GitHub Actions 原生开源 EDA CI（`iverilog` / `vvp` / `yosys` / `nextpnr-ice40` / `icetime`）执行。

---

## 1. FPGA 配置状态 (`CDONE/VSYNC`) 与光机 `AVDD_OPT_BIAS` 5 态故障安全硬件联锁设计

### 1.1 前序版本安全漏洞剖析
- **`a678be1` 漏洞**：用无源 RC 直接对 `Ball D3 (frame_vsync_1v8)` 滤波，因用户模式下 `frame_vsync_1v8` 占空比仅 `48 / 800,000 = 0.006%`，RC 均值仅 `0.108 mV < 0.95 V`，导致运行期 `U6_OPT_AVDD` 关断。
- **`bb87623` 漏洞**：改为仅对 `1V8_OPT_VDD` + `FPGA_CRESET_B` 做盲延时 RC，未采样 `Ball D3 (CDONE / frame_vsync_1v8)`。若 **FPGA 配置失败（比特流 CRC 错误或 SPI 中断导致 `CRESET_B = 1.8V` 但 `CDONE = 0V`）**、或 **MCU 复位期间 `CRESET_B` 被上拉置高**、或 **运行中 FPGA 死机停振**、或 **`1V8_OPT_VDD` 掉电而 `VSYS` 仍在**，`bb87623` 仍会错误开启或维持 `AVDD_OPT_BIAS` 高压，造成光机背板倒灌与闩锁风险！

### 1.2 5 态肖特基峰值保持 + 双轨快速钳位联锁电路（`RN_FPGA_CFG_PWR` + `U6_OPT_AVDD`）

1. **电路拓扑（零新增芯片面积，集成于 `M-OPT-BRIDGE` `RN_FPGA_CFG_PWR` 无源网络）**：
   - **`FPGA_CRESET_B (Ball F3)` 默认下拉锁死**：配置 `R_CRST_PD = 10 kΩ` 下拉至 `GND`（替代原上拉），确保上电初期、MCU 复位或程序跑飞（`GPIO18` 高阻）时，FPGA 硬件锁定在复位态 (`CRESET_B = 0.00 V`)。
   - **峰值整流充电支路**：`U2_FPGA Ball D3 (IOB_12A_G4_CDONE / frame_vsync_1v8)` $\rightarrow$ 肖特基二极管 `D1 (RB521S-30, Vf = 0.22V)` $\rightarrow$ 限流电阻 `R_CHG = 10 Ω` $\rightarrow$ `U6_OPT_AVDD Pin 3 (EN)` 节点 (`OPT_AVDD_EN`)。
   - **保持与看门狗泄放支路**：`OPT_AVDD_EN` 节点接保持电容 `C_HOLD = 22 nF (0201)` 并联泄放电阻 `R_BLEED = 2.2 MΩ (0201)` 至 `GND`。
   - **双轨快速掉电/复位钳位支路**：
     - 肖特基二极管 `D_RST (RB521S-30)`：阳极接 `OPT_AVDD_EN`，阴极接 `FPGA_CRESET_B`。
     - 肖特基二极管 `D_VDD (RB521S-30)`：阳极接 `OPT_AVDD_EN`，阴极接 `1V8_OPT_VDD` (`1V8_FPGA_IO`)。

2. **5 种工作与故障状态定量验证表（对应 `CHK-04_PIN_PWR` 与 `Mut-18..20`）**：

| 状态编号与工况 | `FPGA_CRESET_B` | `Ball D3 (CDONE/VSYNC)` | `OPT_AVDD_EN` 节点电压计算 | `U6_OPT_AVDD` 输出 (`AVDD_OPT_BIAS`) | 安全性结论 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **State 1：上电初期 / MCU 复位 / 跑飞** | `0.00 V` (`10k` 下拉) | `0.00 V` (Open-Drain 低) | `D_RST` 钳位且无充电脉冲 $\rightarrow$ **`0.000 V <= 0.40 V (VIL)`** | **OFF (`0.00 V`, $120\ \Omega$ 放电)** | **PASS**：杜绝 MCU 未启动时误开高压 |
| **State 2：配置进行中或配置失败 (CRC 错误)** | `1.80 V` | **`0.00 V`** (`CDONE` 保持低) | `D1` 截止，`R_BLEED` 泄放 $\rightarrow$ **`0.000 V <= 0.40 V (VIL)`** | **OFF (`0.00 V`, $120\ \Omega$ 放电)** | **PASS**：配置未成功绝不开启光机 `AVDD` |
| **State 3：配置成功 + 60Hz VSYNC 扫描** | `1.80 V` | `60.000 Hz`, `1.000 μs` 正脉冲 (`1.80 V`) | $\tau_{\text{chg}} = (25+10)\Omega \times 22\text{nF} = 0.77\ \mu\text{s}$，首脉冲达 `1.148 V`，峰值 **`1.580 V`**；帧间 `16.667 ms` 经 $\tau_{\text{bleed}} = 48.4\text{ ms}$ 衰减至谷值 **`1.120 V >= 0.95 V (VIH)`** | **ON (`2.80 V / 3.30 V` 连续稳定输出)** | **PASS**：谷值裕量 `+170 mV`，零帧间抖动 |
| **State 4：FPGA 死机 / 时钟丢失 (`VSYNC` 停振)** | `1.80 V` | 卡死在 `0.00 V` | `C_HOLD` 经 `R_BLEED` 泄放：$t_{\text{wdog}} = 48.4\text{ ms} \times \ln(1.58/0.40) = \mathbf{66.5\text{ ms}}$ | **66.5 ms 内自动关断 OFF** | **PASS**：硬件级丢失脉冲看门狗保护 |
| **State 5：主动复位或 `1V8_OPT_VDD` 断电掉电** | `0.00 V` 或 `1V8 -> 0V` | 任意 | `D_RST` 或 `D_VDD` 正偏导通强制拉低 `C_HOLD`：$t_{\text{fast\_off}} = 3 \tau_{\text{chg}} = \mathbf{2.31\ \mu\text{s}}$ 至 `0.22 V <= 0.40 V` | **2.31 μs 极速关断 + $120\ \Omega$ 放电** | **PASS**：严格保证 `AVDD` 先于 `1V8` 关断 |

---

## 2. 双目透明 AR 光机接口 (`J_DISP_L` / `J_DISP_R`) 与 QSPI 协议定义

| BTB 引脚 (`BM28B0.6-10DS`) | 左光机 `J_DISP_L` (`Y=4.20mm`) | 右光机 `J_DISP_R` (`Y=14.80mm`) | 源端器件与引脚 | 电气特性与嘉立创 EDA 布线约束 |
| :--- | :--- | :--- | :--- | :--- |
| **Pin 1** | `1V8_OPT_VDD` | `1V8_OPT_VDD` | `U4_1V8` (`1V8_FPGA_IO`) | **第 1 顺位上电轨 (`1.80V`)**：每座就近放置 `4.7 μF (0402) + 100 nF (0201)` |
| **Pin 2** | `GND` | `GND` | `L2/L5 GND` 平面 | 数字电源与时钟主回流地，紧邻 Pin 3 布置伴随接地微盲孔 |
| **Pin 3** | `OPT_SCK_L` (`24.000 MHz`) | `OPT_SCK_R` (`24.000 MHz`) | `U2_FPGA Ball E3 (IOB_13B)` | 对称 T 型分支（各 `5.30 mm`，$\Delta L = 0.00\text{ mm}$）+ **各串接 `22 Ω` 阻尼电阻** |
| **Pin 4** | `OPT_CS_N_L` | `OPT_CS_N_R` | `U2_FPGA Ball C3 (IOB_10A)` | 对称 T 型分支 + **各串接 `22 Ω` 阻尼电阻** + `10 kΩ` 上拉至 `1V8_OPT_VDD` |
| **Pin 5..8** | `opt_l_qdo[0..3]` | `opt_r_qdo[0..3]` | 左：`A1,A2,A4,E4` / 右：`E5,D5,F5,F4` | 左/右独立 4-bit QSPI 数据 D0..D3，源端串接 `22 Ω`，`50 Ω` 阻抗控制 |
| **Pin 9** | `AVDD_OPT_BIAS` | `AVDD_OPT_BIAS` | `U6_OPT_AVDD Pin 1 (OUT)` | **第 2 顺位 5 态联锁上电轨**：仅当 `CDONE/VSYNC` 活跃时开启，断电 `2.31 μs` 关断 + $120\ \Omega$ 放电 |
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
| **Pin 8** | `FPGA_CRESET_B` | `1.8V` | `L -> B` | *(鼻梁终结)* | `U8_LS1 Bank 2 Ch7` $\rightarrow$ `U2_FPGA Ball F3` 及 `D_RST` 阴极 (`10k` 下拉) |
| **Pin 9..12** | `host_qio[0..3]` | `1.8V` | `L <-> B` | *(鼻梁终结)* | `U8_LS1` $\leftrightarrow$ `U2_FPGA Balls E1, F1(SPI_SO), F2, B1` |
| **Pin 13** | `frame_vsync_1v8` | `1.8V` | `B -> L` | *(鼻梁终结)* | `U2_FPGA Ball D3 (CDONE/VSYNC)` $\rightarrow$ `D1` 峰值检波、`U9_IMU FSYNC` & `U8_PDM_LS Ch1` |
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
- **`BLK-JBD-02`（上电初始化寄存器序列 LUT 缺失）**：待获取 JBD 面板解锁、温补与亮度 DAC 寄存器表后，在 `CDONE=1` 且 `AVDD_OPT_BIAS` 稳定后由主控下发。
- **`BLK-JBD-03`（QSPI `0x32` 行写命令格式与 2×2 像素合并指令未核实）**：待获取原厂协议手册后核对 `CMD_HDR_NIBBLES = 12` 编码。
- **`BLK-JBD-04`（`AVDD_OPT_BIAS` 精确电压值与 3D STEP 缺失）**：`U6_OPT_AVDD` 封装兼容 `2.8V` (`TLV75528P`) 与 `3.3V` (`TLV75533P`)，待原厂规格书与 `JBD013VGA_STEP.stp` 确认后选贴并完成光机仓干涉复核。
