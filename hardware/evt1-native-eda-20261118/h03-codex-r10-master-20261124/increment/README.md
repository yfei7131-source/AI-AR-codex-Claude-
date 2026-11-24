# 原生工程增量接入与回滚

R10-MASTER 的写入由唯一主工程维护者执行。专项窗口交付基线提交和归档 SHA-256、板号、网络和已确认端点、坐标、线宽、设计意图及证据。接收端从对应原生归档建立隔离副本，保留专项原件和现场失败日志。

本目录的工具执行已验证的同层加线增量。可定位的端点为已放置焊盘中心或既有同网过孔／线端。设备换层、接口映射、原理图 ECO、平面和叠层属于另外审查的设计变更。编辑器在接线时自动分段，工具逐网、逐层、逐线宽验证中心线覆盖并核对锁定线。计划采用 mil、Y 向上，保留明确的原生焊盘号。

在已连接嘉立创 EDA 专业版的本地电脑，从该目录运行。替换代码块内的归档路径、输出目录与主项目 UUID。

```powershell
python -B easyeda_increment.py apply <checkpoint.epro2> pcb1-batch-01.json <trial-output>
python -B easyeda_increment.py apply <checkpoint.epro2> pcb1-batch-01.json <master-output> --target <master-uuid> --acceptance <trial-output>/acceptance.json
python -B easyeda_increment.py restore <checkpoint.epro2> <recovery-output> --name EVT1-H03-R10-RECOVERED-NOT-FOR-FAB --board PCB1
```

每次接入先导出实时工程，对账 1,451 份原生文档记录，然后用 typed PCB API 写铜。保存重开后复验严格 DRC 及铜路径。若宿主已完成保存、关闭、重开但就绪读取超时，`verify <checkpoint.epro2> <plan.json> <batch-output>` 只补做身份、就绪和落盘复验，保留原超时回执。对主工程补证时加 `--master`。不重放已落盘铜线。

失败批次停留在隔离副本。恢复从已知良好归档导入一个不同 UUID 的工程，逐记录复核并复跑原生 DRC。主工程需要回滚时，从同一检查点恢复后重新指定当前主项目 UUID，历史工程和原始记录保留。完成批次后，工程级验收另做三板严格 ERC、DRC、Protel2 网表对账及独立重导入。任何制造放行均需独立于本流程的工程授权。

本地 ZIP 含逐批快照、PR #60 原件和独立再导出副本。在 ZIP 根目录复现发布对账。

```powershell
python -B increment/verify_regression.py . increment/baseline-pr60.epro2 EVT1-H03-R10-MASTER-NOT-FOR-FAB.epro2 increment/independent-readback.epro2
```
