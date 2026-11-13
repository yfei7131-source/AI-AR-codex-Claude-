# STATE — evt0-r5-rework（2026-11-13 第二轮）
完成：S0–S4（PCB ec8419f1）+ S5 VBUS/VSYS；缺口51，PCB sha256前缀 dc5f98a7。原生ERC/DRC/重铺：NOT RUN。
下一步：1) 有KiCad时 bash tools/run_native_checks.sh evt0_core（SC_BEFORE=58 SC_AFTER=51），先看J3短线零余量、PGOOD/过孔与内层铜间距；2) USB DP/DM差分对（J1→U2→U1.13/14），需叠层确认、耦合布线、回流分析，不以1.0mm长度差代替阻抗分析；3) 余缺口：音频UART2、显示9、相机。
GitHub Draft PR：未创建（沙箱无网络/gh）。约束：R4/R5只读；R28/J3/J4/DNP不变；不降规则、不绕联锁。

## 第三轮
PCB仍 dc5f98a7，51缺口。原生检查 NOT RUN；USB差分阻断（需叠层/阻抗/工艺参数，且USB类0.25孔需改为≥0.30）；Draft PR 未建。
下一步需：KiCad环境运行 run_native_checks.sh；用户提供叠层与90Ω目标；GitHub 访问权限或让我输出 git bundle。

## 第四轮（S0–S6 r4）
PCB 现为 **c0f1ca5c**（SHA256 `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`）；SCH 不变 `81d599e6d107…`。新增 S6：删除R4既有GND悬空短线 40b55a19（D1.2处0.255mm冗余短线），缺口仍51、模型悬空0。原生ERC/DRC/重铺：**NOT RUN**（无KiCad），见 evidence/native_NOTRUN_S6。
下一步仍为：1) KiCad 10.0.7 内 `bash tools/run_native_checks.sh evt0_core`（先看 J3 短线零余量、PGOOD↔CHG_EN1 过孔0.035mm、VSYS约35mm DNP段）；2) USB 仍阻断（需叠层/90Ω/工艺，USB类过孔0.25→≥0.30）；3) 余缺口按原生重铺后重新统计。GitHub：未建PR。

## 第五轮 stage1（2026-11-13 新窗口；PCB/SCH 未改，仍 c0f1ca5c / 81d599e6）
- 入包ZIP SHA256 `ab6fd780937599660f06a0343b9bca84aa8a0f47a47e66f2e90a5a05d2041587`；包内249文件哈希 249/249 OK；PCB/SCH 与上文一致。证据 `evidence/round5_baseline_integrity/`。
- 原生 ERC/DRC/覆铜重铺/parity：**NOT RUN**。`run_native_checks.sh` 实跑退出码2；环境探测（无 kicad-cli/pcbnew/dpkg 包、无网络、pip/apt 不可用）见 `evidence/native_NOTRUN_round5_start/`。
- 离线自检复现（zy_pcb，**非原生**）：缺口51 / 违规0 / 悬空0，与STATE一致。
- 新增断点工具 `tools/make_stage_zip.py`（仅打包+重算SHA256，非检查器）。
- 下一步：S7（见CHANGELOG第五轮）；有KiCad时第一动作仍为 `SC_BEFORE=51 bash tools/run_native_checks.sh evt0_core`。

## 第五轮 S7（R5 S0–S7 r5）
PCB 现为 **b6ff6dd2**（SHA256 `b6ff6dd25e6bbd05912485d4e4d8b766747021804476e2e6c94f3ec786518935`）；PRO `88775ef8793c…`；SCH 不变 `81d599e6d107…`。几何与 c0f1ca5c 逐字节相同，仅标题栏标识更新；网络类默认过孔改 0.6/0.30。缺口仍51、违规0、悬空0（离线，非原生）。原生ERC/DRC/重铺/parity：**NOT RUN**（无KiCad、无网络）。
关键事实：R4 有真实 KiCad 10.0.7 原生DRC（15违规：12孔径+3库不一致；58未连接；parity 0）；离线模型逐网复现该58（差异为空）→ R5 预期原生 unconnected=51（预测，非结果）。
40 g：仅算术——`MASS_BUDGET.json` 分配合计 50 g（=工程目标50g），距 40 g 挑战差 10 g；CAD概念模型 43.4 g（含假设项，非称重，无储备）。未虚构任何实测质量。
下一步：1) 有KiCad → 按 `NATIVE_RUN_PLAYBOOK.md`；2) 仍无KiCad → 不再重复空转，等待用户提供 KiCad 环境或叠层/90Ω/板厂能力；3) USB 仍阻断。GitHub：未建PR，无新Commit。
