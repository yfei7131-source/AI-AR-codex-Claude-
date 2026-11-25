# 智元跃动 AI/AR 智能眼镜 EVT-1 / H03-R3 — 剩余 BLOCKED 清单（NOT FOR FAB）

> **放行硬性约束**：本清单中任意 `BLOCKED` 项在未获得实测验证与书面工程签核前，严禁解除 `NOT FOR FAB`，严禁降低制造规则，严禁牺牲 40 g 整机目标或真实双目透明 AR 架构。

## 1. R3 独立副本 `.epro2` 手动上传 GitHub
- **状态**：**待用户本地上传**
- **R3 云端工程**：`EVT1-H03-GEMINI-R3-NOT-FOR-FAB-20261123`（[编辑器链接](https://pro.lceda.cn/editor#id=9ddea73b8d35456bad84c40e331d2f05)，嘉立创 EDA 专业版 `V4.1.105`）
- **实测导出文件**：`ProPrj_EVT1-H03-GEMINI-R3-NOT-FOR-FAB-20261123_2026-11-23.epro2`（`1,558 KB`，`epro2 (V3格式)`）
- **操作步骤**：本地打开上述 R3 云端工程，执行 `文件 (F) -> 另存为 -> 工程另存为(本地)(A)... -> epro2 (V3格式)` 导出并计算本地 SHA-256，连同本 `README.md` 与 `BLOCKED.md` 手动提交 GitHub。

## 2. PCB1 线宽 DFM 剩余阻断（1 条 `2 mil` 导线 `e938` + 472 条 `3 mil` 导线）
- **状态**：**BLOCKED**
- **实测进展**：8 条 `2 mil` `GND` 导线中已有 **7 条成功加宽至 `4 mil`**（`e901/e914/e923/e937/e951/e952/e953`，0 间距/0 短路错误）。
- **具体缺口**：
  - 剩余 1 条底层 `2 mil` `GND` 导线 **`e938`**（`(53.5, 1383.3)→(45.1, 1391.7)`）加宽至 `4 mil` 或 `3.5 mil` 时与 `BB_FB` 通孔 **`e85`**（`12/6 mil`，`(32.5, 1395)`）实测间距仅 `5.0~5.2 mil < 6.0 mil`，须先东移 `e938` 拐点绕行或西/北移 `e85` 过孔 `2~3 mil` 后再加宽至 `4 mil`。
  - PCB1 另存 `472` 条 `3 mil` 导线（嘉立创标准 6 层 1 oz 常规能力为 [3.5 mil / 0.09 mm](https://jlcpcb.com/6-layer-pcb)，`3 mil` 仅限 BGA 扇出区或高阶工艺 EQ），须在板厂 DFM EQ 中确认或局部加宽。

## 3. PCB1 `J2 (J_CAM)` / `J3 (J_CHG)` 封装与剩余 1 项 Netlist Error
- **状态**：**BLOCKED**
- **具体缺口**：
  - `J2`（广濑 [BM28B0.6-24DS/2-0.35V(53)](https://www.hirose.com/en/product/p/CL0673-5025-0-53)，26 脚）：待相机模组供应商冻结配对 FPC 针位与官方 Land Pattern 图纸。
  - `J3`（4 针磁吸充电接口 `MPN_TBD`）：待真实供应商选型、电流参数与机械封装图纸。
  - 两者均保持 `转到PCB=是`，严禁改为 `转到PCB=否` 伪装闭环。

## 4. 三板剩余 726 处未连通飞线
- **状态**：**BLOCKED**
- **当前 R3 实测统计**：PCB1 **`355`**、PCB2 **`237`**、PCB3 **`134`**，三板合计 **`726`**（间距错误 `0`、短路错误 `0`）。
- **解除条件**：在完成 PCB2 内层 `FPGA_C...` 线束迁移与 PCB3 HDI 层叠 EQ 后，推进全板关键供电、GND、复位、FPGA、AVDD 保护与安全联锁网络布通，保持 0 间距违规与 0 规则降级。

## 5. PCB2 8 颗去耦电容联合重布局（保留 C2/C3 功能性 RC）
- **状态**：**BLOCKED**
- **具体缺口**：`C5/C8/C9/C10/C11/C12/C31/C32` 在 4 mm 窄板框与锁定 0.152 mm 规则下受顶层 QFN/0201 及底层 `FPGA_C...` 走线束阻挡，须先将 `FPGA_C...` 迁入内层信号层并重构底层回流地；功能性 RC（`C2`、`C3`）与 AVDD 硬件保护保持不变。

## 6. PCB3 0.80 mm 2+N+2 HDI 叠层与 U11（0.35 mm WLCSP）内圈逃线
- **状态**：**BLOCKED**
- **具体缺口**：当前叠层为默认 6 层 `JLC06161H-3313`（`1.7873 mm`，1+4+1），仅定义 1 阶盲孔且无 BGA 区域规则；[nRF5340-CMAA WLCSP95](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)（`0.35 mm` 球距，需避光防护）在锁定 `0.152 mm` 间距下无法内圈扇出。须取得板厂针对 `0.80 mm` 2+N+2 顺序压合叠层、二阶微盲孔、[盘中孔 VIPPO](https://jlcpcb.com/blog/via-in-pad-pcb)（IPC-4761 Type VII）及 U11 局部 `3/3 mil` 细间距规则的书面 EQ 签核；若 EQ 不可行，再与结构/ID 联合评审替代封装 `nRF5340-QKAA (aQFN94, 7×7 mm)`。

## 7. 光机、相机安全联锁与整机 40 g / MECR-01 签核
- **状态**：**BLOCKED**
- **具体缺口**：真实双目透明 AR 光机 FPC 配对、AVDD 关断、相机隐私联锁、拼板公差、MECR-01 光学结构干涉及 40 g 整机重量预算均须供应商最终资料与实物测试放行。