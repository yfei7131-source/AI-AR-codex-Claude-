# PR #37 16 项 ECO 独立核查与本轮真实原理图实施记录

> **工程基线**：PR #36（`hardware/evt1-h02-h03-native-20261120` @ `38135f38`）  
> **设计输入**：PR #37（`research/arch-review-evt1-v1-20261120` 16 项 ECO 与 83 器件布局方案）  
> **实施平台**：嘉立创 EDA 专业版 **V4.1.97**（`easyeda-agent v1.17.0`，真实导入、在线编辑、保存、重载、回读并导出 `.epro2`）  
> **制造准入**：**NOT FOR FAB / BLOCKED**

---

## 1. 独立核查关键纠偏（4 项硬核原厂/电气实证发现）

本轮首席研发接管拒绝照单全收 PR #37，逐项核查原厂规格书与现行原理图物理引脚后，发现 **4 项必须纠偏的设计问题**：

1. **ECO-07（USB 限流 `TPS2553DRVR`）— 驳回 PR #37 的 `56.2 kΩ`，修正为 `61.9 kΩ 1%`**
   - TI `TPS2553` 官方最大过流公式：$I_{\mathrm{OS(max)}} = 22980 / R_{\mathrm{ILIM}}^{0.94}$。
   - PR #37 建议 `56.2 kΩ` 计算得 **$I_{\mathrm{OS(max)}} = 520.7\text{ mA} > 500\text{ mA}$**（违反 USB 2.0 FS 上限！）。
   - 修正为 E96 标准值 **`61.9 kΩ 1%`** 后，$I_{\mathrm{OS(max)}} = 475.5\text{ mA} < 500\text{ mA}$，且 $I_{\mathrm{OS(min)}} \approx 410\text{ mA} > 380\text{ mA}$ 双充电器总需流。

2. **ECO-02（摄像隐私硬件联锁）— 发现 PR #37 分压值在最差角仍失效，且 `0201` 限流电阻短路烧毁**
   - 按 `Kingbright APHD1608LCGCK` 官方最差正向压降 $V_{F,\max} = 2.50\text{ V}$、低电源角 `3V3_SYS = 3.201 V` 复算：PR #37 建议的 `200 Ω / 1.40 Ω / 12.1k–56.2k–34.8k` 产生 $V_{\mathrm{INA,min}} = 0.964\text{ V} < V_{\mathrm{TH,L}} = 1.094\text{ V}$，**低温高 VF 角仍触发假锁死**！
   - 此外，LED 短路故障下 `R_LIMIT` 功耗达 `75.6 mW`，超过 `0201`（50 mW）额定功率。
   - **本轮真实原理图修正方案（全 PVT 闭环且零端子回归）**：
     - `U5`（`U5_LED2V8`）：`TLV75528PDQNR` → **`TLV75533PDQNR`**（同系列 5 脚 `TI DQN0004A` 直接兼容，≤10 mA 压差 `<15 mV` 且上限钳位于 `≤3.35 V`）
     - `R21`（`R_LIMIT`）：`249 Ω` → **`150 Ω 1% 0402 100 mW`**（`RC0402FR-07150RL`）
     - `R31`（`R_SENSE`）：`2.20 Ω 0.1%` → **`1.10 Ω 0.1% 0402 Kelvin`**
     - `R35 / R34 / R33`（`R_WIN_TOP / MID / BOT`）：`33.2k / 32.4k / 32.4k` → **`20.0k / 56.2k / 24.9k 1%`**
     - **全 PVT 最差角验证（含 ±22 mV 比较器误差与非关联电源最差角）**：正常电流 `4.50–10.36 mA`，低端余量 **`+100.3 mV`**，高端余量 **`+231.4 mV`**，LED 开路锁定余量 **`743.5 mV`**，LED 短路锁定余量 **`391.7 mV`**，短路功耗 **`75.6 mW < 100 mW`**。

3. **ECO-01（双电池电源多路器 `TPS2116DRLR`）— 纠正 `PR1` 迟滞误判，实证现有 8 脚直插自动切换模式**
   - TI `TPS2116`（SLVSEW3）官方确认 **`PR1` 内部比较器无硬件迟滞**（若用优先级模式必须外加 `ST→PR1` 反馈电阻 `R_HYS`，否则电池跌落临界点会产生抖动）。
   - 核查现行 `M-MAIN-L` 原理图 `U9`（`U4_OR`）物理连接：`Pin 4 = GND`, `Pin 5 = GND`。按 `TPS2116` §7.3.1 真值表，`MODE = GND, PR1 = GND` 进入 **Auto-Switchover（自动高电势无缝切换）模式**，与 `LM66200DRLR` 完全 8 脚 1:1 兼容并将额定电流从 `2.0 A` 提升至 **`2.5 A`**（覆盖 `2.3 A` 峰值）。同时将 `C27`（`C_OR_OUT`）由 `1 µF` 升级为 **`22 µF 10 V X5R`**（结合分布式电容实现 `≥30 µF` 有效 `VSYS` 储能）。

4. **ECO-14（USB ESD `U12_ESD_USB`）— 发现现行原理图符号缺失 GND 引脚，禁止盲目绑定**
   - 核查 PR #36 原理图发现 `U12`（`U12_ESD_USB`）当前符号仅有 **3 脚**（`1: VBUS_5V`, `2: USB_DM`, `3: USB_DP`），**缺少 `GND` 泄放脚**！
   - 若强行绑定 6 脚 `TI TPD2E001DRYR` 将造成引脚失配或悬空无效 ESD 保护。本轮严格将其评定为 **`CONDITIONAL / BLOCKED`**，归入下一轮同步改网表 ECO（新增 GND 脚并更新原理图符号）。

---

## 2. 16 项 ECO 独立审核结论总表

详见结构化机器可读矩阵：[ECO_AUDIT_MATRIX.csv](ECO_AUDIT_MATRIX.csv)。

| 分类 | ECO 项 | 数量 | 说明 |
| --- | --- | :---: | --- |
| **本轮已在原生原理图真实实施并回读验证** | `ECO-01`, `ECO-02`（修正全 PVT）, `ECO-10`（BOM 高度实时 `sch modify`）, `ECO-13`（EVT1 候选用料+封装） | **4** | 0 净网表破坏，严格保持 201 网络组 / 1075 端子 / 92 NC |
| **ACCEPT（待同步改网表 ECO 轮实施）** | `ECO-03`, `ECO-07`（修正 `61.9 kΩ`）, `ECO-08`, `ECO-09`, `ECO-12`, `ECO-15`, `ECO-16` | **7** | 涉及增删器件/改引脚网络，避免本轮单边破坏 H02 1075 端子受控基线 |
| **CONDITIONAL（受 NDA / 机械 / 符号门禁约束）** | `ECO-04`（相机 SKU）, `ECO-05`（20+2P T-FPC ICD）, `ECO-06`（桥板缩封换脚）, `ECO-11`（6L 0.6mm HDI 厂 EQ）, `ECO-14`（缺失 GND 脚符号） | **5** | 其中 `ECO-05`/`ECO-06` 已在原生 `PCB2` 中完成定量空间与通道验证 |

---

## 3. 本轮 22 项原厂核对原生封装绑定清单（100% 清空 PR #36 `PRIMARY_LAND_READY` + `PRIMARY_LAND_PENDING`）

全部 22 项绑定均满足 **原理图符号引脚集 == 受控网表端子集 == 原厂封装焊盘集**，经 EasyEDA Pro V4.1.97 保存、关闭重开、全三板严格 ERC 实测验证（总严格 ERC `268 → 246`，净消除 **`22`** 项 `MISSFOOTPRINT`，**0** 新增错误）：

| 板区 | 位号（源位号） | MPN | 绑定封装名 / 来源 | 引脚数 |
| --- | --- | --- | --- | :---: |
| `M-MAIN-L` | `U9` (`U4_OR`) | **`TPS2116DRLR`** (ECO-01) | `TI_DRL0008A_SOT-583-8_2.1x1.2mm`（TI 4224486 新建） | 8 |
| `M-MAIN-L` | `U7` (`U7_INA`) | `INA185A4IDRLR` | `TI_DRL0006A_SOT-563-6_1.6x1.2mm`（TI 4223266 新建） | 6 |
| `M-MAIN-L` | `Q1` (`Q_CHG_ISO_R`) | `PMV65XP` | `Nexperia_SOT23_TO-236AB`（Nexperia SOT23 新建） | 3 |
| `M-MAIN-L` | `L1` (`L1_BB`) | **`DFE201612E-R47M=P2`** (ECO-13) | `Murata_DFE201612E_2016_2.0x1.6mm`（Murata a=0.8/b=2.4/c=1.6 新建） | 2 |
| `M-MAIN-L` | `U5` (`U5_LED2V8`) | **`TLV75533PDQNR`** (ECO-02) | `X2SON-4_L1.0-W1.0-P0.65-TL-EP`（TI DQN0004A 核验复用） | 5 |
| `M-MAIN-L` | `U6`, `U11`, `U13` | `TLV75528/18/12PDQNR` | `X2SON-4_L1.0-W1.0-P0.65-TL-EP`（TI DQN0004A 核验复用） | 5×3 |
| `M-MAIN-L` | `U14` (`U7_WIN`) | `TLV7042DSGR` | `WSON-8_L2.0-W2.0-P0.50-TL-EP`（TI DSG0008A 核验复用） | 9 |
| `M-MAIN-L` | `U17` (`U8_CAM_SCCB_EN`) | `SN74LVC1G07DPWR` | `X2SON-5_L0.8-W0.8-P0.48-BL-EP`（TI DPW0005A 核验复用） | 5 |
| `M-MAIN-L` | `U19`, `U20` (`U8_LS3/4`) | `PCA9306DQER` | `X2SON-8_L1.4-W1.0-P0.35-BL`（TI DQE0008A 核验复用） | 8×2 |
| `M-OPT-BRIDGE` | `U10`, `U11` | `SN74LVC1G175/2G17DCKR` | `TI_DCK0006A_SC70-6`（PR #36 几何 新建） | 6×2 |
| `M-OPT-BRIDGE` | `U14` (`U_AVDD_WD`) | `LTC6993IS6-2#TRPBF` | `ADI_TSOT23_6_S6`（PR #36 几何 新建） | 6 |
| `M-OPT-BRIDGE` | `U7`, `U12`, `U13` | `TPS389018/25DSET` | `TI_DSE0006A_WSON-6_1.5x1.5mm`（TI DSE0006A 新建） | 6×3 |
| `M-OPT-BRIDGE` | `U8` (`U_AVDD_LS`) | `SN74LVC2T45DCUR` | `TI_DCU0008A_VSSOP-8_2.3x2.0mm`（TI DCU0008A 新建） | 8 |
| `M-OPT-BRIDGE` | `U1`, `U4` | `TLV75518/12PDQNR` | `X2SON-4_L1.0-W1.0-P0.65-TL-EP`（TI DQN0004A 核验复用） | 5×2 |
| `M-AUD-R` | `U3` (`U3_R`) | `BQ25170DSGR` | `WSON-8_L2.0-W2.0-P0.50-TL-EP`（TI DSG0008A 核验复用） | 9 |
