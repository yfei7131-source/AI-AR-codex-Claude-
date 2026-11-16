# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1) 系统架构 R1.2

**版本**: `R1.2` (`EVT-1-SYS-ARCH-R1.2-20261117`)  
**电气基线**: Codex **Rev D1.1** (`hardware/evt1-rev-d1-1-20261117/`, 135 BOM owners / 1067 物理端子, `NOT FOR FAB`)  
**光学基线**: Claude **双目光学 R0.1** (`research/claude-dual-ar-optics-r01-20261117/`)  
**架构状态**: `NOT FOR FAB` — 静态/拓扑/协议模型与本机脚本门禁已验证；原生 EDA/SPICE/CAD/3D STEP、物理样机测试及 JBD 原厂 NDA 参数仍处于 `BLOCKED` / `OPEN_UNMEASURED`。

---

## 1. 架构继承与冲突裁决原则

1. **严格以 Rev D1.1 为最新电气基线**：全面继承 `hardware/evt1-rev-d1-1-20261117/` 的 `BOM_V1_0_FROZEN.csv`（135 项）、`PINMAP_V1_0_FROZEN.csv`（1067 端子）、`NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv`、`ICD_INTERFACE_CONTROL_TABLE.csv`、`CONNECTOR_PINOUT_REV_D1.csv`、`AVDD_SAFETY_CONTRACT_REV_D1_1.json` 及 `03_FPGA_RTL/evt1_ar_display_fpga_bridge_rev_c.v`。
2. **彻底清除 R1 / Rev C 过时遗留**：禁止回退使用旧版 `BQ24074`（`RISET` 16.2k/54.9mA 超出手册 590R–8.9k/≥100mA 合法范围）、`TPS63802DLAR`（3.0×2.0mm 封装超出 M-MAIN-L 1.4×2.3mm 区域）、`24Pin BTB` 及无壳/无辅材 `34.75g` 预算。
3. **不覆盖 Rev D1.1 或既有 GitHub 分支**：R1.2 作为独立系统集成交付包输出，保留 Rev D1.1 与 Claude R0.1 原文件只读不改。
4. **光学-电气协同与阻断边界**：将 Claude 光学 R0.1 的双目 JBD Hummingbird Mini II 光机、单绿衍射波导、两级双目校准、热限制及结构解耦要求落实到 Rev D1.1 真实电路与连接器上；凡涉及 JBD NDA（引脚极性、AVDD 电压/容值/放电曲线、初始化 LUT、QSPI 48-bit 精确头格式、`2x2` binning 指令、`JBD013VGA_STEP.stp`）均保持 `BLOCKED`。

---

## 2. 冻结可确认与阻断清单：主控、FPGA 与双目显示链路

### 2.1 主控与音频双芯架构（继承 Rev D1.1 `SYSTEM_BUDGETS_V1_0.json` §1）
- **主控 SoC (`U1_HOST`, `BOM-01`)**: **ESP32-S3-PICO-1-N8R8**（LGA-56 + EP = 57 物理端子，33 个唯一 GPIO 已分配，避开 14 个禁用引脚；`CHIP_PU` 配备 `10kΩ / 1µF` RC 上电延时）。负责 Wi-Fi / BLE 5.0、摄像头 DVP 采集（8-bit + PCLK/VSYNC/HREF/XCLK）、本地唤醒词及向 FPGA 发送显示帧/控制指令（`SPI2` 40 MHz）。
  - *关键裁决*：**ESP32-S3-PICO-1 无 MIPI DSI 接口**，因此 Claude R0.1 `CLAUDE_RESEARCH_R0_1_SOURCE.md` 中的 `ECR-01`（建议删除 FPGA 由 SoC 直驱双光机）被 **正式否决（REJECTED）**，与 `INTEGRATION_GATES.md` 第 3 行一致。
- **BLE 音频协处理器 (`U11_BLE`, `BOM-36`)**: **Nordic nRF5340-CMAA-R7**（WLCSP-95 Config 3，3.99×4.39mm，95/95 球全显式映射）。作为唯一 `I2S` 主设备（`I2S_BCLK_1V8`、`I2S_LRCLK_1V8`、`I2S_AMP_DIN_1V8`），提供 **BLE 5.4 LE Audio (CIS/BIS LC3)**。ESP32-S3 作为 `I2S` 从设备（`I2S_S3_DOUT`）及唯一 `PDM_CLK` 主设备（3-Mic PDM 采集）。
  - *注*：若产品强需求传统 Classic BT A2DP/HFP，`BLK-RevC-04` 仍为 `BLOCKED`（需更换为 ESP32-PICO-V3-02 或 ESP32-S31）。
- **被阻断的宣传型 SoC**: `BES2800BP`（`BLK-RevC-03` 保持 `BLOCKED`：仅有 3 页产品简报、无 363-ball 球图、无内部 Camera ISP、无公开 SDK）。

### 2.2 FPGA 桥接与双目显示链路（继承 Rev D1.1 `SYSTEM_BUDGETS_V1_0.json` §4 & Claude R0.1 §1.5, §2.4, §3.1）
- **显示桥接 FPGA (`U2_FPGA`, `BOM-02`)**: **Lattice iCE40UP5K-UWG30ITR**（30-ball WLCSP，18/18 PIO 球全部唯一分配并经 `ice40up5k_uwg30_rev_c.pcf` 约束）。
  - **上电时序 (`FPGA-TN-02006-2.3`)**: `1V2_FPGA_CORE` (`U4_1V2` `TLV75512PDQNR`, IN=`VSYS`) → `1V2_FPGA_PLL` (`100Ω/4.7µF`) → `1V8_FPGA_IO` (`U4_1V8F` `TLV75518PDQNR`, `EN=1V2_FPGA_PLL` ≥1.082V > VHI 1.0V) → `1V8_FPGA_VPP` (`10Ω/4.7µF`，Target SPI CRAM 模式)。
  - **主机-FPGA 隔离**: `U8_LS1` (`SN74AXC8T245RJWR`, `VCCA=3V3_SYS`, `VCCB=1V8_FPGA_IO`) 隔离 `SPI_SO` 启动总线竞争并实现 `Ioff` 断电防反灌。
- **双目显示带宽与缩放模式协调（Rev D1.1 vs Claude R0.1）**:
  - **Rev D1.1 现行基线**: `320×240 × 4bpp` 双目镜像，QSPI 24 MHz，有效带宽 `36.86 Mbps`（相对 24 MHz 四线 96 Mbps 留有 `2.60x` 裕量，相对 42 MHz 168 Mbps 留有 `4.56x`/`5.21x` 裕量），依赖 JBD 内部 `2×2` pixel-binning 或缩放指令。
  - **Claude R0.1 光学核算**: 若采用原生 `640×480 × 8bpp` 满帧传输，单眼即需 `147.5 Mbps`（60 Hz），在第三方初步手册 `J013G02VGA30E1N` 写时钟上限 `42 MHz`（`168 Mbps`）下仅支持约 `≤68 fps` 单工或 `≤60 Hz` 纯文本 HUD。
  - **R1.2 裁决**: 保留 Rev D1.1 的 `320×240 × 4bpp` 24 MHz QSPI 架构与 `OPT_CTRL (0xA4)`（`SCAN_EN`、`OPT_PWR_REQ`、`RAW_ARM`）通用传输通道；`2×2` binning 命令与 `48-bit` 行头格式 (`0x32` + 行号 + 24-bit 保留) 维持 `BLK-JBD-03` (`BLOCKED`)，待 JBD NDA 确认。
- **双目独立写阻断 (`BLK-JBD-05`)**: `J_DISP_L` 与 `J_DISP_R` 的 `opt_sck` (Ball E3) 和 `opt_cs_n` (Ball C3) 当前为共享 T 型分支，且 iCE40UP5K 18 个标准 PIO 球已满。单眼独立寄存器校准（如单眼亮度 DAC / 电子像素偏置）目前 `BLOCKED`，需待 JBD NDA 确认协议是否支持片内寻址；否则需评估复用开漏 RGB 球 (`C5/B5/A5`)。

---

## 3. AVDD 安全联锁深度审查：Rev D1.1 9-IC 看门狗 vs D3 低脉冲与 Gemini 94b50cf

### 3.1 Gemini 94b50cf 方案缺陷实证（`test_rev_d1_1_avdd_safety.py` 复现）
Rev D1.1 在 `AVDD_HARDWARE_SOURCE_REVIEW.md` 与 `GEMINI_94B_COMPARISON.md` 中通过解析计算与敏感度测试复现了旧 `94b50cf`（D3 正脉冲峰值保持整流）的 4 项硬伤：
1. **首帧欠压**：`1 µs` 有限脉冲经 `35Ω / 22nF` 充电，首帧峰值 `1.1488 V`，首帧谷值仅 **`0.8142 V < 1.0 V`**（`TLV755P` 实际保证开启阈值 `VHI = 1.0 V, VLO = 0.3 V`，非旧假设的 `0.95/0.40 V`）；稳态谷值 `1.0094 V` 裕量仅 `9.36 mV`，在 `-5%` 轨压 / `+20%` 电容 / `±1%` 电阻偏差下跌至 **`0.9859 V < 1.0 V`**。
2. **漏电失效**：在 `+0.2 µA` 正向漏电注入下，1 s 后稳态电压仍达 **`0.4400 V > 0.3 V`**，无法可靠关断。
3. **死锁盲区**：峰值保持整流无法检测 `D3` **卡高（stuck-HIGH）** 故障（`1.5800 V` 持续导通）。
4. **危险泄放**：`2.31 µs` 肖特基快速钳位会向 `CRESET_B` 或正在掉电的 `1.8V` 轨注入保持电容电流，且缺乏驱动器/轨阻抗证明。

### 3.2 Rev D1.1 9-IC 外部看门狗 + 资格锁存 + 双监督架构与 D3 低脉冲兼容性
Rev D1.1 完全移除了 `R_SEQ 100kΩ / C_SEQ 220nF` 及 `EN→CRESET` 肖特基二极管，改用 **9 颗独立器件** 构成硬件安全联锁（与 `D3` **低电平有效、空闲高电平、60 Hz 帧末 1 µs 低脉冲** 100% 兼容）：
1. **电平转换 (`U_AVDD_LS`, `SN74LVC2T45DCUR`)**: 将 `1V8_FPGA_IO` 域的 `D3` (`AVDD_D3`) 转换至 `VSYS` 域 (`AVDD_D3_VSYS`)。
2. **可重触发脉冲看门狗 (`U_AVDD_WD`, `LTC6993IS6-2#TRPBF`)**: 上升沿触发（对应每帧 `1 µs` 低脉冲结束回到高电平的上升沿）。`RSET = 402 kΩ (1%)` 设定超时窗口 **`31.624 – 34.259 ms`**（全温 `3%` + 电阻 `1%`），远大于 60 Hz 帧周期 `16.67 ms`（正常刷新持续重触发），且小于 2 帧丢失时间；上电典型启动 `4.02 ms`。
3. **资格锁存器 (`U_AVDD_QUAL`, `SN74LVC1G175DCKR`) + 施密特清零 (`U_AVDD_SCHMITT`, `SN74LVC2G17DCKR`)**: `U_AVDD_QUAL` 的 `D` 接 `VSYS`、时钟接 `AVDD_D3_VSYS` 上升沿、`CLR_N` 由 `AVDD_WD_Q` 经 `10kΩ / 100nF`（`τ = 1 ms`）延时释放。**效果**：`CDONE` 变高本身不会产生有效脉冲使能 `AVDD`，必须等待**真实帧脉冲完成后**的第一个完整上升沿才锁存 `AVDD_PULSE_QUAL = 1`。
4. **双轨监督 + 直接钳位 (`U_AVDD_IO_PG` `TPS389018DSET`, `U_AVDD_SYS_PG` `TPS389025DSET`, `U_AVDD_SYS_CLAMP` `TPS389025DSET`)**:
   - `U_AVDD_IO_PG` 监测 `1V8_FPGA_IO`，`MR` 接 `FPGA_CRESET_B`；
   - `U_AVDD_SYS_PG` 监测 `VSYS`，`MR` 接经 `10kΩ / 10nF`（`τ = 100 µs`）RC 滤波后的 `AVDD_D3_VSYS`——正常 `1 µs` 低脉冲仅跌落至 `0.99 × VSYS`（高于 `0.7 × VSYS` 门限，不误触发），若 `D3` 持续卡低则约 `138.6 µs` 后触发 `MR`；
   - 2 颗 `74LVC2G07GS` 开漏缓冲器 (`U_AVDD_CLEAR_OD`, `U_AVDD_EN_OD`, `VOL ≤ 0.1 V`, `IOZ ≤ 2 µA`) 与 `U_AVDD_SYS_CLAMP` 共同实现 `EN` 强制拉低钳位（`≤ 0.25 V < TLV755P VLO 0.3 V`）。
5. **RTL 安全加固 (`RTL_SAFETY_REVIEW.md`)**: 异步置位/同步释放 `pwr_off_sync`；被抑制时强制光机输出钳位 (`SCK=0, CS_N=1, DATA=0`)；`hb_rearm_q` 防止 `OFF→ON` 期间 VSYNC 冻结时伪造 D3 边沿；`OPT_PWR_REQ=0` 时拒绝 `SCAN_EN` 和 `RAW_ARM`。

### 3.3 剩余故障风险与验证边界（严格区分仿真通过与实物阻断）
- **已通过（仅限静态拓扑与 Python 解析/事件模型）**：`test_rev_d1_1_avdd_safety.py` 36 项模型断言 `PASS_MODEL_ONLY`；`verify_rev_d1_1_electrical.py` 24 项静态检查 `PASS`。
- **尚未执行 / 本地工具缺失**：`03_FPGA_RTL/run_rev_d1_1_safety.py` 因沙箱缺少 `iverilog` / `vvp` 退出码 `2` (`BLOCKED_NATIVE_ICARUS`)；`ngspice` 缺失 (`BLOCKED_NATIVE_NGSPICE_UNAVAILABLE`)；GitHub CI (`rev_d1_1_ci.yml`) 在本离线包中未附带当前分支运行通过日志，不得宣称已通过。
- **物理与 NDA 阻断 (`BLK-D11-PHY / JBD / CORNER / OFF-HOLD / CAD`)**：`EN` 拉低仅代表 LDO 使能关闭，不证明光机负载电容已安全泄放；最短关电保持时间（`OFF→ON` hold time）、PVT 全角（慢升慢降、窄跌落、开关振铃、`Ioff`）及 `AVDD` 与 `1V8_OPT_VDD` 相对掉电顺序仍处于 **`BLOCKED`**，必须通过实物示波器同屏波形测试与 JBD NDA 文档闭环。

---

## 4. 电源架构、跨板接口与连接器对账（Rev D1.1 基线）

| 子系统 | 现行器件 / 规格（Rev D1.1） | 关键电气与安全约束 | 状态 |
| :--- | :--- | :--- | :--- |
| **左镜腿充电 (`U3_L`)** | `BQ25180YBGR` (DSBGA-8, I2C `0x6A` @ `U8_LS3`) | `50 mA` / `4.20 V` / `SYS_REG 4.5 V`，独立保护板 NTC；固件须回读校验 I2C 寄存器 | `VERIFIED_STATIC` / `D1-BAT-01 OPEN` |
| **右镜腿充电 (`U3_R`)** | `BQ25170DSGR` (`5.49k` ISET / `27k` VSET) + `Q_CHG_ISO_R` (`PMV65XP`) + `Q_CHG_MUTE_R` (`2N7002`) | `54.64 mA` / `4.20 V`，修正 `STAT`/`/PG` 引脚 | `VERIFIED_STATIC` / `D1-BAT-01 OPEN` |
| **双电 ORing (`U4_OR`)** | `LM66200DRLR` (SOT-8 `DRL`, 40 mΩ) | 双电池隔离裕量 `0.2 V` | `VERIFIED_STATIC` |
| **主降压升压 (`U4_BB`)** | `TPS63805YFFR` (DSBGA-15, `2.285×1.374×0.625mm`) | `560k/100k` FB → `3.300 V`，`0.47 µH` `L1_BB` MPN 待定；依赖电芯 PCM 提供欠压隔离 | `VERIFIED_STATIC` / `D1-PWR-01 OPEN` |
| **系统 1.8V / FPGA 电源** | `U4_1V8` (`TPS62840DLCR`), `U4_1V2` (`TLV75512PDQNR`), `U4_1V8F` (`TLV75518PDQNR`) | `1V2_FPGA_PLL` 使能 `U4_1V8F`，确保 `1V8_FPGA_IO` 严格后于内核上电 | `VERIFIED_STATIC` |
| **主干跨板 BTB (`J_BTB_L`, `J_BRIDGE_IN`)** | **30+2P `BM28B0.6-30DS/2-0.35V(53)`** | 30 路 0.3A 信号 + 2 路 5.0A 电源 (`PWR1=VBAT_R_RET`, `PWR2=GND`)；1.25× 降额载流全部达标 | `VERIFIED_STATIC` / `BLK-RevC-02` |
| **右镜腿 BTB (`J_BTB_R`)** | **16+2P `BM28B0.6-16DS/2-0.35V(53)`** | 16 路信号 + 2 路 5.0A 电源；右电池与扬声器焊盘移至 `M-AUD-R` | `VERIFIED_STATIC` / `BLK-RevC-02` |
| **摄像头 BTB (`J_CAM`)** | **24P `BM28B0.6-24DS/2-0.35V(53)`** | `U8_CAM_ISO1/2` (`SN74AXC8T245RJWR`) 隔离 14 路 IO；`U8_LS4` (`PCA9306DQER`) + `U8_CAM_SCCB_EN` 隔离 SCCB；`INA185` + `TLV7042` 隐私窗口 `[1.091, 2.182] V` (`[2.48, 4.96] mA`) | `VERIFIED_STATIC` / `D1-CAM-01 OPEN` |
| **双目光机 BTB (`J_DISP_L`, `J_DISP_R`)** | **10+2P `BM28B0.6-10DS/2-0.35V(53)`** (`3.60×1.70×0.60mm`) | `PWR1=AVDD_OPT_BIAS`, `PWR2=GND`；`JBD` 原厂 FPC 极性/引脚映射待 NDA | `BLOCKED_NDA` (`BLK-JBD-01`) |

---

## 5. Claude 光学 R0.1 落地：光机、波导、双目校准与结构热约束

1. **光机与波导选型落地**：
   - 主选 **JBD Hummingbird Mini II**（`0.15 cc`, `0.3 g`, `8 lm`, `60 mW` 典型功耗, `30° FOV`, `3.3 mm` EPD, `Infinity` VID, 单绿 `640×480`；备选 Mini III `0.1 cc`, `0.3 g`, `30 mW`）+ 单绿 SRG 衍射波导（户外 `≥1500 nits` 入眼亮度需波导效率 `≥190 nits/lm`，`1000 nits/lm` 光机下仅需 `19%` 峰值通量）。
   - **严禁将第三方文档 `J013G02VGA30E1N` 或 `"JBD013VGA-G"` 当作量产输入**（`CLAUDE_RESEARCH_R0_1_SOURCE.md` §1.5 / `H-08` 明确指出其仅作询价参考，最终机械与引脚以 JBD NDA 签字图纸为准）。
2. **双目对齐与两级校准机制（`CLAUDE_RESEARCH_R0_1_SOURCE.md` §1.5, §3.5, §4.3）**：
   - 光学指标：`100%` 双目重叠率、垂直视差 `dipvergence ≤ 3.4 arcmin`（目标）/ `≤ 6 arcmin`（硬限）、水平会聚 `vergence ≤ 5 / 10 arcmin`、旋转 `≤ 15 arcmin`、亮度差 `≤ 10%`、焦距偏差 `±0.25 D`。
   - 工程转化（`640×480` @ `30°` 对角 FOV 下 `1 px ≈ 2.25 arcmin`，`1 µm` 位移 `≈ 0.56 arcmin`）：
     1. **机械级解耦**：采用高刚度 **Ti/Mg（钛/镁合金）独立光学底座**承载左右光机与波导，与 TR90 镜框结构解耦，保证装配后双目机械 AA 偏差 `≤ ±0.1°`。
     2. **电子级像素校准**：预留每边 **`16 px` overscan**（有效显示区域 `608×448`），出厂标定偏置参数存入主机 NVM（**禁止覆写 JBD 内部 Demura 表**）。*注意*：当前若要实现单眼独立偏置或独立亮度微调，受限于 `BLK-JBD-05` 共享 `opt_cs_n`。
3. **热设计与功耗约束（`CLAUDE_RESEARCH_R0_1_SOURCE.md` §3.3, §3.4）**：
   - **整机连续功耗上限**：**`≤ 1.5 W`**；**皮肤接触温升限值**：**`≤ 40 °C` 舒适线** / **`43 °C` IEC 62368-1 硬限**；微显示面板最高结温 `80 °C`，光机模块外壳限温 `60 °C`。
   - 电池选型冲突提示：主选 `Grepow GRP3911040` (`3.71×11.0×40.0 mm`, 含 PCM 长 `43.5 mm`, `110 mAh`, `249.3 Wh/L`) 需后部 `≥11.6 mm` 下垂桨叶镜腿；若 ID 要求 `≤6.0 mm` 超薄直腿，须切换至 `GRP220550` (`2.38×5.60×50.0 mm`, `47 mAh`, `4.35 V`) 并同步调整充电截止电压（`BLK-RevC-02`）。

---

## 6. 统一质量预算、FPC 与 6 层 HDI 空间约束

1. **质量预算统一（严禁沿用旧 `34.75 g`）**：
   - **Rev D1.1 现行分析估算**：`MASS_PLAN_REV_D1_1.csv` 计入 9 颗 AVDD 安全器件为 **`41.2408 g`**（`verify_rev_d1_1_electrical.py` / `SYSTEM_BUDGETS_V1_0.json` 按 `+0.20 g` 估算为 **`41.1978 g`**，两者差 `0.043 g` 已在 R1.2 对账表显式记录）——**当前均超出 `40.0 g` 整机目标**。
   - **有条件减重方案（`CONDITIONAL_CAPS_UNMEASURED`）**：在采用 `0.45 mm` 壁厚 PA12 镜腿壳（单侧上限 `1.80 g`）、前框+铰链上限 `9.55 g`、全 FPC+补强片上限 `0.35 g`、紧固件/胶/防尘网上限 `0.40 g` 后，含 `0.50 g` 预留裕量的候选总重为 **`39.4230 g`**（`MASS_PLAN_REV_D1_1.csv`）/ **`39.3800 g`**（`verify_rev_d1_1_electrical.py`），满足 `≤ 39.5 g` / `≤ 40.0 g` 目标，但尚未经实际 CAD 体积与称重验证。
   - **Claude R0.1 `37.0 g` 预算处置**：标记为 `research-only / NOT FOR FAB`，不作为结构与采购基线。
2. **FPC 与 6 层 HDI 约束（`SYSTEM_BUDGETS_V1_0.json` §5）**：
   - **PCB 叠层**：6 层 `2+2+2` 激光微孔 HDI + 铜填充堆叠盘中孔（`IPC-2226 Type III`），总厚约 `0.626 mm`（含阻焊 `SM 0.03 mm`）。
   - **制造规则（不得降低）**：最小线宽/线距 **`50/50 µm`**，微孔钻孔/焊盘 **`75/180 µm`**，埋孔钻孔/焊盘 **`200/400 µm`**，板边最小间距 `0.25 mm`，器件 courtyard 最小间距 `0.20 mm`。
   - **动态弯折 FPC**：`FPC_CAM_L` (`R_min 1.5 mm`, 设计 `1.8 mm`, `L=6.5 mm`), `FPC_BRIDGE` (`R_min 1.5 mm`, 设计 `2.0 mm`, `L=12.0 mm`), `FPC_HINGE_R` (`R_min 1.5 mm`, 设计 `1.8 mm`, `L=6.5 mm`)，均为 2 层 `0.12 mm` 聚酰亚胺；所有 BTB 配合区预留 `+0.32 mm` 补强片 Z 向高度；`M-OPT-BRIDGE` 需在光学底座下方预留 BTB 高度与动态避让。
   - **天线净空**：`M-MAIN-L` `Y=0.0–4.2 mm`（仅 `ANT1`）及 `M-AUD-R` `ANT2` 区域严禁铺铜与走线。

---

## 7. 验证门禁矩阵（EVT-1 R1.2 → EVT-2 准入条件）

| 门禁编号 | 验证项 | 当前状态 | 闭环通过判据 |
| :--- | :--- | :--- | :--- |
| **GATE-01** | 电气表/BOM/PINMAP/NETLIST/ICD 静态对账 | **PASS (Static)** | `verify_rev_d1_1_electrical.py` 24/24 + `verify_r1_2_integration.py` 全部通过 |
| **GATE-02** | 原生 RTL 仿真与综合静态时序 (`iverilog/yosys/nextpnr/icetime`) | **BLOCKED (缺本地工具 / CI 未附日志)** | `make -C 03_FPGA_RTL sim synth pnr sta` 返回 `VERILOG_TB_RESULT: PASS` 且 `clk_48m fmax >= 48 MHz` |
| **GATE-03** | 原生 `ngspice` PVT 与漏电瞬态仿真 | **BLOCKED (缺本地 `ngspice`)** | 覆盖 `VSYS` 慢升慢降、`1.8V` 掉电、`-40..85°C` 与最大漏电边界 |
| **GATE-04** | JBD 原厂 NDA 解密 (`BLK-JBD-01..05`, `BLK-D11-JBD`) | **BLOCKED (NDA)** | 获取签字 JBD 手册、`JBD013VGA_STEP.stp`、AVDD 额定/电容/泄放时间、48-bit QSPI 与初始化 LUT |
| **GATE-05** | 原生 EasyEDA Pro / KiCad 3D STEP 干涉与 6L HDI DRC | **BLOCKED (`BLK-RevC-02`, `BLK-D11-CAD`)** | 导入 ID 壳体 `EVT1_ID_TEMPLE_SHELL.stp` 与光学底座 STEP，确认零干涉与 6L Type-III DRC 0 报错 |
| **GATE-06** | 实物板级 AVDD 安全、双目 AA、温升与整机称重 | **BLOCKED (`BLK-D11-PHY`, `UNV-RevC-06`)** | 同屏示波器验证 10 种 AVDD 故障工况；双目 `dipvergence ≤ 6 arcmin`；连续功耗 `≤ 1.5 W`、壳温 `≤ 40/43 °C`；整机实测 `≤ 40.0 g` |
