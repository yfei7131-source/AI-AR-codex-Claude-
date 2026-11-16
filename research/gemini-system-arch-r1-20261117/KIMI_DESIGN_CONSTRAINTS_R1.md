# 智元跃动 AI/AR 智能眼镜 V1.0 — KIMI 嘉立创 EDA 专业版 R1 硬性设计约束

**适用范围**：左镜腿主控板 (`M-MAIN-L`)、鼻梁光学桥接刚柔板 (`M-OPT-BRIDGE`)、右镜腿音频板 (`M-AUD-R`)  
**严格遵循文件**：`BOM_V1_0_FROZEN.csv` (45 位号)、`PINMAP_V1_0_FROZEN.csv` (45 行全引脚)、`ICD_FPGA_HOST_OPTICS_SPEC_REV_C.md`、`EVT1_SYSTEM_ARCH_R1.md`

---

## 1. 6 层 2+2+2 Any-Layer / Stacked-VIPPO HDI 制造约束（严禁降级）
1. **叠层厚度 (`0.598 mm` 裸板 / `0.628 mm` 含阻焊)**：`L1(30μm) - PP1(55μm) - L2_GND1(18μm) - PP2(68μm) - L3_SIG1(18μm) - CORE(220μm) - L4_PWR(18μm) - PP3(68μm) - L5_GND2(18μm) - PP4(55μm) - L6(30μm)`。
2. **线宽/线距与孔径**：最小线宽/线距 **`50 μm / 50 μm` (`2 mil / 2 mil`)**；激光微盲孔 **`75 μm` 孔径 / `180 μm` 焊盘**（铜浆塞孔电镀盖帽 VIPPO）；核心埋孔 `200 μm / 400 μm`。
3. **细间距 BGA/WLCSP 逃线规则**：
   - `U11_BLE (nRF5340-CMAA-R7, WLCSP-95, 0.35 mm pitch)` 与 `U2_FPGA (iCE40UP5K-UWG30ITR, 0.40 mm pitch)` 内排焊球**必须**采用 `L1 -> L2 -> L3` 叠孔 VIPPO 逃线，严禁使用普通通孔或降级为 4 层板。
   - `U1_HOST (ESP32-S3-PICO-1-N8R8)` 底部中央 `4×4 mm` 散热焊盘 (`Pin 57`, `X=2.1..6.1, Y=7.0..11.0 mm`) 背面严禁放置 `U8_LS1` / `U8_CAM_ISO1` 等器件，专留阵列散热 VIPPO 直连 `L2/L5` 地平面。

## 2. 原理图关键电气防呆与禁止事项
1. **光机 `AVDD_OPT_BIAS` 联锁 (`D3` 极性待与 `Rev D1` 最终签核)**：
   - 按 `EVT-1 R1` 默认基线，`U2_FPGA Ball F3 (CRESET_B)` 接 `10 kΩ` 下拉，`Ball D3` 经 `D1 (RB521S-30) + R_CHG=10Ω` 驱动 `C_HOLD=22nF || R_BLEED=2.2MΩ` 接 `U6_OPT_AVDD.EN`，并由 `D_RST` 钳位至 `CRESET_B`、`D_VDD` 钳位至 `1V8_OPT_VDD`；**若最终确认采用 `Rev D1` `D3` 低脉冲逻辑，KIMI 必须改接 `C_AC=10nF` 交流耦合负边沿电荷泵，严禁直接接入正向峰值保持电路！**
2. **主控与电平转换防呆**：
   - `ESP32-S3 Pin 46 (VDD3P3_CPU)` 及 14 个内部 Flash/PSRAM/XTAL 禁用脚（`28, 30..35, 38..42, 53..54`）严禁引出。
   - `U2_FPGA Ball F1 (SPI_SO / host_qio[1])` 必须接入 `U8_LS1` **Bank 1 (`Ch1`, `DIR1 = QSPI_DIR1_EN`)**；`Ball C1 (SPI_SS_B)` 接 `10 kΩ` 下拉；`Ball B2 (VCCPLL)` 必须接 **`100 Ω + 4.7 μF + 100 nF`** 滤波。
3. **跨板连接器与射频净空**：
   - `J_CAM`、`J_BTB_L`、`J_BRIDGE_IN` 统一采用 **24-Pin `BM28B0.6-24DS/2-0.35V(53)`**，`J_BTB_L Pins 22..24` 与 `J_BTB_R Pins 10..12` 1:1 走通 3 线立体声 I2S；`J_DISP_L` (`Y=4.20mm`) 与 `J_DISP_R` (`Y=14.80mm`) 保持等长 `5.30 mm` ($\Delta L \le 0.20\text{ mm}$)。
   - `M-MAIN-L (Y=0..4.2mm)` 与 `M-AUD-R (Y=0..4.0mm)` 射频净空区全层挖空铺铜，仅允许放置 `ANT1` / `ANT2_BLE`。
   - **JBD 原厂资料缺失项 (`BLK-JBD-01..04`) 未签核前，暂不投板光机转接 FPC，且 `U6_OPT_AVDD` 保持 `2.8V/3.3V` 共封装待定状态。**
