# GitHub 手动同步（不可宣称已经同步）

1. 在仓库 https://github.com/yfei7131-source/AI-AR-codex-Claude- 中从 `hardware/evt1-h03-gemini-cbb-sync-20261122` 创建独立分支，例如 `hardware/evt1-h03-gemini-pr48-route-20261123`。
2. 将本交接包内 `hardware/evt1-native-eda-20261118/h03-gemini-pr48-20261123/` 目录原样上传到新分支（GitHub 网站不会自动解压 ZIP）。
3. 检查上传后 `.epro2` 的 SHA-256 与 `SHA256SUMS.txt` 一致，文件并非 LFS 指针。
4. 创建 Draft PR，Base=`hardware/evt1-h03-gemini-cbb-sync-20261122`，Head=新分支；保持 NOT FOR FAB。
5. 原生 EDA 另建独立工程重导入、执行 ERC/DRC、Import Changes、全板 257 件/729 处基线核查，并补充相机供电新铜线的专项安全审计。
6. 若 CI 没有运行，要明确记录：Checks 0 不等于通过。
