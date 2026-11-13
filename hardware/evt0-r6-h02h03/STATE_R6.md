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
