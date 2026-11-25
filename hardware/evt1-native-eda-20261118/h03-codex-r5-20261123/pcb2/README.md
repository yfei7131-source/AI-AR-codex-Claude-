# H03 R5 桥板走线与放置验证

**NOT FOR FAB**。单位均为 mil，采用 EasyEDA 原生 Y 向上坐标。输入为 PR #52 的 R4 原生工程、PCB2 铜箔回读及严格 DRC。铜箔筛查对账全部 397 段原生归档走线、47 颗过孔与焊盘外形。两段极短 R4 底层地线只出现在原生归档中，仍纳入分析。过孔使用归档的实际层跨。原生回读未报告曲线、顶/底层区域铜箔或覆铜。本次候选未模拟内电层、电源完整性或阻抗。

## 可实施候选

- FPGA 1V8 I/O 去耦 C16 和 1V2 CORE 去耦 C28 的现有地铜簇在跨层铜连接图中相异。C16.2 到 C28.2 可在顶层使用 3.6 mil 线宽，折线路径为 (44.7,468.1) → (44.7,466.2) → (24.6,446.1) → (24.6,440.4)，总长 36.0257 mil。对异网焊盘的保守最小距离为 6.2964 mil，铜到板边为 22.8 mil。该增量回流连接仍需实际原生 DRC、保存重载和铜连通验证。 [筛查记录](screen-3p6.json)
- 10 段接触 C5/C10/C31/C32 的顶层 GND 路由可沿原中心线按 3 → 4 mil 做 DFM 调整。候选保留原端点、网络和层。另有 4 段底层 CDONE/VSYNC 在几何上可加宽，暂留原宽等待叠层与信号回流验证。 [筛查记录](width-screen.json)
- C5.2 到 C10.2 和 C8.1 到 C12.1 已有完全相同端点的原生铜线。原生 DRC 列出的开路对象不是这些线段不存在的证据。新增同坐标铜会产生重复线。结合完整归档和真实铜簇，可区分同网其他断点。

## 继续阻断的工作

对 C5/C9/C11/C31 的 11 个当前布置下 VSYS/GND 同层补线组合执行了有界网格和几何检查。现有铜箔及元件保持在原位时，没有可用的候选。原生 6 mil 间距和项目电源及敏感线的较大间距均保留。 [网格筛查](grid-screen.json)

C11 的实际外形为 EIA 0201。其原焊盘均未触及同网铜。底层近候选 (93,364) / 180° 可将 C11.1 到实际目标 U13.4 的直线间距从 639.25 mil 缩至 125.51 mil。在该假设布置下，C11.2 到 C20.2 可用两段 3.6 mil 底层线，长 58.20 mil。4 个候选锚点的 16 个 VSYS 供电组合未找到同层路径。装配方面，候选 C11 至最近 U3 XSON6 的标称本体距为 20.10 mil，至 C22 0402 为 24.13 mil。XSON 无外伸引脚，公开表未单列该封装，保守用 QFN 40 mil 做筛查时 U3/U5 处不满足。既有方案暂保留，后续需要供应商确认 XSON 装配窗，联合解决铜箔和回流。 [放置候选](placement-screen.json) · [连通筛查](placement-route-screen.json) · [测量距离](c11-assembly.json) · [嘉立创封装装配间距](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components) · [Nexperia SOT1202 原厂封装](https://www.nexperia.com/packages/SOT1202.html)

## 复跑

将下方的 package 替换为仓库中 hardware/evt1-native-eda-20261118 的路径，命令从本目录运行。此目录输出只提供静态工程验证，原生执行证据见 R5 的 EDA 日志。

```text
python -B plan_bridge_r5.py package screen-3p6.json --width 3.6
python -B width_bridge_r5.py package width-screen.json
python -B grid_bridge_r5.py package grid-screen.json
python -B placement_bridge_r5.py package placement-screen.json
python -B route_placement_r5.py package placement-screen.json placement-route-screen.json
python -B c11_ground_r5.py package placement-screen.json c11-ground.json
python -B c11_assembly_r5.py package/h03-codex-r4-20261123/verification/pcb2-restore-copper.json c11-assembly.json
```
