# 智元跃动 AI/AR 智能眼镜 EVT-1 H03 — 剩余 BLOCKED 清单（NOT FOR FAB）

> **放行硬性约束**：本清单中任意 `BLOCKED` 项在未获得实测验证与书面工程签核前，严禁解除 `NOT FOR FAB`，严禁降低制造规则，严禁牺牲 40 g 整机目标或真实双目透明 AR 架构。

## 1. 原生工程交付闭环（待手动上传）
- **状态**：**BLOCKED（原生 `.epro2` 交付未完成）**
- **阻断原因**：远程浏览器管理员策略禁止本地文件访问（`Access to local files on your machine is disabled by your administrator`），无法在远程环境中完成 `.epro2` 二进制文件上传、本地 SHA-256 计算及独立重导入复核。
- **解除条件**：从嘉立创 EDA 专业版云端工程 [EVT1-H03-CODEX-PR46-20261121](https://pro.lceda.cn/editor#id=49218390f19d408e857f00938cbf6c78) 通过 `文件 (F) -> 另存为 -> 工程另存为(本地)(A)...` 导出 `.epro2`，计算本地 SHA-256，提交至基于 [PR #47](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/47) 的独立 Draft PR，并在本地嘉立创 EDA 客户端执行一次独立重导入核验。

## 2. PCB1 接口封装与剩余 1 项 Netlist Error
- **状态**：**BLOCKED**
- **具体缺口**：
  - `J2`（`EVT1_J2_J_CAM`，26 脚，已核实广濑料号 [BM28B0.6-24DS/2-0.35V(53)](https://www.hirose.com/en/product/p/CL0673-5025-0-53)）：待相机模组供应商确认配对 FPC 针位定义与官方 Land Pattern 封装图纸。
  - `J3`（`EVT1_J3_J_CHG`，4 脚，`MPN_TBD`）：待真实 4 针磁吸充电接口选型、电气电流参数与机械封装图纸冻结。
  - 两颗器件均保持 `转到PCB=是`，严禁通过改为 `转到PCB=否` 伪装网表闭环；因此 PCB1 保留 1 项 Netlist Error 与原理图 ERC 缺失封装致命错误。
- **解除条件**：导入经审核的 `J2`/`J3` 官方封装，重新执行 `从原理图导入变更` 并确认 PCB1 Netlist Error 归零。

## 3. 三板 729 处未连通飞线与窄条高密布线通道
- **状态**：**BLOCKED**
- **当前基线**：三板合计 **729** 处未连通（PCB1 `358`、PCB2 `237`、PCB3 `134`），当前间距错误为 `0`。
- **阻断原因**：PCB2 与 PCB3 均为约 140~160 mil 窄条双面高密贴装，表层焊盘与既有线束密集，在当前锁定 6 mil（`0.152 mm`）规则下缺乏零违规表层直连通道，且多条关键控制/供电/复位/FPGA/GND 飞线需与内层参考平面和 BGA 扇出协同规划。
- **解除条件**：在完成层叠与通道规划后，逐网布通关键供电、GND、复位、FPGA、AVDD 保护与相机/光学安全联锁网络，保持 0 间距错误与 0 规则降级。

## 4. PCB2 8 颗去耦电容联合重布局（保留功能性 RC）
- **状态**：**BLOCKED**
- **具体缺口**：`C5`、`C8`、`C9`、`C10`、`C11`、`C12`、`C31`、`C32` 位于板顶集中区，在当前锁定 6 mil 规则与底层 `FPGA_C...` 竖向走线束占用的条件下，无法在不引入间距冲突（实测 51~58 项）的前提下直接贴近对应 IC 摆放。功能性定时/滤波 RC 电容 `C2`（`AVDD_QUAL_RC`）与 `C3`（`AVDD_REQ_FILTER`）必须保留原电气功能。
- **解除条件**：完成 `FPGA_C...` 线束迁入内层、底层回流地与去耦布局的联合设计，且实测 DRC 零恶化。

## 5. PCB3 真实层叠（0.80 mm 2+N+2 HDI）与 U11（0.35 mm WLCSP）内圈逃线
- **状态**：**BLOCKED**
- **具体缺口**：
  - 当前工程物理堆叠为默认 6 层 `JLC06161H-3313`（1+4+1，总厚 `1.7873 mm`），**并非 0.80 mm 2+N+2 HDI**；盲孔仅定义 `BV_L1_L2` / `BV_L5_L6` 且过孔尺寸为空。
  - [nRF5340-CMAA WLCSP95](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)（`0.35 mm` 球距，保留 ECO-08 LFXO）在锁定 `0.152 mm` 铜距规则下，内圈有网球位几何上无法完成居中盲孔逃线或穿线。
- **解除条件**：取得板厂针对 `0.80 mm` 2+N+2 顺序压合叠层、二阶微盲孔、[盘中孔 VIPPO](https://jlcpcb.com/blog/via-in-pad-pcb)（IPC-4761 Type VII）、U11 BGA 局部细间距规则及 WLCSP 避光/装配公差的书面 EQ 签核，再切换层叠并完成 U11 逃线与 RF/LFXO 启动验证。

## 6. 光机、相机安全联锁与整机 40 g / MECR-01 签核
- **状态**：**BLOCKED**
- **具体缺口**：双目透明 AR 光机 FPC 配对、AVDD 硬件关断保护、相机隐私联锁、拼板/层压公差、MECR-01 光学与结构干涉检查及 40 g 整机重量预算均需供应商最终针位参数与实物样机测试作为放行依据。
