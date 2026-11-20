# 01. 真双目透明 AR 光学、接口兼容性、FPGA 桥接与 AVDD 时序审查

**状态：`ARCHITECTURE REVIEW / CONDITIONAL / NOT FOR FAB`**  
**审查对象**：PR #29–#35 有效网表/PINMAP/BOM、Rev D1.1 FPGA RTL（`evt1_ar_display_fpga_bridge_rev_c.v`）、`HARDWARE_GATES.md` 与原厂公开资料。

---

## 1. JBD 光机与波导接口不可混用矩阵

根据 JBD 官方公开产品资料与 PR #35 `HARDWARE_GATES.md`，不同 SKU 之间存在**硬性接口/分辨率/功耗断层，严禁在同一 PCB 或同一 FPGA 桥接架构下混用**：

| 维度 | 路径 A：单色 QSPI 路线（现行受控基线预留） | 路径 B：单色 MIPI 路线 | 路径 C：双目全彩 MIPI 路线 |
| --- | --- | --- | --- |
| 代表原厂器件 | `JBD013VGA`（0.13″ 面板，~0.2 g） / `Hummingbird Mini II` 单色光机（0.15 cc，0.3 g，~60 mW，~8 lm，30° FOV） | `Hummingbird Mini II` / `Mini I` 的 MIPI 接口背板版本 | `Hummingbird I` 双目全彩波导模组 / `Hummingbird II` 全彩投影器（0.2 cc，0.5 g，500×380，25° FOV，~95 mW，X-cube 合色） |
| 物理数据接口 | **4-bit QSPI**（1.8 V 单端 CMOS，SCK + CS_N + D0–D3） | **MIPI DSI**（高速 D-PHY 差分对 + LP 切换） | **MIPI DSI**（双路高速差分） |
| 与现行 `iCE40UP5K-UWG30` 兼容性 | **有条件兼容（CONDITIONAL）**，但需解决下述分眼校准与 NDA 协议阻断 | **完全不兼容（INCOMPATIBLE）** — iCE40UP5K 无硬 MIPI D-PHY，且 UWG30 仅有 18 个普通 CMOS PIO，既无高速差分接收/发射器也无够用引脚 | **完全不兼容（INCOMPATIBLE）** — 分辨率（500×380 RGB）超出 iCE40UP5K 1024 Kibit SPRAM 帧缓冲容量，且无 MIPI D-PHY |
| 与现行 `BM28B0.6-10DS/2`（10+2P）兼容性 | **板侧候选预留（BLOCKED）** — 需 JBD NDA 确认实际 FPC 针位/对插方向/电源域 | **不可直接套用** — 缺 100 Ω 差分阻抗对屏蔽排列与专用 MIPI 电源轨确认 | **不可直接套用** — 全彩 RGB 面板需要独立 R/G/B 阳极/偏置及控制线 |
| 波导与耦合约束 | 单色绿光（~525 nm）单层表面浮雕光栅（SRG）衍射波导，眼盒/出瞳/鼻梁侧耦合几何待波导厂 STEP（`BLK-OPT-01`）；单眼 3.2 g 预算（0.3 g 光机 + ~2.9 g 波导与胶合件）合理但未实称 | 同单色波导 | 需全彩多层或宽带色散补偿衍射波导，质量与损耗显著高于单色单层波导，将直接冲击 40 g 目标 |
| 工程裁决 | **保留为 EVT-1 唯一受控基线（CONDITIONAL / BLK-JBD-01..05 OPEN）** | **禁止混用**；若 JBD 仅交付 MIPI SKU，必须立项新架构（如带 MIPI DSI 的 AP/MCU 或 CrossLink-NX 桥接） | **禁止混用**；不得在当前 EVT-1 板上强改 |

**原厂证据链接**：
- JBD 0.13″ VGA MicroLED 面板：https://www.jb-display.com/product_des/3.html
- JBD Hummingbird I 双目全彩波导模组：https://www.jb-display.com/product_des/8.html
- JBD Hummingbird II 全彩投影器：https://www.jb-display.com/product_des/17.html
- JBD Hummingbird Mini II 公开规格（0.15 cc / 0.3 g / 640×480 / 30° FOV / 60 mW / MIPI or QSPI）：https://www.jb-display.com/

---

## 2. 双眼 FPGA 接口审查（基于 PR #32 / #35 实际 RTL 与网表）

经逐行审查 `evt1_ar_display_fpga_bridge_rev_c.v`（828 行）与 `effective_pinmap.csv`，当前 `iCE40UP5K-UWG30ITR` 18 颗 CMOS PIO 全部用尽（0 余量），存在以下**4 项必须纳入架构契约的真实约束与风险**：

### 2.1 [P0-ARCH / CONDITIONAL] 共享 `opt_cs_n` / `opt_sck` 与无 MISO 读回对双眼独立校准的限制
- **实证**：`U2_FPGA` 仅输出 1 路 `opt_sck`（Ball E3）和 1 路 `opt_cs_n`（Ball C3），经 `R_DAMP_SCK_L/R`（22 Ω）与 `R_DAMP_CS_L/R`（22 Ω）星形分叉至 `J_DISP_L` 和 `J_DISP_R`；`opt_l_qdo[3:0]` 与 `opt_r_qdo[3:0]` 独立。此外，`raw_window_q` 透传模式（RTL L145–L148）把 `host_qio` 同时广播到左右两眼（`opt_l_qdo = host_qio` 且 `opt_r_qdo = host_qio`），且**不存在光机到 FPGA 的 MISO 读回路径**。
- **工程后果**：
  1. 若 JBD 实片存在**左右眼个体差异校准参数**（如左右眼独立亮度补偿/Demura 寄存器、不同行/列偏移或左右眼镜像寄存器配置，即 `BLK-JBD-05`），当前 `raw_window_q` 广播模式无法向左右眼写入不同寄存器值！
  2. 无法读回光机 ID / 温度 / 状态寄存器以确认初始化成功或故障码。
- **不重开发 FPGA 的架构处置建议**：
  - **硬件门禁**：在签署 JBD NDA 确认 `BLK-JBD-02/05` 前，保持 `J_DISP_L/R` 与 `U6_OPT_AVDD` 为默认 **DNP**。
  - **若 NDA 要求分眼寄存器初始化**（且无需增加 FPGA 引脚）：由于左右眼 `opt_l_qdo[3:0]` 与 `opt_r_qdo[3:0]` 物理独立，未来在验证 JBD 协议后仅需在 `RAW` 窗口中通过**发向另一眼的 NOP 指令或将 `A4` 扩展为左/右眼通道掩码**（不改 UWG30 封装引脚），或在非对称需求时升级至 QFN48 封装（`SG48`，需评估桥板面积）以获得独立 `OPT_CS_L/R` 与 `MISO`。在 NDA 未闭合前，**禁止提前修改已通过 CI 时序收敛（49.65 MHz > 48 MHz）的 RTL**。

### 2.2 [P1-ELEC] `U8_LS1` Bank 1 在 ESP32 复位与 FPGA 配置期间的 CMOS 浮空输入风险
- **实证**（`effective_pinmap.csv` L168–L191、`netlist_by_board.txt` L107）：
  - `U8_LS1`（`SN74AXC8T245RJWR`）`OE` 硬接地（常使能），`DIR1` 接 `GPIO0`（`QSPI_DIR1_EN`，被 `R_DIR1_PU` 10 kΩ **和** `R_ESP_BOOT` 10 kΩ 双重上拉至 `3V3_SYS` → 有效 5 kΩ，复位默认 `DIR1 = HIGH` 即 A→B）。
  - ESP32-S3 复位时 `GPIO13/14/9`（`host_qio1..3_3v3`）为高阻输入且无上下拉电阻 → `U8_LS1` 的 `A1/A2/A3` 在 `OE=0, DIR1=1` 期间**完全浮空**，违反 TI `SN74AXC8T245` 数据手册 §8.3.3 禁止 CMOS 输入浮空条款（可引发直通电流与输出振荡，驱动未就绪的 FPGA `SPI_SO` Ball F1）。
  - 配置期间固件拉低 `GPIO0`（`DIR1 = LOW`，B→A）以读取/隔离 FPGA `SPI_SO`（Ball F1），但此时 FPGA 的 `F2 (host_qio2)` 与 `B1 (host_qio3)` 在配置期间为高阻 → `U8_LS1` 的 `B2/B3` 浮空！
- **可执行变更（ECO-09）**：
  1. 删除重复的 `R_ESP_BOOT`（保留 `R_DIR1_PU = 10 kΩ` 单一上拉）；
  2. 在 `host_qio1_3v3` / `host_qio2_3v3` / `host_qio3_3v3`（A1–A3）与 `host_qio2` / `host_qio3`（B2–B3）上增加 `100 kΩ 0201` 弱下拉（与该器件 `A4/B4` 现行 `100 kΩ` 下拉策略完全一致），消除所有复位/配置阶段的 CMOS 浮空输入。

### 2.3 [P0-ELEC] FPGA 1V2 → 1V8 上电顺序 `H04-01` 阻断的确定性硬件闭环
- **实证**（PR #32 `ELECTRICAL.md` L13、Lattice `FPGA-DS-02008` v2.4 表 4.2/4.3、TI `TLV755P` §5.5）：
  - Lattice 硬性要求：`VCC (C2)` 与 `VCCPLL (B2)` 必须先达到 **`≥ 0.50 V`**，之后才允许施加 `SPI_VCCIO1 (D2)`，再施加 `VPP_2V5 (D4)`，单调斜率 `0.6–10 V/ms`。
  - 现行电路将 `1V2_FPGA_PLL` 直接连到 `U4_1V8F`（`TLV75518PDQNR`）的 `EN` 脚。由于 `TLV755P` 仅保证 `V_LO ≤ 0.30 V` 关闭、`V_HI ≥ 1.00 V` 开启，**在 `0.30 V–0.50 V` 区间内 `U4_1V8F` 完全可能提前导通**，从而破坏 Lattice 上电顺序！
  - 此外，经核算 `R_PLL = 100 Ω` 与 `C_FPGA_PLL_BULK = 4.7 µF` 的 RC 时间常数为 `τ = 0.47 ms`，10%–90% 均斜率约 `0.93 V/ms`（在 `0.6–10 V/ms` 内，需实测 MLCC 直流偏置下的有效容值）；而 `R_VPP = 10 Ω` + `4.7 µF`（`τ = 47 µs`）几乎与 `1V8_FPGA_IO` 同坡上升，在 `SPI_VCCIO1 = 0.5 V` 时 `VPP` 已抬升至约 `0.35 V`（是否满足“同轨允许”须在 `H04-01` 实测并核对 Lattice TN-02006 表格注记）。
- **可执行变更（ECO-03）**：
  - 在 `1V2_FPGA_PLL` 与 `U4_1V8F.EN` 之间增加 1 颗超微型高精度电压监测器 **`TI TPS3895ADRYR`**（USON-6，`1.45 × 1.00 × 0.50 mm`，`VCC = 1.7–6.5 V` 接 `VSYS`，`ENABLE` 接 `VSYS`，`SENSE` 内部基准 `0.500 V ±1%` 全温精度，**有源高推挽输出 `SENSE_OUT`** 直接驱动 `U4_1V8F.EN`，`CT` 悬空或加 `100 pF` 滤噪）。
  - 分压电阻取 `R_SEQ_TOP = 49.9 kΩ 1%`、`R_SEQ_BOT = 56.2 kΩ 1%`（0201）：
    - 标称开启门限：`V_IT = 0.500 × (1 + 49.9/56.2) = 0.944 V`
    - 全温 ±1% 器件 + ±1% 电阻最坏范围：**`[0.9258 V, 0.9624 V]`**
    - 严格满足 **`0.9258 V >> 0.50 V`**（100% 保证核心与 PLL 先越过 0.50 V）且 **`0.9624 V < 1.14 V`**（1.20 V ±5% 下限），彻底解除 `H04-01` 设计级阻断（实物波形仍需示波器验收）。

### 2.4 [P1-SAFETY] Rev D1.1 AVDD 安全链与 FPC 针位核查
- **继承并保留**：Rev D1.1 以独立硬件看门狗（`LTC6993-2`）、双轨电源监测（`TPS389018` + `TPS389025`）、独立低压钳位（`TPS389025`）、施密特整形（`SN74LVC2G17`）、心跳资格锁存（`SN74LVC1G175`）与双路开漏钳位（`74LVC2G07GS`）构成的 9-IC 独立硬件安全链**逻辑架构正确、予以完整保留**，禁止回退到 Rev D1 的 RC 盲延时或向 `CRESET_B` 放电的二极管方案。
- **保留为 `BLOCKED` 的供应商门禁**（不可虚构）：
  - `BLK-JBD-01`：左右眼真实 FPC 焊指编号、插接面方向、机械配对图与 `P1–P10 / PWR1 / PWR2` 逐脚连通性（现行板端 `BM28 10+2P` 仅作候选占位，且 `PWR1` 与 `P9` 并接候选 `AVDD_OPT_BIAS`）。
  - `BLK-JBD-02/03`：JBD 上电初始化寄存器表、休眠唤醒、QSPI 操作码/dummy 周期、帧刷新格式与亮度/电流曲线。
  - `BLK-JBD-04`：`AVDD_OPT_BIAS` 标称电压、纹波、峰值/浪涌电流、上下电顺序、允许掉电放电时间与反灌电流极限；现行 `U6_OPT_AVDD`（候选 `TLV755P` 120 Ω 典型主动放电）在获得 NDA 极限前保持 **DNP & BLOCKED**。
  - `BLK-JBD-05`：左右眼分眼校准需求、波导 STEP（`BLK-OPT-01`）、眼盒与光机热阻。
