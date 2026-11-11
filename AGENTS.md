# Codex 开发指令 — AI/AR Glasses V1

## 项目目标（不许重新收缩功能）
开发「L1 信息显示 + L2 视觉 AI 增强现实」眼镜 V1，保持 `docs/FEATURES_F01_F22.md` 的 16 P0、5 P1、1 预研，F15/F17/F19/F20/F22 属于首代 P0。禁用“先做无显示 AI 眼镜作为最终版本”的建议。可以阶段性用无屏开发板验证，但最终首版包含 AR 显示。

## 当前现状
已有浏览器 AR HUD/手机中枢和 localhost API；Sprint02加入 `mobile/` Flutter工程、`firmware/` ESP-IDF工程、BLE/显示接口及20图验收工具。Sprint03继续同一工程：Flutter Web媒体/语音、Windows同源TLS配对网关、iOS CoreBluetooth与Wi-Fi媒体桥、Codemagic无签名任务、固件BLE v2会话和有界JPEG通道。当前成果与边界以 `docs/SPRINT_03.md` 为准，Sprint01/02证据保留为历史。

用户环境为Windows+iPhone，无Mac/Android、不购买Apple会员；优先可测试的Web与无签名云编译，不把unsigned产物写成可安装iPhone。没有Codemagic账号/远程仓库连接，Swift与云构建未执行。XiaoMi Webcam本地链路在Sprint02已验；本轮没有iPhone实测。用户暂不提供API Key，不要反复询问；测试照片未经确认不得传外部服务。真实AI、BLE/Wi-Fi硬件、光学AR、镜片/机械及PCB仍待验，不可把构建/测试桩当实机成功。

## 执行优先级
1. 阅读 README.md、docs/FEATURES_F01_F22.md、docs/ARCHITECTURE.md、docs/SPRINT_01.md。
2. 先运行 `python -m unittest discover -s tests -v`，确认行为可重现。
3. 完善视觉 AI 数据契约：image/jpeg/png、mode、HUD 结果/超时/错误；补测试。
4. 为真实手机 App 建立 Flutter 项目，对接已有 API，不得把密钥放 App；加 BLE 设备接口适配层。
5. 对接 Brilliant Halo SDK，先在官方 emulator 测试 Lua 端文字与事件；中文采用栅格化，不直接绘制多字节 UTF-8。
6. 用 ESP32-S3 官方开发板 + OV2640 摄像头 + I2S/PDM 音频验证采集、功耗和链路，固件从 `78/xiaozhi-esp32`/`Visionbridge-AI-Glasses` 选择可兼容分支，保留上游许可证和依赖。
7. 完成元件选型、原理图、电源安全、Pin Map、KiCad ERC/DRC 后方可设计/导出 Gerber。AR 显示在独立光学驱动子系统，不得声称 ESP32-S3 DVP = MIPI DSI。

## 强制工程红线
- 物理摄像指示灯必须和摄像头供电/实际采集联动，不能仅靠 App 文案模拟。
- 任何外部执行动作必须用户显式确认；当前已确认任务仍标识 `confirmed_local_only`。
- 不得提交云 API Key、个人图片、音频数据和日志；默认 localhost、最小留存、明确删除范围。
- 无法确认第三方 LICENSE，禁止复制工程文件或纳入商业产品；只能阅读参考。
- 必须提供测试输出和可复现运行步骤，不能把未测试代码写成“已完成”。
- 眼镜鼻梁、耳后、太阳穴配重、近视/散光镜片适配必须在机械审查中列为 P0。

## 后续开发（直接执行已授权且可验证的部分）
复现Sprint03测试和构建，保留22项冻结功能与三层状态。优先iPhone Safari手动信任后的摄像/停止/语音实测、Codemagic实际Swift编译、原生BLE扫描选择UI、已选板物理灯与相机、App↔BLE/Wi-Fi及中文bitmap→受支持AR设备链路。无硬件/密钥时继续可编译/可测试适配，不虚构成功。不开放无鉴权LAN API，不擅改系统信任/防火墙，不解锁未审核板级采集，不把ESP32-S3 DVP当MIPI显示输出。后续有服务端Key后再执行20图真实验收与人工核对。
