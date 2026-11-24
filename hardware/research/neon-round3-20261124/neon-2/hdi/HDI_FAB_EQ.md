# 智元跃动 AI/AR 智能眼镜 V1.0｜PCB3 HDI 制造工艺研究与板厂 EQ 清单（HDI_FAB_EQ）

* **项目与基线**：智元跃动 AI/AR 智能眼镜 V1.0（EVT-1 H03 R6），对应 [AI-AR-codex-Claude- 仓库](https://github.com/yfei7131-source/AI-AR-codex-Claude-) 与 Draft PR [PR #54: EVT-1 H03 R6 three-board native DFM and HDI trial (NOT FOR FAB)](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)（提交 `d164a19`）

* **研究对象**：PCB3 `0.80 mm` 六层二阶 HDI（2+2+2）工艺可行性、R6 K4 试验 4 项孔间距错误、微孔/焊盘/反焊盘/介质/VIPPO 制造约束、多制造路线对比及板厂 EQ 询问清单

* **状态声明**：**`NOT FOR FAB`**。本文档仅基于远程浏览器实时核对的 GitHub 工程资料与板厂公开文档形成工程评估与 EQ 询问包，**未修改任何 PCB 文件，未虚报任何制造商确认结果**。

## 1. 资料核对范围与远程访问记录

以下 6 项指定资料及关联变更文件均已通过远程浏览器实时打开并核对：

| 资料名称 | 核对状态 | 证据链接 | 关键核对说明 | 
| ----- | ----- | ----- | ----- | 
| 项目仓库主页 | 已核对（正常访问） | [AI-AR-codex-Claude-](https://github.com/yfei7131-source/AI-AR-codex-Claude-) | Public 仓库，确认项目目录与分支结构 | 
| 最新工程 PR #54 | 已核对（正常访问） | [PR #54](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54) / [PR #54 Files changed](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54/files) | Draft 状态，`hardware/evt1-h03-r6-codex-20261123` → `r5`，155 个变更文件；通过 diff 视图读取 `BLOCKED.md`、`hdi/k4-test-stack.json` 与 `verification/trials/hdi-k4-native-outcome.json` | 
| R6 HDI 研究文档 | 已核对（正常访问） | [R6 HDI README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md) | 获取 PCB3 0.80 mm 叠层预算、75/100 μm 激光孔、捕获盘、埋孔与 0.35 mm BGA 冲突数据 | 
| JLCPCB HDI 制造主页 | 已核对（正常访问） | [JLCPCB HDI PCB Manufacturing](https://jlcpcb.com/pcb-fabrication/hdi-pcb) | 获取 1–3 阶 HDI、PP 选项、0.5–3.0 mm 板厚、75–150 μm 激光孔、捕获盘/目标盘 +6 mil、孔间距、填铜凹陷 ≤25.4 μm、MOQ 3 pcs 等参数 | 
| JLCPCB HDI FAQ | 已核对（正常访问） | [JLCPCB HDI Capabilities & FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) | 获取 6L 2+2+2 结构图与 `08`（0.8 mm）代码、50 μm `S1000-2MB-106 RC72%` PP、0.5–2.4 mm 板厚范围、Skip Via 拆解为叠孔规则 | 
| GS Swiss PCB 能力页 | 已核对（正常访问） | [GS Swiss PCB Manufacturing Capabilities](https://www.gs-swiss.com/en/technologies-and-products/pcb-manufacturing-capabilities) | 获取刚性板标准 16 层/极限 40 层、30 μm 芯板、Ø50 μm 标准/Ø15 μm 极限激光孔、40/40 μm 标准线宽距、铜填孔与表面处理能力 | 

**远程访问异常明确说明**：

* 尝试直接打开 `verification/trials/hdi-k4-drc.json`、`hdi/k4-test-stack.json` 与 `BLOCKED.md` 的独立 GitHub blob 页面时，GitHub 返回 SPA 前端加载错误或 HTTP 500 错误；按要求**未反复尝试 GitHub 登录**。其中 `BLOCKED.md`、`hdi/k4-test-stack.json` 与 `verification/trials/hdi-k4-native-outcome.json` 已通过 [PR #54 Files changed](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54/files) 成功核对；**`verification/trials/hdi-k4-drc.json` 的完整原始全量列表未能直接打开**，4 项新增孔间距错误的逐条坐标、对象 ID 与报错文本均来自已核对的 `verification/trials/hdi-k4-native-outcome.json`。

## 2. PCB3 0.80 mm 六层二阶 HDI 制造可行性评估

### 2.1 候选叠层预算与公差核算

根据 [R6 HDI README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md)，PCB3 预算候选为 `2+2+2` 六层二阶 HDI（当前集成原生归档尚未实际采用该叠层）：

| 叠层要素 | R6 候选预算值 | 数量 / 说明 | 小计厚度 | 对照 JLCPCB 规则核查 | 
| ----- | ----- | ----- | ----- | ----- | 
| 双面阻焊（Solder Mask） | 20 μm / 面 | Top + Bottom | 40 μm | 需板厂按实际阻焊与字符工艺确认 | 
| 外层铜厚（L1 / L6） | 35 μm / 层 | 2 层（约 1 oz 成品） | 70 μm | 常规外层 1 oz 成品铜厚 | 
| 内层铜厚（L2 / L3 / L4 / L5） | 18 μm / 层 | 4 层（0.5 oz） | 72 μm | 常规内层 0.5 oz 铜厚 | 
| 二阶压合介质（L1-L2, L2-L3, L4-L5, L5-L6） | 50 μm / 层 | 4 层 PP | 200 μm | 刚好触及 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 压合 PP 下限 `≥ 50 μm`（对应 [FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 中 `Shengyi S1000-2MB-106 RC72%` 0.050 mm） | 
| 芯板（L3-L4 机械埋孔跨度） | 418 μm | 1 层 Core | 418 μm | 满足 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 埋孔芯板下限 `≥ 300 μm`（余量 +118 μm） | 
| **名义成品总厚** | **0.800 mm** | `40+70+72+200+418` | **800 μm** | [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 成品厚 `< 1.0 mm` 公差为 **±0.10 mm**（实测范围 **0.70–0.90 mm**） | 

### 2.2 关键可行性结论与厚度边界冲突

1. **结构层面可行，但处于单张 106 PP 工艺下限**：[JLCPCB HDI FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 明确支持 6 层 2 阶（`L1-PP-L2-PP-L3-Core-L4-PP-L5-PP-L6`）及 `0.80 mm`（叠层代码 `08`）成品厚，且 `418 μm` 芯板满足 `≥ 0.30 mm` 埋孔芯板要求。但 `50 μm` 单张 `106 RC72%` 压合介质在覆盖 `18 μm` 内层铜箔后存在填胶余量紧张、CAF 风险升高及阻抗敏感度放大问题。

2. **PP 加厚与芯板下限的硬耦合约束**：在维持 `0.800 mm` 名义总厚与 `142 μm` 铜厚、`40 μm` 阻焊不变的前提下，要保证 L3–L4 芯板 `≥ 300 μm`，单层 PP 厚度上限为 `(800 - 142 - 40 - 300) / 4 = 79.5 μm`：

   * 若板厂采用 [JLCPCB FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 列出的 **55 μm** 或 **60 μm** PP，则芯板可调至 **398 μm** 或 **378 μm**，仍满足 `≥ 300 μm`；

   * 若板厂因填胶或阻抗要求改用 [JLCPCB 主页](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 示例中的 `1078/1080 RC69`（**86 μm**）或 `106 × 2 RC72`（**100 μm**），4 层 PP 合计 `344–400 μm`，剩余芯板厚度将跌至 **218–274 μm（< 300 μm，违反埋孔芯板下限）**，届时成品名义厚度必须上调至约 **0.83–0.90 mm**（或改为一阶 HDI）。

3. **0.35 mm 球距 BGA 几何瓶颈（JLCPCB 路线的最大阻断）**：[R6 HDI README.md](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md) 指出，在 `0.35 mm` 球距下，按 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 最小捕获盘规则（孔径 + 6 mil），即使是 Ø75 μm 激光孔其最小盘径也达 `0.2274 mm`，两盘并排间距仅 `0.1226 mm`（对相邻 Ø0.195 mm 焊盘仅 `0.1388 mm`），均低于项目锁定的 `0.1524 mm`（6 mil）间距要求；且 [JLCPCB FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 仅说明一般支持 **0.4 mm 球距 BGA**，未承诺 0.35 mm 球距。因此 JLCPCB 路线**无法对 0.35 mm BGA 受阻球全面采用居中盘中孔（VIPPO）**，必须采用外引短线（dogbone/landing）或转向支持 Ø50 μm 激光孔与更小环宽的高精密 HDI 板厂（如 [GS Swiss PCB](https://www.gs-swiss.com/en/technologies-and-products/pcb-manufacturing-capabilities)）。

4. **文档口径差异提示**：[JLCPCB HDI 主页](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 标注成品板厚范围为 `0.5–3.0 mm`，而 [JLCPCB HDI FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 标注为 `0.5–2.4 mm`；虽然 `0.80 mm` 在两者交集内，但仍需以板厂 EQ 签核叠层表为准。

## 3. R6 K4 试验 4 项孔间距错误根因分析与合规方案

### 3.1 4 项孔间距错误逐条核对

依据 [PR #54 Files changed](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54/files) 中的 `verification/trials/hdi-k4-native-outcome.json`，隔离试验对网络 `I2S_LRCLK_1V8`（源端 `U11.K4 P0.22` 至接收端 `J1.P12`、`U10.C3`）写入 7 个过孔并实现物理导通（未连通错误由 132 降至 130），但新增 4 项 `Clearance Error / Hole to Hole`（规则 `otherClearance`，层 `Multi-Layer`，阈值 `>= 11.8 mil`），已被排除出集成交付（`excluded_from_delivery: true`）：

| 错误编号 | 坐标 (mil) | 冲突对象（同网络 `I2S_LRCLK_1V8`） | 实测间距 vs 规则阈值 | 物理结构判别 | 对照 JLCPCB 真实制造规则 | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| `err0` | `179.47, 328` | `e54` ↔ `e53` (`7fa29d9f0f3614ee`, `7f50c60184eec044`) | `0 mil` vs `>= 11.8 mil` | 同心叠孔（L1–L2 与 L2–L3 垂直投影重合） | [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 工艺上支持同网络叠孔，但推荐优先错孔 | 
| `err1` | `178.62, 323.5` | `e54` ↔ `e55` (`7fa29d9f0f3614ee`, `49b4adac003c25fb`) | `5.3 mil` vs `>= 11.8 mil` | Ø100 μm 激光盲孔 ↔ Ø6 mil L3–L4 机械埋孔（孔壁距 5.3 mil / 0.135 mm） | [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 同网络盲孔到埋孔下限 `≥ 5 mil (0.13 mm)`，实测仅高出 +0.3 mil（余量极紧） | 
| `err2` | `102.97, 301` | `e57` ↔ `e56` (`f56f95e25feded23`, `81e5bfe5b5bccb1d`) | `0 mil` vs `>= 11.8 mil` | 同心叠孔（孔壁投影间距 0 mil） | 同 `err0`（属于 EDA 跨层投影规则与叠孔工艺的口径冲突） | 
| `err3` | `137.97, 376` | `e58` ↔ `e59` (`7e6a6f49aba20daa`, `39c14a439eb27f4b`) | `0 mil` vs `>= 11.8 mil` | 同心叠孔（孔壁投影间距 0 mil） | 同 `err0`（属于 EDA 跨层投影规则与叠孔工艺的口径冲突） | 

### 3.2 合规的叠孔、错孔、埋孔与层跨解决方案

针对上述 4 项错误（本质为 **EasyEDA Pro 全局 Multi-Layer 11.8 mil 孔距规则** 与 **二阶 HDI 同网络叠孔/紧邻埋孔结构** 的双重冲突），可执行以下三种合规方案：

1. **方案 A：全错孔方案（Staggered Microvia，首选推荐）**

   * **做法**：取消 `e53/e54`、`e56/e57`、`e58/e59` 三处同心叠孔，将 L1–L2 与 L2–L3（及 L6–L5 与 L5–L4）激光孔横向错开，在 L2/L5 中间层用短铜线互连；同时拉大 `e54` 与 L3–L4 机械埋孔 `e55` 的中心距。

   * **两级几何标准**：

     * **满足板厂最小制造标准（JLCPCB 同网络孔壁 ≥ 5 mil / 0.13 mm）**：两颗 Ø100 μm 激光孔中心距 `≥ 0.23 mm (9.06 mil)`；Ø100 μm 激光孔与 Ø152.4 μm（6 mil）机械埋孔中心距 `≥ 0.256 mm (10.09 mil)`（建议工程留余量至孔壁 ≥ 6–8 mil，避免 `err1` 仅 +0.3 mil 的边缘风险）。

     * **零豁免通过 EasyEDA Pro 原生 11.8 mil DRC**：按 `hdi-k4-native-outcome.json` 核算结果，两颗 Ø100 μm 激光孔中心距 `≥ 15.75 mil (0.400 mm)`，激光孔与 6 mil 机械埋孔中心距 `≥ 16.78 mil (0.426 mm)`。

   * **优势**：直接清零全部 4 项原生 DRC 错误，且符合 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 对错孔良率更高、无叠孔界面热机械开裂风险的明确建议。

2. **方案 B：局部叠孔 + 埋孔错位 + 同网络层对规则分层（空间极度受限备选）**

   * **做法**：仅在 BGA/连接器出线区确实无法容纳 15.75 mil 错孔的位置保留两级激光叠孔（L1–L2 叠 L2–L3），但**严禁三阶通叠（禁止激光孔直接叠在 L3–L4 机械埋孔正上方）**，机械埋孔与邻近激光孔保持至少 `≥ 6–8 mil` 孔壁距（高于 JLCPCB 5 mil 下限）。

   * **前提条件**：① 在 EDA 中仅针对“同网络、相邻激光层对”做规则作用域细化（**严禁放宽不同网络孔间距规则**）；② 必须获得板厂 EQ 书面确认叠孔填铜凹陷、回流焊热冲击可靠性及四线低阻（Kelvin）测试覆蓋。

3. **方案 C：层跨重分配（减少不必要的二阶跨层与埋孔）**

   * **关于跳孔（Skip Via）的警示**：[JLCPCB HDI 主页](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 与 [FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 均明确说明，L1–L3 / L6–L4 跳孔**必须提供单独钻孔文件，且生产时会被拆解为叠孔（stacked blind/buried vias）制造**，因此跳孔**不能**规避叠孔的工艺成本与可靠性风险。

   * **层跨优化建议**：`I2S_LRCLK_1V8` 为音频时钟信号（低速），在满足局部参考地回流重建的前提下，可评估将其在 U11 扇出后优先布在 L2/L3，并仅在 BGA 禁布区外使用常规通孔或单次 L2–L5 埋孔换层，从而减少对 6L 二阶叠孔/埋孔的依赖。

## 4. 激光孔、捕获盘、反焊盘、压合介质与 VIPPO 制造约束核验

| 工艺项 | R6 工程参数（[R6 HDI README](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/hdi/README.md) / `k4-test-stack.json`） | JLCPCB 公开约束（[主页](https://jlcpcb.com/pcb-fabrication/hdi-pcb) / [FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)） | GS Swiss PCB 公开约束（[能力页](https://www.gs-swiss.com/en/technologies-and-products/pcb-manufacturing-capabilities)） | 核验结论与风险点 | 
| ----- | ----- | ----- | ----- | ----- | 
| **激光微孔直径与纵横比** | 75 μm（AR=0.667 @ 50 μm）与 100 μm（AR=0.50 @ 50 μm） | 75–150 μm（默认 100 μm）；纵横比 `≤ 1:1`（且要求孔径 > 介质厚） | 标准 Ø50 μm，极限 Ø15 μm；纵横比未公开 | **通过**：在 50 μm 介质下 75/100 μm 均满足 JLCPCB `≤ 1:1`；但若介质增厚至 `86 μm`，**75 μm 孔将直接失效**，只能用 `≥ 100 μm` | 
| **捕获盘 / 目标盘（Capture / Target Pad）** | 75 μm → Ø0.2274 mm (8.95 mil)；100 μm → Ø0.2524 mm (9.94 mil) | 捕获盘与目标盘均要求 `孔径 + 6 mil (+0.15 mm)`，单边环宽 `≥ 3 mil (75 μm)` | 激光孔环宽标准 `Ø50 μm`、极限 `Ø20 μm`（未单独区分捕获/目标盘） | **JLCPCB 受阻 / GS Swiss 可行**：JLCPCB 盘径在 0.35 mm BGA 下破坏 6 mil 间距；GS Swiss 50 μm 孔+小环宽可满足 0.35 mm 球距 | 
| **反焊盘（Antipad）** | `k4-test-stack.json`：L2 半径 10.53 mil（Ø21.05 mil，75 μm 方案）/ 11.02 mil（Ø22.04 mil，100 μm 方案）；`BLOCKED.md` 列 L2/L5 10 mil 反焊盘待联合验证 | 公开页面**未规定**具体反焊盘最小值（需结合内层过孔到铜/走线 `≥ 6 mil` 推算：Ø0.10 mm 孔最小反焊盘约 Ø0.40 mm / 16 mil；Ø0.15 mm 埋孔约 Ø0.45 mm / 18 mil） | 公开页面**未规定** | **待 EQ 确认**：R6 的 21–22 mil 反焊盘在电气隔离上裕量充足，但在 0.35 mm（13.78 mil）球距下**相邻反焊盘必然连片开窗，会严重切割 L2/L5 GND 参考平面**，需与局部回流重建联合确认 | 
| **压合介质与芯板** | 4 × 50 μm PP + 418 μm L3–L4 芯板 | 盲孔介质 `50–127 μm`（最小 `S1000-2MB-106 RC72%` 50 μm）；埋孔芯板 `≥ 300 μm`；基材限生益 S1000-2M / 南亚 NP-175F（Tg 170°C） | 刚性芯板标准 `30 μm`；支持 FR-4 / BT / PI / ABF；压合 PP 下限未公开 | **高风险待确认**：单张 50 μm PP 为 JLCPCB 绝对下限，若被迫换用 86 μm 1080 PP，0.80 mm 厚度与 300 μm 芯板下限将发生冲突 | 
| **机械埋孔（L3–L4）** | Ø0.1524 mm (6 mil) 孔 / 12 mil 盘，AR ≈ 2.74 | 0.15–0.55 mm（介质 ≤1.0 mm 极限 0.10 mm）；盘 = 孔 + 6 mil；AR `≤ 16:1`；树脂塞孔 + 电镀盖帽 | 机械微孔标准 Ø100 μm / 极限 Ø75 μm；环宽标准 Ø100 μm / 极限 Ø75 μm | **通过**：6/12 mil 埋孔符合 JLCPCB 常规能力，但需在 EQ 中确认塞孔电镀盖帽平整度与 L2–L3/L3–L4 对准公差 | 
| **VIPPO（盘中孔电镀填平）** | R6 文档未列出独立 VIPPO 参数表；K4 采用外引 19.5 mil 走线至独立 landing 下孔 | 激光盲孔默认**电镀填铜整平**，最大凹陷（fill recess）`≤ 25.4 μm`；机械埋孔树脂塞孔盖帽；FAQ 强调盘中孔需在备注中明确焊盘几何与表面平整要求 | 盲孔**铜填充**，通孔铜/环氧树脂填充；未公开凹陷上限与 VIPPO 专项规范 | **需谨慎使用**：JLCPCB 25.4 μm 最大凹陷对 0.35 mm 细间距 BGA（锡球直径仅 \~0.20–0.22 mm）偏大，存在焊球空洞/虚焊风险；若用 VIPPO 必须向板厂 EQ 锁定更严的凹陷指标（建议 ≤ 10–15 μm）或避开居中盘中孔 | 

## 5. 可行制造路线对比（3 套方案）

| 对比维度 | 路线 1：JLCPCB 6L 二阶 HDI（2+2+2，错孔为主） | 路线 2：GS Swiss PCB（或同级 mSAP/高精密 HDI 厂）6L 二阶 HDI | 路线 3（降本减险备选）：JLCPCB 6L 一阶 HDI（1+4+1，L2–L5 埋孔） | 
| ----- | ----- | ----- | ----- | 
| **结构与微孔配置** | 2+2+2；Ø100 μm（默认）/ Ø75 μm（局部）错孔 + L3–L4 6/12 mil 埋孔；0.35 mm BGA 采用外引短线（dogbone） | 2+2+2 或 Any-layer；Ø50 μm 激光微孔 + 50 μm 环宽（盘 Ø150 μm）+ 40/40 μm 线宽距；支持 0.35 mm BGA 盘中孔 | 1+4+1；仅 L1–L2 与 L5–L6 一阶激光盲孔 + L2–L5 机械埋孔，无二阶叠孔 | 
| **0.80 mm 厚度可行性** | **有条件可行**（需板厂签核 50–60 μm PP + 378–418 μm 芯板，成品公差 0.70–0.90 mm） | **高可行性**（支持 30 μm 级薄芯板与细介质，0.80 mm 厚度裕量大，需 EQ 确认具体叠层） | **高可行性**（仅 2 层 PP，可用更可靠的 86 μm 1080 PP + \~450 μm 芯板轻松压到 0.80 mm） | 
| **成本与打样门槛** | **中（二阶中最低）**：MOQ 3 pcs，支持在线提交 Gerber 先工程审核再付款（[JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb)） | **高**：高精密/欧洲工艺与 NRE 成本高、交期长，需商务与工程立项评估（[GS Swiss](https://www.gs-swiss.com/en/technologies-and-products/pcb-manufacturing-capabilities)） | **中低**：比二阶减少 1 次压合与 1 次激光钻孔，单价与交期显著优于路线 1 | 
| **可靠性与良率** | **中**：IPC Class 2；采用全错孔可规避叠孔开裂，但 50 μm 单张 PP 与 25.4 μm 填铜凹陷需严格控制；返修困难 | **高**：成熟细间距 mSAP/微孔铜填工艺，支持 ENIG/ENEPIG，适合超紧凑穿戴主控/显示板（具体 IPC 等级需 EQ 确认） | **中高**：消除二阶叠孔热机械界面风险，允许更厚 PP 提升介质耐压与抗 CAF 能力 | 
| **核心供应商限制** | 不承诺 0.35 mm BGA；盘径 = 孔 + 6 mil 限制居中 VIPPO；线宽距下限 3/3 mil（极限 2.7/2.7 mil 增本）；仅生益/南亚 FR-4 | 公开能力页缺失叠层表、板厚公差、孔间距、反焊盘、VIPPO 凹陷及 IPC 等级，前期沟通与打样周期长 | 内层扇出通道少于二阶，需验证 PCB3 上 U11（0.35 mm BGA）全部受阻信号能否在一阶结构下完成扇出 | 
| **适用阶段建议** | **EVT-1 快速验证首选（前提：确认 U11 无需全面 VIPPO 且 50–60 μm PP 获批）** | **若 PCB3 0.35 mm BGA 扇出与 0.80 mm 厚度在 JLCPCB 被 EQ 驳回，作为升级主路线** | **若复核发现 PCB3 仅少量低速网受阻且可 dogbone 扇出，优先降阶以换取良率与交期** | 

## 6. 可直接提交板厂的 EQ 技术询问清单

以下清单可直接附带 Gerber/Drill 与候选叠层图，分别提交给 JLCPCB（审单工程师）及备选高精密 HDI 厂（如 GS Swiss PCB）进行正式 EQ 签核：

| EQ 编号 | 询问类别 | 具体技术问题（可直接复制发送） | 期望板厂书面答复内容 | 对应风险/依据 | 
| ----- | ----- | ----- | ----- | ----- | 
| **EQ-01** | 0.80 mm 六层二阶叠层与 PP 选型 | 请确认 6 层 2 阶 HDI（2+2+2：L1-L2、L2-L3、L3-L4 埋孔、L4-L5、L5-L6）成品板厚 **0.80 mm（±0.10 mm）** 是否支持采用 **4 × 50 μm（如 S1000-2MB-106 RC72%）或 55/60 μm PP + 378–418 μm 芯板**？外层 1 oz / 内层 0.5 oz 铜厚下，单张 106 PP 填胶与耐压是否满足量产可靠要求？如必须改为 1080/2×106 PP，请给出满足芯板 ≥ 0.30 mm 的最小成品厚度。 | 签核版叠层表（含材料型号、RC%、压合后介质厚、成品厚及公差、阻抗线宽） | 避免 86 μm PP 导致芯板 < 300 μm 冲突 | 
| **EQ-02** | 75 μm vs 100 μm 激光孔与盘径下限 | 在上述签核介质厚度下，请确认最小可行激光盲孔直径（75 μm 或 100 μm，纵横比 ≤ 1:1），以及**捕获盘与目标盘最小直径/单边环宽**是否可低于 `孔径 + 6 mil`（例如允许 2–2.5 mil 环宽）？ | 明确 75/100 μm 激光孔对应最小捕获盘、目标盘直径与加工公差 | 决定 0.35 mm BGA 是否必须外引或转高精密厂 | 
| **EQ-03** | 错孔、叠孔与埋孔间距约束 | 针对同网络二阶互联：① 优先采用错孔（Staggered）时，请确认 L1–L2 与 L2–L3 激光孔、以及 L2–L3 激光孔与 L3–L4 6/12 mil 机械埋孔的**最小孔壁到孔壁间距**与推荐工程余量；② 若局部空间受限必须使用 L1–L2 + L2–L3 叠孔，请确认叠孔良率、热冲击可靠性（是否支持多次无铅回流）及是否允许激光孔邻近/跨接在埋孔焊盘边缘。 | 书面确认错孔/叠孔/埋孔最小间距表、叠孔可靠性保证及是否需单独钻孔文件 | 直接解决 R6 K4 4 项孔间距错误（含 `err1` 5.3 mil 边缘问题） | 
| **EQ-04** | VIPPO 盘中孔平整度与凹陷控制 | 若在 0.35 mm 球距 BGA 焊盘（Ø0.195 mm）上采用铜填平盲孔（VIPPO），请确认**盲孔填铜表面凹陷（dimple/recess）能否管控在 ≤ 10–15 μm**（而非默认 25.4 μm），以及表面处理（推荐 ENIG）后的平整度与防空洞能力；同时确认 L3–L4 机械埋孔树脂塞孔电镀盖帽的平整度要求。 | 明确 VIPPO 最大凹陷实测上限、焊盘最小尺寸、是否额外收费及表面处理建议 | 防止 25.4 μm 凹陷引发 0.35 mm BGA 虚焊/空洞 | 
| **EQ-05** | 反焊盘（Antipad）与内层铜距 | 请确认 L2/L5 电源地层针对 Ø75/100 μm 激光孔与 Ø0.15 mm 机械埋孔的**最小反焊盘直径**（或孔壁到内层铜皮最小安全间距）。针对 0.35 mm 球距区域，若采用 10 mil 半径（Ø20 mil）反焊盘会导致相邻开窗连通，请确认可安全缩小的最小反焊盘尺寸以保留 GND 回流桥。 | 给出激光盲孔与机械埋孔的内层最小孔壁到铜皮间距及最小反焊盘直径 | 配合 `BLOCKED.md` 中 L2/L5 反焊盘与局部 GND 回流重建验证 | 
| **EQ-06** | 0.35 mm BGA 阻焊桥与细线距 | PCB3 含 0.35 mm 球距 BGA（焊盘 Ø0.195 mm，盘间距 \~0.155 mm），请确认：① 绿油/黑油阻焊桥（solder mask dam）能否成型，还是必须采用开窗（NSMD/gang opening）；② 局部 2.7/2.7 mil（或 GS Swiss 40/40 μm）线宽距的附加费用与良率影响。 | 明确最小阻焊桥宽度、最小线宽/线距及对应加价项 | 防止 BGA 贴片连锡并锁定布线规则 | 
| **EQ-07** | 阻抗控制、测试与交付条款 | 请确认：① 在签核叠层下，单端 50 Ω 与差分 90/100 Ω（MIPI/USB/I2S 等）的推荐线宽/线距及实测公差；② 是否包含**四线低阻（Kelvin）测试**与切片（cross-section）微孔报告；③ 3–10 片 EVT 打样交期、工程费与单价；④ 是否支持按 IPC-6012 Class 2 或 Class 3 验收。 | 阻抗计算表、检测报告清单、打样报价与交期 | 锁定 EVT-1 采购与来料检验标准 | 

## 7. 未解决阻断（BLOCKED Items）

在以下阻断项全部闭合前，PCB3 必须继续保持 **`NOT FOR FAB`** 状态，**不得擅自放宽全局 DRC 规则或推进制板**：

1. **`BLOCKED-01`｜板厂 0.80 mm 6L 二阶叠层与单张 50 μm PP 签核未完成**：尚无任何板厂（JLCPCB 或 GS Swiss PCB）对 `4 × 50 μm PP + 418 μm Core = 0.800 mm` 叠层、填胶可靠性及阻抗线宽出具书面 EQ 确认。

2. **`BLOCKED-02`｜0.35 mm BGA 捕获盘间距冲突未闭合**：在 JLCPCB 规则（孔 + 6 mil）下，75/100 μm 激光孔捕获盘无法同时满足 0.35 mm 球距与项目锁定的 0.1524 mm（6 mil）铜距；必须等待 EQ-02 / EQ-04 回复，或在“全外引 dogbone + 局部错孔”与“切换高精密 HDI 厂（如 GS Swiss PCB）”之间做出架构裁决。

3. **`BLOCKED-03`｜R6 K4 试验 4 项孔间距错误及关联工程项未闭合**：隔离试验已排除出集成交付，需在选定错孔间距标准（15.75/16.78 mil 或板厂确认值）后，与 `BLOCKED.md` 中登记的 **L2/L5 10 mil 反焊盘验证、局部 GND 回流重建、R4.1 下拉闭合** 联合复核。

4. **`BLOCKED-04`｜未公开的板厂细项参数缺失**：

   * [JLCPCB 公开页面](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 与 [FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 未明确给出反焊盘下限、0.35 mm BGA 承诺、表面处理对 VIPPO 凹陷的影响以及 2.4 mm vs 3.0 mm 板厚上限差异；

   * [GS Swiss PCB 能力页](https://www.gs-swiss.com/en/technologies-and-products/pcb-manufacturing-capabilities) 未公开 6L 2+2+2 叠层、0.80 mm 板厚公差、压合介质下限、微孔纵横比、孔间距、反焊盘、叠孔/错孔规则、VIPPO 凹陷及 IPC 等级；

   * `verification/trials/hdi-k4-drc.json` 独立页面在 GitHub 返回加载错误/500，后续如需全量原始 DRC JSON 审计，建议在本地克隆分支或通过 raw/API 拉取核对。