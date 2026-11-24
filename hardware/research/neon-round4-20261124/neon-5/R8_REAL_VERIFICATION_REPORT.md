# H03-R8 PCB2 真实全量铜层 JSON 修复与联合重排验证报告

**基线继承**：PR #58 (`1b69c06e81500d6a8b5ce4aaf268513c6b89dfd4`) · 附件 `R8-PCB2-Real-Data-Handoff.zip`  
**验证范围**：`OFFLINE_FULL_COPPER_GEOMETRY_SCREEN_NOT_NATIVE_DRC`（`full_board_native_drc_completed: false`；**严禁以离线几何筛查冒充 EasyEDA Pro 原生全板 DRC**）  
**交付方式**：本地增量 ZIP（`h03_r8_pcb2_real_verified_delta.zip`，**未上传 GitHub**）

## 1. 真实全量输入核对（零夹具冒充）

修复后的 `h03_r8_pcb2_joint_relayout.py` 已完整适配 EasyEDA Pro 原生字段（`padNumber`、`copper.lines`、`lineWidth`、`startX`/`startY`/`endX`/`endY`、`copper.vias`、`holeDiameter`/`diameter`、`RECT`/`ELLIPSE`/`POLYGON` 焊盘及 `["POLYGON", [x, y, "L", ...]]` 路径），并直接在附件两个真实全量铜层 JSON 上运行通过：

| 真实输入文件 | 器件数 | 走线段数 | 过孔数 | POLYGON 焊盘数 | `semanticSha256` | 运行结果 |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **R7 真实数据** (`R8/logs/before/PCB2-copper.json`) | `86` | `398` | `47` | `16` | `a9bae8b8...9dcf` | **PASS** |
| **R8 真实数据** (`R8/logs/after/PCB2-copper.json`) | **`86`** | **`406`** | **`47`** | **`16`** | `e0cc058b...3a2c` | **PASS** |

自动化测试 `python3 -m unittest -v test_h03_r8_pcb2_joint_relayout.py` 直接加载真实 R7 与 R8 文件，**3/3 全部 OK（4.406 s）**，完整日志见 `verification/unittest_real_r7_r8.txt`。

## 2. 缺失平面与结构数据显式标记（严禁假设为空）

解析真实 R7/R8 `PCB2-copper.json` 证实以下数据未包含在铜层导出中，脚本已在 `missing_data_flags` 中显式标记，**未假设为空或虚构多边形**：

1. **`l2_gnd_plane_geometry` / `l5_gnd_plane_geometry`**：`copper.pours`、`poured`、`regions`、`fills` 均为 `[]`（0 个多边形）。新增 `BV_L5_L6` 盲孔的 `L5` 平面落点状态明确标为 **`UNVERIFIED_MISSING_L5_PLANE_IN_COPPER_JSON`**，须在 EasyEDA Pro 原生工程中复核。
2. **`via_layer_span_metadata`**：`copper.vias` 仅含 `x/y/holeDiameter/diameter/net/primitiveId`，无层跨字段；全部 47 颗过孔均按保守模式纳入孔壁间距（≥ `11.811 mil`）与 L6 铜距障碍计算。
3. **`silkscreen_assembly_outline`**：`availability.silk = "not-requested"`，装配间距核查基于器件原生 `bbox`。

## 3. 已知冲突 `d4ca5cb6211b4cf9`、MK2 干涉与四组场景求解结论

* **已知冲突 GND 铜箔核实**：`d4ca5cb6211b4cf9` 位于 `layer=2 (L6)`、`net=GND`、`lineWidth=3 mil`、`(130.9, 277.4) → (114.0, 290.2)`；实测与第三轮 R8-C 路径 `(121.38, 282.0) → (111.8, 238.6)` 间距为 **`0.0 mil`（直接相交）**。
* **`MK2` 声学区与 `POLYGON` 焊盘核实**：`MK2`（`IM69D130V01XTSA1`，L6 `X=[1.10, 155.12], Y=[819.01, 986.49]`）共解析 4 个 `POLYGON` Pad 5（孔径 `1.42332 / 1.42338 mil`）；原生 `C11 (142.32, 877.56)` 与 `MK2` BBox 重叠 **`906.73 sq.mil`**。
* **四组场景实测对比（R8 真实全量数据）**：
  * **`S1`（零移位 + 仅 L6 单层，全铜保留）**：**`0 PASS`**（证实单层无法绕过真实 L6 铜箔与 `d4ca5cb6211b4cf9`）。
  * **`S3`（复现第三轮 `U1 +50 / U3 +38 / U5 +64` 移位）**：**`0 PASS`**，检出 **13 处器件包络重叠**（`U1↔C22/J1/U3/U5`、`U5↔C22/U14/U3`、`U3↔C20/C22/U6`）及 **10 次 `KNOWN_GND_CONFLICT_d4ca5cb6211b4cf9`**，彻底否决第三轮移位方案。
  * **`S4`（强移 `U1` 并重布 `d4ca5cb6211b4cf9`）**：**`0 PASS`**，因 `U1/U3/U5/U6/J1/C20/C22/U14` 在 4.6 mm 窄板中段已满载，任何局部平移都会触发邻近包络冲突。
  * **`S2`（唯一无包络冲突合法解：零动周边 IC + L6 天然空窗 + `L4` 立体 `VSYS` 换层）**：全板 `Y = 20..818 mil` 扫描证实 **`X=[62..104], Y=[358..382]`** 是全板非 `MK2` 区域唯一零移位合法窗口，产出 **`80` 个 PASS 候选**（`shift_envelopes_clean: true`、`MK2` 重叠 `0.00 sq.mil`、`d4ca5cb6211b4cf9` 保留不动且经 `L5` 地层与 `L4` 垂直隔离）：
    * **最优候选 #1**：`C11` 置于 **L6 `(90.0, 366.0)`, `180°`**（`Pad1 VSYS = (102.62, 366.0)`，`Pad2 GND = (77.38, 366.0)`）；新增 `BV_L5_L6` 于 **`(63.38, 366.0)`**（孔壁距 `12.85 mil` > `11.811 mil`）；最小 L6 器件间距 **`6.93 mil`**（> `6.0 mil`）；`AVDD_REQ_FILTER` 间距 **`40.40 mil`**（>> `11.8 mil`）。
    * **明确准入阻断项（须先签核再实施）**：该位处于 L1 主 FPGA `U2` 背面投影区（`in_u2_bga_shadow: true`），`VSYS` 走 `L4`（`Y=0..450` 为 0 条走线）需板厂 **HDI `L6→L4` 盲埋孔 EQ 批准**，并在 EasyEDA Pro 原生工程中复核 `L5` 地平面在 `(63.38, 366.0)` 的完整覆盖及全板原生 ERC/DRC。

## 4. Codex 复跑命令

```bash
export PCB2_R7_COPPER_JSON=<path>/R8/logs/before/PCB2-copper.json
export PCB2_R8_COPPER_JSON=<path>/R8/logs/after/PCB2-copper.json
python3 -m unittest -v test_h03_r8_pcb2_joint_relayout.py
python3 h03_r8_pcb2_joint_relayout.py --copper-json "$PCB2_R8_COPPER_JSON" --out verification/r8_real_eval.json
```
