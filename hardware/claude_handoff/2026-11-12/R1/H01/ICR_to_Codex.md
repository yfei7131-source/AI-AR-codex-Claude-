# 接口变更/确认请求（硬件 → Codex）。硬件不改任何软件/固件。
| ID | 类型 | 内容 | 阻塞 |
|---|---|---|---|
| ICR-01 | 确认 | 提供 `firmware/main/board.h/.c` 实际 GPIO 表；硬件运行 `tools/check_fw_compat.py <repo>` 输出差异 | GPIO 冻结、PCB |
| ICR-02 | 请求 | 拉低 CAM_PWR_EN 之前：停止 XCLK，SCCB 与 DVP 相关脚置高阻/输出低；上电后延时再初始化传感器 | 相机倒灌（R-D） |
| ICR-03 | 确认 | CAM_PWR_EN 高有效、复位默认关（板上 10k 下拉，GPIO3） | 隐私联锁 |
| ICR-04 | 确认 | 显示驱动是否接受 QSPI + 帧缓存型 microLED 面板（JBD）；协议层对分辨率 640×480 单色的假设 | 光机选型 |
| ICR-05 | 确认 | 调试日志能否改走 USB-Serial-JTAG 以释放 GPIO43/44；能否接受四线 PSRAM（2 MB） | GPIO 预算 |
| ICR-06 | 确认 | 麦克风归属（ESP I2S 直采 / BT 音频 SoC 转发）与 I2S 格式 | 音频架构 |
| ICR-07 | 确认 | VBAT_ADC：GPIO1，分压 1:2，固件换算系数 | 电量显示 |
