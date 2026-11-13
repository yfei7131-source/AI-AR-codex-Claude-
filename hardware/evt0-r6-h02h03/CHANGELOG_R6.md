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

注：此前名为 `native_after_s3/` 的目录其输入 PCB 哈希为 S3 之前的板（`6dbc5dc8…`），已更名为 `native_r6_s2_stackup_pre_s3/`，避免误读。
