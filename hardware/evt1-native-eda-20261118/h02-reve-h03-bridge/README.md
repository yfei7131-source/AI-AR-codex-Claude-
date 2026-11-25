# 智元跃动 AI/AR V1.0 — H02 Rev E 电气闭环 + H03 原生桥板布局交付包

> **状态**：`VERIFIED_H02_REVE_H03_BRIDGE` · **制造准入**：**BLOCKED / NOT FOR FAB**  
> **工程基线**：PR #38（`hardware/evt1-h02-h03-rd-20261120` @ `ecf8fc7`）  
> **原生 EDA 工具**：嘉立创 EDA 专业版 **V4.1.97**（`easyeda-agent v1.17.0` 实机导入、保存重载、三板严格 ERC / Protel2 网表 / 桥板 `PCB2` 全铜层 dump 与严格 DRC 回读并导出 `.epro2`）

---

## 1. 本轮核心成果总览

| 交付维度 | PR #36 基线 | PR #38 基线 | **本轮 H02 Rev E + H03 实测** | 状态 |
| --- | :---: | :---: | :---: | :---: |
| **可编辑原生 `.epro2`** | `NATIVE` | `RD` | [ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2](native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2) | **LIVE EXPORTED & SHA256 VERIFIED** |
| **安全关键 ECO 闭环** | 0 项 | 4 项 | **新增 5 项 + 更名**：`ECO-03` (`TPS3895ADRYR`)、`ECO-07` (`TPS2553DRVR` + `61.9k`)、`ECO-08` (`FC1610AN` LFXO)、`ECO-09` (去重 `R10` + 3× `100k` 下拉)、`ECO-14` (6 脚 `TPD2E001DRYR` + GND)、`LED_2V8 → LED_3V3_PRIV` | **100% PERSISTED & PROTEL2 VERIFIED** |
| **三板受控网络组** | `201` | `201` | **`207`**（`112 / 58 / 37`，+6 合法安全网络，0 非预期 diff） | **PASS** |
| **三板严格 ERC 总计** | `268` | `246` | **`130`**（`56 / 34 / 40`，本轮净降 **`116`** 项，0 新增错误） | **PASS（较 PR #36 减半以上）** |
| **桥板 `PCB2` 真实摆放** | `10` 器件 / `92` 焊盘 | `10` 器件 / `92` 焊盘 | **`17` 器件 / `122` 焊盘**（严格保持 `22.0 × 4.2 mm`；`17/17` UniqueID 对齐） | **PASS** |
| **桥板 `PCB2` MK2 与间距 DRC** | `6` 项 Clearance 报错 | `6` 项 Clearance 报错 | **`0` 项 Clearance 报错**（MK2 扩至 Infineon Ø0.80 mm + L2/L5 防焊盘） | **PASS（100% 清零）** |
| **结构变更申请** | — | — | [MECR_01_BRIDGE_25x4_6MM.md](MECR_01_BRIDGE_25x4_6MM.md)（`22×4.2 → 25×4.6 mm`，+0.03 g） | **SUBMITTED FOR ID/ME** |

---

## 2. 交付文档与脚本索引

- **原生工程**：[native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2](native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2)
- **Rev E 网表与 ECO 差异总表**：[REV_E_NETLIST_AND_ECO_DIFF.md](REV_E_NETLIST_AND_ECO_DIFF.md)
- **ECO-02 3.3V 隐私供电域与最坏故障复核**：[ECO02_PRIVACY_RAIL_AUDIT.md](ECO02_PRIVACY_RAIL_AUDIT.md)
- **桥板结构变更申请书（22×4.2 → 25×4.6 mm）**：[MECR_01_BRIDGE_25x4_6MM.md](MECR_01_BRIDGE_25x4_6MM.md)
- **阻断与条件项清单**：[BLOCKED.md](BLOCKED.md)
- **机器核验报告与构建回执**：[verification-report.json](verification-report.json) · [candidate-build-report.json](candidate-build-report.json)
- **Rev E 工程 BOM**：`evidence/engineering-bom/`（`M-MAIN-L.reve.csv`, `M-OPT-BRIDGE.reve.csv`, `M-AUD-R.reve.csv`）
- **可复现脚本**：[prepare_reve_h03.py](prepare_reve_h03.py) · [capture_reve_h03.py](capture_reve_h03.py) · [verify_reve_h03.py](verify_reve_h03.py)

---

## 3. 一键复现校验命令

```powershell
python -B hardware/evt1-native-eda-20261118/h02-reve-h03-bridge/verify_reve_h03.py `
  --capture hardware/evt1-native-eda-20261118/h02-reve-h03-bridge/evidence `
  --archive hardware/evt1-native-eda-20261118/h02-reve-h03-bridge/native/ZY_AIAR_EVT1_H02_REVE_H03_BRIDGE_NOT_FOR_FAB.epro2 `
  --out hardware/evt1-native-eda-20261118/h02-reve-h03-bridge/verification-report.json
```
