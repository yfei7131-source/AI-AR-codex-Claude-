# 智元跃动 AI/AR 智能眼镜 V1.0 — EVT-1 系统架构 R1.1 审查与状态重基线规范

**文档编号**：`ZY-AIAR-EVT1-ARCH-R1.1-20261116`  
**工程原则**：
1. **撤销缺乏依据的 `FROZEN` 标识**：立即撤销 R1 中对旧版 `BQ24074RGTR`、`TPS63802DLAR`、`24-Pin BTB`、`34.75 g` 质量预算及未完成三方对账项目的 `FROZEN` 标识，禁止将旧 Rev C 方案回退为现行设计。
2. **诚实阻断声明**：因 [GitHub 仓库 `AI-AR-codex-Claude-`](https://github.com/yfei7131-source/AI-AR-codex-Claude-) 为私有/受限仓库，本环境无法读取 **Codex `Rev D1` (PR #21)** 与 **Claude 光学 `R0.1` (PR #22)** 的实际源文件，所有需从 PR #21 / PR #22 继承的新器件选型、FPC/光学接口与重量数据均严格标记为 **`BLOCKED_AWAITING_PR21_PR22_FILES`**，严禁虚构参数。
3. **JBD 原厂 NDA 资料**：`BLK-JBD-01 ~ BLK-JBD-04` 继续保持 `BLOCKED`。

---

## 1. R1 旧版方案撤销与三方对账状态表

| 领域 | Gemini R1 (`94b50cf`) 原方案 | R1.1 状态修正（撤销 `FROZEN`） | 需从 PR #21 (`Rev D1`) / PR #22 (`R0.1`) 继承核对的内容 |
| :--- | :--- | :--- | :--- |
| **左电池充电与路径管理** | `BQ24074RGTR` (`4.40V` DPPM) + `LM66200` | **`DEPRECATED_IN_R1_1`**（撤销 `FROZEN`，禁止回退） | **BLOCKED (待读取 PR #21)**：读取 `Rev D1` 替换 `BQ24074` 的最新充电/PMIC 器件型号、引脚、ISET/NTC 参数及验证状态 |
| **3V3 系统稳压电源** | `TPS63802DLAR` (`3.30V` Buck-Boost) | **`DEPRECATED_IN_R1_1`**（撤销 `FROZEN`，禁止回退） | **BLOCKED (待读取 PR #21)**：读取 `Rev D1` 替换 `TPS63802` 的最新稳压方案、电感封装及效率/纹波实测 |
| **跨板与摄像头 BTB** | `24-Pin BM28B0.6-24DS` (`J_CAM`, `J_BTB_L`, `J_BRIDGE_IN`) | **`DEPRECATED_IN_R1_1`**（撤销 `FROZEN`，禁止回退） | **BLOCKED (待读取 PR #21 / PR #22)**：读取 `Rev D1` / `R0.1` 最新 BTB Pin 数、线序、FPC 形态及 NETLIST |
| **整机质量与重心预算** | `34.75 g`（基于旧 Rev C 估算，`UNVERIFIED`） | **`RETRACTED_SUPERSEDED`**（撤销旧预算） | **BLOCKED (待读取 PR #21 / PR #22)**：读取 `R0.1` 光学/波导实重与 `Rev D1` 最新结构/电池 BOM 质量汇总 |
| **FPGA 核心桥接架构** | `iCE40UP5K-UWG30ITR` (18 PIO, 256 字 FIFO, 4x SPRAM, `60Hz` 防撕裂) | **`VALIDATED_SIM_ONLY__PENDING_CI`**（不覆盖 Rev D1） | **BLOCKED (待读取 PR #21)**：核对 `Rev D1` 是否修改了 FPGA RTL/PCF（特别是 `Ball D3` 极性）及 GitHub CI 实测 Fmax |
| **JBD 双目光机接口** | 对称 10-Pin BTB 预留契约 + `BLK-JBD-01..04` | **`BLOCKED_JBD_NDA`**（禁止猜测参数） | **BLOCKED (待读取 PR #22 & 原厂 NDA)**：核对 `R0.1` 光学包络、出瞳/波导结构约束，JBD 电气参数仍等原厂 NDA |

---

## 2. 重点专项：`Rev D1` `D3` 低脉冲逻辑 vs Gemini 五状态 `AVDD` 联锁兼容性与安全测试要求

### 2.1 真实电气兼容性结论：**直接混用不兼容（`INCOMPATIBLE`）**
依据 [Lattice `FPGA-TN-02006-2.3` Table 3.1 (p. 11)](https://0x04.net/~mwk/sbdocs/ice40/FPGA-TN-02006-2-3-iCE40-Hardware-Checklist.pdf)，`Ball D3 (IOB_12A_G4_CDONE)` 在 CRAM 配置期间被 FPGA 内部开漏拉低（`0.00V`），配置成功后释放并由 `4.7 kΩ` 上拉至 `1.80V`，随后交由用户 RTL 控制：
- **Gemini `94b50cf` 五状态联锁前提**：假设用户模式下 `Ball D3` **空闲为 `0.00V`**，仅在每帧起始输出 **`1.000 μs` 正高脉冲 (`1.80V`)**，通过 `D1 (RB521S-30)` 正向峰值检波给 `C_HOLD = 22 nF || R_BLEED = 2.2 MΩ` 充电维持 `V_valley = 1.120 V >= 0.95 V (VIH)`。
- **与 `Rev D1` `D3` 低脉冲逻辑的冲突**：`Rev D1` 用户模式下 `Ball D3` **空闲为 `1.80V` 高电平**，仅在帧同步窗口输出**低电平脉冲 (`0.00V`)**。若直接接入 `94b50cf` 的 `D1` 正向峰值保持电路：
  1. `D3` 空闲常高 (`1.80V`) 会使 `D1` 持续导通，将 `U6_OPT_AVDD.EN` 永久锁定在 `1.580V`；
  2. **导致 State 4（FPGA 死机/VSYNC 停振看门狗 `66.5 ms` 自动关断）完全失效**，且 **State 2（比特流异常停在空闲高电平）误开启 `AVDD_OPT_BIAS`**。

### 2.2 兼容性改造方案（二选一，待读取 PR #21 确认 `Rev D1` 主控/IMU 边沿需求后定版）
1. **选项 1（若 `Rev D1` 保留 `D3` 低脉冲逻辑）—— 弃用直接峰值检波，改用交流耦合负边沿电荷泵**：
   - 将 `Ball D3` 串联隔直电容 `C_AC = 10 nF` 后接钳位二极管（阳极接 `OPT_SW_NODE`、阴极接 `1V8_OPT_VDD`）与整流肖特基 `D1`（阴极接 `OPT_SW_NODE`、阳极接 `C_HOLD` 电荷泵/负压倍压或经单颗反相器/NMOS 负脉冲整形后充入 `C_HOLD`），彻底隔断 `D3` 稳态 `1.80V` 直流电平，确保**只有存在 `60 Hz` 周期性低脉冲跳变时** `U6_OPT_AVDD.EN` 才维持 $\ge 0.95\text{ V}$。
2. **选项 2（若经 PR #21 核实 `U1_HOST`/`U9_IMU` 可改为上升沿触发）—— 统一为 `94b50cf` 正高脉冲**：
   - 保持 `94b50cf` 极简无源 5 态联锁，无需新增 `C_AC` 与整形电路。

### 2.3 光机 `AVDD` 安全联锁强制测试要求（`SAFETY_TEST_REQUIREMENTS`）
无论最终采用选项 1 或选项 2，EVT-1 R1.1 投板及首件测试必须全部通过以下 6 项实测判据（当前均为 **`UNVERIFIED_AWAITING_PROTOTYPE`**）：
1. **POR / MCU 复位态 (`CRESET_B = 0V`)**：`U6_OPT_AVDD.EN <= 0.40 V (VIL)`，`AVDD_OPT_BIAS <= 0.05 V`。
2. **配置失败态 (`CRESET_B = 1.80V, CDONE = 0V` 或加载坏 CRC 比特流)**：`U6_OPT_AVDD.EN <= 0.40 V`，`AVDD_OPT_BIAS` 保持 `0.00 V` 持续 $\ge 10\text{ s}$ 无误触发。
3. **正常 `60 Hz` 扫描态**：`U6_OPT_AVDD.EN` 帧间最小谷值电压 $\ge 1.10\text{ V}$（较 `0.95 V VIH` 留足 $\ge 150\text{ mV}$ 裕量）。
4. **VSYNC 停振看门狗态（注入 FPGA 时钟/输出卡死在 `0V` 或 `1.8V` 恒定电平）**：`AVDD_OPT_BIAS` 必须在 **`< 100 ms`** 内自动关断至 `< 0.10 V`。
5. **`1V8_OPT_VDD` 掉电先序保护（热拔掉 `1V8` 保持 `VSYS`）**：`AVDD_OPT_BIAS` 必须在 **`<= 5.0 μs`** 内触发关断并经内部 $120\ \Omega$ 泄放，严禁 `AVDD` 晚于 `1V8_OPT_VDD` 跌落。
6. **热复位阶跃（运行中拉低 `CRESET_B`）**：`AVDD_OPT_BIAS` 关断响应时间 $\le 5.0\ \mu\text{s}$。
