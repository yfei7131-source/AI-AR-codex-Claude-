# 智元跃动 AI/AR 智能眼镜 V1.0 — 独立首席系统架构审查与可执行设计输入

**状态：`ARCHITECTURE REVIEW / CONDITIONAL / NOT FOR FAB`**  
**继承基线**：PR #29–#35（尤其 PR #32 `7572be31` 与 PR #35 `hardware/evt1-h02-erc-20261120` @ `ccc535842fca777bf1b84611556983db03af40d7`）  
**变更边界**：本分支（`research/arch-review-evt1-v1-20261120`）为纯增量架构审查与 Codex 可执行设计变更输入，**未修改 `main`、未重建 H02 原理图、未重复开发 FPGA、未覆盖 Codex 原生 EDA 工程、未放宽制造规则、未牺牲真双目透明 AR / 40 g 目标 / 既有安全条件**。

---

## 1. 交付物索引

| 文件 | 用途 | 状态 |
| --- | --- | --- |
| [01_DUAL_AR_OPTICS_AND_INTERFACE_AUDIT.md](01_DUAL_AR_OPTICS_AND_INTERFACE_AUDIT.md) | 真双目透明 AR 光机/波导/QSPI vs MIPI 不可混用矩阵、双眼 FPGA 接口缺陷、FPGA 1V2→1V8 时序闭环方案（`TPS3895ADRYR`）、AVDD 安全链与 `BLK-JBD-01..05` 门禁 | `CONDITIONAL` / `BLOCKED`（NDA 项） |
| [02_BRIDGE_22X4_2MM_INTEGRATION_SOLUTION.md](02_BRIDGE_22X4_2MM_INTEGRATION_SOLUTION.md) | 22×4.2 mm 桥板全量 83 器件 150.0% 溢出证明、U8/U10/U14 与三处远置连接器审查、**Option A（严守 22×4.2 mm + 20+2P 缩针 + 封装微缩）**与 **Option B（25×4.6 mm 板上 20+2P）**零重叠 2D 几何解、换封装引脚重映射表与 6L HDI 叠层闭环 | `CONDITIONAL_PASS`（2D 几何）/ `BLOCKED`（原生布线与 3D 装配） |
| [03_SYSTEM_DEFECTS_AND_THREE_BOARD_AUDIT.md](03_SYSTEM_DEFECTS_AND_THREE_BOARD_AUDIT.md) | 左主板、光学桥板、右音频板 12 项有实证的架构与电气缺陷（P0 7 项 / P1 4 项 / P2 1 项），含 `LM66200` 零迟滞振荡与 2.4 V 跌落、隐私联锁全温区误关断、OV5640 1.5 V DVDD 错配、nRF5340 缺失 32.768 kHz 晶振、2450AT18B100E 3× 高度错误等 | `EVIDENCE_BACKED_AUDIT` |
| [04_OEM_COMPONENT_VERIFICATION_MATRIX.csv](04_OEM_COMPONENT_VERIFICATION_MATRIX.csv) | JBD 光机、Hirose BM28 连接器、相机模组、桥板微缩 IC、电源/射频/音频关键器件原厂核查台账（含精确订货料号、封装、三维尺寸、约束、证据 URL 与 `BLOCKED` 标注） | `OEM_VERIFIED` / `BLOCKED` |
| [05_CODEX_ECO_DCR_CHANGE_LIST.csv](05_CODEX_ECO_DCR_CHANGE_LIST.csv) | 供 Codex 直接实施的 16 项工程变更清单（ECO/DCR），含优先级、目标板、位号、精确改动、引脚重映射警示、40 g/安全影响与台架验收方法 | `READY_FOR_CODEX_REVIEW` |
| [verify_arch_review.py](verify_arch_review.py) | 零硬编码路径的确定性 Python 校验器（桥板 83/84 器件 2D 零重叠求解器、隐私联锁 6 角点 PVT/攻防校验、FPGA 时序阈值、LM66200 跌落、双充电流、热与质量 delta） | `PASS`（分析级） |
| [evidence/arch_verification_report.json](evidence/arch_verification_report.json) | `verify_arch_review.py` 生成的机器可读校验结果与 Option A/B 关键 IC 坐标 | `DETERMINISTIC_MATCH` |

---

## 2. 本轮核心裁决摘要

1. **真双目 AR 接口硬边界（禁止混用）**：JBD `Hummingbird Mini II / JBD013VGA` 单色微显示支持 QSPI 或 MIPI（依背板 SKU 固化，**不可混用**）；`Hummingbird I` 双目全彩波导模组与 `Hummingbird II` 全彩投影器仅公开 **MIPI**，与当前 `iCE40UP5K`（18 PIO、无硬 D-PHY）+ `BM28 10+2P` 硬件完全不兼容。若签收件为 MIPI，必须整体更换桥接架构，禁止套用现板。
2. **22×4.2 mm 桥板集成破局**：PR #35 `bridge_trial.md` 仅试算了 14 颗主器件，忽略了其余 69 颗位号（`U_AVDD_SCHMITT`、`U_AVDD_CLEAR_OD`、`U_AVDD_EN_OD`、62 颗阻容、`TP_AVDD_SAFE`），PR #35 现封装全量占地 **237.97 mm² / 158.70 mm² = 150.0%（数学无解）**。本方案通过：
   - **删除 `J_BRIDGE_IN` 上 10 根 `NC_TRUNK_PASS` 废针**：从 `BM28 30+2P (7.85 mm)` 缩为 **`BM28B0.6-20DS/2-0.35V(53)`（`6.10 × 1.70 mm`）**，并将 `VSYS` 升至 **`PWR1 (5 A)`**，根除 P2/P3 `15 mA/触点` 均流危机；
   - **5 颗原厂同源封装微缩 + 被动 0402/0201 化**：`U_AVDD_LS → SN74LVC2T45YZPR`、`U_AVDD_QUAL → SN74LVC1G175DRYR`、`U_AVDD_SCHMITT → SN74LVC2G17DSFR`（**注意 4/6 脚互换**）、`U_AVDD_WD → LTC6993IDCB-2#TRPBF`（**注意 S6→DCB 全脚重排**）、`MK2_C → IM69D127V11XTSA1`（消除 NRND，**注意 2–5 脚重排**）；
   - 在严守 `22.0 × 4.2 mm`、保护 PR #35 三处边缘出线区、保持 `≥ 0.200 mm` 间隙与 `≥ 0.254 mm` 铜边距条件下，实现 **83/83 器件（含新增 `TPS3895ADRYR` FPGA 时序器）2D 零重叠布局（TOP 49.26% / BOT 48.76%）**，整机条件估算净减重 `-0.018 g`（`39.423 g → 39.405 g ≤ 40.0 g`）。
3. **7 项新揭露或已闭环方案的 P0 设计缺陷**：
   - `LM66200` 零迟滞等 SOC 双电池切换振荡 + `6 µF` 有效电容在 `0.8 A / 18 µs` 死区跌落 **2.40 V** → 切换至 `TPS2116DRLR` 优先滞回模式 + `VSYS` 补足 `≥ 30 µF` 有效储能；
   - 摄像隐私联锁在 `2.80 V / 249 Ω` 下冷态 `-10°C`（`1.48 mA < 2.48 mA`）与热态 `+60°C`（`6.11 mA > 4.96 mA`）**双向误关断** → 换 `TPS22916CYFPR` `3.30 V` 开关 + `200 Ω / 1.40 Ω / 12.1k-56.2k-34.8k`（6 角点含短路/开路攻击 `6/6 PASS`）；
   - 相机三路 LDO `EN` 短接违反上电时序且 `1.2 V DVDD` 与 `OV5640 (1.5 V)` 不兼容、`CAM_PWDN` 死接地 + 1 ms 复位 RC 违反 `t2≥5 ms + t3≥1 ms`；
   - `nRF5340-CMAA` 缺失 32.768 kHz LFXO 晶振（`XL1/XL2` 悬空，与 `electrical_source_audit.md` 声明矛盾）→ 补装 `Epson FC1610AN`；
   - `2450AT18B100E` 天线高度 BOM 误填 `0.50 mm`（原厂实际 `1.30 ± 0.20 mm` = 3× 偏差）；
   - 双充静态电流 `558.72 mA > 500 mA` USB SDP 上限 → 增加 `TPS2553DRVR` 前置限流开关并利用 `BQ25180` 4.5 V `VINDPM`；
   - FPGA `1V2_FPGA_PLL → U4_1V8F.EN` `0.5 V` 门限无法证明 → 增加 `TPS3895ADRYR`（`0.926–0.962 V` 严格窗内）。

---

## 3. 复现校验

```powershell
python research/arch-review-evt1-v1-20261120/verify_arch_review.py --check
```

预期输出：`PASS: deterministic match verified (all_analytical_design_checks_pass=True)`。  
**重要声明**：上述 `PASS` 仅代表架构级解析模型与 2D 矩形几何校验通过，**不构成**原生 EDA ERC/DRC、PCB 布线、3D STEP 总装、实物台架或制造批准；`H02`、`H03`、`BLK-JBD-01..05`、相机模组冻结及 40 g 实测称重保持 **BLOCKED**。
