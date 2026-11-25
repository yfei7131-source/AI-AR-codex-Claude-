# KIMI 执行手册 — EVT-1 Rev D（V1.1，继承 Rev C `bb87623`）

**输入优先级**：`NETLIST_ELECTRICAL_CONNECTION_REV_D.csv` > `CONNECTOR_PINOUT_REV_D.csv` > `TRANSLATOR_BANKS_REV_D.json` > `PINMAP_V1_0_FROZEN.csv` > `BOM_V1_0_FROZEN.csv` > `ICD_FPGA_HOST_OPTICS_SPEC_REV_D.md`。
文件名中的 `FROZEN` 是沿用的旧标签，以便 Git 历史连续，不代表已冻结。工程状态为 `NOT_FOR_FAB`。

## 1. 原理图任务（嘉立创 EDA 专业版）

1. 按 NETLIST 逐行连线。`Role` 字段含义：DRV 推挽驱动；RCV 输入；SRC/SINK 电源；DRV_OD 开漏；DRV_TRI_SLOT 分时三态；BIDIR_DIRCTL 方向受 DIR 控制；PULLUP/PULLDOWN 上下拉；TIE 固定电平；NC 不连接。
2. 新增器件：`U4_1V8F` TLV75518PDQNR、`U8_AUD_LS2` SN74AXC4T245RSVR、`U8_LS4` PCA9306DQER、`RN_CAM_REQ`、`RN_AUD_R`。
3. 修改器件：J_BTB_L 与 J_BRIDGE_IN 改为 `BM28B0.6-30DS/2-0.35V(53)`；U4_1V2 的 IN 改接 VSYS；R_SEQ 改从 D3 取电；R_LIMIT 移到高边；R_SDR 改为 69.8 kΩ；窗口分压改为 33.2k/32.4k/32.4k。
4. 所有 SN74AXC8T245 与 SN74AXC4T245 的 OE 接 GND，未用通道按 TRANSLATOR_BANKS 处理（接地或悬空）。
5. **不得自行编造的引脚号**：SN74AXC4T245 RSV、PCA9306 DQE、nRF5340-CMAA 各球位。请从 TI 和 Nordic 的公开数据手册映射；nRF5340 的 I2S/UARTE/GPIO 可通过 PSEL 分配到任意 GPIO（任务 KIMI-RevD-04）。
6. MAX98357A WLP 球位沿用 Rev C 字母，需对照 ADI 封装图复核。

## 2. PCB 任务（6 层 2+2+2 HDI，继承 Rev C 叠层）

- M-MAIN-L：J_BTB_L 位于 Y=42.40（1.70×6.55 mm，为估算值，需按 Hirose 图纸核对）；MK1_L 移到 Y=36.90，声孔随之移动；U8_AUD_LS2 位于 BOTTOM (2.90, 43.60)；U8_LS4 位于 TOP (1.80, 13.40)；RN_CAM_REQ 位于 TOP (1.40, 34.00)。
- M-OPT-BRIDGE：J_BRIDGE_IN 位于 Y=3.60；U4_1V2 位于 (1.40, 7.60)，U4_1V8F 位于 (2.80, 7.60)。
- M-AUD-R：J_BTB_R 坐标不变（深度改为 1.70 mm）；新增电池焊盘 TP_BAT_R_P/N、TP_NTC_R，以及喇叭焊盘 SPK_R±。
- FPC_BRIDGE：VBAT_R_RET 与 GND 线宽 ≥0.5 mm，贯穿两个铰链；L2 为整片地；host_sck 两侧布置 GND 保护针（P7/P9）。完成布线后计算铰链段 IR 压降（当前未验证）。
- XCLK 检测支路的 330 Ω 电阻紧贴 GPIO46 走线放置，分支长度 ≤2 mm。

## 3. Codex / CI 任务

```
make -C 03_FPGA_RTL all          # iverilog 仿真 → yosys → nextpnr-ice40 --up5k --package uwg30 → icetime
python3 05_Verification_Scripts/verify_rev_d_electrical.py
```

通过判据：输出 `VERILOG_TB_RESULT: PASS`（包含 Rev D 自检 R1–R4）；clk_48m 时序 ≥48 MHz；在 host_sck / host_cs_n 域的时序报告中确认 RAW 组合路径；验证脚本无 FAIL。旧脚本 `verify_v1_0_engineering.py` 将 Rev C 的缺陷编码为通过条件，已退役，仅保留在 `99_RevC_Baseline/`。

## 4. 固件约束（ESP32 / nRF5340）

- ESP32 I2S 配置为**从机**（BCLK=GPIO44 输入，LRCLK=GPIO17 输入，DOUT=GPIO43 输出）；PDM_CLK 走 GPIO45。
- FPGA 配置流程：GPIO0 置低（DIR1=L）→ 拉低再释放 CRESET_B → 发送比特流 → GPIO21 变高后再补发 ≥49 个 SCK → GPIO0 置高。
- 光机初始化流程见 ICD §3；IMU FSYNC 配置为下降沿；GPIO21 下降沿中断。
- nRF5340 UART RX 使能上拉；不需要音频时将 AMP_SD_MODE 拉低。

## 5. 仍需原厂/NDA 资料（不得虚构）

BLK-JBD-01..05、摄像头传感器型号（UNV-RevD-02）、J_CHG / ESD / 喇叭选型（OPEN-RevD-03）。

## 6. 40 g 质量收敛（MASS-01 = OPEN）

| 项目 | Rev D 估算 | 收敛上限 |
|---|---|---|
| 前框 + 铰链支架 | 10.6 g | ≤9.8 g |
| 单侧镜腿外壳（PA12，0.6 mm 壁厚） | 2.36 g | ≤1.9 g |
| 全部 FPC + 补强板 | 0.40 g | ≤0.35 g |
| 紧固件、胶、泡棉、网布 | 0.50 g | ≤0.40 g |
| 整机 | 41.0 g（TR90 方案 41.6 g） | 39.13 g + 0.5 g 余量 ≤40 g |

电子部分在本版仅增加 0.03 g，单靠电气改动无法收敛到 40 g。电池采用 Config B（GRP220550）属于续航与质量之间的产品决策，其实际质量须先称重确认后再写入账目。
