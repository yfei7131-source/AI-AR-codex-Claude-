# NATIVE_RUN_PLAYBOOK — 下一个**有 KiCad** 的窗口的第一动作
适用工程：`evt0_core/`（R5 S0–S7，PCB `b6ff6dd2`，SCH `81d599e6`，PRO `88775ef8`）。无 `kicad-cli` 时本手册不适用，仍记 NOT RUN。

## 1. 命令（在副本运行，输入文件不被改写）
```bash
kicad-cli version                      # 期望 10.0.x；先看 `kicad-cli pcb drc --help` 确认 --refill-zones/--save-board 被支持
SC_BEFORE=58 SC_AFTER=51 bash tools/run_native_checks.sh evt0_core evidence/native_R5S7_$(date -u +%Y%m%dT%H%M)
python3 tools/compare_native_expected.py evidence/native_R5S7_<同上> evidence/round5_calibration/expected_native_R5_unconnected_by_net.json
```
`--save-board` 不被支持时：去掉该参数，另在 KiCad 中手动重铺并另存副本，命令与原因写入证据；仍不得把重铺板直接覆盖输入工程，先审查再决定。

## 2. 预期（**模型预测，不是原生结果**；依据 `evidence/round5_calibration/`）
| 项 | R4 原生实测（10.0.7，2026-11-12） | R5 S7 预期 | 依据 |
|---|---|---|---|
| unconnected_items | 58 | **51**，逐网见 expected JSON（R4 逐网 − GND4 − PGOOD1 − VBUS1 − VSYS1） | 离线模型在R4上与原生逐网一致（58=58，37网无差异） |
| drill_out_of_range | 12（U1 焊盘41，孔0.20） | 0 | S2 孔→0.30 |
| lib_footprint_mismatch | 3（U1/J3/J1） | 0（**待原生确认**） | S3；aiar_fp库与板上封装逐字一致（fp_promote 重生成比对） |
| schematic_parity | 0 | 0 | R5 SCH 与 R4 SCH 仅 6 行 Footprint 属性不同 |
| 间距/短路/孔距/铺铜(starved_thermal, isolated_copper) | 0 | 未知 | S1/S4/S5 新铜与重铺**从未原生检查** |
ERC：R3 文档称 10.0.7 原生 0/0（载入官方库后），**报告文件未随本包，无法复核**；R5 SCH 电气内容与 R4 相同。

## 3. 分诊顺序
1. 先看 ERC 与 parity（应为0）。非0 → 先查 S3 封装库标识（`aiar_fp`、fp-lib-table）。
2. DRC 违规（预期0）：优先 ① `/CHG_PGOOD_N` 过孔(133.8,118.1) ↔ CHG_EN1 过孔（离线余量仅0.035mm）② J3 的 GND 短线与相邻焊盘（离线净距=规则0.20mm，零余量）③ VSYS 约35mm 沿 DNP 排针 J4 ④ 新增 GND/VBUS/VSYS/PGOOD 过孔穿过 In1/In2 铺铜后的 starved_thermal/isolated_copper。仅在原生报告指出违规处做**最小**改动，每改一步保存一个阶段ZIP。
3. unconnected 与 expected 有偏差 → 逐网核对 S1/S4/S5/S6，不要扩大到相机/显示/USB。
4. 覆铜：检查 In1 GND 回流连续性与割裂（USB 回流前提），记录后再决定是否采纳重铺结果。

## 4. 规则一致性待决项（R4/R5 继承；**需用户/板厂确认，勿擅自放宽**）
| 项 | 现状 | 风险 |
|---|---|---|
| 铜到板边 | DRU `Copper to board edge (min 0.3)`；`.kicad_pro` `min_copper_edge_clearance 0.5` | 自定义规则通常覆盖板级默认，实际生效可能是0.3而非0.5；以板厂能力为准，未确认前不改 |
| USB 线宽窗口 | DRU `track_width min 0.18 / opt 0.2 / max 0.25`；板最小线宽 0.20（DRU 头注亦写 0.20） | 低于板最小线宽；USB 布线前须由板厂能力/叠层决定，**不得用 <0.20 线宽** |
| 网络类过孔默认 | 原 Default/CamClk/USB 为 0.5/0.25（<板最小孔0.30） | **S7 已改为 0.6/0.30**（Power 原本即 0.6/0.30） |
| U1 EP 12×0.30 过孔 | 贴片焊盘内通孔 | 回流焊吸锡/堵孔/钢网开窗未决（制造可行性，需板厂+贴片厂意见） |

## 5. 不得做
出 Gerber / 任何制造放行；降低规则或用 ignore 隐藏违规；布 USB DP/DM（叠层、90Ω、板厂公差未给）；改动隐私联锁、电池保护、DNP、R28/J3/J4；把离线自检当作原生结果；宣称 40 g 已达成。
