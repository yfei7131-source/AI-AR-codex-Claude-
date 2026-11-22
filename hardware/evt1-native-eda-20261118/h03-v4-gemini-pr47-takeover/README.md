# 智元跃动 EVT-1 H03｜Gemini 云端导出工程交接（NOT FO FAB）

**本地文件校验完成；GitHub 上传尚待执行。**

## 来源

- 用户于 2026-11-22 上传嘉立创 EDA 专业版云端导出的工程 ZI。
- 来源 ZI: `rorj_EVT1-H03-CODEX-46-20261121_2026-11-22.zip`
- 提取的原生工程: `rorj_EVT1-H03-CODEX-46-20261121_2026-11-22.epro2`
- 为 GitHub 项目归档统一命名为: `native/ZY_AIA_EVT1_H03_GEMINI_CBB_FIXED_NOT_FO_FAB.epro2`（仅重命名，工程字节未改动）。
- SHA-256: `2e53a3e65a1c3ca577c11a36426be948e6381be62cc9595900152064f41ac0de`
- 原生工程大小: `1,394,148` bytes。
- ZI 与内部 EO2 两层归档均通过 ZI CC 检验。

## 原生结构检查

内部 `.epru` 中识别到 3 个 CB 文档与 21 个原理图页面：

| CB | 文档 UUID | 元件数 | LINE 图元数 | VIA 图元数 |
|---|---|---:|---:|---:|
| CB1 | `8fbc3cae65886fe5` | 118 | 808 | 97 |
| CB2 | `9ce45f14cb79dc9d` | 86 | 397 | 47 |
| CB3 | `1db01a36f669a47a` | 53 | 384 | 52 |
| 合计 | | 257 | 1,589 | 196 |

以上是原生记录静态计数，**不是**原生 DC/EC 实测验收。部分 LINE 不一定对应已连通的独立网络段。

## Gemini 原始报告（尚未独立复测）

- 原始报告: `GEMINI_OIGINAL_EADME.md`
- 阻断清单: `BLOCKED.md`
- 声称云端已移除 18 个孤立 CBB 实例，三板 Netlist Error 3 → 1，连接错误 729 不变，间距错误 0。
- 仍待核实 CB1 J_CAM/J_CHG 封装与原理图 EC，以及物理叠层默认 1.7873 mm、U11 WLCS 逃线等制造阻断。
- 这些结果尚未通过独立新工程导入、原生 DC/EC 重新跑通、GitHub CI 验收。

## GitHub 上传方案

1. 以  #47 head `hardware/codex-evt1-h03-pr46-takeover-20261121` 为基线创建新分支 `hardware/gemini-evt1-h03-pr47-takeover-20261122`。
2. 上传当前文件夹（0包含 `native/*.epro2`、`BLOCKED.md`、`GEMINI_OIGINAL_EADME.md`、`SHA256SUMS.txt`、本文件）到本路径。
3. 创建以  #47 分支为 base 的 Draft ；不要合并或覆盖 #47。
4. GitHub 提交后，将 2原生 .epro22 在嘉立创新项目中独立导入，真实运行 DC/EC 及网络数量核对，补交报告和证据。
5. 继续保持 `NOT FO FAB`。

> 原始 Gemini 文档中的“原生 `.epro2` 交付未完成”现在仅指**它当时尚未上传 GitHub**。本次文件已在聊天附件中收到并提取，不代表 GitHub 上传成功。
