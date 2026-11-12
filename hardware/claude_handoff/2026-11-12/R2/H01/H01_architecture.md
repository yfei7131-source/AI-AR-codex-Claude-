# H01 系统架构 R2（草稿，未冻结）

依据：R1 工程 + Codex 交接包（**仅含 `board.c/.h` 节选和接口摘要 `00_CLAUDE_先读_软件接口交接.md`；完整源码 ZIP 未生成/未上传**）。凡标「摘要」者来自交接摘要，未读源码。

## 1. 分块（R2）
```
USB-C ─ ESD ─ BQ24072(充电+路径, pin15=TD→GND) ─ VSYS ─┬─ 3V3(EVT-0 LDO / EVT-1 buck-boost) ─ ESP32-S3-WROOM-1-N16R8
1S LiPo+NTC ─ JP1(电流测量/电池断开) ─┘                 ├─ CAM_2V8 / CAM_1V2 / CAM_3V3（CAM_PWR_EN 硬件门控）─ DVP 相机
                                                        │      └─ CAM_2V8 → 隐私灯（纯硬件）
                                                        ├─ AR 光机电源(DISP_PWR_EN) ─ microLED 光机 + 光波导【接口待厂商规格书】
                                                        └─ 经典蓝牙音频 SoC(BT_AUD_EN)：HFP/A2DP【未选型】
```

## 2. 本轮确定的结论
1. **充电器保持 BQ24072RGTR，不换料。** 15 脚是 TD，R6 改 0R 接 GND（终止使能）。TI 引脚表：'72/'73 pin15=TD，'74=ITERM，'75/'79=SYSOFF；TD 仅启动时采样、内部约 285 kΩ 下拉、不得悬空。BQ24075/79 不能直接替换（OUT 稳压 5.5 V，会抬高 VSYS 和 LDO 热耗）。
2. **BQ24072 没有运输模式。** EVT-0 用 JP1 断开电池；量产运输模式列为 EVT-1 充电器选型条件【待定】。
3. **相机/按键 GPIO 与固件参考 profile 逐脚一致**（15 个字段全部 match，见 `H02/evt0_core/fw_compat_report.md`）。固件 `gl_board` 结构体只有 18 个槽位，**没有** CAM_PWR_EN、显示、麦克风、电量、BT 音频字段 → 14 个硬件网络在固件侧无定义（ICR-08）。
4. **未改固件时，自研板相机永远不上电**（GPIO3 无人驱动，R13 下拉）。R2 增加 JP2+R32 台架跳线，仅供未改固件联调；隐私灯仍由 CAM_2V8 硬件驱动，联锁未被旁路。
5. **iPhone 约束决定音频架构**：iOS 对非 MFi 设备不开放经典蓝牙数据通道，手机只能经 BLE 控制眼镜、经 HFP/A2DP 传音频。因此经典蓝牙音频 SoC 必须能独立完成 HFP/A2DP，手机 App 对它的控制只能经 ESP32-S3 BLE 转发 → ESP↔音频 SoC 至少需要 EN + 一条控制/状态链路（I2C 优先，节省 GPIO）。用户在 iPhone 上会看到两个蓝牙身份（BLE 外设 + 经典音频设备），配对流程需 Codex 设计（ICR-11）。
6. **AR 显示仍阻断**：ESP32-S3 无 MIPI-DSI；J4 的 QSPI 只是按 JBD 公开宣传预留，光机引脚/电压/时序无规格书，不冻结。帧缓存量级：640×480×1bpp = 38.4 kB，8bpp = 307 kB，八线 PSRAM 8 MB 可容纳（算术结论，非实测）。

## 3. 电源树（R2）
| 轨 | 来源 | 负载 | 门控 |
|---|---|---|---|
| VBUS | USB-C | BQ24072 IN（EN2/EN1=0/1 → USB500） | – |
| VSYS | BQ24072 OUT（'72：跟随电池电压） | 3V3 LDO、CAM_2V8 LDO、隐私灯、光机/音频子板 | 无（JP1 手动） |
| 3V3 | TLV75733 | ESP32-S3、CAM_1V2 LDO、Q3 | – |
| CAM_2V8/1V2/3V3 | TLV75528 / TLV75512 / Q3 | AVDD / DVDD / DOVDD | CAM_PWR_EN（默认关） |

**LDO 压差结论**：电池供电时 VSYS = VBAT − I×R(BAT→OUT)；3V3 维持额定值的条件是 VBAT > 3.3 V + LDO 压差 + 路径压降。Wi-Fi 发射峰值下，电池大约 3.5 V 以下 3V3 开始跟随下跌，可用电池容量被截掉一段。EVT-0 仅作台架验证可接受（T14 实测定界）；**EVT-1 必须换 buck-boost**【器件待选，压差/峰值电流数值须重读手册】。

## 4. GPIO 预算（WROOM-1-N16R8 已满）与 R3 方案（待 Codex 答复 ICR-05/08 后才改图）
| 动作 | 释放/用途 | 依赖 |
|---|---|---|
| 控制台改 USB-Serial-JTAG | GPIO43/44 → 常电传感器 I2C（IMU/触摸/ALS/IO 扩展器/音频 SoC 控制）；R2 已预留 R30/R31 上拉位（DNP） | ICR-05 |
| I2C IO 扩展器承接 DISP_RST 等慢速信号 | 释放 GPIO14 → 传感器中断/唤醒 | 扩展器【待选】 |
| GPIO45/46 保持低速使能输出 + 下拉 | 不用于 UART/I2C（上电绑带须为低） | – |
| 相机 SCCB(GPIO4/5) 不与常电传感器共用 | 上拉接受控的 CAM_DOVDD，相机断电时总线失效 | – |

## 5. 未决项
光机规格书/EVK；经典蓝牙音频 SoC 选型；3V3 buck-boost；电池（容量/保护板/NTC）；IMU/触摸/ALS；F01–F22 逐项定义（`docs/FEATURES_F01_F22.md` 未到手）。
