# EVT-1 Rev D 缺陷与修复台账（继承 Rev C `bb87623`）

每一项均给出：Rev C 缺陷 → Rev D 修复（已写入哪些文件）→ 验证证据（`verify_rev_d_electrical.py` 检查号 / 故障注入号）。
"已验证"仅指对交付文件的计算或结构检查；无实物测量，原生 EDA 未执行。

## P0

| ID | Rev C 缺陷 | Rev D 修复 | 修改文件 | 证据 |
|---|---|---|---|---|
| RD-P0-01 | `U6_OPT_AVDD.EN` 由 `1V8_OPT_VDD` 经 RC 充电、仅以 `FPGA_CRESET_B` 钳位：CRESET_B 释放 13.6 ms 后无论 FPGA 是否配置成功都给光机上 AVDD；且所用 VIH/VIL=0.95/0.40 V 并非 TLV755P 数据手册值 | D3 改为低有效 `cdone_vsync_n`（空闲高，每帧 1 µs 低脉冲）；`R_SEQ` 改从 D3 充电，配置期 CDONE 硬拉低 → EN≈1 mV；配置成功且 `OPT_PWR_REQ=1` 才开启；D_SEQ 保留作复位快速泄放；阈值改为 VHI=1.0 / VLO=0.3 V | RTL、TB、PCF、BOM-33/45、PINMAP、NETLIST、JSON | SEQ-01；F05、F06、F12 |
| RD-P0-02 | 右电池电流 `VBAT_R_CELL_P`（J_BTB_R P13）→ U3_R → `VBAT_R_RET`（P3）两次经过 0.3 A 信号触点，而 OR 二极管可让单节电池承担整机峰值（估计 1.0 A）；所谓 "4×3 A MP 屏蔽脚" 在 BM28 上不存在 | J_BTB_L/J_BRIDGE_IN 升级为 `BM28B0.6-30DS/2`，VBAT_R_RET 走 5 A PWR1、GND 走 5 A PWR2；电池/NTC/喇叭改为 M-AUD-R 焊盘；右功放直接由右电池供电，VSYS 不再跨右铰链 | BOM-15/31/40/43/44、CONNECTOR_PINOUT、NETLIST | NET-03；F01 |
| RD-P0-03 | I2S 总线同时被 ESP32（经 1 kΩ "隔离"）和 nRF5340 驱动；nRF5340 PDM 也被列为同一麦克风总线的消费者（第二个 PDM 时钟主机） | nRF5340 为唯一 I2S 主机（BCLK/LRCLK/AMP_DIN），ESP32 改为 I2S 从机，音频经 `I2S_S3_DOUT` 送入 nRF SDIN；ESP32 为唯一 PDM 时钟主机；新增 `U8_AUD_LS2`（SN74AXC4T245）；新增 `AMP_SD_MODE` 控制两颗功放关断 | BOM-04/36/38/47/53、PINMAP、NETLIST、ICD-03 | NET-01、AUD-02；F02、F03 |
| RD-P0-04 | `U4_1V2` 由 `1V8_SYS` 供电，1.8 V I/O 必先于 1.2 V 内核上电，违反 iCE40UP 上电顺序 | `U4_1V2` 输入改为 VSYS；新增 `U4_1V8F`（TLV75518）供 SPI_VCCIO1/VCCIO/VPP/光机 1.8 V，EN 接 VCCPLL（≥1.082 V > VHI 1.0 V） | BOM-32/46、PINMAP、NETLIST、JSON | SEQ-02；F07 |

## P1

| ID | Rev C 缺陷 | Rev D 修复 | 证据 |
|---|---|---|---|
| RD-P1-01 | `IPC_S3_TX` 位于 U8_LS1 Bank1，FPGA 配置期 DIR1=L 时方向反转，与 ESP32 TX 冲突 | 移至 U8_PDM_LS Bank2（固定 B→A）；Bank1 Ch4 两侧 100 kΩ 下拉 | NET-04 |
| RD-P1-02 | U8_LS1 VCCB=1V8_SYS，FPGA I/O 未上电时 B 侧驱动反灌 | VCCB 改为桥板回传的 `1V8_FPGA_IO`（干线 P6），利用 Ioff 隔离；A7 加 100 kΩ 下拉使 FPGA 默认保持复位 | SEQ-02；F16 |
| RD-P1-03 | 摄像头 SCCB 直连常电 SYS_I2C_1V8，摄像头断电时经 ESD 二极管反灌 | 新增 `U8_LS4`（PCA9306，VREF1=受控 DOVDD） | PRIV-02；F09 |
| RD-P1-04 | CAM_RESET_N/CAM_PWDN 经 U8_CAM_ISO2 B6/B7，但无任何主机 GPIO 驱动 | RESET_N=DOVDD RC 上电复位，PWDN=10 kΩ 下拉；B6..B8 接地 | PRIV-02 |
| RD-P1-05 | 隐私 LED 在左板低边串 R_LIMIT，桥板 LED 阴极无回流针 | R_LIMIT 移到高边，阴极接桥板本地 GND | PRIV-02；F15 |
| RD-P1-06 | `U5_LED2V8.EN` 无驱动源（33 个合法 GPIO 已全部占用） | XCLK 活动检测（330 Ω + RB521S-30 + 100 nF + 100 kΩ）：无 XCLK → LED 灭 → 摄像头断电（约 23 ms） | PRIV-02 |
| RD-P1-07 | 右功放 SD_MODE 用 100 kΩ → 0.90 V，内部下拉 −20% 时仅高于 0.77 V 门限约 30 mV | 改 69.8 kΩ → 0.913–1.195 V（含 VDD ±5%） | AUD-01；F04 |
| RD-P1-08 | GPIO45（VDD_SPI 启动配置脚）/GPIO43（ROM UART TX）在新音频拓扑下若接输入会被转换器驱动 | 重映射：GPIO43=I2S_S3_DOUT 出、GPIO44=BCLK 入、GPIO17=LRCLK 入、GPIO45=PDM_CLK 出 | NET-06；F08 |
| RD-P1-09 | 光机初始化（BLK-JBD-02）在 RTL 中没有任何通道；上电即开始扫描 | 0xA4 OPT_CTRL（SCAN_EN 默认 0、OPT_PWR_REQ 默认 1、RAW_ARM）+ 单次 RAW 透传窗口；不预设任何 JBD 命令内容 | RTL-01、RTL-02；TB R1–R4（未执行） |
| RD-P1-10 | VBUS/USB 网络、ESD、喇叭、摄像头模组在 BOM 中缺失 | BOM-50..54，MPN 标 `MPN_TBD`，不编造型号 | NET-00 |

## P2

| ID | 内容 | 修复 |
|---|---|---|
| RD-P2-01 | 隐私窗口下限 0.878 V 低于 LDO VHI 1.0 V（EN 上拉源为 V_INA_OUT） | 分压改为 33.2k/32.4k/32.4k → 窗口 [1.091, 2.182] V；健康 LED 2.59–4.59 mA 位于窗口内（PRIV-01；F11） |
| RD-P2-02 | BM28 深度、UWG30 封装尺寸、TLV755 DQN 焊盘间距与公开资料不符 | 1.70 mm / 2.15×2.55 mm / 0.65 mm |
| RD-P2-03 | 多个 Datasheet_URL 指向无关文档，状态列全部宣称 `VERIFIED_FULL_DATASHEET` | 改为 `URL_TBD (...)` 或正确 TI 链接；状态列按本轮实际复核情况重新分级 |
| RD-P2-04 | ICD 声称 VSYS=3.5–4.4 V | 电池供电时为 2.8–4.4 V；若 JBD 需 3.3 V AVDD，VSYS<3.6 V 时失稳（写入 BLK-JBD-04） |

## 未关闭项（不得视为通过）
- **RTL-03**：iverilog/yosys/nextpnr/icetime 未执行，Rev D Verilog 未编译。
- **MASS-01**：补入 Rev C 遗漏项后标称 41.0 g（TR90 外壳 41.6 g），超出 40 g；需满足机构质量上限（见 KIMI 手册 §6）。
- **BLK-JBD-01..05**、**UNV-RevD-02**（摄像头 PWDN 时序取决于最终传感器）。
