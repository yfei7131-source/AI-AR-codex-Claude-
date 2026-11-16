# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 — EVT-1 Rev C KIMI (嘉立创EDA) 与 Codex (GitHub CI) 工程交接手册

**工程版本**：`V1.0-EVT1-RevC-PR19-ElectricalAudited-20261116`  
**Git 分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严格保护 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）  
**主控与音频冻结架构**：[Espressif `ESP32-S3-PICO-1-N8R8`](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf) (左镜腿 Wi-Fi/DVP/AI 主控) + [Nordic `nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) (右镜腿 BLE 5.4 LE Audio 协处理器) + [Lattice `iCE40UP5K-UWG30ITR`](https://www.micro-semiconductor.com/datasheet/10-ICE40UP5K-MDP-EVN.pdf) (鼻梁双目 QSPI 桥接 FPGA) + `2x ADI MAX98357AEWL+T` (数字 I2S 功放)

---

## 1. 继承 `a678be1` 的整机原理图深度电气核查与闭环修正

1. **修复 `U6_OPT_AVDD` 光机 `AVDD_OPT_BIAS` 上电时序电路（消除 `0.006%` 占空比 VSYNC RC 滤波关断缺陷，`CHK-04_PIN_PWR` / `Mut-18`）**：
   - **问题根因**：`a678be1` 将 `U6_OPT_AVDD` ([TI `TLV75528PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)) 的 `EN` 脚经 RC 接至 `Ball D3 (CDONE / frame_vsync_1v8)`；但用户模式下 `frame_vsync_1v8` 为推挽输出（每 `800,000` 周期仅 `48` 周期为高，占空比 `0.006%`），RC 直流均值仅 **`0.108 mV < 0.95 V`**，导致运行期 `U6_OPT_AVDD` 关断。
   - **修复方案**：改为由常驻 `1V8_OPT_VDD` (`1.80 V`) 经 `R_SEQ = 100 kΩ + C_SEQ = 220 nF` ($\tau = 22.0\text{ ms}$) 充电，并由肖特基二极管 `D_SEQ (RB521S-30, Vf = 0.22V)` 钳位至 `FPGA_CRESET_B`：
     - 当 `FPGA_CRESET_B = 0V` 时，`OPT_AVDD_EN` 被钳位在 `0.22 V <= 0.40 V (VIL)`，`AVDD_OPT_BIAS` 严格关断并由内部 $120\ \Omega$ 放电至 `0.00 V`；
     - 当 `FPGA_CRESET_B = 1.80V` 释放后，`OPT_AVDD_EN` 在 **`t_EN = 13.64 ms`** 跨过 `0.95 V (VIH)` 开启 `AVDD_OPT_BIAS`（比 `3.80 ms` 的 FPGA Target SPI 配置完成时间晚 **`+9.84 ms`**），稳态保持 **`1.80 V` DC**，复位或掉电时经 `D_SEQ` 在 `< 5 μs` 内快速关断。
2. **修复 `J_BTB_L` / `J_BRIDGE_IN` (24-Pin) 与 `J_BTB_R` (16-Pin) 的 3 线立体声 I2S 跨板映射（消除单脚截断缺陷，`CHK-07` / `Mut-19`）**：
   - **问题根因**：`a678be1` 在 `J_BTB_L` 上仅留 `Pin 23 (S3_I2S_MUX_1V8)` 单脚给 I2S，与 `J_BTB_R` 的多脚 I2S 不匹配。
   - **修复方案**：利用 [Hirose `BM28B0.6-24DS/2-0.35V(53)`](https://www.hirose.com/en/product/document?clcode=CL0673-5043-0-51&productname=BM28B0.6-16DS/2-0.35V(51)&series=BM28&documenttype=Catalog&lang=en&documentid=D49354_en) 的 4 个 `3.0 A` 金属屏蔽接地固定脚 (`MP1..MP4`) + `Pin 5 (GND)` 连接 `FPC_BRIDGE` L2 完整地平面，将 `J_BTB_L` / `J_BRIDGE_IN` 的 **`Pins 22, 23, 24`** 分配给 **`I2S_BCLK_1V8`、`I2S_LRCLK_1V8`、`I2S_DOUT_1V8`**，与 `J_BTB_R` 的 **`Pins 10, 11, 12`** 实现 **100% 1:1 直通**；左右功放 `U10_AMP_L/R` ([ADI `MAX98357AEWL+T`](https://www.analog.com/media/en/technical-documentation/data-sheets/max98357a-max98357b.pdf)) 通过 `SD_MODE` 引脚硬件分槽提取左/右声道。
3. **全机 45 位号 BOM 与 45 行全器件级 `PINMAP_V1_0_FROZEN.csv` 100% 闭环**：
   - `PINMAP_V1_0_FROZEN.csv` 现已覆盖全部主控 (`57/57` 脚)、FPGA (`30/30` 球)、4 颗电平转换器 (`32/32` 通道)、6 颗 BTB 座 (`J_DISP_L/R` 10P、`J_CAM` 24P、`J_BTB_L` 24P、`J_BRIDGE_IN` 24P、`J_BTB_R` 16P)、电源管理芯片 (`BQ24074`、`BQ25170`、`LM66200`、`TPS63802`、`TPS62840`、`TLV755P`)、隐私联锁 (`INA185A4`、`TLV7042`)、声学器件 (`MAX98357A`、`IM69D130`) 及传感器 (`ICM-42688-P`、`ASFLMB-48M`)，可供 KIMI 直接在嘉立创 EDA 中按表连线。

---

## 2. 40g 高密度集成、6 层 HDI 叠层、结构与热设计硬性约束

- **6 层 2+2+2 Type-III Stacked-VIPPO HDI 叠层**：总厚 `0.628 mm`（含阻焊），最小线宽/线距 `50/50 μm`，激光微盲孔 `75/180 μm` 铜浆塞孔电镀盖帽，支持 L1$\rightarrow$L2$\rightarrow$L3 叠孔逃逸 `nRF5340-CMAA` (`0.35 mm` pitch) 与 `iCE40UP5K-UWG30` (`0.40 mm` pitch) 内排引脚。
- **质量、重心与温升模型（物理样机回板前标记为 `UNVERIFIED`）**：整机预估质量 **`34.75 g`**（较 `40.0 g` 留有 `5.25 g` 裕量），左右质量差 **`0.36 g`**，重心 **`Y = 35.92 mm`**；采用双轨目录电池 Config A [Grepow `GRP3911040`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) (`2×110mAh = 0.814Wh`，HUD 续航 `3.24h`) 或 Config B `GRP220550` (`2×47mAh`，适配 $\le 6.0\text{ mm}$ 超细直镜腿)；30s 拍照突发峰值外壁温升预估 **`37.2 °C`** (`< 43.0 °C`)。
