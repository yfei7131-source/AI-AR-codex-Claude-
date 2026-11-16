# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 — EVT-1 Rev C (PR #19 P0 深度整改版) Kimi 工程交接手册

**工程版本**：`V1.0-EVT1-RevC-PR19-P0Fixed-20261116`  
**Git 分支**：`handoff/evt1-rev-c-feasibility-20261115`（对应 PR #19 独立分支，保留 `main`、`PR #16`、`PR #17`、`PR #18` 原貌）  
**主控与音频冻结架构**：`ESP32-S3-PICO-1-N8R8` (左镜腿 Wi-Fi/DVP/AI 主控) + `Nordic nRF5340-CMAA-R7` (右镜腿 BLE 5.4 LE Audio 协处理器) + `Lattice iCE40UP5K-UWG30ITR` (中梁双目 QSPI 桥接 FPGA) + `2x ADI MAX98357AEWL+T` (数字 I2S 功放)

---

## 1. 本轮 P0 深度整改闭环（基于 `9a302e2`）

### 1.1 修复防撕裂写入期间 FIFO 溢出问题与最坏时序验证 (`evt1_ar_display_fpga_bridge_rev_c.v`)
- **原 `9a302e2` 缺陷根因**：
  1. 原 `9a302e2` 在 `0xA2 / 0xA3` 防撕裂写入模式下，当主机写入地址命中当前扫描行或下一预取行 (`tear_row_collision == 1`) 时直接挂起 `spram_do_write` 达 **1~2 个完整水平扫描行（`2,000 ~ 4,000` 个 `clk_48m` 周期 = `41.67 ~ 83.33 μs`）**。在此期间主机 40 MHz QSPI 连续突发输入 `416 ~ 833` 个 16-bit 字，仅 `6.4 μs` 即令 64 字 FIFO 溢出 (`fifo_overflow_sticky = 1`)。
  2. 原 `cdc_fifo_mem [0:63]` 写端口位于带异步复位的 `always @(posedge host_sck or posedge host_cs_n)` 块内且采用组合逻辑异步读，导致 `yosys synth_ice40` 无法映射为硬件 Block RAM。
- **P0 整改方案**：
  1. **256 深 × 32-bit 硬件 EBR 双时钟格雷码异步 FIFO（实例化 `2x SB_RAM40_4K`：`u_cdc_fifo_hi` + `u_cdc_fifo_lo`）**：
     - 采用 Lattice [`SB_RAM40_4K`](https://www.farnell.com/datasheets/3215488.pdf) 原生双端口 Block RAM（深度由 64 字提升至 **256 字**，0 LUT 存储开销），配合前瞻读地址 `fifo_ebr_raddr = spram_do_write ? rptr_bin_next[7:0] : rptr_bin[7:0]` 实现零气泡每周期 1 字 (`48.00 Mwords/s`) 排空。
  2. **非阻塞 SPRAM 写入仲裁 + EBR 乒乓双页行缓存 (`Page 0: 0..79`, `Page 1: 128..207`)**：
     - 移除 `tear_row_collision` 对 `spram_do_write` 的行级阻塞（`spram_do_write = (!fifo_empty_c) && (!prefetch_active)`），使 FIFO 排空仅在每行 82 周期 (`1.7083 μs`) 的 HBLANK 行预取窗口暂停。在最坏 40 MHz 主机连续突发及任意活跃行相位碰撞下，FIFO 最大积压严格为 **19 / 256 字（`13.47x` 深度裕量，`fifo_overflow_sticky == 0`）**。
     - 行缓存 `u_ebr_l` / `u_ebr_r` 内部划分为奇偶乒乓双页（偶行使用 `0..79`，奇行使用 `128..207`），确保 `next_row` 预取绝不覆盖正在扫描输出的 `cur_row`，并在 `ICD-01` 中规定主机以 `frame_vsync_1v8` / `VBLANK` (`6.667 ms` 窗口容纳 `3.840 ms` 双目满帧突发) 同步启动帧传输。
  3. **拆分 `host_sck` 异步复位块与移除非 Verilog-2005 语法**：
     - `always @(posedge host_sck or posedge host_cs_n)` 仅复位 4-bit `h_nib_cnt`，其余数据与格雷码指针全部置于纯同步 `always @(posedge host_sck)`，消除 `yosys` `proc_dff` 异步锁存器错误；清除 `V_ACTIVE[8:0]`、`w_idx[15:0]` 等非 IEEE 1364-2005 整数切片语法。

### 1.2 修复 `Makefile` 管道退出码丢失、增加测试台超时保护与 GitHub Actions CI
- **`Makefile` 管道退出码修复**：加入 `SHELL := /bin/bash` 与 `.SHELLFLAGS := -eu -o pipefail -c`，并在 `vvp $(TOP)_sim.vvp | tee iverilog_sim.log` 后增加 `grep -q "VERILOG_TB_RESULT: PASS" iverilog_sim.log` 双重校验，杜绝 `tee` 吞掉 `vvp` 非零退出码。
- **测试台看门狗超时与最坏碰撞测试 (`tb_evt1_ar_display_fpga_bridge_rev_c.v`)**：新增 `SIM_TIMEOUT_CLKS = 3,500,000` 周期超时保护，并加入活跃扫描行第 239 行 `col_cnt = 1780` 跨 HBLANK 预取边界的 `0xA2` 最坏碰撞突发测试。
- **GitHub Actions 原生 EDA CI (`.github/workflows/fpga_eda_ci.yml`)**：自动安装 `YosysHQ/setup-oss-cad-suite@v3`，依次执行 `make all` (`iverilog`、`vvp`、`yosys`、`nextpnr-ice40`、`icetime`) 与 `verify_v1_0_engineering.py` 并归档全部日志。

### 1.3 对照 Lattice 官方规范 (`FPGA-TN-02006-2.3` & `FPGA-EB-02007`) 复核 UWG30 封装、配置与供电
- **电源滤波与上电时序 ([`FPGA-TN-02006-2.3` pp. 8–10](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf))**：
  - `Ball C2 (VCC 1.2V)` 与 `Ball B2 (VCCPLL 1.2V)` 最先上电；在 BOM 中新增 `RN_FPGA_CFG_PWR` (`BOM-33`)，为 `Ball B2 (VCCPLL)` 配置强制要求的 **$100\ \Omega$ 串联电阻 + $4.7\ \mu\text{F} + 100\text{ nF}$ 滤波网络**（Checklist Item 1.4）。
  - `Ball D4 (VPP_2V5)`：依据 Table 2.1 Note 6（Target SPI 模式且不使用内部 `HFOSC`/`LFOSC`/`RGB` 恒流源时允许 $1.8\text{ V}\pm 5\%$），通过 $10\ \Omega + 4.7\ \mu\text{F}$ RC 延时在 `Ball D2 (SPI_VCCIO1 1.8V)` 之后上电，并预留至 `2V8_SYS` 的 $0\ \Omega$ DNI 跳线以兼容 NVCM 烧录。
- **Target SPI 配置引脚与消除 `Ball F1 (SPI_SO)` 启动冲突 ([`FPGA-TN-02006-2.3` Table 3.1 pp. 11–13](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf))**：
  - `Ball C1 (SPI_SS_B)` 配置 $10\text{ k}\Omega$ 下拉电阻至 `GND`（确保 `CRESET_B` 释放时采样 `SPI_SS_B = 0` 进入 Target SPI 模式）；`Ball F3 (CRESET_B)` 配置 $10\text{ k}\Omega$ 上拉至 `1V8_FPGA_IO`；`Ball D3 (CDONE)` 配置 $4.7\text{ k}\Omega$ 上拉至 `1V8_FPGA_IO`。
  - **关键电气修正**：在 1-bit Target SPI 配置期间，`Ball F1 (SPI_SO)` 为 FPGA 主动输出，而 `Ball E1 (SPI_SI)`、`Ball D1 (SPI_SCK)`、`Ball C1 (SPI_SS_B)`、`Ball F3 (CRESET_B)` 为 FPGA 输入。将上述 4 路输入放入 `U8_LS1` **Bank 2 (`Ch5..Ch8`, `DIR2 = HIGH` 常驻 `A->B` `3.3V->1.8V`)**，而将 `Ball F1 (SPI_SO / host_qio[1])`、`host_qio[2..3]` 放入 `U8_LS1` **Bank 1 (`Ch1..Ch4`, `DIR1` 由 `ESP32-S3 GPIO0 / QSPI_DIR1_EN` 控制)**：启动配置期间置 `DIR1 = LOW` (`B->A`) 避免 `U8_LS1` 与 `Ball F1 (SPI_SO)` 输出对顶短路；待 `CDONE = 1` 且完成 49 个配置时钟后置 `DIR1 = HIGH` (`A->B`) 切换为 4-bit QSPI 显示传输。

### 1.4 解决双目显示对称布线、双轨电池结构与全 BOM 44 位号装配
- **鼻梁板 (`M-OPT-BRIDGE`) 对称双翼布局**：将 `U2_FPGA` 置于中点 (`Y = 9.50 mm`)，左光机连接器 `J_DISP_L` 置于左翼 (`Y = 4.20 mm`)、右光机连接器 `J_DISP_R` 置于右翼 (`Y = 14.80 mm`)，左右走线长度严格对称（均为 $5.30\text{ mm}$，$\Delta L_{\text{L-R}} = 0.00\text{ mm}$），彻底消除左右 FPC 交叉跨越。
- **双轨标准目录电池方案**：同时提供 Config A（[Grepow `GRP3911040`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) $4.20\text{ V}, 110\text{ mAh}, 3.71\times 11.0\times 40.0\text{ mm}$，适配 $\ge 12.8\text{ mm}$ 水滴形镜腿尾端，续航 $3.24\text{ h}$）与 Config B（[Grepow `GRP220550`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) $4.35\text{ V}, 47\text{ mAh}, 2.38\times 5.6\times 50.0\text{ mm}$，适配 $\le 6.0\text{ mm}$ 等截面超细直镜腿，高度零突出）。
