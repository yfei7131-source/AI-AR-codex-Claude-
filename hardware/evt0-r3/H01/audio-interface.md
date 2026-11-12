# F03 · 独立通话子系统

选择 Microchip BM83SM1-00AA（独立 DM164152 EVB 作首台验证），目标为 HFP Hands-Free，iPhone 为 Audio Gateway。A2DP Sink 承接手机播报，不承载双向通话。EVB 在 Embedded 模式可先用本地按键测 F03；需外部命令时，使用该硬件/固件匹配的 Host 模式并关掉 EVB 原有主控的 UART 输出。ESP32-S3 维持独立 BLE 业务。由音频板负责 HFP 麦克风、音频放大和扬声器，J7 不传 PCM、USB、扬声器功率或充电电流。[Microchip BM83](https://www.microchip.com/en-us/product/bm83)、[DM164152 EVB](https://www.microchip.com/en-us/development-tool/dm164152)。

| 主板 R3 J7 | BM83 模组引脚 | 设计动作 |
|---|---|---|
| 1 GND | 16/50 GND | 共信号地；EVB 按原厂方案自行供电 |
| 2 ESP_TX，GPIO43 | 29 P8_6/UART_RXD | 0Ω 串联默认不装；仅显式选择 UART 的装配变体才接 |
| 3 ESP_RX，GPIO44 | 30 P8_5/UART_TXD | 同上；双向电平/输入漏电/掉电反灌经核实后装跳线或电平转换器 |

BM83 的 #23 BAT_IN 允许 3.2–4.2 V，#24 SYS_PWR/#25 VDD_IO 属内部电源，不与主板 3V3/VSYS 相连。#26 MFB 用于本地上电/唤醒，#49 P0_0 在 Host 模式可通知主机唤醒，三针 UART 仅适用于双方已唤醒的台架。穿戴版需要为这些信号补硬件和电源域审查。GPIO46 保持绑带释放；GPIO43 可能出现 ROM 启动输出；不要同时接调试 UART 和 I²C 上拉。UART 电平需双向核规格与电源顺序，不能仅凭插针间距接线。EVB 提供人声采集与输出；自研子板可从 BM83 的 #13/14/15 麦克风节点和 #6/7/8 模拟音频节点按原厂参考做声学设计。开放式单元的功放/阻抗/限幅另测。[模块引脚](https://onlinedocs.microchip.com/oxy/GUID-414904F5-364E-4377-B959-9226AD29D6A9-en-US-8/GUID-5FC141CE-AE19-4658-9333-3E22FD2F4681.html)、[UART 唤醒与时序](https://onlinedocs.microchip.com/oxy/GUID-414904F5-364E-4377-B959-9226AD29D6A9-en-US-8/GUID-694950A7-062D-4AB6-A7D7-3832E720743F.html)。

**主机控制合同（待实现）。** 首轮接听/挂断/音量依赖系统通话 UI 或 EVB 按钮。第二轮明确记录模块 firmware/Config Tool/SPKcommandset 版本，用已验证的 UART 命令分别查询链路、来电与通话状态、接听、挂断、音量设置；动作需收到状态改变才算成功。重连先查询状态，悬而未决的接听/挂断不自动重发。BLE v1/v2 既有 opcode 不扩义，产品如需要转发上述事件，先定义独立带版本、请求 ID 和能力协商的服务。电池电量来自校准电量计或 ADC；USB 供电 EVB 的数值无法替代眼镜电量。

**实机顺序。** 先将 BM83 与系统蓝牙配对并接通双向电话，再用 iOS 应用选择 S3 BLE。互换配对顺序，测试挂断后 A2DP 播报恢复、来电抢占、断电重连、设备遗忘与媒体 AP 并发。一条链路断开时独立显示其状态。记录路由名称、音频方向、单次按键对应的实际通话状态与音频恢复用时。当前无实体测试结果。
