# P2-01 / P2-02 | 三板全局可布线性评估与隔离验证 STATE

**2026-11-25 · L3 隔离验证通过 · NOT FOR FAB**

- **基线**：PR #66 commit `45bc2d4e7e6ca9383ecc0184365fc66dbb89be9e`；原生工程基线 PR #64 `79ce0553f6aaa90ebfee773dceefaf5505d11f30`（R11-MASTER EPRO2 SHA-256 `758618cb4bbb12a5ed34200cbf7c51f2e476c80ed9eee96643efed4764791074`），严格遵循 PR #65 V2.0 工作流。
- **产品约束保持**：40 g 整机目标、真实双目透明 AR、高密度 HDI 集成、不降规、不覆盖 R11 主档。
- **工具链状态**：`easyeda-agent` Skill/CLI/Daemon/固定 Connector 均为 `v1.20.0`（窗口 `5095e7f7-071b-4d2e-ab41-c5aa3ae3fd02`），宿主嘉立创 EDA 专业版 `4.1.97`。

## 原生验证指标（隔离工程 vs R11 基线）

| 项目 | R11 原生基线 | P2-01 隔离试布（L3 独立重导入通过） | 变化 |
| --- | ---: | ---: | ---: |
| PCB1 连接错误 | 322 | **320** | **-2**（`R41_2` + `R40_2`） |
| PCB2 连接错误 | 227 | 227 | 0 |
| PCB3 连接错误 | 127 | 127 | 0 |
| **三板合计连接错误** | **676** | **674** | **-2** |
| 新增原生 DRC 对象 | — | **0** | 零回归 |
| 独立 V4 DFM 新增未解项 | — | **0** | 3 板审查通过 |
| 严格 ERC / Protel2 网表 | 4 / 0 / 2（1 网表差） | 4 / 0 / 2（1 网表差，字节一致） | 零变更 |

- **隔离试布实测耗时**：应用 `89.25 s` + V4 DFM `3.33 s` + 独立重导入 `42.99 s` + 门禁验证 `1.40 s` = `136.96 s`。
- **隔离产物**：[P2-01-ISOLATED-PCB1-R41-GND-NOT-FOR-FAB.epro2](isolated-trial/P2-01-ISOLATED-PCB1-R41-GND-NOT-FOR-FAB.epro2)（SHA-256 `8417e1fb4f8ac7c825f4ecb68ddca6569aebb1864fb0f95c17f3028563160689`），接纳回执 [acceptance.json](isolated-trial/acceptance.json)。

## 已完成核心结论

1. **网络分类与规则审计**：三板 207 网（PCB1 112 / PCB2 58 / PCB3 37）全量分类完成；实证 207 网均绑定 `1.9685 mil` EPRU 默认规则且无量产网类；电源 + GND 占总开放错误 46.4%（314/676）。
2. **外层饱和数学证明**：`pcb route solve/check` 跨三板 184 组真实跨岛对扫描仅 1/184 通过（8 mil VSYS，20 mil 规则门槛拒绝）；真实地平面跨岛扫描仅 1/30 零拆线直连通过（已通过 L3 隔离验证）。证明在现布局上继续盲目外层布线不可行。
3. **三大布局/通道根因**：(a) 21.6–23.6 mil 阻容砖墙与混网交错（7.5–9.4 mil 铜缝 < 15.96 mil 通道需求）；(b) 外层 3.5–4 mil GND 串接围墙堵道；(c) 0.35–0.40 mm 细间距逃线墙与 54 条跨层专属网。`pcb layout-plan` 24 组单件方向搜索 0 候选，证实须成组协同重排。
4. **可执行 P3 候选**：整理 18 颗离线 DFM-V4 合规 4/10 mil 单阶 GND 盲孔候选（PCB1 11 / PCB2 4 / PCB3 3）及无依赖 vs 门控 P3 ECO 路径。

## 剩余阻断（BLOCKED）

- `BLK-01`：0.80 mm 6 层 HDI 物理叠层与 PCB3 `U11`（0.35 mm WLCSP 95 球）2+N+2 板厂 EQ。
- `BLK-02`：PCB1/PCB2 `J2/J3` 实物针序与真实双目透明 AR 光机包络（6 项 ERC + 1 项 PCB1 网表差）。
- `BLK-03`：PCB1 `U12`（TPD2E001DRYR）引脚冲突待 ECO 批准。
- `BLK-04`：`easyeda-agent` v1.20.0 内置工具限制（44 个 POLYGON 焊盘阻断 `pcb routability`；`pcb layout solve` 仅双层；`pcb.via.list` 缺盲孔跨层致 `pcb check` 误报间距）。

## 交付与索引

- [三板可布线性与 ECO 方案](P2-01-ROUTABILITY-ECO-PLAN.md) · [结构化总表 JSON](P2-01-3BOARD-ROUTABILITY-AND-ECO.json)
- [L3 接纳回执](isolated-trial/acceptance.json) · [V4 DFM 审查](isolated-trial/dfm-review.json) · [试布计划](isolated-trial/p2-01-trial-plan.json)
- [网络分类与规则回读](net-classes/) · [逐脚可布性回执](routability/) · [求解器汇总](solvers/) · [原生诊断](evidence/)

## 下一步（P3）

优先推进无外部依赖的 `P3-NoDep-1`（三板 207 网量产规则/网类规范化 + ANT1/ANT2 禁布区 + PCB1 悬空线清理）、`P3-NoDep-2`（18 颗 4/10 mil 单阶 GND 盲孔落地并拆除外层 GND 围墙）与 `P3-NoDep-3`（三板阻容成组重排与 PCB2 双面均衡，触发 L3）；同步推进 `BLK-01/02/03` 外部确认与 ECO 审批。
