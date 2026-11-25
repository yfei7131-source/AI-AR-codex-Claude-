# P1-01 原生批次工具

适用于已审批的 EVT-1 引线、4/10 mil GND 盲孔及同面空闲贴片器件移位。批次要求原始 EPRO2 的 SHA-256、板号、功能网络、原生端点和坐标。时间、记录和外部签核进入 V2.0 各级门禁。脚本仅处理已定义的操作，EDA API 的任意命令由专项单列验证。

运行环境为本仓库、Python 3.10+、已连接的 EasyEDA Agent CLI 和嘉立创 EDA 专业版。如果计划包含盲孔，须给出官方桌面 CLI 的路径和其已连接 session ID，脚本还会在 SDK 侧复核当前项目和 PCB 的 UUID。

默认自动固定到唯一已连接且兼容的 1.20.0 Connector。存在多个兼容窗口时，为 apply、reimport、replay 和 restore 显式提供 --window，值取自 easyeda health 的 windowId。旧版注册不参与批次。

## 使用顺序

1. 从明确归档与新鲜原生回读构造计划。`r11-fixture-plan.json` 是已发布 R10→R11 增量的历史测试样本。每次新批次给定新计划 ID 与新检查点哈希。L1 对应局部布线，L2 对应批量修改，L3 增加三板及独立重导入。位姿使用 EDA 原生 mil、Y 向上、角度为度。两端口用 `Designator.Pad` 或现有线端和过孔的 primitive ID。带 GND 盲孔的线路必须从原生端口连续走到盲孔中心，且完整孔盘落在原生 GND 平面内。
2. `batch_gate.py lint --checkpoint BASE.epro2 --plan plan.json` 校核检查点、范围、线宽和坐标。工程线宽、层跨与几何要求仍须用捕获的规则和预先评审的设计约束给定。
3. `native_batch.py apply --checkpoint BASE.epro2 --plan plan.json --name P1-ISOLATED-TRIAL-20261125 --out trial`。有盲孔追加 `--editor PATH --session ID`。写入前核对新隔离项目的原生档和移动器件的旧端子状态。所有写入后的 `POST-BATCH.epro2`、`baseline/` 和 `after/` 保存原生证据，`candidate.json` 表示有待接纳的候选。各组写入均以当前项目和文档为界。
4. L2/L3 运行 `dfm_review.py --checkpoint BASE.epro2 --post trial/POST-BATCH.epro2 --plan plan.json --baseline-logs trial/baseline --after-logs trial/after --out dfm`，生成独立原生 V4 跨层孔距、板边、孔环和旧版铜碰撞矩阵证据。几何形状不确定的候选会保持待审。 3W、阻抗、铺铜回流、三维及材料工艺须按批次范围补充对应专项工程证据。
5. 独立重导入运行 `native_batch.py reimport --checkpoint trial/POST-BATCH.epro2 --name P1-ISOLATED-REIMPORT-20261125 --out replica`。L3 与接受为下一里程碑检查点的 L2 均需独立重导入。L3 校核三块板。按审核过的原生数据完成对应级别的检查。
6. `batch_gate.py verify --checkpoint BASE.epro2 --post trial/POST-BATCH.epro2 --plan plan.json --baseline-logs trial/baseline --after-logs trial/after --dfm-review dfm/dfm-review.json --reimport replica/NATIVE-REEXPORTED.epro2 --reimport-logs replica --out acceptance.json`。仅 L1 可省略 DFM，局部或批量试验可在无升级风险时省略独立重导入并保持在隔离项目。结果按对象比较原生 DRC 与 ERC，核对保持的布局、铜段、焊盘网络、平面、禁布区及规则，检查编译网表字节一致。
7. 准备下一检查点时，用 `native_batch.py replay` 加 `--acceptance acceptance.json` 在另一工程复放。接纳文件必须绑定同一计划、检查点且有独立重导入。按实际复放归档验证一遍，之后交由主工程负责人接入。
8. 任何一笔失败保留原始回执。用 `native_batch.py restore --checkpoint BASE.epro2 --baseline-logs trial/baseline --name P1-ISOLATED-ROLLBACK-20261125 --out rollback` 从只读源归档恢复到一个新项目。L1/L2 目标范围可通过 `--boards PCB2` 指定。比较恢复档、原生 DRC/ERC 对象和网表，`rollback.json` 保留恢复身份。

每条命令从脚本所在目录执行时在命令前加 `python`。输出目录和归档输出使用新路径。L3 归档应包含原始日志、实际工程输出、计划及审核证据的 ZIP。报告固定为 **NOT FOR FAB**。

## 工具验证

`python -m unittest discover -s . -v` 复跑真实历史归档的几何初检及失败分支。设置 `P101_R11_INDEPENDENT_EXPORT` 指向历史 R11 独立重导入的真实 EPRO2，可以复跑 L3 测试。最近实测共八项通过，历史连接错误 689→676 仅用作回归样本。
