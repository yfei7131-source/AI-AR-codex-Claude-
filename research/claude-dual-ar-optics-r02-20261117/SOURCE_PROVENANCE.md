# Claude R0.2 来源与使用边界

- 用户上传原始：`Claude输出(1).zip`（SHA256 `0c147eb6ef4913d2e1158d5fc85d7be6974c4de8ec4a2c81213f6446df171d64`）
- 内层：`智元跃动 R0.2 AI 可执行研发交接包.zip`（SHA256 `cdae5e7e1a8e5424f28c7fe382a7cd4dd5510ae48a54dd0ec25069c5cbb43d52`）
- 原始包 `MANIFEST.json` 所有源文件哈希已经逐项复核；本次为公开 GitHub 制作了**有记录的隐私裁剪**。
- 保留 R0.2 研究正文 `05_ORIGINAL_EXTRACTS/SRC_R02_CLAUDE_RESEARCH.txt`、工程决策/执行/验收文档及角色提示词。
- 排除 4 份清理后的历史私人聊天转录 `SRC_C*_CONVERSATION_CLEAN.txt`（并未对外上传），另使用新的 manifest/hash，因此原始 `MANIFEST.json` 与 `SHA256SUMS.txt` 不直接复用。
- 排除文件及原始 SHA256（本 repo 不提供原始转录）：
  - `05_ORIGINAL_EXTRACTS/SRC_C1_CONVERSATION_CLEAN.txt`: `1b591672dd80a651280e53e081c89cb86d92585a9da9399f994cb2ba4e8c76f9`
  - `05_ORIGINAL_EXTRACTS/SRC_C25_CONVERSATION_CLEAN.txt`: `1a89127e3b9c50293ed60c5fe4485389a1dd5ad635c5c57c1c127771a352de38`
  - `05_ORIGINAL_EXTRACTS/SRC_C4_CONVERSATION_CLEAN.txt`: `b2efe1bf817b75b7b93f5285a26cb778808ed39a3aa64f65ffd55852fba404d7`
  - `05_ORIGINAL_EXTRACTS/SRC_C5_CONVERSATION_CLEAN.txt`: `769dbd5052d8e724838531bb145fcce4c42e2c82a4d6b069e68bb8ac0a216efb`
- 此包是 ECR/ADR/测试规范与交接包；**无 EVT-1 原生可编辑原理图/PCB/STEP**，研究意见不是硬件设计批准。
- 原 Claude 文档可能引用历史 Rev D1 的旧状态。WorkBuddy/Gemini/Codex 执行前须核对 Rev D1.1 最新 `97ee1f6733416099f842dca00389ab50f3568c96` 与已通过的 CI，不能用旧报告回滚电源和安全联锁。
- P1 是现行保留方案；P2/P3 仅用于比较研究。不得未获 JBD NDA/EVK 验证就删除 FPGA 或重画 J_DISP。
