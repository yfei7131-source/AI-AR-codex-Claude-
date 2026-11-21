# EVT-1 H03 接管与原生整改

**NOT FOR FAB。** 基线为 PR #46 的 `35b44f515fdf2bf7c004dab50c63c0c7a95441e0`。接管时工作区已有 Gemini 未提交的 V4 原生工程。原始 98 个文件逐一备份并做 SHA-256 比对。当前编辑器重新导出的 Gemini 验收工程与交接归档逐文档核对一致。Codex 在独立嘉立创 EDA 专业版 V4.1.97 项目中继承了该工程。 [PR #46](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/46) · [备份清单](evidence/takeover/GEMINI-SHA256.txt)

[Codex 保存后导出的可编辑工程](native/ZY_AIAR_EVT1_H03_CODEX_V4_NOT_FOR_FAB.epro2) · [独立重导入与逐对象核验](evidence/takeover/codex-verification.json)

## 实际铜线整改

| 板 | PR #46 未连通 | Gemini 交接 | Codex 保存及重导入 | Netlist Error | 去耦类告警 |
| --- | ---: | ---: | ---: | ---: | ---: |
| PCB1 主板 | 358 | 358 | 358 | 1 | 3 |
| PCB2 光学桥板 | 238 | 238 | 237 | 1 | 10 |
| PCB3 右板 | 136 | 134 | 134 | 1 | 0 |
| 合计 | 732 | 730 | 729 | 3 | 13 |

- **PCB2 `AVDD_WD_Q`。** 实测原生焊盘 `R3.1 → R6.1` 之间新增一段底层走线，宽 3.5 mil、长 21.7 mil。局部规划从真实铜回读和盲孔层跨距计算障碍，保存后导出与独立加载的 DRC 一致。更新前后连通性回执中，该对焊盘由断开变为一段铜线直连。 [路径回读](evidence/takeover/operations/pcb2-avdd-path-after.json)
- **PCB3 GND。** 移除 `C5.2 ↔ U11.C2` 的六段重复支路。原接地走线及其它支路保持连接，原生 `duplicateSegments` 从 1 降为 0，严格 DRC 的 134 项未连通和 1 项网表告警逐项一致。 [修改后证明](evidence/takeover/operations/pcb3-gnd-verified.json)
- 归档差异精确到上述七条 `LINE` 记录。三板原理图及规则未变更，207 个 Protel2 网络组通过原文件逐字节比对。严格 ERC 仍为主板 11、桥板 6、右板 7 条 fatal 诊断，独立重导入后的三板 ERC/DRC 逐项一致。 [三板原始 ERC 和 DRC](evidence/takeover/after/) · [独立重导入回读](evidence/takeover/independent/)

## V4 DFM 与 U11

- **141 个盲孔。** PR #46 和当前工程各复核 141 个。V4 分别计算孔壁至真实铣边、铜环外缘至铣边，以及同网或异网孔壁间距，附对应中心距。两份工程的已测 JLCPCB 孔壁与孔对项目均为零告警。Gemini 的整改关闭了另设的 0.350 mm 铜边布置告警 6 项。Codex 铜线整改未移动或改径任何孔。 [V4 测量口径与测试](DFM_V4.md) · [本轮最终归档逐孔证据](evidence/takeover/final-dfm/)
- **U11 nRF5340-CMAA。** 原厂球位、原生焊盘与 Protel2 对齐 95 个，52 个已分配网络，43 个显式 NC。保持 ECO-08 的 LFXO。按现有 6.0 mil 铜距、3.0 mil 环宽和 0.075 mm 孔径计算，36 个内圈有网球位中 25 个未通过居中盲孔铜距筛查。Nordic Config #3 参考板为四层和一级盲孔，其环宽与 EVT-1 不同。2+N+2 制造与逃线仍待批准。 [最终 95 球矩阵](evidence/takeover/final-u11/u11-cmaa-config3-ball-matrix.csv) · [原厂资料与电气判定](u11/README.md)
- **剩余异常。** PCB1 有两个应转 PCB 但未绑定封装的接口。PCB2 和 PCB3 的聚合 Netlist Error 仍缺宿主差异明细。13 项去耦类告警已经定位，其中两项是功能指定的定时或滤波 RC。其余器件按真实负载与回流重评估，当前布局筛查未找到安全的单件搬移方案。 [逐项剩余审计](residual/README.md) · [制造阻断](BLOCKED.md)

保留真实双目透明 AR、40 g 整机目标、MECR-01 的几何评估边界和 PR #40–#46 历史工程。

## 复现

在本目录执行以下命令。当前工作副本和独立回读项目分开采集。 `capture_codex_live.py` 的恢复模式复用首次创建的独立验证工程 UUID。

```powershell
python -B -m unittest discover -s . -p test_independent_hdi_dfm_auditor_v4.py -v
python -B -m unittest discover -s residual -p test_residuals.py -v
python -B u11/audit_u11.py --check
python -B verify_codex_round.py --capture evidence/takeover --before evidence/takeover/before --live native/ZY_AIAR_EVT1_H03_CODEX_V4_NOT_FOR_FAB.epro2 --restored evidence/takeover/independent-editor-export.epro2 --output verification-replay.json
```

应用测试首次在 Windows HTTP 用例遇到连接错误，复跑 102 项全部通过。原生重导入曾在工程树加载前返回找不到图纸，加载完成后使用同一独立项目继续验证。两次情况均保留回执。公开提交的文本回执移除了本机绝对路径和团队标识，原生归档与 Protel2 文件保留原字节。
