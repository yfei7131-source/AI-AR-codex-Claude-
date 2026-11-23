# PCB3 U11 R3 复核

**NOT FOR FAB**。只读对比 R2 与 R3 原始工程，PCB3、U11 封装和所在原理图页的记录正文相同，比较排除了文档头和记录票据。使用项目已有 Nordic Config #3 引脚契约，逐球验得 95 个球位、52 个有网球和 43 个显式 NC。22 个有网球接触同网顶层线或过孔铜，接触结果未计入内电层整网连通。95 个球均未发现居中孔。证据见 native JSON 和 CSV。[Nordic 95 球引脚表](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html) · [Nordic CMAA Config #3](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ref_circuitry.html)

## 裸板与装配

- R3 的 U11 为顶层 90°、0.350 mm 节距，原生圆形铜盘 Ø0.195 mm。PCB3 外框 5.20 × 34.00 mm，从 aQFN94 的 7 × 7 mm 外形可得，换封装须先做结构 ECO。CMAA 背面已有遮光膜，器件侧面与球侧仍需保护。[Nordic 封装原厂尺寸](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/mec_spec.html) · [Nordic 侧面与球侧遮光要求](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/recommended_op_conditions/doc/recommended_op_conditions.html)
- 嘉立创公开 HDI 允许 1–3 阶级数，0.80 mm 落在厚度范围内。现有六层板只定义 L1–L2 和 L5–L6，且孔径规则未绑定，原生工程中的盲孔 21 + 19 颗全部为 4/10 mil 孔径/铜盘。当前 L2/L5 为内电层，无法把它们直接当作通用信号逃线层。拟定 2+N+2 的叠层需确认每次压合 PP、过孔跨度、错位或叠孔、参考地连续性及 50 Ω/90 Ω 阻抗。孔径 Ø0.075 mm 要求每个钻孔跨层介质厚度不高于 0.075 mm，具体材料组合仍待板厂 EQ。嘉立创激光微盲孔采用铜填平，机械埋孔采用树脂塞孔并铜盖覆。[嘉立创 HDI 工艺规格](https://jlcpcb.com/pcb-fabrication/hdi-pcb) · [嘉立创 HDI FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)
- Ø0.075 mm 激光孔加 3 mil 双侧环的铜盘最小为 Ø0.2274 mm。与相邻异网/未赋网 Ø0.195 mm 圆盘的轴向铜间距为 0.1388 mm，小于锁定 6 mil（0.1524 mm）。36 个内圈有网球中的 25 个未通过这一必要条件，余下 11 个正处于已有同网 GND 网格。增加内层无法改变顶层铜几何。继承的 Nordic 四层参考采用单阶激光孔，名义 Ø0.07874 mm 钻孔及 Ø0.20066 mm 铜盘，对应环宽 2.40 mil。可继续依据现有限制评估离心逃逸，数字脚重映射须固件和板级 ECO。当前证据不支持将 0.18–0.20 mm 的新铜盘用于所拟的 ≥0.075 mm 激光孔。[Nordic 参考包下载](https://www.nordicsemi.com/Products/nRF5340/Downloads) · [嘉立创目标盘及捕获盘规则](https://jlcpcb.com/pcb-fabrication/hdi-pcb)
- PCB3 的 5.20 mm 边落在嘉立创 HDI 裸板 5 mm 公开下限以上，单板外形小于其标准 PCBA 的最小外形。标准 PCBA 公示 BGA 球距最小 0.30 mm，经济版为 0.50 mm。此处应确认拼板、钢网、双面贴装和 X 光验收。[嘉立创标准 PCBA 能力](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)
- 嘉立创普通 1 oz 多层为 3.5/3.5 mil，其 3 mil 例外限 BGA 扇出。嘉立创 HDI 另列标准 3/3 mil，并仍有孔到线和环宽限制。原生 PCB3 默认单层线宽规则允许 1.9685 mil，因此 EDA 的线宽 DRC 与生产线宽筛查分别记录。[嘉立创普通板规则](https://jlcpcb.com/capabilities/Capabilities) · [嘉立创 HDI 规则](https://jlcpcb.com/pcb-fabrication/hdi-pcb)
