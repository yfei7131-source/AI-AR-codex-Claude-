# EVT-1 H02 原生工程交付 · NOT FOR FAB

本轮在 PR #32 基线上合入 PR #33 的部分回件。先由嘉立创 4.1.97 导出 KIMI 当前工作副本，保留修改前字节，再把修复导入新的独立工程 `EVT1-H02-CODEX-20261119-C`。原始归档、原有工程和其他分支用于只读取证。三张 PCB 是 PR #30 的部分布局，作为 H02 绑定目标保留。

## 工程与证据入口

- [编辑器导出的原生工程](native/ZY_AIAR_EVT1_H02_NATIVE_NOT_FOR_FAB.epro2)，[保全的 KIMI 当前工作副本](native/KIMI-current-before.epro2)，以及[此次编辑器的实际导入文件](native/CODEX-H02-import-candidate.epro2)。
- [21 页与三板关联变更](evidence/hierarchy-transform.json)及[原生板级网表](evidence/native-C/board-netlists/)。18 张游离子页归入左主板、光学桥板、右音频板，分别为 8、7、6 页。修复桥板根图误指向主板电源来源页的实例。保留元件和页 UUID，两板各自的 `BAT1` 位号按板作用域分离。
- [料号清理规则](CATALOG.md)、[制造网表分组校验](NET_MEMBERSHIP_GATE.md)、[综合状态](evidence/native-audit.json)、[严格原生 ERC](evidence/native-C/erc/)和[台账及文件哈希](SHA256SUMS.txt)。

## 验收边界

| 项目 | 状态与依据 |
| --- | --- |
| 三板 SCH/PCB 绑定和页归属 | **PASS**。嘉立创原生返回三套不同 PCB UUID，21 页已归入对应板组；沿用三套原始 PCB 的受控设计范围。 |
| 真正板级网络 | **PASS**。三份原生 Protel2 验证 201 个网络组与 971 个板上已连端子（主板 110/494，桥板 56/294，右板 35/183）。同组成员和编译网名同时逐项比对；外部电池/扬声器的 PCB 排除标志独立检查。11 个源电源旗标的真实网名从 PR #32 的 POWER_ORIGINS 修正。 |
| 编辑器归档端子、NC、料号和存档 | **PASS**。保存、重载和编辑器再导出后，按原生符号和标记对象逐个核对全部 **1,075 个端子、92 个显式 NC、52 个受控厂商标识**。清理 131 个误填的描述值，恢复 `Y1_OSC` 的原厂 ASADV 封装，并在原生器件列表回读到 UUID。逐页在线捕获在第 17 页超时，16/21 页成功。 [归档交叉校验](evidence/native-C/archive-verification.json) |
| 严格 ERC 与最终 H02 | **FAIL / BLOCKED**。三块根图均运行严格 ERC 并返回 FAIL，保留缺失封装、仅符号和电源页告警。BOM CSV 导出达到两次通信重试上限后停止，第 17 页的超时调用未重试。 [原始编辑器回读](evidence/native-C/) |

## BLOCKED

1. 原厂缺失的封装、采购料号和 JBD FPC/AVDD/时序、摄像头模组针位保持阻断。已映射的 KiCad 焊盘数据和嘉立创工程的实际库关联逐项核对；确认封装和 PCB 焊盘安全前不得批量重绑定。
2. PR #32 受控 KiCad 的六个 DNP 实例需要验证嘉立创原生装配变体与输出。尤其两个光学连接器和 AVDD 稳压器在工程样件中维持禁装条件。当前归档禁止用于投板、贴装、连接光机或供电。
3. H02 完整验收通过后再推进三板制造级布线和实际 DRC/DFM。保持 [PR #32 桥板调整与制造规则](../closure/BRIDGE_RELAYOUT.md)。22 × 4.2 mm 桥板、六层 0.50 mm 叠层及双眼 FPC 机电接口均须重新通过各自的门禁。
4. 继承 PR #32 的 FPGA 仿真和 48 MHz 约束验收，以及有条件的电气模型。板级上电、AVDD 放电、摄像隐私、双电池与充电、电耗、双目光学性能和整机质量仍需实物验证。双目透明 AR 与 40 g 目标保持。

## 复现范围

`prepare_hierarchy.py` 以保全原生归档和 PR #30 的 PCB 归档为输入；`repair_native_fields.py` 修正可确认的原厂标识和 ASADV 封装；`repair_native_power_names.py` 按源表修正旗标。CI 重现可导入候选并逐字节核对解包后的文件。`capture_native_h02.py` 只面向新工程 UUID，实际采集三板原生制造网表、逐页引脚/NC 和 ERC。`verify_h02.py` 可离线复现最终回读，验收失败按退出码 1 保留。
