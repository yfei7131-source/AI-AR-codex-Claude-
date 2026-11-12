# EVT-0 R4 独立 DC 布线试验 — 2026-11-12

**仅为局部研发副本，DRC 失败，制造与实机验收未放行。** 从提交 `164067e6cc5e7fb021a6232a775b153f0bcfd1fe` 的 R3 最终板复制。主项目可直接打开 [evt0_core.kicad_pro](H02/evt0_core/evt0_core.kicad_pro)，其原理图、PCB、规则、项目符号库和库表均在副本内。复查官方封装差异需安装 KiCad 10 标准库，3D 预览需标准模型库。

## 本次实际结果

- 仅补通 `/CHG_EN1`：R3.1 → U3.6。U3 选模下拉仍为 USB100，CE 禁充及 R5/R36 DNP 不变。
- 最终删除 R4 副本内 6 段 QFN 南侧重复地环/桥接线，为该信号扇出让位；保留所有其他旧铜的 UUID、几何和网名，增加 12 段 CHG_EN1 线与 2 个过孔。逐项 UUID、整数几何和原因见 [dc-change-audit.json](evidence/dc-change-audit.json)。R3 原件未删除、未更改任何铜项。
- 84 件封装、305 个物理编号焊盘、284 个唯一引脚的网名/封装/DNP/BOM 对应仍一致；器件与焊盘位置、尺寸、钻孔、角度和 DNP 均未变。没有实施封装孔径变更、规则放宽、接口装配或固件解锁。
- 最终板有 1013 段线/弧、86 个过孔，合计 1099 个铜项。4 层、1.0 mm，总厚度与工艺门槛不变。
- **原生 KiCad 10.0.7 DRC JSON 与文本报告均 exit 5**：15 个规则违规（12 个 U1 孔径错误、U1/J3/J1 共 3 个库图形差异警告）、58 个未连接项目、0 个原理图一致性问题。相对 R3 的 59 项仅减少 CHG_EN1 这一项；未出现新的短路、间距、地网缺口或悬空线警告。R3 的 4 个 J3 地网缺口原样保留。
- 未新跑 ERC：R4 原理图、符号库与规则输入从 R3 继承，原始 R3 ERC 0/0 记录仍是历史证据。本次仅报告新 PCB 映射/DRC 结果，不把继承记录称作 R4 新验收。

最终 PCB SHA-256：`8bd12a6f5e0cf8387e02309d92ff7ffc4a36350ab4e68a4f381ce8a96d1efed0`。这是 Windows 本机输入字节哈希；Git 的 LF 归一化可能改变归档文本字节哈希。

## 失败尝试与保留事项

`/CHG_PGOOD_N` 网格搜索仍未解决；`/VBUS` 的短扇出与原 USB 地桥发生几何冲突。一次移除 USB 地桥的实验虽然补通 VBUS，却引入 1 个地连接缺口和 2 个悬空线警告，该方案已撤回。两处替代地过孔候选也与既有 CC/电源铜线冲突，程序拒绝保存。**最终副本保留 R3 的 USB 地桥，VBUS 和 PGOOD 仍未连接。** 日志保留在 `evidence/dc-routing-attempt*.txt`，未采用方案的原生 DRC 见 [attempt3-drc-before-ground-repair.json](evidence/attempt3-drc-before-ground-repair.json)。不以被撤回实验的“已连通”描述最终 PCB。

没有对 CAM_2V8 支路追加布线；J3/J4/J7 未确认端点、所有 DNP 和电压选择均保持。其余相机、显示、音频、USB、天线、U3 热孔/钢网、电池与供电安全门槛继续开放。下一步应在独立 R4 副本有计划地重排局部回流/扇出，再处理 VBUS、PGOOD 和 USB 差分；本次不扩大器件布局或接口设计范围。

## 真实证据与复现

- [最终原生 DRC JSON](H02/evt0_core/evidence/pcb-drc-final.json)、[文本报告](H02/evt0_core/evidence/pcb-drc-final.rpt)、[验证汇总](evidence/pcb-verification.json)、[原生检查日志](evidence/native-verification-log.txt)。所有检查使用 `--severity-all --schematic-parity --exit-code-violations --refill-zones`，临时配置载入官方库；没有修改全局设置或严重度。
- [最终布线日志](evidence/dc-routing-log.txt)、[铜线变更审计](evidence/dc-change-audit.json)、[剩余网络数量](evidence/remaining-connections.json)。其他复制自 R3 的中间 DRC/工程审查文件保持其 R3 历史语境，不能当作本次 R4 结果；本页上述 `final` 报告为实际 R4 输入的检查。
- 操作前 [R3 全文件哈希清单](evidence/r3-source-before.json) 与结束 [保护检查](evidence/r3-source-after.json)：74 个 R3 文件全部 SHA-256 一致，差异 0。最终板也由检查器确认验证期间字节未变。

从仓库根使用 KiCad 10 自带 Python 复现检查（实际路径按安装位置替换）：

```powershell
& 'C:/codex-tools/kicad-10.0.7/bin/python.exe' hardware/evt0-r4-review/H02/evt0_core/gen/verify_pcb.py
```

生成本次局部试验的脚本为 `H02/evt0_core/gen/minimal_dc_r4.py`，读取旁边保留的 R3 最终板，写入 R4。重复运行会重建这个独立试验副本；已有新的 R4 人工修改时应先另存再运行。不要运行继承的 `gen/pcb_layout.py` 或 `gen/gen_kicad.py` 覆盖当前布线板。

本次没有制造文件、焊接/通电、热/隐私故障、USB/无线或整机验证。`manufacturing_release=false`。
