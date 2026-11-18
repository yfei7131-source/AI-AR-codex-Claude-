# EVT-1 嘉立创 EDA 原生接管回件

## 结论：部分原生候选工程已交付，整板设计与制造均为 BLOCKED

- 基线：`cec8deab978c0a6e04bb2293291dd4b5f13ac43a`（PR #29，`hardware/evt1-native-eda-20261118`）。
- 保留双目透明 AR、40 g 目标、摄像头供电／实际采集联动隐私灯及既定核心架构；这些目标没有因本次布局被删除，也没有被证明已经达成。
- 本次产生了真实的嘉立创 EDA 专业版原生 PCB 候选、封装核查、检查日志、原生工程及 3D 文件，不是仅有报告的回件。
- **禁止投板。** 受控原理图原生重建、完整器件布局、合法布线、整板 ERC/DRC、板厂工艺确认、机械／光学／热／RF 验证均未完成。
- 未修改 KiCad 版本号伪装导入，未生成伪造的 `.kicad_sch`／`.kicad_pcb` 回件。

## 1. 可编辑工程与文档标识

原生工程：[`native/ZY_AIAR_EVT1_KIMI_20261118.epro2`](native/ZY_AIAR_EVT1_KIMI_20261118.epro2)

- 工程：`ZY_AIAR_EVT1_KIMI_20261118`
- 项目 UUID：`cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662`
- 嘉立创 EDA 专业版：4.1.97；CLI／daemon／connector：1.17.0
- 主板：SCH `dff3a8fe270050d6`，PCB `8fbc3cae65886fe5`
- 桥板：SCH `43a42f20d31f8062`，PCB `9ce45f14cb79dc9d`
- 右板：SCH `388fb7a3b1e5f2d6`，PCB `1db01a36f669a47a`
- 焊盘审计板：`271a28697816c22b`

`.epro2` 内含三板 PCB 文档、三板原理图页及独立焊盘审计板；PCB 候选文档是该工程的组成部分，不是伪造的独立 `.kicad_pcb`。

工程 ZIP CRC、SHA256 和文档记录已核验。另创建独立恢复验证项目 `95d3c2150079ae83a6d7912339aeaeba4f3a78abf8d15cecab2e88c60bfed872`，不覆盖源工程、不提取团队库；恢复后回读 21／10／4 件候选器件，器件焊盘、bbox、板框及基础标量规则与源回读一致。

证据：

- [`native/native-project-inspection.json`](native/native-project-inspection.json)
- [`native/archive-restore-verification.json`](native/archive-restore-verification.json)
- [`native/restored-readback/`](native/restored-readback/)
- [`layout/review-3/91-project-export-corrected.log`](layout/review-3/91-project-export-corrected.log)

注意：三板 SCH 当前只有 Drawing-Symbol 图框，**没有受控电气原理图**；恢复验证 PASS 仅限于 35 件候选及空原理图工程的可恢复编辑性，不是设计完成证明。

## 2. 原理图接管与输入核对

### 已实际通过

- 输入审计：150 BOM 行、1094 个源端子、1075 个 CAD 端子；254 条封装映射中 114 条编号焊盘匹配、140 条 BLOCKED。
- KiCad 10.0.8 对受控三板原理图执行真实 ERC：每板均为 0 error、0 warning、0 exclusion；端子对账无缺失、无额外端子、无网络不匹配。
- 嘉立创 EDA 对 `.kicad_sch` 直接导入真实失败：`--file must be an .epro2, .epro or .zip archive`。
- 自定义符号修复尝试仍然失败，保留原始 `partial:true`、`verified:false` 记录；完整三板受控网表原生原理图重建为 BLOCKED，未用空原理图冒充。

### 两种 ERC 不可混淆

| 检查 | 实际对象 | 结果 |
|---|---|---|
| KiCad ERC | 受控三板完整原理图 | PASS，三板均 0／0／0 |
| 嘉立创 SCH DRC | 当前仅有图框的原生 SCH 页 | `passed:true`、计数全 0；**仅为空页结果，不是受控设计 ERC PASS** |

证据：

- [`evidence/kicad-source-audit.json`](evidence/kicad-source-audit.json)
- [`evidence/kicad-native-workspace/kicad-verification.json`](evidence/kicad-native-workspace/kicad-verification.json)
- [`evidence/easyeda-kicad-import-probe.log`](evidence/easyeda-kicad-import-probe.log)
- [`evidence/native-library/09a965e44457e53c-retry-01-symbol-build.log`](evidence/native-library/09a965e44457e53c-retry-01-symbol-build.log)
- [`native/native-project-inspection.json`](native/native-project-inspection.json)

## 3. 真实原生候选布局

共 **35 件**：主板 21 件、桥板 10 件、右板 4 件。均真实写入嘉立创 PCB，逐件保存／回读并再次进行全板回读。它们仍是 `UNBOUND_CONTROLLED_NETLIST_CANDIDATE`，不是完整 SCH↔PCB 绑定结果。

- [`layout/native-candidate-placement.csv`](layout/native-candidate-placement.csv)：按实际回读 bbox 计算的坐标、层、旋转和器件来源。
- [`layout/review-3/REVIEW_SUMMARY.json`](layout/review-3/REVIEW_SUMMARY.json)：最终检查摘要及逐项原始日志路径。
- [`layout/review-3/geometric-audit.json`](layout/review-3/geometric-audit.json)：板框、同面 bbox、预留区和布线铜范围独立审查。
- [`layout/review-3/*/fresh-board.json`](layout/review-3/)：最终原生回读。
- [`layout/refinement-1/`](../kimi-return/layout/refinement-1/) 至 [`layout/refinement-5/`](layout/refinement-5/)：实际原生修正过程；失败试验也保留。

几何检查使用实际原生渲染 bbox，仅作有限候选空间审查，不是供应商 courtyard、STEP 装配或整机可行性认证。

| 板 | 候选数量 | 有限几何结果 | 未解决空间问题 |
|---|---:|---|---|
| M-MAIN-L | 21 | `PASS_WITHIN_LIMITED_SCOPE` | 未放全器件、RF／散热／机械仍未验证 |
| M-OPT-BRIDGE | 10 | **FAIL** | U8 换到底层后与 `J_BRIDGE_IN` 预留区冲突；另有 2 件无合法候选 |
| M-AUD-R | 4 | `PASS_WITHIN_LIMITED_SCOPE` | 仅 4 件候选，nRF、连接器、电池等尚未放入 |

桥板 `U14 / U_AVDD_WD` 和 `U10 / U_AVDD_QUAL` 的状态是 `BLOCKED_NO_LEGAL_CANDIDATE_IN_SEARCH`：在既有锚点及有界 0.20 mm 全 bbox 搜索中未找到合法候选，**不宣称数学上绝对无解**。

时钟局部修正已回读：主板与桥板 `clk_48m` 对应焊盘中心距离均为 0 mm（同一器件的镜像／现场坐标口径），不据此宣称时钟 SI、启动或布线完成。

## 4. 板框与基础工艺规则

- 主板：长 46 mm，局部宽 5.8／8.2／5.8 mm。
- 桥板：22 × 4.2 mm。
- 右板：34 × 5.2 mm。
- 三板观察到 6 铜层；基础标量规则已保存回读：0.05 mm 线宽／间距，微孔 0.075／0.18 mm，默认孔约 0.20／0.40 mm。
- 原生坐标比较仅允许 0.0001 mil 序列化的半量化误差，**不是制造规则放宽**。
- 供应商叠层、介质厚度、阻抗、盲埋孔层跨、VIPPO、完整规则矩阵、0.50 mm 桥板目标均 BLOCKED／UNVERIFIED。

证据：[`evidence/board-rule-limitations.json`](evidence/board-rule-limitations.json) 及 [`layout/review-3/REVIEW_SUMMARY.json`](layout/review-3/REVIEW_SUMMARY.json)。

## 5. 最终真实原生 DRC：全部 FAIL

以下来自最终 `layout/review-3` 的原生 `pcb drc --strict --json`，进程／脚本退出码不等于 DRC PASS。原始违规行均保留。

| 板 | Clearance | 同封装 Clearance | Connection | Netlist | 合计 |
|---|---:|---:|---:|---:|---:|
| M-MAIN-L | 19 | 4 | 205 | 1 | **229** |
| M-OPT-BRIDGE | 2 | 4 | 59 | 1 | **66** |
| M-AUD-R | 2 | 4 | 18 | 1 | **25** |
| 合计 | 23 | 12 | 282 | 3 | **320** |

- 主板剩余 Clearance：9 Plane Zone→Via、9 Hole→Plane Zone、1 Plane Zone→Slot；另有 4 个同封装 SMD Pad→Slot。
- 桥板和右板各 2 Plane Zone→Slot、4 个同封装 SMD Pad→Slot。
- `pcb check` 和 `layout-lint` 也保留 `incomplete:true`、丝印、嵌入过孔和铺铜等检查项；没有以辅助 lint 的局部零项替代真实 DRC。
- 没有脚本新增 tracks、arcs、standalone vias、pours、poured 或 fills。主板存在 9 个 ESP32 封装嵌入 GND 过孔，24 mil 直径／12 mil 孔；不得称“板上无过孔”。
- **没有合法信号／电源布线，Connection Error 未清零，禁止投板。**

原始日志：[`layout/review-3/`](layout/review-3/) 下各板 `04-native-drc-strict.log`、`05-check-strict-json.log`、`06-layout-lint.log`、`11-native-erc-strict-json.log`。

## 6. 封装核查

- 26 种精确系统 Device：不同脚号集合与实际原生焊盘编号集合 **26 PASS／0 FAIL**。
- 原生几何可读取；独立审计板已保存并重载。
- 这不等于原厂 land pattern、阻焊／钢网、供应库存、可制造性或可装配性通过。140 条未决封装映射仍是 BLOCKED。

文件：

- [`FOOTPRINT_AUDIT.csv`](FOOTPRINT_AUDIT.csv)：26 种 Device 的逐类型脚号／焊盘编号集合。
- [`evidence/pad-audit/native-pad-audit.json`](evidence/pad-audit/native-pad-audit.json)：原始审计及限制。
- [`evidence/pad-audit/`](evidence/pad-audit/)：原生回读与日志。

## 7. 3D 与视觉证据边界

最终导出为 `3d/*-retry-02/`，与 Round-3 候选一致；无后缀的同名目录属于早期历史证据，不能作为最终版本使用。

| 板 | OBJ | STEP |
|---|---|---|
| M-MAIN-L | 成功，2,106,251 bytes | **BLOCKED**：22,150,672 bytes，超过 20 MiB 传输上限 |
| M-OPT-BRIDGE | 成功，985,661 bytes | 成功，10,696,883 bytes |
| M-AUD-R | 成功，362,342 bytes | 成功，4,948,327 bytes |

- 35／35 个已放置候选有模型绑定；`autoGenerateModels:false`、`modelCoverage:binding-only`。
- 这不是完整 PCBA／整机模型，不包含所有未放器件、连接器、光机、FPC、电池、壳体或铰链。
- `previewVerified:false`；官方画布截图因隐藏标签页未可靠取得。`actual-both.svg` 是辅助回读渲染，不能冒充官方整板截图或实装认证。
- 未删减主板模型伪造 STEP，也没有把 OBJ 改名为 STEP。

详见 [`3d/README.md`](3d/README.md) 和 [`3d/3D_AND_BINDINGS.json`](3d/3D_AND_BINDINGS.json)。

## 8. BLOCKED、审核与复现

- 总状态：[`VERIFICATION.json`](VERIFICATION.json)
- 完整阻塞项：[`BLOCKED.md`](BLOCKED.md)
- Codex 审核：[`evidence/codex-review/KIMI_NATIVE_REVIEW.json`](evidence/codex-review/KIMI_NATIVE_REVIEW.json)
- 审核原始命令：[`evidence/codex-review/review-command.log`](evidence/codex-review/review-command.log)
- 文件校验：[`SHA256SUMS.txt`](SHA256SUMS.txt)

`review_kimi_return.py` 最终真实退出码为 2，`native_review=BLOCKED`、`manufacturing=BLOCKED`。脚本要求 KiCad 原生回件，但本次没有通过伪造格式转换来消除这一阻塞。

在仓库根目录复算最终离线证据（原生 EDA 操作需本机嘉立创连接环境）：

```bash
python "hardware/evt1-native-eda-20261118/kimi-return/tools/analyze_native_layout.py" --round 3
python "hardware/evt1-native-eda-20261118/kimi-return/tools/finalize_return.py"
python "hardware/evt1-native-eda-20261118/kimi-return/tools/run_codex_review.py"
```

最后一条预期保留真实非零退出码 2；不要把它改写成 0。`verify_native_layout.py`、`verify_archive_restore.py` 等原生工具的实际命令及结果均已保存在对应日志中。
