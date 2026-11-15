# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 (EVT-1 Rev B) 硬件架构与 Kimi 工程交接规范

- **仓库基准**：[`yfei7131-source/AI-AR-codex-Claude-`](https://github.com/yfei7131-source/AI-AR-codex-Claude-)（基于 `commit 6b9da263`、[PR #17 FPGA V2.2-r1](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17) 及 [PR #16 Kimi EVT-0 R9](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)）
- **交付分支**：`handoff/evt1-v1-arch-kimi-handoff-20261115`（独立分支，不修改 `main`，不覆盖 Kimi R9 `hardware/evt0-r9-pcb-20261115`）

---

## 一、 电气缺陷修正与数据手册核对 (Electrical Fixes)

### 1.1 相机隐私硬件联锁电路修正（修复 `TLV7032` 推挽误用与 7 类故障安全闭环）
- **原设计缺陷（`commit 6b9da263`）**：误选推挽输出（Push-Pull）双比较器 `TLV7032DSGR` 进行窗口比较器输出线与（Wire-AND），当一侧输出高电平、另一侧输出低电平时会造成 $V_{CC}$ 对地直通短路（$I_{SC} \approx 29\text{ mA}/33\text{ mA}$）；且未覆盖隐私 LED 阳极-阴极被短接（Jumper Bypass）及上电复位（POR，$V_S < 1.6\text{ V}$）期间的高阻毛刺风险。
- **工程修正方案（依据 [TI SLVSE13J Fig 7-3](https://www.ti.com/lit/ds/symlink/tlv7031.pdf) 与 [TI INA185 SBAS899B](https://www.ti.com/lit/ds/symlink/ina185.pdf)）**：
  1. **更换为开漏输出双比较器 `TLV7042DSGR`**（WSON-8 $2.0\times 2.0\times 0.8\text{ mm}$，Open-Drain 输出，$I_{CC}=315\text{ nA/ch}$）：`OUTA`（Pin 1）与 `OUTB`（Pin 7）直接并联构成硬件 Wire-AND 节点 `PRIV_WINDOW_OK`。
  2. **高侧采样 + 低侧限流拓扑**：`2V8_CAM`（由 `U5_CAM2V8` [`TLV75528PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf) 受控输出）$\rightarrow R_{\text{SENSE}} (1.50\ \Omega, \pm 0.1\%) \rightarrow$ 隐私绿光 LED `D3_PRIV`（[`APHD1608LZGCK` / `WP710A10LID`](https://www.kingbrightusa.com/images/catalog/SPEC/WP710A10LID.pdf)，$V_F=1.90\text{ V}$）$\rightarrow$ **低侧限流电阻 $R_{\text{LIMIT}} (300\ \Omega, \pm 1\%) \rightarrow \text{GND}$**。
  3. **收紧窗口阈值以拦截 LED 旁路短接**：`U7_INA`（`INA185A4IDRLR`，$G=200\text{ V/V}$，跨阻 $300\text{ mV/mA}$）将电流映射为 $V_{\text{INA\_OUT}}$；由 `3V3_SYS` 经 $1\%$ 精密分压链（$R_1=36.0\text{ k}\Omega, R_2=21.0\text{ k}\Omega, R_3=9.09\text{ k}\Omega$）设定窗口阈值 **$V_{\text{TH}-}=0.454\text{ V}$（$1.51\text{ mA}$）** 与 **$V_{\text{TH}+}=1.502\text{ V}$（$5.01\text{ mA}$）**。
  4. **零 POR 毛刺保护**：`U7_INA` 与 `U7_WIN` 由常通 `3V3_SYS` 供电（确保在相机开启前已完成 POR），而开漏节点 `PRIV_WINDOW_OK` 的上拉电阻 $R_{\text{PU}}=47\text{ k}\Omega$ **上拉至受控电源轨 `2V8_CAM`**，并经 $10\text{ k}\Omega + 100\text{ nF}$（$\tau = 1.0\text{ ms} > t_{\text{ON}}=200\ \mu\text{s}$）RC 滤波后驱动相机核电源 `U6_CAM1V2`（[`TLV75512PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)）的 `EN` 引脚。

| 状态编号 | 故障 / 工作模式 | 回路電流 $I_{\text{LED}}$ | `INA185A4` 输出 $V_{\text{INA}}$ | `TLV7042` 窗口判据 $[0.454\text{ V}, 1.502\text{ V}]$ | `U6_CAM1V2` ($1.2\text{ V}$ 核电源) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **State 0** | **正常工作（LED 点亮）** | $2.99\text{ mA}$ | $0.896\text{ V}$ | **PASS（窗口内）** | **ON ($1.20\text{ V}$)** |
| **State 1** | **LED 开路 / 拆毁** | $0.00\text{ mA}$ | $\le 0.011\text{ V}$ | `OUTB` 拉低（$<0.454\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 2** | **LED 阳极-阴极短接旁路** | $9.29\text{ mA}$ | $2.786\text{ V}$ | `OUTA` 拉低（$>1.502\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 3** | **LED 阳极对地短路** | $1866.7\text{ mA}$ | $3.274\text{ V}$（饱和） | `OUTA` 拉低（$>1.502\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 4** | **LED 阴极对地短路** | $600.0\text{ mA}$ | $3.274\text{ V}$（饱和） | `OUTA` 拉低（$>1.502\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 5** | **$R_{\text{SENSE}}$ 开路** | $0.00\text{ mA}$（共模差分饱和） | $3.274\text{ V}$（饱和） | `OUTA` 拉低（$>1.502\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 6** | **$R_{\text{SENSE}}$ 短路** | $3.00\text{ mA}$（差分输入为 0） | $\le 0.011\text{ V}$ | `OUTB` 拉低（$<0.454\text{ V}$） | **OFF ($0\text{ V}$)** |
| **State 7** | **相机关闭 / POR 阶段** | `2V8_CAM = 0V` | 上拉轨为 $0\text{ V}$ | `PRIV_WINDOW_OK = 0V` | **OFF ($0\text{ V}$)** |

### 1.2 双电池对称充电、NTC 保护与电源路径隔离修正
- **原设计缺陷（`commit 6b9da263`）**：左镜腿采用 `BQ24072RGTR`（USB 插入时 `OUT` 电压跟踪 $V_{\text{BAT\_L}} + 0.225\text{ V}$），右镜腿采用无独立系统输出脚的线性充电器 `BQ25170DSGR`（`OUT` 直接接右电池 `VBAT_R` 并连至 `LM66200DRLR` 的 `VIN2`）。当左电池深度亏电（如 $V_{\text{BAT\_L}}=3.2\text{ V} \Rightarrow V_{\text{OUT\_L}}=3.425\text{ V}$）而右电池电压较高（如 $V_{\text{BAT\_R}}=3.9\text{ V}$）且插入 USB 充电时，`LM66200` 会导通 `VIN2`，导致系统负载电流从 `BQ25170` 输出端抽走，造成右电池无法正常触发 $10\%\ I_{\text{CHG}}$ 充满截止（Safety Timer 超时故障）。
- **工程修正方案（依据 [TI BQ24074 SLUS810N](https://www.ti.com/lit/ds/symlink/bq24074.pdf)、[TI BQ25170 SLUSD85](https://www.mouser.lt/datasheet/2/405/1/bq25170-2303674.pdf) 与 [TI LM66200 SNVSC02A](https://docs.sparkfun.com/SparkFun_Thing_Plus_RA6M5/assets/component_documentation/LM66200.pdf)）**：
  1. **将左镜腿充电 IC 替换为同封装引脚兼容的 `BQ24074RGTR`**（VQFN-16 $3.0\times 3.0\text{ mm}$，`Pin 15 ITERM` 悬空保持默认 $10\%$ 截止）：当插入 USB $5.0\text{ V}$ 时，`BQ24074RGTR` 的 DPPM 输出脚 `OUT`（连至 `LM66200` `VIN1`）**恒定稳压在 $4.40\text{ V}$**（始终高于右电池最高充电电压 $4.20\text{ V}$ 达 $+0.20\text{ V}$）。
  2. **充电期自动理想二极管隔离**：USB 插入期间，`LM66200DRLR` 因 `VIN1 (4.40V) > VIN2 (VBAT_R <= 4.20V)` 自动反向截止 `VIN2` 通道，系统负载 $100\%$ 由 `BQ24074` 的 $4.40\text{ V}$ `OUT` 供电，左右两颗电芯（`BAT_L` 由 `BQ24074` `BAT` 脚独立充电 $118.67\text{ mA}/0.494\text{C}$，`BAT_R` 由 `BQ25170` `OUT` 脚独立充电 $120.48\text{ mA}/0.502\text{C}$）均实现零系统负载干扰的精准 $10\%\ I_{\text{CHG}}$ 截止。
  3. **电池放电期对称汇流**：拔除 USB 后，`BQ24074` 内部 $50\text{ m}\Omega$ BAT-FET 导通使 `VIN1 = VBAT_L_PROT`，`LM66200DRLR`（$R_{\text{DSON}}=22\text{ m}\Omega$）自动实现左右双电池理想二极管无损均流，后级接 [`TPS63802DLAR`](https://www.ti.com/lit/ds/symlink/tps63802.pdf) 升降压输出恒定 `3V3_SYS = 3.300V`（支持电芯放电至 $2.80\text{ V}$）。

### 1.3 SoC 引脚修正与跨域电平 100% 兼容设计
- **首推架构 `ARCH-A`（`BES2800BP` 原生 $1.8\text{ V}$ 统一电平域）**：主机、音频、传感器（`ICM-42688-P`）、3 麦 PDM（`IM69D130`）与桥接 FPGA（`iCE40UP5K`）全部工作在统一的 `1V8_SYS` 电平域，**无需任何电平转换芯片**。
- **备选架构 `ARCH-B`（`ESP32-S3-PICO-1-N8R8` $3.3\text{ V}$ + 外设 $1.8\text{ V}$）**：
  - 彻底清空 [`ESP32-S3-PICO-1-N8R8`](https://www.mouser.lt/datasheet/2/891/Espressif_Systems_07212023_ESP32_S3_PICO_1_Datashe-3240281.pdf) 内部 Flash/Octal PSRAM 禁用的 14 个引脚（Pin 28 `GPIO26`、Pins 30..35、Pins 38..42 `GPIO33..37`、Pins 53..54），将 `SPI2` 移至 `GPIO9..14`，`USB_DM/DP` 接入 Pin 24/25（`GPIO19/20`）。
  - 配置 3 颗专用双电源电平转换器：`U8_LS1`（[`SN74AXC8T245RJWR`](https://www.ti.com/lit/ds/symlink/sn74axc8t245.pdf)）转换 8 路 FPGA QSPI/控制线；`U8_LS2`（`SN74AXC8T245RJWR`）转换 `ESP32-S3` 与 `BES2800BP`/`ICM-42688-P` 之间的 UART/同步中断线；`U8_LS3`（[`PCA9306DQER`](https://www.quick-teck.co.uk/Management/EEUploadFile/1469771990.pdf)）转换双向开漏 `SYS_I2C` 总线，彻底杜绝 $3.3\text{ V}$ 直连 $1.8\text{ V}$ 造成的过压灌流。

---

## 二、 主控 SoC 架构优化对比与推荐方案 (Main Controller Optimization)

| 维度 | **首选架构 ARCH-A：`BES2800BP` 单主控高集成方案** | **备选架构 ARCH-B：`ESP32-S3-PICO-1` + `BES2800BP` 固件复用方案** |
| :--- | :--- | :--- |
| **核心芯片组合** | [`BES2800BP`](https://www.bestechnic.com/Uploads/keditor/file/20241010/20241010192510_70770.pdf) ($5.2\times 5.8\text{ mm}$ 6nm) + [`iCE40UP5K-UWG30ITR`](https://www.farnell.com/datasheets/3215488.pdf) ($2.11\times 2.54\text{ mm}$) + 可选 [`SSC309QL`](https://www.lisleapex.com/solution-ai-smart-glasses-chip-solutions) ISP | `ESP32-S3-PICO-1-N8R8` ($7.0\times 7.0\text{ mm}$) + `BES2800BP` + `iCE40UP5K` + $2\times$ `SN74AXC8T245` + `PCA9306` |
| **数字 IC 数量与占板面积** | **2 颗**（核心面积 **$35.5\text{ mm}^2$**，0 颗电平转换器） | **6 颗**（核心面积 **$97.9\text{ mm}^2$**，需 3 颗电平转换器） |
| **左镜腿 PCB 宽度适配** | **$5.80\text{ mm}$ 全等宽直条板**（无需 $8.20\text{ mm}$ 局部凸台，完全消除铰链加宽冲突） | 前段 $Y=0..14\text{ mm}$ 必须保留 **$8.20\text{ mm}$ 局部加宽区**以容纳 $7.0\text{ mm}$ LGA-56 |
| **双目显示与音频功耗** | **$195.0\text{ mW}$**（理论续航 **$8.42\text{ h}$**） | **$243.4\text{ mW}$**（理论续航 **$6.74\text{ h}$**） |
| **工程交接策略** | **作为 V1.0 首选量产架构推进**（待恒玄 NDA 球位表合入后直接出 Gerber） | **作为 EVT-1 零 NDA 阻断快速打样备选**（立即可用现有 ESP-IDF 与 FPGA RTL） |

---

## 三、 iPhone 级高密度 HDI 刚柔结合板与 3D 空间布局 (PCB High Integration)

1. **叠层与制造工艺（6 层 2+2+2 Any-Layer / 交错微盲孔 HDI + VIPPO）**：
   - 总板厚 **$0.60\text{ mm} \pm 0.06\text{ mm}$**（鼻梁刚柔结合区刚性岛 $0.50\text{ mm}$，2L PI 柔板区 $0.12\text{ mm}$），最小线宽/线距 **$50/50\ \mu\text{m}$**，激光微盲孔 **$75\ \mu\text{m}$ 钻孔 / $180\ \mu\text{m}$ 焊盘**（支持 $0.25\text{ mm}$ pitch `BES2800BP` 与 $0.40\text{ mm}$ pitch `iCE40UP5K` 盘中孔逃逸）。
2. **三区分布式 PCB 真实封装坐标与 Z 轴堆叠预算（经 `verify_v1_0_engineering.py` 逐器件 AABB 校验 0 碰撞）**：
   - **`M-MAIN-L`（左镜腿主板，长 $46.0\text{ mm}$）**：ARCH-A 为 $5.80\text{ mm}$ 等宽；ARCH-B 前段 $0\sim 14\text{ mm}$ 宽 $8.20\text{ mm}$、后段 $14\sim 46\text{ mm}$ 宽 $5.80\text{ mm}$。双面贴装最大高度：TOP 侧 $1.00\text{ mm}$（`MK1_L` / `U1_S3` $0.96\text{ mm}$）+ PCB $0.60\text{ mm}$ + BOTTOM 侧 $0.90\text{ mm}$（`U3_L BQ24074RGTR`）= **$2.50\text{ mm} \le 3.20\text{ mm}$ 腔体限高**（余量 $0.70\text{ mm}$）。
   - **`M-OPT-BRIDGE`（鼻梁中置刚性岛，$4.20\times 22.0\text{ mm}$）**：TOP 侧布置 `D3_PRIV`、`U2_FPGA`（$2.11\times 2.54\times 0.45\text{ mm}$）与 `U9_IMU`（$2.50\times 3.00\times 0.91\text{ mm}$）；BOTTOM 侧布置 `U4_1V2`（$1.0\times 1.0\times 0.40\text{ mm}$）与 `MK2_C`（$3.0\times 4.0\times 1.00\text{ mm}$）。Z 轴总高 $0.91 + 0.50 + 1.00 = \mathbf{2.41\text{ mm} \le 2.50\text{ mm}}$。
   - **`M-AUD-R`（右镜腿充电与音频副板，$5.20\times 34.0\text{ mm}$）**：单面 TOP 贴装 `U3_R`（`BQ25170DSGR` $2.0\times 2.0\times 0.80\text{ mm}$）、`MK3_R`（$3.0\times 4.0\times 1.00\text{ mm}$）与 `J_BTB_R`（`BM28B0.6-16DS` $4.1\times 1.5\times 0.60\text{ mm}$），Z 轴总高 $1.00 + 0.60 = \mathbf{1.60\text{ mm} \le 3.00\text{ mm}}$。

---

## 四、 FPGA 容量、双目同步、功耗、热与重量/重心预算 (System Verification)

1. **FPGA 存储容量硬核查（修正双缓冲溢出隐患）**：
   - [`iCE40UP5K-UWG30ITR`](https://www.farnell.com/datasheets/3215488.pdf) 内部共有 **$1024\text{ Kibit}$ SPRAM**（$4\times 256\text{ Kibit}$）与 **$120\text{ Kibit}$ EBR**。
   - 若对双目 $320\times 240\times 4\text{ bpp}$ 直接在 SPRAM 中做全帧双缓冲（$2\text{ 眼}\times 2\text{ 帧}\times 300\text{ Kibit} = 1200\text{ Kibit}$），将超出 SPRAM 容量 $17.2\%$！
   - **冻结存储架构**：每眼在 SPRAM 中分配 **1 个完整帧缓冲**（$2\times 320\times 240\times 4\text{ bpp} = \mathbf{600.0\text{ Kibit}}$，占 SPRAM **$58.6\%$**），并在 EBR 中分配 **8 行双目乒乓行缓冲 FIFO**（$2\text{ 眼}\times 2\text{ 块}\times 8\text{ 行}\times 320\times 4\text{ bpp} = \mathbf{40.0\text{ Kibit}}$，占 EBR **$33.3\%$**），在 `VBLANK` 消隐期同步突发刷新，双目帧锁相偏差 $< 1\ \mu\text{s}$。
2. **重量与三维重心预算（理论计算值，实测待样机）**：
   - 整机理论总重 **$38.45\text{ g} \le 40.0\text{ g}$**（余量 $1.55\text{ g}$）；左半侧 $13.50\text{ g}$ vs 右半侧 $13.20\text{ g}$（左右偏差 **$0.30\text{ g} \le 0.80\text{ g}$**）；三维重心 $(X=-0.35\text{ mm}, Y=41.28\text{ mm}, Z=-0.35\text{ mm})$ 落在鼻托与耳挂平衡区间 $[35\text{ mm}, 65\text{ mm}]$ 内。
3. **热预算（理论计算值，实测待样机）**：
   - $25^\circ\text{C}$ 环温下 $30\text{ s}$ 相机抓拍突发模式：ARCH-A 峰值功耗 $780\text{ mW} \Rightarrow$ 外壳接触温升估算 **$36.8^\circ\text{C} < 43.0^\circ\text{C}$**（ARCH-B 为 $849.4\text{ mW} \Rightarrow \mathbf{37.9^\circ\text{C} < 43.0^\circ\text{C}}$，符合 IEC 62368-1 穿戴温升限值）。
