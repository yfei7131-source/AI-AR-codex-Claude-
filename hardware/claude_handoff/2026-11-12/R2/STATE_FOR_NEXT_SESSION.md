# STATE_FOR_NEXT_SESSION — 2026-11-12 硬件 R2 已交付

## 本轮实际输入
- `Claude_硬件_R1___R2_续话包.zip`（R1 基线）
- `Codex_软件与固件交接包.zip` = 打包工具 + 接口摘要 + `board.c/.h` 节选。**完整软件源码仍未读到**；GitHub 从会话内访问不到；无 KiCad。

## 本轮交付：`AIAR_HW_R2_20261112.zip`
- H02：U3 15 脚改为 TD、R6=0R 接 GND、TP8=CHG_ISET；新增 R30/R31(DNP)、JP2+R32；重生成 `.kicad_sch/.kicad_sym/netlist/BOM/pinmap`。87 器件、64 网络、生成器自检 0 错误（**不是 KiCad ERC**）。
- tools：`check_fw_compat.py` 重写，可解析结构体位置初始化；对节选运行 exit=2：相机+按键 15/15 一致，14 个硬件网络固件无字段，仓库不完整。
- H01：架构 R2、`HW_SW_COMPAT_MATRIX.csv`、`F01_F22_trace.csv`（骨架）、ICR-01…12、功耗表。
- H03：布局规划表（未放置封装）。H05：测试计划更新，全部 NOT RUN（T01 为 PARTIAL）。
- 详见 `CHANGELOG_R1_to_R2.md`、`VERIFICATION_R2.json`。

## 状态
H01 草稿未冻结｜H02 R2 待真实 ERC｜H03 外框+规划｜H04 需求草稿（未动）｜H05 计划。KiCad ERC/DRC/实机 = NOT RUN。

## 已确定
- 保持 BQ24072RGTR；无运输模式（EVT-0 用 JP1）。BQ24075/79 不是直接替换件。
- 相机/按键 GPIO 与固件 EYE v2.2 参考 profile 一致；`privacy_interlock_verified=false`。
- 未改固件时相机不上电 → 台架用 JP2；正式方案等 ICR-08。
- iPhone 无法经经典蓝牙数据通道控制非 MFi 设备 → 音频 SoC 须独立完成 HFP/A2DP，控制经 ESP BLE 转发。

## 未解风险
1. 完整源码未读：BLE/Wi-Fi/iPhone/显示适配只按摘要核对；F01–F22 定义缺失。
2. AR 光机规格书缺失，J4 不能冻结。
3. GPIO 已满；R3 方案依赖 ICR-05/08 答复。
4. 3V3 LDO 低电量跌落；EVT-1 buck-boost 未选。
5. 经典蓝牙音频 SoC、电池、IMU/触摸未选型。
6. K_ISET/K_ILIM、LDO 压差等数值未在线复核；相机 FPC 序、SOT-23 脚位须对实购料核对。

## 下一轮前三项
1. 用户在 Windows 运行 `双击生成Claude软件资料包.cmd`，上传生成的 `OUTPUT/AIAR_Codex_Software_Context_*.zip` → 运行 `tools/check_fw_compat.py <解压目录>`，补全 F01–F22 映射和 BLE/Wi-Fi/显示核对。
2. 用户本地 KiCad 8 打开 `H02/evt0_core/evt0_core.kicad_pro` 跑 ERC，回传报告 → 修正后做 H03 封装导入与布局。
3. 把 `H01/ICR_to_Codex.md` 交给 Codex，取回 ICR-05/08 答复 → 出 R3 GPIO 重排；同时索取 JBD 光机规格书。

## 分工
Claude 硬件 H01–H05；Codex 软件/固件（只读）；用户测试与 GitHub 同步。未推送任何提交。
