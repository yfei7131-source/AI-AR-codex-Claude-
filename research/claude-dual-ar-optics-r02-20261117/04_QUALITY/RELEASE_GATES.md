# 工程发布与验收门禁

## 五类“已完成”绝不混淆
1. `DOCUMENTED`：文档/任务卡完成；不能表示设计已实施。
2. `IMPLEMENTED`：真实可编辑工程源码发生可审计 diff，形成 commit/完整ZIP。
3. `STATIC_VERIFIED`：脚本、ERC/DRC、netlist parity、HDL CI 等在**该**提交上实际运行，原始日志保留。
4. `BENCH_VERIFIED`：电源/接口/光学/热/质量/寿命在真实器件或EVK上测得。
5. `RELEASE_APPROVED`：评审、BOM/制造/法规门禁和版本标识都闭环。

## 每一个工作项的最小交付字段
`Task ID | owner | source baseline commit/hash | modified paths | design evidence level | test command/tool version | exit status | measurement attachments | residual risks | approval | next action`。

## 交付包必须包含
- 原生 SCH/PCB 或 EDA 源，不得以只有 PDF/截图或网表冒充可编辑文件。
- 每个ECR的 diff、关联文件、批准状态和后退方案。
- ERC/DRC/HDL等所有运行日志，包括 WARN/BLOCKED；不可因没有工具而写 PASS。
- 称重清单及能效/温升实测原始数据（若尚未实施，明确 `NOT_MEASURED`）。
- 供应商官方资料版本号与页码；NDA原件不进入公开仓库。
- `SHA256SUMS.txt`、`MANIFEST.json`、`OPEN_ISSUES.md`。

## 当前本交接包真实验证记录
- 已完成：对上传 ZIP 结构识别、可用会话提取、人工范围审查、CSV/JSON语法检查和 ZIP/SHA256 文件完整性检查。
- 未完成且不得暗示完成：GitHub最新HEAD读取、KiCad ERC/DRC、可编辑电气修改、FPGA编译仿真、任何JBD EVK点亮、FPC/热/称重实测。
