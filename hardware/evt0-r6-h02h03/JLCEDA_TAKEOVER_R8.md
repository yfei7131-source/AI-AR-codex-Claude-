# JLCEDA_TAKEOVER_R8 — 嘉立创EDA接管可行性验证（2026-11-14，R8）

**分支** `hardware/evt0-r8-jlceda-20261114` · **基线** R7 `e6a8363` · **NOT FOR FAB**

## 结论（先说结果）
**KiCad 文件导入路径：阻断，不可行。** R7 工程为 KiCad 10.0 格式（文件头 `version 20260206`，generator 10.0），嘉立创EDA专业版 4.1.97 的 KiCad 导入器拒绝接受。无损接管**不能依赖文件导入**；可行路径为 **typed 重建 + 连接性 parity 证明**（见下文）。

## 实测记录（全部真实执行，证据 `evidence/r8_jlceda_probe/`）
| 探针 | 输入 | 结果 |
|---|---|---|
| ① `extractProjectInfo(.kicad_pro)` | 13,083 B pro 文件（base64 注入 File） | 抛错 `[object Object]`，解析失败 |
| ② `importProjectByProjectFile(.kicad_pro, "KiCad")` | 同上 | API 返回 ok:true，但 EDA 弹出**「错误：选择导入的文件格式不正确或不匹配当前类型，请重新选择导入」**（截图 `import_format_error_dialog.png`），本地工程库无新工程 |
| ③ `importProjectByProjectFile(.kicad_sch, "KiCad")` | 230,990 B sch（经 `sys_FileSystem.readFileFromFileSystem` 读入，大小核对一致） | 返回 null，本地工程库 `Documents/LCEDA-Pro/projects/` 无新增，未生成任何工程 |

- CLI 封装 `easyeda project import` 仅支持 `.epro2/.epro/.zip`，不含 KiCad。
- `sys_FormatConversion` 仅有 Altium/DISA 转换，无 KiCad。
- 环境：easyeda-agent v1.17.0（CLI/daemon/connector 同版，验收见 PR#10），嘉立创EDA专业版 4.1.97，半离线模式。
- 本机无 KiCad/kicad-cli，无法把工程降级转换为 KiCad 6/7 再试；即使转换，层叠/DRU/区域规则的导入损耗也无法验证，**不满足"无损"定义**。

## 可行接管路径：typed 重建 + parity 对账
以 `netlist.csv`（351f6f1b…）、`pinmap_hw.csv`、`bom_evt0_core.csv` 为源数据：
1. 嘉立创EDA 新建正式工程（独立容器，不写回 R7）。
2. 按 BOM 逐器件核对 LCSC 库身份（多变体拒绝默认取首项），`sch cbb-place`/typed 放置。
3. 按 netlist 逐网连接，原理图 `layout-lint → check → bridge-check → drc` 门禁。
4. **parity 对账**：嘉立创EDA 连接性 IR（`sch connectivity`）与 R7 `netlist.csv` 逐脚比对，0 差异才算电气等价接管。
5. PCB 重新布局布线（不复用 KiCad 几何），原生 `pcb drc` 通过后才谈制造可行性。

## 49 项未连接的处置立场（维持红线）
- KiCad 侧：R7 已证明 U2.2 GND 与 PGOOD/TP10 几何死锁、叠层 C1/90Ω 未获板厂确认；本机无原生 KiCad DRC，**不做电源路径改动**。
- 嘉立创EDA 侧：重建后在原生 DRC 下布线，USB 差分仍需板厂叠层/阻抗确认后才落地。
- 双目 AR 显示与 40 g 整机目标保留；EVT-0 验证板不冒充最终镜腿 PCB；原生验证未通过不投板。

## 已落地：重建工程容器与器件选型核对（真实执行）
- 正式工程已创建并打开：**`ZY-AIAR-EVT0-R8-验证板`**（uuid `6757096b0d67c0879a663e8d58216b175a02a33d4d00c1c0bdeda07b8c434b64`，半离线本地库；schematic P1 `7a4e9091b268cd79`、PCB1 `6e4acfce1bdee052`）。**NOT FOR FAB；EVT-0 验证板，非最终镜腿 PCB。**
- BOM 关键器件 LCSC 库核对（`lib search` 实测，证据 `evidence/r8_jlceda_probe/lib_search.txt`）：

| BOM 位号 | MPN | LCSC | 状态 |
|---|---|---|---|
| U1 | ESP32-S3-WROOM-1-N16R8 | C2913202 | 精确匹配 |
| U3 | BQ24072RGTR | C140288 | 精确匹配 |
| U2 | USBLC6-2SC6 | C2687116 | 精确匹配（ST 原厂） |
| U4 | TLV75733PDBVR | C485517 | 精确匹配 |
| U5 | TLV75528PDBVR | C2868951 | 精确匹配 |
| U6 | TLV75512PDBVR | C2877864 | 精确匹配 |
| Q2 | BSS138 | C193019 | 精确匹配 |
| J1 | TYPE-C-31-M-12 | C165948 | 精确匹配 |
| SW1/SW2 | TL3342F160QG | C2886898 | 精确匹配 |
| J2 | SM03B-SRSS-TB | C160403 | 精确匹配 |

选型核对结论：重建路径器件可得性无阻断。多变体项（USBLC6 有兼容型 MSUSBLC6、BSS138 有 SOT-8015 变体）按红线只取 MPN 精确匹配项。

## 下一步（R8 后续）
- 新建嘉立创EDA正式工程，先完成 ESP32-S3 核心 + USB 充电/保护的器件选型核对与原理图重建。
- 板厂叠层确认后落地 USB 90Ω 差分。
