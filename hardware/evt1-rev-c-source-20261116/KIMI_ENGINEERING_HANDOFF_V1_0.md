# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 — EVT-1 Rev C KIMI (嘉立创EDA) 与 Codex (GitHub CI) 工程交接手册

**工程版本**：`V1.0-EVT1-RevC-PR19-CrossTableVerified-20261116`  
**Git 分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严格保护 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）  
**主控与音频冻结架构**：[Espressif `ESP32-S3-PICO-1-N8R8`](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf) (左镜腿 Wi-Fi/DVP/AI 主控) + [Nordic `nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) (右镜腿 BLE 5.4 LE Audio 协处理器与单主 I2S 混音器) + [Lattice `iCE40UP5K-UWG30ITR`](https://www.micro-semiconductor.com/datasheet/10-ICE40UP5K-MDP-EVN.pdf) (鼻梁双目 QSPI 桥接 FPGA) + `2x ADI MAX98357AEWL+T` (数字 I2S 功放)

---

## 1. 本轮跨表一致性审查与 40g 高密度硬件架构闭环

1. **BOM (45 位号) $\leftrightarrow$ PINMAP (40 行全引脚) $\leftrightarrow$ ICD (5 大总线) 100% 一致性修正 (`CHK-07`)**：
   - **修复 `J_CAM` 与 `J_BTB_L` / `J_BRIDGE_IN` 16-Pin 信号溢出**：将 `BOM-05 (J_CAM)`、`BOM-15 (J_BTB_L)`、`BOM-31 (J_BRIDGE_IN)` 由 16-Pin 升级为 **24-Pin [Hirose `BM28B0.6-24DS/2-0.35V(53)`](https://www.hirose.com/en/product/document?clcode=CL0673-5043-0-51&productname=BM28B0.6-16DS/2-0.35V(51)&series=BM28&documenttype=Catalog&lang=en&documentid=D49354_en)**（`1.50 × 5.50 × 0.60 mm`），完整承载摄像头 19 路信号+5 路屏蔽地及跨鼻梁 24 路干线信号，并在 `PINMAP_V1_0_FROZEN.csv` 与 `ICD_FPGA_HOST_OPTICS_SPEC_REV_C.md` 中给出逐针定义。
   - **新增双目光机硬件上电时序门控 LDO `U6_OPT_AVDD` (`BOM-45`)**：在 `M-OPT-BRIDGE` 背面 (`X=2.10, Y=12.20 mm`) 配置 [TI `TLV75528PDQNR`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)（共封装兼容 `TLV75533PDQNR`），由 `U2_FPGA Ball D3 (CDONE)` 经 $100\text{ k}\Omega + 100\text{ nF}$ ($\tau = 10\text{ ms}$) RC 延时控制 `EN`，硬件确保 `1V8_OPT_VDD` 稳定且 FPGA 配置完成后延时 $\ge 3.5\text{ ms}$ 才开启 `AVDD_OPT_BIAS`（Pin 9），断电时通过内部 $120\ \Omega$ 主动放电避免面板闩锁。
   - **补齐 `ESP32-S3-PICO-1` 全部 57 脚与单主 I2S 混音拓扑**：在 `PINMAP_V1_0_FROZEN.csv` 完整列出 `U1_HOST` 1..57 脚，明确由 `nRF5340-CMAA` 作为唯一 `1.8V` 功放 I2S Master 驱动 `U10_AMP_L/R`，接收 `ESP32-S3` 本地 TTS I2S 输入并数字混音，彻底杜绝双主控总线冲突。
2. **保留并验证 FPGA 核心方案 (`evt1_ar_display_fpga_bridge_rev_c.v`)**：
   - 保留 `3x SB_RAM40_4K`（256 字 × 34-bit）格雷码异步 FIFO、`4x SB_SPRAM256KA` 双目独立帧存、`2x SB_RAM40_4K` 乒乓行缓存、`60.000 Hz` (`800,000 clks`) 帧率、`row_cnt=10 -> next_row=11` 活跃行预取防撕裂保持 (`tear_row_holdoff`)，以及 `fifo_not_empty_q`、`s1_diff_10_q`、单调递增 `pf_addr_q` 等 `48.000 MHz` 关键路径优化。

---

## 2. 面向 40g 目标的 6 层 HDI、主副板、FPC、结构与散热约束

| 预算与约束类别 | 工程设计参数 | 验证结果 / 约束门限 |
| :--- | :--- | :--- |
| **6 层 2+2+2 Type-III HDI 叠层** | `L1(30μm) - PP1(55μm) - L2_GND1(18μm) - PP2(68μm) - L3_SIG1(18μm) - CORE(220μm) - L4_PWR(18μm) - PP3(68μm) - L5_GND2(18μm) - PP4(55μm) - L6(30μm)`，总板厚 **`0.598 mm`**（含阻焊 `0.628 mm`） | 线宽/线距 `50/50 μm`；激光微盲孔 `75/180 μm` 铜浆塞孔叠孔 VIPPO（满足 `0.35 mm` pitch `nRF5340` 与 `0.40 mm` pitch `iCE40UP5K` 逃线） |
| **三板尺寸与 3D Z 轴包络** | 左主控板 `M-MAIN-L`：`5.80(局部8.20) × 46.00 mm`，Z 堆叠 **`2.49 mm`** $\le 3.20\text{ mm}$<br>鼻梁板 `M-OPT-BRIDGE`：`4.20 × 22.00 mm`，Z 堆叠 **`2.41 mm`** $\le 2.80\text{ mm}$<br>右音频板 `M-AUD-R`：`5.20 × 34.00 mm`，Z 堆叠 **`1.63 mm`** $\le 3.00\text{ mm}$ | 全 45 位号器件含 BTB 插合 FPC+补强板附加高度 (`+0.32 mm`) 零超限、零重叠、RF 净空区零侵入 |
| **动态转轴与桥接 FPC 约束** | `FPC_CAM_L` / `FPC_HINGE_R`：2 层 `0.12 mm` 压延铜聚酰亚胺，设计弯折半径 **`1.80 mm`** $\ge 1.50\text{ mm}$（IPC-2223 动态标准，弯折环长 `6.50 mm`）<br>`FPC_BRIDGE`：2 层 `0.12 mm`，设计弯折半径 **`2.00 mm`** | 动态弯折区仅走单层压延铜线并做泪滴补强，严禁在弯折区放置过孔或元器件 |
| **整机质量、重心与双轨电池** | 整机预估总重 **`34.75 g`**（较 `40.0 g` 留有 **`5.25 g` 裕量**），左右质量差 **`0.36 g`**（$\le 0.80\text{ g}$），重心 **`Y = 35.92 mm`**（位于 `[35.0, 65.0] mm` 鼻托-耳廓舒适区间）<br>双轨目录电芯：Config A [Grepow `GRP3911040`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) (`2×110mAh = 0.814Wh`，续航 `3.24h`) / Config B `GRP220550` (`2×47mAh`，适配 $\le 6.0\text{ mm}$ 超细直镜腿) | 实测质量/重心/放电曲线在首件回板前标记为 `UNVERIFIED`；壳体干涉标记为 `BLOCKED` (`BLK-RevC-02`) |
| **热设计与皮肤接触温升预算** | `M-MAIN-L` `U1_HOST` 底部 `4×4 mm` 散热焊盘经阵列 VIPPO 导热至 L2/L5 铜箔 + `25 μm` 人工合成石墨片 (`k = 1500 W/m·K`) 沿镜腿内壁均热（等效热阻 $R_{\theta} = 24.5\ ^\circ\text{C/W}$） | 25°C 环温下 30s 拍照突发峰值功耗 `805 mW`（占空比 0.62）预估外壁温升至 **`37.2 °C`**（`< 43.0 °C` IEC 62368-1 限值） |
