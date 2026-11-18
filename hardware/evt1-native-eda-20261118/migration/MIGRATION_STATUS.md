# EVT-1 KiCad → 嘉立创EDA 工程迁移专项：BLOCKED（未产生任何转换工程）

- 日期：2026-11-19（本机，UTC+8）。原始调用日志内的时间戳为 UTC。
- 源基线：PR #29，分支 `hardware/evt1-native-eda-20261118`，提交 `cec8deab978c0a6e04bb2293291dd4b5f13ac43a`。
- 结论：**0 / 3 工程转换成功，没有生成 `.epro` / `.epro2` / `.eprj*` 文件，三套工程全部保持 BLOCKED。**
- 本轮只涉及格式迁移与网络一致性核对，未修改任何电路、BOM、NETLIST、RTL、CAD 源文件，未改动 PR #29 / #30 / main，未修改 Rev D1.1 或 Gemini R1.2。

## 1. 已完成的源端提取

从 PR #29 提取 `kicad/` 下三套原理图工程与 `footprints/EVT1_Reviewed.pretty/` 自定义封装，目录结构保持不变，并按工程分别打包 ZIP（用于导入尝试）。

| 工程 | 原理图页数 | ZIP 字节 | 源端 CAD 端子数（按 `kicad/CAD_TERMINALS.csv` 的 Board 列统计） |
| --- | --- | --- | --- |
| evt1-audio-right | 6（含根图，下同） | 49056 | 236（M-AUD-R） |
| evt1-main-left | 8 | 102112 | 524（M-MAIN-L） |
| evt1-optical-bridge | 7 | 65817 | 315（M-OPT-BRIDGE） |

合计 1075 个 CAD 端子，与 PR #29 证据中的 236 / 524 / 315 一致。ZIP 条目清单与 SHA-256 见 `source_zip_manifest.json`。
三套源 ZIP 保留在本机（路径见清单）；GitHub 文本上传接口不能写二进制，本分支未上传 ZIP 本体，以哈希作为同一性依据，需要时可按清单路径取回。

## 2. 转换尝试的真实环境与原始报错

- 客户端：嘉立创EDA(专业版) **4.1.97**，安装于 `D:\lceda-pro\`，桥接版本 `4.1.97.04b092ac`，前端 `pro-api 0.3.69`。
- `lceda-pro doctor` 返回 `connected:true, versionMatch:true`，即本机命令行通道正常。
- **GUI 被另一会话占用**：启动桌面客户端时弹出「窗口无法显示 / Window Not Visible」，原文为“检测到后台服务运行在不可见的桌面上，新窗口无法在当前桌面显示”，应用建议先 `lceda-pro stop` 再从桌面图标重启。该后台服务持有一个他人工程窗口 `ZY_AIAR_EVT1_KIMI_ARCHIVE_CHECK_20261119`，**未将其关闭，未执行 `stop`**，以免丢失他人未保存内容。因此官方「文件迁移助手」的图形操作本轮无法执行。
- 改用客户端自带自动化 CLI 与官方 API：`open` 建立会话（隐藏会话 `19ea3907`、完整编辑器会话 `78506d71`），`invoke` 调用 `eda.sys_FileManager.importProjectByProjectFile(file, 'KiCad', ...)`。

## 3. 调用序列与返回（原始 JSON 见 `evidence/import_attempts.json`）

| 次序 | 会话 / 权限 | saveTo | 返回 | 结果 |
| --- | --- | --- | --- | --- |
| 01 | 隐藏会话 / 独立脚本 | Offline Client Local Path（EPRJ3） | `undefined`，两次执行为 2519 ms 与 746 ms（存档为后者） | 目标目录无任何文件 |
| 02 | 隐藏会话 / 独立脚本 | 省略 | `undefined`，715 ms | `getAllProjectsUuid() = []` |
| 03 | 隐藏会话 / 独立脚本 | 省略 | 垃圾 ZIP 7 ms、KiCad ZIP 829 ms，均 `undefined` | 对照组同样无输出 |
| 04 | 完整编辑器 / 独立脚本 | 省略 | `undefined`，1077 ms | `projectsAfter = []` |
| 05 | 完整编辑器 / 扩展权限（easyeda-agent-connector） | Offline Client Local Path | `undefined`，1086 ms | 无落盘文件 |
| 06 | 完整编辑器 / 独立脚本 | New Project，本地团队 `Documents\LCEDA-Pro\projects` | `undefined`，1149 ms | 工程列表仍为空 |

其它观测：`getReadyState() = "notLoaded"`；工作区只有 `Personal`；本机为离线客户端，团队即本地文件夹 `Documents\LCEDA-Pro\projects` 与 `example-projects`；调用期间 console 无任何错误输出。

**判读**：导入接口在本机对所有输入（包括故意构造的非 ZIP 垃圾输入）都返回 `undefined` 且不产生工程，属于“导入通道未产生任何输出”。这些日志**不能**证明 KiCad 文件本身不兼容，也**不能**被解释为转换成功。按任务要求，已停止对 evt1-main-left、evt1-optical-bridge 的批量转换，未做空原理图或空工程冒充产物。

## 4. 具体不兼容对象与风险（在真正转换前必须先解决）

1. **KiCad 版本代差**：源工程 `.kicad_sch` 头为 `(version 20231120)`，由 KiCad 10 工具链生成（PR #29 证据记录 `kicad: 10.0.7`）；官方《导入 KiCad》页写明专业版支持 **KiCad 5.1 / 5.9** 格式，低版本需先在 5.1 重新保存。当前版本明显高于官方承诺范围，属于首要不兼容风险。**禁止通过修改版本号冒充兼容**，本包未做任何此类修改。
2. **标准封装库在本机不存在**：三套工程 `fp-lib-table` 引用 `${KICAD10_FOOTPRINT_DIR}` 下的 `Capacitor_SMD`、`Inductor_SMD`、`Package_SON`、`Package_TO_SOT_SMD`、`Resistor_SMD`。本机未安装 KiCad（`kicad` / `kicad-cli` 均不在 PATH），这些库无法解析，转换后封装必然缺失或需要逐对象重指定。
3. **自定义符号库**：每套工程带 `evt1.kicad_sym`（86518 / 189480 / 127862 字节）与 `sym-lib-table` 的 `${KIPRJMOD}` 引用；官方建议使用 KiCad 自带打包功能把库一并打包，本包是手工打包，已含符号库与库表，但未经验证官方解析器是否接受。
4. **分层原理图结构**：根图通过 `sheet` 分别引用 5、7、6 张子图，页名含空格与连字符，需核对导入后层级是否保留、同名标签是否被错误跨板合并。三套板各自独立 PCB，同名网络标签不允许跨板连通。
5. **自定义封装仅 1 个**：`footprints/EVT1_Reviewed.pretty/` 只有 `Abracon_ASADV_2016-4Pin_2.0x1.6mm.kicad_mod`，与 `FOOTPRINT_MAP.csv` 的逐对象映射需在转换后逐条对账。
6. **本轮没有 `.kicad_pcb`**：源目录只有原理图工程，PCB 布局布线不在本次迁移范围，任何“已可投板”结论都不成立。
7. **官方已知差异**：官方文档提示 KiCad 的 `PWR_FLAG` 会被转成符号库而非网络标签，PCB 导入会自动重建铺铜且结果有差异，这些都需要列入后续差异清单。

## 5. 验证状态清单（全部未通过，保持 BLOCKED）

| 核对项 | 状态 | 说明 |
| --- | --- | --- |
| 嘉立创侧分层原理图 | BLOCKED | 没有生成工程，无法读取 |
| 元器件 / 符号 / 引脚 | BLOCKED | 无转换产物可比对 |
| 236 / 524 / 315 CAD 端子一致性 | BLOCKED | 仅有源端基线，无目标端数据 |
| 电气网络一致性 | BLOCKED | 未获得嘉立创侧网表 |
| 封装与 FOOTPRINT_MAP 对账 | BLOCKED | 标准库缺失，未进入转换 |
| 嘉立创侧 ERC | BLOCKED | 未运行 |
| KiCad 侧 ERC / 网表复跑 | UNVERIFIED | 本机无 KiCad，沿用 PR #29 记录（10.0.7，ERC 0/0/0，端子对账 PASS），不是本机复跑结果 |

## 6. 建议的下一步（需要决策者选择）

1. 由工程负责人确认可以关闭现有嘉立创后台服务后，执行 `lceda-pro stop`，从桌面图标重启客户端，用官方「文件迁移助手」GUI 对 `evt1-audio-right.zip` 做一次转换并保存原始错误弹窗；成功后再逐个处理另外两套。
2. 或在装有 KiCad 10 的机器上，用 KiCad 自带打包功能重新导出三套工程（把库一起打包），再交给官方迁移助手；若官方仍只接受 5.1/5.9，需要先在受控副本上评估降级保存的电气损失，并单独记录，不得直接改写源工程。
3. 任何转换成功后，必须输出：目标端器件与引脚清单、网络清单、封装映射差异、嘉立创原生 ERC 结果，再与 `kicad/CAD_TERMINALS.csv` 的 1075 端子逐条对账，通过前一律 BLOCKED。

## 7. 本包文件

- `MIGRATION_STATUS.md`：本报告。
- `source_zip_manifest.json`：三套源 ZIP 的字节数、SHA-256、条目清单与本地路径，及端子基线。
- `evidence/import_attempts.json`：六次导入调用与状态探针的原始返回。
- `evidence/lceda_environment.json`：客户端版本、doctor 结果、GUI 阻断原文、官方文档口径与本机会话信息。

NOT FOR FAB。本包只证明“本轮格式迁移未完成及其原因”，不构成任何 R1.3 或 EVT-1 的研发交付，也不作为硬件进度推进的依据。
