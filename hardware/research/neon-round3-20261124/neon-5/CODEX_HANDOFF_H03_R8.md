# Codex 实施交接指南 — H03-R8 PCB2 联合重排与几何验证增量包

**基线继承**：[PR #55（H03-R7，`ac38a71947f5d7bdd4e5d193584fbb7c6c05363c`）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55) · 兼容 `#57/neon-5` 完整 `PCB2-copper.json`  
**交付方式**：本地增量 ZIP（`h03_r8_pcb2_relayout_delta.zip`，**未上传 GitHub**）  
**严正红线**：本包输出严格标记为 **`OFFLINE_GEOMETRY_SCREEN_NOT_FULL_BOARD_DRC`**（`full_board_native_drc_completed: false`），**严禁以离线局部几何验证冒充 EasyEDA Pro 原生全板 ERC/DRC**。

## 1. 本次脚本修复与验证要点

1. **完整 Copper JSON 与 `POLYGON` 焊盘真实解析（`h03_r8_pcb2_joint_relayout.py`）**：
   * 移除旧版硬编码回退逻辑，强制要求通过 `--copper-json PATH` 传入完整原生 `PCB2-copper.json`。
   * 完整解析 `outline`、`components`、`pads`（`RECT` / `OVAL` / `ROUND` / **`POLYGON` 多格式顶点及焊盘孔 `hole`**）、6 层 `tracks`、`vias`（盲孔/通孔）及 `L2 (layer 15)` / `L5 (layer 18)` GND 平面多边形。
   * **缺数据必报错（Fail-Fast）**：缺失 `outline`、必需器件（`C11/U13/MK2/U1/U3/U5/U2/J1`）、`U13` 关键焊盘（`VSYS/GND/AVDD_REQ_FILTER`）、`MK2` 的 `POLYGON` 焊盘、`tracks`、`vias` 或 `L2/L5` 平面，以及畸形/少于 3 顶点的 `POLYGON` 焊盘，均抛出 `MissingCopperDataError` / `InvalidPolygonPadError` 并以非零码退出。
2. **自动化测试证据（`verification/unittest_output.txt`）**：
   * 5 项测试全部通过（`Ran 5 tests ... OK`）：覆盖 `POLYGON` 三种编码解析、畸形 `POLYGON` 拒收、4 类缺数据严格报错、PR #55 已核实固件端到端验证，以及 L6 阻断时自动触发 `NO_VSYS_L6_ROUTE` 与 `L4_STEREO_REQUIRES_HDI_EQ` 回退。
3. **远程浏览器访问 `#57/neon-5` 状态说明**：
   * 本次会话尝试通过远程浏览器访问 `#57/neon-5` 时返回环境策略拒绝（`POLICY_DECISION_DENY`），因此本包内的 `fixtures/pcb2_verified_extract_pr55.json` 严格基于此前已核实的 PR #55 原生几何提取构造。Codex 在本地检出 `#55` 与 `#57/neon-5` 后，**必须**将 `--copper-json` 指向仓库中最新的完整 15,896 行 `PCB2-copper.json` 复跑，若字段结构有变化脚本会第一时间报错定位。

## 2. 可执行布局坐标与失败候选摘要（离线实测）

* **MK2 干涉审计**：成功解析 `MK2` 全部 4 个 `POLYGON` Pad 5（孔径 `1.42332 / 1.42338 mil`），证实 R7 原生 `C11 (142.32, 877.56)` 与 `MK2` BBox 重叠 **`906.73 sq.mil`**。
* **主推方案 `R8-C_JOINT_U1_U3_U5_SHIFT`（`U1 +50 / U3 +38 / U5 +64 mil` 协同北移）**：
  * 统计：**`33 PASS` / `149 FAIL`**（失败原因：`SMD_SPACING_FAIL: 132`、`BOARD_EDGE_FAIL: 14`、`HOLE_WALL_FAIL: 3`，详见 `verification/relayout_eval_output.json`）。
  * **推荐平衡坐标（Top #2，装配余量更充裕）**：`C11` 置于 **L6 `(134.0, 282.0)`, `0°`**（Pad1 `VSYS` `(121.38, 282.0)` → A* 直连 `U13.4 (111.8, 238.6)` 长度 `44.44 mil`，距 `AVDD_REQ_FILTER` `31.50 mil`；Pad2 `GND` `(146.62, 282.0)` → 新增 `BV_L5_L6` 于 **`(160.62, 282.0)`**，孔壁距 `48.94 mil`、`L5` 平面边距 `8.48 mil`、最小器件距 `7.98 mil`、`in_u2_bga_shadow = false`、`MK2` 重叠 `0.00 sq.mil`）。
  * **备选紧凑坐标（Top #1）**：`C11` 置于 **L6 `(132.0, 282.0)`, `0°`**，`BV_L5_L6` 于 **`(158.62, 282.0)`**（`L5` 边距 `10.48 mil`，最小器件距 `6.02 mil`）。
* **备选方案 `R8-A_ZERO_IC_SHIFT_L4_STEREO`（零动周边 IC）**：
  * 最优位 `C11 = L6 (90.0, 366.0), 180°`，`BV_L5_L6 = (63.38, 366.0)`；位于 `U2` BGA 背面投影区（`in_u2_bga_shadow = true`），在完整 L6 铜箔阻断下须走 `L4` 立体换层并申请板厂 HDI EQ。

## 3. Codex 本地复跑与原生全板 DRC 闭环步骤

1. 在本地仓库检出 `#55` 与 `#57/neon-5` 后，先对**完整 `PCB2-copper.json`** 运行脚本：
   ```bash
   python3 -m unittest -v test_h03_r8_pcb2_joint_relayout.py
   python3 h03_r8_pcb2_joint_relayout.py \
     --copper-json <path_to_full_PCB2-copper.json> \
     --out verification/full_copper_relayout_eval.json
   ```
2. 核对 `full_copper_relayout_eval.json` 中的 `joint_shift_neighbor_notes`（特别是 `U5` 北移后与 `C22` 的协同避让）以及完整 400 段铜线下的 `R8-C` A* 通路结果。
3. 在独立 EasyEDA Pro 克隆工程中写入通过的坐标与盲孔，**执行原生 Schematic ERC、Import Changes、全板严格 PCB DRC，并保存关闭重开复验持久化**，以原生全板 DRC 报告作为唯一最终验收依据。
