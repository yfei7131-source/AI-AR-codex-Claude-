# easyeda-agent 验收报告（2026-11-14）

## 连接状态（easyeda health，证据 01_health.json）
- daemon v1.17.0 @ 127.0.0.1:60832 ✓
- 连接器 v1.17.0（1 窗口，electron，JLCEDAPro 4.1.97）✓
- versionGate ok（CLI/daemon 同版、connector major.minor 兼容）✓
- hostCompatibility ok（4.1.97 满足 V4 主线基线，推荐 ≥4.1.60）✓

## 工程
- 名称：`New Project_2026-11-14_14-30-17`（projectUuid `0fb3d3be…`）——独立新建空工程，非 R7 资产
- 文档：schematic P1 ×2（活动 7960bd579a141949 / 1c4cc46f72ecf8cf）、PCB1（dbf0342ee1b2d9a4）
- 因工程为空，实例化标准电路块 `block.ams1117_ldo_3v3` 作为受试电路（证据 06_block_apply.json）

## 实际修改记录
1. `sch block-apply block.ams1117_ldo_3v3`：放置 U1=AMS1117-3.3(C6186)、C1=100nF/0402(C1525)、C2=10µF/0805(C440198)、C3=22µF/0805(C45783)，布 GND/+5V 内部连线
2. 修复块自身 reconcile 缺陷：`sch connect` 补接 C1.1、C3.1 → +3V3（几何守卫拒绝自动方向，按实测引脚朝向 C1.1 up/6、C3.1 down/8 显式短桩）
3. `pcb import-changes` 同步 4 器件到 PCB1；`pcb outline-round --rect=-20,-785,742,-135` 建 762×650 mil 圆角板框（4 原生圆弧、已锁定）
4. 可恢复位置调整：C2（`253e5365d5ee4f4c`）(+50,+50) mil：(80.307,-684.878) → (130.307,-634.878)，回读确认；随后 (−50,−50) 恢复原位，回读确认 (80.307,-684.878)（证据 17_move_c2.json、19/20）

## 验证结果
| 项 | 结果 | 证据 |
|---|---|---|
| 原理图读取 | 4 器件、逐引脚、3 网络（+5V/+3V3/GND）、10 连接；bridge-check 0 问题 | 08/10_sch_connectivity.json、07_bridge_check.json |
| PCB 读取 | 4 元件坐标、板框中心线 762×650 mil、2 铜层（Top/Bottom SIGNAL）、3 网络、实时规则（clearance 5.98mil 等） | 12/13/14/15/16 |
| 保存→重载→回读 | 两次 `doc reload` 均「saved → closed → reopened」，移动与恢复后坐标持久、uniqueId 稳定 | 18/20_doc_reload*.txt、19 |
| 原生 SCH DRC | **通过，0 违规** | 22_sch_drc.json |
| 原生 PCB DRC | 运行成功，`passed:false` —— **10 项 Connection Error / No Connection**（GND×4、+3V3×4、+5V×2 焊盘未布线连接）；属未布线板的预期如实结果，非几何/规则违规 | 21_pcb_drc.json |

## 结论
读取、写入、几何守卫、保存、重载、回读、原生 DRC 全链路在嘉立创EDA专业版 4.1.97 上验证通过；
板级未布线导致的 10 项未连接为当前真实状态（本工程为一次性测试工程，可不处理）。
未触碰任何 R7/KiCad 正式工程。
