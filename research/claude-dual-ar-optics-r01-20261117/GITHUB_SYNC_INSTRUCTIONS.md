# DeepSeek / Codex 上传 GitHub 操作说明

Repository: https://github.com/yfei7131-source/AI-AR-codex-Claude-
Source basis: PR #21 / `hardware/evt1-rev-d1-20261117` / `ff7ccf93fb6ebce289e6a262adcea4e77c8d4928`（开始前重新核查远端 HEAD）。

任务：将 ZIP 中的 `research/claude-dual-ar-optics-r01-20261117/` 文件夹完整上传到独立分支 `research/claude-dual-ar-optics-r01-20261117`，创建对 PR #21 基线的 Draft PR。

约束：
- 严格逐字节保留 `CLAUDE_RESEARCH_R0_1_SOURCE.md`；校验 `SOURCE_MANIFEST.sha256`；不上传 ZIP 外层私人对话 HTML。
- 不修改 `main`、PR #19/#20/#21、KIMI 原生 CAD 与其他研究分支；禁止 force push。
- 研究报告中关于“删除 FPGA”“37g”仅为待验证 ECR，不替换 Rev D1 当前电气基线。
- 输出实际 commit SHA、Draft PR URL、源文件 Git blob/hash、校验和及上传结果。未操作成功必须如实说明。
