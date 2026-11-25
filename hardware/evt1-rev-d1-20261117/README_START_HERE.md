# 智元跃动 AI/AR V1.0 — EVT-1 Rev D1

**NOT FOR FAB / NOT_FOR_FAB**。双目透明 AR；40g 产品目标保持。源于 PR #20 / 882242f，恢复 Claude 2026-11-17 01:10 中断脚本。本包交付实际 CSV 电气工程、可重现迁移、原版 FPGA 和验证工具；尚无 Rev D1 原生 CAD 或实物验证。

先读 `01_Architecture_and_Interfaces/KIMI_ENGINEERING_HANDOFF_REV_D1.md`。权威输入为 `02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv`，PINMAP 每行从同一终端生成。旧文件名 FROZEN 不代表制造冻结。Rev D 原包保存在仓库同级目录 `evt1-rev-d-claude-20261117`。

运行：`python 00_Rev_D1_Change_Record/rev_d1_apply.py`；`python 05_Verification_Scripts/verify_rev_d1_electrical.py`；`python 05_Verification_Scripts/check_rev_d1_reproducibility.py`。迁移始终读取干净 Rev D，不向其写入。FPGA 保留 `make -C 03_FPGA_RTL all`。
