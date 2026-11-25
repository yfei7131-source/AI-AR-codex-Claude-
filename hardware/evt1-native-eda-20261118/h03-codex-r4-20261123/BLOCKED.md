# EVT-1 H03 R4 制造与验证阻断

**NOT FOR FAB**。当前仍有 726 处未连通、1 项原生网表差异和 6 项原生严格 ERC 致命项。

| 阻断 | 已确认事实与解除条件 |
| --- | --- |
| PCB1 472 段 3 mil | 普通 1 oz 规则模板允许 1.9685 mil 的编辑设定值。嘉立创普通多层 1 oz 公示 3.5/3.5 mil，3 mil 例外限 BGA 扇出区。R4 的 472 段分布于顶层/底层/两信号内层，数量 181/175/72/44，包括非局部 USB、GND、反馈及相机线。须取得所选层叠、铜厚、每层及局部制造窗口的书面 EQ，再按约束重布。 [嘉立创普通多层能力](https://jlcpcb.com/capabilities/pcb-capabilities) · [嘉立创铜厚](https://jlcpcb.com/help/article/jlcpcb-copper-weight) · [嘉立创 HDI](https://jlcpcb.com/pcb-fabrication/hdi-pcb) |
| PCB1 J2/J3 与网表差异 | J2 的实际配对 FPC 针位、方向、防反结构及替代位置未冻结。J3 缺供应商、配对触点及充电座电气机械约束。R4 保留两者转 PCB 属性和网表检查。原生 DRC 只给出板级 Import Changes 信息。获得供应商资料后须绑定封装并用原生同步差异复核。 [接口证据](connector/PCB1_CONNECTOR_AUDIT.md) |
| PCB2 去耦与 FPGA 线束 | C5/C8/C9/C10/C11/C12/C31/C32 对应 VSYS 和光机偏置或保护。底层窗口含 28 段 3 mil FPGA 线，分别为 9 段复位和 19 段 CDONE/VSYNC。需联合验证内信号层、L2/L5 GND 回流、过孔和边缘空间。保留 C2/C3 功能性 RC、AVDD 和启动时序约束。 [回读](bridge/bridge-decap-readback.json) · [Lattice 硬件设计清单](https://www.latticesemi.com/-/media/LatticeSemi/Documents/ApplicationNotes/IK/FPGA-TN-02006-2-4-iCE40-Hardware-Checklist.ashx?document_id=47779) |
| PCB3 U11 与薄板 HDI | 工程只定义 L1–L2 和 L5–L6 两侧一阶微盲孔。0.80 mm 2+N+2 尚缺具体压合材料、介质厚度、层跨、激光填铜、目标/捕获盘和 SMT 窗口的板厂确认。0.2274 mm 最小盘与原球阵、锁定间距有几何冲突。须验证完整逃线与回流、射频、避光及装配。 [95 球与工艺推导](u11/README.md) |
| 电气及整机验收 | 关闭 ERC、DRC 和网表差异，布通电源、GND、复位、FPGA、控制及保护网络。真实双目透明光机和配对 FPC、MECR-01、40 g 预算、隐私联锁、AVDD 关断、安全电源、拼板及射频仍需对应签核。 |

141 孔的 V4 离线通过范围限标称圆孔、铜盘、已声明层跨和轮廓的几何筛查。板厂 EQ、厚度、阻抗、压合、钻孔和装配能力仍需确认。
