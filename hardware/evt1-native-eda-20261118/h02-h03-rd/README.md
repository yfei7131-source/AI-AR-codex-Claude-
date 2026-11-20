# 智元跃动 AI/AR V1.0 — EVT-1 H02→H03 首席硬件研发接管交付包

> **状态**：`VERIFIED_RD_ROUND` · **制造准入**：**BLOCKED / NOT FOR FAB**  
> **工程基线**：PR #36（`hardware/evt1-h02-h03-native-20261120` @ `38135f38`）  
> **设计输入**：PR #37（16 项 ECO 与 22×4.2 mm 桥板 83 器件方案，已独立核查并纠偏 4 项关键电气/引脚缺陷）  
> **原生 EDA 工具**：嘉立创 EDA 专业版 **V4.1.97**（`easyeda-agent v1.17.0` 实机连接、在线修改、保存、关闭重载、全三板 ERC/Protel2/PCB2 DRC 回读与导出）

---

## 1. 核心交付成果速览

| 验证项 | PR #36 基线 | 本轮实测结果（EasyEDA Pro V4.1.97） | 结论 |
| --- | :---: | :---: | :---: |
| 原生 `.epro2` 工程 | `ZY_AIAR_EVT1_H02_H03_NATIVE_NOT_FOR_FAB.epro2` | [ZY_AIAR_EVT1_H02_H03_RD_NOT_FOR_FAB.epro2](native/ZY_AIAR_EVT1_H02_H03_RD_NOT_FOR_FAB.epro2) | **LIVE EXPORTED & ZIP/SHA256 VERIFIED** |
| **三板严格 ERC 总计** | `268`（`124 / 87 / 57`） | **`246`**（**`112 / 78 / 56`**，净消除 **`22`** 项 `MISSFOOTPRINT`，**0** 新增） | **PASS（100% 清空 PR #36 READY+PENDING）** |
| **受控网络组** | `201`（`110 / 56 / 35`） | **`201`**（`110 / 56 / 35`，0 差异） | **PASS** |
| **受控板内连接端子 / 总端子 / NC** | `971` / `1,075` / `92` | **`971` / `1,075` / `92`**（层次拓扑 100% 不变） | **PASS** |
| **真实原生原理图 ECO 实施** | 0 项 | **4 项**（`ECO-01`、`ECO-02` 全 PVT 修正、`ECO-10` 实时 `sch modify`、`ECO-13`） | **PERSISTED & READBACK VERIFIED** |
| **桥板 `PCB2` 实测严格 DRC** | `66` 项（10 器件 / 92 焊盘 / 2 锁定禁放区） | **`66`** 项（0 退化，完成 83 器件 Courtyard 91.6% vs 73.1% 与通道核验） | **VERIFIED_PRE_ROUTING** |
| **电气与安全回归测试** | — | ECO-02 PVT / ECO-01 / ECO-07(61.9k) / ECO-03 / Rev D1.1 AVDD / H02 单元测试 | **ALL PASS** |

---

## 2. 目录与关键交付文件

- **可编辑原生工程（NOT FOR FAB）**：[native/ZY_AIAR_EVT1_H02_H03_RD_NOT_FOR_FAB.epro2](native/ZY_AIAR_EVT1_H02_H03_RD_NOT_FOR_FAB.epro2)
- **ECO 独立审计与实施文档**：[ECO_AUDIT_AND_EXECUTION.md](ECO_AUDIT_AND_EXECUTION.md) · [ECO_AUDIT_MATRIX.csv](ECO_AUDIT_MATRIX.csv)
- **22×4.2 mm 光学桥板原生 PCB2 验证报告**：[BRIDGE_NATIVE_PCB_VERIFICATION.md](BRIDGE_NATIVE_PCB_VERIFICATION.md) · [bridge-native-pcb-verification.json](bridge-native-pcb-verification.json)
- **完整机器核验报告与构建回执**：[verification-report.json](verification-report.json) · [candidate-build-report.json](candidate-build-report.json)
- **阻断与条件项清单**：[BLOCKED.md](BLOCKED.md)
- **确定性脚本（100% 可复现）**：
  - [prepare_rd_candidate.py](prepare_rd_candidate.py) — 从 PR #36 基线确定性构建 ECO + 22 封装绑定候选工程
  - [capture_rd_round.py](capture_rd_round.py) — EasyEDA Pro V4.1.97 在线 `sch modify`、保存重载、三板 ERC/Protel2、PCB2 dump/DRC 与导出驱动
  - [verify_rd_round.py](verify_rd_round.py) — 端到端归档/网表/ERC 差值/实读回执/电气 PVT 安全校验
  - [verify_bridge_native_pcb.py](verify_bridge_native_pcb.py) — 原生 `PCB2` 几何、禁放区、DRC 与 PR #37 83 器件定量核验
- **原始实时采集证据**：`evidence/`（含 `erc/` 三板严格 ERC 原件、`board-netlists/` 三板 Protel2 原件、`bridge/` PCB2 完整铜层 dump 与严格 DRC 原件、`operations/` 在线 `sch modify` 回执、`readback/` 修改页引脚回读、`tests/` 自动化测试日志）

---

## 3. 一键复现验证命令

```powershell
# 1. 验证实时导出 .epro2、三板 Protel2 网表 (201/971/1075/92)、严格 ERC (268->246) 与电气 PVT 安全测试
python -B hardware/evt1-native-eda-20261118/h02-h03-rd/verify_rd_round.py `
  --capture hardware/evt1-native-eda-20261118/h02-h03-rd/evidence `
  --archive hardware/evt1-native-eda-20261118/h02-h03-rd/native/ZY_AIAR_EVT1_H02_H03_RD_NOT_FOR_FAB.epro2 `
  --build-report hardware/evt1-native-eda-20261118/h02-h03-rd/candidate-build-report.json `
  --out hardware/evt1-native-eda-20261118/h02-h03-rd/verification-report.json

# 2. 复现 22.0 x 4.2 mm 桥板原生 PCB2 封装、禁放区、DRC 与 83 器件布线空间核验
python -B hardware/evt1-native-eda-20261118/h02-h03-rd/verify_bridge_native_pcb.py `
  --dump hardware/evt1-native-eda-20261118/h02-h03-rd/evidence/bridge/bridge-rd-persisted.dump.json `
  --drc hardware/evt1-native-eda-20261118/h02-h03-rd/evidence/bridge/pcb-drc-after.json `
  --keepouts hardware/evt1-native-eda-20261118/h02-h03-rd/evidence/bridge/keepouts.json `
  --out-json hardware/evt1-native-eda-20261118/h02-h03-rd/bridge-native-pcb-verification.json `
  --out-md hardware/evt1-native-eda-20261118/h02-h03-rd/BRIDGE_NATIVE_PCB_VERIFICATION.md
```
