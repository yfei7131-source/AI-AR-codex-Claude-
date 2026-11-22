# PR #47 Gemini 原生工程同步前静态核验（NOT FOR FAB / BLOCKED）

## 1. 同步范围与基线

- GitHub 基线：PR #47，研发分支 `hardware/codex-evt1-h03-pr46-takeover-20261121`，最新提交 `2c9c8dc6f4e20ace07c909a10f31fd1b3d3332e5`。
- 独立同步分支：`hardware/evt1-h03-gemini-cbb-sync-20261122`，创建时起点与上述提交一致。
- 交付包：`ZYD_Gemini_PR47_GitHub_ready.zip`，1,383,435 bytes，SHA-256 `52165fe444e73bf08683e3b5f2efbc54fac69a9d657870f4e5aeabae727bd10d`。
- 本轮只做上传、同步、静态核验与 GitHub 交付；不重新设计 PCB，不修改原生 `.epro2` 的任何字节，不降低制造规则，不合并 Draft PR。

## 2. 原生 `.epro2` 完整性与结构核验

文件：`native/ZY_AIAR_EVT1_H03_GEMINI_CBB_FIXED_NOT_FOR_FAB.epro2`

- 大小：1,394,148 bytes。
- SHA-256：`2e53a3e65a1c3ca577c11a36426be948e6381be62cc9595900152064f41ac0de`。
- 文件头为 ZIP `PK`，外层归档 CRC 检查无错误；`SHA256SUMS.txt` 中记录的值与本地实算完全一致。
- `project2.json` 标题为 `EVT1-H03-CODEX-PR46-20261121`，记录编辑器版本 `4.1.105`。
- 内部 `EVT1-H03-CODEX-PR46-20261121.epru` 为可解析的原生文档记录，不是空文件或文本冒充；静态解析到 3 个 `BOARD`、3 个 `SCH`、21 个 `SCH_PAGE` 和 3 个 `PCB` 文档。

| PCB | 文档 UUID | COMPONENT | LINE | VIA |
|---|---|---:|---:|---:|
| PCB1 | `8fbc3cae65886fe5` | 118 | 808 | 97 |
| PCB2 | `9ce45f14cb79dc9d` | 86 | 397 | 47 |
| PCB3 | `1db01a36f669a47a` | 53 | 384 | 52 |
| 合计 | — | 257 | 1589 | 196 |

以上为本机对原生记录的独立静态计数，只证明文件结构与对象数量，**不等同于嘉立创 EDA 独立重导入成功，也不等同于 DRC/ERC 实测通过**。

## 3. Gemini 本轮成果与数据来源

以下数值来自交付包中的 `GEMINI_ORIGINAL_README.md` 与 `BLOCKED.md`，本轮没有独立重跑嘉立创 EDA 的 DRC/ERC，也没有重新布线：

- Gemini 报告清理三板顶层汇总页的 18 个孤立 CBB 实例，保留同级真实电路图页及工程库副本。
- Gemini 报告三板 Netlist Error 合计由 **3 降为 1**；PCB1 仍保留 1 项，PCB2、PCB3 报告为 0。
- Gemini 报告三板未连通飞线合计 **729**：PCB1 358、PCB2 237、PCB3 134；间距错误报告为 0。
- Gemini 报告总 DRC 错误由 732 降为 730；上述数值均未由本轮独立复测。
- 257 个器件为本轮已独立静态核对的对象数；Gemini 报告整改前后均为 257，未据此宣称电气网表零差异。

## 4. 仍保持的制造与工程阻断

- PCB1 的 `J2/J3` 官方封装、配对 FPC/磁吸充电接口资料与剩余 1 项 Netlist Error 未关闭。
- 三板 729 处未连通飞线及高密布线通道未关闭。
- PCB2 八颗去耦电容联合重布局未关闭，功能性 RC 保留要求不变。
- 当前默认六层叠层 `JLC06161H-3313`、总厚 1.7873 mm，不是目标 0.80 mm 2+N+2 HDI；U11 0.35 mm WLCSP 内圈逃线、板厂 EQ 与局部规则签核未关闭。
- 光机/相机安全联锁、配对 FPC、结构光学干涉、整机 40 g 与实物验证未关闭。

因此本交付始终保持 **NOT FOR FAB / BLOCKED**。

## 5. 交付包原文件的保留说明

- 原 `README.md` 中存在 `NOT FO FAB`、`ZI`、`CB`、`DC/EC` 等字符缺失，并仍写着“GitHub 上传尚待执行”；`GEMINI_ORIGINAL_README.md` 和 `BLOCKED.md` 也保留 Gemini 当时的“原生交付未完成”记录。
- 为保持交付包证据原貌，本轮**不改动这些原报告**。本文件与实际 GitHub PR 只补充本次同步和静态核验事实，不把原报告中的预上传状态误写成当前仍未上传，也不解除任何工程阻断。
- 交付包只含 5 个原文件；未发现缓存目录、密钥文件或无关产物。对文本报告的常见密钥/令牌关键字扫描为 0 项。新增文件仅为本核验记录。

## 6. 上传文件与本地 SHA-256

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `BLOCKED.md` | 4612 | `965731365b28caeabe7d4cdd05a16fce196acc72bde7c09ca1736b4494e392ad` |
| `GEMINI_ORIGINAL_README.md` | 12356 | `a17dd769e3aa5b15bc7b6d528ec9c901220ca5d7730195a4d7d494e4e22f23ce` |
| `README.md` | 2415 | `2185cf12dd5da15f1cc419953b1715488ea7f37aca7c49f0bcee91528a4551d4` |
| `SHA256SUMS.txt` | 125 | `6d0e4905c9c7fe52a596421b2aa3beb71d03735659c230cd467f6258b1fb4255` |
| `native/ZY_AIAR_EVT1_H03_GEMINI_CBB_FIXED_NOT_FOR_FAB.epro2` | 1394148 | `2e53a3e65a1c3ca577c11a36426be948e6381be62cc9595900152064f41ac0de` |

远端文件存在性、回读 SHA-256 与 GitHub Actions 结果以实际 Draft PR 和提交后的检查记录为准，未预先宣称通过。
