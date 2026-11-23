# H03-R7 · 实际验证与跳过项

## 原生工程

| 项目 | 实际结果 | 原始证据 |
|---|---|---|
| R6→R7 基线 | 原生设计记录未变，先保存备份再工作 | `baseline/`、`verification/r6-to-r7-baseline-diff-pcb1.json` |
| PCB2 三段 VSYS 隔离加宽 | 3→4 mil，236 Connection 不变，无新增 DRC | `verification/54-pcb2-vsys-width-trial-result.json` |
| 同一修改集成 | 保存、重载、完整几何对账通过，无新增 DRC | `verification/56-pcb2-vsys-width-integrated-result.json` |
| PCB1／PCB3 | 原生记录原样继承 | `verification/r7-verification.json` |
| 三板最终 DRC | 340+1／236／132；均仍有未闭环错误 | `verification/61-*-final-drc.stdout.json` 等 |
| 三板严格 ERC | fatal 4／0／2 | `verification/61-*-final-erc.stdout.json` 等 |
| 三板网表 | 207 网组／1,013 成员，与 R6 一致 | `verification/final/*.net` |
| 独立导入及再导出 | 独立 UUID，所有 1,451 份文档记录一致 | `verification/66-*`、`68-*`、`r7-verification.json` |
| 独立副本现场复检 | 三板 DRC／ERC／铜箔／网表一致 | `verification/69-*`、`70-*`、`71-*` |
| 盲孔规则子集 | PCB1／2／3：61／40／41 个盲孔，V4 子集 0 违规 | `dfm/`、`verification/r7-verification.json` |

盲孔 V4 子集结果不是完整 DFM、阻抗或制造商签核。原生 DRC 的 `passed:false` 始终按失败保留，没有改成通过。

## 保存与重载

- PCB1、PCB2：显式 `saved:true`，保存→关闭→重开→稳定读取通过。
- PCB3：显式保存、关闭及重开成功，首次就绪读取超时；一次有界只读 `doc ready` 返回 `ready:true`，之后完整 dump／DRC／ERC／netlist 成功。
- 原始 `63-PCB3-final-reload.stdout.json` 保持 `partial`；没有覆盖或改写历史证据。

## 仓库测试

实际分开执行，未将两条命令合并宣传：

- Python：**102 项中 101 通过，1 项按条件跳过**，结果 `OK (skipped=1)`。原始输出：`verification/repository-python-tests.txt`。
- 被跳过的浏览器契约使用真实 `D:\1\Kimi\Kimi.exe --test tests/web_client.test.cjs` 独立执行：**25 通过，0 失败，0 跳过**。原始输出：`verification/repository-node-tests.txt`。
- Windows 普通 `node` shim 的两次环境尝试失败已停止，没有修改测试或用 shim 冒充通过。早期组合输出保留在 `verification/repository-tests.txt`。

## 本轮未执行／不支持／跳过

- 未取得板厂对 0.80 mm 二阶 HDI、顺序压合、阻抗、填孔及捕获盘的确认，未投板、未导出制造放行结论。
- 没有实物、40 g 整机、光学、RF、热或结构装配测试。
- 未生成声称已验证的 3D 装配模型；完整几何 dump 仅用于数据对账。
- 未重复 KiCad 导入、重画原理图、SES 层跨探针或已失败的同参数自动布线。
- 无合法新支路候选，因此没有调用新路线集成工具强行写入。
- 没有用未知 MPN／封装、假阻抗、假成本或假测试消除 BLOCKED。

## 机器校验

`verify_r7.py` 输出 `VERIFIED-LIMITED-R7`。此状态只覆盖：限定加宽、档案完整性、规则不变量、保存重载、独立导入再导出、网表、继承端子／NC 差异及盲孔规则子集。H02 旧端子清单的继承差异标为 `INHERITED-R6-DELTA-NOT-R7-REGRESSION`，不是全部端子基线 PASS。
