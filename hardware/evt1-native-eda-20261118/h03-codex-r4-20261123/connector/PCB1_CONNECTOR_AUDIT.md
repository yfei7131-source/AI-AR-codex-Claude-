# PCB1 J2 / J3 审查 · NOT FOR FAB

从 R3 和 R4 原生 .epro2 重建 J2、J3 符号管脚与原理图线段端点，按线组的 NET 属性读取网络。两版的 30 个触点、实例、封装字段和 PCB 放置状态逐项相同，30 个触点均匹配历史嘉立创 EDA 专业版 Protel2 导出。R4 原生严格 DRC 仍返回 1 项板级 `Netlist Error`，消息只列 `Import Changes`，没有给出逐对象差异。J2 和 J3 是回读确认的待放 PCB 器件，设备库 Footprint 与实例 Origin Footprint 为空。历史原生 Protel2 中两者均为 `Convert to PCB=yes`，J2 在原生工程中有显式字段，J3 使用实例默认值。

## J2 · J_CAM

- 主板端是 Hirose **BM28B0.6-24DS/2-0.35V(53)** 插座（CL0673-5025-0-53），原厂规格为 24 个信号触点、2 个端部电源触点、0.35 mm 节距和 0.60 mm 对插高度。对应系列 24+2 插头是 **BM28B0.6-24DP/2-0.35V(53)**（CL0673-5024-0-53），应在实际配对 FPC 上复核。两侧使用各自的原厂焊盘图，不能镜像复制同一封装。原厂系列目录第 6、7 页分别给出插头、插座的铜箔与钢网布局。型号专用原厂 2D 图页可定位。 [插座原厂页和图纸](https://www.hirose.com/en/product/p/CL0673-5025-0-53) [插头原厂页和图纸](https://www.hirose.com/en/product/p/CL0673-5024-0-53) [系列目录](https://www.hirose.com/en/product/series/BM28)
- 主板插座本体为 6.80 × 1.70 × 0.60 mm，原 BOM 的长轴为 5.50 mm。按继承锚点 (2.90, 19.00) mm、长轴沿 Y，原厂本体投影为 X [2.05, 3.75] mm，Y [15.60, 22.40] mm，比原长轴预算各端大 0.65 mm。FPC 出线、补强、盖件和工具装配包络须另计。R4 可核定本体尺寸，但供应商的相机模组订货号、FPC 版本、触点编号观察面和装配防反约束仍缺。 [H02 机械与接口门禁](../../h02-erc/HARDWARE_GATES.md) [原厂插座规格](https://www.hirose.com/en/product/p/CL0673-5025-0-53)
- 原生 PCB1 前后回读显示，按该锚点投影，顶层 U16、U21 各有 10 个焊盘中心落入 J2 本体投影。其包围框重叠分别为 1.700 × 3.235 mm、1.700 × 3.210 mm。U15、U22 的包围框也与投影相交。旧锚点无法直接放件并保留现有顶层布局，配对 FPC 冻结后需联动调整。碰撞初筛的逐件结果随 JSON 保存。
- 目录标明 BM28 无机械极性。原理图在 `P1/PWR1` 接 `CAM_AVDD_2V8`，`PWR2` 接 GND，两个端部电源触点不可互换。实际 FPC 方向、26 个触点逐点网络及防反须用配对图和总装交叉验证。还需冻结传感器 DVDD、电源时序、PWDN 极性以及隐私联锁实测条件。保留 J2 **BLOCKED**。 [相机 ECO-04](../../h02-h03-rd/ECO_AUDIT_MATRIX.csv) [Hirose BM28 无极性说明](https://www.hirose.com/en/product/series/BM28)
- R3/R4 库元数据和 SCH 实例的 `UserDocLink` 仍引用其他触点数的旧目录入口。上面的 CL0673-5025-0-53 为本位号的准确技术来源。

## J3 · J_CHG

- 当前只有逻辑定义 `1=VBUS_5V_USB`、`2=USB_DM`、`3=USB_DP`、`4=GND`。原生 `VBUS_5V_USB` 网络含 J3.1、U12.5、U22.4 和 U22.6，是 U22 限流器之前的外部总线。历史受控 CAD CSV 的 J3.1 为 `VBUS_5V`，已由 Rev E ECO-07 分离为前级 `VBUS_5V_USB` 和后级 `VBUS_5V`。 [Rev E ECO-07](../../h02-reve-h03-bridge/REV_E_NETLIST_AND_ECO_DIFF.md)
- 保留 J3 **BLOCKED**。供应商料号和配对触点图、板边定位和磁体机械防反、接触电流能力、短接及反接工况，以及充电座电流协议和启动/热插拔要求仍需冻结。 [设计输入](../../Inputs/effective_bom.csv)

## 复跑

从仓库根目录执行。工具采用原生 .epro2 记录流、现有 Protel2 解析器及历史 CAD 端子表。

```powershell
$package = 'hardware/evt1-native-eda-20261118'
$r4 = "$package/h03-codex-r4-20261123"
$r3Project = (Get-ChildItem "$package/h03-codex-r3-handoff-20261123/native/*.epro2").FullName
$r4Project = (Get-ChildItem "$r4/native/*.epro2").FullName
python "$r4/connector/audit_pcb1_connectors.py" $r3Project $package
python "$r4/connector/audit_pcb1_connectors.py" $r4Project $package
```

输入见 `h02-native/verify_h02.py`、`h03-v4-dfm-u11-2n2-route/evidence/takeover/independent/board-netlists/M-MAIN-L.net` 和 `kicad/CAD_TERMINALS.csv`。两份 JSON 输出各自标注原生工程 SHA-256、源文档 ID、器件 ID、每脚线组 ID 与网络。

锚点筛查的复跑参数为 `--pcb1-dump <该修订的原生 PCB1 铜数回读 JSON>`。前后两次筛查均使用嘉立创 EDA 专业版 `pcb dump --include-copper` 的项目及文档身份验证回执，对应输入文件的字节指纹和语义指纹记录在各自 JSON。
