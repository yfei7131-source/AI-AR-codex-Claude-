# P2-01 / P2-02 三板全局可布线性评估与可执行 ECO 方案

**2026-11-25 · NOT FOR FAB · 40 g / 真实双目透明 AR / 高密度 HDI / 不降规**

- **继承基线**：PR #66 commit `45bc2d4e7e6ca9383ecc0184365fc66dbb89be9e`，原生工程基线 PR #64 `79ce0553f6aaa90ebfee773dceefaf5505d11f30`（R11-MASTER EPRO2 SHA-256 `758618cb4bbb12a5ed34200cbf7c51f2e476c80ed9eee96643efed4764791074`），工作流严格执行 PR #65 V2.0 规范。
- **工具链实测**：`easyeda-agent` Skill/CLI/Daemon/已固定 Connector 均为 `1.20.0`（窗口 `5095e7f7-071b-4d2e-ab41-c5aa3ae3fd02`），宿主嘉立创 EDA 专业版 `4.1.97`。旧 `1.17.0`/`1.18.0` 注册仍存在全局诊断告警，本轮所有读写均固定至 `v1.20.0` 窗口。
- **数据复核**：PR #66 `p2/manifest.json` 全部 6 份文件（`PCB1/2/3.json` 与 `.net`）SHA-256 100% 一致；复用同源 `PCB1/2/3-copper.json` 原始快照与既有工具，未重复开发提取器。

---

## 1. 三板全局量化概览与网络分类

| 指标 | PCB1（左主板） | PCB2（光学桥板） | PCB3（右音频/BLE板） | 三板合计 |
| --- | ---: | ---: | ---: | ---: |
| 有效尺寸（mm / mil） | 8.30 × 46.10 / 326.8 × 1815.0 | 4.70 × 25.10 / 185.1 × 988.3 | 5.30 × 34.10 / 208.7 × 1342.6 | — |
| 器件分布（TOP / BOT） | 118（56 / 62） | 86（58 / 28） | 53（23 / 30） | 257（137 / 120） |
| 飞线总长 / 交叉数（`layout-lint`） | 53,960 mil / 1,917 | 14,197 mil / 371 | 13,149 mil / 426 | 81,306 mil / 2,714 |
| 命名网络 / 未闭合网络 | 112 / 92 | 58 / 54 | 37 / 36 | 207 / 182 |
| 原生基线连接错误（R11） | 322 | 227 | 127 | **676** |
| 其中：GND / 高电流电源 / 电源支路 | 25 / 29 / 88（44.1%） | 28 / 25 / 56（48.0%） | 14 / 13 / 36（49.6%） | 314（46.4%） |
| 其中：差分/对线 / RF时钟高速 / 总线 / 控制 | 4 / 30 / 53 / 93 | 0 / 9 / 32 / 77 | 4 / 32 / 10 / 18 | 362（53.6%） |
| 跨层专属开放网（无同层跨岛对） | 25 | 18 | 11 | **54** |
| 外层跨岛扫描（`pcb route solve`）通过率 | 1 / 80（8 mil VSYS，20 mil 拒绝） | 0 / 63 | 0 / 41 | **1 / 184（0.54%）** |
| 浮空 GND 零拆线直连真实地平面通过数 | **1 / 15**（`R41.2→R38.2`） | 0 / 9 | 0 / 6 | **1 / 30** |
| 合法 DFM-V4 4/10 mil GND 盲孔候选取点数 | **11 / 19** | **4 / 15** | **3 / 7** | **18 / 41** |

> 完整逐网分类见 [3board-net-classification.json](net-classes/3board-net-classification.json) 与 [P2-01-3BOARD-ROUTABILITY-AND-ECO.json](P2-01-3BOARD-ROUTABILITY-AND-ECO.json)。

---

## 2. 内置求解器实测能力与边界矩阵

| 内置命令 | 实测状态 | 真实观测结论与工具边界 |
| --- | --- | --- |
| `pcb net-classes` / `pcb net-class list` | `live-verified` | 三板默认信号线宽均为 `1.97 mil (0.05 mm)`（R11 继承 EPRU 默认值）；R11 原生基线存在 **0 个量产网络类**，207 条网全部绑定 `default`。 |
| `pcb routability` | `BLOCKED-TOOL` (`incomplete`) | 三板均 fail-closed（`checked: 0`）：共 **44 个 POLYGON 焊盘**（PCB1 24：MK1 声孔环 4 + U11/U13 等削角电源焊盘；PCB2 16：MK2 4 + U1/U4 等；PCB3 4：MK3 4）不被精确焊盘接触引擎支持；且仅证明双层板过孔换层，不建模 L2/L5 负片地平面。 |
| `pcb route-critical --dry-run` | `live-verified` | 正确识别三板 `6-layer (power-planes)`；PCB1 `USB_D` 标 `already-routed`（注意 U12 针序冲突未解），`SPK_L`/`SPK_R` 标 `unroutable`，PCB2 `diffPairs` 为空。 |
| `pcb layout-lint` | `live-verified` (`incomplete`) | 三板同面短/叠/越界/紧距均为 `0 / 0 / 0 / 0`；因同上 POLYGON 焊盘标 `incomplete`。 |
| `pcb check` | `live-verified`（含误报口径） | 每板 41 项 `clearance ERROR` 源自 `pcb.via.list` 缺少盲孔跨层信息（将单阶盲孔误当 6 层通孔与 L3 走线碰撞；原生 DRC 间距错误为 0）。真实有效告警：去耦过远（PCB1 3 / PCB2 9）、天线禁布不完整（ANT1 / ANT2）、PCB1 GND 悬空断头 `(125,975)`、电源线宽偏细。 |
| `pcb escape-plan` | `offline-verified`（受布局阻断） | 校验 Schema v3 通过；对 PCB1 U19、PCB2 U3、PCB3 U3/U10 求解时，因现布局紧贴包络无外层直出逃线通道而失败。 |
| `pcb layout-plan` | `offline-verified`（密度全拒） | 跨三板执行 24 组方向搜索（U10/C40、U11/C10、U3/R6、U19/R17、U14/C11、U3/R10），**0 个合法单件移位候选**：固定邻件本体间距已小于 6 mil，且 PCB2 4.70 mm 宽度在左右方向直接触发越界。证明必须采用**多器件成组协同重排**而非单件微调。 |
| `pcb layout solve/check` | `BLOCKED-TOOL` | v1.20.0 联合布局求解器仅支持双层 TOP/BOTTOM，不支持 6 层 HDI 内层角色与跨层求解。 |
| `pcb route solve/check` | `offline-verified` | 单层 TOP/BOTTOM 精确几何引擎运行正常。跨三板 184 组真实跨岛对扫描（`step=2`, `detour=200`）仅 1 组通过（8 mil VSYS，按 20 mil 规则门槛拒绝）；真实地平面跨岛扫描检出 1 条零拆线可执行路径（`PCB1 GND L2 R41.2→R38.2`），直接以数学证据证明**现布局外层纯布线已饱和（<1% 闭合率）**。 |

---

## 3. 主要阻断根因定位（分板）

### 根因共性（决定 P3 路线）
1. **阻容砖墙与混网交错**：三板 0201/0402 阻容按 `21.6–23.6 mil` 行距密集排布，焊盘 `14.2 mil` 仅留 `7.5–9.4 mil` 铜缝，远低于 4 mil 走线 + 2×5.98 mil 间距所需的 `15.96 mil`；且不同电源/信号网阻容交叉排列（如 PCB2 `1V8_FPGA_IO C1` 卡在 `VSYS C4/C5` 正中，PCB3 `LFXO C22/C23` 封死 `1V8_SYS C15/C17`）。
2. **外层 GND 菊花链堵道**：大量阻容未直接就近打 4/10 mil 盲孔入 L2/L5 地平面，而是用 `3.5–4 mil` 外层 GND 线沿列串接（例：PCB2 C4/C5 走廊存在 32 段外层 GND 线），形成铜墙封锁电源/信号出口。
3. **0.35–0.40 mm 细间距器件逃线墙 + 54 条跨层专属网**：外层无法直穿，必须依赖 L3(16)/L4(17) 内层信号与受控 HDI 盲/埋孔。
4. **EPRU 1.97 mil 默认规则残留**：三板 207 条网未建量产网类规则，导致自动/半自动工具缺少规则约束。

### 分板重点问题
- **PCB1（322 错）**：`U1`（57 脚 0.40 mm，36 开放）、`J1`（32 脚 0.35 mm，27 开放）、`U15/U16/U18/U21`（四颗 24 脚 0.40 mm 电平转换，共 59 开放）；`C21/C31/C40` 去耦超距（117/197/241 mil）；`ANT1` 缺全层禁布；GND L2 悬空段 `(125,975)`；**`U12` TPD2E001DRYR 引脚冲突**；`J2/J3/BAT1/SPK1` 外部待定。
- **PCB2（227 错）**：**4.70 mm 极窄板宽** + **TOP 过重（58 TOP vs 28 BOT）**；`U2`（30 球 0.40 mm FPGA，25 开放）、`J1`（15 开放）；9 颗去耦电容超距（`C3` 距 `U13.3` 达 653 mil！`C10/C12` 距 `U11.5` 153/200 mil）；**`J2/J3` 光机 FPC 针序与包络 BLOCKED**。
- **PCB3（127 错）**：**`U11` nRF5340 0.35 mm WLCSP 95 球（球缝仅 6.00 mil，32 开放）**——内圈焊球物理上必须依赖板厂确认的 **2+N+2 盲埋孔叠层（BLOCKED）**；`U3` 充电芯片四面被 `C9/C11/R1/TP4/TP5/Q1` 与板边锁死；`ANT2` 缺全层禁布；`J1`（12 开放）、`U10` WLP-9（6 开放）。

---

## 4. 隔离原生试布成果与可执行候选（区分实测 vs 离线）

### 4.1 已完成 L3 原生隔离验证（`accepted-isolated`，未改动 R11 主档）
- **批次计划**：[p2-01-trial-plan.json](isolated-trial/p2-01-trial-plan.json)（`P2-01-ISOLATED-PCB1-R41-GND`，仅新增 1 条零拆线、独立 `route solve/check` 通过的 6 mil L2 GND 走线 `PCB1 R41.2 → R38.2`，`[202.2, 1330.5] → [202.2, 1377.8]`，长 47.3 mil，0 折角）。
- **原生验证结果**（[acceptance.json](isolated-trial/acceptance.json)、[dfm-review.json](isolated-trial/dfm-review.json)）：
  - 原生连接错误：**PCB1 `322 → 320`（单段线闭合 2 项：`R41_2` 与 `R40_2` 浮空地子岛），三板合计 `676 → 674`**。
  - 新增 DRC 对象：`0`；现有铜/布局/规则/禁布区/平面修改：`0`；严格 ERC 与三板 Protel2 网表字节一致。
  - 独立 V4 DFM 审查：`Audited 3 board(s); 0 unresolved new findings`。
  - 独立重导入验证：`independentReimportVerified: true`（隔离项目 `ffb06a8c…`，独立重导入项目 `cb97e80e…`），产物 [P2-01-ISOLATED-PCB1-R41-GND-NOT-FOR-FAB.epro2](isolated-trial/P2-01-ISOLATED-PCB1-R41-GND-NOT-FOR-FAB.epro2) SHA-256 `8417e1fb4f8ac7c825f4ecb68ddca6569aebb1864fb0f95c17f3028563160689`。
  - 实测耗时：应用 `89.25 s` + V4 DFM `3.33 s` + 独立重导入 `42.99 s` + 门禁校验 `1.40 s` = `136.96 s`。

### 4.2 离线验证 P3 候选与明确拒绝项
- **18 个 DFM-V4 合规 4/10 mil GND 单阶盲孔候选（offline-verified，供 P3 接入官方 SDK 会话执行）**：PCB1 11 个（`R40.2/R41.2/C33.2/C38.2/C13.2/C6.2/C26.2/C16.2/U14.9/C1.2/C15.2`）、PCB2 4 个（`Y1.2/C24.2/C25.2/C16.2`）、PCB3 3 个（`C7.2/C21.2/C8.2`），全部满足 `≥0.350 mm` 板边、`≥0.240 mm` 异网孔壁与 `≥6 mil` 同层铜距，详情见 [gnd-closure-candidates.json](solvers/global-sweep/gnd-closure-candidates.json)。
- **明确拒绝项**：
  1. `PCB1 VSYS L2 J1.P2→J1.P3`：8 mil 通过离线求解，但 20 mil 规则门槛报 `endpoint-blocked`（J1 0.35 mm 间距）；不降规写入，转入 P3 受控焊盘缩颈 ECO。
  2. 首轮试布中 15 条外层 GND 短接：实测导致既有 3–4 mil 外层 GND 线段被拆段/替换，或仅在同一浮空地岛内部互连（PCB2/PCB3 零 DRC 下降），已剔除；P3 统一改走 4/10 mil 单阶盲孔直入 L2/L5 地平面。

---

## 5. 阻断清单（BLOCKED）与可执行 P3 任务拆分

### 外部与工具阻断
| ID | 阻断项 | 状态 | 影响范围 |
| --- | --- | --- | --- |
| `BLK-01` | 0.80 mm 6 层 HDI 物理叠层表与 2+N+2 板厂 EQ | **BLOCKED** | 4 个内层物理厚度/介质缺失；PCB3 U11 0.35 mm WLCSP 内圈逃线、阻抗控制及 L3/L4 定型受阻。 |
| `BLK-02` | PCB1/PCB2 `J2/J3` 连接器实物针序与双目透明 AR 光机包络 | **BLOCKED** | 6 项严格 ERC `MISSFOOTPRINT`、1 项 PCB1 网表差异及光学接口区走线冻结。 |
| `BLK-03` | PCB1 `U12`（TPD2E001DRYR）符号/封装/网表引脚冲突 | **BLOCKED（待 ECO 批准）** | 原生 1=USB_DP/2=GND/5=VBUS 与 TI DRY 手册冲突，需批准 ECO 并补 0.1 µF VCC 旁路及重布 USB 差分。 |
| `BLK-04` | `easyeda-agent` v1.20.0 工具能力边界 | **BLOCKED-TOOL** | 44 个 POLYGON 焊盘阻断 `pcb routability`；`pcb layout solve` 仅支持 2 层；`pcb.via.list` 缺盲孔跨层致 `pcb check` 误报间距。 |

### P3 可执行任务（严格拆分无外部依赖 vs 依赖门控）
1. **P3-NoDep-1（规则规范化与废铜清理，L2）**：全三板 207 网建立显式生产网类（取消 1.9685 mil EPRU 默认，锁定 SIGNAL ≥4 mil / POWER_BRANCH ≥6–10 mil / POWER_TRUNK ≥15.75–20 mil / GND ≥6 mil），清理 PCB1 GND L2 悬空线 `(125,975)`，补全 PCB1 `ANT1` 与 PCB3 `ANT2` 全层禁布区。
2. **P3-NoDep-2（直入地平面盲孔收口 + 拆外层 GND 围墙，L2/L3）**：通过官方 SDK 会话落地 18 颗已核 4/10 mil 单阶 GND 盲孔（`BV_L1_L2`/`BV_L5_L6`），随后按网清理堵道的冗余外层 3.5–4 mil GND 串接墙，释放阻容通道。
3. **P3-NoDep-3（成组协同重排，触发 L3）**：
   - PCB1：按 `3V3_SYS`/`1V8_SYS`/`VSYS` 重新聚类 `C30/C38/C42/R7/R9` 等阻容阵列，拉近 `C21/C31/C40` 去耦至 ≤100 mil。
   - PCB2：沿 Y 轴重排 `VSYS` 电容组（`C4/C5/C8/C9/C10/C12`）剥离插队的 `1V8_FPGA_IO C1`，拉近 `C3/C10/C12` 去耦，并将部分无光学干涉阻容由 TOP（58 件）迁至 BOT（28 件）实现双面均衡。
   - PCB3：成组外移 `TP4/TP5/Q1` 打开 `U3` 充电芯片周边通道；分离 `1V8_SYS C15/C17` 与 `LFXO C22/C23` 晶振区。
4. **P3-Gated-1（待 ECO 批准，触发 L3）**：落实 PCB1 `U12` TPD2E001DRYR 封装/原理图/网表修正与 `USB_D` 90 Ω 差分重布。
5. **P3-Gated-2（待 `BLK-01`/`BLK-02` 签核，触发 L3）**：录入确认后的 0.80 mm 6L HDI（含 PCB3 2+N+2）叠层与 `J2/J3` 封装，在 L3(16)/L4(17) 完成细间距器件（PCB1 U1/U15/U16/U18/U21、PCB2 U2、PCB3 U11/U10）扇出与 54 条跨层专属网闭合。
