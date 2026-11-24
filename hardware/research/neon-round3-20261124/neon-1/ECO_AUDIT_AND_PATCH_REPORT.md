# 智元跃动 EVT-1 H03 — ECO 审计实测与受控基线更新补丁报告（继承 #55 & #57/neon-1，NOT FOR FAB）

> **继承基线**：PR #55（`hardware/kimi-evt1-h03-r7-20261123`，Commit `ac38a71947f5d7bdd4e5d193584fbb7c6c05363c`）与 PR #57 / `neon-1`（`hardware/research/neon-round2-20261124`，Commit `b92d2df8d7171622e8494243ede5970d1182f4c9`）。  
> **红线遵守**：未上传 GitHub，未修改任何受控基线、未删网、未关闭规则，保持 `NOT FOR FAB`。

## 1. 现有 ECO 审计脚本实测结果（`neon-1/audit_h02_to_r7_eco_delta.py`）

针对 PR #55 核验提取的 `controlled-sch-audit.json`、`69-PCB1-independent-erc.stdout.json` 与 `63-PCB3-final-erc.stdout.json` 实际运行现有审计脚本（退出码 `0`）：

```json
{
  "schematicEcoAudit": {
    "status": "PASS_WITH_APPROVED_ECO_DELTA",
    "terminalCount": 1076,
    "controlledTerminalCount": 1075,
    "netTerminalDelta": 1,
    "explicitNCCount": 92,
    "controlledNCCount": 92,
    "archiveRawNCMarkers": 94,
    "rawVsExplicitNCGap": 2,
    "unexpectedFindings": []
  },
  "missfootprintAudit": {
    "status": "PASS_CLASSIFIED",
    "totalFound": 6,
    "boardInterfaceBlocked": [
      [
        "PCB1",
        "J2"
      ],
      [
        "PCB1",
        "J3"
      ]
    ],
    "externalAssembly": [
      [
        "PCB1",
        "BAT1"
      ],
      [
        "PCB1",
        "SPK1"
      ],
      [
        "PCB3",
        "BAT1"
      ],
      [
        "PCB3",
        "SPK1"
      ]
    ],
    "unexpected": [],
    "missing": []
  }
}
```

> *复现说明*：因本地沙箱无外网，本次输入由远程浏览器从 PR #55 实测提取的 JSON 字段重建；在本地仓库检出 `hardware/kimi-evt1-h03-r7-20261123` 后可直接执行：
> ```bash
> python3 hardware/research/neon-round2-20261124/neon-1/audit_h02_to_r7_eco_delta.py \
>   --audit-json hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/controlled-sch-audit.json \
>   --pcb1-erc hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/69-PCB1-independent-erc.stdout.json \
>   --pcb3-erc hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/63-PCB3-final-erc.stdout.json
> ```

## 2. 验证汇总（1075→1076 端子、NC 与 6 项 ERC fatal）

| 审计维度 | 实测结果 | 根因与处置分级 |
| :--- | :--- | :--- |
| **端子数 (`1075 → 1076`)** | `PASS_WITH_APPROVED_ECO_DELTA`（净差 `+1`） | ECO-09 删除重复上拉 `R10` (`R_ESP_BOOT`, `-2`) + ECO-14 `U12` 升级为 6 脚 TI `TPD2E001DRYR` (`+3`)，对称差集精确为 5 项，零未知漂移 |
| **NC 标记 (`92` vs `94`)** | `explicitNCCount = controlledNCCount = 92`；`rawVsExplicitNCGap = 2` | ECO-08 `U11.F11/F12` 移除 NC (`-2`) 与 ECO-14 `U12.4/6` 新增 NC (`+2`) 抵消；`archiveRawNCMarkers = 94` 多出 2 处位于 252 个已解析受控器件之外的原始 `SCH_PAGE` `NO_CONNECT="yes"` 属性 |
| **板载缺封装（2 项 fatal）** | **`PCB1: J2 (ie165)`、`PCB1: J3 (ie284)`** | `Convert to PCB=yes`，直接导致 PCB1 唯一 1 项 Netlist Error；**必须保持 `BLOCKED`**，严禁虚构封装或改 `Convert to PCB=no` |
| **板外装配（4 项 fatal）** | **`PCB1: SPK1 (ie447)`、`BAT1 (ie226)`；`PCB3: SPK1 (ie377)`、`BAT1 (ie65)`** | `Convert to PCB=no`（板外扬声器/电池线焊装配，不触发 PCB Netlist Error）；**严禁关闭规则**，待受控基线维护者评审决定是否采用线焊盘占位封装或受控白名单 |

## 3. 受控基线更新补丁说明（`controlled_baseline_eco_h02_to_r7.patch`）

补丁基于 `hardware/evt1-native-eda-20261118/kicad/CAD_TERMINALS.csv`（Commit `7572be31793d976aaabf0313bc13596d188e9580`，1,076 行）生成，**仅作候选补丁交付，未经基线维护者审批不得直接合入**：
1. **Hunk 1（第 231–237 行，ECO-14）**：`U12` 由旧 3 脚更新为 6 脚 `TPD2E001DRYR`（`DRY0006A`，保持 `BLOCKED`）：Pin 1 `USB_DP`、Pin 2 `GND`、Pin 3 `USB_DM`、Pin 4 `NC`、Pin 5 `VBUS_5V_USB`、Pin 6 `NC`。
2. **Hunk 2（第 438–443 行，ECO-09）**：移除已删除的 `R10 (R_ESP_BOOT)` 2 行端子（同步需在调用方 `catalog` 索引中退役 `R_ESP_BOOT` 对应项 `41bc0941336b1513` 才能消除 `unresolvedComponents`）。
3. **Hunk 3（第 959–964 行，ECO-08）**：将 `U11.F11` / `U11.F12` 由 `NC` 更新为 `CONNECTED`（`+LFXO_XL1` / `+LFXO_XL2`）。
4. **本地预检命令**：`git apply --check controlled_baseline_eco_h02_to_r7.patch`（注意：若原文件为 CRLF 或带 UTF-8 BOM，可加 `--ignore-whitespace` 预检）。
