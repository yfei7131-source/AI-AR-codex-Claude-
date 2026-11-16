# 智元跃动 (Zhiyuan Yuedong) AI/AR 智能眼镜 V1.0 — EVT-1 Rev C (P0 深度整改版) Kimi 工程交接手册

**工程版本**：`V1.0-EVT1-RevC-P0Remediated-20261115`  
**Git 分支**：`handoff/evt1-rev-c-feasibility-20261115`（独立分支，保留 `main`、`PR #16`、`PR #17`、`PR #18` 原貌）  
**主控与音频冻结架构**：`ESP32-S3-PICO-1-N8R8` (左镜腿 Wi-Fi/DVP/AI 主控) + `Nordic nRF5340-CMAA-R7` (右镜腿 BLE 5.4 LE Audio 协处理器) + `Lattice iCE40UP5K-UWG30ITR` (中梁双目 QSPI 桥接 FPGA) + `2x ADI MAX98357AEWL+T` (数字 I2S 功放)

---

## 1. 本轮 P0 工程缺陷整改闭环清单（基于 `44b860b`）

### 1.1 修复 FPGA 主机 QSPI 跨时钟域写入丢数、帧存边界与帧撕裂防护 (`evt1_ar_display_fpga_bridge_rev_c.v`)
- **原 `44b860b` 缺陷根因**：
  1. 主机 QSPI (`host_sck = 40.000 MHz`, `100 ns/word`) 与 FPGA 系统时钟 (`clk_48m = 48.000 MHz`, `20.833 ns/clk`) 之间仅采用 1 深度的 `h_wr_toggle` + `wr_pending` 寄存器。
  2. 每行 HBLANK 期间 (`col_cnt = 1800..1881`, 共 **82 个 `clk_48m` 周期 = `1.7083 μs`**)，单端口 [`SB_SPRAM256KA`](https://www.farnell.com/datasheets/3215488.pdf) 被行预取 (`prefetch_active = 1`) 独占读取 80 个 16-bit 字写入 [`SB_RAM40_4K`](https://www.farnell.com/datasheets/3215488.pdf) 行缓存，此时 `spram_do_write = 0`。主机连续突发写入在该 `1.7083 μs` 窗口内到达的 **18~19 个 16-bit 像素字直接覆盖 `h_latched_data/addr` 并全部丢失**。
  3. 缺少帧存地址上界保护（`>= 0x4B00` 越界写入会回卷破坏 Bank 1），且复位后 `row_cnt` 从 `0` 开始导致第 0 帧 Row 0 (`0x0000..0x004F`) 未经过 `row_cnt = 399` 的预取即直接扫描输出。
- **P0 整改方案（已写入 `rtl/evt1_ar_display_fpga_bridge_rev_c.v` 与 `rtl/tb_evt1_ar_display_fpga_bridge_rev_c.v`）**：
  1. **64 深 × 34-bit 双时钟格雷码异步 CDC FIFO (`cdc_fifo_mem [0:63]`)**：
     - 写时钟域 (`host_sck`) 采用 7-bit 二进制指针 `wptr_bin` 与格雷码指针 `wptr_gray`，通过 2 级触发器 (`wptr_gray_s1/s2`) 同步至 `clk_48m` 读时钟域；读指针 `rptr_gray` 同步回 `host_sck` 判定满标志 `fifo_full_h`。
     - 连续满帧 40 MHz QSPI 突发 (`10.00 Mwords/s`) 在 82 周期 (`1.7083 μs`) HBLANK 预取暂停期间最多积压 $\lceil 1.7083\ \mu\text{s} \times 10.0\ \text{Mwords/s}\rceil + 1 = 19$ 个字，64 字深度提供 **`3.37x` 安全裕量**；预取结束后以 `48.00 Mwords/s` 速率在 **24 个 `clk_48m` 周期 (`0.50 μs`)** 内排空积压，实现连续满帧 (`2 × 19,200 = 38,400` 字) **0 丢数**。
  2. **帧存边界硬件裁剪 (`MAX_FB_WORDS = 19,200 = 0x4B00`)**：
     - 严格覆盖每眼 `0x0000..0x3FFF` (Bank 0: `u_spram_l0`/`u_spram_r0`) 与 `0x4000..0x4AFF` (Bank 1: `u_spram_l1`/`u_spram_r1`)；任何 `>= 0x4B00` 的越界地址硬件拦截并累加 `boundary_err_cnt`。
  3. **VBLANK 复位与防撕裂模式 (`0xA2 / 0xA3`)**：
     - 复位时 `row_cnt` 初始化为 `240` (160 行 = `6.6667 ms` VBLANK 起点)，确保首帧 Row 0 (`0x0000..0x004F`) 在 `row_cnt = 399, col_cnt = 1800..1881` 完成预取后再进入 `row_cnt = 0` 扫描；同时支持 `0xA2/0xA3` 防撕裂写入（检测 `tear_row_collision` 防止读写同扫描行撕裂）。

### 1.2 修复 `SN74AXC8T245RJWR` 通道方向分组冲突与 `ESP32-S3-PICO-1` 完整 57 引脚映射
- **原 `44b860b` 缺陷根因**：
  1. 根据 TI [`SN74AXC8T245` 官方数据手册 (SCES875C Table 7-1, p. 20)](https://www.ti.com/lit/ds/symlink/sn74axc8t245.pdf)，芯片内部 8 个通道分为两个 4 通道组：**`DIR1` (Pin 1) 控制 `Ch1..Ch4 (A1..A4 <-> B1..B4)`**，**`DIR2` (Pin 10) 控制 `Ch5..Ch8 (A5..A8 <-> B5..B8)`**。原 `44b860b` 在 `U8_LS1` 的 `Ch5..Ch7` 放置 `3.3V -> 1.8V` (`A -> B`) 信号，却在同属 `DIR2` 控制的 `Ch8` 放置反向的 `frame_vsync_1v8` (`1.8V -> 3.3V`, `B -> A`)，导致 `U8_LS1 B8` 与 FPGA `Ball D3` 输出对顶短路！
  2. 原 `ICD-04` 将摄像头 14 根数字信号 (`D0..D7, PCLK, VSYNC, HREF, XCLK, RESET_N, PWDN`) 塞入单颗 8 通道 `U8_CAM_ISO`，既超出 8 通道容量又混用收发方向。
  3. 对照 [`ESP32-S3-PICO-1` 官方数据手册 v1.2 Table 2-1 (pp. 11–13)](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf)，原 `44b860b` 将 `Pin 46` (`VDD3P3_CPU` 电源脚) 误作 DVP GPIO，且 `USB_D-/D+` 与 `GPIO1/2` 引脚号存在 1 脚位偏移。
- **P0 整改方案（4 颗 `SN74AXC8T245RJWR` 全部 8 个 4-bit Bank 方向 100% 统一）**：

| 芯片位号 | VCCA / VCCB | Bank 1 (`Ch1..Ch4`, `DIR1` 控制) | Bank 2 (`Ch5..Ch8`, `DIR2` 控制) | 方向一致性核查 |
| :--- | :--- | :--- | :--- | :--- |
| **`U8_LS1`** | `3.3V` / `1.8V` | **`DIR1 = HIGH` (`A->B` `3.3V->1.8V`)**：`host_qio[0..3]` (`S3 Pins 16,18,19,14 -> FPGA E1,F1,F2,B1`) | **`DIR2 = HIGH` (`A->B` `3.3V->1.8V`)**：`host_sck`, `host_cs_n`, `FPGA_CRESET_B`, `IPC_S3_TO_NRF_TX` | **PASS (0 冲突)** |
| **`U8_PDM_LS`** | `1.8V` / `3.3V` | **`DIR1 = HIGH` (`A->B` `1.8V->3.3V`)**：`frame_vsync_1v8`, `IPC_NRF_TO_S3_RX`, `PDM_MIC_D0`, `PDM_MIC_D1` | **`DIR2 = LOW` (`B->A` `3.3V->1.8V`)**：`PDM_CLK`, `S3_I2S_BCLK`, `S3_I2S_LRCLK`, `S3_I2S_DOUT` | **PASS (0 冲突)** |
| **`U8_CAM_ISO1`** | `CAM_DOVDD_1V8` / `3.3V` | **`DIR1 = HIGH` (`A->B` `1.8V->3.3V`)**：`CAM_D0..CAM_D3` (`J_CAM -> S3 Pins 9..12`) | **`DIR2 = HIGH` (`A->B` `1.8V->3.3V`)**：`CAM_D4..CAM_D7` (`J_CAM -> S3 Pins 13, 43..45`) | **PASS (0 冲突)** |
| **`U8_CAM_ISO2`** | `CAM_DOVDD_1V8` / `3.3V` | **`DIR1 = HIGH` (`A->B` `1.8V->3.3V`)**：`CAM_PCLK`, `CAM_VSYNC`, `CAM_HREF`, `A4=GND` (`S3 Pins 47,48,8`) | **`DIR2 = LOW` (`B->A` `3.3V->1.8V`)**：`CAM_XCLK` (`S3 Pin 52`), `CAM_RESET_N`, `CAM_PWDN`, `B8=GND` | **PASS (0 冲突)** |

### 1.3 真实器件封装、镜腿外形、FPC 弯折与 HDI 逃线复核
- **电芯与镜腿外形冲突核实 (`CHK-05A / CHK-05B`)**：
  - [Grepow `GRP3911040`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) ($4.20\text{ V}, 110\text{ mAh}$) 实标尺寸为 **$3.71\text{ mm (厚)} \times 11.00\text{ mm (高)} \times 40.00\text{ mm (长)}$**（含保护板长 $43.50\text{ mm}$）。若采用等截面细直镜腿（内腔高 $\le 6.00\text{ mm}$、外高 $\le 7.50\text{ mm}$），`GRP3911040` 在高度方向存在 **`+5.00 mm` 硬干涉**！必须在耳后弯折端 (`Y = 82..126 mm`) 设计 **$\ge 12.80\text{ mm}$ 高的水滴形电池仓 (`Drop-Tip Paddle`)**，或切换至同目录细长电芯 **[Grepow `GRP220550`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) ($4.35\text{ V}, 47\text{ mAh}, 2.38\times 5.60\times 50.0\text{ mm}$)**（可直接装入 $6.00\text{ mm}$ 内腔高的等截面细镜腿，双电芯总能量 $0.357\text{ Wh}$，续航 $1.42\text{ h}$）。
  - [`ESP32-S3-PICO-1-N8R8`](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf) 封装为 **$7.00\times 7.00\times 0.96\text{ mm}$ LGA-56**（引脚间距 $0.40\text{ mm}$、焊盘宽 $0.20\text{ mm}$），无法放入 $5.80\text{ mm}$ 等宽窄板，必须在左镜腿前段 `Y = 4.2..14.0 mm` 局部加宽至 **$8.20\text{ mm}$**（外壳局部宽 $9.80\text{ mm}$）。
  - [`nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) 为 **$3.994\times 4.390\text{ mm}$ WLCSP-95 ($0.35\text{ mm}$ pitch, $11\times 11$ 阵列)**：焊盘直径 $180\ \mu\text{m}$，焊盘边缘净距 $350 - 180 = 170\ \mu\text{m}$，在 $50/50\ \mu\text{m}$ 线宽线距下相邻焊盘间仅能走 **1 根线**，内圈第 3、4 排引脚必须采用 **IPC-2226 Type III 叠孔电镀填平微盲孔 (`L1->L2->L3` Stacked VIPPO, $180/75\ \mu\text{m}$)** 逃逸至 `L3_SIG1`。
  - 因沙盒环境无供应商 3D STEP 外壳模型与原生 KiCad/EasyEDA 布线文件，`CHK-05B` 严格标记为 **`BLOCKED`**，绝不通过手工尺寸盒宣称整机 3D 零碰撞。
