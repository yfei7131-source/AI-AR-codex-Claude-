# 智元跃动 AI/AR 智能眼镜 V1.0 — PCB2（光学桥板）去耦布局与电源完整性设计评审报告

**文档状态**：工程评审稿（`NOT FOR FAB`，严禁修改 KIMI 原生生产工程）  
**评审日期**：2026-11-23  
**适用基线**：[GitHub PR #54（EVT-1 H03 R6 Draft）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54) · [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) · EasyEDA Pro V4.1.97  
**基线工程校验指纹（SHA-256）**：`c4ca657e50915789b7255430dd2e0f49c7828d85a2f73c42547701efbb213dd5`

## 1. 评审结论与 R6 基线核查

基于远程浏览器对 [AI-AR-codex-Claude- 仓库](https://github.com/yfei7131-source/AI-AR-codex-Claude-)、[PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)、[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)、[Lattice 半导体官方技术文档](https://www.latticesemi.com/view_document?document_id=47779) 及 [嘉立创 SMD 最小间距规范](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components) 的独立核查，PCB2（光学桥板，4.6 mm 窄板）当前核心状态与结论如下：

| 核查维度 | R6 已核实基线数据 | 当前状态与核心风险 | 来源依据 |
| :--- | :--- | :--- | :--- |
| **整机与 PCB2 DRC 基线** | 全板 257 器件；严格原生 DRC 开路 708（PCB1 340 / **PCB2 236** / PCB3 132）；0 铜间距/短路错误；PCB2 网表错误 0 | 仍有 236 处未布线开路；交付状态锁定 `NOT FOR FAB` | [PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54) |
| **PCB2 归档几何规模** | 400 段铜线、47 颗独立过孔（**40 颗盲孔**仅连外层与相邻平面 + **7 颗通孔**均属非 GND 网络）；绑定封装内正尺寸电镀通孔为 0 | L2 与 L5 均为有效 GND 平面，但缺少跨板 GND 通孔缝合，两参考地平面间高频耦合薄弱 | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) |
| **R6 已验证可执行增量** | `Y ≥ 750 mil` 区域 21 段原有 GND 走线由 3 mil 加宽至 4 mil（11 段在 `C5/C10/C32/C9` 现有地铜域，10 段在同区其他 GND 铜域） | 已通过异网铜间距 ≥ 6.2 mil、铜到板边 ≥ 12 mil 离线筛查；保留 FPGA 时钟/复位/安全信号 | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) |
| **C11 双端连接阻断** | C11 两端均无实际铜接触；底面 `Y = 104–378 mil` 共 80 个合规放置位、485 条短折线及 1 mil 八方向网格筛查结果：**0 个 VSYS 连通，0 个双端回路候选** | 仅靠原层局部微调无法解套，必须结合 `U13` 走廊重排或内层电源换层 + 局部 L5 地盲孔返流 | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) |
| **MEMS 声学区与地通孔** | 6/12 mil 与 8/16 mil GND 通孔筛查结果全部收敛于 `MK2`（[Infineon IM69D130](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf)）原生装配包络内；原位盲孔换通孔扫描未通过 | **BLOCKED**：须待声学结构组冻结麦克风声腔边界、过孔填盖与阻焊注册规则，或释放非声腔桥区 | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) |

## 2. 八颗去耦电容（C5/C8/C9/C10/C11/C12/C31/C32）独立布局评估

在桥板八颗去耦电容的联合评估中，必须同时坚守历史工程不变量：保留 `C2`（`AVDD_QUAL_RC`）与 `C3`（`AVDD_REQ_FILTER`）功能时序/滤波 RC 拓扑、AVDD 安全保护链路，以及既有 FPGA 时钟、复位与安全信号布线（[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)）。

依据 Lattice 官方 [Power Decoupling and Bypass Filtering (`FPGA-TN-02115` / `TN1068`)](https://0x04.net/~mwk/doc/lattice/ecp/PowerDecouplingandBypassFilteringforProgrammableDevices.PDF) 与 [High-Speed PCB Design Considerations (`FPGA-TN-02178` Ver 6.4)](https://canada.newark.com/site/binaries/content/assets/common/product-family-documents/lattice-lfmxo5-100t-evn/lattice-lfmxo5-100t-evn-an1.pdf?ICID=I-FP-EMB-DKHQ-LATTICE-LFMXO5-100T-EVN-TR) 准则：去耦电容应选用 X5R/X7R 低 ESL/ESR 介质（耐压 ≥ 1.8× 轨压以抑制直流偏置降额，参考 [Mach-NX Hardware Checklist](https://www.latticesemi.com/view_document?document_id=53036)），严格遵循 **“过孔 → 去耦电容焊盘 → 器件电源引脚”** 的短宽连接顺序，小容值（如 100 nF / 10 nF）最贴近负载焊盘。

| 器件位号 | R6 已核实现状与已知几何/网络信息 | 关键工程风险 | 建议位置、层别与处理策略 | 原生几何数据缺口 |
| :--- | :--- | :--- | :--- | :--- |
| **C5** | 位于 `Y ≥ 750 mil` 去耦铜域；R6 已将该组现有 GND 走线从 3 mil 加宽至 4 mil（共 11 段涵盖 C5/C10/C32/C9） | 4.6 mm 窄板边缘余量紧张，若继续移动易破坏 6.2 mil 异网间距 | **原位微调保留**；优先维持 4 mil 短宽地支线，检查就近 `L1–L2` 或 `L6–L5` 盲孔直连最近参考地平面 | 缺原生 X/Y 坐标、封装尺寸及具体供电轨名称 |
| **C8** | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) 未单独列项；[PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54) 隔离试验显示 `C1–C8` 跨层 1.8 V 试验暴露 **7 个严格间距失败** | 强行在表层穿插跨层 1.8 V 走线会触发 6.2 mil 铜间距违例 | **暂不合入表层跨层方案**；待底部 `FPGA_C...` 线束迁入 `L3/L4` 后，在释放出的 L6/L1 走廊内按 0.15 mm（6 mil）装配间距重新布置 1.8 V 电源扇出与 `BV_L5_L6` 地盲孔 | 缺 C8 精确坐标、所在面（L1/L6）及 7 处 DRC 违例明细 |
| **C9** | 属于 `Y ≥ 750 mil` 已加宽 4 mil 地铜域组（与 C5/C10/C32 同组） | 避免在加宽地线时侵占焊盘进线与时钟/安全信号隔离带 | **原位保留并巩固回流**；保持 4 mil 地线宽度，电源侧遵循“过孔 → 电容焊盘 → IC 引脚”路径 | 缺原生 X/Y 坐标、封装与具体供电轨名称 |
| **C10** | 属于 `Y ≥ 750 mil` 已加宽 4 mil 地铜域组 | 同上；需防止局部地支线形成细长串联感抗 | **原位保留**；确认其 GND 焊盘到最近盲孔的长度最短化，不与其他高频回流共用细支线 | 缺原生 X/Y 坐标与封装尺寸 |
| **C11** | **核心阻断项**：两端均无实际铜接触；底面 `Y = 104–378 mil` 目标连接 `U13.1/U13.4`（`VSYS`）与 `U13.2`/GND 盲孔；80 个候选位双端连通为 **0** | 若强行拉线必然破坏 `AVDD_REQ_FILTER` 隔离或违反 6 mil 装配/6.2 mil 铜间距 | **执行第 3 节专项解套方案**（优先方案 A：冻结机械窗口后重排 `U13` 邻接 `VSYS` 与 `AVDD_REQ_FILTER` 走廊，并采用内层电源换层 + 独立 L5 地盲孔返流） | 缺 `U13` 具体料号/封装、C11 当前精确坐标及 `c11-dual-route-tree.json` 原始阻塞坐标 |
| **C12** | **已有验证有效回流**：外表面铜簇 `C12.2` 经由既有过孔 `d66a84af7c151bc9` 直连连续 `L2` GND 平面（过孔盘距 L2 平面边界 **7.168 mil**） | 重复加线或移位可能破坏已验证的 L2 低感回路，或逼近 L2 平面边界 | **冻结地回路，严禁重复加线**（与 `C33.2` 经 `3ee8ab886f357cc2` 距 L2 边界 6.574 mil 一并保护）；仅在电源侧核验短宽进线 | 缺 C12 电源端精确网络名与坐标 |
| **C31** | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) 未单独列项，归属桥接八电容待联合重排集合 | 窄板内受底面线束挤压，缺少低感地返流通道 | **与线束换层联动布局**：待底面 `FPGA_C...` 总线迁入 `L3/L4` 后，在目标电源引脚附近配置独立 `BV_L5_L6` 或 `BV_L1_L2` 地盲孔，并满足嘉立创最小装配间距 | 缺 C31 精确坐标、封装、所属电源轨及所属器件引脚 |
| **C32** | 属于 `Y ≥ 750 mil` 已加宽 4 mil 地铜域组 | 需核验与邻近光机/FPGA 器件的 1.0 mm（QFN/BGA）或 0.15 mm（0201/0402）装配边界 | **原位保留**；维持 4 mil 局部地走线，并在原生 DRC 下复核与板边 ≥ 12 mil 余量 | 缺原生 X/Y 坐标与封装尺寸 |

## 3. C11 的 VSYS 与 GND 无法同时安全连接的根因与专项解决方案

### 3.1 阻断机理诊断

根据 [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) 的离线筛查结果，C11 在底面 `Y = 104–378 mil` 区域陷入**“几何—电气双重死锁”**：

1. **物理走廊饱和**：4.6 mm（`181.1 mil`）窄板扣除两侧 `12 mil` 铜到板边安全距后，有效布线净宽仅约 `157.1 mil`（与项目基线 ~160 mil 窄走廊一致）。在该窄带内同时挤占了 `U13` 引脚区（`U13.1/U13.4` 为 `VSYS`，`U13.2` 为 `GND`）、敏感模拟滤波节点 `AVDD_REQ_FILTER` 及底面密集信号走廊。
2. **单面平铺拓扑不可达**：在维持 `6 mil`（`0.15 mm`，符合 [嘉立创 0201/0402 最小装配间距](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)）器件包络间距与 `6.2 mil` 异网铜间距的前提下，C11 两端无法在 L6 同层同时绕过 `AVDD_REQ_FILTER` 与周围阻挡铜皮触达 `U13.1/U13.4`（`VSYS`）和 `U13.2`/GND 盲孔，因此 80 个候选位、485 条短折线和 1 mil 八方向网格搜索的 `VSYS` 连通数与双端回路候选数均为 **0**。
3. **禁止妥协项**：不得通过降低铜间距规则（低于 `6.2 mil`）、侵占 `AVDD_REQ_FILTER` 滤波隔离带、或在未获声学/工艺批准前随意打穿全通孔的方式强行连通。

### 3.2 可实施解决方案对比（推荐方案 A，备选方案 B）

#### 方案 A（推荐主方案）：U13 走廊协同重排 + 电源内层（L3/L4）立体换层与 L5 局部盲孔返流

核心思路是**打破 L6 单平面死锁**：将 `VSYS` 馈电与 `GND` 回流在 Z 轴方向解耦，避免在 L6 表层与 `AVDD_REQ_FILTER` 争夺同一横向通道。

* **器件位置建议**：在机械与装配窗口冻结后，将 C11 保持在 `U13` 底面邻近的 `Y = 104–378 mil` 有效窗口内，旋转并对齐至与板长轴（Y 轴）平行或垂直的最小占位姿态，使其 GND 端面向 `U13.2` 或最近的 L5 连续地平面投影区，`VSYS` 端背离 `AVDD_REQ_FILTER` 敏感节点；与邻近 0201/0402 器件保持 ≥ `0.15 mm`（`6 mil`），与 SOT 封装保持 ≥ `0.20 mm`（`8 mil`），与 QFN/BGA 保持 ≥ `1.0 mm`（`40 mil`）（[嘉立创 SMD 最小间距规范](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)）。
* **走廊重排前置动作**：先将底面穿越该区域的 `FPGA_C...` 非关键表层总线迁至内层 `L3/L4`，并协同微调 `U13` 邻接的 `VSYS` 主馈线与 `AVDD_REQ_FILTER` 走线（保持 `C3` RC 滤波拓扑与 ≥ `11.8 mil` 敏感信号间距不变），在 `U13.1/U13.4` 侧腾出至少 `25–30 mil` 的立体换层窗。
* **网络连接与层选择**：
  * **`VSYS` 端**：从 `U13.1 / U13.4` 经短宽铜皮（线宽 ≥ `4 mil`，优先 `6–8 mil`）或独立 `L6 → L4`（或 `L6 → L3`）电源换层通道引至内层电源支路，再就近扇出至 C11 的 `VSYS` 焊盘，严格遵守 [Lattice `FPGA-TN-02115`](https://0x04.net/~mwk/doc/lattice/ecp/PowerDecouplingandBypassFilteringforProgrammableDevices.PDF) 的 **“过孔 → C11 焊盘 → U13 引脚”** 去耦流向。
  * **`GND` 端**：在 C11 的 GND 焊盘紧邻处放置 1 颗 `L6–L5` 局部盲孔（`BV_L5_L6`），以最短宽颈部（线宽 ≥ `4 mil`）直接锚定至原生连续 `L5` GND 参考平面，不再在 L6 表层长距离绕线寻找 `U13.2`。
* **回流路径与 PI 优势**：高频瞬态电流经 `C11 (L6) → BV_L5_L6 → L5 完整地平面 → U13.2 地盲孔` 闭合，回路面积最小化，且与 `AVDD_REQ_FILTER` 实现物理层隔离。

#### 方案 B（条件备选方案）：6 层板 Via-in-Pad（VIPPO）树脂塞孔电镀填平方案（需 Fab EQ 批准）

若机械结构冻结后 `U13` 邻接区域仍无法腾出独立盲孔扇出空间，可申请嘉立创 6 层板免费/标准 Via-in-Pad（盘中孔）或 1+N+1 HDI 激光微盲孔工艺（[JLCPCB 6-Layer PCB Capabilities](https://jlcpcb.com/6-layer-pcb)；[JLCPCB Blind Vias in HDI PCBs](https://jlcpcb.com/blog/hdi-pcb-blind-vias)，激光微孔直径支持 `0.075–0.15 mm`，支持填铜/树脂塞孔盘中孔）：

* **实施要点**：将 C11 的 `GND` 盲孔（`L6–L5`）直接置于焊盘中心（VIPPO），省去焊盘到过孔的颈部扇出与阻焊桥占位，把腾出的表层间隙全部让给 `VSYS` 走线（≥ `4 mil`）与 `6.2 mil` 异网安全间距。
* **准入门槛（BLOCKED 前提）**：必须先获得板厂 EQ 确认（盘中孔塞孔平整度、0201/0402 焊盘防立碑/锡膏流失评估、以及与当前 `JLC06161H` 叠层兼容性），在获批前不得直接合入生产层叠。

## 4. FPGA 线束换层、去耦回流路径与 L2/L5 地平面连续性研究

### 4.1 6 层窄板叠层规划与 FPGA 线束换层策略

针对 PCB2 既有 6 层结构（`L1 Top` / `L2 GND` / `L3 Inner1` / `L4 Inner2` / `L5 GND` / `L6 Bottom`），原生 `L2` 与 `L5` 已确认为有效连续 GND 平面（[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)）。建议层分配与换层原则如下：

| 层别 | 建议功能定位 | 参考平面与回流要求 | 窄板约束下的关键动作 |
| :--- | :--- | :--- | :--- |
| **L1 (Top)** | 主要器件面、光机/桥接关键短线、表层去耦焊盘 | 紧邻 **L2 GND** | 保持 `C12.2`（`d66a84af7c151bc9`）与 `C33.2`（`3ee8ab886f357cc2`）既有 L2 回路不变；禁止无必要开槽 |
| **L2 (Inner GND)** | 完整高速参考地平面 | — | 禁止高速线束在 L2 走长线割裂参考面；仅保留必要过孔反焊盘，维持连续铜边界（保护既有 6.574–7.168 mil 边距） |
| **L3 (Inner Sig/Pwr)** | **迁入的 `FPGA_C...` 线束（主层）** + 局部电源支路 | 紧邻 **L2 GND**（主回流） | 将原占 L6 底面的 `FPGA_C...` 总线迁入 L3，与 L4 正交或错开走线以抑串扰；高速信号间距优先 ≥ 5× 线宽（受窄板限制时严格 ≥ `6.2 mil`，敏感信号 ≥ `11.8 mil`） |
| **L4 (Inner Sig/Pwr)** | 其余 `FPGA_C...` 线束 + `VSYS` / `1.8 V` 局部电源换层支路 | 紧邻 **L5 GND**（主回流） | 承接 C11 `VSYS` 与 C8 `1.8 V` 的内层立体换层走廊，释放 L6 器件与盲孔空间 |
| **L5 (Inner GND)** | 完整底面参考地平面 | — | 为底面去耦电容（含 C11、C31、C8 等）提供紧耦合 `BV_L5_L6` 地盲孔直接落点 |
| **L6 (Bottom)** | 底面去耦电容（含 C11）、局部电源/地短宽连接 | 紧邻 **L5 GND** | 清退长距离 `FPGA_C...` 总线后，集中服务去耦电容布局与 4 mil 以上局部地线加宽 |

### 4.2 换层回流路径与 L2/L5 地平面缝合（原厂依据）

* **同为地参考平面的换层（L1/L3 ↔ L4/L6）**：依据 Lattice [iCE40 Hardware Checklist (`FPGA-TN-02006`, Figure 7.1)](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf) 与 [High-Speed PCB Design Considerations (`FPGA-TN-02178`, Sec 2.3.2 & 4.2)](https://canada.newark.com/site/binaries/content/assets/common/product-family-documents/lattice-lfmxo5-100t-evn/lattice-lfmxo5-100t-evn-an1.pdf?ICID=I-FP-EMB-DKHQ-LATTICE-LFMXO5-100T-EVN-TR)，当 FPGA 高速信号从参考 `L2 GND` 的层（L1 或 L3）换层到参考 `L5 GND` 的层（L4 或 L6）时，**必须在信号换层过孔紧邻处布置 `L2–L5` 伴随过渡地过孔（Transition Ground Via）**。否则回流电流被迫绕行整个 4.6 mm 窄板寻找远端 L2/L5 跨接点，导致严重共模辐射、地弹与时钟/数据眼图恶化。
* **跨电源参考平面的换层**：若某段线束在 L3/L4 局部区域以电源铜皮而非地平面为参考，按 [`FPGA-TN-02006` Figure 7.1 右侧规范](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf)，须在换层点附近补充 `GND–VCC` 缝合电容（如 100 nF）。
* **PCB2 当前 `L2–L5` 缝合缺口与破局**：R6 归档确认 PCB2 的 47 颗独立过孔中，40 颗为仅连外层与相邻平面的盲孔，其余 7 颗通孔均属非 GND 网络（[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)）。这意味着 **L2 与 L5 之间极度缺乏专用的低感 GND 缝合过孔**。由于 R6 筛查出的全部 6/12 mil 与 8/16 mil 通孔候选均落在 `MK2` 声学包络内（BLOCKED），正确破局方式为：
  1. 在 `FPGA_C...` 线束换层区及 **非声腔桥区**（与声学结构组联合确认释放），通过微调若干非关键局部地支线，优先开辟至少 **2–4 处 `8/16 mil`（或经工艺确认的 `6/12 mil`）GND 通孔空窗**，直接桥接 `L2` 与 `L5`；
  2. 确保新增通孔同时满足外铜间距 ≥ `6.2 mil`、敏感信号间距 ≥ `11.8 mil`、原生孔壁间距 ≥ `11.811 mil`（[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)）。

## 5. 4.6 mm 窄板、MEMS 声学区、光机 FPC 与装配制造约束矩阵

| 约束域 | 关键物理/工艺参数 | 对 PCB2 去耦与布线的硬约束 | 来源依据 |
| :--- | :--- | :--- | :--- |
| **4.6 mm 窄板几何** | 标称板宽 4.6 mm（`181.1 mil`）；铜到板边 ≥ `12 mil`（双边共 `24 mil`）→ 有效布线净宽 ≈ `157.1 mil`（~3.99 mm） | 单颗 `8/16 mil` 过孔加两侧 `6.2 mil` 间距即占 `28.4 mil`（约 18% 净宽）；表层无法同时容纳密集总线与去耦电容，必须依托 6 层板内层立体布线 | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md) |
| **MEMS 声学区（MK2）** | [Infineon IM69D130](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf) 底部进音数字 PDM 麦克风（`VDD = 1.8 V`）；PCB 进音孔径须大于封装声孔径，密封环完整 | **严禁在 `MK2` 声腔与密封环包络内新增未填塞通孔**（防漏气及声学频响劣化）；相关通孔方案在声学结构组冻结声腔、过孔填盖与阻焊注册规则前保持 **BLOCKED** | [PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)；[IM69D130 手册](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf) |
| **光机 FPC 接口区** | 窄板端接光学模组 FPC（弯曲应力、插拔限位、高速显示信号与独立模拟/数字电源隔离） | FPC 连接器及补强板弯折投影区内禁放陶瓷去耦电容（防弯折裂纹）；连接器焊盘周边预留贴装与返修余量；高速线束换层须紧邻伴随地过孔 | 工程约束（具体 FPC 连接器料号与坐标见第 8 节数据缺口） |
| **嘉立创 6 层板制造能力** | 最小线宽/线距 `3.5 mil (0.09 mm)`；常规板厚 0.8/1.0/1.2/2.0 mm；6 层板支持免费 Via-in-Pad；HDI 激光微盲孔 `0.075–0.15 mm` | 本工程 R6 线宽整改保守采用 **≥ `4 mil`**（保留制造良率余量），异网铜间距门槛 **≥ `6.2 mil`**；涉及 HDI 叠孔/激光盲孔须经板厂 EQ 签核 | [JLCPCB 6-Layer PCB](https://jlcpcb.com/6-layer-pcb)；[JLCPCB HDI Blind Vias](https://jlcpcb.com/blog/hdi-pcb-blind-vias) |
| **嘉立创 SMD 最小装配间距** | 按器件最外侧边到边测量：`0201/0402–0201/0402` ≥ **0.15 mm [6 mil]**；`–0603/0805` ≥ **0.18 mm [7 mil]**；`–SOT` ≥ **0.20 mm [8 mil]**；`–SOP` ≥ **0.40 mm [16 mil]**；`–QFP` ≥ **0.50 mm [20 mil]**；`–QFN/BGA` ≥ **1.00 mm [40 mil]** | C11 及八颗去耦电容移动时，必须按相邻器件真实封装查表核对最小装配间距（特别是靠近 QFN/BGA 芯片或 SOT 器件的边界） | [JLCPCB SMD Minimum Spacing](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components) |

## 6. ERC / DRC 验收要求矩阵

每项方案在隔离原生工程中实施后，必须全部满足下表硬性验收门槛，方可视为通过（**任何一项未通过即维持 `BLOCKED`，严禁调低规则掩盖违例**）：

| 验收项 | 适用方案 | 量化验收标准（PASS 门槛） | 校验方式 |
| :--- | :--- | :--- | :--- |
| **原理图 ERC** | 方案 A / B 全部 | 0 新增严重错误（保持全板既定逻辑与网表一致，不得删改安全网络或设置 `转到PCB=否` 规避） | EasyEDA Pro 原生 Schematic ERC |
| **PCB2 网表一致性** | 方案 A / B 全部 | PCB2 Netlist Errors = **0**（与 R6 基线持平，不得引入悬空或错网） | EasyEDA Pro Import Changes + Netlist Check |
| **C11 双端物理连通** | 方案 A / B | C11 的 `VSYS` 端与 `GND` 端均实现实际铜接触，无开路（PCB2 Opens 至少较基线 236 净减少 ≥ 2） | 原生严格 DRC（Opens 检查）+ 实体网络高亮回读 |
| **异网铜间距** | 方案 A / B | 全板铜间距错误 = **0**；常规异网铜间距 ≥ **`6.2 mil`**，敏感模拟/滤波信号（含 `AVDD_REQ_FILTER`）≥ **`11.8 mil`** | 原生严格 DRC（Clearance 检查） |
| **铜到板边距离** | 方案 A / B | 所有新增与修改走线/焊盘/过孔铜到板边 ≥ **`12 mil`** | 原生严格 DRC（Board Outline Clearance） |
| **过孔与孔壁间距** | 方案 A / B | 原生孔壁到孔壁间距 ≥ **`11.811 mil`**；0 个 Hole-to-Hole 失败（杜绝 PR #54 隔离试验中的叠孔冲突）；不新增未填塞孔落入 `MK2` 声腔包络 | 原生严格 DRC（Hole-to-Hole）+ 机械/声学层叠图目检 |
| **SMD 装配间距** | 方案 A / B | 满足 [嘉立创 SMD 最小间距表](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)（0201/0402 间 ≥ `0.15 mm [6 mil]`，至 SOT ≥ `0.20 mm [8 mil]`，至 QFN/BGA ≥ `1.00 mm [40 mil]`） | 封装外框/3D 干涉核查 + JLCDFM 检查 |
| **既有回路与安全逻辑保护** | 方案 A / B | `C2`/`C3` RC 拓扑、`C12.2`（`d66a84af7c151bc9`）与 `C33.2`（`3ee8ab886f357cc2`）L2 回路、FPGA 时钟/复位/安全走线 100% 保持无退化 | R6 前后 Diff 对比 |
| **持久化与交付标签** | 方案 A / B | 隔离工程保存 → 关闭 → 重新打开后，上述全部 DRC/网表指标一致复现；维持 **`NOT FOR FAB`** 标识 | EasyEDA Pro 保存重载复检 |

## 7. KIMI（隔离工程）分步执行清单

**铁律**：严禁直接修改 KIMI 原生生产工程。以下全部操作须在**独立隔离分支/云端克隆副本**中按顺序执行，并在每一步完成后运行原生 DRC 留档。

1. **创建隔离副本与基线快照**
   * 从 R6 基线（SHA-256 `c4ca657e50915789b7255430dd2e0f49c7828d85a2f73c42547701efbb213dd5`）克隆独立试验工程（命名保留 `NOT-FOR-FAB` 标记）。
   * 导出 PCB2 原生坐标清单（含 `C5/C8/C9/C10/C11/C12/C31/C32`、`U13`、`MK2`、FPGA 与光机 FPC 连接器），补齐第 8 节所列数据缺口。
2. **锁定不可触碰保护对象**
   * 在 EDA 编辑器中锁定 `C2`（`AVDD_QUAL_RC`）、`C3`（`AVDD_REQ_FILTER`）、`C12.2`（过孔 `d66a84af7c151bc9`）、`C33.2`（过孔 `3ee8ab886f357cc2`）、`MK2` 声学包络以及 FPGA 时钟/复位/安全信号线。
3. **验证并固化 R6 局部地线加宽（前置已验证项）**
   * 确认 `Y ≥ 750 mil` 的 21 段 GND 走线（含 `C5/C10/C32/C9` 区域 11 段）均为 `4 mil`，运行原生 DRC 确认 0 铜间距/板边违例。
4. **执行 FPGA 底面线束换层（L6 → L3/L4）**
   * 将占据 L6 底面走廊的 `FPGA_C...` 非关键总线迁入内层 `L3`（优先）与 `L4`，避开 `L2`/`L5` 完整地平面；在换层过孔旁预留非声腔区的 `L2–L5` 过渡地过孔位。
   * 对照 [Lattice `FPGA-TN-02006` Figure 7.1](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf) 检查每一组跨 `L2/L5` 换层信号的回流连续性。
5. **实施 C11 方案 A（U13 走廊重排 + 立体换层与 L5 盲孔返流）**
   * 与机械/结构组确认 `Y = 104–378 mil` 装配窗口后，微调 `U13` 邻接的 `VSYS` 与 `AVDD_REQ_FILTER` 走廊（保持 `AVDD_REQ_FILTER` ≥ `11.8 mil` 净空）。
   * 将 C11 的 `VSYS` 端通过内层 `L4/L3` 换层支路按“过孔 → C11 焊盘 → `U13.1/U13.4`”顺序连通（线宽 ≥ `4 mil`）。
   * 在 C11 的 `GND` 焊盘紧邻处放置 `BV_L5_L6` 盲孔直连 `L5` GND 平面。
   * 若受限无法布置独立盲孔，再向板厂提交方案 B（VIPPO / 激光微盲孔）EQ，未批复前保持 `BLOCKED`。
6. **联动处理 C8、C31 及非声腔区 `L2–L5` 地缝合通孔**
   * 利用步骤 4 释放出的 L6/L1 空间，重新核查 `C8`（1.8 V 跨层 7 处间距违例点）与 `C31` 的去耦短宽连接及 `BV_L5_L6` 落点。
   * 与声学结构组联合确认 `MK2` 声腔禁区外的非声腔桥区，重放局部支线形成 2–4 处 `8/16 mil`（或 `6/12 mil`）GND 通孔空窗，将 `L2` 与 `L5` 低感缝合。
7. **原生严格 ERC/DRC 与保存重载验证**
   * 运行原生 Schematic ERC、Import Changes、严格 PCB DRC（检查 Opens、Clearance、Board Edge、Hole-to-Hole）与离线复跑脚本（`c11_dual_route_screen.py`、`ground_stitch_refine.py`）。
   * 保存工程、关闭并重新打开，核验全部 DRC 结果与开路数持久化无回归；将前后对比数据归档至 PR 报告，严禁解除 `NOT FOR FAB`。

## 8. 数据缺口与严禁虚构声明

本次评审通过远程浏览器成功核查了 [PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)、[PCB2_R6.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb2/PCB2_R6.md)、[嘉立创 SMD 最小间距规范](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components) 与 Lattice 官方技术文档；但在访问 GitHub 分支子目录及原始 JSON/Python 文件（`BLOCKED.md`、`plan_pcb2_r6.py`、`plan_bridge_r5.py`、`c11-dual-route-tree.json`、`decap-ground-widths-r6.json`、`geometry-report.json`、`PCB2-blind-vias.csv`）时，远程浏览器返回 `PERMISSION_DENIED`，且本环境未直连 EasyEDA Pro 原生工程。为确保零虚构，以下数据缺口明确标注，待 KIMI 在隔离原生工程中直接回读补齐：

1. **器件精确原生坐标与封装尺寸**：`C5/C8/C9/C10/C11/C12/C31/C32` 与 `U13` 的精确 `(X, Y)` 坐标、旋转角度、所在板面（L1/L6）及封装尺寸（0201/0402 等），本报告未做任何坐标推测。
2. **器件具体料号与引脚表**：PCB2 上 Lattice FPGA 的具体料号/封装（例如具体 iCE40 或 Nexus 型号，本报告所引 Lattice 原厂准则均取自通用电源去耦与高速 PCB 规范 [`FPGA-TN-02006`](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf)、[`FPGA-TN-02115`](https://0x04.net/~mwk/doc/lattice/ecp/PowerDecouplingandBypassFilteringforProgrammableDevices.PDF)、[`FPGA-TN-02178`](https://canada.newark.com/site/binaries/content/assets/common/product-family-documents/lattice-lfmxo5-100t-evn/lattice-lfmxo5-100t-evn-an1.pdf?ICID=I-FP-EMB-DKHQ-LATTICE-LFMXO5-100T-EVN-TR)）、`U13` 具体料号，以及光机 FPC 连接器型号与引脚定义。
3. **局部违例与网络明细**：`C8`、`C31` 的具体供电轨归属及 PR #54 中 `C1–C8` 1.8 V 隔离试验的 7 处严格间距失败坐标；`c11-dual-route-tree.json` 中 80 个候选位的逐点阻断日志。
4. **原生实测结果**：本报告不包含任何虚构的 DRC 通过截图、眼图/PDN 仿真数值或实测纹波结果，所有整改效果须以隔离原生工程真实写入、保存重载与严格 DRC 报告为准。
