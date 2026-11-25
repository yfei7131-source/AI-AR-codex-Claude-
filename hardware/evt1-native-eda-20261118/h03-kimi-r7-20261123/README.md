# EVT-1 H03-R7 · 原生工程与有限布线验证

**NOT FOR FAB。基线为 PR #54 / R6；本目录不是整板布线完成或投板许可。**

## 本轮实际设计变更

仅将 PCB2 顶层三段既有 `VSYS` 铜线从 **3 mil 加宽到 4 mil**，中心线、网络、层和其他几何不变。原生对象 ID 为 `381ef9afc47f16a4`、`3de2ea0455688422`、`b95291d44ac4bb63`；替换后的对象及完整几何见 `verification/56-pcb2-vsys-width-integrated-result.json`。

修改先在独立试件验证，再写入集成工程；两次均完成保存、重载、完整铜箔回读及严格原生 DRC，无新增错误。该操作**不是新增连通、阻抗认证、C11 闭环或制造批准**。未连通总数仍为 708。

PCB1、PCB3 和全部原理图、库、器件、过孔、平面、区域及制造规则保持 R6 原状。R7 未修改核心架构、双目透明 AR、40 g 目标或安全设计。

## 原生交付

- 可编辑集成工程：`native/EVT1-H03-KIMI-R7-NOT-FOR-FAB.epro2`
- SHA-256：`85764dfc4ad8e9a408a67a78575c50b5cb091ea704c6bd3783f5d12906c6b2e6`
- 集成项目：`37f434ba2161d11e7536f134c776285fbdc9db9c040debca7ccd85f6ebbea46d`
- 独立重导入项目：`038ca2c55a325ffb9f130a53eab997bca78c8b05f2c589857db34f8be255a3e2`
- 独立再导出：`verification/independent/EVT1-H03-KIMI-R7-REEXPORT-NOT-FOR-FAB.epro2`
- 再导出 SHA-256：`22a278fda082fcc67f7caa53830ac9946a9fc83c86266af4a3a1bdd8275bb7a9`

导入回执的 `contentVerified:false` 没有被当作验收。最终档案与独立再导出已按全部 **1,451 份原生文档记录**逐记录比较一致；三板另做现场完整铜箔回读、DRC、ERC 和 Protel2 网表比较。工程含 3 Board、3 个原理图层级、21 页、3 块 PCB、257 个已放器件。

## 三板原生结果

| 板 | R6 严格 PCB DRC | R7 严格 PCB DRC | R7 严格 ERC fatal | 独立副本 |
|---|---|---|---:|---|
| PCB1 | 340 Connection + 1 Netlist | 340 Connection + 1 Netlist | 4 | 数量、签名、几何一致 |
| PCB2 | 236 Connection | 236 Connection | 0 | 数量、签名、几何一致 |
| PCB3 | 132 Connection | 132 Connection | 2 | 数量、签名、几何一致 |

这些结果是当前设计的真实失败／未闭环项，不是 DRC 通过。最终原始回执为 `verification/61-*`、`62-*`、`63-*`，独立副本为 `69-*`、`70-*`、`71-*`。PCB3 初次重载的保存、关闭和重开均成功，但首次就绪读取超时；原始 partial 回执保留，随后一次有界只读 `doc ready` 通过，最终完整铜箔及 DRC 回读通过。没有用重复重载掩盖该事件。

三份 Protel2 网表与 R6 逐组件、逐网络成员一致，共 **207 个命名网组、1,013 个网表成员**。文件在 `verification/final/` 与 `verification/independent/`。

### 继承的 H02 端子基线差异

对当前原生页／Unique ID／位号的独立核对识别 **1,076 个端子**，而不是旧 H02 清单的 1,075 个。旧 `R_ESP_BOOT` 两个端子无法按当前原生身份解析，当前 U12 的 4／5／6 三个端子超出旧清单。**该差异在 R6 基线、R7 最终档案和独立副本中完全相同，R7 未修改原理图。** 不将其写成“1,075 全等”，也不擅自补器件或改符号。

92 个旧受控 NC 均保留；归档另有 94 个原始 NC 标记，差分位置为后续继承的 U11.F11/F12、U12.4/6。完整原始差异和身份见 `verification/controlled-sch-audit.json`。该基线迁移差异与 PCB1 的一项原生 Netlist Error 分别记录，不能相互抵销。

## 制造和布线结论

- `HDI_DECISION.md`：K4 的错位微孔／埋孔／PTH／封装备选比较、拒收记录及工艺决策。
- `BLOCKED.md`：需要板厂、连接器／FPC、声学／结构及受控基线维护者确认的项目。
- `VERIFICATION.md`：实际执行、失败、跳过和验证覆盖范围。
- `verification/r7-verification.json`：机器可读的限定范围验收结果。

## 可复现校验

在仓库根目录执行：

```bash
python "hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/tools/run_controlled_sch_audit.py"
python "hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verify_r7.py"
```

校验器检查原生哈希、全部记录、三板规则不变量、三段加宽范围、保存重载、实时几何、独立再导出、端子／NC 继承边界、网表以及盲孔规则子集。其 `VERIFIED-LIMITED-R7` 不代表制造、阻抗、实物或整板布线通过。
