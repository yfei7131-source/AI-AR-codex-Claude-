# EVT-1 嘉立创 EDA 三板回读 · NOT FOR FAB

源设计取 PR #30 的 `14e95c11d237eee7e3d32c4e8ac729ac84bbbecb`，其受控三板原理图沿用 PR #29 的 `cec8dea`。实读对象是嘉立创 4.1.97 中导入的 `EVT1-AR-YF-001`。项目级 `sch connectivity --all-pages` 遇到跨板复用位号而返回 `duplicate component cmp-BAT1`。已分 21 页导出，由 [`board_pages.json`](evidence/jlc-import/board_pages.json) 标明各页应归属的板。原始文件按 SHA‑256 锁定。

| 核对项 | 状态 | 实际结果 |
| --- | --- | --- |
| 三板端子、按页网络名和 NC 标记 | PASS | 左主板 524、桥板 315、右音频板 236，合计 1,075 个端子。983 个有网端子和 92 个 NC 标记均匹配，未检出缺失、额外端子或网络名差异。 |
| SCH 页归属与 SCH/PCB 绑定 | FAIL | 每块板的根图已导入，各功能子页独立成其他原理图文档。三块板的 PCB 绑定为空，且多出一项电源来源板组。仍需重建板级跨页连通及隔离。 |
| 器件纳入 PCB 标志 | FAIL | 左右电池及扬声器共四个外部装配符号误被设为加入 PCB。 |
| 嘉立创原生严格 ERC | FAIL | 21 次调用均返回 `passed:false`，包含 `MISSFOOTPRINT`、`PORTTOPIN` 等规则。根图与子图调用的报告可能重复。原始结果在 `evidence/jlc-import/erc/`。 |
| BOM 与封装身份 | BLOCKED | 233 个受控参考 MPN 待导入字段补齐，114 个已映射封装在导入原理图的 BOM 中缺少对应字段。 |
| PR #30 部分 PCB 回读 | BLOCKED | 35 个候选器件覆盖 393 个对应焊盘编号，未检出已比对焊盘的网络差异。完整 PCB 网络、封装身份、布局与 DRC 待核。 |

按页端子比对按板限定作用域。连接器快照的 net ID 由网络名生成，不能单独作为跨页连通或跨板隔离的证据。报告独立记录端子比对、器件入板属性、原生层级、严格 ERC 和 PCB 覆盖范围。制造状态保持 BLOCKED。

## KIMI 回件格式

1. 先恢复三板各自的原理图子页归属，按板建立 PCB 绑定。把 `BAT_L`、`BAT_R`、`SPK_L`、`SPK_R` 保持为外部装配符号。恢复受控 MPN、封装身份和映射，保留 JBD 未冻结接口。
2. 每页导出 `easyeda sch connectivity --page <UUID>` 至 `sch/<UUID>.json`。在该页读回 `easyeda sch list --include-pins`、`easyeda bom export --type csv --enrich=false`、`easyeda sch drc --json --strict`，依次写入 `pins/<UUID>.json`、`bom/<UUID>.csv` 和 `erc/<UUID>.json`。附原始 `easyeda board list` 与 `easyeda sch pages` JSON 填入 `lceda-boards.json` 和 `lceda-pages.json`，附三板归属 `board_pages.json`。同时提交三板原始 PCB dump，以 `M-MAIN-L.json`、`M-OPT-BRIDGE.json`、`M-AUD-R.json` 命名。当前输入约定保留受控 CAD 位号和封装名，有重命名时附可审核映射。
3. 交回板级网表、原生 ERC/DRC、确切工程版本与原始回读，再审跨页网络、焊盘和板间端子。完整回件前维持 NOT FOR FAB。

## 复现

下列命令从仓库根执行。`--source` 可指定独立受控输入目录，默认使用本仓库的 `hardware/evt1-native-eda-20261118`。

```bash
pkg=hardware/evt1-native-eda-20261118
python -m unittest discover -s "$pkg/closure" -p test_verify_eda_return.py -v
python "$pkg/closure/verify_eda_return.py" \
  --schematic "$pkg/closure/evidence/jlc-import" \
  --pcb "$pkg/kimi-return/native/restored-readback" --output readback.json
```

对账器退出码为 0 PASS、1 FAIL 或 2 BLOCKED。当前实测退出 1，测试验证该 FAIL 及各独立状态能够被正确保留。原始运行见 [JSON 报告](evidence/readback-report.json)、[运行日志](evidence/readback-run.log)和[测试日志](evidence/unittest.log)。
