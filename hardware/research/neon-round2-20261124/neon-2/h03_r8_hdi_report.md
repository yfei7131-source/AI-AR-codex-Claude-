# H03-R8 专项攻关报告｜二阶 HDI 层跨工具阻断根因、K4 错孔整改与 0.80 mm 板厂 EQ 包

- **项目基线**：智元跃动 AI/AR 智能眼镜 V1.0（EVT-1 H03 R8），承接 [PR #55 (R7)](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55)（分支 `hardware/kimi-evt1-h03-r7-20261123`，提交 `ac38a71947f5d7bdd4e5d193584fbb7c6c05363c`）
- **核心攻关目标**：定位并解决 R7 请求创建 `L2–L3` 微盲孔却退化为普通通孔（`NORMAL`）的工具阻断，验证嘉立创 EDA 专业版二阶 HDI 层跨创建方法与 API 能力，制定 K4 四项孔距错误可执行整改方案，并完善 `0.80 mm` 六层二阶 HDI 板厂 EQ 技术包。
- **状态声明**：**`NOT FOR FAB`**。不降低任何制造/DRC 规则，不虚报板厂签核；原生 EasyEDA Pro 写回验证与 GitHub 分支/Draft PR 推送因当前环境无本地 Windows EasyEDA Pro 守护进程且未登录 GitHub，已按规程明确登记为 **`BLOCKED`**。

## 1. R7 工具阻断根因定论：为何请求 L2–L3 微盲孔退化为普通通孔

依据对 [PR #55 Files changed](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55/files) 中 `HDI_DECISION.md`、`hdi/r7-hdi-span-probe.ses`、`verification/hdi-span-probe-archive-diff.json` 与嘉立创 EDA 专业版官方文档的交叉核对，R7 阻断的**直接根因已 100% 锁定**：

1. **R7 实测现象**：R7 通过 Specctra Session (`.ses`) 定义 `padstack r7_bv_l2_l3`（仅含 `Inner1`/`Inner2` 圆形焊盘）及 `(via r7_bv_l2_l3 180 318 (contact Inner1 Inner2) (type route))`，并经本地 Windows CLI（`easyeda.exe`，端口 `127.0.0.1:60832-60841`）导入保存。归档差异显示新增过孔 `["VIA", "ebcd6e8ba51e304e"]`（网络 `I2S_LRCLK_1V8`，坐标 `(180, 318)`）的 `ruleName` 为 `""`，`viaType` 退化为 `"NORMAL"`（普通通孔）。
2. **底层数据模型约束**：根据 [EasyEDA Pro 文件格式文档（Pads and Vias > VIA）](https://prodocs.easyeda.com/en/format/pcb/pad_via/#via-via) 与 [`PCB_PrimitiveVia.create()` API 文档](https://prodocs.easyeda.com/cn/api/reference/pro-api.pcb_primitivevia.create.html)：
   - 过孔图元本身**不直接接受 `startLayer` / `endLayer` 参数**；层跨完全由引用**设计规则中已预先注册的盲埋孔规则名**（文件格式第 9 字段 `ruleName` / API 参数 `designRuleBlindViaName`）决定，同时需设置 `viaType = EPCB_PrimitiveViaType.BLIND`（枚举值 `1`，见 [`EPCB_PrimitiveViaType`](https://prodocs.easyeda.com/en/api/reference/pro-api.epcb_primitiveviatype.html)）。
   - R7 工程归档中的 `blindViaRules` **仅存在 `BV_L1_L2`（`staLayerId: 1, endLayerId: 15`）和 `BV_L5_L6`（`staLayerId: 18, endLayerId: 2`），不存在 `BV_L2_L3`、`BV_L3_L4`、`BV_L4_L5`**。
   - `easyeda pcb via` 与 `.ses` 导入链路均**不会自动注册新的 `blindViaRules` 条目**；当目标层跨无对应规则名时，编辑器静默回退为 `ruleName: ""` 与 `viaType: "NORMAL"`。

## 2. 嘉立创 EDA 专业版二阶 HDI 层跨创建方法与 API 能力核实

已通过远程浏览器逐一核查 [扩展 API 参考总览](https://prodocs.easyeda.com/cn/api/reference/pro-api.html)、[`PCB_Drc` 全量方法表](https://prodocs.easyeda.com/cn/api/reference/pro-api.pcb_drc.html)、[盲埋孔用户指南](https://prodocs.easyeda.com/cn/pcb/place-blind-buried-via/)、[命令行客户端文档](https://prodocs.easyeda.com/cn/api/guide/cli.html) 与 [Gerber 导出规范](https://prodocs.easyeda.com/en/pcb/export-pcb-fabrication-file-gerber/)：

| 能力项 | 官方核实结果 | 接口/操作路径与约束 | 证据链接 |
| :--- | :--- | :--- | :--- |
| **专用盲埋孔规则创建 API** | **不存在** | 全部 31 个 PCB 相关类中无 `addBlindViaRule` / `createBlindViaRule` 等专用接口 | [pro-api.html](https://prodocs.easyeda.com/cn/api/reference/pro-api.html) |
| **通用规则配置读写 API（BETA）** | **存在（需核验键名）** | `PCB_Drc` 提供 `getCurrentRuleConfiguration()`、`overwriteCurrentRuleConfiguration()`、`saveRuleConfiguration()`（共 37 个不重复方法），数据结构为 `Record<string, any>`；可用于读取并追加 `BV_L2_L3`/`BV_L3_L4`/`BV_L4_L5` 而不改动任何间距规则 | [pro-api.pcb_drc.html](https://prodocs.easyeda.com/cn/api/reference/pro-api.pcb_drc.html) |
| **原生 GUI 盲埋孔规则注册** | **官方正式支持（100% 可靠）** | `设计规则 -> 物理规则 -> 盲埋孔 (blindVia) -> 点击 "+"` 添加规则（配置 `Name`、`Start Layer`、`End Layer`，限制：顶层起始时结束层不可为底层） | [place-blind-buried-via](https://prodocs.easyeda.com/cn/pcb/place-blind-buried-via/) |
| **API 放置二阶盲/埋孔** | **支持（前提：规则已注册）** | `eda.pcb_PrimitiveVia.create(net, x, y, holeDiameter, diameter, 1, 'BV_L2_L3', null, false)`，并用 `getState_ViaType()` 与 `getState_DesignRuleBlindViaName()` 读回校验 | [pcb_primitivevia.create](https://prodocs.easyeda.com/cn/api/reference/pro-api.pcb_primitivevia.create.html) |
| **原生 DRC 严格检查 API** | **支持** | `eda.pcb_Drc.check(true, false, true)`（`includeVerboseError: true` 返回详细错误数组）或 `checkDetailed()` | [pcb_drc.check_1](https://prodocs.easyeda.com/cn/api/reference/pro-api.pcb_drc.check_1.html) |
| **钻孔文件分层导出** | **支持（对齐 JLCPCB）** | 自动按盲埋孔层跨输出独立钻孔文件（如 `Drill_PTH_Inner1_to_Inner2.DRL`），直接匹配 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 对盲埋孔按层跨拆分钻孔文件的要求 | [export-pcb-fabrication-file-gerber](https://prodocs.easyeda.com/en/pcb/export-pcb-fabrication-file-gerber/) |

**标准六层二阶 HDI（2+2+2）需注册的 5 条盲埋孔规则表**：

| 规则名（`designRuleBlindViaName`） | 物理层跨 | EasyEDA 内部层 ID（承接 R7 归档） | 钻孔工艺 | 建议钻孔 / 捕获盘尺寸（JLCPCB 合规） |
| :--- | :--- | :--- | :--- | :--- |
| `BV_L1_L2` | Top (L1) ↔ Inner1 (L2) | `1 ↔ 15`（已存在） | 激光盲孔（电镀填铜） | Ø100 μm (3.94 mil) / Ø252.4 μm (9.94 mil) |
| `BV_L2_L3` | Inner1 (L2) ↔ Inner2 (L3) | `15 ↔ 16`（**R7 缺失，R8 新增**） | 激光盲孔（电镀填铜） | Ø100 μm (3.94 mil) / Ø252.4 μm (9.94 mil) |
| `BV_L3_L4` | Inner2 (L3) ↔ Inner3 (L4) | `16 ↔ 17`（**R8 新增**） | 机械埋孔（树脂塞孔盖帽） | Ø152.4 μm (6.0 mil) / Ø304.8 μm (12.0 mil) |
| `BV_L4_L5` | Inner3 (L4) ↔ Inner4 (L5) | `17 ↔ 18`（**R8 新增**） | 激光盲孔（电镀填铜） | Ø100 μm (3.94 mil) / Ø252.4 μm (9.94 mil) |
| `BV_L5_L6` | Inner4 (L5) ↔ Bottom (L6) | `18 ↔ 2`（已存在） | 激光盲孔（电镀填铜） | Ø100 μm (3.94 mil) / Ø252.4 μm (9.94 mil) |

## 3. K4 四项孔距错误可执行整改方案（零规则放宽）

R6/R7 隔离试验中，网络 `I2S_LRCLK_1V8` 新增 4 项 `Hole to Hole >= 11.8 mil` 错误（3 处 `0 mil` 同心叠孔 + 1 处 `5.3 mil` 激光孔到埋孔）。R8 整改方案采用**全错孔（Staggered Microvia）+ 埋孔错位**，在**完全保留 EasyEDA Pro 原生 11.8 mil 孔距规则、项目 6.0 mil（0.1524 mm）铜距规则与 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) 最小 3 mil 单边环宽**的前提下，通过离线几何校核脚本 `r8_k4_geometry_verifier.py` 验证全部相邻孔对：

| 过孔对（网络 `I2S_LRCLK_1V8`） | R6/R7 失败值 | R8 错孔参考坐标 (mil) | R8 中心距 (mil) | R8 孔壁距 (mil / mm) | R8 盘间距 (mil) | 原生 11.8 mil / JLCPCB 5.0 mil |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `e53_r8 (BV_L1_L2)` ↔ `e54_r8 (BV_L2_L3)` | `0 mil`（`err0`） | `(179.47, 328.00)` ↔ `(195.47, 328.00)` | `16.0000` | `12.0630` (`0.3064 mm`) | `6.0630` | **PASS / PASS** |
| `e54_r8 (BV_L2_L3)` ↔ `e55_r8 (BV_L3_L4)` | `5.3 mil`（`err1`） | `(195.47, 328.00)` ↔ `(195.47, 311.00)` | `17.0000` | `12.0315` (`0.3056 mm`) | `6.0315` | **PASS / PASS** |
| `e53_r8 (BV_L1_L2)` ↔ `e55_r8 (BV_L3_L4)` | 未单独报错 | `(179.47, 328.00)` ↔ `(195.47, 311.00)` | `23.3452` | `18.3767` (`0.4668 mm`) | `12.3767` | **PASS / PASS** |
| `e56_r8 (BV_L4_L5)` ↔ `e57_r8 (BV_L5_L6)` | `0 mil`（`err2`） | `(102.97, 301.00)` ↔ `(118.97, 301.00)` | `16.0000` | `12.0630` (`0.3064 mm`) | `6.0630` | **PASS / PASS** |
| `e58_r8 (BV_L4_L5)` ↔ `e59_r8 (BV_L5_L6)` | `0 mil`（`err3`） | `(137.97, 376.00)` ↔ `(153.97, 376.00)` | `16.0000` | `12.0630` (`0.3064 mm`) | `6.0630` | **PASS / PASS** |

*(注：上述 `±16.0 mil / ±17.0 mil` 为隔离验证参考偏置；在 PCB3 实板上执行时，需按周边邻近网络与反焊盘开窗避让方向选取无碰撞象限，并由 `r8_hdi_span_and_k4_trial.js` 调用 `eda.pcb_Drc.check(true, false, true)` 现场验收。)*

## 4. 0.80 mm 六层二阶 HDI 板厂 EQ 技术包（R8 增补项）

结合 `HDI_FAB_EQ.md` 既有 EQ-01 至 EQ-07 及本轮离线脚本校核结果，R8 明确增补以下板厂提交附件与 **EQ-08**：

1. **三档合规 0.800 mm 叠层方案（已通过 `r8_k4_geometry_verifier.py` 校核）**：
   - 基准候选：`4 × 50 μm PP`（[JLCPCB FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) `S1000-2MB-106 RC72%`）+ `418 μm Core`（AR: 75 μm 为 `0.667`、100 μm 为 `0.500`）；
   - 稳健备选 1：`4 × 55 μm PP` + `398 μm Core`（AR: 75 μm 为 `0.733`、100 μm 为 `0.550`）；
   - 稳健备选 2：`4 × 60 μm PP` + `378 μm Core`（AR: 75 μm 为 `0.800`、100 μm 为 `0.600`）；
   - **否决边界**：若采用 `86 μm (1078/1080)` PP，在 0.800 mm 总厚下芯板跌至 `274 μm`（违反 [JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb) `≥ 300 μm` 埋孔芯板下限），且 75 μm 激光孔纵横比升至 `1.147`（违反 `≤ 1:1`）。
2. **增补 EQ-08（钻孔文件命名与层跨验收）**：向 JLCPCB 审单工程师确认，由 EasyEDA Pro 导出的独立分层钻孔文件（`Drill_PTH_Top_to_Inner1.DRL`、`Drill_PTH_Inner1_to_Inner2.DRL`、`Drill_PTH_Inner2_to_Inner3.DRL`、`Drill_PTH_Inner3_to_Inner4.DRL`、`Drill_PTH_Inner4_to_Bottom.DRL`）是否可直接按 2+2+2 错孔压合加工，以及是否要求额外附带 `stackup.pdf` 叠层编号标注。

## 5. 交付清单与实际验证日志

| 交付文件 | 类型 | 实际执行/验证状态 | 说明 |
| :--- | :--- | :--- | :--- |
| `H03_R8_HDI_REPORT.md` | R8 攻关主报告 | **已生成并核对** | 含 R7 根因定论、EasyEDA Pro API 能力表、K4 整改方案与阻断清单 |
| `r8_hdi_span_and_k4_trial.js` | EasyEDA Pro 原生执行脚本 | **已编写，待本地 Windows 宿主机运行** | 实现规则审计、二阶层跨注册、错孔创建、读回防回退检查及原生 DRC |
| `r8_k4_geometry_verifier.py` | 离线几何与叠层校核脚本 | **已在沙箱实跑通过（Exit 0）** | 校验 4 组叠层预算与 5 组相邻错孔间距（最小孔壁距 `12.0315 mil`） |
| `r8_offline_verification_log.json` | 实际离线验证日志 | **已由脚本实时生成** | 时间戳 `2026-11-23T22:54:18Z`，明确标注原生 DRC 状态为 `BLOCKED` |
| `HDI_FAB_EQ.md` | 板厂 EQ 技术包（上一轮已交付） | **已完成并保留在工作目录** | 包含 EQ-01 至 EQ-07、JLCPCB 与 GS Swiss 对比及阻断项 |

## 6. 明确阻断项（BLOCKED）与本地宿主机一键闭环步骤

1. **`BLOCKED-R8-01`｜原生 EasyEDA Pro 独立工程验证无法在当前云端沙箱执行**：
   - **阻断原因**：[PR #55](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55) 未提供可公开访问的 EasyEDA Pro 云端工程链接或账号，原生验证依赖本地 Windows 宿主机上的 `C:\Users\Admin (无密码) \.local\bin\easyeda.exe`（`127.0.0.1:60832-60841`）；当前环境无桌面版 EasyEDA Pro 与出站网络。**未伪造 `.epro2` 归档或原生 DRC 通过日志。**
   - **本地闭环命令**：在 Windows 宿主机打开隔离副本工程（复制自 `native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2`），通过 EasyEDA Pro 内置 CLI 或扩展脚本运行 `r8_hdi_span_and_k4_trial.js`，保存后执行关闭重开持久化检查，并留存输出 JSON 与重导出 `.epro2`。
2. **`BLOCKED-R8-02`｜GitHub 独立分支与 Draft PR 无法由当前未登录会话直接推送**：
   - **阻断原因**：远程浏览器访问 [PR #55](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55) 为未登录访客态（右上角显示 `Sign in` / `Sign up`），且沙箱 VM 无出站网络；按规程未反复尝试 GitHub 登录。
   - **本地闭环命令**（在已鉴权的本地仓库根目录执行）：
     ```bash
     git fetch origin hardware/kimi-evt1-h03-r7-20261123
     git checkout -b hardware/evt1-h03-r8-20261123 origin/hardware/kimi-evt1-h03-r7-20261123
     mkdir -p hardware/evt1-native-eda-20261118/h03-r8-20261123/{hdi,tools,verification}
     # 将本轮交付文件及宿主机实跑后的 .epro2 / 原生 DRC 日志放入对应子目录
     git add hardware/evt1-native-eda-20261118/h03-r8-20261123/
     git commit -m "H03-R8: 2nd-order HDI span fix, K4 staggered trial, and EQ package (NOT FOR FAB)"
     git push -u origin hardware/evt1-h03-r8-20261123
     gh pr create --draft --base hardware/kimi-evt1-h03-r7-20261123 --head hardware/evt1-h03-r8-20261123 --title "EVT-1 H03 R8 2nd-order HDI span & K4 trial (NOT FOR FAB)"
     ```
3. **`BLOCKED-R8-03`｜板厂 EQ 签核与 0.35 mm BGA 盘距冲突仍未闭合**：在 JLCPCB 或备选高精密厂对 EQ-01 至 EQ-08 出具书面回复前，严禁移除 `NOT FOR FAB`。
