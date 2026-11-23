# H03 R6 PCB3 二阶 HDI 研究 · NOT FOR FAB

输入为 PR #53 可编辑 R5 归档、独立重导入铜箔读回和原厂 WLCSP95 球表。计算只使用 75 µm 与 100 µm 激光孔，以及已有名义 6/12 mil 的机械钻孔尺寸。本目录没有修改集成原理图或原生 PCB。

## 工艺窗口和替代封装

- 两个阶段每层以 50 µm 压合介质为候选。标准 100 µm 激光孔每阶纵横比 0.50，75 µm 孔每阶 0.667。以 418 µm L3–L4 芯、外层 35 µm 铜、内层 18 µm 铜、双面 20 µm 阻焊预算得 0.800 mm。Ø0.1524 mm L3–L4 芯内机械埋孔纵横比约 2.74。制造商需确认实际压合、铜量、材料名义厚度、阻抗、埋孔塞覆和针脚装配。跨阶跳孔按两个独立激光级叠孔验收。当前归档只声明 L1–L2 和 L5–L6，未采用该叠层。 [嘉立创 HDI 公示](https://jlcpcb.com/pcb-fabrication/hdi-pcb)
- 75 µm 捕获盘/目标盘直径最小 0.2274 mm。0.35 mm 球距下，对相邻既有 Ø0.195 mm 铜盘仅留 0.1388 mm；两颗最小捕获盘并排名义仅有 0.1226 mm，两者均不足项目锁定 0.1524 mm。100 µm 档最小盘为 0.2524 mm。把所有受阻球同时改用居中孔无法满足铜箔间距。孔壁间距和铜边间距需分别验收。 [嘉立创 HDI 孔距量测指南](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)
- Nordic CLAA 和 CMAA 都是 4.390 × 3.994 mm、95 球、0.35 mm 节距，官方共用球位表。CLAA 也标记为不推荐新设计。QKAA 本体宽 7 mm，PCB3 宽 5.20 mm，结构至少需重开器件所在截面才可继续。 [Nordic 订购选项](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ordering_info/doc/ordering_info.html) · [Nordic 球位表](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html)

## PCB3 实际铜数据筛查

- K4 的 LRCK 在顶层有可用向外扇出。100 µm 档从 K4 到 J1.P12 找到两条不碰原焊盘阻焊开口的名义候选。保留原 K4/P0.22，组合走线使用 L1–L2–L3 和 L6–L5–L4 两组叠孔及 L3–L4 芯内机械埋孔，四层线宽均 4 mil。第一方案三孔位为顶 (177.5, 328.0)、底 (94, 295) 和芯 (180, 318)，坐标单位 mil。按原生检查实测门槛，异网平面留 10.15 mil，走线到板边至少 11.85 mil，RF 保留 12 mil 工程筛查余量。L2 向边缘开槽消除窄铜条，L5 原 GND 铜与最近反焊盘实际只余 0.665 mil。L2/L5 各保持单个地平面多边形，未切到原接地铜。U10.C3 名义走线在筛查排除底面阻焊开口后没有可通过的候选，R4.1 也留待布线。 [严格形态筛查](symmetric-mask-safe.json)
- K5/P0.20 到 U10.C1 的原针位在有界 75 µm 筛查中没有顶层逃线。另以外圈显式 NC 的 L9/P0.15 替换 BCLK 驱动可得到名义路径，L9 原官方复用为 QSPI IO2 与通用 GPIO。现有 nRF5340 构建没有外接 QSPI 网络。此变更需要原理图 NC 和 PCB 原位同步、固件 PSEL.SCK 归属及 System OFF 和上电默认电平及整机音频验证。原 nRF 单主、原有下拉和其余 I2S 针位保持。J1.P11 与 R3.1 仍待闭合。 [BCLK 候选](bclk-pair-research.json) · [Nordic I2S PSEL](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/i2s.html)
- 两个不同网络候选联合筛查的最小共享层铜边间距为 30.827 mil，最小孔壁间距 36.827 mil，L2/L5 反焊盘之间无面积重合。两张 GND 平面均保留一个多边形且无现有接地铜受切割。0.665 mil 的 L5 名义余量不足以判定公差下可靠接地。没有把这些半网作为已布通 I2S 或已通过制造的工程提交。 [联合筛查](i2s-two-net-joint-screen.json)
- 专供隔离原生试验的 K4 单端路径可复用 4/10 mil 铜与孔尺寸。它与整链候选的坐标不同。中心 (176.98031,327.75588) 的 L2 边开槽给出 10.15 mil 铜边与 13.15 mil 孔边净距，GND 平面保留 99.56% 面积与单块拓扑。L3 没有该网络的既有铜。 [定位与试验条件](k4-test-stack.json) · [严格 L2 开槽](k4-native-clearance-notch.json)

复跑使用 Python 3 和 Shapely 2。脚本参数为 R5 项目目录及输出路径。对 K4 名义标准筛查执行 python -B symmetric_stack.py R5 OUTPUT。联合回放执行 python -B replay_i2s_pair.py R5 symmetric-mask-safe.json bclk-pair-research.json OUTPUT。
- 扩大底层搜索后，从同一 K4 叠孔入口 (177.5,328) 和芯内埋孔 (180,318) 分支至底面 (101,301) 和 (136,376)，分别接 J1.P12 与 U10.C3。两块地平面联合复核的最近保留接地铜余量提高到 7.18 mil（L2）与 8.48 mil（L5）。100k 下拉 R4.1 仍未找到保留阻焊的可用接法。当前候选完整驱动链仍需完成该下拉及制造工艺。 [改进路由](k4-full-net-research.json)
