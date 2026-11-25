# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) 工程变更记录 (CHANGELOG)

**仓库地址**：`https://github.com/yfei7131-source/AI-AR-codex-Claude-`

**目标分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严禁覆盖 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）

## 1. 版本演进与本轮修复详情

### v1.0-EVT1-RevC-PR19-ElectricalAudited（本轮提交，继承 `a678be1` 修复光机 `AVDD` 时序与跨板 3 线 I2S 网表）

1. **修复光机 `U6_OPT_AVDD` 上电时序电路与 `Ball D3 (CDONE / frame_vsync_1v8)` 占空比冲突 (`CHK-04_PIN_PWR` / `Mut-18`)**：

   * **发现并消除 `a678be1` 隐患**：原方案从 `Ball D3 (frame_vsync_1v8)` 经 RC 驱动 `U6_OPT_AVDD.EN`，但用户模式下 `frame_vsync_1v8` 占空比仅 `48 / 800,000 = 0.006%`，RC 平均电压仅 `0.108 mV < 0.95 V`，会导致运行期光机 `AVDD_OPT_BIAS` 关断。

   * **肖特基钳位 RC 硬件时序链**：改为由 `1V8_OPT_VDD` (`1.80 V`) 经 `R_SEQ = 100 kΩ + C_SEQ = 220 nF` ($\tau = 22.0\text{ ms}$) 充电，并由肖特基二极管 `D_SEQ (RB521S-30, Vf = 0.22V)` 钳位至 `FPGA_CRESET_B`。当 `FPGA_CRESET_B = 0V` 时钳位在 `0.22 V <= 0.40 V` 确保关断；当 `FPGA_CRESET_B = 1.80V` 释放后在 **`t_EN = 13.64 ms`**（即 `3.80 ms` Target SPI 配置完成后 **`+9.84 ms`**）开启 `AVDD_OPT_BIAS`，稳态保持 **`1.80 V` DC**，复位或掉电时在 `< 5 μs` 内快速放电并启动 $120\ \Omega$ 主动泄放。

2. **修复 `J_BTB_L` / `J_BRIDGE_IN` (24-Pin) 与 `J_BTB_R` (16-Pin) 的 3 线立体声 I2S 跨板直通映射 (`CHK-07` / `Mut-19`)**：

   * **消除单脚截断缺陷**：移除原 `J_BTB_L Pin 23 (S3_I2S_MUX_1V8)` 单脚概括错误，利用 `BM28B0.6-24DS` 的 4 个 `3.0 A` 金属屏蔽接地脚 (`MP1..MP4`) + `Pin 5 (GND)` 连接 `FPC_BRIDGE` L2 完整地平面，将 `J_BTB_L` / `J_BRIDGE_IN` 的 **`Pins 22, 23, 24`** 明确分配为 **`I2S_BCLK_1V8`、`I2S_LRCLK_1V8`、`I2S_DOUT_1V8`**，与 `J_BTB_R` 的 **`Pins 10, 11, 12`** 实现 **100% 1:1 直通**。

   * **补齐全部 45 位号器件级引脚网表**：在 `PINMAP_V1_0_FROZEN.csv` 中新增 `U10_AMP_L/R (MAX98357A)`、`MK1..3 (IM69D130)`、`U9_IMU (ICM-42688-P)`、`Y1_OSC`、`U3_L/R`、`U4_OR/BB/1V8/1V2`、`U5_LED2V8`、`U7_INA/WIN` 与 `U6_CAM_*` 的完整引脚定义，并将反向故障注入扩展至 **19 项（`19/19` 100% 捕获）**。

### Commit `a678be1437b965ac83874138f28792202e0901a9` (`a678be1`)

* 将 `J_CAM` (`BOM-05`)、`J_BTB_L` (`BOM-15`)、`J_BRIDGE_IN` (`BOM-31`) 升级为 24-Pin `BM28B0.6-24DS/2-0.35V(53)`（`1.50 × 5.50 × 0.60 mm`），新增 `BOM-45 U6_OPT_AVDD`，并建立 `CHK-07` 跨表一致性审查。

### Commit `dfcf8e113e1a67eb876eb6534ead04d4b3b382b5` (`dfcf8e1`) 及 `d15cc6f` / `8697069` / `43f2960`

* 修复 GitHub Actions Run `43844651739` 中 `row=0, w_idx=0, addr=0x0000` 处 `16'h5AC3 == ~16'hA53C` 导致的 1 处 mismatch（改为 `16'h5AC2`），完成 `clk_48m` 三级流水线（`fifo_not_empty_q`、`s1_diff_10_q`、单调递增 `pf_addr_q`、`ebr_wdata_l/r_q`、`pix_shift_l/r`）与 256 字 EBR FIFO + `Row 10->11` `tear_row_holdoff` 防撕裂改造。
