# EVT-0 R3 · 12 项接口裁决

本表对应原交接 [ICR R2](../../claude_handoff/2026-11-12/R2/H01/ICR_to_Codex.md)。EYE、DevKitC-1 载板和 EVT-0 分别用自己的 profile。针号匹配只回答数字接线，物理层还有电压、上电和光学要求。

| 请求 | 裁决 | 对真实源码的答复、后续证据 |
|---|---|---|
| ICR-01 | 已存在 | 核对 `firmware/main/board.c`、`board.h`、`camera_adapter.c`。按键 GPIO0、XCLK15、SDA4、SCL5、D[0..7]=11/9/8/10/12/18/17/16、VSYNC6、HREF7、PCLK13 共 15 项与 J3 的 DVP 信号一致。EYE 原板 J4 与 EVT-0 的 J3 是不同连接器和供电设计。 |
| ICR-02 | 接受 | `camera_adapter.c` 需要在授权内使能，等待已选模组电源/时钟稳定后初始化；错误、撤销、结束均停止采集、释放摄像引脚并关断。SCCB 上拉随 DOVDD 断电。未选传感器之前，等待值只能作台架初值。H05 先用假负载示波记录掉电残压、XCLK 和反灌。 |
| ICR-03 | 调整硬件 | GPIO3 高有效、下拉默认关闭。R2 的 JP2 强制上电另有绑带采样与处理器管脚争用风险。R3 去掉强制跳线，TP11 只观测。由 CAM_2V8 直接供 D3，10k 下拉和 LED 单支路仍需做开路、欠压和可视度验证。 |
| ICR-04 | 阻塞 | `firmware/main/display_adapter.[ch]` 只接 reviewed sink，宽高 1..256、长度 ceil(w/8)×h，未实现任何 QSPI 厂商命令。主机 `app/hud_bitmap.py` 的 mono1_msb 明确行补位。J4 默认不连接光机，待确切驱动板规格/电平/时序/眼盒图。独立 Halo 评估通路见本目录架构。 |
| ICR-05 | 已存在 / 调整硬件 | `firmware/sdkconfig.defaults` 已设 USB_SERIAL_JTAG，D−19/D+20。R3 43/44 优先给可断开的音频 UART；默认断开以隔离 ROM 启动输出和 J6。R2 提议的同线常电 I²C 与 UART 互斥。N16R8 使用八线 PSRAM，保留 35–37，按独立 16 MB Flash/8 MB OPI profile 编译。 |
| ICR-06 | 接受 | AI 录音接口拟由 S3 在 J5 接 I²S 标准数字麦克风，SCK41/WS42/SD2，首轮目标 16 kHz 单声道 PCM，具体槽宽、位移、时钟极性以麦克风料号定。现有 `mobile/` 和 Web 的手机录音路径继续可用；R3 只登记脚位。电话上行麦克风由 BM83 音频子板采集，独立时钟域。 |
| ICR-07 | 接受 | GPIO1=ADC1_CH0，原理图 R9/R10 各 1 MΩ、C4=100 nF。4.2 V 时节点约 2.1 V，分压耗电 2.1 µA，Rth=500 kΩ、RC=50 ms。拟用校准 ADC1 高衰减、上电待至少 5τ 再采样、与 DMM 比较。高阻漏电、加载误差及温度待测，`firmware/main/core.c` 的 unknown 电量继续有效。 |
| ICR-08 | 接受 / 调整硬件 | `CONFIG_GL_BOARD_AIAR_EVT0_R3` 独立选择。cam_pwr_en=3、vbat_adc=1、mic_sck/ws/sd=41/42/2、audio_uart_tx/rx=43/44；辅助脚位登记不自动开启外设。没有已选光机，不绑定 disp_*；GPIO46 不驱动 J7。GPIO0/3/45/46 重置必须检查绑带。 |
| ICR-09 | 接受 | 所有 profile 持续 privacy_interlock_verified=false。T11/T12 要记录电气和光学指示、单故障、复位及在途撤销；初次实物验证先在封闭台架、已批准的器件组合上评审。T21 拆成默认拒绝和解锁后的真实 JPEG 两步，禁止靠跳线或改布尔量制造通过。 |
| ICR-10 | 接受 | R3 AP 拟在 esp_wifi_start 后 set/get 最大 TX 功率，默认请求 44（11 dBm，1 单位=0.25 dBm）。设置值与读回是驱动配置。厂商表 802.11b 1 Mbps @20.5 dBm 的模组峰值 355 mA；既不能外推本机 11 dBm 实际电流，也不能代表整板峰值。T14/T31 记录波形、跌落、距离、重试和传输时延。 |
| ICR-11 | 调整硬件 | BM83SM1-00AA/DM164152 独立 HFP HF/A2DP。R3 J7 三针双向 UART 和公共地，供电与音频在 EVB 本地。先系统配对/拨接来电，然后连接 S3 控制服务，反序再测；失链、恢复与媒体抢占均待 iPhone。没有新增 call BLE opcode；未来命令及厂商引脚见 H01/audio-interface.md。 |
| ICR-12 | 已存在 / 阻塞 | 256²×1bpp=8192 B；gray8=65536 B，C sink 只接受前者。S3 的 a002/003/004/005 数据合同没有位图写入，HTTP 仅拉取/删除 JPEG。M1 走手机/主机→独立 Halo SDK BLE，按事件刷新与显式关闭，未设 FPS 保证。M3 自研光机待规格、带序号/超时/撤销的下行契约以及功耗/带宽实测。 |

参考：[S3-EYE V2.2 原理图](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-EYE-MB_20211201_V2.2.pdf)、[ESP32-S3-WROOM-1 数据手册表 6-4](https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf)、[ESP-IDF Wi-Fi API](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32s3/api-reference/network/esp_wifi.html)、[ADC 校准](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/adc/adc_calibration.html)。
