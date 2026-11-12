# 接口变更/确认请求（硬件 → Codex）R2。硬件不改任何软件/固件。
依据：`firmware/main/board.c/.h` 节选（sha256 见 `H02/evt0_core/fw_compat_report.md`）+ 交接摘要。完整源码未读，条目可能已被源码覆盖，请 Codex 逐条标注「已有/接受/拒绝」。

| ID | 类型 | 内容 | 阻塞 | R2 状态 |
|---|---|---|---|---|
| ICR-01 | 确认 | board.c EYE v2.2 profile 的按键+相机 15 个 GPIO 与硬件 pinmap 逐脚一致 | – | **已核对（节选）** |
| ICR-02 | 请求 | 拉低 CAM_PWR_EN 前：停 XCLK，SCCB 与 DVP 脚置高阻/输出低；上电后延时再初始化传感器 | 相机倒灌 | 开放 |
| ICR-03 | 确认 | CAM_PWR_EN 高有效、复位默认关（GPIO3，板上 10k 下拉） | 隐私联锁 | 开放 |
| ICR-04 | 确认 | `display_adapter.h` 的物理层假设：分辨率、位深、帧格式、刷新方式；能否接 QSPI+片上帧缓存 microLED | 光机选型 | 开放 |
| ICR-05 | 请求 | 控制台改 USB-Serial-JTAG，释放 GPIO43/44 作常电 I2C；确认是否依赖八线 PSRAM | GPIO 预算 | 开放 |
| ICR-06 | 确认 | AI 语音麦克风归属（ESP I2S 直采 GPIO2/41/42 或音频 SoC 转发）与格式 | 音频架构 | 开放 |
| ICR-07 | 确认 | VBAT_ADC：GPIO1（ADC1_CH0），分压 1:2 | 电量 | 开放 |
| ICR-08 | **请求** | 新增自研板 profile（如 `CONFIG_GL_BOARD_AIAR_EVT0`），相机/按键脚同 EYE；`gl_board` 增加字段：`cam_pwr_en=3`、`vbat_adc=1`、`mic_sck=41 / mic_ws=42 / mic_sd=2`、`disp_cs=21 / disp_clk=47 / disp_d[4]={38,39,40,48} / disp_rst=14 / disp_pwr_en=45`、`bt_aud_en=46`（字段名与 `tools/check_fw_compat.py` 的 `FIELD_NET` 对应，改名请告知）。显示相关脚在光机规格书到手前可能变更 | 自研板相机上电、全部外设 | **新增** |
| ICR-09 | 请求 | `privacy_interlock_verified` 仅在硬件提交 H05 T11/T12 实测记录后对自研板 profile 置 true；EYE 参考板保持 false | 拍摄门禁 | **新增** |
| ICR-10 | 确认 | 开发 Wi-Fi AP 的发射功率上限与 JPEG 传输期间的峰值电流预期；能否提供降功率配置供 LDO 版 EVT-0 使用 | 3V3 跌落 | **新增** |
| ICR-11 | 确认 | F03 通话：iPhone 侧同时存在 BLE 外设与经典蓝牙音频设备的配对/重连流程；ESP 经 BLE 转发对音频 SoC 的控制（接听/挂断/音量/电量）所需命令集 | 音频 SoC 选型 | **新增** |
| ICR-12 | 确认 | 眼镜端 HUD 位图来源：手机栅格化后经 BLE 还是 Wi-Fi 下发；单帧字节数与更新频率 | 显示带宽/功耗 | **新增** |
