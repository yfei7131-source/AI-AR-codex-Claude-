# H01 R3 当前裁决与冻结边界 — 2026-11-12

本页接续 R2 历史记录。[架构](H01_architecture.md)、[ICR-01–12](ICR_to_Codex.md)、[22 项追踪](F01_F22_trace.csv)、[硬件/软件矩阵](HW_SW_COMPAT_MATRIX.csv)是 R3 的当前设计输入。H01 的输出是可审查的研发分配；全部需求的产品验收仍未完成。

| 项目 | 已有的具体成果 | 当前结论 |
|---|---|---|
| F01–F22 | ID、名称与优先级逐行对应仓库冻结需求；16 P0、5 P1、1 R；F21 保留预研 | 需求分配完整，真实验收未完成 |
| GPIO | R3 独立 N16R8 profile；22 个唯一 GPIO 与硬件 pinmap 对应；GPIO35–37 保留 PSRAM；46 不作音频使能 | 数字分配匹配，电平/启动/实物连线另验 |
| 相机 | `camera_power.c` 与授权内采集链；J3/R16/R17/R18 初装 DNP；已去除 JP2 强制上电 | 四种 profile 均锁定；不得以改布尔量或跳线替代 T11/T12 |
| 音频 | BM83 EVB 独立 HFP/A2DP；J7 仅地与可选双向 UART；R33/R34 DNP | 接口方案已给出；UART 驱动/电话控制 opcode/唤醒未实现，HFP 未实测 |
| 电源 | BQ24072 #15 TD 对地；CE 默认高，R5/R36 DNP；USB100；记录电流设定和 LDO 压差边界 | 禁充台架方案；电池/NTC/温升/峰值及低电量范围仍阻断 |
| AR | 独立 Halo 台架工具与 mono1_msb；S3 sink 未绑定；J4 DNP | 软件像素或 emulator 不证明光学显示；M3 光机接口未冻结 |
| 机械与光学 | PRD 内部目标为裸镜≤50 g、55 g 警戒，验配整镜另称；25°C指定工况皮肤接触面≤41°C；4h 不适≤2/10 | 目标继续适用；H04 原始草稿中的“no target approved”不是现行目标定义；无实测及适用标准结论 |

追踪表的 `allocation` / `interface` 描述设计目标与责任，不能读成已实现：F12 的“手机持久离线队列”尚未完成；F16 尚无流式字幕；F14 配置持久化未完成；F05 连续对话与真实语音未验。`docs/TRACEABILITY.md` 的代码、自动测试、真实环境三层状态继续适用。现有 API 的本地任务确认不等于外部动作已执行；浏览器 TTS 不等于 F03 通话。

所有未确认器件和接口在 [RELEASE_GATES.csv](RELEASE_GATES.csv) 保留阻断记录。H01 不批准生产 BOM、最终机械接口或投板。J4 的通用排针 footprint 只保留研发占位，不为任何裸屏协议背书。R3 PCB 实际放置/布线及 DRC 结果由 H02/H03 和原生报告分别记录；H01 审计不会把这些结果代为通过。

从仓库根复现无写 ECAD 的源合同检查：

```powershell
python hardware/evt0-r3/H01/verify_h01.py --output hardware/evt0-r3/evidence/h01-contract.json
```

该命令比较权威 22 项需求、源路径、22 个 GPIO、四种锁定 profile、关键 DNP 装配及 ICR 完整性，保留输入 SHA-256。exit 0 仅表示这些源合同一致；输出始终包含 `manufacturing_release=false`、`hardware_verified=false`。KiCad ERC、PCB DRC、Swift/iPhone、供电、相机隐私与光学测试有各自的真实证据和门槛。
