# EVT-0 R9 PCB 研发报告（嘉立创EDA专业版）

日期：2026-11-15 ｜ 分支：hardware/evt0-r9-pcb-20261115 ｜ 基线：PR#11 commit f1eee75c（R8）

## 0. 定位声明
- EVT-0 是**验证板**，不是最终 40g 镜腿 PCB；本板不投板（NOT FOR FAB）。
- 原生验证未全绿前，不宣称可打样。本轮结束时的门禁状态见 §7。

## 1. 本轮输入基线（已核对，未重复开发）
- R8 原理图：84/84 器件、273 脚连线、对 R7 网表 274/274 对账 0 错配、原生 DRC 0/0/0。
- R8 PCB：84/84 布局合法（layout-lint 0 short/0 overlap/0 off-board）、板框 60×80mm、4 层叠层。
- 视觉重叠标签：纯外观遗留，不影响电气，R8 已存档。

## 2. 板框 60×80mm 偏差说明（EVT-0 合理化）
- R7 KiCad 板框为 50×70mm；R9 实测 J4（PZ2.54-1X12P-ZW）+ U1（ESP32-S3-WROOM）+ J3（FH12-24S FPC）在合法间距下无法容纳。
- EVT-0 验证板目标是验证电气与固件链路，非镜腿外形；扩为 60×80mm 已锁定。最终 40g 镜腿 PCB 需重新进行结构设计（P0 阻断项，见 §8）。

## 3. 叠层与电源架构
- 叠层：Top SIGNAL / In1(15) PLANE(GND) / In2(16) SIGNAL(3V3 正片铺铜) / Bottom SIGNAL。
- **3V3 铺铜失败根因（已查明并解决）**：easyeda 铺铜的 per-layer 插入优先级必须连续且从 0 开始；显式 `--priority 0` 后一次成功（pour id 20895127e0849450）。
- GND 负片内电层：layer 15，pour id b41389d09a6003ff。
- 本轮 GND 缝合收尾后，GND 网未连接对象 4 → **0**（原生 DRC 确认）。

## 4. USB 差分阻断立场（红线，未布线）
- R7 DRU 要点：USB2 90Ω 差分 W0.22/S0.15 仅为估算，**未经板厂叠层与阻抗计算确认**；回流路径未验证。
- 本轮自动布线两次将 USB_DP/USB_DM 纳入布线，均已全部 rip-up 清零并复核为 0。
- USB_DP/USB_DM 各 5 个对象保持未连接并列入未连接清单，直到板厂叠层/阻抗/回流三要素齐备。

## 5. 布局整改
- C17 移出 J1 焊盘区至相机排阻区 (400,1500)；R10 避让 J1 槽口；J6 移至板右缘 (2150,1500) rot90 重锁定。
- 整改后 layout-lint：84 件 0 short / 0 overlap / 0 off-board。

## 6. 布线执行记录
1. route-short（130 段）+ route-power（54 段+12 孔）；USB 两次被布线器纳入，均 rip-up 清零。
2. 官方 autoroute 分批（1–7 网/批，大网批必超时且结果不持久）：完成 DISP 全部、EN、CC2、CAM_Y2-Y9、CAM_SIOD/SIOC/XCLK/PCLK/PWDN/RST_N/VSYNC/HREF、CAM 电源、VBAT_ADC、VBUS、VBAT、VSYS、CHG_* 部分、U0RXD、BAT_NTC 等，720 条走线全部 L1/L2。
3. DRC 间距整改：删除 15 条违规走线 + 3 个问题过孔（263→171）。
4. **GND 缝合与间距清零战役（drc_r9_15→r9_17）**：
   - EPAD（U3_17）3×3 热孔阵：左/中列 6 孔与 VBAT(L2 x663.94)、CHG_EN1(L2 x690.2) 纵向干线间距 4.7–4.8mil（<6）→ 删除 6 孔，保留右列 (724,426/450/474) 3 孔，EPAD 保持接通。
   - U3_5(GND)：南侧被 BAT_NTC L2 干线(y306.3)、VBAT L2 干线(y337.59)、CHG_EN1 过孔(690.2,360.9)、BAT_NTC 过孔(640.9,509.5) 四面封死，任何合规过孔均无解 → 改为 L1 直连 EPAD：pin5 焊盘 (670.5,390.9) 上行 34.1mil 接入 EPAD 铜皮（焊盘间隙 11.85mil、同网、两侧间距 ≥8.85mil）。
   - J3_2(GND)：原过孔 (687,2494.75) 压在 CAM_VSYNC L2 干线上 → 改 L1 两段短线 (686.7,2437.5)→(686.7,2402)→(800.9,2290.2)，沿 FPC 焊盘排与 CAM_SIOD 对角线之间的走廊（≥9.2mil）搭接既有已连通 GND 过孔 (800.9,2290.2)。
   - J3_15(GND)：原短线+过孔压在 CAM_PWDN L1 干线上；下方走廊 CAM_Y7/CAM_Y8（w9.88）夹道仅 29.5mil，容不下合规 24mil 过孔 → 将 CAM_Y7/CAM_Y8 在 y[2150,2182] 段颈缩至 6mil（符合最小线宽规则），并改用 DRU 下限 20/12mil 过孔 (430.8,2166)，两侧间距 6.7mil 达标。
   - R10_2(GND)：原过孔 (520,270) 0mil 撞 J1 VBUS TH 焊盘 B4A9 及壳体槽口 → 移至 (501,251)，与 VBUS 焊盘/孔/槽口间距 ≥6.5mil。
5. 每步后均 pour-rebuild → save → doc reload → 原生 DRC，证据见 evidence/fix_gnd_clearance/。

## 7. 原生验证结果（终值）
- DRC 进程（原生 `pcb drc`，证据 evidence/drc_r9_*.txt）：
  - 间距违规：263 → 201 → 191 → 171 → 28（r9_15）→ 9（r9_16）→ **0（r9_17）**
  - 未连接对象：49（R8 基线）→ 47（r9_17，17 网）→ 43（r9_22）→ 41（r9_25）→ **40（r9_28，15 网）**，其中 USB_DP/USB_DM 占 10（阻断项）。
  - R9-S2（drc_r9_18→22）：VSYS 双断点经 via-hop（2 过孔+6 走线，绕开 CHG_EN1 L2 干线与 C3_2/GND L1 围栏，最小间距 6.3mil）清零；CAM_SIOC 51.2mil 同轴缺口 L1 桥接清零。中途两轮违规（drc_r9_19/20 共 8 项）全部拆除重布后收敛，证据 evidence/fix_vsys_camsioc/。
  - R9-S3（drc_r9_23→28）：VBUS 主岛↔TP1 岛 L1 桥接（94.6mil，w19.685 同宽）；U0TXD 主干 U1.37↔J6.3 贯通（4 过孔 6 走线，net-path PASS）；CHG_CE_N 尝试产生 7 项违规后完整拆除复原。证据 evidence/fix_vbus_u0txd/。
- **终值：Clearance 全类 0（Track/Pad/Via/Hole/Slot 全部清零）；Connection Error 40 对象 / 15 网。**
- 未连接清单：evidence/UNCONNECTED_R9.md（extract_unconnected.py 生成）。
- 原理图↔PCB parity：274/274（269 精确 + 5 结构性）、0 错配，与 R8 基线一致（evidence/parity_r9.txt，IR：conn_r9_final.json，289 脚 0 漂移）。
- 制造规则：全程未降低；当前 DRU 存档 evidence/rules_r9_final.json（最小过孔 0.5/0.3mm、孔到孔 0.3mm、铺铜间距 0.254mm）。
- 相机隐私联锁、电池保护、12 件 DNP 均未改动。

## 8. 制造风险与阻断清单
- [阻断] USB 90Ω 差分：叠层/阻抗/回流未确认，10 对象未布线。
- [阻断] 最终镜腿 PCB：60×80 EVT 板非产品外形，需独立结构/光学/配重审查（鼻梁、耳后、太阳穴配重 P0）。
- [阻断] 13 网 30 对象未连通（USB 之外，见 UNCONNECTED_R9.md），逐网根因见 evidence/fix_vbus_u0txd/README.md：CHG_PGOOD_N/CHG_CE_N/CHG_ISET/CHG_ILIM/CHG_TD（U3 周边 VBUS/VBAT/VBAT_ADC/GND 围栏互锁，多轮尝试无合法过孔位）、CAM_PWR_EN（U1_15 被 STRAP46/DISP_PWR_EN/CAM_2V8 合围）、U0TXD 两分接（VBAT_ADC 整板高墙等六重封锁，主干 U1.37↔J6.3 已通）、CAM_DVDD（0 铜，需独立电源走线轮次）、CAM_Y6、MIC_SCK/SD/WS（跨板长线，布线器无路径）。均不强行放行。
- [阻断·封装] J1 VBUS TH 焊盘 A4B9/B4A9：钻孔 Ø1.417mm 覆盖 0.6×1.3mm 焊盘，有效焊环为零，走线穿洞无铜可接。需按数据手册修订封装焊环，列入下一轮。
- [风险] 孤铜残段（U0TXD R33_1 侧、VBUS、CHG_CE_N 过孔）待连网或清除，已在清单标注。
- [风险] J3_15 借道处 CAM_Y7/CAM_Y8 存在 32mil 长 6mil 颈缩段，已合规但建议下轮评估是否加宽回路。
- [待办] 丝印压焊盘外观项（silk-over-pad WARN），不阻断电气。

## 9. 工程可重开验证
- 全部修改后执行 `pcb save` → `doc reload`（saved → closed → reopened）→ 回读铺铜/走线/布局一致；reload_r17.json 记录 "✓ reloaded pcb 6e4acfce1bdee052"。
- 工程：ZY-AIAR-EVT0-R8-验证板（uuid 6757096b0d67c0879a663e8d58216b175a02a33d4d00c1c0bdeda07b8c434b64），嘉立创EDA专业版 4.1.97 + easyeda-agent v1.17.0。
