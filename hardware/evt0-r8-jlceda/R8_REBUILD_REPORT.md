# EVT-0 R8 — 嘉立创EDA 重建完成报告（H03-R8 收尾）

日期：2026-11-14 ｜ 执行：Kimi（首席PCB硬件工程师）｜ 工程：`ZY-AIAR-EVT0-R8-验证板`（嘉立创EDA专业版 V4.1.97）

## 结论（真实状态，未虚构）

**R7 KiCad 工程已在嘉立创EDA专业版完成 typed 重建，电气网表 274/274 逐脚对账一致（0 错配），原生 schematic DRC 0 fatal / 0 error / 0 warn。**

- 本板是 EVT-0 **验证板**，不是最终镜腿 PCB；双目 AR 显示与 40g 整机目标不变。
- **NOT FOR FAB**：未做板厂叠层/阻抗工艺确认前不得投板。R7 侧 USB 差分/电源路径阻断立场不变（见 `hardware/evt0-r6-h02h03/USB_R7_ADDENDUM.md`）。
- 12 件 DNP 安全配置保持 DNP，隐私联锁/电池保护未触碰。

## 基线核验（防旧版误用）

| 项 | 值 |
|---|---|
| R7 源工程 | `hardware/evt0-r6-h02h03/evt0_core/`（PR#8, commit 3c8b5823） |
| PCB SHA256 | `13dc5652…`（与任务给定一致） |
| SCH SHA256 | `3de738b3…`（与任务给定一致） |
| EDA 工程 uuid | `6757096b0d67c0879a663e8d58216b175a02a33d4d00c1c0bdeda07b8c434b64` |
| 原理图页 P1 uuid | `7a4e9091b268cd79` |

KiCad 10 直导已被证实阻断（4.1.97 导入器不支持，证据 `evidence/r8_jlceda_probe/`），本工程为**按 BOM/网表逐件重建 + 对账**，非文件转换。

## 完成内容

1. **器件 84/84**：全部放置并与 R7 BOM 逐件一致（`sch list` 核对 missing=[] extra=[]）；12 件 DNP 写入自定义属性。27 项 LCSC 选型映射留证（`lcsc_mapping.csv`；唯一偏差：TP 用 C9900000335 SMD PAD 代替 D1.0mm 测试点）。
2. **布局**：11 模块 autolayout + 手工修整；layout-lint 0 重叠 / 0 出图纸。
3. **连线**：273 脚全部落位。本轮（R8 收尾）完成最后 16 脚：U1:4/5/8/15/19/21/22/23、R23:1/2、R24:1/2、J7:1/2/3、D3:1/2、C18:1、R16:1、J3:12、TP9:1、TP1:1 及 C11/R23/R24/D3/J7/TP9/TP1/U3/R14/R15 十处器件级移位让位。
4. **16 个合法 NC 脚**（J1:A8/B8、J3:1/23/24、SW1:3/4、SW2:3/4、U1:28/29/30、U3:14、U4:4、U5:4、U6:4）已打原生非连接标识，与 R7 网表一致（R7 中这些脚本就不布线）。
5. **事故修复留痕**：本轮修复 2 起假失败/守卫漏检造成的缺陷——GND↔CAM_1V2 桥接短路（R16:1 桩线落到 GND 横线上，已整树删除分网重连并复检为 0）；U1:21 旗标脱桩致网络漂为 $1N417（已删孤儿桩旗、重挂 CAM_PCLK_R，恢复 R7 一致性）；清理 4 个重复旗标。
6. **校验门（`sch gate` 原始输出：`evidence/r8_rebuild_final/gate_final.json`）**：
   - layout-lint **PASS**（0 体重叠 / 0 出图纸 / 2 过近告警）
   - check **PASS**（0 error/fatal；244 条 warn/info 全部为标签视觉重叠与图签区侵入）
   - bridge-check **PASS**（0 桥接 / 0 孤儿，272 线树）
   - 原生 drc **PASS（0 fatal / 0 error / 0 warn / 0 info）**
   - clusters **FAIL（外观项）**：104 处标签/标志视觉重叠。`sch destagger` 两次因连接器过载基线读取超时被安全拒；属可读性遗留，不影响电气与制造数据。

## 网表对账（`parity_final.py` / `parity_final.txt`）

- R7 网表 274 条：OK **269**、错配 **0**、结构性映射 **5**（#FLG1/2 为 KiCad 电源旗伪元件；J1:SH→EDA J1:1-4、J2:MP→J2:4/5、J3:MP→J3:25/26，8 个机械焊盘在 EDA 侧全部正确落在 GND）。
- 保存→关闭→重开→回读 connectivity：273 连接逐脚一致（`conn_verify.json`）。

## 产物（artifact，SHA256 见提交记录）

| 文件 | 说明 |
|---|---|
| `20261114-224209-schematic_netlist-2a0ab673.enet` | EDA 原生网表导出 |
| `20261114-224339-schematic_bom-c2e9e707.csv` | EDA 原生 BOM 导出 |
| `conn_verify.json` | 重载后 connectivity IR（对账基准） |
| `gate_final.json` | 校验门原始输出 |
| `parity_final.py/.txt` | 对账脚本与结果 |
| `lcsc_mapping.csv` | 选型映射 |

## 遗留项（如实）

1. 104 处标签视觉重叠待消（`sch destagger`，需连接器空闲时执行）；不影响 DRC/网表/制造。
2. PCB1 为空白板：布局布线未开始；USB 差分需板厂叠层+90Ω 阻抗确认后方可布线（延续 R7 阻断）。
3. TP1:1 VBUS 由 power 类旗标重挂（原为 netflag），仅图形差异，网络一致。
4. 嘉立创EDA 原生 PCB DRC 尚未有对象可跑（PCB 为空）。

## 复现路径

easyeda CLI v1.17.0 + daemon + EDA 连接器；路由 `--project "ZY-AIAR-EVT0-R8-验证板"`。校验：`sch gate`；对账：`python r8_rebuild/parity_final.py`（输入 `conn_verify.json` 与 R7 `netlist.csv`）。
