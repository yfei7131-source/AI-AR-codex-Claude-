# EVT-1 H03 R9-W4-PCB1 接口、封装与装配空间核查状态报告（STATE — NOT FOR FAB）

- **日期**：2026-11-24
- **继承基线**：[PR #60](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/60)（`a825953d62603624d2ad5105d223d07b87ba8d05`）、[PR #61](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/61) 与本次正确附件 `R9-Gemini-W4-PCB1.zip`（SHA-256：`85897dc6f8e62e3044a60a8a773cc9d63462cd42c969b1ebb14b0d38f34cd907`）
- **PCB1 真实基线核对（100% 实测匹配）**：
  - 器件总数：**`118`**（`PCB1-copper.json` 实测 118，全部导出至 `reports/PCB1_118_COMPONENTS_INVENTORY.csv`）
  - 精确 8 点异形板框：全长 `46.00 mm`，前端（`Y = 0–4.2 mm`）宽 `5.80 mm`、中前宽段（`Y = 4.2–14.0 mm`）宽 `8.20 mm`、镜腿中尾段（`Y = 14.0–46.0 mm`）宽 `5.80 mm`；6 层板，`830` 走线、`97` 过孔、`6` 铜皮区
  - 原生严格 ERC：`4` 项 `MISSFOOTPRINT`（`J2` `ie165`、`J3` `ie284`、`SPK1` `ie447`、`BAT1` `ie226`）
  - 原生严格 DRC：`334 Connection Error + 1 Netlist Error`（`0` 间距/短路违规）
- **本轮核心成果（离线真实数据研发 + 可导入封装 + 零碰撞坐标）**：
  1. 扫描全板 118 器件、830 走线与 97 过孔，证实 **`Y = 36.20–45.75 mm` 顶层（L1）为 PCB1 唯一零碰撞可用装配窗**（底层 L2 已被 `MK1` `[0.55, 41.20 -> 4.46, 45.46] mm` 与 `U19/R15/R17` 占用，故尾段严禁使用任何 DIP 通孔件；前端 `Y < 6.5 mm` 为 `ANT1` 射频天线净空区，严禁放置金属连接器）。
  2. 生成 3 个可直接导入 EasyEDA Pro 的标准 `.kicad_mod` 真实封装（`J3_MillMax_856-10-004-30-051000.kicad_mod`、`J3_SubPCB_4P_1p0mm_SMD_Pad.kicad_mod`、`J2_Hirose_BM28B0p6-24DS_2-0p35V53.kicad_mod`），并输出带主工程安全锁的 EasyEDA Pro 增量脚本（`scripts/easyeda_pro_r10_j2_j3_delta.js`）与可复现 2D 碰撞验证脚本（`scripts/pcb1_118comp_space_audit.py`）。
  3. 核实 PCB1 已内置 `U12`（`TPD2E001DRYR` ESD，L2 `(0.92, 10.14) mm`）、`U22`（`TPS2553DRVR` 限流开关，L1 `(1.59, 23.51) mm`，配 `R38 = 61.9 kΩ`）及 `TP2/TP6/TP7` 飞线测试点；提示 `U12` 距尾段 `J3` 约 `31 mm`，后续布线应移近 `J3`（`≤3 mm`）。
- **维持 `BLOCKED` 的未实测/受限项**：
  - `BLK-TECH-J2`：缺摄像头模组原厂 FPC 图纸与四线通断实测，`J2` 端部 `[25, 26]` vs `[27, 28]` 极性与 `1–24` 针序维持 `BLOCKED`，禁止猜测连线；
  - `BLK-TECH-J3`：缺左镜腿尾段 3D STEP 壳体壁厚与磁铁腔体图纸，以及 `856-10-004-30-051000` 独立温升与防反接/防汗液倒灌实测；
  - `BLK-ENV-CLOUD`：云端 `eda_luhqetwc` 尚无 R9 工程且远程浏览器禁止本地文件导入，未改动任何主工程、未降低任何规则。
