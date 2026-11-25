# H03 连通性和去耦复核 · NOT FOR FAB

使用 PR #46 的原始证据、独立重导入的 V4 PCB 读回和三板原生 Protel2 导出进行逐对象核对。V4 此处指接手时保存的 Gemini 候选，后续原生编辑以对应阶段的回读为准。 [原始 PR #46 证据](../../h03-u11-wlcsp-v3-dfm-route/evidence/reimport-verify/) [V4 独立重导入](../evidence/reimport-verify/) [逐项结果](electrical-residuals.json)

| 板 | 实际网组数 | 已放器件 / 有网焊盘端子 | 严格 DRC 未连通，PR #46 → 接手时 V4 | Netlist Error | 去耦位置告警 |
| --- | ---: | ---: | ---: | ---: | ---: |
| PCB1 左主板 | 112 | 118 / 477 | 358 → 358 | 1 | 3 |
| PCB2 光学桥板 | 58 | 86 / 303 | 238 → 238 | 1 | 10 |
| PCB3 右音频板 | 37 | 53 / 191 | 136 → 134 | 1 | 0 |
| 合计 | 207 | 257 / 971 | 732 → 730 | 3 | 13 |

## 三项 Netlist Error

三份原生 Protel2 与 PR #46 的原始文件逐字节一致。257 个已放器件按板、位号及原生 Unique ID 全部匹配，971 个有网焊盘端子与板级原理图同名。全部走线和过孔的网络均在同板原理图出现。PR #46 文档中的网组分板数量为 109 / 58 / 40，原始文件直接计数为 112 / 58 / 37，总数均为 207。 [左主板网表](../evidence/erc-3board/board-netlists/M-MAIN-L.net) [桥板网表](../evidence/erc-3board/board-netlists/M-OPT-BRIDGE.net) [右板网表](../evidence/erc-3board/board-netlists/M-AUD-R.net)

- **PCB1 有两项实际待放器件。** `J2 / J_CAM / 1fb9863844ab5169` 与 `J3 / J_CHG / bd3ee0abdb58119f` 均为 `Convert to PCB=yes`，原生封装字段为空。J_CAM 需冻结两端接口及互配图，J_CHG 需确定四触点磁吸座与充电输入边界。PCB1 和 PCB3 各自的 BAT1 与 SPK1 都有明确的 `Convert to PCB=no`，属于板外装配。 [受控 BOM](../../Inputs/effective_bom.csv)
- **PCB2 和 PCB3 保留聚合告警。** 比对范围内的器件、UID 与焊盘网络一致。三个 DRC 回执仅给出通用的 `Import Changes` 提示，缺少宿主逐对象变更清单，尚不能确定这两板的告警根因。放行需逐项核对宿主差异预览中的板绑定、封装、类型及属性，再对明确的差异做增量修改。 [PCB1 DRC](../evidence/reimport-verify/PCB1-drc-reimport.json) [PCB2 DRC](../evidence/reimport-verify/PCB2-drc-reimport.json) [PCB3 DRC](../evidence/reimport-verify/PCB3-drc-reimport.json)

## 十三项去耦位置告警

以下距离为电容第 1 脚到其实际功能端的平面直线下界。供电和地的完整回路距离须由布铜后量测。板内同名 VSYS 的最近 U 器件经常与电容的实际功能归属不同。 [受控端子与功能](../../Inputs/effective_netlist.csv) [左主板原始 DFM](../evidence/post-route/PCB1-dfm-check.json) [桥板原始 DFM](../evidence/post-route/PCB2-dfm-check.json)

| 板与电容 | 实际功能端 | 布局验收 |
| --- | --- | --- |
| PCB1 C21 | U13.1 相机 DVDD 稳压器 OUT | 输出电容及地回路靠近 U13，检查电容有效值和稳定性。 |
| PCB1 C31 | U15.24 相机隔离器 VCCA | 靠近隔离器 VCCA 与 GND。DFM 指向该网所在的 LDO 输出。 |
| PCB1 C40 | U10.A2 音频放大器 VDD | 100 nF 本地回路与对应供电、地端一起核对。 |
| PCB2 C2 | U11.3，AVDD_QUAL_RC | 资格确认定时 RC，保留时序与回流验证。 |
| PCB2 C3 | U13.3，AVDD_REQ_FILTER | 请求滤波 RC，保留滤波和失效测试。 |
| PCB2 C5、C8、C9 | `U_AVDD_EN_OD.5`、`U_AVDD_QUAL.5`、`U_AVDD_SCHMITT.5` | 分别靠近对应逻辑供电及地回路。 |
| PCB2 C10、C11、C12 | `U_AVDD_SYS_CLAMP.4`、`U_AVDD_SYS_PG.4`、`U_AVDD_WD.5` | 分别靠近钳位监督器、PG 监督器的 VDD 和看门狗电源。 |
| PCB2 C31、C32 | U6.4 IN、U6.1 OUT | 两者属于默认禁装的光学 AVDD 稳压单元。保留已知电路和预留，按最终器件、供电时序和 FPC 联合放行。 |

其中 C11 到 U13.4 的直线距离为 **639.25 mil**，工具到最近同网 U11 的提示为 171 mil。按独立重导入的 25 × 4.6 mm 板框和底面原生器件包围框，对 1 mil 网格及四个 90° 方向扫描。C11 电源焊盘距实际 VDD ≤100 mil 的板内摆位共 **99,973** 个，现有底面器件包围框检查通过 **0** 个，未进入走线筛查。C11 保持阻断，闭环需要桥板局部联动布局及请求、监督和关断的实测。C2、C3 保留原始告警计数和功能复核要求。 [TI TPS3890 端子及布局](https://www.ti.com/lit/ds/symlink/tps3890.pdf) [光学 AVDD 电气门禁](../../closure/ELECTRICAL.md)

## PCB3 GND 重叠支路

V4 的 PCB3 原生 DFM 检出 1 项重叠走线。新 6 段与原 3 段均连接 C5.2 和 U11.C2；现有的两条 GND 分支均在端点接入。基于独立读回的检查确认 6 段支路无其它 GND 焊盘、过孔或走线接触，计划限于移除这 6 段。原生编辑后再次读回，确认为同工程和 PCB，移除件数及 ID 精确匹配，保留导体、器件、板框、规则和丝印均可逐项重放。严格 DRC **134 项未连通、1 项 Netlist Error**，重复走线告警 **1 → 0**。 [原生重复线发现](../evidence/post-route/PCB3-dfm-check.json) [写入前约束和重读验证程序](verify_gnd_branch.py)

在本目录运行以下离线回放，使用 Python 标准库与仓库现有网表解析器。

```powershell
python audit_electrical_residuals.py --output electrical-residuals.json
python -m unittest discover -s . -v
```
