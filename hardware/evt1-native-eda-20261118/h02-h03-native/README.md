# EVT-1 H02/H03 嘉立创专业版原生迭代

**制造状态 BLOCKED。** 在嘉立创 EDA 专业版 **V4.1.97** 中重新打开 PR #35 的既有工程，直接提交了 L2 实例字段和桥板两处禁放区。基线原理图、原生库与 PCB 的文档身份沿用 PR #35。保存、关闭重开并由编辑器导出后，归档对象级对照只发现 L2 的四条属性记录和桥板的两条区域记录有变化。 [可编辑工程](native/ZY_AIAR_EVT1_H02_H03_NATIVE_NOT_FOR_FAB.epro2) · [原生导出回执](evidence/after/archive-response.json) · [归档复核](evidence/verification.json)

## 原生改动与版图回读

- **左主板 L2。** 将实例的 `MPN` 和 `UserDocLink` 对齐 Murata DFE21CCN2R2MELL。宿主同时把两个空供应商字段由 null 规整为空字符串。实例 ID、原生封装以及 1→BK_SW、2→1V8_SYS 均读回匹配。 [保存后实例与引脚](evidence/after/l2-pins.json)
- **光学桥板。** 在 22.00 × 4.20 mm 原生板框内写入左右眼 FPC 各一处锁定、仅限制元件的 TOP 禁放区，距现有临近元件均约 0.428 mm。10 个已放元件、92 个焊盘、板框和原制造规则一致。严格 DRC 写入前后逐项一致，共 66 项。 [原生版图回读图](evidence/bridge/bridge-actual.svg) · [坐标、回读和 DRC](bridge_preflight.md)
- **D3 与 SCH/PCB。** 实测摆放输入覆盖 0.300 mm 铜到板边及端子 K→GND、A→PRIV_LED_ANODE。工程封装可读，宿主拒绝将对应旧工程器件或工程封装创建为桥板组件，复查确认无残留图元。既有 10 个桥板布局器件已逐脚对账，SCH/PCB 实例 UID 尚待同步。 [原生操作回执](evidence/operations/)

## H02 电气与装配检查

| 检查 | 本轮结果 |
| --- | --- |
| 原生严格 ERC | 主板 124、桥板 87、右板 57，逐对象比对与 PR #35 相同。18 条 ONLYSYMBOL 均匹配对应板内分层实例，规则继续启用。 [原始三板 ERC](evidence/after/erc/) |
| 原理图网络 | 三份原生 Protel2 对照受控设计均通过，201 个网络组和 971 个板上已连端子。三板 21 页归属、1,075 个原理图端子和 92 个显式 NC 均通过归档复核。 [原生板级网表](evidence/after/board-netlists/) |
| 250 条 MISSFOOTPRINT | 3 条有原厂推荐焊盘，17 条已确认料号待校核焊盘，93 条有封装类别，127 条受控封装仍阻断，6 条 DNP，4 条板外。桥板 U10/U11 的 TI DCK0006A、U14 的 ADI S6 已核对来源、封装方向和 18 个引脚。工程库创建了 DCK 空容器，宿主拒绝建形，容器随后已精确回滚。三处绑定继续 BLOCKED。 [逐对象分类与原厂数据](footprints/candidate-audit.json) |
| BOM 和 DNP | 三个 Basis 原生 CSV 导出请求均超时。SDK 对三板变体均只返回 Basis。六个 DNP 的工程样件变体及其 BOM/CPL 尚待取得。工程物料清册由本次原生归档提取，涵盖 118、83、52 个位号。 [原生导出回执](evidence/bom/) · [变体回读](evidence/variants/) · [工程清册](evidence/engineering-bom/) |

## FPGA 与制造阻断

[FPGA 回归记录](fpga/README.md)包含双目显示、主机帧、关断和主机编码的 Windows Icarus 实跑日志。本轮分支接入现有 GitHub Actions，沿用 48 MHz 门槛。基线后未发现 Gemini Neon 的可实施提交。

原型目标保留双目透明 AR、40 g 及电源和隐私安全。余下封装绑定、六项 DNP、JBD 双眼光机和 FPC、AVDD、电气实例同步、MK2 声孔和内层平面间隙、完整布线及制造签核仍待完成。 [接口与安全闸口](../h02-erc/HARDWARE_GATES.md)

## 复现

在本 EVT-1 目录运行以下命令。命令输出写入新路径。

```powershell
python -B h02-h03-native/verify_h02_h03.py --archive h02-h03-native/native/ZY_AIAR_EVT1_H02_H03_NATIVE_NOT_FOR_FAB.epro2 --capture h02-h03-native/evidence/after --output verification.json
python -B h02-h03-native/footprints/audit_candidates.py --check
```

桥板核验入口见 [bridge_preflight.md](bridge_preflight.md)。保留 [应用测试原始输出](evidence/unit-tests.log)。提交的工具回执对本机路径和团队标识做了脱敏，网表及由宿主导出的归档保留原字节。
