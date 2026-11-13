# 开始新一轮 Claude 对话 — 先看这里

本ZIP为**真实工程源文件 + 13:46断点续接资料**，不是13:46已经完成工程整改的证明。

## 工程位置

- `github-pr4/hardware/evt0-r5-rework/evt0_core/evt0_core.kicad_pro`
- `github-pr4/hardware/evt0-r5-rework/evt0_core/evt0_core.kicad_pcb`
- `github-pr4/hardware/evt0-r5-rework/evt0_core/evt0_core.kicad_sch`
- `github-pr4/hardware/evt0-r4-review/`、`github-pr4/hardware/evt0-r5-experimental/` 为完整历史对照版，**只读**。
- 原工程目录 `github-pr4/hardware/evt0-r5-rework/` 下含全部原生检查脚本、BOM、库、失败报告、STATE。
- 新增 `RECOVERED_1346_UNVERIFIED/`：从13:46日志中恢复的辅助源码，不要等同于已验证项目文件。

## 请 Claude 阅读

首先读取根目录 `STATE_FOR_NEXT_SESSION.md` 与项目的 `STATE_R5_REWORK.md`、`VERIFICATION_REPORT.md`、`USB_DIFF_BLOCKERS.md`；再读取 `RECOVERED_1346_UNVERIFIED/README_脚本来源与可信边界.md`。不需重新导入三天聊天HTML。

## 当前工程哈希

PCB SHA256 `dc5f98a7b45fd428bca0fe21d0d779b6cabd7f3f8a63cf296d51d9ac0a63e3ff`

## 重要限制

- USB尚未布线；In1/In2覆铜未重铺；原生 ERC/DRC=NOT RUN；GitHub本轮未成功同步。
- 13:46新增脚本仅从工具参数恢复，可能有运行缺陷；它们不是完成PCB修改的证据。
- 任何实际布线修改均需修改工程副本并保存可下载ZIP，勿覆盖R4/R5旧版。
