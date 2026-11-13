# EVT-0 Core R3 原理图电气审查

R3 默认装配用于限流台架。相机和光机不接，充电关闭。PCB、电池和光学系统均未实测。ECAD 生成源在 `gen/design.py`。名为 `AUDIT_R0_to_R1.md`、`fw_compat_report.md` 的前序记录保留其原始版本语境，R3 以本页与仓库固件为准。

| 器件/网络 | 图上的真实连接、选料 | 验证边界 |
|---|---|---|
| J1/U2/D1 | USB-C 两个 CC 各接 5.1 kΩ 到地。J1 修正外壳 S1 为库内四个同号 SH 焊盘，接地。U2 USBLC6-2SC6 #1/#6 接 D+，#3/#4 接 D−，#2 地，#5 VBUS。U1 GPIO19 是 D−、20 是 D+。 | D1 的具体 5 V TVS 料号、钳位、反向漏电和 ESD 试验未冻结。没有 PD 或 USB 大电流协商。 |
| U3 | BQ24072RGTR #13 IN，#10/11 OUT=VSYS，#2/3 BAT，#8 和 EP17 接地，#15 TD 经 0 Ω 接地使能充电终止；#14 TMR 悬空采用内部默认安全计时；#7 PGOOD、#9 CHG 是开漏。RGT0016C 3×3 mm，0.5 mm 脚距，底部散热盘标称 1.68 mm，库盘 1.7 mm。 | 核对钢网、底部焊盘散热通道与供电压降。对充电与 Wi-Fi 并发的温升没有测量。不得替换为脚 15 有不同功能的变体。 |
| 充电默认态 | 具备 VBUS 时 R35 把 CE 拉高；R36 与 ISET 电阻 R5 均空置。EN1 经 R3 下拉、EN2 接地，默认 USB100。R4=1.6 kΩ 在 TI 规定的 ILIM 编程范围 1.1–8 kΩ 内，此模式采用固定输入限流。TS 仅连接电池 NTC，移除 R8 假温阻位置。 | 加装 R36/R5 前先确认 4.2 V 终止、保护板、NTC 曲线/断短检测、允许充电电流和温度。按 797/890/975 AΩ 以及 5.9 kΩ ±1% 得到 134–167 mA（典型151 mA）编程范围；有效充电电流仍受 USB100、系统负载、热环/DPPM 限制。此电流计算不批准电池使用。 |
| J2/JP1 | 1=电池正，2=NTC，3=负，MP 接地；JP1 用于 BAT 串联测流。 | 商用电池线束无通用针序。核对端子方向、极性、NTC 至负端阻值及断短阈值。拔 JP1 只断电池，插 USB 时 VSYS 仍可上电。 |
| U4 | TLV75733PDBVR #1/#3 接 VSYS、#2 GND、#4 NC、#5=3V3。低电压时无法升压。1 A 表项可见最大压差 425 mV；按此表项至少要求 3.725 V 输入方有 3.3 V 加压差的空间。 | BQ24072 OUT 低 VBAT 且 USB 有效时标称仅约 3.4 V；纯电池时还存在 BAT→OUT 压降。USB100 亦不足以单独供满负荷无线峰值。测量 VBAT、VSYS、3V3、复位和脉冲负载，再确定工作下限；当前无全电量范围承诺。 |
| U1 | U1 两个接地端及 EP41 均接地，#2=3V3。IO35–37 保留给八线 PSRAM。GPIO3 驱动 CAM_PWR_EN，R13 10k 下拉，TP11 仅观察；移除 JP2/R32。GPIO45/46 有外部下拉，46 保留绑带且不接音频使能。 | 实测复位窗口、BOOT、看门狗、EN 时序与天线禁布。R9/R10 1 MΩ / 1 MΩ 到 GPIO1，C4=100 nF，源阻抗约 500 kΩ，RC 约 50 ms；必须校准 ADC 和静态漏电误差。 |
| U5/U6/Q2/Q3 | TLV75528/12 DBV 两路 #1 IN、#2 GND、#3 EN、#4 NC、#5 OUT。U5 随 GPIO3 产生 AVDD=CAM_2V8，U6 EN 由 AVDD 打开。BSS138 Q2 下拉 DMG2305UX Q3 栅，Q3 源接 3V3，漏接 CAM_3V3，R29 上拉栅，默认关断。R19/R20 的 SCCB 上拉在传感器侧 DOVDD。 | 每路核对开/关时序、MOS 源漏、未供电时 DVP/SCCB/时钟反灌电流、电平和输出电容有效容量。关轨前须停钟、将接口置安全态。 |
| D3/R27 | CAM_2V8 → 560 Ω → D3 阳极，D3 阴极接地。WP710A10LID 为 2 mA 档红灯，2.8 V 与典型 1.7 V 时约 1.96 mA。省去独立 LED 门极和白灯对 VSYS 的裕量依赖。 | 指示 AVDD 存在。灯开路或短路仍可能供电，相机通过信号线反灌时亦可能不亮。T11/T12 需物理测量亮度、可见范围、时序和故障行为；固件门禁保持 false。若产品要求任一灯故障即断采集，应先增加独立光/电流检测与关断硬件。 |
| J3 | FH12-24S-0.5SH 是待定底触点连接器，J3 和电压选件 R16/R17/R18 全部 DNP。R2 的 #10=1.2 V、#11=3.3 V 与 Espressif EYE v2.2 参考 FPC #10=1.5 V、#11=2.8 V 不同。 | 不得直接插 EYE 相机。按实购模块逐针落实电压、控制与时序、触点朝向、尾排编号、高/低电平和机械锁紧，再决定外接稳压器或内部 DVDD；R17/R18 互斥。 |
| J4/J5/J6/J7 | J4 DNP，QSPI 仅电气预留。J5 在 MCU 端提供 3V3 I²S 麦克风数据信号。J6 保留 UART0 调试。J7 为独立上电音频 EVB 三针台架口，1 GND，2 由 GPIO43 TX 经 R33 指向 BM83 #29，3 由 BM83 #30 经 R34 到 GPIO44 RX；R33/34 均 DNP。 | 光机电压、FPC、协议、亮度与波导未冻结。装 UART 选件前确认电平/电源先后与线缆，必要时加带断电隔离的转换器，移除串口控制台、外部调试发送端与 I²C 选件 R30/R31。独立 EVB 处理通话音频并本地控制 MFB；没有量产 HOST_WAKE、MFB 和休眠唤醒时序。 |

[TI BQ2407x 引脚、电流和封装](https://www.ti.com/lit/ds/symlink/bq24072.pdf) · [TI TLV757P 压差](https://www.ti.com/lit/ds/symlink/tlv757p.pdf) · [TI TLV755P 引脚](https://www.ti.com/lit/ds/symlink/tlv755p.pdf) · [ST USBLC6](https://www.st.com/resource/en/datasheet/usblc6-2.pdf) · [Kingbright D3](https://www.kingbrightusa.com/images/catalog/spec/WP710A10LID.pdf) · [EYE V2.2 原理图](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-EYE-MB_20211201_V2.2.pdf) · [Microchip BM83 引脚](https://onlinedocs.microchip.com/oxy/GUID-414904F5-364E-4377-B959-9226AD29D6A9-en-US-8/GUID-5FC141CE-AE19-4658-9333-3E22FD2F4681.html)。

**验证复现**。从本目录运行下面的命令。第二条使用独立临时配置和 KiCad 自带的官方库表；Windows 传入实际 `kicad-cli.exe` 路径与 `share/kicad` 目录。

```sh
python gen/gen_kicad.py
python gen/verify_erc.py --cli kicad-cli --share /usr/share/kicad
```

10.0.7 原生 ERC 初次 0 errors / 84 warnings，均因首次便携运行未载入官方封装库。加载官方库表后，在相同检查严重度下 0 errors / 0 warnings。没有排除手工违规项，报告列出 KiCad 默认未启用的规则。生成器单独报告 23 条装配选件提示（DNP 后悬空的相机、显示和 UART 网络），不是实机通过记录。导出的原生网表核对了 84 件、284 个编号引脚与 22 种官方封装，程序比较每个引脚的网络或显式 NC 状态，及每件对应的封装编号集合；比对不检查焊盘尺寸公差、装配方向或电压容限。输入 SHA-256、真实 ERC 报告在 `../../evidence/`；用于 PCB 对照的净表在 `evidence/evt0_core.xml`。本次验证使用 KiCad 8 文件格式、10.0.7 检查器，未在 8.x 程序运行。
