# EVT-1 H03 R11-MASTER STATE

**2026-11-25 · 嘉立创 EDA 专业版 V4.1.97 · NOT FOR FAB**

继承 PR #62 提交 `59fb25511ad82649d26de0016137bb2e18c4332d` 的原生 EPRO2。PR #63 的 Neno0–4 共 62 份文件全部核对。整机 40 g 目标、真实双目透明 AR、高密度集成及既有制造安全规则继续适用。 [PR #62](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/62) · [PR #63](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/63)

## 原生验证

| 板 | 基线 → 主档连接错误 | 独立重导入 | 严格 ERC fatal | 网表差异 |
| --- | ---: | ---: | ---: | ---: |
| PCB1 主板 | 328 → 322 | 322 | 4 | 1 |
| PCB2 光学桥板 | 232 → 227 | 227 | 0 | 0 |
| PCB3 右音频板 | 129 → 127 | 127 | 2 | 0 |
| **三板** | **689 → 676** | **676** | **6** | **1** |

三板接入 24 段走线与 4 颗错位接地盲孔，净减 13 项原生连接错误。三板均通过显式保存、文档重载和新回读。独立项目重新导入主档后，1,451 份原生文档记录、连接错误对象、ERC 对象及三份 Protel2 网表一致。严格 DRC 仍报上表中的连接与网表错误，间距与短路类别为零。独立 V4 子集审计覆盖 146 个盲孔，孔径、孔壁、环宽、板边及层跨检查为零项违规。旧版矩阵的 12 条继承警报待审。新标出的 3 条 PCB3 TP3.1 间距按原生圆形铜盘复算，最小保守净距 6.85 mil。 [回归](verification/regression.json) · [盲孔与间距审计](verification/dfm-reconciliation.json) · [原始日志](logs/)

- **PCB1** 接入 Neno0 的 U18 接地支路。L6 6 mil 短线搭配既有 BV_L5_L6 规则的 4/10 mil 盲孔，接入真实 L5 GND 铜面。R16/R24 同面移近 U19，接上 SCL 和使能信号并用 6 mil 连接两颗上拉的 3.3 V 端，上游馈电仍开放。第三颗 R18 换面试布曾降至 319 项，其背面位置与正面 J3 候选投影重合，壳体和磁铁高度待核，主档保留通过回归的双电阻方案。
- **PCB2** 将 C11 移出 MK2 装配占位，接到 L5 GND 和 U14.5 的 20 mil VSYS 局部支路。同时接入 U8.4 的 L6→L5 地回流。C11 原属 U13 电源监督器，U13 及上游 VSYS 仍需连通。复放使用通过 3W 平行检查的折线。
- **PCB3** 将 C6.2 的 6 mil 接地支路通过 BV_L1_L2 接入 L2 GND。C14 试验曾将 PCB3 降到 124 项，但该位置未解决 nRF 就近去耦。由试验前检查点独立导入，复现 127 项和完整文档记录。 [回滚验证](logs/rollback/verification.json)

三板原生自动扇出回读无新增图元。两面自动布线试验所得 PCB2 线宽 1.96 mil 且报错数无改善。PCB3 四信号层作业长期停在 0%，被取消，返回的中间候选仍使用约 1.97 mil 线宽。上述批次均停留在隔离工程。Neno1 缺少可用内层孔跨且几何碰到地平面，Neno2 多处穿越地平面且涉及未接受的 I²S 引脚 ECO。 [五窗口核查](verification/pr63-five-window-admission.json)

## 制造阻断

- **J2/J3** 的实物针序、极性和装配未确认，封装待定。BAT1/SPK1 四个板外实例留在原理图与 BOM，保留既有板端焊点映射。六项 MISSFOOTPRINT 和 PCB1 一项网表差异仍开放。已放端子 PCB1/PCB2/PCB3 共 477/303/191 个，原生网表逐脚匹配。 [ERC/网表台账](verification/erc-netlist-regression.json)
- **PCB1 U12** 的 TPD2E001DRYR 物理引脚分配与原生符号及焊盘网络有冲突。DRY 封装 1 脚为 VCC、4 脚为 GND、3/6 脚为 I/O、2/5 脚为 NC。原生 1 脚连 USB_DP、2 脚连 GND、5 脚挂 VBUS。纠正需要核准新版封装、重接 PCB 的 USB 与地铜，并落实 VCC 的 0.1 µF 旁路。 [TI 数据手册 §5](https://www.ti.com/lit/ds/symlink/tpd2e001.pdf#page=3)
- 三板残余电源馈电、信号连接与高密度逃线待闭合。0.80 mm HDI 叠层及二阶盲埋孔、光机和机械、实测整机质量与板厂 EQ 仍待签核。

## 工程交付

可编辑原生档 [EVT1-H03-R11-MASTER-NOT-FOR-FAB.epro2](EVT1-H03-R11-MASTER-NOT-FOR-FAB.epro2)，SHA-256 `758618cb4bbb12a5ed34200cbf7c51f2e476c80ed9eee96643efed4764791074`。同目录 ZIP 包含工程、STATE、回归原始记录和审计文件。
