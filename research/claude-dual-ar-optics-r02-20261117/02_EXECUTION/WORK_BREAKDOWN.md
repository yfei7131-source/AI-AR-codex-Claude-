# 执行计划：任务有前置条件、输出和验收，而不只是“继续研究”

## 阶段 0：基线盘点（所有人先做，阻断后续改图）
**T00 / WorkBuddy + Codex / 无需 JBD NDA**  
输入：最新可访问仓库及真实 Rev D1 ZIP，历史本包。  
操作：确认 HEAD/分支/时间/修改文件/变更责任；定位 SCH/PCB/BOM/PINMAP/ICD/RTL/firmware/测试脚本；对照 ECR 表查已有重复修改。  
输出：`BASELINE_AUDIT.md`、`SOURCE_FILE_INDEX.csv`、`CONFLICT_DIFF.md`、`README.md` 引导；不修改设计。  
验收：每个被引用文件有真实路径+commit/hash；未发现的项明确 `MISSING`，不虚构路径；工作树保持 clean。

## 阶段 1：可独立执行的设计准备（可并行，禁止覆盖电气主线）
**T01 / Claude / 显示协议证据闭环 / P0**  
输入：R0.2报告、具体 JBD SKU/模组修订。操作：把供应商问题清单与官方资料需求形成一份请求；整理裸面板与 Mini II 的差异对照；为 G1–G6 设计实验记录模板。  
输出：`JBD_VENDOR_QUESTIONS.md`、`JBD_DATASHEET_GAP_MATRIX.csv`、`EVK_BENCH_PROCEDURE.md`、附 E2/E4 状态标签的证据表。  
验收：无未注明来源的 pin/power/command 数字；能逐项指向“谁提供/哪个实测才能关闭”。

**T02 / Gemini / 结构、双目光学和重量 / P0**  
输入：真实结构CAD或约束清单、官方 STEP（如有）、现有完整质量台账。操作：鼻侧/镜腿两条包络比较、刚性副框、公差链、FPC 出线、跨板布线及热分布；建立逐件质量与公差和减重 Pareto。  
输出：`OPTICAL_PACKAGING_3D_CLEARANCE.md`、示意 STEP/参数CAD（真实可编辑文件如工具支持）、`MASS_BUDGET_RECONCILED.csv`、`THERMAL_SCENARIOS.csv`、`ALIGNMENT_FIXTURE_PLAN.md`。  
验收：没有官方 3D 的尺寸标 `PROVISIONAL`；质量总和包含外壳、镜片、波导、光机、PCB/FPC、电池、摄像头、音频、胶、紧固件、连接器；给出40g差距而不改目标。

**T03 / Codex / 接口与 RTL 替身验证 / P0**  
输入：Rev D1 当前实际工程；协议研究；历史 Rev D 文件（如果仓库存在）。操作：建立可配置的光机协议抽象层、模拟/回环测试；审查电源门控、FPGA 的已存在 RTL 测试；保留 P1 作为可回退基线。  
输出：独立分支 PR、参数配置、单测/RTL 仿真（若有工具）、功能差异和 CI 日志。  
验收：默认未配置 JBD 指令时 **fail closed**，不得向未知真实模组发指令；现有功能没有回归；不宣称点亮成功。

**T04 / KIMI / ECAD 草图级 ECR 评估 / P0**  
输入：当前可编辑 ECAD + 已评审 ECR，不能单靠研究报告。操作：先做 J_DISP 逻辑引脚和 pin 数审计（不猜具体 pin）；空间、封装、FPC 和供电路径冲突清单；对已获得原厂证据并批准的项才实际落图。  
输出：`SCHEMATIC_IMPACT_REPORT.md`、`PIN_BUDGET.csv`、`NET_IMPACT.csv`、项目源文件 diff，按条件出 ERC/DRC 日志。  
验收：未获原厂资料的变化不能进入制造版；所有网络带引脚/封装/出处/设计状态。

## 阶段 2：供应商/EVK 门禁（条件触发）
**T05 / Claude+Codex / JBD EVK 点亮**：JBD 官方资料到手→安全供电检查→单眼 ID/复位→写入指定测试图→双眼逐眼 CS/读回→同步实验；留波形、固件版本、串口、功耗原始数据。无 EVK/样品则状态 `BLOCKED`，不“模拟通过”。

**T06 / Gemini+KIMI / 波导与装配**：光机/波导厂家提供公差及3D→更新鼻侧光机舱和副框→公差链/扭转 FEA（如可用）→装配与双相机校准治具→工程图+测量法。若无实物数据仅保留计算，不称完成可靠性。

**T07 / Codex+KIMI / ECR 真实电气修改**：得到设计批准后按 ECR 独立提交；使用最新源树修改 KiCad/EDA/NETLIST/BOM/ICD/固件，执行 ERC、DRC、netlist parity、封装/引脚对照、HDL CI，记录工具版本、命令、退出码、日志，失败即回退/修复。

## 阶段 3：实物 EVT 和收口
**T08**：执行 `EVT_TEST_MATRIX.csv`，不做纸面代测；FPC循环、右电池压降、热像、双目失调、光机亮度与帧同步、逐件称重。  
**T09**：仅在 G1–G6 与实物收益通过后决定 P2/P3、是否删除 FPGA；完成 PR 设计评审。  
**T10**：汇总每一个问题为 `CLOSED / OPEN / BLOCKED`，附正式完整可编辑工程包及制造风险报告，准备 EVT1→下一版变更评审。

## 推荐执行顺序
`T00 → {T01, T02, T03, T04(审核)} → T05/T06(外部输入) → T07(审批落图) → T08 → T09/T10`。
*注意*：T01 和 T02 可独立推进；T03 的软件模拟与 T04 审核可以进行，但不能突破缺失的 JBD 原厂接口门禁。
