# 智元跃动 AI/AR 智能眼镜 EVT-1 / H03 — 剩余 BLOCKED 清单（PR #48 续研，NOT FOR FAB）

> **放行硬性约束**：本清单中任意 `BLOCKED` 项在未获得实测验证与书面工程签核前，严禁解除 `NOT FOR FAB`，严禁降低制造规则，严禁牺牲 40 g 整机目标或真实双目透明 AR 架构。

## 1. 本轮原生 `.epro2` 导出与独立 Draft PR 补交
- **状态**：**待本地同步提交**
- **实测进展**：嘉立创 EDA 专业版云端工程 [ProPrj_EVT1-H03-CODEX-PR46-20261121](https://pro.lceda.cn/editor#id=49218390f19d408e857f00938cbf6c78) 已保存并通过关闭重开持久化验证，网页端 `工程另存为(本地) -> epro2 (V3格式)` 实测成功导出（`1,416 KB`）。
- **手动导出步骤**：在本地打开上述云端工程，点击 `文件 (F) -> 另存为 -> 工程另存为(本地)(A)... -> epro2 (V3格式)`，计算本地 SHA-256 后连同本 `README.md` 与 `BLOCKED.md` 提交至基于 PR #48 的独立 Draft PR。

## 2. PCB1 `J2 (J_CAM)` / `J3 (J_CHG)` 封装与剩余 1 项 Netlist Error
- **状态**：**BLOCKED**
- **实测确认**：PCB1 精确网表对比确认全部元件/网络差异 100% 仅涉及 `J2` 与 `J3`。
- **具体缺口**：
  - `J2`（广濑 [BM28B0.6-24DS/2-0.35V(53)](https://www.hirose.com/en/product/p/CL0673-5025-0-53)，26 脚）：待相机模组供应商冻结配对 FPC 针位与官方 Land Pattern。
  - `J3`（4 针磁吸充电接口 `MPN_TBD`）：待真实供应商选型、电流参数与机械封装图纸。
  - 两者均保持 `转到PCB=是`，严禁改为 `转到PCB=否` 伪装闭环。

## 3. 三板 729 处未连通飞线与窄条高密布线
- **状态**：**BLOCKED**
- **当前重开复核基线**：PCB1 `358`、PCB2 `237`、PCB3 `134`，合计 **729**（间距错误均为 `0`）。
- **解除条件**：在完成 PCB2 内层走线束迁移与 PCB3 HDI 层叠 EQ 后，推进全板关键供电、GND、复位、FPGA、AVDD 保护与安全联锁网络布通，保持 0 间距违规。

## 4. PCB2 8 颗去耦电容联合重布局（保留 C2/C3 功能性 RC）
- **状态**：**BLOCKED**
- **具体缺口**：`C5/C8/C9/C10/C11/C12/C31/C32` 在 4 mm 窄板框与锁定 0.152 mm 规则下受顶层 QFN/0201 及底层 `FPGA_C...` 走线束阻挡，须联合将 `FPGA_C...` 迁入内层信号层并重构底层回流地，实测 DRC 零恶化后方可落盘；功能性 RC（`C2`、`C3`）与 AVDD 硬件保护保持不变。

## 5. PCB3 0.80 mm 2+N+2 HDI 叠层与 U11（0.35 mm WLCSP）内圈逃线
- **状态**：**BLOCKED**
- **具体缺口**：当前叠层为默认 6 层 `JLC06161H-3313`（`1.7873 mm`，1+4+1），仅定义 1 阶盲孔且无 BGA 区域规则；[nRF5340-CMAA WLCSP95](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) 在锁定 `0.152 mm` 间距下无法内圈扇出。
- **解除条件**：取得板厂针对 `0.80 mm` 2+N+2 顺序压合叠层、二阶微盲孔、[盘中孔 VIPPO](https://jlcpcb.com/blog/via-in-pad-pcb)（IPC-4761 Type VII）、U11 局部细间距规则及避光/装配公差的书面 EQ 签核。

## 6. 光机、相机安全联锁与整机 40 g / MECR-01 签核
- **状态**：**BLOCKED**
- **具体缺口**：真实双目透明 AR 光机 FPC 配对、AVDD 关断、相机隐私联锁、拼板公差、MECR-01 光学结构干涉及 40 g 整机重量预算均须供应商最终资料与实物测试放行。