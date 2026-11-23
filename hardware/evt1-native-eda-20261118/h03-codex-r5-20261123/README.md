# 智元跃动 AI/AR 智能眼镜 V1.0 · EVT-1 H03 R5

**NOT FOR FAB**。继承 PR #52 的提交 710fe9deb9b0a39325e851193fcd083352de5927。保留三板、21 页原理图、既有器件与 BOM 顺序、真实双目透明 AR、40 g 目标和光机、隐私、充电安全网络。变更通过嘉立创 EDA 专业版 V4.1.97 的隔离项目实施并保存。 [R4 Draft PR #52](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/52)

## R5 原生铜箔修改

- **PCB3**。为 U11.A5 增加 4 mil 顶层支线和一颗 4/10 mil GND 微盲孔，复用 L1–L2 已定义跨层。铜盘至最近异网铜 6.079 mil，孔边到最近原焊球开口 3.131 mil，L2 铜盘至地平面边界 17.1 mil，均为标称尺寸。原生严格 DRC 中 A5 的未连通项消失。U11.B2–C2 原两段 3 mil 折线换为一段 4 mil 顶层线并验证端到端路径。底层新增 R4.2 到 C4.2 的可回读 GND 路径，以及 MK3.4 到既有 GND 过孔的支线。R4.2 和 MK3.4 仍在整网开路清单中，须继续核对返回铜到完整地网。 [U11 几何和替代工艺](u11/U11_R5_GEOMETRY.md) · [PCB3 保存后 DRC](verification/PCB3-after-drc.json) · [A5 铜箔前后图](verification/PCB3-U11-A5-before-after.svg)
- **PCB1**。顶层新增 6 mil GND 路径 R20.2–R22.2 和 4 mil CHG_ISO_GATE 局部路径 R19.2–R20.1。充电栅极远端 Q1.1 后续布通。106 段电源和 GND 从 3 mil 加宽到 4 mil，原中心线保留。EDA 将一段的同网 T 接点自动拆成两段，端点和铜包络均复核。472 段 3 mil 剩 366 段。 [局部宽度与布线筛查](pcb1/plan-pcb1-power-fresh.json) · [原生回执](verification/PCB1-width-batch/)
- **PCB2**。C16.2–C28.2 新增 3.6 mil 顶层 GND 回流段，验证连接不同的铜簇。C5/C10/C31/C32 一带的 10 段地线沿现有中心线 3→4 mil。C5.2–C10.2 和 C8.1–C12.1 已有铜线。批量加宽时 EDA 已按原中心线替换对应旧 ID，首次删除尝试返回旧 ID 不存在。随后通过回读确认同网、同层、原中心线及目标宽度，再正式保存。 [桥板回流和 C11 放置试验](pcb2/README.md) · [原生回执](verification/PCB2-apply/)

## 实测验证

| 原生严格检查 | PCB1 | PCB2 | PCB3 |
| --- | ---: | ---: | ---: |
| 未连通，修改前 → 独立重导入后 | 355 → 352 | 237 → 236 | 134 → 132 |
| Netlist Error，前 → 后 | 1 → 1 | 0 → 0 | 0 → 0 |
| 严格 ERC 致命项，前 → 后 | 4 → 4 | 0 → 0 | 2 → 2 |

三板合计未连通 **726 → 720**。原生 DRC 三板仍失败，间距和短路项均为 0。工程载荷审批只允许上述三板铜箔及编辑器自动占位计数变化。其余文档及 PCB 规则、层叠、板框、焊盘网络、器件位姿、丝印和电源安全逻辑保持一致。新盲孔经独立重导入后仍为 L1–L2，V4 几何复核覆盖 142 颗盲孔。 [验证脚本](verify_r5.py) · [前后原始 ERC/DRC](verification/) · [可编辑 .epro2](native/EVT1-H03-CODEX-R5-NOT-FOR-FAB.epro2)

现用 Typed Via API 只生成通孔。A5 先按历史 PR #47 的原生归档方法增加单颗同类型盲孔，在独立项目原生导入后，用 Typed Track 写入走线，显式保存、关闭重载、重跑严格检查并由专业版重新导出。 [单过孔候选差异](verification/a5-archive-delta.json) · [原生保存重载](verification/final-PCB3-reload.json)

R5 可编辑档案 SHA-256 为 84b99c1c60fd03aca74e19f025c3a37b421342d79de7c068009543e6b2e9b070。完整剩余条件见 [BLOCKED](BLOCKED.md)。
