# 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) 工程变更记录 (CHANGELOG)

**仓库地址**：`https://github.com/yfei7131-source/AI-AR-codex-Claude-`

**目标分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 [Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)，严禁覆盖 `main`、[PR #16](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/16)、[PR #17](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/17)、[PR #18](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/18)）

## 1. 版本演进与本轮修复详情

### v1.0-EVT1-RevC-PR19-CrossTableVerified（本轮提交，跨表一致性修正与双目光机时序完善）

1. **BOM (45 位号) $\leftrightarrow$ PINMAP (40 行) $\leftrightarrow$ ICD (5 总线) 跨表一致性修正与自动化门禁 (`CHK-07` / `CHK-08`)**：

   * **扩充 `J_CAM` (`BOM-05`)、`J_BTB_L` (`BOM-15`)、`J_BRIDGE_IN` (`BOM-31`) 为 24-Pin `BM28B0.6-24DS/2-0.35V(53)`**：修复原 16-Pin BTB 无法容纳 8-bit DVP 摄像头 19 路信号+5 路屏蔽地（共 24 脚）及跨鼻梁干线 24 路信号的溢出问题，更新 3D 装配坐标 (`1.50 × 5.50 × 0.60 mm`) 并通过全部间距与高度检查。

   * **新增双目光机模拟偏置上电时序门控 LDO `U6_OPT_AVDD` (`BOM-45`, `TLV75528PDQNR`/`TLV75533PDQNR`)**：置于 `M-OPT-BRIDGE` 背面 (`X=2.10, Y=12.20 mm`)，其 `EN` 由 `U2_FPGA Ball D3 (CDONE)` 经 $100\text{ k}\Omega + 100\text{ nF}$ ($\tau = 10\text{ ms}$) RC 延时驱动，从硬件上保证 `1V8_OPT_VDD` 稳定且 FPGA 配置完成后延时 $\ge 3.5\text{ ms}$ 才开启 `AVDD_OPT_BIAS`（Pin 9），断电时由内部 $120\ \Omega$ 主动放电。

   * **固化 `nRF5340-CMAA` 单主 I2S 数字混音拓扑**：明确由 `nRF5340-CMAA` 作为唯一 `1.8V` 功放 I2S Master 驱动 `U10_AMP_L/R`，接收 `ESP32-S3` 经 `U8_PDM_LS` Bank 2 转换后的本地 TTS I2S 信号进行混音，消除双主控 I2S 驱动冲突。

   * **补齐 `PINMAP_V1_0_FROZEN.csv` 全部 57 脚 `U1_HOST` 与 6 颗 BTB 逐针连接表**：在 `verify_v1_0_engineering.py` 中新增 `CHK-07` 跨表一致性检查与第 17 项故障注入测试（`17/17` 故障注入 100% 拦截）。

### Commit `dfcf8e113e1a67eb876eb6534ead04d4b3b382b5` (`dfcf8e1`，基于 `d15cc6f` 深度加固)

1. **FPGA RTL `48.000 MHz` (`clk_48m`) 关键路径二次深度优化 (`evt1_ar_display_fpga_bridge_rev_c.v`)**：

   * **预寄存 FIFO 非空标志 (`fifo_not_empty_q`)**：将原本位于 `start_ebr_rd` 组合路径上的 9-bit 格雷码相等比较器 (`rptr_gray == wptr_gray_s2`) 提前一拍寄存为 `fifo_not_empty_q <= ((ebr_rd_phase_q ? rptr_gray_next : rptr_gray) != wptr_gray_s1)`，使 `start_ebr_rd` 简化为单级 3 输入 `SB_LUT4`（零跨页比较延迟，零下溢风险）。

   * **进位链 MSB 同胞触发器直采 (`s1_diff_10_q`) 与 2 级 LUT4 写使能仲裁**：在 Stage 0 $\rightarrow$ Stage 1 的 11-bit 行偏移减法器 `s0_diff_hi = s0_addr_q[14:4] - next_row_base_hi_q[10:0]` 中，将最后收敛的最高位 `s0_diff_hi[10]` 直接打入同一 Logic Cell 内部的 `SB_DFFE` (`s1_diff_10_q <= s0_diff_hi[10]`)，彻底消除 11-bit 进位链顶端的后级 LUT 与跨 Tile 布线延迟；低位分别由 3 个单级 `SB_LUT4` 打入 `s1_hit_a_q` (`[9:6]==0`)、`s1_hit_b_q` (`[5:3]==0 && s0_tear_q`)、`s1_hit_c_q` (`!bit[2] || [1:0]==0`)。Stage 1 中 `s1_is_next_row` 与 `s1_do_write` 各仅占 1 级 4 输入 `SB_LUT4`（总组合逻辑深度仅 **2 级 `SB_LUT4`**）。

   * **单调递增全帧预取地址计数器 (`pf_addr_q`)**：移除 `next_row_base_q[14:0]`（省去 15 个触发器、15-bit `+80` 加法器及 `pf_addr_q` 上的 15-bit 2:1 并行加载多路器），利用全帧预取地址严格按 `0 .. 19,199` 单调递增的特性，在 VBLANK (`!next_row_valid_q`) 清零 `pf_addr_q`，在 `prefetch_read_q` 期间纯 `+1` 递增，使 `pf_addr_q` 在 Yosys `synth_ice40` 下直接映射为 15 个纯 `SB_CARRY + SB_DFFESR` 单元（0 后级 LUT）。

   * **2 级平衡 XOR 树 (`wptr_bin_dec`) 与裁剪 `rst_n_q` 70% 局部布线扇出**：将格雷码转二进制的串行 `for` 循环改为显式 2 级平衡 `SB_LUT4` XOR 树；移除零初始化统计计数器与数据流水线寄存器上冗余的 `if (!rst_n_q)` 同步复位，将 `rst_n_q` 扇出从 \~125 降至 36。

   * **`host_sck` (`40.000 MHz`) 域预译码**：在 Nibble 2 预寄存 `h_cmd_ok_q`，在 Nibble 7 预寄存 `h_in_bounds_q` (`< 0x4B00`)，使 Nibble 9 的 `fifo_we_h` 仅需单级 LUT；在测试台 `tb_evt1_ar_display_fpga_bridge_rev_c.v` 的 `qspi_burst_write_frame` 入口加入 `#1.0` ns 相位偏移，消除 `wait(...)` 唤醒与 `posedge clk_48m` 同拍时的仿真器 delta-cycle 歧义。

2. **完善主控** $\leftrightarrow$ **FPGA** $\leftrightarrow$ **双目光机接口定义并细化 JBD 4 项阻断 (`ICD_FPGA_HOST_OPTICS_SPEC_REV_C.md`)**：

   * 新增独立接口控制规范文档，完整定义 `ESP32-S3-PICO-1`、`U8_LS1`/`U8_PDM_LS`、`iCE40UP5K-UWG30` 与 `2x JBD013VGA-G` 的物理引脚、Target SPI 启动时序、40MHz QSPI 显存写入帧格式、24MHz 双目锁步扫描时序，以及 `BLK-JBD-01 ~ BLK-JBD-04` 阻断边界。

### Commit `d15cc6f841282664be7dda37bb0111d83ad42e3d` (`d15cc6f`)

* 定位并修复 GitHub Actions Run `43844651739` 中 Icarus 仿真的 **1 处数据不匹配**：位于 **`row = 0, w_idx = 0, addr = 0x0000`**（左眼期望值/实际值 `0xA53C`，右眼期望值/实际值 `0xA53C`，因 `16'h5AC3 == ~16'hA53C` 在 `addr=0x0000` 处触发 `cap_l === cap_r` 断言），将 `calc_right_word` 常数改为 `16'h5AC2`。

* 完成 `s0 -> s1 -> spram_q` 三级寄存器流水线重构，解决 `nextpnr-ice40` (`27.17 MHz`) 与 `icetime` (`27.43 MHz`) 单周期级联违例。

### Commit `8697069b189aab419433639e4ea8c70baef05182` (`8697069`)

* 修复测试台第 239 行未触发真实行预取缺陷（改为测试 `row_cnt == 10` 触发 `next_row == 11` 预取碰撞），扩展为 `3x SB_RAM40_4K`（256 字 × 34-bit）异步 FIFO 并加入 `tear_row_holdoff` 防撕裂保持机制。

### Commit `43f2960979ff` (`43f2960`) 及更早基础提交 (`9a302e2`, `44b860b`, `8eaa633`, `6eaebe0`)

* 完成 `ESP32-S3-PICO-1` 57 引脚核查、`nRF5340-CMAA-R7` BLE 5.4 LE Audio 协处理器集成、`4x SN74AXC8T245` 方向分组与 `Ball F1 (SPI_SO)` 隔离、双电池 `BQ24074 + BQ25170 + LM66200` 供电树、10 态开漏窗口比较器 `TLV7042 + INA185A4` 隐私联锁、Lattice `FPGA-TN-02006-2.3` 硬件配置规范及 `.github/workflows/fpga_eda_ci.yml`。
