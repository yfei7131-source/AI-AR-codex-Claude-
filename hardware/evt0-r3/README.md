# EVT-0 R3 研发交付 — 2026-11-12

**研发审查版本，制造与实机验收均未放行。** 全部22项需求保留，P0/P1/R=16/5/1。当前状态：H01分配和兼容审查已记录；H02原理图通过原生ERC；H03已导入封装并推进电源/低速布线，仍有明确失败项。

## 修改保护与对象

恢复时先执行git status/diff，完整备份132个已修改/新增文件。恢复提交 `739fd328d6c11ba11148a935a6a31882f5340582` 保存中断前成果；后续为增量提交。清单与SHA-256见 [recovery-manifest.json](evidence/recovery-manifest.json)。本机字节原件位于工作区父目录 `.ai-glasses-backups/r3-resume-20261112/`。没有reset、覆盖主干或改动PR #1分支。

本R3板与 `hardware/kicad/s3-carrier-a/`、`hardware/kicad/cam-rail-a/` 是不同工程；后一工程已有的制造文件随恢复提交保留，不能用作R3投板文件。Claude R1/R2原件保留在 `hardware/claude_handoff/2026-11-12/`。

## 当前成果

- [H01状态与实现边界](H01/R3_STATUS.md)、[ICR-01–12](H01/ICR_to_Codex.md)、[十项放行门槛](H01/RELEASE_GATES.csv)：核对完整仓库源码、22个GPIO与22项需求；音频采用独立BM83 EVB的可选UART研发方案，光机继续独立驱动，不把S3 DVP视作显示输出。
- [H02电气审查](H02/evt0_core/ELECTRICAL_REVIEW.md)：相机电源与关轨高阻固件、禁充默认态、TD引脚、ESD引脚、DNP电压选件及端点核对。所有profile保持 `privacy_interlock_verified=false`。
- [H03当前规则/操作说明](H03/H03_STACKUP_AND_RULES.md)与[逐件实际放置](H03/H03_placement_actual.csv)：84件封装、1007段走线、84个过孔、2个内层电源/地填充区。增量保留原147铜项的UUID、几何和网名；修复R3/D1短路、J3/SW1重叠及丝印冲突。
- [独立PCB审查](H03/PCB_REVIEW_R3.md)与[剩余网络清单](H03/remaining_connections.csv)：制造、RF、热、USB和未确认接口继续列为开放问题。
- 原生审查图：[铜线PDF](evidence/pcb-copper-review.pdf)、[顶面装配PDF](evidence/pcb-assembly-review.pdf)、[背面装配PDF](evidence/pcb-back-assembly-review.pdf)。它们是审查图，不是制造批准。

## 真实验证

| 检查 | 本次结果 | 证据 |
|---|---|---|
| 软件unittest | 102/102，exit 0 | `evidence/resume-software-tests.txt` |
| 固件主机C编译/执行 | 20核心+18媒体+9相机API桩故障检查=47/47，exit 0 | `evidence/resume-firmware-host-tests.txt` |
| ESP-IDF v5.4.3四种既有构建 | unconfigured/EYE/EVT0/EVT0-AP各27源文件集合和SHA、磁盘bin长度/SHA及完成日志匹配；本次未重编/烧录 | `evidence/resume-idf-revalidation.json` |
| H01源合同 | 22项、22 GPIO、84实体器件一致，exit 0；十项门槛仍开放 | `evidence/h01-contract.json` |
| Halo emulator | 三种命令分块均65536像素一致；physical=false | `evidence/halo-emulator-resume.json` |
| KiCad 10.0.7 ERC | 0错误/0警告，exit 0；284唯一引脚/22种封装核对 | `evidence/evt0-erc.rpt`、`evt0-erc-inputs.json` |
| PCB网表映射/保护 | 305物理编号焊盘、284唯一引脚、封装/DNP/BOM一致；原147铜项全部未变 | `evidence/pcb-verification.json` |
| KiCad 10.0.7 DRC | **失败，exit 5**：15规则违规（12孔径错误+3封装库图形差异警告）、59未连接、0原理图一致性问题 | `H02/evt0_core/evidence/pcb-drc-final.json`、`.rpt` |

初始DRC为78规则违规、130未连接；当前没有短路、庭院重叠或丝印违规。DRC使用原生severity-all、schematic-parity和临时官方库配置，无手工违规排除，检查器默认忽略的规则仍在报告列出。`manufacturing_release=false`。

## 遗留与下一步

1. **布局布线尚未完成**：59个未连接含接口预留/选件、USB，以及VBUS、VSYS、CHG_EN1、CHG_PGOOD_N等剩余连接。低速布线仍需继续完成，不能把这些缺口都归因于供应商资料。
2. U1的12个官方0.20mm热孔不满足当前0.30mm门槛；U1天线基材/壳体/RF与U3 EP热孔/钢网工艺待设计和审查；三件丝印移层引起的库差异待本地封装审查。未降低门槛或隐藏错误。
3. USB P/M网名需一致迁移为工具可识别的差分对，再按确认叠层设计阻抗、回流、耦合及长度差。没有USB、EMC或射频实测。
4. 相机完整料号、FPC触点面/线序/供电、光机/波导接口、BM83 EVB和UART电平/断电隔离、具体数字麦、电池/NTC均待确认。对应DNP与十项门槛保持。未通过LED故障、反灌、时序验证，禁止解锁采集。
5. 电池/USB100/LDO欠压、无线峰值及热测试、通话、iPhone Swift编译/安装、真实BLE/Wi-Fi JPEG、光学AR、处方与佩戴测试均未完成。没有上传个人媒体或执行真实AI验收。

复现入口分别见H01状态、H02电气审查、H03当前说明与 [软件/固件复核](evidence/RESUME_SOFTWARE_FIRMWARE.md)。可编辑PCB为当前权威输入；不要运行基线生成器覆盖已布线板。未生成R3 Gerber/钻孔制造包。
