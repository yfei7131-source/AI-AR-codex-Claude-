# 智元跃动 AI/AR 智能眼镜 V1.0 — EVT-1 系统架构 R1 审查与冻结规范

**文档编号**：`ZY-AIAR-EVT1-ARCH-R1-20261116`  
**审查基线**：
- **Gemini `94b50cf` (`EVT-1 Rev C`)**：本地完整工程已核验（`6 PASS | 5 BLOCKED | 1 UNVERIFIED | 0 FAIL`，`21/21` 反向故障注入拦截）。
- **GitHub PR #21 (`Rev D1`)**：**私有仓库访问受限 (`BLOCKED_REPO_INACCESSIBLE`)**，仅依据用户指令明确的 **D3 低脉冲逻辑** 进行电气/时序兼容性审查；其余差异项严格标记待导入源文件后核对。
- **GitHub PR #22 (`Claude 光学 R0.1`)**：**私有仓库访问受限 (`BLOCKED_REPO_INACCESSIBLE`)**，光机/光学/结构/重量参数严禁猜测，标记待导入源文件后执行三方对账。

---

## 1. 核心专项审查：光机 `AVDD` 五状态联锁与 `Rev D1` `D3` 低脉冲逻辑兼容性分析

### 1.1 两种 `Ball D3 (IOB_12A_G4_CDONE)` 信号极性定义对比
依据 [Lattice `FPGA-TN-02006-2.3` Table 3.1 (p. 11)](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf)，`Ball D3` 在 Target SPI 配置阶段为开漏 `CDONE`（配置中拉低 `0.00V`，配置成功后释放并由 `4.7 kΩ` 上拉至 `1.80V`）；进入用户模式后复用为 `frame_vsync_1v8`：
- **Gemini `94b50cf` (`EVT-1 Rev C`) 定义**：用户模式下**空闲为 `0.00V` 低电平**，每帧（`800,000` 个 `48 MHz` 周期 = `16.667 ms`）仅在 `row_cnt=0, col_cnt=0..47` 输出 **`1.000 μs` 正高脉冲 (`1.80V`)**。
- **PR #21 (`Rev D1`) `D3` 低脉冲逻辑**：用户模式下**空闲为 `1.80V` 高电平**，每帧输出**低电平脉冲 (`0.00V`)**。

### 1.2 兼容性结论：**直接混用存在严重硬件安全冲突（`INCOMPATIBLE_WITHOUT_CIRCUIT_CHANGE`）**
若将 `94b50cf` 的正向肖特基峰值保持联锁电路（`D1 RB521S-30` 阳极接 `D3`、阴极接 `C_HOLD=22nF || R_BLEED=2.2MΩ`）**不加修改**直接接入 `Rev D1` 的 `D3` 低脉冲逻辑，将引发以下 2 项确定性故障：
1. **State 4（FPGA 死机 / VSYNC 停振看门狗）完全失效**：`Rev D1` 下 `D3` 空闲即处于 `1.80V` 高电平，`D1` 持续正偏导通将 `C_HOLD` 死锁在 `1.580V >= 0.95V (VIH)`。即使 FPGA 时钟停振或状态机卡死在空闲态，只要 `D3` 停留在 `1.80V`，`U6_OPT_AVDD` 永远不会在 `66.5 ms` 内关断！
2. **State 2（配置刚完成但用户逻辑未输出脉冲）提前误开启**：`CDONE` 释放上拉至 `1.80V` 的瞬间即对 `C_HOLD` 充电开启 `AVDD_OPT_BIAS`，无法区分“FPGA 正常扫描”与“比特流异常停在空闲高电平”。

### 1.3 采用、修改或弃用决策依据
| 决策选项 | 工程判定 | 定量依据与实施条件 |
| :--- | :--- | :--- |
| **方案 A（推荐默认采用）：保留 `94b50cf` 正脉冲 + 无源 5 态联锁** | **ADOPT (`EVT-1 R1` 默认基线)** | `94b50cf` 的正脉冲 (`1.000 μs` @ `60.000 Hz`) 仅需 3 颗 `0201` 肖特基二极管 + 3 颗 `0201` 阻容即可同时覆盖复位 (`0.00V`)、配置失败 (`CDONE=0` $\rightarrow$ `0.00V`)、正常扫描 (`V_valley=1.120V >= 0.95V`)、停振看门狗 (`66.5 ms` 关断) 与 `1V8` 掉电 (`2.31 μs` 极速关断)，零有源反相器功耗与面积开销 |
| **方案 B（若必须兼容 `Rev D1` `D3` 低脉冲）：弃用直接峰值检波，改用交流耦合负脉冲电荷泵 / 单稳态** | **MODIFY（仅当 `Rev D1` 主控/IMU 强制要求低脉冲时启用）** | 若 `U1_HOST` (`GPIO21`) 或 `U9_IMU` (`FSYNC`) 硬件/固件强制采用下降沿低脉冲，则 `94b50cf` 正向峰值保持电路**必须弃用**，改为 **交流耦合负边沿电荷泵**（`Ball D3` 串联 `C_AC=10nF` 隔直电容 $\rightarrow$ 钳位二极管接 `1V8` + 整流肖特基对 `C_HOLD` 仅响应下降沿跳变），以隔断 `D3` 稳态直流高电平，保留 State 2/4/5 安全联锁；或在 FPGA/主控侧将 `D3` 改为正脉冲同时在 `ESP32-S3` 固件配置 `GPIO_INTR_POSEDGE` |

---

## 2. EVT-1 系统架构 R1 冻结基线（可确认部分）

1. **双芯片公开资料主控分工（`FROZEN`）**：
   - **左镜腿主控 (`M-MAIN-L`)**：[Espressif `ESP32-S3-PICO-1-N8R8`](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf)（LGA-56，`7.0×7.0×0.96 mm`），负责 Wi-Fi、8-bit DVP 摄像头采集（20MHz XCLK/PCLK）、本地语音唤醒 (`ESP-SR`)、40MHz QSPI 显存推流及 `iCE40UP5K` Target SPI 配置；**57/57 引脚已核查，Pin 46 (`VDD3P3_CPU`) 与 14 个禁用引脚零误用**。
   - **右镜腿音频协处理器 (`M-AUD-R`)**：[Nordic `nRF5340-CMAA-R7`](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)（WLCSP-95，`3.99×4.39×0.45 mm`），负责 BLE 5.4 LE Audio (CIS/BIS LC3) 及作为唯一 `1.8V` 功放 I2S Master 驱动左右 `MAX98357AEWL+T`。
   - **备选与阻断**：[Bestechnic `BES2800BP`](https://www.bestechnic.com/Uploads/keditor/file/20260807/20260807114413_51028.pdf) 因无公开 363 球位图、无公开 SDK 及无内置 Camera ISP 保持 **`BLOCKED`**；传统手机经典蓝牙 BR/EDR (A2DP/HFP) 为功能取舍阻断项（`BLK-RevC-04`）。
2. **双目透明 AR 显示链路（`FROZEN_CORE_RTL`）**：
   - 鼻梁桥接 FPGA：[Lattice `iCE40UP5K-UWG30ITR`](https://www.micro-semiconductor.com/datasheet/10-ICE40UP5K-MDP-EVN.pdf)（WLCSP-30，`2.11×2.54×0.45 mm`，`18/18` 合法 CMOS PIO），内部实例化 `3x SB_RAM40_4K`（256 字×34-bit 格雷码异步 FIFO）+ `4x SB_SPRAM256KA`（双目独立 19,200 字帧存）+ `2x SB_RAM40_4K` 乒乓行缓存，输出 `24.000 MHz` 锁步双路独立 QSPI 至对称布置的 `J_DISP_L` (`Y=4.20mm`) / `J_DISP_R` (`Y=14.80mm`)，严格 `60.000 Hz` (`800,000 clks`) 伴随活跃行防撕裂保护 (`tear_row_holdoff`)。
3. **双电池供电与硬件隐私安全架构（`FROZEN`）**：
   - 双轨目录电芯：[Grepow `GRP3911040`](https://www.grepow.com/shaped-battery/ultra-narrow-battery.html) (`2×110mAh = 0.814Wh`, `3.71×11.0×40.0 mm`, 适配 `≥12.8mm` 水滴形镜腿) 或 `GRP220550` (`2×47mAh`, `2.38×5.6×50.0 mm`, 适配 `≤6.0mm` 超细直镜腿)；左 `BQ24074RGTR` (`4.40V` DPPM) + 右 `BQ25170DSGR` + 理想二极管 `LM66200DRLR` 隔离；`TPS63802` (`3V3_SYS`) + `TPS62840` (`1V8_SYS`) + `TLV75512` (`1V2_FPGA_CORE`)。
   - 10 态开漏窗口比较器相机隐私联锁（`INA185A4` + `TLV7042DSGR`）+ 双 `SN74AXC8T245` 零倒灌隔离（实测漏电反灌 $\le 0.84\text{ mV}$）。
4. **跨板接口与 40g 级 6 层 HDI 物理架构（`FROZEN_WITH_BLOCKERS`）**：
   - `J_CAM` (`M-MAIN-L`)、`J_BTB_L` (`M-MAIN-L`)、`J_BRIDGE_IN` (`M-OPT-BRIDGE`) 统一冻结为 **24-Pin [Hirose `BM28B0.6-24DS/2-0.35V(53)`](https://www.hirose.com/en/product/document?clcode=CL0673-5043-0-51&productname=BM28B0.6-16DS/2-0.35V(51)&series=BM28&documenttype=Catalog&lang=en&documentid=D49354_en)**，`J_BTB_R` 为 16-Pin，`J_DISP_L/R` 为 10-Pin，实现 3 线立体声 I2S (`Pins 22..24 <-> Pins 10..12`) 与摄像头 19 路信号 1:1 零溢出映射。
   - 6 层 2+2+2 Type-III 叠孔 VIPPO HDI（`0.628 mm` 总厚，`50/50 μm` 线宽线距，`75/180 μm` 激光微盲孔），分析总重 **`34.75 g`**（`<= 40.0 g` 预算，`UNVERIFIED` 待首件称重）。
