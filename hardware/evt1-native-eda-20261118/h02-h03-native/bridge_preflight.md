# 光学桥板原生预布局验收

本轮在原生 `PCB2`（`9ce45f14cb79dc9d`）写入双目光机 FPC 顶面器件禁放区。两处均经保存、关闭重开和导出 EPRO2 验证，记录为独立锁定多边形，规则仅为 `no-components`。保留 22.00 × 4.20 mm 桥板、双目透明 AR、40 g 整机目标和 PR #32 制造条件。 [PR #35](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/35) · [PCB 约束](../PCB_CONSTRAINTS.json) · [保存后对账](bridge_preflight_after.json)

| 保护区 | 板面 | 区域 Y 范围（mm） | 最近既有元件 / 间隙 | 原生图元 |
| --- | --- | --- | --- | --- |
| 左眼 FPC | TOP | 3.03–5.37 | U13 / 0.428 mm | `0a908ce33a052ebb` |
| 右眼 FPC | TOP | 13.63–15.97 | U7 / 0.428 mm | `0ba8a7175248ae26` |

- **焊盘与连通性。** 10 个已放对象的 92 个物理焊盘全部对齐受控端子与 PR #35 原生 Protel2。81 个物理焊盘有网，11 个保留明确 NC。MK2 逻辑地脚 `5` 对应 4 个物理 GND 铜盘。10 个既有对象的 PCB 实例 Unique ID 与 SCH 均未配对，8 个为空，U8 与 Y1 使用旧的人工键。严格 DRC 的 `Import Changes` 提示仍待解除。 [逐焊盘与实例身份报告](bridge_preflight_before.json)
- **D3 预布局。** Kingbright `APHD1608LCGCK` 建议 TOP 90°，原点 `(2.10, 1.40)` mm（`82.677165, 55.118110` mil）。按 +Y 读 K、A，分别为 GND 和 PRIV_LED_ANODE。原生封装占位至左侧光机 FPC 预留最小约 0.280 mm，名义铜到板边 0.300 mm。当前嘉立创放置接口拒绝解析工程内器件，D3 仍未放置。导光件和实物隐私联锁仍待验。 [Kingbright V.4B 第 1 页](https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf)
- **U8 与接口。** 将连接器包络与 FPC 预留作为输入，0.05 mm 网格搜索现有 DCUR 封装的已见姿态和反向投影，既有邻件固定时零可行点。能只移动一个既有邻件的组合涉及 IMU U9 或麦克风 MK2，受惯性轴或声孔机械约束。三处远置支撑与 YZPR 替代封装保留为 PR #35 的条件方案。 [PR #35 桥板几何方案](../h02-erc/bridge_trial.md)
- **严格 DRC。** 写入前后违规对象及规则完全一致，共 66 项。59 项为连接、4 项为 MK2 同封装焊盘距声孔槽不足、2 项为声孔槽与内层平面重叠、1 项为网表。MK2 地焊盘至槽的 DRC 实测为 5.3 mil，要求 6 mil，两个内层平面要求 10 mil。归档声孔 Ø0.700 mm，Infineon 建议 Ø0.800 mm。须联合复核声孔、地铜和内层开窗，再验证封装及声学装配。嘉立创铜回读未覆盖这两个负片平面的完整铜形。 [保存后 DRC 对账](bridge_preflight_after.json) · [Infineon §7 图 12](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf)

核验脚本读取采集原件，复现 D3 投影、逐脚网络、实例关联和 U8 有限域搜索。传入 D3 放置后同一版本的三份回读，脚本也会核对极性、铜盘尺寸和安装姿态。

```powershell
python -B h02-h03-native/bridge_preflight.py --dump bridge-before.dump.json --archive before-edit.epro2 --drc pcb-drc-before.json --check h02-h03-native/bridge_preflight_before.json
python -B h02-h03-native/bridge_preflight.py --dump bridge-persisted.dump.json --archive ZY_AIAR_EVT1_H02_H03_NATIVE_NOT_FOR_FAB.epro2 --drc pcb-drc-after.json --before-dump bridge-before.dump.json --before-drc pcb-drc-before.json --require-keepouts --check h02-h03-native/bridge_preflight_after.json
```

实际桥板走线、完整原生 DRC、配对 STEP、D3 导光件及功能验证为 **BLOCKED**。当前几何验收用于局部原生预布局。**NOT FOR FAB**。
