# 智元跃动 AI/AR 智能眼镜 V1.0（EVT-1 H03）U11 nRF5340 WLCSP95 扇出与封装工程决策报告

**文档编号**：`U11_ESCAPE_DECISION.md`

**核查基准**：[GitHub PR #54（EVT-1 H03 R6, NOT FOR FAB）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)、[R6 HDI 研究文档](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md) 与 [Nordic nRF5340 官方产品规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html)

**工程状态**：仅只读核对与工程决策，**未修改任何 KIMI 工程或 GitHub 仓库**；当前工程维持 **`NOT FOR FAB`** 状态。

## 1. 决策结论与首选方案

### 1.1 明确首选方案（方案 A：EVT-1 阶段推荐）

**保留 `U11 = nRF5340-CMAA`（WLCSP95，4.390 × 3.994 mm，0.35 mm 球距），以“板厂签核的 6 层 2+2+2（二阶）HDI + 激光铜填盘中孔（VIPPO）+ 局部 3/3 mil 扇出规则”替代现行非 HDI 6 mil 通用规则，并同步实施外圈空闲 GPIO 重映射（优先将 `K5 / BCLK` 重映射至外圈 `L9 / P0.15`，按需释放其余内圈可重映射 GPIO）。**

* **核心依据 1（物理板宽红线）**：PCB3 现行板宽为 **5.20 mm**（[R6 hdi/README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md)）。`nRF5340-CMAA` 封装体尺寸为 **4.390 × 3.994 mm**，典型高度仅 **0.449 mm**（[Nordic Mechanical specifications](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html?contentId=Eklj6e1CyGsPLBrPbUCj8Q)），是 `nRF5340` 家族中唯一能直接装入 5.20 mm 窄板且守住整机 **40 g** 重量目标的封装。

* **核心依据 2（原厂生命周期红线）**：`nRF5340-CLAA` 虽与 `CMAA` 共用 95 球位表和 0.35 mm 节距，但原厂已明确标注 **`CLAA` 不推荐用于新设计（Not recommended for new designs）**，新设计必须锁定 **`nRF5340-CMAA-R7` / `nRF5340-CMAA-R`**（[Nordic Ordering info](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ordering_info/doc/ordering_info.html)）。

* **核心依据 3（几何死锁的本质是规则错配）**：在 0.35 mm（13.78 mil）球距下，用非 HDI 通用规则（3 mil 过孔焊环 + 6 mil 铜间距 + 11.8 mil 孔壁间距）做居中盘中孔在数学上必然无解。必须切换至经过板厂 EQ 书面签核的二阶 HDI 工艺边界（0.075 mm 激光铜填盲孔、0.18–0.20 mm 捕获盘、3/3 mil 扇出线宽/线距），绝不可把 R6 的“理论几何候选路径”等同于实际可制造通过。

### 1.2 备选与淘汰路线界定

* **备选方案 B（结构变更兜底）**：若 PCB3 无法在 EVT-1 拿到满意的 0.80 mm 二阶 HDI 良率/交期/成本，且结构团队（MECR-01）批准将 PCB3 局部加宽至 **≥ 8.5–9.0 mm**、增厚镜腿截面并重算 40 g 重量配平，则切换至 **`nRF5340-QKAA`（aQFN94，7.00 × 7.00 mm，0.4 mm 节距）**。需注意该封装内圈焊盘同样需要 IPC-4761 Type VII 树脂塞孔盖帽盘中孔（[QFN vs WLCSP vs BGA 封装分析](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)），并不能彻底取消 VIPPO 工艺。

* **不建议 EVT-1 采纳**：`nRF5340` 第三方成品模组（最窄 7.8 mm，远超 5.20 mm 板宽）、`nRF54L15`（需重构双核 SDK/音频架构，且 QFN40 5×5 mm 仍不满足 5.20 mm 板边净距）、`nRF52840`（无双核 LE Audio 架构且射频功耗显著更高）。

## 2. U11 nRF5340 WLCSP95 全球位与剩余 25 个内圈受阻球位复核

依据 [PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)、[R6 BLOCKED.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/BLOCKED.md)、[r3-u11-native-audit.json](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r4-20261123/u11/r3-u11-native-audit.json) 与 [r3-u11-95ball-native.csv](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r4-20261123/u11/r3-u11-95ball-native.csv) 逐项核对，U11 共 95 球，其中 36 个内圈有网球中，11 个位于同网 GND 内部网格，其余 **25 个内圈球位**在现行锁定 6 mil（0.1524 mm）铜间距与 0.2274 mm 居中过孔捕获盘约束下全部受阻。

### 2.1 25 个内圈受阻球位完整分类与扇出策略

| 工程分类 | 数量 | 球位坐标 | 原厂引脚名 | 现有网络名 | 能否重映射 | 扇出与电气优先级策略 | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | 
| **A. 地网与 VBUS 接地** | 7 | `B2`、`B9`、`C2`、`E5`、`K6`、`K11`、`B11` | `VSS` (×4)、`AVSS` (×2)、`VBUS` | `GND` | 不可 | **最易闭合**：L1→L2 单阶激光微盲孔直下 L2 完整地平面，无需占用 L3/L4 信号通道；`K6/K11` 优先保证射频/模拟回流低感接地。 | 
| **B. 1.8 V 主电源** | 5 | `B7`、`B10`、`D2`、`E11`、`H11` | `VDD` | `1V8_SYS` | 不可 | L1→L2→L3 错孔/叠孔汇入 L3 电源铜皮，去耦电容紧贴封装外缘布置，避免细长引线增大电源阻抗。 | 
| **C. 内部稳压/射频退耦/DCDC** | 4 | `B4`、`B5`、`B6`、`B8` | `DECR`、`DECN`、`DCC`、`DECA` | `NRF_DECR_RF`、`NRF_DECN`、`NRF_DCC`、`NRF_DECA` | 不可 | **最高保护等级**：严禁绕远或与高速数字线并行；`B4 (DECR)` 与 `BLE_RF`/`BLE_ANT` 维持 ≥12 mil 隔离并就近接退耦电容与 L2 地平面（遵循 [Nordic Reference circuitry](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ref_circuitry.html?contentId=RMhcbnA~~22itqm6XdPmBQ)）。 | 
| **D. 晶振/调试/复位** | 3 | `F11`、`F2`、`G2` | `P0.00 (XL1)`、`SWDCLK`、`nRESET` | `LFXO_XL1`、`BLE_SWDCLK`、`BLE_NRESET` | 不可 | `F11 (LFXO_XL1)` 为 32.768 kHz 模拟晶振端，必须短线就近至 `X2` 并包地隔离；`F2/G2` 为低速调试复位线，可安全通过二阶微盲孔下 L3/L4 逃线。 | 
| **E. 可重映射数字 GPIO** | 6 | `J4`、`J5`、`K2`、`K3`、`K4`、`K5` | `P0.21`、`P0.19`、`P0.24`、`P1.04`、`P0.22`、`P0.20` | `I2S_AMP_DIN_1V8`、`I2S_S3_DOUT_1V8`、`AMP_SD_REQ_1V8`、`IPC_NRF_TX_1V8`、`I2S_LRCK_1V8`、`I2S_BCLK_1V8` | **可重映射** | **核心减压杠杆**：优先将 `K5 (BCLK)` 迁至外圈空闲 `L9 (P0.15)`；若联合扇出仍拥挤，可继续评估将 `J4/J5/K2/K3/K4` 迁至其他未占用外圈 GPIO，从源头减少内圈高阶盲孔数量。 | 

> **关键工程发现**：25 个受阻球中，**12 个为同网 `GND`/`1V8_SYS`**（可在 L2/L3 局部平面消化），**6 个为可重映射数字 GPIO**，真正必须从内圈独立引出且不可重映射的点对点信号仅 **7 个**（4 颗退耦/DCDC + 1 颗晶振 + 2 颗调试复位）。这意味着只要 HDI 激光盘中孔规则通过板厂 EQ 签核，并释放部分 E 类内圈 GPIO，U11 25 球联合扇出在 6 层 2+2+2 HDI 下具备清晰的工程收敛路径。

## 3. 0.35 mm 球距下的可制造扇出、微盲孔与多层信号连接分析

### 3.1 为什么现行锁定规则与 0.35 mm 球距存在根本冲突

依据 [Nordic Mechanical specifications](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html?contentId=Eklj6e1CyGsPLBrPbUCj8Q) 与 [R6 hdi/README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md)：

* **球距与焊球尺寸**：`nRF5340-CMAA` 球距 `e = 0.35 mm`（13.78 mil），焊球直径 `b = 0.19–0.25 mm`（`CLAA` 为 `0.12–0.18 mm`），现有封装焊盘直径为 `Ø0.195 mm`（7.68 mil）。

* **传统非 HDI 规则的数学死锁**：

  * 相邻 `Ø0.195 mm` 焊盘净距仅为 `0.35 - 0.195 = 0.155 mm`（6.10 mil），刚好贴着项目锁定的 `6 mil`（0.1524 mm）下限，**外层两球之间完全无法穿过任何 3 mil 或 4 mil 走线**。

  * 若套用机械孔/保守 3 mil 焊环规则，75 µm 激光孔最小捕获盘为 `0.075 + 2 × 0.0762 = 0.2274 mm`（100 µm 孔为 `0.2524 mm`）。此时捕获盘与相邻 `Ø0.195 mm` 焊盘净距跌至 **`0.1388 mm`**，两颗最小捕获盘并排净距仅 **`0.1226 mm`**，均违反 `0.1524 mm` 锁定间距。

* **R6 孤立试验暴露的真实阻断**：在 [PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54) 与 [R6 BLOCKED.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/BLOCKED.md) 中，仅对单根 `K4` 实施二阶叠孔试验即在原生严格 DRC 中报出 **4 处 Hole-to-Hole 失败**（3 对同心叠孔孔壁投影 `0 mil`、1 处激光孔到 6 mil 埋孔仅 `5.3 mil < 11.8 mil`），且最近的跨层回流地孔距过层点高达 **`10.73 mm`**。**这明确证明：理论几何连线 ≠ 可制造通过。**

### 3.2 可制造 HDI 工艺窗口与叠层方案对比

结合 [JLCPCB 官方 HDI 工艺能力](https://jlcpcb.com/capabilities/pcb-capabilities)、[JLCPCB 过孔设计指南](https://jlcpcb.com/blog/pcb-via-design-best-practices) 与 [IPC-2226 激光微盲孔焊环规范](https://www.lcsc.com/blog/pcb-annular-ring-guide/)，给出面向 0.35 mm WLCSP95 的工程化工艺窗口对照：

| 工艺参数 | R6 现行锁定非 HDI 规则 | JLCPCB 公开 HDI 能力边界 | 面向 U11 的推荐 EQ 申报目标 | 制造风险与工程说明 | 
| ----- | ----- | ----- | ----- | ----- | 
| **叠层结构与板厚** | 默认 6 层 `JLC06161H-3313`（1+4+1，1.7873 mm） | 支持 1/2/3 阶 HDI（TG170 NP-175F / S1000-2M） | **6 层 2+2+2（二阶 HDI），目标总厚 `0.80 mm`**（L1–L2、L2–L3、L4–L5、L5–L6 每阶 50 µm 介质 + 418 µm L3–L4 芯） | 必须向板厂索取正式叠层与阻抗表，不得沿用 1.7873 mm 非 HDI 叠层。 | 
| **激光微盲孔（VIPPO）** | 3 mil 焊环（Ø0.2274 / 0.2524 mm 捕获盘） | **0.075–0.15 mm** 激光钻孔 + **电镀填铜**（纵横比 ≤ 1:1） | **Ø0.075 mm（3 mil）激光铜填盲孔**，盘中孔捕获盘 **`Ø0.195–0.20 mm`**（单边焊环 `0.060–0.0625 mm` ≈ 2.4 mil，优于 IPC-2226 Level B 的 1 mil 下限） | 0.20 mm 捕获盘在 0.35 mm 球距下相邻铜距恢复至 **`0.15 mm`（5.9 mil）**；盘面平整度需 ≤ ±5 µm 以防锡球空洞。 | 
| **二阶盲孔互联方式** | R6 试验采用同心叠孔（DRC 报 0 mil 错误） | 需板厂 EQ 确认叠孔 vs 错孔良率 | **优先错孔（Staggered L1–L2 与 L2–L3 错开）**；仅在空间极端受限且板厂书面批准铜填叠孔时局部使用叠孔 | 0.80 mm 薄板二阶叠孔在多次无铅回流下易出现铜界间微裂纹（IPC-WP-019 重点风险），错孔可靠性显著更高。 | 
| **L3–L4 芯内机械埋孔** | Ø0.1524 mm（6 mil）孔 / Ø0.3048 mm（12 mil）盘 | 标准 **0.15–0.55 mm** 树脂塞孔盖帽（极限 0.10 mm，限穿透介质 ≤ 1.0 mm） | **Ø0.15 mm（6 mil）机械埋孔 / Ø0.25–0.30 mm 焊盘**，树脂塞孔电镀盖帽（纵横比 0.418 / 0.15 ≈ 2.79，远低于机械孔上限） | 避免将 6 mil 埋孔紧贴激光盲孔放置，按板厂 EQ 锁定盲孔-埋孔最小孔壁间距。 | 
| **线宽 / 线距** | 4 mil 线宽 / 6 mil 间距（局部残留 3 mil） | 标准 **3 / 3 mil**（0.0762 mm）；极限 **2.7 / 2.7 mil** | **BGA 扇出区局部 3 / 3 mil**（`0.0762 mm`），出 BGA 区域立即加宽至 **4 / 4 mil** 以上 | L2/L5 尽量保持完整参考地平面，数字信号优先分配在 **L3 / L4** 内层并紧邻 L2/L5 地平面。 | 
| **阻焊与焊盘类型** | 现有 0.195 mm 焊盘 + 2 mil 阻焊扩展 | 激光微盲孔需配合 ENIG/OSP 表面处理 | NSMD（非阻焊限定）焊盘 + **ENIG（化镍浸金）**；激光微盲孔严格居中盘中孔，不在焊球间留露铜过孔 | 0.35 mm 球距下极难制作完整阻焊桥，通常采用组开窗（Gang Relief）或激光高精度 LDI 绿油，需 SMT 厂与板厂共同评审钢网开口。 | 

### 3.3 多层信号连接与回流完整性硬约束

1. **禁止“飞线式”远距回流**：R6 中 K4 换层点距最近跨层地孔达 **10.73 mm**（[R6 BLOCKED.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/BLOCKED.md)），对高速边沿（I2S BCLK 最高 8 MHz，上升沿数纳秒）会形成大环路天线并恶化 2.4 GHz BLE 接收灵敏度。在 6 层 2+2+2 结构中，**每处信号从 L1→L3/L4→L6 换层点周围 `≤ 1.5 mm` 内必须就近放置 L2↔L5 地缝合过孔**。

2. **反焊盘净距控制**：L2/L5 地平面在微盲孔/埋孔处的反焊盘净距按板厂 EQ 与 R6 筛查基线控制（R6 筛查 `k4-native-clearance-notch.json` 验证 10.15 mil 净距下地平面仍保留 **99.56%** 面积），严禁多个反焊盘连成细长槽口割断 RF 回流路径。

## 4. K4 / K5 I2S、BCLK 引脚重映射的电气与固件兼容性验证

### 4.1 Nordic 原厂引脚与 I2S 外设证据核对

经远程浏览器直接核对 [Nordic nRF5340 Pin assignments（Table 3 WLCSP95）](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html) 与 [Nordic nRF5340 I2S 外设规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html)：

| 球位 | 原厂引脚名 | 原厂功能类型 | Recommended usage 标注 | 现行网络 / 建议角色 | 原厂兼容性判定 | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| **`K4`** | `P0.22` | Digital I/O（General purpose I/O） | 空（无低频/射频限制） | `I2S_LRCK_1V8`（保留或可迁） | **完全兼容**，无射频敏感或低频限制。 | 
| **`K5`** | `P0.20` | Digital I/O（General purpose I/O） | 空（无低频/射频限制） | 原 `I2S_BCLK_1V8`（建议释放为 NC） | 电气兼容，但物理位于内圈且 R6 有界筛查无顶层逃线。 | 
| **`L9`** | `P0.15` / `IO2` | Digital I/O / Dedicated pin for QSPI | `QSPI`（仅在使用 QSPI 时专用） | **候选新 `I2S_BCLK_1V8`（SCK）** | **完全兼容**：当前 PCB3 未外接 QSPI 芯片，`P0.15` 作为通用 GPIO 可通过 `PSEL.SCK` 映射为 I2S 位时钟。 | 

### 4.2 I2S 电气特性与重映射兼容性评估

1. **寄存器级全引脚可重映射**：`nRF5340` 的 5 路 I2S 信号（`MCK`、`SCK`、`LRCK`、`SDIN`、`SDOUT`）无任何硬绑定球位，完全由 `PSEL.MCK`（`0x560`）、`PSEL.SCK`（`0x564`）、`PSEL.LRCK`（`0x568`）、`PSEL.SDIN`（`0x56C`）、`PSEL.SDOUT`（`0x570`）寄存器配置，其中 `PORT`（bit 5）支持 `P0/P1`，`PIN`（bits 4:0）支持 `0..31`，`CONNECT`（bit 31，`0 = Connect`）控制通断（[Nordic I2S](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html)）。

2. **时钟频率与时序余量充裕**：

   * `f_MCK` 最大 `12.288 MHz`，`f_SCK`（BCLK）最大 `8.000 MHz`，`f_LRCK` 最大 `96 kHz`，占空比 `45%–55%`；

   * `t_SCK_LRCK` 为 `-5 ~ +5 ns`（典型 `0 ns`），`t_S_SDIN ≥ 20 ns`、`t_H_SDIN ≥ 15 ns`，`t_S_SDOUT ≤ 50 ns`、`t_H_SDOUT ≥ 13 ns`（[Nordic I2S](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html)）。

   * 在 PCB3 窄板短距离走线（数厘米级，传播延迟 < 0.3 ns）下，将 `BCLK` 从 `K5` 移至外圈 `L9` 不会导致建立/保持时间违例；仅需保证 `BCLK` 走线远离 `BLE_RF`/`DECR`（≥ 12 mil）并紧贴 L2/L5 完整地平面，必要时在驱动端预留 `22–33 Ω` 串联阻尼电阻位置以抑制过冲和 2.4 GHz 谐波辐射。

3. **关键固件与默认电平陷阱（原厂明确要求）**：

   * **I2S 禁用与 System OFF 状态**：Nordic 文档明确指出，当 I2S 模块禁用或芯片进入 System OFF 时，I2S 外设不再控制物理引脚，**必须在 GPIO 外设中直接配置这些引脚的方向与电平**（Master 模式下 `MCK/LRCK/SCK/SDOUT` 禁用前输出 `0`，`SDIN` 为输入）。

   * **下拉电阻必须物理闭环**：R6 研究中 `K4` 的 100 kΩ 下拉 `R4.1` 尚未找到保留阻焊的接法，且 `K5→L9` 候选的 `J1.P11` 与 100 kΩ 下拉 `R3.1` 仍未闭环（[R6 hdi/README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md)）。若缺少有效下拉或未在 Zephyr `pinctrl` sleep 状态拉低，系统休眠/上电瞬间可能导致音频功放（`U10`）误触发 POP 音或浮空漏电。

   * **软件核归属与 QSPI 禁用检查**：在 nRF Connect SDK / Zephyr 设备树（DTS）中，需确认 `i2s0` 归属 Application Core，将 `&i2s0_default` / `&i2s0_sleep` 中的 `I2S_SCK_M` 由 `P0.20` 改为 `P0.15`，确认 `&qspi` 状态为 `disabled`，并排查 `P0.15` 未与开发板/MCUboot 默认 LED、按键或串口引脚冲突。

## 5. 现有封装与其他真实封装/处理器方案综合对比

结合 PCB3 现有 **5.20 mm 板宽**、**功耗**、**2.4 GHz 射频**、**nRF Connect SDK 双核软件兼容**及**整机 40 g 目标**，对 6 种真实可采购方案进行横向对比：

| 对比维度 | 方案 A（首选）：`nRF5340-CMAA` (WLCSP95) | 淘汰项：`nRF5340-CLAA` (WLCSP95) | 方案 B（备选）：`nRF5340-QKAA` (aQFN94) | 第三方模组：`Raytac MDBT53V` / `MDBT53-1M` | 下一代评估：`nRF54L15` (`CSP47` / `QFN40`) | 淘汰项：`nRF52840` (`WLCSP94` / `QFN48`) | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | 
| **封装尺寸与高度** | **4.390 × 3.994 mm**，高 0.449 mm (Nom)，0.35 mm 球距（[Nordic 机械规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html?contentId=Eklj6e1CyGsPLBrPbUCj8Q)） | 4.390 × 3.994 mm，高 0.404 mm (Nom)，**NRND 不推荐新设计**（[Nordic Ordering](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ordering_info/doc/ordering_info.html)） | **7.00 × 7.00 mm**，高 ≤ 0.85 mm，0.4 mm 节距（[Nordic 机械规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html?contentId=Eklj6e1CyGsPLBrPbUCj8Q)） | `MDBT53V`: **7.8 × 12.4 × 1.85 mm**；`MDBT53-1M`: **9.3 × 14.3 × 1.85 mm**（[Raytac](https://www.raytac.com/product/ins.php?index_id=135) / [SparkFun](https://www.sparkfun.com/raytac-bluetooth-5-2-module-mdbt53-1m.html)） | `CSP47`: **2.45 × 2.25 × 0.42 mm**；`QFN40`: **5.0 × 5.0 × 0.85 mm**（24 GPIO）（[Nordic nRF54L15](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/keyfeatures_html5.html)） | `WLCSP94`: 3.5 × 3.6 mm；`QFN48`: 6.0 × 6.0 mm（[Nordic BLE](https://www.nordicsemi.com/Products/Wireless/Bluetooth-Low-Energy)） | 
| **PCB3 5.20 mm 板宽适配** | **唯一直接适配**（单边余量 0.60 mm，满足 0.35 mm 板边净距） | 尺寸适配，但料号生命周期受阻 | **不适配**（超宽 1.80 mm，需扩板至 ≥ 8.5–9.0 mm 并过 MECR-01） | **严重超宽超厚**（超宽 2.6–4.1 mm，无法装入镜腿） | `QFN40` 5.0 mm 仅余单边 0.10 mm **不合规**；`CSP47` 可适配但仍为超细间距 WLCSP | `QFN48` 超宽；`WLCSP94` 仍需 HDI | 
| **PCB 工艺与可制造性** | 需 **6 层 2+2+2 HDI + 铜填激光 VIPPO** + 板厂 EQ | 同左，且焊球更小（0.12–0.18 mm），贴装窗口更窄 | 0.4 mm 节距相对宽松，但内圈仍需 **IPC-4761 Type VII 填孔盖帽 VIPPO** | 常规 4/6 层通孔板即可，无需 HDI | `CSP47` 仍需 HDI 激光微盲孔；`QFN40` 无需 HDI 但装不下 | `WLCSP94` 同样需 HDI | 
| **功耗与热阻** | 0 dBm TX **3.4 mA** / RX **2.7 mA**（[nRF5340 PB](https://www.nordicsemi.com/-/media/Software-and-other-downloads/Product-Briefs/nRF5340-SoC-PB.pdf)）；模拟 θJA **28.51 °C/W**（[封装分析](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)） | 同 CMAA | 同 CMAA；带中心散热盘，模拟 θJA **20.74 °C/W**（散热更优） | 与 nRF5340 同源，屏蔽罩+模组基板增加厚度 | 0 dBm TX **4.8 mA** / RX **3.4 mA** @ 3 V，休眠 0.7–2.9 µA（[Nordic nRF54L15](https://www.nordicsemi.com/Products/nRF54L15)） | 功耗明显高于 nRF5340（nRF5340 TX 降 29%、RX 降 41%） | 
| **射频与光敏风险** | RX 灵敏度 **-98 dBm**；**裸硅侧面/球侧光敏**，须加遮光/屏蔽 | 同 CMAA | RX 灵敏度 **-98 dBm**；塑封体无光敏问题，中心 VSS 焊盘接地更稳 | 自带认证与天线，但镜腿内空间排布受限 | 最大 TX +8 dBm (CSP)，灵敏度 -96 dBm；CSP47 同样有裸硅防护需求 | 灵敏度 -95 dBm（比 nRF5340 低 3 dB） | 
| **软件与音频架构兼容** | **100% 兼容**（双 Cortex-M33 128/64 MHz、1 MB+256 KB Flash、512+64 KB RAM、原生 LE Audio） | 100% 兼容 | **100% 兼容**（仅引脚映射微调） | 100% 兼容 | **需大改固件**：单 Cortex-M33 + RISC-V 协处理器、256 KB RAM、无 USB，双核 IPC 与音频栈需重写 | **不兼容**：单核 64 MHz，无双核 LE Audio 隔离能力 | 
| **整机 40 g 目标影响** | **最优**（芯片体积极小、0.80 mm 薄板、无结构增重） | 同左 | **负面**（PCB3 加宽 + 镜腿外壳重开模增重约 1.5–3 g，且破坏佩戴重心） | **严重负面**（模组厚度 1.85 mm + 扩板增重显著） | `CSP47` 重量优，但 EVT-1 研发风险不可控 | 不满足音频性能基线 | 
| **阶段结论** | **EVT-1 明确首选** | **禁用（NRND）** | **备选 B（仅当 HDI EQ 失败且 MECR-01 通过）** | **排除** | **留作 V2.0 架构预研** | **排除** | 

## 6. 必须实际验证的工程放行条件（禁止将理论几何视为制造通过）

在取消 **`NOT FOR FAB`** 标记并投板前，以下 6 类实测与签核条件**必须全部闭环**，缺一不可：

1. **板厂 HDI 工艺 EQ 书面签核（Fab EQ Gate）**：

   * 必须向目标板厂（如 JLCPCB HDI 产线或同等 2+2+2 能力板厂）提交 PCB3 0.80 mm 6 层 2+2+2 叠层草图与 U11 局部 Gerber，取得关于 **Ø0.075 mm 激光铜填盲孔**、**Ø0.195–0.20 mm 捕获盘**、**错孔/叠孔允许间距**、**3/3 mil BGA 局部线宽线距**、**Ø0.15 mm 树脂塞孔埋孔** 及 **50 Ω 单端射频线宽** 的正式书面 EQ 确认。

2. **EasyEDA Pro 原生规则更新与零报错签核（EDA Gate）**：

   * 在 PCB3 独立工程中导入板厂签核后的 HDI 叠层与局部 BGA 规则区，验证 **25 个受阻内圈球全部 100% 逃线闭环**，确保 **0 处未连通飞线、0 处 Hole-to-Hole 冲突、0 处铜箔短路/间距违规、0 处网表差异**。

3. **首板物理可靠性与 SMT 工艺验证（PCBA / Cross-Section Gate）**：

   * 投产 5–10 片 PCB3 首板（含工艺边 coupon），执行 **微盲孔金相切片（Cross-section）** 检查填铜饱满度与二阶界面结合，经 3 次无铅回流热冲击测试无微裂纹；贴装 `nRF5340-CMAA` 后 100% 执行 **X-Ray 透视检测**，确认 95 球无连锡、无冷焊、盘中孔空洞率达标。

4. **K4/K5（→L9）I2S 音频与低功耗实测（Electrical / Firmware Gate）**：

   * 示波器实测 `L9 (BCLK)`、`K4 (LRCK)`、`SDIN`/`SDOUT` 眼图与边沿单调性，确认 `t_SCK_LRCK` 满足 ±5 ns 规范且无明显振铃；

   * 验证上电初始化、I2S 启停切换、System OFF 休眠/唤醒全流程中 **`R3.1`/`R4.1` 100 kΩ 下拉生效**、无音频 POP 音、无引脚浮空额外漏电（静态电流符合预算）。

5. **2.4 GHz 射频传导与辐射实测（RF Gate）**：

   * 实测 `BLE_RF` 匹配网络回波损耗（S11 ≤ -10 dB）、0 dBm 传导发射功率与 -98 dBm 级接收灵敏度，重点核查 **开启 I2S 音频播放时对 BLE 接收底噪（Desense）的影响**，确保 `B4 (DECR)` 退耦与 L2/L5 完整回流地有效抑制数字噪声耦合。

6. **WLCSP95 裸硅防光敏与结构跌落验证（Mechanical / Optical Gate）**：

   * 遵循 Nordic 官方要求（[WLCSP 光敏防护要求](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)），在透明镜腿或强光照射工况下验证 U11 侧面与底部遮光方案（局部屏蔽罩或黑色不透光三防/点胶），并在整机 40 g 配重下完成跌落与镜腿弯折测试，按实测决定是否引入低温返修型底部填充（Underfill）。

## 7. 供 KIMI 执行的工程变更建议（不修改当前工程，按序分步执行）

以下建议面向后续 KIMI / 硬件工程师在新建分支或副本中执行，**严禁直接覆盖现行基线，且在全部 Gate 通过前保持 `NOT FOR FAB`**：

### Step 0：基线冻结与板厂 EQ 前置（执行任何布线前）

1. 基于 PR #54 分支创建独立 HDI 变更分支（如 `evt1-h03-r7-u11-hdi-eq`），保持 PCB1/PCB2 不动，仅隔离变更 PCB3。

2. 确认 BOM 与原理图中 U11 采购料号严格为 **`nRF5340-CMAA-R7`**（剔除任何 `CLAA` 引用），封装焊盘按 `CMAA` 官方机械尺寸复核（球径 0.19–0.25 mm，NSMD 铜盘 Ø0.195–0.20 mm，ENIG 表面处理）。

3. 将本文第 3.2 节的 6 层 2+2+2（0.80 mm）叠层参数提交目标板厂完成 EQ 签核，拿到正式规则文件后再写入 EasyEDA Pro 规则管理器。

### Step 1：原理图与固件引脚重映射同步 ECO

1. **释放 `K5 (P0.20)`，重映射 `I2S_BCLK_1V8` 至外圈 `L9 (P0.15)`**：

   * 原理图：断开 `U11.K5` 上的 `I2S_BCLK_1V8` 并标注 `NC`；移除 `U11.L9` 的 `NC` 标记，接入 `I2S_BCLK_1V8`，确保 `U11.L9 ↔ J1.P11 ↔ U10.C1 ↔ R3.1 (100 kΩ 下拉)` 完整连接。

   * 固件同步：在 Zephyr DTS 中将 `i2s0` 的 `SCK` 引脚更新为 `P0.15`，显式配置 `i2s0_sleep` 默认下拉/输出低，并确认 `&qspi` 为 `disabled`。

2. **闭环 `K4 (P0.22 / I2S_LRCK_1V8)` 拓扑**：

   * 在原理图与布局中核实 `R4.1`（100 kΩ 下拉）与 `R3.1` 可就近挪移至 `U10` 或 `J1` 侧低密度区，无需挤在 U11 阻焊开窗边缘强行接出，彻底消除 R6 中 `R4.1` 无阻焊安全接法的死锁。

3. **按需二级减压（仅在 Step 2 联合扇出拥挤时启用）**：

   * 统计 U11 外圈其余显式 `NC` 通用 GPIO，按同一同步 ECO 流程优先外迁 `K2 (AMP_SD_REQ_1V8)`、`K3 (IPC_NRF_TX_1V8)`、`J4 (I2S_AMP_DIN_1V8)`、`J5 (I2S_S3_DOUT_1V8)`，确保每迁出 1 球即减少 1 组内圈二阶盲孔。

### Step 2：PCB3 0.80 mm 2+2+2 HDI 叠层与 25 球联合扇出

1. **配置 6 层 2+2+2 叠层与局部规则区**：

   * 在 EasyEDA Pro 叠层管理器中将 PCB3 从默认 `JLC06161H-3313`（1.7873 mm）切换为板厂签核的 `0.80 mm` 6 层 2+2+2 叠层，声明 `L1–L2`、`L2–L3`、`L4–L5`、`L5–L6` 四组微盲孔与 `L3–L4` 芯内机械埋孔。

   * 仅在 U11 封装投影区外扩 0.5 mm 范围内启用板厂签核的 **HDI 局部规则**（3/3 mil 线宽线距、Ø0.075/0.20 mm 铜填微盲孔），BGA 区外维持 ≥ 4 mil 线宽与常规间距。

2. **按优先级分批完成 25 球联合扇出**：

   * **第 1 批（A 类 7 颗地网 + C 类 4 颗退耦/DCDC）**：7 颗地网球就近 L1→L2 微盲孔直连 L2 地平面；`B4 (DECR)`、`B5 (DECN)`、`B6 (DCC)`、`B8 (DECA)` 最短路径扇出至紧邻电容，严格维持 `BLE_RF`/`DECR` ≥ 12 mil 保护区。

   * **第 2 批（D 类 `F11` 32.768 kHz 晶振 + B 类 5 颗 `1V8_SYS`）**：`F11` 短线避让高速数字线；5 颗 `VDD` 经微盲孔汇入 L3 电源铜皮并就近去耦。

   * **第 3 批（剩余 E 类数字信号 + `F2/G2` 调试复位）**：优先采用 **L1–L2 与 L2–L3 错孔**扇出至 L3/L4 走线，在所有换层点 `≤ 1.5 mm` 范围内补齐 L2↔L5 地缝合过孔（彻底消除 R6 10.73 mm 远距回流缺陷），并将 PCB3 其余 129 段 3 mil 常规走线视空间加宽至 4 mil。

### Step 3：原生 DRC、网表与回放验证

1. 执行 EasyEDA Pro 原生 **Update PCB from Schematic（Import Changes）**、**全板 ERC** 与 **严格 DRC**，确认 PCB3 未连通数由 R6 的 132 降至 **0**、Hole-to-Hole 报错 **0**、间距/短路报错 **0**。

2. 导出 Gerber、钻孔分表（区分激光盲孔 L1–L2/L2–L3/L4–L5/L5–L6 与机械埋孔 L3–L4）、IPC-2581/ODB++ 与坐标文件，先送板厂做 **免费/正式 DFM 二次复核（Pre-CAM EQ）**；确认无异常后方可按第 6 节流程发起首板打样与实测验证。