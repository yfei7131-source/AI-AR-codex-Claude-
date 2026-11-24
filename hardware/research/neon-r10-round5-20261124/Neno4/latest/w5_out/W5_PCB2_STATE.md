# W5 PCB2 STATE — R9 继承 PR #60/#61 真实全量回归与 C11 联合换层方案

**状态**：`NOT FOR FAB` · 未降低任何规则 · 未修改主工程 · 未上传 GitHub  
**基线输入**：`R9-Gemini-W5-PCB2.zip`（PR #60 `a825953d62603624d2ad5105d223d07b87ba8d05`，`PCB2-copper.json` `semanticSha256: 70482367cb313b6c...`）  
**验证范围**：`OFFLINE_FULL_COPPER_GEOMETRY_SCREEN_NOT_NATIVE_DRC`（`full_board_native_drc_completed: false`）

## 1. R9 PCB2 真实全量数据核对（86 器件 / 419 线 / 47 孔）

| 指标 | R9 实测值 | 说明 |
| :--- | :--- | :--- |
| **器件数 / 走线数 / 过孔数 / POLYGON 焊盘** | **`86`** / **`419`** / **`47`** / **`16`** | 较 R8（406 线）新增 13 段顶层 `VSYS` 走线（`Y=903..962` 与 `Y=270.5..296.1`） |
| **原生 ERC / DRC** | ERC fatal = **`0`**；DRC = **`232 Connection Error`** | 含 `C11_1 (VSYS)`、`C11_2 (GND)`、`U13_1 (VSYS)`、`U13_4 (VSYS)`、`U13_3 (AVDD_REQ_FILTER)`、`U13_6 (AVDD_PG_NODE)` |
| **已知冲突 GND 铜箔** | `d4ca5cb6211b4cf9`（L6 `GND` `3 mil`，`(130.9,277.4)→(114.0,290.2)`） | 复核与第三轮 R8-C 路径间距 `0.0 mil`（直接相交） |
| **缺失数据显式标记** | `l2_gnd_plane_geometry`、`l5_gnd_plane_geometry`、`via_layer_span_metadata`、`silkscreen_assembly_outline` | `pours/poured/regions/fills` 为空且 `copper.vias` 缺层跨，**未假设为空** |

## 2. C11 联合换层、VSYS 完整路径与 GND 回流求解结论

在不降低任何规则（异网铜距 ≥ `6.2 mil`、敏感/3W ≥ `11.8 mil`、板边 ≥ `12.0 mil`、孔壁 ≥ `11.811 mil`、SMD 间距 ≥ `6.0 mil`、零 `MK2` 侵入）下，对真实 R9 419 段铜线求解结果如下：

* **`S1`（零移位仅 L6 单层）**：`0 PASS`；**`S3`（第三轮 `U1/U3/U5` 移位）**：`0 PASS`（13 处器件包络重叠 + `d4ca5cb6211b4cf9` 冲突）。
* **`S2`（唯一零包络冲突合法解：零动周边 IC + L6 天然空窗 + `L4` 立体 `VSYS` 换层 + `BV_L5_L6` 回流）**：产出 **`80` 个 PASS 候选**（`shift_envelopes_clean: true`、`MK2` 重叠 `0.00 sq.mil`、`d4ca5cb6211b4cf9` 保留不动）：
  * **最优候选 #1**：`C11` 从 `MK2` 包络 `(142.32, 877.56)` 撤出，迁至 **L6 `(90.0, 366.0)`, `180°`**（最小 L6 器件间距 **`6.93 mil`**）。
  * **VSYS 完整换层路径**：`C11.1 (102.62, 366.0)` → `L6→L4` 激光盲埋孔（因处于 L1 主 FPGA `U2` 背面投影区 `in_u2_bga_shadow=true`，严禁打穿通孔至 L1） → 空置 `L4` 内层（`Y=0..450` 为 0 条走线）直达 `U13.4 (111.8, 238.6)` 换层回 L6（路径长 `127.73 mil`，距 `AVDD_REQ_FILTER` **`40.40 mil`**，与 L6 `d4ca5cb6211b4cf9` 经 L5 地层垂直隔离）。
  * **GND 回流路径**：`C11.2 (77.38, 366.0)` → 短宽颈部 → 新增 **`BV_L5_L6` (`4/10 mil`) 于 `(63.38, 366.0)`**（孔壁距 **`12.85 mil`** > `11.811 mil`）锚定至 `L5` 地平面。
  * **预期 DRC 改善**：原生写入并闭环 `C11.1`/`C11.2` 后，PCB2 232 项连接错误预计净降 ≥ 2（降至 ≤ 230）；但最终数值必须以 EasyEDA Pro 原生严格 DRC 实测为准。

## 3. 自动化测试与阻断边界

* **自动化测试**：`test_w5_r9_pcb2_relayout.py` 直接在 R9 真实 86/419/47 数据上运行 **2/2 OK**（见 `verification/w5_unittest.txt`）。
* **保持 `BLOCKED` 项**：(1) 本会话远程浏览器被策略拒绝（`POLICY_DECISION_DENY`），无法直接云端导入 `EVT1-H03-R9-NOT-FOR-FAB.epro2` 执行原生写入与 ERC/DRC；(2) `S2` 方案的 `L6→L4` 微盲孔须获板厂 HDI EQ 批复，并在 EasyEDA Pro 原生工程中复核 `L5` 地平面在 `(63.38, 366.0)` 的完整覆盖。
