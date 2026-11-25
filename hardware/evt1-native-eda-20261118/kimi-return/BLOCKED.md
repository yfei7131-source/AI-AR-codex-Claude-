# EVT-1 BLOCKED／FAIL／UNVERIFIED 清单

**当前总状态：BLOCKED；制造状态：BLOCKED；禁止投板。**

双目透明 AR、40 g、摄像隐私灯和核心架构保持不变。下列事项未解决前，不得把 35 件候选布局称为三板 Layout 完成。

## P0：真实失败，必须保留

### FAIL-01：三板原生 DRC 未通过

- 主板：229 项；桥板：66 项；右板：25 项；合计 320 项。
- Connection Error 合计 282 项，Netlist Error 合计 3 项，Clearance 合计 23 项，同封装 Clearance 合计 12 项。
- 未进行信号／电源合法布线；无脚本新增 tracks／arcs／standalone vias／pours／fills。
- 主板 9 个 ESP32 封装嵌入 GND 过孔及原生 Plane／Slot 对象不能忽略，不能声称无过孔。
- 原始证据：`layout/review-3/*/04-native-drc-strict.log`、`layout/review-3/REVIEW_SUMMARY.json`。

### FAIL-02：桥板当前候选仍侵入连接器预留区

- `U8 / U_AVDD_LS` 换到底层后，与 `J_BRIDGE_IN` 的底层预留区在 0.20 mm 审查内相交。
- 不得删除或缩小连接器／光机／FPC 预留区，不得降低间距来隐藏冲突。
- 底层变更只是候选，不是装配批准；需结合真实连接器、FPC 出口、镜腿腔体和底部器件高度重新布局。
- 原始证据：`layout/review-3/geometric-audit.json`、`layout/refinement-5/manifest.json`。

### FAIL-03：辅助检查仍有未解决项

- `pcb check`、`layout-lint` 均为不完整覆盖，不能用来抵消真实原生 DRC。
- 存在丝印方向／压焊盘／出板框、封装嵌入 via-in-pad、铺铜／plane 可见性限制和不支持精确检查的 POLYGON 焊盘几何。
- 原始证据：`layout/review-3/*/05-check-strict-json.log`、`06-layout-lint.log`。

## P0：接管与电气完成条件

### BLOCK-01：完整受控原生原理图尚未建立

- `.kicad_sch` 不能直接作为嘉立创项目导入，原始失败已保留。
- 自定义符号构建尝试真实失败，存在 `partial:true`、`verified:false`，不得据此继续伪造完整原理图。
- 当前三板 SCH 仅有 Drawing-Symbol 图框，0 个电气器件；其 0 ERC 只是空页结果。
- 完整 SCH↔PCB 绑定未完成；部分非空 `uniqueId` 不是绑定证明。
- 下一步：由可验证的官方符号／器件创建路径建立受控网表原生原理图，再逐端子对账并执行真实原生 ERC。不得简单重复本轮已失败的脚本修复。
- 原始证据：`evidence/native-library/09a965e44457e53c-retry-01-symbol-build.log`、`native/native-project-inspection.json`。

### BLOCK-02：未决封装、连接器和供应资料

- 254 条封装映射中 140 条仍 BLOCKED；仅 114 条通过编号焊盘匹配。
- 26 种系统 Device 的脚号集合／焊盘编号集合 PASS，不代表原厂 land pattern、mask／paste、装配或供应资格。
- JBD 原厂显示接口／光机／FPC 资料、BTB／显示／摄像／充电连接器正式封装和实物装配资料未齐。
- nRF5340 及匹配／天线、主被动器件、电池与结构件未完成原生布局。
- 下一步：先冻结正式器件与资料，再补齐 PCB；不能选择“相近封装”直接投板。
- 原始证据：`evidence/kicad-source-audit.json`、`evidence/pad-audit/native-pad-audit.json`、`../H03_PCB_INPUTS.md`。

### BLOCK-03：桥板两件器件无合法候选

- `U14 / U_AVDD_WD`、`U10 / U_AVDD_QUAL` 在既有锚点和有界 0.20 mm 全 bbox 搜索中无合法候选。
- 此结论是 `BLOCKED_NO_LEGAL_CANDIDATE_IN_SEARCH`，不是全局数学无解。
- 下一步：连同 U8 冲突、真实连接器及全被动器件一起重新规划桥板双面布局，不能仅移动这两个器件就宣称可行。
- 原始证据：`layout/candidate-placement-plan.json`、`layout/review-3/geometric-audit.json`。

### BLOCK-04：Codex 原生回件审核未通过

- `review_kimi_return.py` 实际退出码 2。
- `native_review=BLOCKED`、`manufacturing=BLOCKED`；三板 KiCad 原生输入仍被审核脚本标记缺失。
- 本次交付真实 `.epro2`，没有通过伪造 `.kicad_sch`／`.kicad_pcb` 来绕过审核。
- 原始证据：`evidence/codex-review/KIMI_NATIVE_REVIEW.json`、`review-command.log`。

## P0：制造、光学、机械与安全

### BLOCK-05：板厂能力与叠层／阻抗未冻结

- 观察到 6 铜层及已保存基础标量规则，不等于板厂接受完整工艺。
- 未确认 6 层 2+2+2 叠层、介质、铜厚、阻抗、盲埋孔层跨、微孔填铜／盖帽、VIPPO、桥板 0.50 mm 目标。
- 0.20 mm courtyard 原生 device-to-device 规则、0.25 mm copper-to-edge 完整矩阵、USB／RF 阻抗几何仍未获供应确认。
- 不得把线宽／间距／孔径写成“可制造”或降低已批准约束。
- 原始证据：`evidence/board-rule-limitations.json`、各板最终 `fresh-board.json`。

### BLOCK-06：双目透明 AR 与 FPC 实装未验证

- 双目架构保留，但 JBD 原厂资料缺失；双目显示链路、光机外形、出瞳／视场、透明波导、FPC 弯折与连接器插拔空间未验证。
- 本次候选 PCB 不是双目光学可行性证明。
- 下一步：取得受控原厂资料后，将光学引擎、FPC、连接器、驱动电源、结构腔体和散热联合审查。
- 原始证据：`../H03_PCB_INPUTS.md`、当前工程的明确 BLOCKED 描述。

### BLOCK-07：镜腿、整机装配、40 g 和热／声学未证明

- 46 mm 主板、22 × 4.2 mm 桥板、34 × 5.2 mm 右板只是原生板框候选，不是镜腿内腔装配通过。
- 双电池、配重、鼻梁／耳后／太阳穴受力、铰链折叠、近视／散光镜片适配、摄像头视角、扬声器／麦克风孔、EMC、散热、功耗与温升未验证。
- 未建立完整重量清单、重心模型、热仿真或样机测试，**40 g 未证明**。
- 主板 SoC、桥板 FPGA、充电／电源与双面器件的装配高度和热路径未通过实装认证。
- 下一步：结构、热、声学、电池安全、光学和 PCB 联合评审后才能冻结外形。

### BLOCK-08：RF／SI／PI 未完成

- nRF、天线、馈线、匹配、ESP32 RF、USB、MIPI／显示相关接口及电源完整性未验证。
- RF keepout region 的存在不代表天线／射频认证。
- 48 MHz 对应焊盘中心重合只用于候选局部优化，不等于合法走线、过孔、回流路径、阻抗、SI 或启动可靠性。
- 不得在缺少叠层、厂家 impedance 和完整原理图时开始所谓“最终合法布线”。

## P1：交付覆盖限制

### BLOCK-09：主板 STEP 未导出

- 主板官方 STEP 为 22,150,672 bytes，超过 20 MiB 传输上限；无 `board.step`。
- 三板 OBJ 和桥板／右板 STEP 已实际导出；主板仅保留 OBJ，不删模型伪造 STEP。
- 详见 `3d/3D_AND_BINDINGS.json` 与原始导出日志。

### UNVERIFIED-01：视觉／3D 实装检查覆盖不完整

- 35 个已放置候选均有模型绑定，但只是 `binding-only`，`autoGenerateModels:false`。
- 不包含未放器件和整机结构；`previewVerified:false`。
- 官方画布截图受隐藏标签页限制；`actual-both.svg` 是辅助回读渲染，不是官方整板截图或结构装配认证。

### UNVERIFIED-02：实物验证不存在

- 未打样、未焊接、未上电、未测量功耗／温度／射频／声学／光学／质量。
- 受控 KiCad ERC PASS 仅是原理图检查，不是硬件功能证明。
- 摄像头隐私灯的供电／实际采集联动架构未删改，但硬件联动仍需实物验证。
