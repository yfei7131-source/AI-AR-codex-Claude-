# Codex 执行任务：承接 Claude 硬件 R2 并与 Sprint03 固件集成

**优先级 P0｜目标：交付安全、可验证的 EVT-0 H01/H02/H03 增量；不是直接投板或宣称成品眼镜。**

## 环境与资料
- 仓库：`yfei7131-source/AI-AR-codex-Claude-`
- 当前正在进行的硬件 PR #1：`hardware/h01-h05-v1-kicad`，其中已有 `S3-CARRIER-A` 配置；先检查避免重复。
- Claude 原始文件：`hardware/claude_handoff/2026-11-12/R2/`（R1 仅作参考）。
- 软件权威来源：同一仓库最新 `firmware/`、`protocols/`、`mobile/`、`docs/FEATURES_F01_F22.md`；Claude 附带的软件摘要不是权威源码。

## 需要直接执行
1. 先读取 `review/CLAUDE_R1_R2_AUDIT.md`、`R2/STATE_FOR_NEXT_SESSION.md` 与 `R2/H01/ICR_to_Codex.md`；每项 ICR-01~12 回复 `已存在/接受/调整硬件/阻塞`，指明源文件和证据。区分 DevKitC-1 S3-CARRIER-A 与 Claude EVT-0，不覆盖现有工作。
2. 对 Codex 现有 `gl_board` / 摄像固件执行 GPIO/相机供电/隐私安全联锁集成设计：`privacy_interlock_verified` **保持 false**，直至实体联锁 T11/T12 真实验证。禁止通过 JP2 旁路门禁。修正 R2 T21 测试前提。
3. 完整复核 BLE GATT V1/V2、Wi-Fi JPEG、iPhone CoreBluetooth 及 HUD 位图格式与拟选硬件的兼容，补齐 F01–F22 追踪矩阵；标记 F21 预研。不得声称没有光机/手机时已实测。
4. 指出音频 J7 缺少控制/状态/数据接口并提出可执行硬件变更协议（优先器件选型+真实引脚），无需擅自虚构蓝牙通话已实现。
5. 逐器件审查 BQ24072 TD、电流设定、3V3 欠压、电池/相机 rail，确认封装与相机 FPC；没有规格书的 J4 仅占位，阻止最终版布局。
6. 用实际 KiCad 8 / `kicad-cli` 执行 ERC，修正可修正的电气错误；具备通过条件的部分进行 footprint 关联/PCB layout、运行 DRC。不把 Python 自检视作 ERC。没有 KiCad 时保存源文件并诚实报告待验证。
7. 交付一份真正可应用的代码/工程 PR：变更源码、测试记录、未完成列表、相机隐私 Gate 记录与下一迭代方案。只在自己的工作分支修改，不覆盖软件主干。

## 禁止
- 未经真实联锁验证将 `privacy_interlock_verified` 改 true。
- 把原理图草稿、仅外框 PCB、模拟图像/手机 HUD 声称为可打样/真实 AR。
- 缺少光机规格书就锁死 QSPI FPC、电源和驱动。
- 虚构 KiCad ERC/DRC、系统蓝牙通话与实机拍摄结果。

## 交付格式
`变更文件清单 + ICR-01~12 答复矩阵 + 真实测试/失败日志 + 可编辑 KiCad/固件工程 + commit SHA / PR + 未解决硬件阻断项`。
