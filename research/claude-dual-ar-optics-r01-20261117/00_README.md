# Claude 独立光学研究 R0.1 — 归档说明

状态：**SOURCE-ONLY / UNVERIFIED / NOT FOR FAB**。

- 项目：智元跃动 AI/AR 智能眼镜 V1.0 EVT-1
- 来源：Claude Fable 5.2，2026-11-17 02:20 左右导出的研究正文。
- 本包基于用户上传的 `新建文件夹(3).zip`；`新建文件夹(4).zip` 与其 SHA-256 完全一致，为重复副本。
- 完整原始研究正文见 `CLAUDE_RESEARCH_R0_1_SOURCE.md`，**字节不改动**。
- 重要：Claude 明确未读取 Codex Rev D1 实际工程，所以它对 SoC/DSI/FPGA/重量的条件性架构建议**未经现有硬件设计对齐**。
- **本研究不修改** Rev D1 原理图、BOM、NETLIST、RTL、PCB；不得将 ECR 提案当作设计冻结或原厂确认。
- **不上传** 对话记录 HTML；原始 ZIP 内包含历史对话，公开 GitHub 归档研究文件即可，避免公开聊天数据。源 HTML 的 SHA-256 留在来源记录中供离线核对。

## 研究涵盖内容

JBD Mini II/Mini III 光机与单绿 SRG 波导；双目 3–6 arcmin 对准建议；光学与热预算；LIFCL-17 条件架构；双眼校准；工装/EVT 测试；15 项风险清单及 Gemini/KIMI 任务卡。

## 已知限制

- 现有 Rev D1 使用 ESP32-S3 + nRF5340 + iCE40UP5K，不能直接按研究的“双原生 MIPI DSI 主控”假设移除 FPGA。
- Claude 的 37g 独立光学估算不等于 Rev D1 的 41.1978g 设计估算；需统一 BOM 和装配 CAD 后重算。
- JBD 实际引脚、初始化、命令、电压和 STEP 尚未取得正式签署文件。

## 上传说明

建议独立研究分支 `research/claude-dual-ar-optics-r01-20261117`，以 Codex Rev D1 PR #21 当前基线为父提交；只提交本文件夹，创建 Draft PR，**不得直接合并 main 或覆盖 Rev D1**。
