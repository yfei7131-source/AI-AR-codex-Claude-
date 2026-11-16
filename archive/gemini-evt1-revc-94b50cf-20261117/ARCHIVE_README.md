# Gemini EVT-1 Rev C `94b50cf` — 历史工程归档（NOT FOR FAB）

**该包为 Gemini 导出中的旧 Rev C 分支增量，非当前 Rev D1 新基线。**

- 用户提交的 Gemini 导出 ZIP SHA256: `a2a5c00095649fb4b9476edde8893ba23ed0ad6527fe6fc3a4090f9a9daf7077`
- 原始工程文件：`source/ZY_AIAR_V1_0_KIMI_HANDOFF_PACKAGE.zip`（包含原有 `handoff_evt1_rev_c.bundle`、patch、RTL/PCF/TB/Makefile、BOM/PINMAP/ICD、验证脚本和日志）。
- 内层 Git bundle：`94b50cf66c149f0b5a613edd8e15f18cd2a0eb15`，直接父提交 `bb876238fd25ac6be7c8f706b3d273b05d85a847`。已在本地 `git bundle verify` 和 `git fetch` 验证通过。
- `delta/94b50cf_vs_bb87623.patch`：上面两版本的真正差异，用于审查，不得直接 cherry-pick 到 Rev D1。
- `latest_export_artifacts/`：导出 ZIP 附带的 4 张 CSV 和 EDA 日志，忠实保留原始字节。导出中没有最新原生 CAD/PCB。
- 不附公开 Gemini 对话 Markdown，以避免将整段用户对话发布到公开仓库。

## 新增变化（与 bb87623 比较）

- 光机 AVDD 改为基于 CDONE/VSYNC 的峰值保持、放电和双电源钳位五状态联锁；相关 RC/二极管网络及测试更新
- FPGA CRESET_B 默认 10k 下拉
- 左镜腿尾端补充 USB pogo / 电池 / 扬声器 Pads 1..9
- 更新 BOM、PINMAP、ICD、预算、验证脚本/日志，共更动 12 个源树文件
- **未修改 FPGA RTL/PCF/Testbench**。上传的验证日志不是现行 Rev D1 原生电路/实物验证。

## 与现行 Rev D1 的风险与冲突

1. Gemini 94b 方案将 D3 视作正脉冲 VSYNC 进行肖特基充电；Claude Rev D/ Codex Rev D1 的 D3 信号设计为 `cdone_vsync_n`、用户模式短暂低脉冲，逻辑极性不同。必须先在现有 RTL/PCF/FPGA 启动序列中检查信号和配置模式，不得直接接入。
2. Gemini 源依赖 24P / 16P 跨板 BTB；Rev D1 继承 Rev D 30Pin/5A 电源触点改型，旧连接图不再是当前权威。
3. 旧 BOM/PINMAP 和电源树含早期器件选型；Rev D1 有 103 个 BOM owners / 957 物理终端、BQ25180 等校核，不得直接回退。
4. Gemini 声称的 5 态仿真/故障注入 **未在 Rev D1 现行硬件上验证**。既有 FPGA GitHub CI 成功不等于这一版峰值保持电路实测通过。
5. JBD NDA 引脚/FPC、QSPI/初始化、AVDD、STEP 与实际原理图/PCB/DFM/硬件测量仍阻断，保持 NOT FOR FAB。

## GitHub 归档建议

单独创建 `archive/gemini-evt1-revc-94b50cf-20261117`，以 PR #19 的 Rev C 远端 `c5c14da3ee9a11503ea99accd136f17473ba792b` 为起点，新增目录 `archive/gemini-evt1-revc-94b50cf-20261117/`，将**本包解压后的全部文件按目录原样上传**，Draft PR 的目标分支为 `handoff/evt1-rev-c-source-20261116`，标记 `ARCHIVE ONLY / UNVERIFIED / NOT FOR FAB`。

原 `94b50cf` 是 bundle 内的独立历史，不能宣称已经是 GitHub PR #19 的 HEAD；如要完整保留该祖先分支，可另按 bundle 原提交存档，但不能改写 PR #19 或 Rev D1，也不要强推或直接合并设计。保留文件哈希和远端比对证据。
