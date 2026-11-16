# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 — EVT-1 Rev C KIMI (嘉立创EDA) 与 Codex (GitHub CI) 工程交接手册

**工程版本**：`V1.0-EVT1-RevC-PR19-5StateInterlockVerified-20261116`  
**Git 分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严格保护 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）  
**主控与音频冻结架构**：[Espressif `ESP32-S3-PICO-1-N8R8`](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf) (左镜腿 Wi-Fi/DVP/AI 主控) + [Nordic `nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) (右镜腿 BLE 5.4 LE Audio 协处理器) + [Lattice `iCE40UP5K-UWG30ITR`](https://www.micro-semiconductor.com/datasheet/10-ICE40UP5K-MDP-EVN.pdf) (鼻梁双目 QSPI 桥接 FPGA) + `2x ADI MAX98357AEWL+T` (数字 I2S 功放)

---

## 1. 继承 `bb87623` 的整机电气设计闭环与 5 态光机安全联锁修正

1. **修复 FPGA 配置状态与光机 `AVDD_OPT_BIAS` 上电联锁（解决复位、配置失败 `CDONE=0`、VSYNC 停振及 `1V8` 断电四类安全隐患，`CHK-04_PIN_PWR` / `Mut-18..20`）**：
   - **`bb87623` 漏洞根因**：`bb87623` 仅采用 `1V8_OPT_VDD` + `FPGA_CRESET_B` 的盲延时 RC，未将 `Ball D3 (CDONE / frame_vsync_1v8)` 纳入硬件联锁，且 `FPGA_CRESET_B` 采用上拉电阻。若 **MCU 复位/跑飞 (`GPIO18` 高阻)** 或 **FPGA 比特流配置失败 (`CRESET_B = 1.80V` 但 `CDONE = 0.00V`)**，盲延时 RC 仍会在 `13.64 ms` 后错误开启 `AVDD_OPT_BIAS`；同时当 **`1V8_OPT_VDD` 先于 `VSYS` 断电**时，RC 放电耗时 `> 16 ms`，违反光机断电时序！
   - **5 态肖特基峰值保持 + 双轨快速钳位联锁电路**：
     - **`FPGA_CRESET_B (Ball F3)` 改为 `10 kΩ` 下拉至 `GND`**：确保上电初期、MCU 复位或崩溃时，FPGA 被硬件锁定在复位态 (`0.00 V`)。
     - **`Ball D3 (CDONE / frame_vsync_1v8)` 肖特基峰值检波 (`D1 RB521S-30` + `R_CHG = 10 Ω` $\rightarrow$ `C_HOLD = 22 nF || R_BLEED = 2.2 MΩ`) + 双轨快速泄放钳位 (`D_RST` 接 `FPGA_CRESET_B`、`D_VDD` 接 `1V8_OPT_VDD`)**：
       1. **State 1（上电/MCU 复位 `CRESET_B = 0V`）**：`V_EN = 0.00 V <= 0.40 V (VIL)`，`AVDD_OPT_BIAS` **OFF** (`0.00 V`)。
       2. **State 2（配置进行中或配置失败 `CRESET_B = 1.8V, CDONE = 0V`）**：`Ball D3 = 0.00 V` 无脉冲，`V_EN = 0.00 V <= 0.40 V (VIL)`，`AVDD_OPT_BIAS` **永久保持 OFF**！
       3. **State 3（配置成功 + `60.000 Hz` `1.000 μs` VSYNC 正常）**：充电时间常数 $\tau_{\text{chg}} = 0.77\ \mu\text{s}$，首脉冲达 `1.148 V`，稳态峰值 **`1.580 V`**，帧间 `16.667 ms` 经 $\tau_{\text{bleed}} = 48.4\text{ ms}$ 衰减至谷值 **`1.120 V >= 0.95 V (VIH)`**（`+170 mV` 裕量），`AVDD_OPT_BIAS` **连续稳定 ON**！
       4. **State 4（VSYNC 丢失 / FPGA 死机看门狗）**：`R_BLEED` 在 **`66.5 ms`** 内将 `C_HOLD` 泄放至 `< 0.40 V`，自动关断 `AVDD_OPT_BIAS`。
       5. **State 5（主动复位或 `1V8_OPT_VDD` 掉电断电）**：`D_RST` 或 `D_VDD` 在 **`2.31 μs`** 内强制将 `C_HOLD` 拉低至 `0.22 V <= 0.40 V`，确保 `AVDD_OPT_BIAS` 极速关断并启动 [TI `TLV755P`](https://www.ti.com/lit/ds/symlink/tlv755p.pdf) 内部 $120\ \Omega$ 主动放电！
2. **全机 45 位号 BOM $\leftrightarrow$ 45 行全引脚 `PINMAP_V1_0_FROZEN.csv` $\leftrightarrow$ 5 总线 `ICD_INTERFACE_CONTROL_TABLE.csv` 100% 闭环 (`CHK-07` / `CHK-08`)**：
   - 补齐左镜腿尾端磁吸充电与左电池/扬声器焊盘组 `PAD_USB_POGO & PAD_BAT_SPK_L`（`Pads 1..9`），与 `J_BTB_L/J_BRIDGE_IN` (24P)、`J_CAM` (24P)、`J_BTB_R` (16P)、`J_DISP_L/R` (10P) 共同构成零悬空网表，并通过 **21 项反向故障注入测试 (`21/21` 100% 捕获)**。
