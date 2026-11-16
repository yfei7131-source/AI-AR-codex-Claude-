# 智元跃动 AI/AR V1.0 — EVT-1 Rev D1.1

**NOT FOR FAB / NOT_FOR_FAB**。保持双目透明AR和40g产品目标。本轮只修改确认的AVDD联锁与关电逻辑，Rev D1基线保留在同级evt1-rev-d1-20261117。

权威电气表：02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv；PINMAP逐针派生。先读01_Architecture_and_Interfaces/KIMI_REV_D1_1_UPDATE_CHECKLIST.md和ICD Rev D1.1。

可复现：python 00_Rev_D1_1_Change_Record/rev_d1_1_apply.py；python 05_Verification_Scripts/check_rev_d1_1_reproducibility.py；python 05_Verification_Scripts/verify_rev_d1_1_electrical.py；python 05_Verification_Scripts/test_rev_d1_1_avdd_safety.py --require-ngspice；make -C 03_FPGA_RTL all。

PASS仅表示对应测试覆盖的文件、逻辑或模型通过。物理电路、JBD参数、原生CAD/ERC/DRC、掉电轨序和实测仍BLOCKED。CI日志和完整ZIP分别交付；不得据此投板。
