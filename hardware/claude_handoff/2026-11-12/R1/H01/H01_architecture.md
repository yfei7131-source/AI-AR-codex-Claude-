# H01 系统架构 R1（草稿，未冻结）

状态：真实 GitHub 源码两轮均未到手 → F01–F22 逐项映射、GPIO、BLE/媒体协议兼容性均为 **未核对**。下列为硬件侧可独立推进的部分。

## 1. 分块
```
USB-C ─ ESD ─ BQ24072(充电+路径) ─ VSYS ─┬─ 3V3 主轨(EVT-0: LDO；EVT-1: buck-boost) ─ ESP32-S3-WROOM-1-N16R8
1S LiPo + NTC ─────────┘                 ├─ CAM_2V8 / CAM_1V2 / CAM_3V3（三路均受 CAM_PWR_EN 硬件门控）─ DVP 相机
                                          │      └─ CAM_2V8 直接驱动隐私指示灯（固件无法关闭）
                                          ├─ AR 光机电源(DISP_PWR_EN) ─ microLED 光机 + 光波导（真实光学显示，必保留）
                                          └─ BT 经典音频 SoC 子系统(BT_AUD_EN)：HFP/A2DP、麦克风阵列、扬声器功放
ESP32-S3: BLE 控制 + Wi-Fi/BLE JPEG 媒体 + 相机 DVP + 显示 QSPI + I2S 麦克风
```

## 2. AR 光学显示（基线候选，未锁定）
- **基线：JBD 0.13" 单绿 microLED（JBD4UM480P 系列，640×480）光机 + 衍射光波导。** 厂商公开资料称背板自带帧缓存、可直接用 SPI/QSPI 传输显示数据、无需桥接芯片 → 与 ESP32-S3（无 MIPI-DSI）直接匹配，EVT-0 的 J4 QSPI 排针即为此预留。
- 公开功耗参考：JBD Hummingbird 彩色光机典型 0.26 W；Roadrunner I 彩色光机典型 90 mW（2025-12 发布）。单绿光机功耗、引脚、电压轨、初始化序列 **须向 JBD/模组厂索取规格书**，本项目尚无。
- 备选：Micro-OLED（如 Sony ECX336 类 0.23"）+ 棱镜/BirdBath——需并行/MIPI 接口，ESP32-S3 要加 FPGA 或桥接，成本功耗更高，仅作后备。
- 不采用“无显示/仅音频”方案。

## 3. 电源树（EVT-0 R1）
| 轨 | 来源 | 负载 | 门控 |
|---|---|---|---|
| VBUS 5V | USB-C | BQ24072 IN（USB500 限流） | – |
| VSYS | BQ24072 OUT | 3V3 LDO、CAM_2V8 LDO、隐私灯、光机/音频子板 | SYSOFF=运输模式 |
| 3V3 | TLV75733 | ESP32-S3、CAM_1V2 LDO 输入、Q3 | – |
| CAM_2V8 / CAM_1V2 / CAM_3V3 | TLV75528 / TLV75512 / Q3 | 相机 AVDD / DVDD / DOVDD | CAM_PWR_EN（默认下拉=关） |
功耗预算见 `power_budget.csv`（全部为估算，未实测）。

## 4. 关键未决项
1. **GPIO 预算超限**（R-A）。候选：a) 调试串口改用 USB-Serial-JTAG，释放 IO43/44 作传感器 I2C；b) 换四线 PSRAM 模组（N16R2）释放 IO35–37（JPEG 缓冲是否够用须 Codex 确认）；c) 麦克风/扬声器全部交给 BT 音频 SoC，ESP 仅经 I2S 取一路麦克风数据；d) I2C IO 扩展器承接低速 EN/RST。须与 Codex 走 ICR 后定。
2. 通话链路：ESP32-S3 无经典蓝牙，BT 音频 SoC 选型未做（需支持 HFP+A2DP、双麦 ENC、iPhone 路由验证）。
3. 3V3 buck-boost 选型（EVT-1）。
4. 电池：容量/尺寸/保护板/NTC 未定；当前充电电流按约 150 mA 设置，须与电芯规格匹配。
