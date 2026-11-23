# PCB3 U11（nRF5340-CMAA）逃线、封装与替代方案决策（U11_ESCAPE_DECISION）

> **审核基线**：GitHub [PR #54 (H03-R6)](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/54)（PCB3 实测板宽 **`5.20 mm`**，U11 对齐 95 球：52 个有网球位、43 个显式 NC，保留 ECO-08 LFXO；36 个内圈有网球位中 25 个在当前锁定规则下受阻）。  
> **状态标签定义**：`[已证实]` 原厂/板厂公开规格或 PR #54 实测；`[理论可行]` 几何与工艺兼容；`[需要试验]` 须打样/验证；`[供应商待确认]` 须书面 EQ 确认。

## 1. 剩余 25 个受阻内圈有网球位的真实几何瓶颈复核

* **器件官方物理规格 `[已证实]`**：Nordic [nRF5340-CMAA WLCSP95](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html)（参考 [Nordic 官方下载页 Reference Layout v1.3](https://www.nordicsemi.com/Products/nRF5340/Downloads)）：
  * 封装尺寸：**`4.390 × 3.994 mm`**，95 球，球距 **`0.35 mm`（`13.78 mil`）**，标称高度 **`0.449 mm`**，湿敏等级 **MSL 1**。
  * **避光硬约束 `[已证实]`**：Nordic 官方明确要求 nRF5340 WLCSP 侧面与锡球侧必须提供可见光/近红外避光防护（仅背面有吸光涂层）。
* **为何 25/36 内圈有网球位在当前规则下全部受阻 `[已证实]`**：
  1. **规则错配**：工程当前锁定全局铜距 **`0.1524 mm`（`6.0 mil`）**，而在 `0.35 mm` 球距下，即便放置 [嘉立创 HDI 最小激光盲孔](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)（`Ø0.075 mm` 孔 + `Ø0.225 mm` 捕获盘），相邻焊盘铜边净距也仅为 `0.350 - 0.225 = 0.125 mm`（`4.92 mil < 6.0 mil`）；若按 `0.100 mm` 默认激光孔（`Ø0.250 mm` 盘），铜边净距为 `0.100 mm`（`3.94 mil < 6.0 mil`）。
  2. **孔距实际达标 `[已证实]`**：在 [嘉立创官方 HDI 规则](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) 下，异网盲孔边到边仅要求 `>= 0.24 mm`。`0.35 mm` 节距放置 `Ø0.075 mm` 盲孔时孔边净距为 `0.275 mm > 0.24 mm`（`Ø0.100 mm` 时为 `0.250 mm > 0.24 mm`）。
  3. **结论**：25 个受阻内圈球位在**物理上并非无解**，真正卡点是：① 必须从默认 1+4+1 叠层切换至 **2+2+2 HDI + VIPPO**；② 必须通过书面 EQ 批准 **U11 局部区域铜距 `3.5 mil (0.09 mm)`（或 `3.0 mil`）** 与 **SMD `Ø0.225 mm` 铜盘 / `Ø0.195 mm` 阻焊开窗** 方案。
  * *注*：PR #54 中已明确记录 25 个受阻内圈有网球位总数（52 有网 / 36 内圈有网 / 25 居中盲孔铜距失败），但未在已公开的 R6 diff 摘要页展开逐球号清单；KIMI 在 R7 中可直接复用 `u11/audit_u11.py` 输出完整 25 球坐标表并按本节 VIPPO 参数一次性校核。

## 2. 三种路线对比决策矩阵（严守 5.20 mm 板宽、功耗、软件兼容与 40 g 目标）

| 评估维度 | 方案 A（推荐）：保留 `nRF5340-CMAA` (`WLCSP95`) + 2+2+2 HDI + 书面 EQ | 方案 B：同芯片换封装 `nRF5340-QKAA` (`aQFN94`) | 方案 C：更换芯片 `nRF54L15` (`WLCSP47` / `QFN48`) |
| :--- | :--- | :--- | :--- |
| **封装尺寸 vs PCB3 `5.20 mm` 板宽** | **`4.390 × 3.994 mm` `[已证实]`**，双侧共留 `1.206 mm` 边距，**无需改镜腿板宽** | **`7.0 × 7.0 mm` `[已证实]`**，**超出 `5.20 mm` 板宽 `1.80 mm`**，必须将镜腿板加宽至 `>= 8.0 mm`，直接破坏 MECR-01 结构 | `QFN48` 为 **`6.0 × 6.0 mm`**（超宽）；`WLCSP47` 为 **`2.4 × 2.2 mm` `[已证实]`**，板宽余量充裕 |
| **逃线与 PCB 工艺门槛** | 需 `0.80 mm` **2+2+2 HDI + VIPPO** + U11 局部 `3.5 mil` EQ `[供应商待确认]` | `0.4 mm` 节距内圈仍须 [1 阶激光 VIPPO（IPC-4761 Type VII）](https://devzone.nordicsemi.com/f/nordic-q-a/96530/nrf5340-aqfn94-pcb-trace-routing-for-inner-pads-via-in-pad)，可降至 1+N+1 HDI `[已证实]` | `WLCSP47` 球数减半（47 球），1+N+1 HDI 逃线压力大减 `[理论可行]` |
| **功耗与热性能** | 成熟双核低功耗；θJA `28.51 °C/W` `[已证实]` | 相同芯片；θJA `20.74 °C/W` 更优 `[已证实]` | `22 nm FD-SOI`，BLE 活跃电流较 nRF5340 降约 `40%`，待机约 `1.6 µA` `[已证实]`（见 [LCSC/Nordic 对比](https://www.lcsc.com/blog/nordic-nrf54-series-vs-nrf53-what-has-actually-changed-in-next-gen-bluetooth-le/)） |
| **LE Audio / USB / 软件兼容** | **100% 兼容**：成熟双核 LE Audio 产线方案、原生 USB 2.0、零固件迁移成本 `[已证实]` | **100% 兼容**：同芯片同 SDK `[已证实]` | **高风险不兼容**：[公开对比明确指出](https://www.lcsc.com/blog/nordic-nrf54-series-vs-nrf53-what-has-actually-changed-in-next-gen-bluetooth-le/) `nRF5340` 仍是成熟 LE Audio 与 USB 2.0 首选；`nRF54L15` 无 USB 2.0 且单核+RISC-V 协处理器架构需重写音频/蓝牙固件与原理图 `[已证实]` |
| **40 g 整机目标影响** | **最优**：维持 `5.20 mm` 窄板、标称厚 `0.449 mm`、`0.80 mm` 薄板 | **负面**：板宽加大 + 封装增厚至 `0.85 mm` + 镜腿结构件增重 | 芯片更轻小，但若外补 USB 桥接/音频协处理器反而增加 BOM 与面积 |
| **综合决策结论** | **首选主路线（P0 推进板厂 EQ）** | **不推荐（仅作 EQ 完全被拒且结构同意改镜腿时的兜底）** | **不推荐用于 EVT-1（会破坏 LE Audio 与软件/原理图继承）** |

## 3. 最终建议与可执行条件

1. **锁定主路线为方案 A（保留 `nRF5340-CMAA` WLCSP95）**：在 `5.20 mm` 窄镜腿、40 g 整机目标、LE Audio 与 USB 2.0 架构约束下，`nRF5340-CMAA` 是唯一不破坏结构与软件继承的器件。
2. **解锁 25 个受阻球位的前置门禁（须由板厂书面 EQ 放行）**：
   * 取得嘉立创或 NextPCB 对 `0.80 mm` 6 层 `2+2+2` HDI、`Ø0.075 mm` 激光 VIPPO（`Ø0.225 mm` 铜盘 + `Ø0.195 mm` SMD 阻焊开窗，或特批 `Ø0.200 mm` 盘）及 U11 局部 `3.5 mil` 间距规则的书面确认；
   * 同步在结构侧冻结 WLCSP 侧面/底部遮光方案（黑胶点涂或屏蔽罩），保留 ECO-08 LFXO 与 RF 50 Ω 匹配网络。
3. **止损触发条件**：仅当两家以上 HDI 板厂书面否决 `0.35 mm` WLCSP95 的 `0.80 mm` 2+2+2 方案时，才启动 MECR-01 结构评审评估方案 B（`aQFN94` 加宽镜腿至 `>= 8.0 mm`），严禁在未评审前擅自更换封装或重画整板。
