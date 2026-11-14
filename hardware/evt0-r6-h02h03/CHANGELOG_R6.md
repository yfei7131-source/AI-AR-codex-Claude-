# evt0-r6-h02h03 变更日志

基线：R5 S0–S6 r4（PR#5 head `46150db`，PCB `c0f1ca5c…`，SCH `81d599e6…`）。`hardware/evt0-r5-rework/`、`evt0-r3/`、`evt0-r4-review/`、`evt0-r5-experimental/` 均只读未改。
远端 `hardware/evt0-r5-s7-r5-20261113`（acaaf31，S7）只改标题栏与 via 0.25→0.30，R6 已覆盖该内容，未合并。

所有原生结果均为 **KiCad 10.0.8 `kicad-cli`** 在临时副本上实跑（`tools/r6_native.py`），`inputs_unchanged=True`。
zy_pcb `selfcheck` 仅为辅助，**不是原生 DRC**。

| 步骤 | 改动 | 原生 ERC / DRC / parity / 未连接 | 证据 |
|---|---|---|---|
| S0 | 复现 R5 S6 r4 原生基线（In1/In2 首次真实重铺） | 0/0 · 0 · 0 · 51 | `evidence/native_baseline_S6_r4/` |
| S1 | `.kicad_pro` 网类过孔 0.25/0.5 → 0.30/0.6（仅提高）；USB 类 W/S → 0.22/0.15 | — | `tools/r6_netclass_fix.py` |
| S2 | 插入候选叠层 C1（1.0 mm 4L，F.Cu/0.2104 mm 7628 PP εr4.4/In1 GND）；DRU 加 USB 90Ω 候选、via_count≤2、diff_pair_uncoupled≤3 mm | 0/0 · 0 · 0 · 51 | `evidence/usb_stackup/sweep.json`、`evidence/native_r6_s2_stackup_pre_s3/` |
| S3 | `tools/r6_pi_margins.py`：J3.2/J3.15 GND、/CHG_PGOOD_N、/VSYS 东走廊重做。**脚本在 `P.save()` 之后自检断言失败**（板已写入、证据未写） | 未单独运行 | 自检失败项见 S3b |
| S3b | `tools/r6_s3b_fix.py` 修正 S3 两处缺陷：① J3 GND 0.20 mm 颈缩违反 Power ≥0.30 mm → 恢复 0.30 mm 单段（与 0.30 mm 焊盘同高，对邻脚间距 = 封装自身 0.20 mm 焊盘间隙 = Power 间距 0.20，属 FH12 0.5 mm 间距固有，不放宽规则）；② /CHG_PGOOD_N 出线距 /CHG_EN1 过孔 0.100 mm（需 0.15）→ x=134.30 出焊盘（距过孔 0.227、距 U3.8 GND 0.288），U3.8 下方移至 x=134.45（距过孔 0.30），45° 进新过孔 (133.80,118.45)（距 B.Cu /VBAT 0.25）。/VSYS 东走廊 x=148.60（距 J4/J5 焊盘 0.40 mm）沿用 S3 | **0/0 · 0 · 0 · 51** | `evidence/step_r6_s3b_fix/`、`evidence/native_r6_s3/` |
| S3c | 标题栏 rev `R6-S3b`，注明 NOT FOR FAB、原生已跑、USB 未布、联锁与电池保护未改；采用 KiCad 重铺后的板作为工作板（重铺幂等：重铺前后 SHA 一致 `4efbde7f…`） | 0/0 · 0 · 0 · 51 | `evidence/native_r6_s3/`、`evidence/render_r6_s3/` |
| S4 | `tools/r6_s4_uart_move.py`：DNP 音频 UART 桥 R33/R34 自板顶 (y≈71) 移至 J7 旁（R33 (131.6,97.5) 0°，位于 J6/J7 courtyard 间 1.4 mm 间隙；R34 (137.6,102.0) 270°）。删除仅通往旧 R34.1 的 U0RXD 分支（5 段+2 过孔，否则成悬空短桩）；新增 11 段 0.2 mm 短线。AUD_UART_TX/RX 由需纵穿全板（各 ~37 mm、3–4 过孔，且封死 U1→J4 通道）变为 <5 mm 本地连接。首版位置原生报 3 处 courtyard 重叠，已改方向/位置后复核 | **0/0 · 0 · 0 · 49** | `evidence/step_r6_s4_uart_move/`、`evidence/native_r6_s4/` |
| S5 | `tools/r6_s5_plane_cleanup.py 110 85 128 117`：USB/相机走廊内 GND/3V3 表层长走线改为就近过孔下平面（In1 GND / In2 3V3）。拆除 GND/3V3 段/孔 47+（含越界后悬空段迭代清除），按 plane 模式为每个失联焊盘簇加最短引出线+过孔；**禁止 via-in-pad**（过孔距任何 SMD 焊盘 ≥0.05 mm）。表层 GND/3V3 铜 103.5 mm → 19.0 mm，新增 23 过孔，最长引出 ≤1.3 mm。充电/电池保护区（x>128）未触及。原生确认 23 过孔均经重铺平面真实连通 | **0/0 · 0 · 0 · 49** | `evidence/step_r6_s5_plane_cleanup/`、`evidence/native_r6_s5/` |

注：此前名为 `native_after_s3/` 的目录其输入 PCB 哈希为 S3 之前的板（`6dbc5dc8…`），已更名为 `native_r6_s2_stackup_pre_s3/`，避免误读。

**S4 后发现（未改，列为下一项整改）**：U1 右列 ↔ J4 走廊被 R3 遗留 0.25 mm 网格阶梯走线占满——F.Cu 有 /VBAT_ADC x=140.25（y 70–93）、/MIC_WS x=135.5、/U0TXD x=137 三道竖墙；B.Cu 有 /MIC_SCK、/MIC_WS 长阶梯斜线 (134.75,75.5)→(145.75,99.25)。显示 9 项在此条件下自动布线最好结果仍为 ~233 mm/18 过孔且不全通，判定不可接受；需先拆除重布这些遗留线（独立步骤、原生复核）再布显示总线。

---

# R7 增补（2026-11-14，分支 hardware/evt0-r7-usb-20261114，NOT FOR FAB）

本机无 KiCad/kicad-cli，原生 ERC/DRC/重铺/parity 全程 **NOT RUN**，未以自定义自检冒充原生验证。

| 步骤 | 改动 | 原生 ERC / DRC / parity / 未连接 | 证据 |
|---|---|---|---|
| R7-S1 | USBLC6 U2 通道对调消除手性交叉（commit `dffcf2c`）：原理图 4 label 文本互换；PCB U2.1/6→/USB_DM、U2.3/4→/USB_DP（net id 不变）；netlist.csv 与 ELECTRICAL_REVIEW 同步。数据手册 ST DS4260 核对：1/6=I/O1、3/4=I/O2 内部短接，双向对称，对调电气等价 | NOT RUN（`evidence/native_r7_s1/`）· 离线自检 49 · 违规 0 · 悬空 0 · U2↔netlist parity OK | `evidence/selfcheck_r7_s1.json`、`evidence/r7_baseline_snapshot/` |
| R7-S2 | U2.2 GND 整改**阻断，PCB 未写入**：(124.5,118.5) 过孔干跑 8 项违规（U2.5 0.175<0.2、TP10.1 0.060、/CHG_PGOOD_N 短路 −0.046）；x123–126/y117–121 网格穷举零可用位，与 PGOOD/TP10 几何死锁 | — | `evidence/r7_s2_gnd_blocked/change.json`（ok=false） |
| R7-S3 | CC2 过孔移位跳过（仅 DP 布线时有意义，DP 阻断） | — | `USB_R7_ADDENDUM.md` |
| R7-S4 | U2.5 VBUS + B.Cu 阶梯线整改**阻断**（电源路径评审事项，无原生 DRC 不做） | — | `USB_R7_ADDENDUM.md` |
| R7-S5 | USB DP/DM 布线**阻断**：GND 链尾段 (124.25,120.75)→(124.5,119.638) 封死 DM→J1 B7/A7 全部绕行（<0.1 mm）；叠层 C1/90 Ω 为 2D 估算（89.9 Ω）未获板厂确认，按红线不强行布线。**USB 8→0 未达成，总未连接维持 49** | — | `USB_R7_ADDENDUM.md` |

下一轮候选（需 KiCad 原生环境）：微调 /CHG_PGOOD_N 让出过孔位（原生 DRC+电源评审）· U2 器件级重排 · 板厂确认叠层/90 Ω 后按 `USB_R6_DESIGN.md` 第 3 节布线。
