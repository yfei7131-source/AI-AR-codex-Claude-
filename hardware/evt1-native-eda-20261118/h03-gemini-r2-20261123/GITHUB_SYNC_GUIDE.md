# GitHub 交接说明（NOT FOR FAB）

- 现有上游研发分支：`hardware/evt1-h03-gemini-cbb-sync-20261122`（PR #48，Draft，含已合并 PR #49）。
- 建议新分支：`hardware/evt1-h03-gemini-r2-20261123`，避免覆盖已归档工程。
- 将此 ZIP **解压后**按内置目录结构提交，共 5 个文件（含原生 `.epro2`）。
- 新建以 `hardware/evt1-h03-gemini-cbb-sync-20261122` 为 Base 的 **Draft PR**。保留 NOT FOR FAB，不合并至主干或投板。
- 新增三个顶层 2 mil GND 线低于嘉立创当前公开 HDI 最小线宽；原生 DRC 报告由 Gemini 提供，非独立复测。不得将此 ZIP 标记为 DFM PASS。
- 后续研发以经 EDA/板厂双重验收的版本为准，而非仅凭 PR 创建即放行。
