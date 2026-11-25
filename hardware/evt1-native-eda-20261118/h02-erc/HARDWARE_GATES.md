# H02 装配与外部接口准入

**BLOCKED · NOT FOR FAB。** 本轮核对 PR #32 的受控输入、PR #34 回存原生工程与 H02 ERC 导入候选。面向双目透明 AR，整机质量目标为 40 g。板级网表的连通性验收与以下装配、供应商和实物验收分别取证。

## 默认工程样件的六项 DNP

KiCad 原理图中有六个 `(dnp yes)` 实例，与 [受控目录计划](../h02-native/catalog-plan.json) 的 `sourceDnp` 逐项匹配。对 PR #34 归档与 ERC 导入候选使用同一板号、页 UUID、图元 ID 和位号解包核对，六个实例属性和对应器件元数据均一致。以下页号用于定位，位号按板隔离。 [PR #34 原生归档](../h02-native/native/ZY_AIAR_EVT1_H02_NATIVE_NOT_FOR_FAB.epro2)

| 板 | 位号与源标识 | 页 UUID | 样件禁装原因 |
| --- | --- | --- | --- |
| M-MAIN-L | C12 · `C_ESP_RF_IN` | `3e7683d1ed324ce9` | ESP32 射频匹配待 VNA 实测 |
| M-MAIN-L | C13 · `C_ESP_RF_OUT` | `3e7683d1ed324ce9` | ESP32 射频匹配待 VNA 实测 |
| M-OPT-BRIDGE | J2 · `J_DISP_L` | `b1ec1f299f13f9eb` | 左眼端 FPC 与机电资料待确认 |
| M-OPT-BRIDGE | J3 · `J_DISP_R` | `b1ec1f299f13f9eb` | 右眼端 FPC 与机电资料待确认 |
| M-OPT-BRIDGE | U6 · `U6_OPT_AVDD` | `d643a0611d67a31a` | AVDD 电压、负载、时序及订货号待确认 |
| M-AUD-R | C21 · `NRF_CT19` | `07dc7dde94c1bf76` | Nordic 射频匹配待 VNA 实测 |

六个原生器件的库属性均为 `Add into BOM=yes`。C12、C13、C21 的实例也显式为 `yes`，J2、J3、U6 的实例无该覆盖字段。归档的 `CONFIG` 仅有 `defaultSheet`，三板根图的 SDK 变体查询均只返回 `Basis`。生产准入须在保存重载后回读三板的工程样件变体，核实每个受控位号的“不装配”状态，在对应采购 BOM 与贴装 CPL 中确认六个位号均排除，同时验证这些位号的板级网络与预留用地。 [本轮原生变体回执](evidence/assembly-variants/) [嘉立创装配变量](https://prodocs.lceda.cn/cn/schematic/tool-assembly-variants/)

## JBD 双目光机

公开资料给出两套不同的接口。JBD 的 Hummingbird 0.13″ VGA 微显示为 QSPI，公开的 Hummingbird I 双目全彩波导模块和 Hummingbird II 全彩投影器为 MIPI。受控设计预留 `JBD013VGA-G` 一类的 QSPI 双眼接口，继续等待具体光机、波导及供应商适配件的型号和版本。若签收件为 MIPI，必须先重新评估 FPGA 至光机的传输、功耗、引脚和布线。 [JBD 0.13″ 微显示](https://www.jb-display.com/product_des/3.html) [JBD Hummingbird I 双目模块](https://www.jb-display.com/product_des/8.html) [JBD Hummingbird II 投影器](https://www.jb-display.com/product_des/17.html)

| 阻断 | 放行所需证据 |
| --- | --- |
| BLK-JBD-01 | 两眼各自的 FPC 焊指编号、插接方向、配对图与 P1–P10、PWR1、PWR2 的端到端连续性。板端 BM28 10+2 为候选，`PWR1` 与 `P9` 同接候选 AVDD。 |
| BLK-JBD-02 / 03 | 具体型号及版本的上电初始化、休眠唤醒、亮度补偿、写入帧格式、时钟与 dummy 周期。使用真实两眼面板验证有效帧和断电恢复。 |
| BLK-JBD-04 | 原厂 AVDD/IO 工作范围及绝对额定、负载/浪涌、电容、上下电顺序、掉电反灌和放电时间。取得光机、配对波导及 FPC 的 STEP、装调与光学公差，核实弯折、避让、眼盒、出瞳和左右眼对位。 |
| BLK-JBD-05 | 供应商确认的分眼寻址及左右眼校准。在对应硬件上验证共享时钟/片选与两路数据的工作模式。 |

两个光学连接器与 AVDD 稳压器继续按默认 DNP 管控。无屏台架可验 D1.1 的心跳、看门狗和 UVLO 关断控制。批准给光机上电之前，须用签收的供应商限值验收实测的 AVDD、反灌和掉电波形。 [受控针位](../Inputs/effective_pinmap.csv) [台架测试门禁](../Inputs/bench_gates.csv) [Hirose 光学连接器](https://www.hirose.com/en/product/p/CL0673-5044-0-53)

## 左主板相机接口与隐私灯

- **J_CAM 机械输入待更新。** 受控 BOM-05 的标识对应 Hirose `CL0673-5025-0-53`。厂家给出 **6.80 × 1.70 × 0.60 mm** 本体、0.35 mm 间距、0.60 mm 名义对插高和 0.011 g 单件目录质量。原表 `Y_size=5.50 mm`、0.022 g，链接落在其他触点数。沿用原锚点 `(2.90,19.00) mm` 和长轴 Y 方向时，本体 Y 范围从 `[16.25,21.75]` 改为 `[15.60,22.40]`，两端各扩 0.65 mm。该计算的范围是本体，配对插头、FPC、加强片、定位及装配工具避让须重新核对。 [受控 BOM](../Inputs/effective_bom.csv) [Hirose 24+2 座原厂页及 2D/STEP](https://www.hirose.com/product/p/CL0673-5025-0-53)
- **J_CAM 封装及 CAM1 模组针位保持 BLOCKED。** 原生 `M-MAIN-L/J2` 的局部触点为 P1–P24 与 PWR1/PWR2。待以原厂座/插头图和实际模组 FPC 的同一观察面确认方向与实物编号，然后验证全 26 触点。模组需冻结具体订货号与版本、8 位 DVP 位序与时序、SCCB、RESETB/PWDN 极性及时序、AVDD/DVDD/DOVDD 电平、内部稳压和掉电容忍度。OMNIVISION 公布 OV5640 支持 DVP 与 MIPI 两种输出，具体模组及 FPC 资料仍待签收。验收包括 rail 次序、不完全供电、反灌、首帧与断电故障窗口。 [受控接口端子](../kicad/EXTERNAL_INTERFACE_TERMINALS_BLOCKED.csv) [OMNIVISION OV5640](https://www.ovt.com/press-releases/omnivision-launches-optimized-quarter-inch-5-megapixel/)
- **D3 隐私灯已生成并离线核对原厂封装，实物门禁仍开。** 桥板 `M-OPT-BRIDGE/D3` 的基线 `Manufacturer Part` 已为 `APHD1608LCGCK`。离线转换对齐了该实例和库默认的旧 `MPN` 及文档链接，并添加对应封装关联。厂家 1 为阴极 K、2 为阳极 A，对应受控网络 `K→GND`、`A→PRIV_LED_ANODE`。原厂 V.4B 第 1 页推荐焊盘为两块 0.70 × 0.80 mm 矩形，内隙 0.80 mm，中心距 1.50 mm。以原厂顶视图、器件中心为原点，K 位于 `(-0.75,0)`，A 位于 `(+0.75,0)`。使用实体灯、限流电阻、光导和外壳测定可见性、电流窗口、温度边界与硬件禁采，并复核触发关断时的灯和摄像轨波形。 [D3 单独转换证据](kingbright-d3-binding.json) [Kingbright V.4B 封装与推荐焊盘](https://www.kingbrightusa.com/images/catalog/SPEC/APHD1608LCGCK.pdf) [隐私联锁台架条件](../closure/ELECTRICAL.md)

本页的几何与装配核对以归档和供应商资料为依据。D3 的编辑器持久化状态以本轮原生回读记录为准。
