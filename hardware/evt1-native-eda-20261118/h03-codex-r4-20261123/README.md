# 智元跃动 AI/AR 智能眼镜 V1.0 · EVT-1 H03 R4

**NOT FOR FAB**。在 R3 独立分支上延续真实双目透明 AR、40 g 整机目标以及 AVDD、相机隐私联锁和电源保护。R3 四个文件已从 GitHub 逐字节回读，原生档案与交接包 SHA-256 一致。继承提交 77f21203840ca2b25d5d30028f96dcfd05b2bd35。 [R3 Draft PR #51](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/51) · [远端 blob 回读](verification/r3_remote_verify.json)

## 原生整改

在嘉立创 EDA 专业版 V4.1.97 导入 R3 隔离副本。PCB1 底层 e938（持久 ID 3ca748787f4325f4）仅接触同一接点的 e937、3.5 mil 地线和 GND 盲孔。原生铜形回读确认，悬空端未连接焊盘、过孔或铺铜。按圆端铜边计算，线宽 2 mil 时 e938 与 BB_FB 过孔 e85 相距 5.968509 mil，加宽至 4 mil 后只剩 4.968509 mil，低于设置约 5.98 mil。R4 移除这一段支线，保留上游铜和两个过孔。 [铜几何前后图](verification/pcb1-e938-before-after.svg) · [几何验算](verification/pcb1-spur-geometry.json) · [操作回执](verification/track-delete.json)

保存并关闭重载 PCB1 后，回读 802 段线。R2 → R3 的 7 段 GND 从 1.9685 mil 加宽到 4 mil，R4 全部保留。472 段 3 mil 维持原状。R3 → R4 的 1,451 个文档正文比对只出现上述线段移除和 PCB1 自动 LINE 占位计数 2 → 3。三板板框、层定义、规则、焊盘网络、元件及 21 页原理图记录一致。R4 导出后用新 UUID 独立重导入并另存，验证工程正文完全一致。 [可编辑 .epro2](native/EVT1-H03-CODEX-R4-NOT-FOR-FAB.epro2) · [重载](verification/pcb1-reload.json) · [重导入](verification/restore-r4.json) · [档案比对](verification/archive-and-rule-parity.json)

R4 档案 SHA-256 为 178f0098acb0fa4194578f01674a84fb26a0d14e27b77b35937b6c27607ea7da。

## 原生严格检查

| 板 | 前 → 后未连通 | 前 → 后网表差异 | 前 → 后 ERC 致命项 |
| --- | ---: | ---: | ---: |
| PCB1 / 主板 | 355 → 355 | 1 → 1 | 4 → 4 |
| PCB2 / 桥板 | 237 → 237 | 0 → 0 | 0 → 0 |
| PCB3 / 右板 | 134 → 134 | 0 → 0 | 2 → 2 |

三板 DRC 违规对象和消息逐项一致，原生日志中间距、短路项均为 0。合计 726 处未连通，三板严格 DRC 均返回失败。6 项 ERC 致命项均为 MISSFOOTPRINT。独立重导入的 PCB1 返回同一组 356 项。完整前后 ERC、DRC 和回执在 verification 目录。 [PCB1 DRC](verification/pcb1-after.json) · [PCB2 DRC](verification/pcb2-after.json) · [PCB3 DRC](verification/pcb3-after.json) · [重导入 DRC](verification/pcb1-restore.json)

## 专项复核

- **141 颗盲孔**（61/40/40）与新采集的三板铜数据逐孔匹配。复用 V4 脚本分别检查孔壁到板边、铜盘到板边、孔壁间距、铜盘间距和环宽。几何筛查三板均无检出违规。最小孔壁/铜盘到板边为 0.442633/0.3664 mm。 [逐孔证据](dfm/) · [嘉立创 HDI 量测规则](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)
- PCB1 对 J2/J3 完成 30 触点复核。J3.1 保持限流器上游 VBUS_5V_USB。若 J2 沿用原锚点，U16、U21 各有 10 个焊盘中心落入正式插座本体投影。 [连接器核查](connector/PCB1_CONNECTOR_AUDIT.md)
- PCB3 对 U11 核查 95 球，52 个有网、43 个显式 NC。22 个有网球检测到同网顶层铜接触。36 个内圈有网球中 25 个不满足最小工艺盘和 6 mil 规则下的居中微盲孔间距。 [95 球矩阵](u11/r3-u11-95ball-native.csv) · [原厂与制造约束](u11/README.md)
- PCB2 完成 8 颗电容和 FPGA 线束联合回读。4.60 × 25.00 mm 桥板上，C8–C11 在筛查窗口内无可用摆位，C5/C12 与现有铜相连，C31/C32 的候选区域重叠且依赖 U6 选装状态。Icarus 实跑显示 RAW、主控帧恢复、主控线协议和 11 个用户态关断用例，四组均通过。 [桥板证据](bridge/)

## 复跑

从本目录运行 python3 -B verify_r4.py。几何单元测试使用 python3 -B -m unittest discover -p test_pcb1_spur.py -v，V4 逐孔复核使用 python3 -B replay_v4_dfm.py --out-dir <新目录>。本机原生重导入另存可通过 verify_r4.py 的 --r3-local-export 和 --r4-restore-export 一并复核。 [剩余阻断](BLOCKED.md)
