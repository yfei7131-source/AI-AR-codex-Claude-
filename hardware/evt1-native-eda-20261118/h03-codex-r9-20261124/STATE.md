# H03-R9 STATE

**2026-11-24 · 嘉立创 EDA 专业版 V4.1.97 · NOT FOR FAB**

本地 R9 继承 PR #58 提交 `1b69c06e81500d6a8b5ce4aaf268513c6b89dfd4` 的原生归档。Git blob `cf39b6ce0c5b4d0affd213a48a13996dcb794944` 与本地源文件一致。交付保留真实双目透明 AR、40 g 整机目标、电源和隐私安全方案。 [PR #58](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/58)

## 原生验收

| 板 | 连接错误基线 → R9 | 严格 ERC fatal | 原生网表差异 |
| --- | ---: | ---: | ---: |
| PCB1 主板 | 339 → 334 | 4 | 1 |
| PCB2 光学桥板 | 232 → 232 | 0 | 0 |
| PCB3 右音频板 | 130 → 129 | 2 | 0 |
| **合计** | **701 → 695** | **6** | **1** |

三板保存、重载、独立重导入并分别执行严格 ERC/DRC。原生 DRC 间距和短路项为 0。独立重导入逐项复现最终 DRC 对象签名，独立再导出核对 1,451 份原生文档记录。三份 Protel2 网表在基线、保存重载、独立重导入阶段逐字节一致，共 207 个命名网组、1,013 个网表成员。三板仍有 257 个已放置器件。规则、叠层、板框、过孔、平面和禁区分别核对。既有 V4 盲孔几何规则子集覆盖 142 颗盲孔，检出 0 项违规。

## 布局与布线

### PCB1 主板

基线连接错误集中于 y=1200–1400 mil 的 82 项和 y=600–800 mil 的 63 项，主要涉及 3V3_SYS、GND、1V8_SYS 和相机电源。U19 原区的两面铜箔与器件占用压缩了电平转换和上拉扇出空间。

将 U19 与 R15、R17 重排于底层尾段的同一 I²C 功能区，R17 合入底层。回读核对三颗器件的锚点、角度、方向和逐脚网络。接通 `SYS_I2C_SCL_1V8` 的 R15.1↔U19.3、`SYS_I2C_SDA_1V8` 的 R17.1↔U19.4，把 U19.2、R15.2、R17.2 接入既有 `1V8_SYS` 铜网。重接 U19.1 到既有 L5 地回路，重建 U19.7↔U19.8 的 `LS3_VREF2_EN` 局部跨线。原生 DRC 的 1V8_SYS 少 3 项，SCL/SDA 1.8 V 各少 1 项。

U19 锚点沿板长移动约 459 mil。高侧 3.3 V、EN 的远端偏置和主机总线尚待收口，后续需重核总线长度、电容和时序。编辑器自动分段一条既有 4 mil 的 1.8 V 主干，几何和线宽已对账。R15 的库件名称被物化为隐藏属性，名称与原库绑定一致。

### PCB2 光学桥板

基线 y=200–400 mil 有 61 项连接错误，尾端 y=800–984 mil 有 47 项，VSYS、GND 和 FPGA 电源占主要部分。R9 接通两段 `VSYS` 局部铜路径。

- R5.2↔R8.1，顶层 4 mil，把 R5 支路接到既有 R8/C8/C12 局部铜簇，保存和独立重导入后的原生 net-path 均导通。首批 8 mil 方案触发 MK2 实际槽区的 11.8 mil 净距规则，7 段原试布已全部撤除，复跑回到 232 项连接错误、0 间距错误。修订线路与原生 `e26` 槽区的几何铜边净距为 12.281 mil。
- U4.3↔U4.4，顶层 6 mil，接通同一稳压器的两个 VSYS 焊盘。嘉立创 net-path 对 POLYGON 焊盘返回 unknown，保存与重导入铜箔回读用原生多边形和同层铜边复核正面积接触。整板 232 个连接错误的对象签名无变化，两段结果只计实测局部连通。

R8-C 的 C11 联合重排仍受 VSYS、去耦回流、器件摆放和 MK2 声学约束。R29 的备选位置落在 FPGA 的跨面投影内，留待装配空间确认。桥板器件位置保留原状。 [第三轮研究归档](https://github.com/yfei7131-source/AI-AR-codex-Claude-/tree/cdf14a8e379e9d0be666b307318ac579a12b845d/hardware/research/neon-round3-20261124)

### PCB3 右音频板

基线约 87 项连接错误集中于 y=200–600 mil 的 U11/U10、供电和音频控制区。保持 U11 扇出、RF、声学和板框。在既有底层走廊用 4 mil 折线接通 `AMP_SD_MODE_1V8` 的 J1.P15↔U1.4，实测少 1 项连接错误。既有 L5 地平面对这条线的几何投影连续。充电器 U3 的邻近焊盘、裸露地盘和板边封住现有候选支路，R6/R10 的相关重排仍待释放走廊。第三轮 K5→L9 的云端试验尚缺完整 I²S 连通与固件闭环，主工程沿用 PR #58 引脚映射。

## L2–L3 隔离试验

两份独立原生副本使用 PCB3 本地坐标 (70,1065) mil。将 `2-3` 注册为原生层 ID 15→16，并放置一颗 Ø3.94 mil 孔、Ø9.94 mil 盘的试件。保存、关闭、重开、再导出均核对其仍为 `BLIND` 和 `2-3`。

- **对照件。** 原 L2 GND 平面下新增 `Plane Zone to Via` 与 `Hole to Plane Zone` 两项原生间距违规，规则要求 10 mil。连接错误仍为 130。
- **反焊盘件。** 仅给试孔所在 L2 平面添加开窗。实际铜边到孔盘净距 10.152 mil，原 L2 平面仍为单一连通多边形，原生间距回到 0，连接错误为 130。
- **恢复。** 在对照工程删除试孔和试验规则，另用精确基线原生归档建立恢复副本。恢复副本的 PCB3 原生记录与基线一致，严格 DRC 回到 130 项连接错误、0 间距错误。对照件的全规则接口回读出现数值表示的浮点末位差，净版恢复以归档逐记录比对为准。

试验确认了局部层跨和一个反焊盘实例。主工程继承原叠层及盲孔规则，0.80 mm 二阶 HDI、U11 批量逃线、参考面回流与板厂 EQ 仍需验证。 [第三轮原始试验报告](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/cdf14a8e379e9d0be666b307318ac579a12b845d/hardware/research/neon-round3-20261124/neon-2/hdi/H03_R8_CLOUD_TRIAL_AND_EQ.md)

## 剩余阻断

6 项严格 ERC fatal 均为缺封装。PCB1 的 J2/J3 上板仍缺接口针序、极性、配对件和装配验证，1 项原生网表差异保留。光机、声学、实际重量、RF、阻抗、电气安全实测及板厂制造签核待验。 [PR #56](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/56) · [PR #57](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/57)

## 交付索引

- [可重载嘉立创工程](EVT1-H03-R9-NOT-FOR-FAB.epro2)，SHA-256 `2ed5b0932c51f5995a68fa602dd922cbfb4ef69429cc21e05cea195c69eaae93`。
- [修改前原始 ERC/DRC](logs/before/)、[保存重载后原始 ERC/DRC](logs/after/)和[独立重导入记录](logs/reimport/)。
- [实际连通路径与接触证据](engineering/actual-connectivity-increment.json)、[最终验证](engineering/final-verification.json)和[布局瓶颈分布](engineering/baseline-spatial-bottlenecks.json)。
- [HDI 对照结果](hdi/control/result.json)、[反焊盘结果](hdi/antipad/result.json)和[净版恢复严格 DRC](hdi/rollback-DRC.json)。
- [仓库单元测试原始输出](logs/repository-unittest.stderr.txt)，102 项通过。

