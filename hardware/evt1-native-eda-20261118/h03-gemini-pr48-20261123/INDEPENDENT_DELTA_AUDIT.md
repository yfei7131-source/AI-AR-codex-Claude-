# EVT-1 H03 Gemini 2026-11-23 原生工程独立静态审查

> **NOT FOR FAB。** 这是对原生 EPRO2 图元记录的离线比较，不是嘉立创 EDA 原生 ERC、DRC 或电气连通性验证。

## 审查来源

- 旧工程：`ProPrj_EVT1-H03-CODEX-PR46-20261121_2026-11-22.zip`，内部 EPRO2 SHA-256 `2e53a3e65a1c3ca577c11a36426be948e6381be62cc9595900152064f41ac0de`。
- 新工程：`ProPrj_EVT1-H03-CODEX-PR46-20261121_2026-11-23.zip`，内部 EPRO2 SHA-256 `74a39d987e906ebdc9125ab6f7a1523050a132f7602462de45d1d73920b8e4e2`。
- 新 ZIP CRC、内部 EPRO2 CRC：均通过。
- 原始文件被完整保留，审查未修改新工程任何字节。

## 独立静态事实

- 两版均包含 1451 个内部文档 UUID，其中包括 3 块 PCB 和 21 个原理图页面，目录 ID 不变。
- 仅 PCB1（`8fbc3cae65886fe5`）的原生图元实体发生变化。PCB2/PCB3 原生文档中的图元数据与旧版一致。
- 元件：PCB1 118 / PCB2 86 / PCB3 53，总计 257；过孔：97 / 47 / 52，总计 196，均未变。
- PCB1 `LINE`：808 → 805；具体为新增 18 条 LINE 记录、删除 21 条 LINE 记录；部分只是线段拆分、方向变换和局部重建，不应把 3 条差额解释为 3 个网络节点的变化。
- PCB2 `LINE` 397 不变；PCB3 `LINE` 384 不变。
- PCB1 新增网络记录：{'CAM_AVDD_2V8': 2, 'GND': 13, 'ESP_VDD_SPI_3V3': 2, 'CAM_DVDD_1V2': 1}；删除记录：{'GND': 21}。
- 原生板卡以外的图元数据未变化（部分图元 `DOCHEAD.client` 标识随导出会话变化，不属于设计变化）；新工程的 PCB1 快照图 `IMAGE/8fbc3cae65886fe5.webp` 比旧包多一份。

## Gemini 原报告与本次审查的差异

- Gemini 报告提到 PCB1 局部 `ESP_VDD_SPI_3V3`、`GND` 安全布线，EDA 重开 DRC 仍为 358 / 237 / 134 未连通、Netlist Error 1 / 0 / 0，间距错误 0；**本次仅可独立证实静态图元差异，不能独立证实 DRC 数值**。
- 实际原生改动还包括 `CAM_AVDD_2V8` 的 **2 条新增 LINE**、`CAM_DVDD_1V2` 的 **1 条新增 LINE**，原 README 未对这些相机供电网络新增线给出专项验收说明。
- 在 Gemini 下一次操作时，应针对 3 条相机供电新线核查始终属于原始 net、实际端点、回流路径、相机隐私/AVDD 关断条件、间距及是否意外触碰其它铜网。需要保存原生 DRC 与交叉网表证据。
- GND 原生更改较多（21 条旧 GND LINE 删除，13 条 GND LINE 新增），需人工或 EDA 复核其原有接地点是否仍连通；仅 DRC 总数不变不能排除局部有连接断开与其他连接同时补齐。

## 当前阻断

1. PCB1 `J2/J3` 实物配对与封装仍缺证据；1 Netlist Error（Gemini 报告）。
2. 全板 729 处未连通（Gemini 报告），本轮未证明减少。
3. PCB2 去耦及走线束重布局未实际完成。
4. PCB3 U11 WLCSP 内圈逃线、0.80 mm HDI/2+N+2 和板厂 EQ 未实际关闭。
5. 当前仍为 NOT FOR FAB。

## 推荐交付基线

以 GitHub PR #48 分支 `hardware/evt1-h03-gemini-cbb-sync-20261122` 为 base，创建新独立研发分支和 Draft PR。不得覆盖 PR #48 原工程。交付前请对额外相机供电改线完成真实 DRC/ERC 与 netlist 验证。
