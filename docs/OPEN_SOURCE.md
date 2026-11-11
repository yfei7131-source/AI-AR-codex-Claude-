# GitHub 开源复用审查（2026-11-10 核实）

| 项目 | URL | 能复用什么 | 风险/决策 |
|---|---|---|---|
| Brilliant SDK | https://github.com/brilliantlabsAR/brilliant_sdk | Halo/Frame 主机端 BLE、图片、文字、音频、端侧 Lua；官方 BSD 3-Clause | **AR 软件主路径**，不代表本体光学硬件全开放 |
| Halo emulator | https://github.com/brilliantlabsAR/brilliant_sdk/tree/main/python/packages/halo_emulator | 无实机验证 Lua HUD 与按钮逻辑 | **优先验证**；安装方式以当前仓库为准 |
| Drakon AI Glasses | https://github.com/SINRG-Lab/Drakon_AIGlasses | 双镜腿 KiCad PCB、固件、机械结构组织方式 | **自研 PCB/镜架参考**；许可证在具体版本未核实前不可复制文件 |
| Omi Glass DevKit | https://github.com/LyndLabs/Omi-Glass-DevKit | ESP32-S3 / OV2640 PCB Gerber/BOM/CPL | **摄像/控制验证参考**；此参考不含真正 AR 光学显示，公开版次存在未打样说明；许可待审 |
| AI Smart-Glasses PCB V0 | https://github.com/AnasSarkiz/ai-smart-glasses-pcb-v0 | 四层 ESP32-S3、充电、音频、摄像、指示灯布局 | **DFM/布局参考**；官方说明为无显示设计且 PCBA 仍有人工审核门槛；许可待审 |
| xiaozhi-esp32 | https://github.com/78/xiaozhi-esp32 | ESP32-S3 语音链路、唤醒、OPUS、设备控制 | **语音固件候选**；MIT；上游可能更新 ESP-IDF 最低版本，务必固定版本 |
| Visionbridge AI Glasses | https://github.com/nickjizheng/Visionbridge-AI-Glasses | 眼镜 ESP32-S3 摄像+语音固件思路 | **设备固件候选**；当前仓库描述为 MIT，必须确认具体 tag 与依赖许可 |

### 复用原则
- 不能因为仓库可见就假定它具有可商业使用的许可证。
- 不复制第三方板级原理图、Gerber、固件到本包：本包只存链接、工程拆解和原创最小示例。
- 先确认是否真实实机运行、是否已打板、BOM 是否可买、原理图是否有完整审查、是否涉及供应商闭源 NDA。
- 只借鉴已经成熟的子系统；不要从不同工程盲目拼接 PCB 并声称可直接生产。
