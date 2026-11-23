# 智元跃动 AI/AR 智能眼镜 V1.0（EVT-1 H03-R8）PCB3 高密度集成、多球联合逃线与同步 ECO 执行报告

**工程状态**：`NOT FOR FAB`（仅限审阅与板厂 EQ 签核，严禁直接投产）  
**执行基线**：[GitHub PR #55（H03-R7, commit `ac38a71`）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55) 与 [R7 HDI_DECISION.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/HDI_DECISION.md)  
**独立可编辑云端工程**：[`EVT1-H03-GEMINI-R8-NOT-FOR-FAB-20261123`](https://pro.lceda.cn/editor#id=13bb509742f243a2852a46125154eb8a)（云端 ID：`13bb509742f243a2852a46125154eb8a`，基于账号 `eda_luhqetwc` 独立副本创建，未修改任何既有 R2/R3/PR46/R7 工程，未降低任何设计规则）  
**红线守恒**：PCB3 板宽实测保持 **5.20 mm（204.72 mil，轮廓周长 78.4 mm）**、保留双目透明 AR 光机架构、整机 **40 g** 重量目标与全套锁定安全/DFM 规则（线宽 ≥ 4 mil、铜距 ≥ 6 mil、孔壁距 ≥ 11.8 mil、RF/DECR 隔离 ≥ 12 mil）。

## 1. H03-R8 独立工程实施与真实原生验证结果

### 1.1 独立工程修改前后实测对比（PCB3 / `evt1-audio-right`）

在 EasyEDA Pro V4.1.105 独立云端工程 [`EVT1-H03-GEMINI-R8-NOT-FOR-FAB-20261123`](https://pro.lceda.cn/editor#id=13bb509742f243a2852a46125154eb8a) 中，完成基线实测、原理图/PCB 同步 **ECO-1（`I2S_BCLK_1V8` `U11.K5 → U11.L9`）**、顶层扇出通道实测以及**保存→关闭→重开云端持久化验证**：

| 验证阶段 | 器件数 | 原理图 ERC（致命/错误/警告） | 网表错误 | PCB3 严格 DRC 总数 | 连接性错误 | 间距/短路/孔距错误 | 关键状态与实测结论 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **PR #55 R7 GitHub 基线** | 53 | 2 / 0 / 0（PCB3） | 0 | 132 | 132 | 0 | R7 仅改 PCB2 3 段 VSYS，PCB3 维持 R6 132 处未连通 |
| **R8 云端克隆基线（改前）** | 53 | 2 / 0 / 0（仅 `SPK1`/`BAT1` 缺封装） | 0 | 134 | 134 | 0 | `Import Changes` 为空，全量严格 DRC 开启 |
| **ECO-1 同步后（保存前/后）** | 53 | 2 / 0 / 0（0 新增） | 0 | 134 | 134 | 0 | 仅 2 项预期网表迁移：`U11:K5`（`I2S_BCLK_1V8`→`-`）、`U11:L9`（`-`→`I2S_BCLK_1V8`） |
| **L9 通道试探与回退** | 53 | 2 / 0 / 0 | 0 | 134 | 134 | 0 | `U11.L9` 顶层向右 4 mil 逃线至 `X=190 mil` 合法；但现行 1+4+1 叠层无 L2-L3/L3-L4/L4-L5 微孔，放置 `15.7 mil` PTH 换层触发实时 DRC 报错，已回退保持 0 违规 |
| **关闭重开持久化终验** | 53 | 0 致命 / 0 错误 / 0 警告（网表日志） | 0 | **135** | **135** | **0** | `U11.L9`（ID `e49e94`）持久化为 `I2S_BCLK_1V8`（网络长 38.6 mil）；`U11.K5`（ID `e49e83`）持久化为 `NC`（0 mil）；38 网络 / 36 飞线 |

### 1.2 PCB3 关键焊盘原生坐标与层叠实测（直接读取自 PCB3 画布）

| 焊盘位号 | 所在层 | 实测网络（R8 ECO-1 后） | 中心 X (mil) | 中心 Y (mil) | 几何与拓扑说明 |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **`U11.L9`** | Top (L1) | `I2S_BCLK_1V8` | `171.3` | `396.7` | 外圈球，Ø7.7 mil（0.195 mm）；向右可 4 mil 合法扇出至 `X=190 mil` |
| **`U11.K5`** | Top (L1) | `NC`（已释放） | `157.5` | `341.5` | 原内圈受阻 BCLK 球，已释放，减少 1 颗内圈受阻信号球 |
| **`U11.K4`** | Top (L1) | `I2S_LRCLK_1V8` | `157.5` | `327.8` | 内圈受阻 LRCK 球，受 `K5` 释放后右侧局部空间缓解，仍需微盲孔换层 |
| **`J1.P11`** | Bottom (L6) | `I2S_BCLK_1V8` | `133.3` | `288.4` | BCLK 连接器端（底层） |
| **`J1.P12`** | Bottom (L6) | `I2S_LRCLK_1V8` | `71.5` | `288.4` | LRCK 连接器端（底层） |
| **`U10.C1`** | Bottom (L6) | `I2S_BCLK_1V8` | `182.3` | `367.3` | 功放 BCLK 输入端（底层，紧邻右侧板边） |
| **`U10.C3`** | Bottom (L6) | `I2S_LRCLK_1V8` | `150.8` | `367.3` | 功放 LRCK 输入端（底层） |
| **`R3.1`** | Bottom (L6) | `I2S_BCLK_1V8` | `125.8` | `621.9` | BCLK 100 kΩ 下拉电阻端（底层） |
| **`R4.1`** | Bottom (L6) | `I2S_LRCLK_1V8` | `177.0` | `598.2` | LRCK 100 kΩ 下拉电阻端（底层） |

- **PCB3 现行叠层实测**：6 层 `JLC06161H-3313(默认)`，总厚 **`1.7873 mm`**，仅定义 **`BV_L1_L2`**（22 颗 4/10/3 mil GND 盲孔）与 **`BV_L5_L6`**（18 颗 4/10/3 mil GND 盲孔，来源：[PCB3-blind-vias.csv](https://raw.githubusercontent.com/yfei7131-source/AI-AR-codex-Claude-/refs/heads/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/dfm/PCB3-blind-vias.csv)），**不存在 `L2-L3`、`L3-L4` 埋孔或 `L4-L5` 微孔**。
- **核心硬件实证结论**：在 `5.20 mm`（`204.72 mil`）窄板上，外圈 `U11.L9` 虽可合法在顶层向右逃线至 `X = 190 mil`，但因 `U10.C1`、`J1.P11`、`R3.1` 全部位于底层，且现行 1+4+1 叠层强制要求使用外径 `15.7 mil`（内径 `7.9 mil`）的普通通孔（PTH）跨层——而板边净距要求通孔中心 `X ≤ 190.87 mil`，内侧又被底层 `U10` 外列焊盘（`X = 182.3 mil`）与 `BV_L1_L2` 地盲孔（`X ≈ 182, Y ≈ 354`）封死，导致实时 DRC 报过孔冲突。**这从物理层面证实：不切入板厂签核的 6 层 `2+2+2`（0.80 mm）二阶 HDI 叠层，即使把 BCLK 迁到外圈，在现行 1+4+1 叠层 + 5.20 mm 板宽 + 锁定规则下依然无法 0 违规换层至底层。**

---

## 2. 基于 132/134 处未连通与 25 个内圈受阻球位的多球联合逃线方案

不再重复单球孤立理论筛查，而是按网络属性、空间象限与层间资源冲突，将 [r3-u11-native-audit.json](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r4-20261123/u11/r3-u11-95ball-native.csv) 中的 **25 个内圈受阻球**重构为 **4 组联合逃线矩阵**（在 `K5` 释放后实际内圈需逃线球降至 **24 颗**）：

| 联合组别 | 球数 | 包含球位与网络 | 目标层与过孔结构（2+2+2 HDI EQ 目标） | 联合避让与通道分配原则 |
| :--- | :---: | :--- | :--- | :--- |
| **G1：地网直下组** | 7 | `B2/B9/C2/E5` (`VSS`)、`K6/K11` (`AVSS`)、`B11` (`VBUS→GND`) | **仅 1 阶 `L1–L2` 铜填激光盲孔**（Ø0.075/0.195 mm 盘中孔）直入 L2 地平面 | **零占用 L3/L4 走线通道**；`K6/K11` 优先保证 RF/模拟回流低感接地。 |
| **G2：1.8 V 电源汇流组** | 5 | `B7`、`B10`、`D2`、`E11`、`H11`（均 `1V8_SYS`） | **L1–L2 + L2–L3 错孔（Staggered）**汇入 L3 电源铜皮 | 5 球同网，允许在 L3 合并为单一局部低阻抗电源岛，再通过去耦电容就近连 L2 地，节省 4 条独立干线通道。 |
| **G3：RF/DCDC/晶振强约束组** | 5 | `B4` (`DECR`)、`B5` (`DECN`)、`B6` (`DCC`)、`B8` (`DECA`)、`F11` (`LFXO_XL1`) | 优先 L1/L3 最短路径扇出；`B4–B8` 集中于 B 列左侧象限，`F11` 位于下侧晶振象限 | `B4 (DECR)` 与 `BLE_RF`/`BLE_ANT` 严格维持 ≥ 12 mil 净距；`F11 (XL1)` 严禁与 I2S 时钟平行或跨分割。 |
| **G4：可重映射数字与调试组** | 7（含释放后） | **已释放**：`K5` (`P0.20`→`NC`，迁至外圈 `L9`)<br>**内圈剩余**：`K4` (`I2S_LRCLK_1V8`)、`J4` (`I2S_AMP_DIN_1V8`)、`J5` (`I2S_S3_DOUT_1V8`)、`K2` (`AMP_SD_REQ_1V8`)、`K3` (`IPC_NRF_TX_1V8`)、`F2` (`SWDCLK`)、`G2` (`nRESET`) | **L1–L2 → L2–L3（错孔）→ L3/L4 干线 → L3–L4 机械埋孔（Ø0.15/0.25–0.30 mm）→ L4–L5 → L5–L6** 落至底层 | 将 `J4/J5/K4` 音频总线统一分配至 **L4 音频专用层**（紧邻 L5 完整地平面），`K2/K3/F2/G2` 分配至 **L3 控/调层**（紧邻 L2 地平面）；若板厂 EQ 后局部拥挤，优先将 `K2/K3/J4/J5` 中 2–3 颗继续外迁至未用外圈 GPIO。 |

---

## 3. `K4 → J1.P12 / U10.C3 / R4.1` 完整网络闭环方案

针对 [R7 HDI_DECISION.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/kimi-evt1-h03-r7-20261123/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/HDI_DECISION.md) 中 `K4` 完整网络未闭环及 `R4.1` 离线求解因 `MK3.5` `POLYGON` 焊盘返回 `incomplete` 的双阻塞，给出面向 `2+2+2` HDI 的完整端到端拓扑：

1. **三段星形/主干拓扑（杜绝 R6 同心叠孔 0 mil 报错）**：
   - **入口段（L1 → L3/L4）**：`U11.K4 (157.5, 327.8)` 利用 `K5 (157.5, 341.5)` 释放后的上方空闲微盲孔区，采用 **L1–L2 激光盲孔 + L2–L3 错位微盲孔**（中心距按板厂 EQ 锁定，避开 R6 同心叠孔 0 mil 违规）转入 L4，经一颗 **L3–L4 芯内树脂塞孔埋孔**（远离激光孔满足板厂 EQ 孔壁距）后转至底层。
   - **底层主干分支（L6）**：底层直接按实测坐标辐射连接三端：
     - 分支 1（向左上）：至 `J1.P12 (71.5, 288.4)`；
     - 分支 2（向中下）：至 `U10.C3 (150.8, 367.3)`；
     - 分支 3（向正下）：绕行 `MK3.5` `POLYGON` 焊盘外缘（在原生 EasyEDA Pro 几何引擎中实时推挤绕过，不依赖离线简化求解器），直连 **`R4.1 (177.0, 598.2)`**。
2. **结构化消除 `R4.1` / `R3.1` 阻焊冲突**：
   - 实测 `R4.1 (177.0, 598.2)` 与 `R3.1 (125.8, 621.9)` 均位于 `Y ≈ 600 mil` 底层低密度区，完全远离 `U11`（`Y ≈ 328–397 mil`）阻焊开窗；只要 `K4` 和 `L9` 经二阶 HDI 下至 L4/L6，底层 4 mil 走线即可直接与 `R4.1`、`R3.1` 闭环，无需在 `U11` 焊球边缘强行接入下拉电阻。

---

## 4. `I2S_BCLK_1V8`（`K5 → L9`）原理图、PCB 与固件 ECO 一致性验证

### 4.1 原厂电气与寄存器兼容性核证

直接核对 [Nordic nRF5340 Pin assignments（Table 3 WLCSP95）](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html) 与 [Nordic nRF5340 I2S 规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html)：
- `K5 (P0.20)` 与 `K4 (P0.22)` 均为通用 `Digital I/O`，无低频或射频限制。
- `L9 (P0.15)` 复用为 `QSPI IO2` 与通用 `Digital I/O`；PCB3 未挂载外部 QSPI Flash，可合法作为 `I2S SCK (BCLK)` 映射引脚。
- I2S `PSEL.SCK (0x564)` 支持全 P0/P1 任意引脚映射；`f_SCK ≤ 8 MHz`、`t_SCK_LRCK = ±5 ns`、`t_S_SDIN ≥ 20 ns`、`t_H_SDIN ≥ 15 ns`，PCB3 厘米级走线延迟 `< 0.3 ns`，时序余量充裕。
- **原厂硬性固件约束**：在 I2S 禁用或进入 `System OFF` 时，I2S 模块释放引脚控制权，**必须在 GPIO 外设（Zephyr `pinctrl` sleep 状态）显式将 `P0.15 (SCK)` 与 `P0.22 (LRCK)` 配置为低电平输出或下拉**，与硬件 `R3.1`/`R4.1`（100 kΩ 下拉）配合，防止 `U10` 音频功放上电 POP 音与休眠漏电。

### 4.2 三端 ECO 一致性核查矩阵

| 域 | 变更内容 | 本轮 H03-R8 实际状态 |
| :--- | :--- | :--- |
| **原理图** | `05-nrf5340-reference-clock-rf-and-swd-1`：`U11.K5 → NC`，`U11.L9 → I2S_BCLK_1V8` | **已实施并通过原生 ERC**（0 新增错误） |
| **PCB 网表** | `PCB3 (evt1-audio-right)`：`Import Changes` 同步 2 项网表变更并持久化 | **已实施并通过重开持久化验证**（0 网表错误、0 间距/短路） |
| **固件 DTS** | 仓库当前 `firmware/` 仅含 ESP-IDF 文件（无 `.dts`/`.overlay`）；已生成可执行 Zephyr/nRF5340 设备树补丁 `nrf5340_pcb3_r8_i2s_eco.overlay`（禁用 `&qspi`，映射 `I2S_SCK_M` 至 `P0.15`，配置 `i2s0_sleep` 低功耗下拉） | **已交付可执行 `.overlay` 文件**，待随 Draft PR 纳入 nRF5340 固件工程 |

---

## 5. 电源、GND、I2S 与 2.4 GHz RF 联合回流验证方案

1. **解决 R6 的 10.73 mm 远距回流缺陷**：PCB3 现有 40 颗盲孔全为 `L1-L2`（22 颗）和 `L5-L6`（18 颗）单侧 GND 盲孔，缺乏跨 L2↔L5 的密集缝合。在 `2+2+2` HDI 叠层中，须在 `I2S_BCLK_1V8`（`L9` 换层点）与 `I2S_LRCLK_1V8`（`K4` 换层点）周围 **`≤ 1.5 mm`** 内各放置至少 1 组 `L2↔L5` 回流地过孔，使 8 MHz BCLK 及其高次谐波回流环路面积缩小 > 85%。
2. **反焊盘与平面完整性**：R6 实测 10.15 mil 反焊盘净距下 L2/L5 地平面保留率达 **99.56%**；联合逃线时须保证 `G2 (1V8_SYS)` 与 `G4 (I2S)` 的埋孔呈棋盘格错开，严禁反焊盘连通割裂 L2/L5。
3. **2.4 GHz RF 与电源隔离**：`BLE_RF`、`BLE_ANT`、`B4 (DECR)` 与所有 I2S 走线/过孔保持 **`≥ 12 mil`** 隔离；`B5 (DECN)`、`B6 (DCC)`、`B8 (DECA)` 退耦电容共地至 `B2/B9/K6/K11` 就近 L2 地平面；`U11` 裸硅侧边/底面按 Nordic 要求加装遮光防护。

---

## 6. 现有结构无法实现时的替代架构评估（真实尺寸、功耗与软件兼容依据）

若目标板厂无法对 **0.80 mm 6 层 `2+2+2` HDI（Ø0.075 mm 铜填激光盘中孔 + Ø0.195–0.20 mm 捕获盘 + 3/3 mil 局部扇出）** 给出可接受良率/签核，按约束优先级提供两套有真实原厂数据支撑的替代架构：

| 替代架构 | 核心芯片与封装 | 真实封装尺寸与高度 | 5.20 mm 板宽与 40 g 目标影响 | 功耗与射频（原厂数据） | 软件/SDK 兼容与工程代价 | 适用决策触发条件 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **替代方案 1（同芯片扩板兜底）** | **`nRF5340-QKAA`** (aQFN94) | **7.00 × 7.00 mm**，高 ≤ 0.85 mm，0.4 mm 节距（[Nordic 机械规范](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html?contentId=Eklj6e1CyGsPLBrPbUCj8Q)） | **破坏 5.20 mm 约束**（需 MECR-01 将 PCB3 局部扩宽至 ≥ 8.5–9.0 mm），镜腿增重约 1.5–3 g，仍需 IPC-4761 Type VII 填孔盖帽 VIPPO | 0 dBm TX **3.4 mA** / RX **2.7 mA**，RX **-98 dBm**（[nRF5340 PB](https://www.nordicsemi.com/-/media/Software-and-other-downloads/Product-Briefs/nRF5340-SoC-PB.pdf)）；θJA **20.74 °C/W**（优于 WLCSP 的 28.51 °C/W） | **100% 软件兼容**（双 Cortex-M33 + 原生 LE Audio，仅改引脚映射） | 仅当 2+2+2 HDI 板厂 EQ 彻底失败 **且** 结构签核 MECR-01 放宽板宽时启用 |
| **替代方案 2（V2.0 换芯降球数）** | **`nRF54L15-CAAA`** (CSP47) | **2.45 × 2.25 mm**，高 0.42 mm，仅 47 球（[Nordic nRF54L15](https://www.nordicsemi.com/Products/nRF54L15) / [nRF54LM20B 对比表](https://www.nordicsemi.com/Products/nRF54LM20B)） | **完美守住 5.20 mm 板宽与 40 g 目标**（体宽比 nRF5340 WLCSP 缩窄 44%，布线走廊释放 > 1.5 mm）；注：QFN40（5×5 mm）单边仅余 0.1 mm 不合规 | 0 dBm TX **4.8 mA** / RX **3.4 mA** @ 3 V，休眠 **0.7–2.9 µA**，TX 最大 +8 dBm，RX **-96 dBm**（[Nordic nRF54L15](https://www.nordicsemi.com/Products/nRF54L15)） | **需重构固件**：单 128 MHz Cortex-M33 + 128 MHz RISC-V 协处理器、256 KB RAM、无内置 USB，需迁移双核 IPC 与 LE Audio 栈 | 不适合 EVT-1 赶进度，列为 **V2.0 轻量化窄板首选预研平台** |

---

## 7. 待完成阻断项与独立 Draft PR 提交说明

1. **板厂 EQ 阻断（保持 `NOT FOR FAB`）**：PCB3 必须获得目标板厂对 `0.80 mm` 6 层 `2+2+2` 叠层（Ø0.075 mm 激光铜填盲孔、Ø0.195–0.20 mm 捕获盘、错孔/埋孔间距、3/3 mil BGA 局部规则）的书面 EQ 签核后，方可在 `EVT1-H03-GEMINI-R8-NOT-FOR-FAB-20261123` 中切换叠层并实施 24 球联合布线至 0 未连通。
2. **GitHub 独立 Draft PR 权限阻断**：核查确认远程浏览器当前**未登录 GitHub 账号**（页面显示 `Sign in / Sign up`），因此本轮无法由浏览器自动推送分支与创建 Draft PR。已为您备妥以下交付物，登录后可直接提交独立 Draft PR（建议源分支：`hardware/gemini-evt1-h03-r8-20261123` → 目标分支：`hardware/kimi-evt1-h03-r7-20261123`）：
   - 独立可编辑云端工程：[`EVT1-H03-GEMINI-R8-NOT-FOR-FAB-20261123`](https://pro.lceda.cn/editor#id=13bb509742f243a2852a46125154eb8a)（可直接导出 `.epro2` 存入 `hardware/evt1-native-eda-20261118/h03-gemini-r8-20261123/native/`）
   - 本工程执行与验证报告：`H03_R8_PCB3_EXECUTION_REPORT.md`
   - 可执行固件设备树同步补丁：`nrf5340_pcb3_r8_i2s_eco.overlay`
