# PCB3 U11 CMAA Config 3 独立复核

**球位和网名对账通过。制造仍为 BLOCKED。** nRF5340-CMAA-R7 的 95 球编号、原理图端子、原生 PCB 焊盘和当前网名逐一相符。原理图明确标有 43 个 NC，52 个球位有受控网络，几何分布为外圈 16、次外圈 22、更深 14。嘉立创 V4 重新导入后的 PCB 回读包含精确的板 ID、元件 ID 和旋转。原生右板 Protel2 字节与 PR #46 相同。95 球按 A–L 跳过 I、列 1–12 的稀疏网格排布。 [逐球清单](u11-cmaa-config3-ball-matrix.csv) · [机器核验](u11-cmaa-config3-verification.json) · [Nordic WLCSP Table 3](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html)

## 必须守住的电气边界

| 范围 | 原生核对 | 下一验收 |
| --- | --- | --- |
| 正常电压、无 USB | 九个 VDD 和 B12 VDDH 在 `1V8_SYS`。19 个 VSS/AVSS 归 GND，B11 VBUS 也归 GND。A11/A12、C11 DECUSB、D11 DCCH 保持显式 NC。 | 在 U11 端实测冷启动、压降和无线突发。Nordic 的 POR 最低为 1.75 V，稳态正常电压最低为 1.70 V。 |
| 两路 DC/DC | B6 DCC 经 10 µH L3 接 B1 DECRF/B4 DECR 共节点。该节点接本板 C9 1 µF、C10 2.2 nF。A9 DCCD 经 10 µH L4 接 A7 DECD 及本板 C11 1 µF。B5 DECN 接 C12 100 nF，B8 DECA 接 C13 1 µF。 | 缩短开关与返回回路。以实际料号、偏压有效容值、线圈额定和脱耦阻抗验证后，再开启两个 DCDCEN。 |
| RF 与编程 | D1→L1 2.2 nH，匹配中点 C7 0.7 pF→GND，经 L2 2.2 nH 到馈线，C21 是 DNP 调谐位。F1/F2/G2 的 SWDIO、SWDCLK、复位独立到 TP6。 | C21 样件装配保持 DNP。复验天线回流、顶部走线阻抗和示波/编程可达性，须做 VNA/S11 与 OTA。 |
| 时钟 | A1/A2 是 HFXO 固定端子。F11/F12 按已继承的 ECO-08 连到 LFXO Y3 及 C22/C23。老版 `CAD_TERMINALS.csv` 仅这两球还写 NC，当前板级网表和原理图 NC 标注已同步。 | 校正 U11 仍写 LFRC 的继承属性。采用外部 12 pF 电容时配置 `XOSC32KI.INTCAP=External (0)`，选择晶体 LFXO，校准/测量负载与启动。HFXO 仍需锁定精确订货号和 FICR 装载设置。 |
| 信号重映射 | J4/J5/K4/K5 是 I2S PSEL 信号，K3/L3 是 UARTE PSEL 信号，K2 为 GPIO。它们在硅片上可重映射，当前板级契约保留原分配。 | J4/J5/K2/K3/K4/K5 这六个内圈球位可列入经批准的 PCB 和固件协同 ECO，仍需按原电源域、回流、固件引脚和休眠状态验收。 |

原厂电路来自 CMAA Config 3，版本 1.0，2025-02-20。项目板本地 `C9/C10/C11/C12/C13/C21` 分别对应 Nordic `C3/C4/C5/C6/C7/C19`。时钟电容和装配状态仍需实物验证。 [原厂电路与 BOM](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ref_circuitry.html) · [电源规格](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/regulators.html) · [振荡器规格](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/oscillators/doc/oscillators.html) · [I2S PSEL](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html) · [UARTE PSEL](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/uarte.html)

## HDI 决策的两项修正

1. **Nordic 参考板为四铜层、一级盲孔。** 原版输出含 GTL、G1、G2、GBL。TX1 有 30 个外层到第一内层的激光孔，其中 11 个恰在 U1 焊盘中心。95 个顶面焊盘在 GTL/GTS 中匹配，铜盘名义直径 0.20066 mm，阻焊开窗 0.29972 mm。激光孔名义直径 0.07874 mm，按 Gerber 名义尺寸计算环宽为 0.06096 mm = 2.40 mil。该制程可作参考，EVT-1 的 3.0 mil 规则需要另外满足。澄清既有报告中“Nordic Config 3 使用 2+N+2”的表述。 [Nordic Reference Layout 1.3](https://www.nordicsemi.com/Products/nRF5340/Downloads) · [Gerber 与钻孔核验](nordic-config3-artwork-verification.json)
2. **2+N+2 只增加逃逸层数，当前环宽仍与顶部铜距冲突。** EVT-1 的 U11 存档铜盘为 7.677 mil（约 0.195 mm），封装旧描述的 0.21 mm 应同步纠正。0.075 mm 钻孔加 3.0 mil 径向环宽的成孔焊盘最小外径 0.2274 mm。在 0.350 mm 节距下，它与紧邻 0.195 mm 焊盘间只余 0.1388 mm（5.46 mil）。满足锁定 6.0 mil 时，单个居中 via 对紧邻异网或无网焊盘的直径上限为 0.2002 mm，两个相等相邻异网 via 时为 0.1976 mm。按这项必要条件计算，**25/36 内圈有网球位** 无法直接使用该居中孔，11 个同网地簇球仅通过单孔局部铜距检查。不能从该检查推断离心逃逸、整网连通、钢网、层间可靠性或设计全局无解。

保留 5.20 mm 结构、0.35 mm 器件与规则，先评估地簇分流、可达离心位置及六个内圈数字信号受控重映射。若考虑 2+N+2，须书面确认激光能力、环宽和各层盘径。以紧邻双 via 为例，3.0 mil 环宽约束要求名义孔径不大于 0.0452 mm，尚无供应商证据证明该孔径和叠层可制造。通过全网连接、回读 DRC 和实物后才可放行。

## 复现

从本目录运行 `python -B audit_u11.py --check`，使用父目录已归档的专业版 V4 工程、板级网表及重新导入的 PCB 回读。用 `python -B verify_nordic_reference.py <原厂ZIP> --check` 独立重算原厂参考板的铜焊盘、阻焊开窗及盲孔数据。原厂 ZIP 的哈希和用户工程证据均已写入对应机器报告。
