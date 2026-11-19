# EVT-1 H02 原生 ERC 修复回读

**制造状态 BLOCKED · NOT FOR FAB。** 本轮基于 PR #34 的编辑器归档，在独立嘉立创工程 `EVT1-H02-ERC-20261120-B` 修复 11 条电源导线的网名以及两处器件封装关联。三板通过保存、关闭、重开、原生网表对账和归档交叉校验，严格 ERC 仍失败。

- [嘉立创保存并重新导出的可编辑原生工程](native/ZY_AIAR_EVT1_H02_ERC_L2_D3_NOT_FOR_FAB.epro2)与[导出的 SHA-256 回执](evidence/archive-response.json)。
- [输入归档至候选的对象级变更](evidence/transform.json)与[回读验证及完整剩余 ERC 对象清单](evidence/round-verification.json)。
- [原生严格 ERC](evidence/erc/)、[保存和重开回执](evidence/reload/)、[原生 Protel2 网表](evidence/board-netlists/)和[本轮 9 页原生引脚回读](evidence/pins/)。

## 严格 ERC 前后对照

| 板 | PR #34 | 本轮 | 剩余 MISSFOOTPRINT | 剩余 ONLYSYMBOL |
| --- | ---: | ---: | ---: | ---: |
| 左主板 M-MAIN-L | 131 | 124 | 117 | 7 |
| 光学桥板 M-OPT-BRIDGE | 98 | 87 | 81 | 6 |
| 右音频板 M-AUD-R | 63 | 57 | 52 | 5 |
| 合计 | 292 | 268 | 250 | 18 |

22 条电源旗标和端口告警已清零。其余两项消除来自 L2 和 D3 的封装关联。无新增诊断。18 条 ONLYSYMBOL 逐对象对应已绑定的分层页实例，规则仍启用。250 条 MISSFOOTPRINT 中，113 条已有受控 KiCad 焊盘编号对照，仍须确认原生封装等效性。其余 137 条在受控封装表中也处于 BLOCKED，其中 4 条属于板外对象。各条均按板、页、位号、图元和受控料号列于回读报告。

| 封装 | 实际回读的焊盘及网络 |
| --- | --- |
| 主板 L2 · Murata DFE21CCN2R2MELL | 1 → BK_SW，2 → 1V8_SYS。两块 0.80 × 1.40 mm 矩形铜盘，中心距 1.60 mm。 [Murata 焊盘规范 §12.1](https://search.murata.co.jp/Ceramy/image/img/P02/JETE243A-0052.pdf) |
| 桥板 D3 · Kingbright APHD1608LCGCK | 厂家 1 对应 K → GND，厂家 2 对应 A → PRIV_LED_ANODE。两块 0.70 × 0.80 mm 矩形铜盘，中心距 1.50 mm。实例和库默认料号及资料链接一并纠正。 [Kingbright 规格书第 1 页](https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf) |

原理图回读识别到两个本地原生封装 UUID。封装迁移到 PCB、paste/mask、贴装方向及 DRC/DFM 继续作为制造前置条件。L2 的原生 `Manufacturer Part` 正确，继承的自定义 `MPN` 和 `UserDocLink` 仍为旧文本。工程物料清册采用原生 `Manufacturer Part` 字段对账。

## 连通性和页面

三板的 SCH/PCB 绑定、21 页归属、PCB 几何和规则通过归档校验。三份编辑器 Protel2 对照 PR #32–#34 的受控图，网络名称与成员均匹配，共 201 组、971 个板上已连端子。重新导出的归档逐脚查验 1,075 个端子和 92 个显式 NC。上轮缺失的五页均取得了本轮直接回读。归档修正涉及的另外四页也已重读，其余 12 页以 PR #34 的逐页原生证据和本轮全项目归档对照交叉核验。

## 制造阻断

- **原生 BOM 及装配。** 三板编辑器 BOM CSV 和指定 Basis 的 XLSX 调用均超时。当前提供由本轮保存后归档直接提取的三份工程物料清册，覆盖左主板 118、桥板 83、右音频板 52 个位号，包含板外物料。嘉立创 SDK 三次板级回读均仅返回 `Basis`，六个受控 DNP 仍缺少工程样件变体和对应 BOM/CPL 证据。 [CSV 回执](evidence/official-bom/) · [XLSX 回执](evidence/official-bom-basis-xlsx/) · [装配变体回读](evidence/assembly-variants/) · [工程清册](evidence/engineering-bom/) · [BOM 对账](evidence/board-bom-verification.json)
- **封装、接口和实物。** 剩余封装逐对象核准。JBD 的两眼光机型号、FPC 针位及方向、AVDD 负载和时序未定。相机模组及针位未定，Hirose 原厂的相机座本体长度为 6.80 mm，受控机械台账的旧值为 5.50 mm。两眼光机及摄像隐私联锁仍需实测。 [装配和外部接口清单](HARDWARE_GATES.md)
- **桥板。** 在 22.00 × 4.20 mm 刚性板内，既有 DCUR 包封无试算共置解。采用 YZPR 封装投影并远置三处连接器时，找到三颗器件共置坐标，最小同面间隙 0.241 mm。实际料号替换、连接器配对 STEP、走线及 PCB DRC/DFM 未放行。继续保留双目透明 AR、40 g 整机目标和原有安全条件。 [桥板几何方案](bridge_trial.md)

## 复现

从 `hardware/evt1-native-eda-20261118` 运行。候选生成从 PR #34 归档哈希起验，输出使用新路径。

```powershell
python -B h02-erc/prepare_candidate.py candidate.epro2 transform.json
python -B h02-erc/verify_round.py --candidate candidate.epro2 --persisted h02-erc/native/ZY_AIAR_EVT1_H02_ERC_L2_D3_NOT_FOR_FAB.epro2 --capture h02-erc/evidence --transform transform.json --output verification.json
python -B h02-erc/bridge_island_trial.py --check
```

`capture_erc_round.py` 采集嘉立创保存、重开和验收回读。需事先导入独立工程并打开根图，传入新工程 UUID、名字和实际连接窗口 ID。 `verify_board_bom.py` 核验原生 BOM 或从归档提取工程物料清册。

[项目测试](evidence/unit-tests.log) 102 项和 [H02 对账回归](evidence/h02-regressions.log) 6 项通过。提交版回执省略本地绝对路径及团队 ID，保留工程 UUID、摘要、命令和验证结果。
