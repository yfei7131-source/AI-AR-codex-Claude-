# EVT-1 H01–H05 原生电气工程 · NOT FOR FAB

基线为 PR #25，提交 `97ee1f6733416099f842dca00389ab50f3568c96`。本目录是独立的 EVT-1 原理图和 PCB 设计输入。打开下列工程的对应 `.kicad_pro` 后进入原理图，三板各自有本地符号库和按功能分组的可编辑层级图页。

| 工程 | 用途 |
|---|---|
| [evt1-main-left](kicad/evt1-main-left/evt1-main-left.kicad_pro) | 左镜腿主控、电池与电源、摄像头和板间接口 |
| [evt1-optical-bridge](kicad/evt1-optical-bridge/evt1-optical-bridge.kicad_pro) | FPGA、48 MHz 时钟、AVDD 监督、双眼板端接口 |
| [evt1-audio-right](kicad/evt1-audio-right/evt1-audio-right.kicad_pro) | 右镜腿音频、nRF5340、右电池和连接器 |

`Inputs/effective_*.csv` 是受控电气输入，`kicad/CAD_TERMINALS.csv` 对应 KiCad 位号和源端子。三板的同名标签分别属于各自 PCB。板间连通由实际连接器和配对的 FPC 决定。原理图保留 JBD 板端预留，未知供应商端参数由阻断清单控制。

本轮补齐 FPGA PLL/VPP 和供电端的漏项、时钟接地及去耦。原 ASFLMB 实际为 5032 封装，超过桥板当前 TOP 器件间的可用区段。改用满足 48 MHz、1.8 V 和 2016 包体条件的 ASADV 候选，须通过样品启动、负载及电压温度复测。成本按现有电源/SoC 分区控制，先统一已验证的无源件封装和采购合并项，再核算单机物料及 HDI 工艺报价。物料成本、整机功耗和质量尚未实测。

维持双目透明 AR 和 40 g 指标。PR #25 原估算为 41.2408 g，满足其特定条件的集成方案估算为 39.423 g。新版需计入板间互连、实选连接器、封装几何和装配公差后重建账本。保留已验证 FPGA，待光机协议和真实负载确认后再评估降低扫描占空比的条件。

- 生成电气输入并对账：`python Inputs/build_effective_inputs.py --check`。
- [原厂资料复核与方案取舍](Inputs/electrical_source_audit.md)及[台架验证状态](Inputs/bench_gates.csv)。
- 重建原生原理图：`python tools/generate_kicad.py`。
- 原生 ERC 和网表回读：`python tools/verify_kicad.py --kicad-cli kicad-cli --output <独立证据目录>`。使用 KiCad 10。
- [逐对象封装映射](FOOTPRINT_MAP.csv)、[PCB 分板与制造约束](H03_PCB_INPUTS.md)及其[机器可读输入](PCB_CONSTRAINTS.json)。
- [主机到 FPGA 通信契约](host/INTERFACE.md)。使用 `python host/check_bridge.py` 运行线序回归，需 Icarus 和 vvp。原 Rev D1.1 显示、关断、综合、路由和 STA 由 CI 重跑。
- [KIMI 实施与回件要求](KIMI_HANDOFF.md)。

证据以工程哈希、原生工具日志和 CI 结果为准。PASS、FAIL、BLOCKED、UNVERIFIED 分别表示检查通过、检查失败、缺少输入无法执行和现有设计尚待确认。原理图和接口输入可供审查，布板后的原生 DRC、供应商 DFM、JBD 参数和实物验收是制造门禁。
