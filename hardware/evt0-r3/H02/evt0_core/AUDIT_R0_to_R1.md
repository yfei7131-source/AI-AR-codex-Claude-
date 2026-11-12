# EVT-0 核心验证板 R0→R1 审计（2026-11-11）

依据：器件数据手册引脚定义（凭已知手册内容核对，未在线重读 PDF）+ KiCad ERC 引脚类型规则。**真实固件源码本轮仍未收到，GPIO 映射未对固件核对。**

## 已修复（design.py 中标 R1-Fx）
| ID | R0 问题 | 后果 | R1 修复 |
|---|---|---|---|
| F1 | J1 四个 VBUS 脚、U3 两个 OUT 脚均为 power_out；GND 无驱动源 | KiCad ERC 必报 3 类错误（已用新自检在 R0 上复现：3 errors） | VBUS/GND 连接器脚改 passive；U3.11 改 passive；VBUS、GND 加 PWR_FLAG |
| F2 | 隐私灯 Q1=2N7002，Vgs(th) 最大 2.5V，栅压仅 2.77V | 批次差异下相机上电而隐私灯不亮（安全缺陷） | Q1→BSS138（逻辑电平，SOT-23 同脚位） |
| F3 | 相机 DOVDD 经 R17 接常电 3V3；SCCB 上拉接常电 3V3 | 相机“断电”时 IO 域仍带电、经上拉/ESD 管倒灌；硬件隐私门控不完整 | 新增 Q2/Q3/R29/C20 高边开关 → CAM_3V3（受 CAM_PWR_EN 控制）；R17 改接 CAM_3V3；R19/R20 上拉改接 CAM_DOVDD；新增 TP10 |
| F4 | 生成器自检只查连通，不查引脚类型 | 自检“0 错误”掩盖 ERC 问题 | gen_kicad.py 增加 ERC 类规则（多 power_out、power_in 无驱动、NC 脚接网等）并导出 pinmap_hw.csv |

## 核对无误（未改）
ESP32-S3-WROOM-1 41 脚→GPIO 对应；IO35–37（八线 PSRAM）悬空；IO19/20=USB D−/D+；IO45/IO46 下拉；BQ24072RGT 16 脚定义及 EN2/EN1=0/1（USB500）；TLV757P/TLV755P SOT-23-5 脚位；USBLC6-2SC6 脚位；24P DVP FPC 为常见 OV2640/OV5640 模组顺序（**仍须对所购模组图纸核对正反序**）。相机/麦克风 GPIO 与 ESP32-S3-EYE 参考板一致（仅作为合理默认，不代表与 Codex 固件一致）。

## 未修复、仅登记的风险
- R-A **GPIO 已用尽**：WROOM-1-N16R8 可用脚全部占用，IMU/触摸/扬声器 I2S/BT 音频 SoC 控制口无脚可用。方案见 H01 §4。
- R-B 3V3 用 LDO：电池低于约 3.5V 时 3V3 跌落（具体压差须按 TLV757P 手册在峰值电流下核算）；EVT-1 改 buck-boost。
- R-C R4/R5、NTC 窗口、D1/D2/D3 具体料号为 VERIFY/TBD。
- R-D 相机断电前固件须把 XCLK/SCCB/数据脚置高阻或低，否则经 ESD 管倒灌（见 H01/ICR_to_Codex.md ICR-02）。
- R-E 显示接口按 QSPI 预留，JBD 光机的真实引脚、电压轨、时序须凭厂商规格书确认。
