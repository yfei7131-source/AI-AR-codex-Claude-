> **最新工程头 = R5 S0–S6 r4，PCB SHA256 `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`（前缀 c0f1ca5c）。** 下文第一～五节记录的是 13:46 的 r3（dc5f98a7），已被第六节更新；以第六节为准。

# ZY AI/AR H02/H03 R5 新窗口续接状态（以2026-11-13 13:46 Claude记录为准）

## 一、真正已交付、可持续迭代的最新工程

- 位置：`github-pr4/hardware/evt0-r5-rework/evt0_core/`
- PCB：`evt0_core.kicad_pcb`；SHA-256：`dc5f98a7b45fd428bca0fe21d0d779b6cabd7f3f8a63cf296d51d9ac0a63e3ff`。
- 原理图：`evt0_core.kicad_sch`；SHA-256：`81d599e6d107563f43d2521262fd50ffaea25e8457332b169c59d1ca32a142e6`。
- 已交付版本 **R5 S0–S5 r3**。这份文件与上一轮r3已交付工程一致；**13:46这轮没有保存新的PCB更改**。
- H03布线：自定义工具统计原R4未连58 → 此版51，仍未连51，**不是 KiCad 原生DRC结论**。
- 记录的已完成步骤：S1 PGOOD 9段线+1via；S2 U1 12处热孔0.20→0.30mm；S3 U1/J3/J1本地封装同步；S4 J3 GND 4段线+4via；S5 VBUS 7段/VSYS 8段0.30mm线。
- `STATE_R5_REWORK.md`、`VERIFICATION_REPORT.md`、`CHANGELOG_R5_REWORK.md`、`USB_DIFF_BLOCKERS.md`、BOM、所有工具与证据已包含在同一工程目录。

- 随附只读对照工程 `github-pr4/hardware/evt0-r4-review/` 与 `github-pr4/hardware/evt0-r5-experimental/`，勿直接修改。

## 二、13:46这一轮实际尝试的工作

- 读取R5 S0–S5 r3，检查沙箱环境，无kicad-cli，无法完成原生ERC、DRC或覆铜重铺。
- 根据对话记录，调用了34次工具；创建了离线网络/几何/局部覆铜近似与USB微带阻抗计算脚本。
- **该轮被限额中断，未看到新的可下载工程ZIP、原生ERC/DRC结果、实物验证或GitHub提交。**
- 我们从日志恢复了可能有用的Python源代码，单独放在 `RECOVERED_1346_UNVERIFIED/`，不可作为完成验证的依据。

## 三、未完成阻断项（严格保持）

1. 原生KiCad 10.0.7 ERC/DRC = **NOT RUN**；In1/In2覆铜**未重铺**，不可生成Gerber或制造放行。
2. GND历史悬空线 `(130.5,117.95)→(130.25,118.0)` 待确认；J3短线零余量、PGOOD vs CHG_EN1 过孔仅0.035mm余量、VSYS约35mm长线均待原生复核。
3. USB_DP/DM **未布线**；板厚约1.0mm但无受控叠层参数、介质Dk/介质厚/铜厚/阻焊/板厂工艺，90Ω差分阻抗尚未设计确认。项目USB网络类的过孔钻孔0.25mm低于板级0.30mm门槛，后续整改不得降低板级规则。
4. 其余自定义工具缺口51（相机32、显示9、USB8、音频UART2）；要以原生重铺后的结果重新统计。
5. GitHub已有PR#4历史基线，但**此次r3和13:46增量尚未在本轮提交/验证成功**；不得宣称已推送。
6. 原版R4、R5实验历史、硬件隐私联锁、DNP、安全和板厂制造规则均保持不变。

## 四、下一轮执行优先级（先保存文件，再继续工程）

P0：读取工程并校验PCB哈希；立即创建工作副本及首次快照ZIP。保留历史工程完整字节。

P1：**如果有 KiCad 10.0.7**，在工作副本里执行 `tools/run_native_checks.sh`（DRC含 `--refill-zones`）、原生ERC/DRC和parity，将原始报告/退出码/重铺PCB留存在新工程包；基线验收必须比较。**若没有KiCad，标记NOT RUN，禁止改成通过。**

P2：先排查GND悬空、J3/PGOOD与覆铜，再做电源完整性复核。无叠层与板厂确认前USB保持阻断；可将恢复的三个辅助脚本作为未验证候选研究，但不要反复开发新替代KiCad检查器。

P3：每完成一项真实工程修改立刻更新CHANGELOG、STATE、验证记录，并输出完整可编辑工程ZIP；GitHub能访问则建立独立Draft PR并核对远程SHA，否则写明不可用，不阻止工程文件交付。

## 五、工程验收口径

提供 `.kicad_pcb/.kicad_sch/.kicad_pro/.kicad_dru`、项目封装库、符号库、BOM、变更记录、原生报告（有环境才可生成）、最新 `STATE_FOR_NEXT_SESSION.md` 和完整ZIP。**不得仅输出解释或脚本；未过原生验证不得称DRC通过。**


## 六、第四窗口（2026-11-13）增量 —— 以此为准
- **S6 已完成**：删除GND悬空短线 uuid 40b55a19（D1.2处，0.255mm冗余）。PCB `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`；SCH 不变 `81d599e6d107563f43d2521262fd50ffaea25e8457332b169c59d1ca32a142e6`。
- zy_pcb 自检（非原生）：缺口51（不变）、违规0、悬空1→0。差异仅 -8行/-157字节（evidence/step6_gnd_stub/S6_diff.patch）。
- 原生 ERC/DRC/覆铜重铺/parity：**NOT RUN**（全盘无KiCad、无网络）。证据 `github-pr4/hardware/evt0-r5-rework/evidence/native_NOTRUN_S6/`。
- 下一轮：KiCad 10.0.7 环境先 `bash tools/run_native_checks.sh evt0_core`；再复核 J3 零余量短线、PGOOD↔CHG_EN1 过孔(0.035mm)、VSYS(35mm，仅连DNP J4.2)。USB 继续阻断。
- GitHub：不可用，无Draft PR/Commit SHA。新窗口提示词见 `COPY_TO_CLAUDE_新窗口提示词_r4.txt`（原提示词保留未改）。
