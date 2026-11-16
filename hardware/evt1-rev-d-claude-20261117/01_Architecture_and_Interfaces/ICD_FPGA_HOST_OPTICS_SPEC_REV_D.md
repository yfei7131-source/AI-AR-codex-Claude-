# 智元跃动 AI/AR 智能眼镜 V1.0 — EVT-1 Rev D 接口控制文档（ICD）

**文档编号**：`ZY-AIAR-V1.0-ICD-REV-D-20261116`（取代 Rev C `ZY-AIAR-V1.0-ICD-REV-C-20261116`，原文保存在 `99_RevC_Baseline/`）
**状态**：`NOT_FOR_FAB`。逐针数据以 `02_BOM_PINMAP_ICD_Blocked/CONNECTOR_PINOUT_REV_D.csv` 与 `NETLIST_ELECTRICAL_CONNECTION_REV_D.csv` 为准，本文为说明。

## 1. 电源树与上电顺序

```
VBUS_5V ─ J_CHG ─┬─ U3_L BQ24074 ─ VOUT_L_PPATH ─┐
                 └─(干线 P1)─ U3_R BQ25170 ─ VBAT_R_RET ─(5 A PWR1)─┤
                                                 U4_OR LM66200 ─ VSYS (2.8–4.4 V)
VSYS ─ U4_BB  → 3V3_SYS    VSYS ─ U4_1V8 → 1V8_SYS (左/右)
VSYS ─(干线 P2/P3)─ 桥板: U4_1V2 → 1V2_FPGA_CORE ─100Ω─ 1V2_FPGA_PLL ─EN→ U4_1V8F → 1V8_FPGA_IO (= 1V8_OPT_VDD) ─10Ω→ VPP
                          U6_OPT_AVDD (EN = RC(D3)) → AVDD_OPT_BIAS
VBAT_R_RET ─ U10_AMP_R.VDD（右功放本地取电）
```

iCE40UP 顺序（数据手册 §4.5）由硬件强制：VCC → VCCPLL（RC）→ `U4_1V8F` 在 VCCPLL ≥ 1.0 V 时使能 → SPI_VCCIO1/VCCIO_0/VCCIO_2 → VPP（10 Ω/4.7 µF）。

## 2. FPGA 配置与光机供电联锁

| 条件 | Ball D3 (`FPGA_CDONE_VSYNC_N`) | `OPT_AVDD_EN` | AVDD_OPT_BIAS |
|---|---|---|---|
| CRESET_B=0（A7 下拉默认保持） | 低（CDONE） | D_SEQ 快速泄放 → <0.3 V | 关（120 Ω 放电） |
| 配置中 / 配置失败 | 低（CDONE） | ≤1 mV | 关 |
| 用户模式，`OPT_PWR_REQ=1`（上电默认） | 高，每帧 1 µs 低脉冲 | 1.8 V（脉冲跌落 118 µV） | 开：CDONE 后 18.7 ms（最坏 20.8 ms）保证开启 |
| 用户模式，`OPT_PWR_REQ=0` | 持续低 | 46 ms 内 <0.3 V | 关 |

TLV755P：VHI=1.0 V，VLO=0.3 V（SBVS320D）。主机在 GPIO21 用下降沿中断取帧同步；GPIO21 读到持续高电平即表示配置成功。IMU FSYNC 需配置为下降沿。

## 3. 主机 QSPI 协议（ICD-01 / ICD-07）

| 命令 | 含义 |
|---|---|
| 0xA0/0xA1 | 左/右眼帧缓冲立即写（继承 Rev C） |
| 0xA2/0xA3 | 左/右眼防撕裂写（继承 Rev C） |
| 0xA4 OPT_CTRL | 地址 0x0000 + 1 个数据字；末 nibble：bit0 SCAN_EN（上电 0），bit1 OPT_PWR_REQ（上电 1），bit2 RAW_ARM，bit3 保留写 0 |

**光机初始化流程（BLK-JBD-02 解除后由固件填内容）**：
1. 读 GPIO21=高（配置成功）；等待 ≥21 ms（AVDD 稳定）。
2. `OPT_CTRL=0b0010`（SCAN_EN=0）。间隔 ≥1 µs。
3. 每条 JBD 初始化命令：`OPT_CTRL=0b0110`（RAW_ARM）→ 下一个 CS 事务被原样镜像到左右两眼（sck/cs_n/qio[3:0]）。RAW 事务建议 ≤10 MHz。
4. `OPT_CTRL=0b0011` 开始扫描（在行边界生效）。

规则：RAW_ARM 仅当此前已写入 SCAN_EN=0 才被接受；RAW 窗口内不解码 0xA0–0xA4；窗口在该事务 CS 上升沿关闭。由于 sck/cs_n 为左右共用，无法单独写某一只眼（BLK-JBD-05）。

## 4. 双目光机连接器 J_DISP_L / J_DISP_R（BM28B0.6-10DS/2）

P1=1V8_FPGA_IO；P2、P10、PWR2=GND；P3=OPT_SCK（22 Ω）；P4=OPT_CS_N（22 Ω，10 kΩ 上拉）；P5–P8=QDO[0..3]（22 Ω）；P9+PWR1=AVDD_OPT_BIAS。左右 T 形分支对称 5.30 mm（继承 Rev C）。JBD 面板侧线序仍属 NDA（BLK-JBD-01），由光机转接 FPC 重映射。

## 5. 跨板干线

`J_BTB_L` = `J_BRIDGE_IN`：BM28B0.6-30DS/2；`J_BTB_R`：BM28B0.6-16DS/2。电源：PWR1=VBAT_R_RET（5 A），PWR2=GND（5 A）。完整逐针表见 `CONNECTOR_PINOUT_REV_D.csv`（含 Rev C 原针位对照列）。只用于右镜腿的网络在桥板焊盘上不连接，仅在 FPC 上汇流。

## 6. 音频（ICD-03）

- I2S：nRF5340 为唯一主机，1.536 MHz BCLK / 48 kHz LRCLK；AMP_DIN 送两颗 MAX98357A；ESP32 为从机，经 `I2S_S3_DOUT` 将 TTS/上行麦克风数据送入 nRF SDIN。
- 声道选择：左功放 SD_MODE 直接接 `AMP_SD_MODE_1V8`（>1.4 V，左声道）；右功放经 69.8 kΩ（0.913–1.195 V，右声道）。nRF 将该线拉低时两颗功放同时关断。
- PDM：ESP32 GPIO45 为唯一时钟主机，3.072 MHz；MK1_L/MK2_C 分时共用 D0，MK3_R 使用 D1。nRF5340 的 PDM 外设不连接。
- 时序预算（AUD-03，采用的延时数值为假设）：I2S 环路 70 ns，对比半周期 326 ns；右麦克风 PDM 环路 120 ns，对比半周期 163 ns。需在 EVT 板上用示波器确认。

## 7. 摄像头与隐私联锁（ICD-04/05）

CAM_PWR_REQ 由 XCLK 活动检测产生，驱动 U5_LED2V8；LED 电流经 INA185 进入窗口比较器，窗口为 [1.091, 2.182] V；三路摄像头 LDO 的 EN 由比较器结果控制，U8_LS4 的 VREF1 接受控 DOVDD。效果：只有 XCLK 运行且 LED 电流正常时，摄像头才会上电。

## 8. NDA 阻断项（不得虚构）

BLK-JBD-01 线序；BLK-JBD-02 初始化表（本版已提供传输通道）；BLK-JBD-03 0x32 行命令格式；BLK-JBD-04 AVDD 电压值与 STEP 模型（若 AVDD 为 3.3 V，要求 VSYS ≥3.6 V）；BLK-JBD-05 单眼独立寄存器写入。
