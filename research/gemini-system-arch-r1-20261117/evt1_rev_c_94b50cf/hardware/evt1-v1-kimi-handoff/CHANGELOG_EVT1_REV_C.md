# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) 工程变更记录 (CHANGELOG)

**仓库地址**：`https://github.com/yfei7131-source/AI-AR-codex-Claude-`

**目标分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严禁覆盖 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）

## 1. 版本演进与本轮修复详情

### v1.0-EVT1-RevC-PR19-5StateInterlockVerified（本轮提交，继承 `bb87623` 修复配置失败/复位/断电下的光机 `AVDD` 5 态安全联锁）

1. **修复 FPGA 配置状态与光机 `AVDD_OPT_BIAS` 硬件安全联锁 (`CHK-04_PIN_PWR` / `Mut-18..20`)**：

   * **发现并消除 `bb87623` 安全漏洞**：`bb87623` 仅使用 `1V8_OPT_VDD` + `FPGA_CRESET_B` 的盲延时 RC，未采样 `Ball D3 (CDONE / frame_vsync_1v8)`，且 `FPGA_CRESET_B` 采用上拉电阻。在 **MCU 复位/高阻**、**FPGA 比特流配置失败 (`CRESET_B=1.8V, CDONE=0V`)**、**VSYNC 停振**或 **`1V8_OPT_VDD` 先于 `VSYS` 断电**时，会导致光机 `AVDD_OPT_BIAS` 误开启或断电反序。

   * **5 态肖特基峰值保持 + 双轨快速钳位联锁电路**：将 `FPGA_CRESET_B` 改为 `10 kΩ` 下拉至 `GND`（确保 POR/MCU 复位期锁定复位），并由 `Ball D3 (CDONE / frame_vsync_1v8)` 经肖特基二极管 `D1 (RB521S-30)` + `R_CHG = 10 Ω` 对 `C_HOLD = 22 nF || R_BLEED = 2.2 MΩ` 峰值充电，配合双肖特基快速泄放二极管 `D_RST`（接 `FPGA_CRESET_B`）与 `D_VDD`（接 `1V8_OPT_VDD`）：
     1. **上电/MCU 复位 (`CRESET_B = 0V`)**：`V_EN = 0.00 V <= 0.40 V`，严格关断；
     2. **配置进行中或配置失败 (`CRESET_B = 1.8V, CDONE = 0V`)**：`Ball D3 = 0.00 V`，`V_EN = 0.00 V <= 0.40 V`，永久关断；
     3. **配置成功 + `60.000 Hz` `1.000 μs` VSYNC 活跃**：$\tau_{\text{chg}} = 0.77\ \mu\text{s}$，峰值 `1.580 V`，帧间谷值 **`1.120 V >= 0.95 V (VIH)`**（`+170 mV` 裕量），连续稳定开启；
     4. **VSYNC 停振看门狗**：`R_BLEED` 在 **`66.5 ms`** 内泄放至 `< 0.40 V` 自动关断；
     5. **主动复位或 `1V8_OPT_VDD` 掉电断电**：`D_RST` / `D_VDD` 在 **`2.31 μs`** 内强制拉低 `C_HOLD` 至 `0.22 V <= 0.40 V`，极速关断并触发 `U6_OPT_AVDD` 内部 $120\ \Omega$ 主动放电。

2. **补齐左镜腿尾端外部接口焊盘组并扩展至 21 项反向故障注入 (`CHK-07` / `CHK-08`)**：

   * 在 `PINMAP_V1_0_FROZEN.csv` 新增 `PAD_USB_POGO & PAD_BAT_SPK_L`（`Pads 1..9`），实现全机 **45 位号 BOM $\leftrightarrow$ 45 行 PINMAP $\leftrightarrow$ 5 总线 ICD** 100% 闭环，并通过全部 **21 项反向故障注入测试 (`21/21` CAUGHT)**。

### Commit `bb876238fd25ac6be7c8f706b3d273b05d85a847` (`bb87623`)

* 修复 `J_BTB_L / J_BRIDGE_IN` (24-Pin) `Pins 22..24` 与 `J_BTB_R` (16-Pin) `Pins 10..12` 的 3 线立体声 I2S (`I2S_BCLK_1V8`, `I2S_LRCLK_1V8`, `I2S_DOUT_1V8`) 1:1 跨板直通映射，消除单脚截断缺陷。

### Commit `a678be1` / `dfcf8e1` / `d15cc6f` / `8697069` / `43f2960`

* 升级 `J_CAM`/`J_BTB_L`/`J_BRIDGE_IN` 为 24-Pin `BM28B0.6-24DS`，新增 `BOM-45 U6_OPT_AVDD`，修复 `row=0, addr=0x0000` 处 `16'h5AC3 == ~16'hA53C` 仿真碰撞，完成 `clk_48m` 三级流水线与 256 字 EBR FIFO + `Row 10->11` `tear_row_holdoff` 防撕裂改造。
