# 验证报告（2026-11-13）
| 项目 | 状态 |
|---|---|
| 原生 ERC | NOT RUN（无 kicad-cli） |
| 原生 DRC / --refill-zones | NOT RUN |
| 覆铜重铺 | NOT RUN；板内 In1/In2 填充为空，须KiCad重铺 |
| 原理图↔PCB 封装ID | 84/84 位号一致（文本比对，非KiCad parity） |
| zy_pcb 自检 | 缺口51、违规0、悬空1（R4既有） |
| PGOOD | 9段+1过孔；对他网最小余量 0.035mm(对 CHG_EN1 过孔)，其余≥0.049mm；孔到孔≥0.335mm |
| U1.41 散热孔 | 12孔0.30mm；孔间净距≥0.69mm；环宽0.15mm |
| J3 GND 过孔 | 4处，过孔对相邻焊盘余量0.328mm；**两条短线与相邻焊盘净距正好=规则0.20mm，零余量**，需原生DRC确认，必要时微调 |
| VBUS/VSYS 新铜 | 对他网最小余量0.05mm；VSYS 长约35mm沿DNP排针J4，只连DNP焊盘 |
| 封装库告警 | 是否消除未知（需原生） |
自检数字来自 zy_pcb，不等于 KiCad DRC。**不得出Gerber，非生产放行。**

## 第三轮更新
原生 ERC/DRC/重铺 仍 NOT RUN（命令退出码2，见 evidence/native_NOTRUN_r3）。USB差分：阻断（USB_DIFF_BLOCKERS.md）。悬空线=R4既有GND短线(130.25,118.0)。PCB未改，不得出制造文件。

## 第四轮更新（S6，PCB c0f1ca5c）
| 项目 | 状态 |
|---|---|
| 原生 ERC / DRC / 覆铜重铺 / parity | **NOT RUN**（无KiCad；evidence/native_NOTRUN_S6，退出码2） |
| zy_pcb 自检（非原生） | 缺口51、违规0、悬空 **0**（r3为1） |
| S6 | 删除GND悬空短线 40b55a19（-8行/-157字节），D1.2仍在唯一GND簇；见 evidence/step6_gnd_stub |
| 未变更的待原生复核项 | J3短线零余量；PGOOD↔CHG_EN1过孔余量0.035mm；VSYS≈35mm（仅连DNP焊盘J4.2）；封装库告警 |
模型结果不等于 KiCad DRC。**不得出Gerber，非生产放行。**

## 第五轮更新（H02/H03，PCB c8aceeaf）
| 项目 | 状态 |
|---|---|
| 原生 ERC / DRC / 覆铜重铺 / parity | **NOT RUN**（无KiCad；evidence/native_NOTRUN_h02_20261113，退出码2） |
| zy_pcb 自检（非原生） | 缺口 51→28、违规0、悬空0；UUID 1694 唯一 |
| J3 GND 短线 | 实测净距恰=0.200=规则（0.5排距×0.3电源最小线宽几何强制；缩宽违DRU、移孔不改y向净距）→ 保留，原生DRC复核项 |
| PGOOD | 最差两段对 CHG_EN1 过孔净距0.185（规则0.15，余量+0.035）；走廊总余量0.084，无有效扩距空间 → 保留 |
| S5 VSYS/VBUS | 15项新铜最小余量+0.05；/VSYS /VBUS 缺口0 |
| 新增布线 A–E | 23缺口连通（17网全通+CAM_DOVDD/DISP_PWR_EN部分）；drc_lite(new)=0、dangling(new)=0 |
| CAM_2V8 手动绕行 | --dry 干跑14项违规（GND/PWDN/SIOD阻挡+穿越J3焊盘）→ 确认拥堵，未写入任何铜 |
| 封装库告警 | 是否消除未知（需原生） |
自检数字来自 zy_pcb，不等于 KiCad DRC。**不得出Gerber，非生产放行。**
