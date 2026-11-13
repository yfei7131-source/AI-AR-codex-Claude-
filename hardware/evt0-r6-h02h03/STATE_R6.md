# STATE — evt0-r6-h02h03

**NOT FOR FAB.** 可编辑 EVT-0 核心验证板（50×70 mm，4 层），用于台架验证，不是眼镜量产外形。

## 当前板（随每次提交更新）
- PCB SHA-256：见 `evidence/native_r6_s3/input_sha256.txt`（最近一次原生检查输入）
- SCH SHA-256：`81d599e6d107563f43d2521262fd50ffaea25e8457332b169c59d1ca32a142e6`（R6 未改原理图）
- KiCad 10.0.8 原生：ERC 0 错 / 0 警；DRC 0 违规；schematic parity 0；**未连接 51**
- In1 = /GND 实心平面（填充 2891 mm²，仅过孔反焊盘），In2 = /3V3 平面（2867 mm²）；顶部天线禁布区无铜

## 未连接 51 项（原生 DRC 分类）
| 组 | 项数 | 说明 |
|---|---|---|
| 相机 J3（DNP FPC）↔ U1/上拉/去耦/电源选件 | 32 | DVP 数据 8、时钟 2+2、SCCB 4、复位/PWDN 3、电源 CAM_2V8/DOVDD/DVDD 11 |
| 显示 J4（DNP 排针）↔ U1 | 9 | QSPI 预留 + RST/CS/CLK + DISP_PWR_EN |
| USB DP/DM | 8 | J1→U2→U1.13/14，需 90Ω 耦合布线 |
| 音频 UART J7 ↔ R33/R34（DNP） | 2 | |

## 阻断 / 未验证
- 叠层 C1 与 USB W/S 0.22/0.15 是 2D 求解 **估算**（89.9 Ω），需板厂阻抗计算与 coupon。
- 实物、光学 AR、电池、隐私灯物理联动均未实测；相机/光机均 DNP。
- 无制造放行；不得导出 Gerber 作为生产文件。

## 下一步
见 CHANGELOG_R6.md 最新行之后的计划：相机 → 显示 → 音频 UART → USB 差分（每步原生复核）。
