# KIMI 可执行原理图与 PCB 设计约束 — EVT-1 R1.2 (`NOT FOR FAB`)

**依据**: Rev D1.1 (`hardware/evt1-rev-d1-1-20261117/`) + Claude 光学 R0.1 (`research/claude-dual-ar-optics-r01-20261117/`)  
**目标**: 指导 KIMI 在嘉立创 EDA Pro / KiCad 8 中完成原理图更新、6 层 HDI 布局布线与 3D STEP 干涉审查。**严禁擅自修改 Rev D1.1 已验证拓扑或降低制造规则。**

---

## 1. 原理图硬性约束（严禁回退旧版）

1. **输入源文件锁定**：仅使用 `Rev D1.1` 的 `BOM_V1_0_FROZEN.csv`（135 项）、`PINMAP_V1_0_FROZEN.csv`（1067 物理端子）与 `NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv`。禁止引入 R1/Rev C 的 `BQ24074`、`TPS63802DLAR`、`24P BTB` 或任何 `RN` 文字聚合簇（必须展开为独立器件与真实网络）。
2. **AVDD 安全联锁展开（9 颗新增器件，移除旧 RC 与二极管）**：
   - **必须删除**：`D3 -> 100k/220nF` 直流平均使能网络、以及 `EN -> CRESET_B` 肖特基泄放二极管。
   - **必须展开**：`U_AVDD_LS` (`SN74LVC2T45DCUR`)、`U_AVDD_WD` (`LTC6993IS6-2#TRPBF`, `RSET=402kΩ 1%`)、`U_AVDD_QUAL` (`SN74LVC1G175DCKR`)、`U_AVDD_SCHMITT` (`SN74LVC2G17DCKR`)、`U_AVDD_IO_PG` (`TPS389018DSET`)、`U_AVDD_SYS_PG` (`TPS389025DSET`, `MR` 经 `10k/10nF` 接 `AVDD_D3_VSYS`)、`U_AVDD_SYS_CLAMP` (`TPS389025DSET`)、`U_AVDD_CLEAR_OD` (`74LVC2G07GS`)、`U_AVDD_EN_OD` (`74LVC2G07GS`) 及对应 `10k/100nF` 资格延时与散热焊盘接地（7 个新增热焊盘全接地）。
   - **JBD NDA 未解除前保持空白/占位**：`AVDD_OPT_BIAS` LDO 精确输出电压、输出电容容值及光机端绝对额定参数不得自行猜测填死。
3. **电源与连接器锁定**：
   - `U3_L` = `BQ25180YBGR` (`0x6A` @ `U8_LS3`)；`U3_R` = `BQ25170DSGR` + `PMV65XP` + `2N7002`；`U4_OR` = `LM66200DRLR`；`U4_BB` = `TPS63805YFFR` (`560k/100k` -> `3.300V`)；`U4_1V8F` (`TLV75518PDQNR`) `EN` 必须接 `1V2_FPGA_PLL`。
   - `J_BTB_L` & `J_BRIDGE_IN` 必须为 **30+2P `BM28B0.6-30DS/2-0.35V(53)`**（`PWR1=VBAT_R_RET`, `PWR2=GND`）；`J_BTB_R` 为 **16+2P**；`J_CAM` 为 **24P**；`J_DISP_L/R` 为 **10+2P**（引脚极性待 `BLK-JBD-01` 确认后再发 FPC 投板）。
4. **音频与摄像头隔离**：
   - 严格保持 `U11_BLE` (`nRF5340-CMAA-R7`, WLCSP-95 Config 3) 为唯一 I2S Master、`U1_HOST` 为 I2S Slave + PDM Master；`MAX98357AEWL+T` WLP-9 焊盘按 `A1 SD_MODE, A2 VDD, A3 OUTP, B1 DIN, B2 GAIN_SLOT, B3 OUTN, C1 BCLK, C2 GND, C3 LRCLK` 核对，`U10_AMP_R` `SD_MODE` 分压 `69.8kΩ` 经 `U10_SD_BUF` 缓冲。
   - 摄像头 `J_CAM` 14 路 IO 经 `U8_CAM_ISO1/2` 隔离，SCCB 经 `U8_LS4` (`PCA9306`) + `U8_CAM_SCCB_EN` 隔离，`U5_LED2V8` 隐私窗口 `INA185A4IDRLR` + `TLV7042DSGR`（`[1.091, 2.182] V`）不得删改。

---

## 2. 6 层 HDI 与 PCB 布局布线规则（不得降级）

1. **叠层与工艺（`IPC-2226 Type III` 2+2+2 堆叠铜填充 VIPPO）**：
   - `L1_TOP (0.030) / PP1 (0.055) / L2_GND1 (0.018) / PP2 (0.068) / L3_SIG1 (0.018) / CORE (0.220) / L4_PWR (0.018) / PP3 (0.068) / L5_GND2 (0.018) / PP4 (0.055) / L6_BOT (0.030) / SM (0.030)`，总厚 `0.626 mm`。
   - 最小线宽/线距 **`50 / 50 µm`**；激光微孔 **`75 / 180 µm`**；埋孔 **`200 / 400 µm`**；板边净空 **`≥ 0.25 mm`**；器件 courtyard 间距 **`≥ 0.20 mm`**。
2. **新增 9 颗 AVDD 器件布局要求**：
   - 紧邻 `U2_FPGA` (`iCE40UP5K-UWG30ITR`) 与 `AVDD_OPT_BIAS` LDO 布置，`AVDD_D3` 走线短而直，避开高速 QSPI (`24 MHz` / `40 MHz`) 与 DC-DC 开关节点 (`U4_BB`, `U4_1V8`)；`10k/10nF` MR 滤波电容紧靠 `U_AVDD_SYS_PG` 引脚。
3. **RF 净空区（严禁铺铜/走线/放金属件）**：
   - `M-MAIN-L`: `Y = 0.0 – 4.2 mm`（仅允许 `ANT1`）。
   - `M-AUD-R`: `ANT2` 净空区严格按 Nordic Config 3 参考设计留空，`Y2_BLE` (`FA-128 32 MHz`) 紧靠 `U11_BLE`。

---

## 3. 光学底座、FPC 与 3D 结构机械约束（整合 Claude 光学 R0.1）

1. **双目光学底座解耦**：
   - 左右光机 (`JBD Hummingbird Mini II`) 与波导必须固定在独立高刚度 **Ti/Mg 光学底座**上，与 TR90 镜框结构解耦，保证装配 AA 偏差 `≤ ±0.1°`。
   - `M-OPT-BRIDGE` 板在 `J_DISP_L` (`Y=4.20 mm`) 与 `J_DISP_R` (`Y=14.80 mm`) 区域必须为光机 3.5 mm FPC（待 `JBD013VGA_STEP.stp` 到位后精调）与 BTB `+0.32 mm` 补强片预留 Z 向装配与拆卸空间。
2. **动态弯折 FPC 规则（2 层 `0.12 mm`）**：
   - `FPC_CAM_L` (`R_min 1.5 mm`, 设计 `1.8 mm`, `L=6.5 mm`), `FPC_BRIDGE` (`R_min 1.5 mm`, 设计 `2.0 mm`, `L=12.0 mm`), `FPC_HINGE_R` (`R_min 1.5 mm`, 设计 `1.8 mm`, `L=6.5 mm`)；弯折区禁止过孔与焊盘。
3. **3D STEP 壳体与电池仓二选一验证（`BLK-RevC-02`）**：
   - 导入 `EVT1_ID_TEMPLE_SHELL.stp` 后核对 **Config A**（`GRP3911040` `3.71×11.0×40.0 mm`, 需 `≥12.8 mm` 下垂桨叶）与 **Config B**（`GRP220550` `2.38×5.60×50.0 mm`, 适配 `≤6.0 mm` 直腿，需同步调整 4.35 V 充电）。
   - **质量红线**：前框+铰链 `≤ 9.55 g`、单侧镜腿壳 `≤ 1.80 g`、全 FPC+补强 `≤ 0.35 g`、紧固件/胶/网 `≤ 0.40 g`，确保整机含 `0.50 g` 裕量控制在 **`≤ 39.42 g`**（`≤ 40.0 g` 目标）。
4. **热设计布局**：高热耗器件（`U1_HOST`, `U4_BB`, `U10_AMP_L/R`）远离鼻托与太阳穴直接贴肤区，配合连续功耗 `≤ 1.5 W` 实现表面温度 `≤ 40 °C`（硬限 `43 °C`）。
