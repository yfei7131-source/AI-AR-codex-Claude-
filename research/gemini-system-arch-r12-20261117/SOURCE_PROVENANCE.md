# Gemini R1.2 来源与使用边界

- 用户上传原始：`gemini输出.zip`（SHA256 `6cfa8bcbefac939a3ba176cbc1ea5c041b9bb15b18c3e1b0a661fed1b857ed58`）
- 内层：`ZY_AIAR_EVT1_SYSTEM_ARCH_R1_2_PACKAGE.zip`（SHA256 `39e179153252763d83a85fec707083c958ab134b7e4972b4374e3848bfb0d682`）
- 本归档从内层保留六份实质交付：EVT1_SYSTEM_ARCH_R1_2.md、RECONCILIATION_EVIDENCE_TABLE_R1_2.csv、KIMI_DESIGN_CONSTRAINTS_R1_2.md、SYSTEM_RISK_REGISTER_R1_2.csv、verify_r1_2_integration.py、r1_2_verification_report.txt。
- 外层风险/对账 CSV 与内层完全相同，避免重复存储。
- 外层 Gemini 对话导出（Markdown）属于私人聊天过程，未进入本公共工程归档。哈希：`d001721890078b503cc355a10cd98b2e0e0900d7cd7a103efa6311f6e5903d02`。
- **重要版本说明**：R1.2 原始校验脚本使用绝对 `/working_dir/...` 路径，引用 Rev D1.1 旧 commit `e78e5726`，不能直接在 GitHub Actions 中复跑；应先改为相对路径并核对最新 PR #25 HEAD `97ee1f6733416099f842dca00389ab50f3568c96`。原文件为保留证据未被静默修改。
- 原报告称静态对账 8/8 PASS，禁止解读为 FPGA EDA、SPICE、ECAD 或实物的成功。
- JBD FPC、供电时序、指令、3D STEP、双眼独立 CS/读回、真实40g、光机安全等依然有阻断。
