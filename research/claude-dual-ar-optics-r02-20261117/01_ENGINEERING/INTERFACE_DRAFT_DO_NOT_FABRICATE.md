# J_DISP/光机接口需求合同草案 — 严禁当作最终 PINMAP
**状态**：PROPOSED / `BLOCKED_BY_JBD_OFFICIAL_PINOUT`。当前无 JBD 官方接口/FPC 针序文件。

| 需求 | 原始依据 | 设计输出 | 冻结条件 |
|---|---|---|---|
| 确定具体光机 SKU（Mini II vs 裸面板 JBD013VGA） | 报告 H1/H2 | `JBD_SKU_REVISION.md` | JBD 书面确认 |
| 确定每只模组供电轨、VCOM 是否内部生成、上下电顺序 | 二手 Mini II/裸面板材料存在差异 | `POWER_SEQUENCE_TBD.xlsx/csv` + 仿真计划 | 官方 datasheet + EVK |
| 逐眼复位、片选、使能、状态/ID 回读 | 报告认为 10pin J_DISP 不足 | `J_DISP_REQUIREMENTS.csv`（只是逻辑信号，不写 pin number） | 原厂 FPC 针序 |
| SPI/QSPI IO 数、方向、电平、时钟与 dummy | 二手资料提出 QSPI≤42MHz写 / ≤32MHz读 | `DISP_BUS_TIMING_SPECS.md` | 原厂时序表 + 示波器/LA |
| 写缓存与 Sync 命令 | 0x62/0x97仅第三方材料；0x32来源冲突 | 固件 `config` 中设置 `opcode=TBD`，默认不向硬件发送 | 官方命令表 + EVK |
| 双目 640×480 / 灰阶 / 局部更新 | 4-bit、8-bit 来源不一致 | `FRAME_FORMAT_OPTIONS.md` 参数化计算 | 确认背板版本 |
| 连接器针数/封装 | “≥16pin”只是数量级建议 | 2~3 个带尺寸的连接器候选及余量、pin count | 厂商 FPC/连接器匹配 |
| FPGA 传输模式 | P1/P2/P3 | RTL接口测试计划/向后兼容回退策略 | 通过 G1–G6 后架构评审 |

## 禁止动作
1. 不得用裸面板 VDD12/VCOM 的二手电压直接配置 Mini II 模组电源；不向未知针脚上电。
2. 不把 `0x62`、`0x63`、`0x97`、`0xA3` 当成实际目标型号的已验证指令。
3. 不把 `≥16pin` 定为最终连接器及位置，不猜测引脚表。
4. 不在现有 Rev D1 正式网络表里未经 ECR批准更换光机接口或删除 FPGA。

## 原厂回复必须包含的最小资料包
`Official SKU + revision; connector/flex drawing; complete pin map; power rails/max current/sequencing; reset/enable and logic levels; SPI/QSPI command and timing; readback; frame memory and sync behavior; optical/mechanical STEP; APL-power/thermal curves; eye safety guidance; NDA/license terms`。
回复材料存证并记录具体版本日期/页码；不应把保密原件上传到开放仓库。
