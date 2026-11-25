# EVT-1 Rev D1 接口控制 — NOT FOR FAB

逐针权威：NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv、PINMAP_V1_0_FROZEN.csv；连接器：CONNECTOR_PINOUT_REV_D1.csv。

电源：两枚独立受保护 4.2V/110mAh 电池，不直接并联；左 BQ25180 的 SYS 与右受保护电池经 LM66200 选择到 VSYS。BQ25180 替代超出低充电电流推荐范围的 BQ24074。右 BQ25170 充电与负载状态必须按 POWER_SOURCE_REVIEW 审查。TPS63805 产生 3V3_SYS；TPS62840 产生 1V8_SYS（VSET=GND）。各器件 NC、接地、反馈、NTC 与外围以逐针表为准。充电初始化、watchdog、过压/欠压及电芯限值尚需固件和台架验收。

iCE40UP 电源顺序保持 Rev D：VSYS→1V2_FPGA_CORE→100Ω滤波1V2_FPGA_PLL→U4_1V8F使能→1V8_FPGA_IO→10Ω/4.7µF VPP。光机 AVDD 由 D3/CDONE 与 OPT_PWR_REQ 联锁，经原 Rev D RC/二极管网络；保持 NOT FOR FAB，JBD AVDD 值不能由本文件冻结。

FPGA、PCF、TB、Makefile 均与 PR #20 相同。A0/A1 立即写；A2/A3 防撕裂写；A4 OPT_CTRL：bit0 SCAN_EN、bit1 OPT_PWR_REQ、bit2 RAW_ARM。默认 SCAN_EN=0、OPT_PWR_REQ=1。RAW_ARM 仅在已停止扫描后接受，下个 CS 事务镜像两眼并在 CS 上升沿解除；无法独立初始化某一眼。初始化需等 CDONE 及 AVDD 建立 ≥21ms，先停扫描，再发送受 NDA 控制的初始化事务，最后打开扫描；禁止猜测 JBD 内容。

连接器针位和跨板干线继承 Rev D；BM28 电源触点 5A，信号触点 0.3A。VBAT_R_RET/GND 不借信号触点承载峰值电流。跨铰链 FPC 需连续地、供电压降计算、动态弯折寿命和无过孔弯折区审查。实际铜宽和阻抗需由板厂叠层复核。

音频：nRF5340 为唯一 I2S 主机，ESP32 从机；PDM_CLK 仅由 ESP32 产生。MAX98357A WLP 球位已纠正，右 SD_MODE 经69.8k，左右增益接地。nRF 32MHz晶振、RF网络、去耦和SWD在电气表显式连接；原厂参考值与待选项见 SOC_SOURCE_REVIEW。

摄像隐私硬件联锁继承 Rev D：XCLK 活动→CAM_PWR_REQ→LED/电流窗口→相机 LDO。相机 I/O 供电隔离、SCCB 使能、RESET/PWDN 的新审查结论见 AUDIO_TRANSLATOR_SOURCE_REVIEW；最终传感器未知，禁止宣称隐私实测通过。

BLK-JBD-01..05 全部保留：FPC针序、初始化、0x32命令、AVDD/STEP、单眼独立寄存器要求。任何传输模型通过均不替代这些资料。
