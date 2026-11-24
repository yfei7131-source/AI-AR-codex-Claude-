# J2 摄像头接口核实与 PCB1 ERC 合规闭环步骤（供导入 R10-TEST-J3 后直接执行）

## 1. J2 器件、配对件与采购条件（已核实，零虚构）

- **主板插座（J2）**：Hirose `BM28B0.6-24DS/2-0.35V(53)`（`CL0673-5025-0-53`）
  - [Hirose 官方页面](https://www.hirose.com/en/product/p/CL0673-5025-0-53) ｜ [2D 图纸 EDC-364666-53-00](https://www.hirose.com/en/product/p/CL0673-5025-0-53/documents?path=%2Fapi%2Fv1%2Fproducts%2FCL0673-5025-0-53%2Fdocuments%2Fdrawing_2d%2Fcontent%3Flang%3DEN)
  - [JLCPCB `C5577343`](https://jlcpcb.com/partdetail/6495731-BM28B0_6_24DS_2_0_35V_53/C5577343)（现货 `153`，1+ `$1.5660`）｜ [DigiKey `H125603CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DS-2-0-35V-53/7793566)（Active，现货 **`4,544`**，1+ `$1.67`，MSL 1，RoHS3，20 周交期）
- **FPC 配对插头**：Hirose `BM28B0.6-24DP/2-0.35V(53)`（`CL0673-5024-0-53`）
  - [DigiKey `H125591CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DP-2-0-35V-53/7793554)（Active，现货 **`2,862`**，1+ `$1.65`，双向确认官方 Mating Product）｜ JLCPCB `C3653707`（0 库存预购）
- **28 物理焊盘 ↔ 26 逻辑端子核心约束**：
  - 信号焊盘 `1–24`：`0.18 × 0.31 mm`，pitch `0.35 mm`，跨距 `3.85 mm`，内距 `1.18 mm` / 外距 `1.80 mm`（`0.3 A`）；
  - 端部电源焊盘 `25–28`：`0.53 × 0.33 mm`，中心跨距 `5.26 mm`，内距 `1.24 mm` / 外距 `1.90 mm`（`5.0 A`）。高 X 侧 `[25, 26]` 内部一体直通、低 X 侧 `[27, 28]` 内部一体直通、两端 LCP 绝缘；
  - 顶层两排焊盘间强制绘制 `NO CONDUCTIVE TRACE` 禁布区，钢网 `0.08 mm`（80 µm），插拔寿命仅 **10 次**。
  - **BLOCKED 极性红线**：本体 100% 中心对称无防呆键、无 Pin 1 丝印，PR #60/#61 均未新增相机模组原厂 FPC 图纸，因此 `[25, 26]` vs `[27, 28]` 极性归属及 `1–24` 镜像针序继续保持 **`BLOCKED`**，严禁猜测连线。

## 2. 导入 `R10-TEST-J3` 后关闭 PCB1 4 项 `MISSFOOTPRINT` ERC 错误的合规步骤

当用户在云端 `eda_luhqetwc` 完成 PR #60 `EVT1-H03-R9-NOT-FOR-FAB.epro2` 导入并另存为 `R10-TEST-J3` 后，按以下顺序执行（**0 降规则、0 删网、0 虚构封装**）：

1. **关闭 `J3`（`ie284`）ERC 错误**：按结构评审锁定方案 1（导入 `footprint_specs/J3_MillMax_856-10-004-30-051000_LandPattern.json` 建立真实 SMD 封装并绑定至 `J3`）或方案 2（绑定 4P 1.0 mm 尾段焊盘封装），保持 `1=VBUS_5V_USB`、`2=USB_DM`、`3=USB_DP`、`4=GND` 与 `U12 (TPD2E001DRYR)` 完整连接，执行原生 `Import Changes` 上板。
2. **关闭 `BAT1`（`ie226`）与 `SPK1`（`ie447`）2 项外接器件 ERC 错误**：保留二者 BOM 物料属性，将其板端飞线接口以真实 SMD 焊接焊盘/测试点封装承接（参照 PCB3 `M-AUD-R` 的 `TP1–TP5` 模式），合法消除 2 项 `MISSFOOTPRINT`，不关闭 ERC 检查规则。
3. **关闭 `J2`（`ie165`）ERC 错误（严格受 `BLK-TECH-J2` 门禁控制）**：在原理图预建与 `C5577343`（`footprint_specs/J2_Hirose_BM28B0p6-24DS_LandPattern.json`）1:1 对应的 28-Pin 原生符号；**仅在获取相机模组 FPC 图纸并完成低电流四线通断实测后**，方可将 `CAM_AVDD_2V8` 与 `GND` 绑定至实测确认的 `[25, 26]` / `[27, 28]` 组并执行 `Import Changes` 上板，从而将 PCB1 严格 ERC Fatal 由 `4 → 0`、原生网表差异由 `1 → 0`。
4. **持久化验证**：运行原生 ERC 与 DRC，保存工程后关闭并重新打开复测，导出 `R10-TEST-J3.epro2` 与原始日志。
