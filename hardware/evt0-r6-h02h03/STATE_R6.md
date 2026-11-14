# STATE — evt0-r6-h02h03（2026-11-13）

**NOT FOR FAB.** 可编辑 EVT-0 核心验证板（50×70 mm，4 层），用于台架验证，不是眼镜量产外形。

## 当前板
- PCB SHA-256：`3b2838c1eb73d2a4792aeba39a50d8b2c46169138f654bcf2ea0773262c1e39a`（KiCad 重铺后板，重铺幂等）
- SCH SHA-256：`81d599e6d107563f43d2521262fd50ffaea25e8457332b169c59d1ca32a142e6`（R6 未改原理图）
- **KiCad 10.0.8 原生**（`evidence/native_r6_final/`，`inputs_unchanged=True`）：ERC 0 错 / 0 警；DRC 0 违规（含 warning）；schematic parity 0；**未连接 49**
- In1 = /GND 实心平面，In2 = /3V3 平面；顶部天线禁布区无铜

## 本轮完成（详见 CHANGELOG_R6.md）
S3b 修正 S3 遗留两处违规 · S4 音频 UART 桥 R33/R34 移至 J7（51→49）· S5 走廊 GND/3V3 表层线改过孔下平面（103.5→19.0 mm，无 via-in-pad）。每步原生复核。

## 未连接 49 项
| 组 | 项数 | 状态 / 下一步 |
|---|---|---|
| USB DP/DM | 8 | 方案已推导（`USB_R6_DESIGN.md`）：对调 USBLC6 通道消除手性交叉、J1 内侧 A6 单次 B.Cu 跳线；先局部重布 U2.5 VBUS、CC2 过孔、U2.2 GND 及 B.Cu 遗留 CHG_ISET/CAM_3V3/VBAT/CAM_PWR_EN 阶梯线（需电源路径评审） |
| 相机 J3（DNP FPC） | 32 | 与 USB 共用 U1 左列走廊，**须在 USB 落地后再布**，避免占用 USB 通道 |
| 显示 J4（DNP） | 9 | U1↔J4 走廊被 R3 遗留阶梯线封死（F.Cu: /VBAT_ADC x=140.25、/MIC_WS x=135.5、/U0TXD x=137；B.Cu: /MIC_SCK、/MIC_WS 斜线）。需先拆除重布；自动布线最佳仍 ~233 mm/18 过孔且不全通，不接受 |

## 阻断 / 未验证（不得写成完成）
- 叠层 C1 与 USB W/S 0.22/0.15 为 2D 求解**估算**（89.9 Ω），需板厂阻抗计算与 coupon。
- 实物、光学 AR、电池、隐私灯物理联动均未实测；相机/光机均 DNP。
- 本轮未推进：器件选型冻结、FPC、功耗/散热实测、双目 AR 光学集成、40 g 质量目标（仍以 `hardware/evt1-id/` 现有输入为准）。
- 无制造放行；不得导出 Gerber 作为生产文件。远端推送：本机无 GitHub 凭据，已提供 git bundle/patch。

## 工具（R6 新增）
`r6_native.py`（原生检查）· `r6_render.py`（kicad-cli PDF→PNG 层图）· `r6_route.py`（网格搜索 + 精确几何平滑）· `r6_s3b_fix.py` · `r6_s4_uart_move.py` · `r6_s5_plane_cleanup.py`（禁止 via-in-pad）· `near.py`（区域铜查询）。

---

# R7 增补（2026-11-14，分支 hardware/evt0-r7-usb-20261114）

**NOT FOR FAB.** R7 为 USB 专项，详见 `USB_R7_ADDENDUM.md`。本机无 KiCad/kicad-cli，原生 ERC/DRC/重铺/parity 全程 **NOT RUN**（`evidence/native_r7_*/`），未以自定义自检冒充原生验证。

## 当前板（R7-S1 后）
- PCB SHA-256：`13dc5652658756b473e7167dbb3d5a436e32ef6559a483904cb897ff6a461306`
- SCH SHA-256：`3de738b3919f08e8f8a7d31f436883947c3454ab17f3abb35c95763c278f0761`
- R6 原板快照：`evidence/r7_baseline_snapshot/`（PCB `3b2838c1…`、SCH `81d599e6…`）
- 离线自检（`evidence/selfcheck_r7_final.json`）：**未连接 49**、违规 0、悬空 0；原生：**NOT RUN**

## R7 结果
- **S1 完成**（commit `dffcf2c`）：USBLC6 U2 通道对调（U2.1/6→/USB_DM 西列、U2.3/4→/USB_DP 东列），消除手性交叉；原理图 4 label、PCB 焊盘网、netlist.csv、ELECTRICAL_REVIEW 同步；gaps 49 不变、违规 0。
- **S2 阻断**（`evidence/r7_s2_gnd_blocked/`，PCB 未写入）：设计文档提议的 U2.2 GND 过孔位 (124.5,118.5) 干跑报 8 项违规（对 U2.5 0.175<0.2、对 TP10.1 0.060、与 /CHG_PGOOD_N 短路 −0.046）；x 123–126/y 117–121 网格穷举零可用位——与 PGOOD/TP10 构成几何死锁，整改需移动充电区信号，无原生 DRC 环境不做。
- **S3 跳过**（仅 DP 布线时有意义）；**S4 阻断**（电源路径评审事项）；**S5 阻断**：GND 链尾段封死 DM→J1 B7/A7 全部绕行（<0.1 mm），且叠层 C1/90 Ω 为 2D 估算未获板厂确认，按红线不强行布线。
- **USB 8→0 本轮未达成，总未连接维持 49。**

## 下一轮候选（需 KiCad 原生环境）
① 微调 /CHG_PGOOD_N 局部段让出 (124.5,118.5) 过孔位（原生 DRC + 电源评审）；② U2 器件级重排；③ 板厂确认叠层与 90 Ω 后按 `USB_R6_DESIGN.md` 第 3 节布线。

红线：DRU 未降、隐私联锁/电池保护/DNP 未动、充电路径未改、无制造放行。
