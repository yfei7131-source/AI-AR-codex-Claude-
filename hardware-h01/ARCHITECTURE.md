# 系统架构与数据通道

```
[眼镜端：摄像头/麦克风/扬声器/按钮/触控/电池]
                  │ BLE 控制/会话；Wi-Fi JPEG（开发通道，实机待验）
                  ▼
[手机端：设备服务 / 相机与音频 / 隐私和身份 / 任务确认]
                  │ HTTPS（经授权）
                  ▼
[AI 供应商适配器：视觉问答 / OCR翻译 / ASR / LLM / TTS]
                  │ 简短的HUD事件/音频
                  ▼
[AR显示适配器 → 显示控制器 → 微显示+光学系统]
                  └── HALO SDK / 未来自研 AR 显示桥接
```

## 开发分层
- **M0 原型软件**（当前）：本地浏览器 WebCam + HTTP API + HUD 模拟；云端模型可选。
- **M1 AR 开发平台**：Brilliant Halo 端 Lua `frame.*` + 手机端 SDK，经 BLE 显示短消息并接收按键。
- **M2 ESP32-S3 自研设备验证板**：DVP 摄像头、I2S/PDM 音频、蓝牙/Wi-Fi、电源；暂不等于整机 AR 主板。
- **M3 整机显示集成**：经光学/显示供应商明确屏幕接口和驱动要求后，选用可支持该接口的显示处理模块，联调 AR HUD。
- **M4 定制 PCB/镜架**：双镜腿结构、热/重心/电池、处方镜片设计和试制。

2026-11-10 M0 增量：保留 `web/index.html → app/server.py → app/provider.py → app/core.py` 主链路，新增 `app/images.py` 做真实文件解码和像素重编码、清除元数据。浏览器分别征求相机、图片上传和语音服务同意；只在点击时提交当前静态帧。`mode=demo/live`、`simulated`、`provider` 和 `request_id` 使结果来源可核验，Live 失败不会回退 Demo。结果与错误均进入最多3行 HUD；完整答案在手机中枢预览。

并发控制采用服务端隐私 epoch 和 HUD 版本：删除前进入的上传/推理不能恢复被清除状态，任务卡可使旧推理失效；浏览器也丢弃被取消/删除操作的迟到响应。原型保持单用户进程内存，媒体不落盘；`store:false` 不构成云端全部删除保证。具体边界见 `../protocols/HTTP_API.md`。首次真实云质量、摄像头和光学 AR 仍分别验收。

## Sprint02 已落地分层（2026-11-11复核）

- 保留Python与浏览器主架构；新增 `mobile/` Flutter原生手机中枢，系统相机/图库→内存预览→显式上传→同一 `/api/ask`。Android开发通过USB `adb reverse` 使用loopback；未开放无鉴权LAN或CORS。
- `app/provider.py` 可选严格OCR结构，完整原文、双向译文和不确定性独立于短HUD；`/api/requests/cancel` 配合客户端UUID和epoch拒绝迟到结果。上游处理/计费不作撤销保证。
- `POST /api/media/validate` 是完全本地的图片上传验收，不调用供应商。XiaoMi Webcam的浏览器与DirectShow实拍链路已单独通过；图片只在忽略的私有目录。真实AI仍按用户本轮不提供Key的约定待验。
- `firmware/` 为ESP-IDF v5.4.3工程：按官方S3-EYE原理图建立可选profile，默认未选板；Sprint02提供8byte控制与20byte状态。Sprint03增量见下节；所有profile未通过物理灯审核前继续拒绝采集。
- `HudDisplayAdapter` 将手机预览与光学投递分离。`app/hud_bitmap.py` 支持真实中文256×256栅格化；当前固件bitmap sink只接受逐行MSB-first的1bpp，256×256为8192B。未配置/未审核sink拒绝显示，不能将像素生成当成光学AR通过。
- 构建工具链在项目外ASCII目录，源码继续留在原目录；SDK、二进制、个人媒体和缓存不纳入Git。固件构建metadata与实际源文件hash关联；每项功能分代码、自动测试、真实环境三层追踪。

本轮具体命令和证据以 [SPRINT_02.md](SPRINT_02.md)、[MOBILE_APP.md](MOBILE_APP.md)、[FIRMWARE_SPRINT02.md](FIRMWARE_SPRINT02.md) 为准。真实AR光学显示、处方镜片、佩戴与PCB保持V1 P0验收门槛。

## Sprint03：Windows+iPhone与设备媒体（2026-11-11）

现有代码路径没有替换，增加两条用途独立的通道：

```text
iPhone Safari（Flutter Web，摄像/预览/HUD/ASR/TTS能力检测）
  → 同源HTTPS + 内存Bearer → app.phone_gateway
  → 随机loopback端口 → 既有 app.server / images / provider / core

未来已安装的iOS App（CoreBluetooth / URLSession）
  ↔ 加密BLE：v1控制/状态；v2临时会话/元数据
  ↔ 设备开发Wi-Fi AP：固定IP HTTP + 临时Bearer / JPEG分块
  → 内存图片，独立用户同意后才可进入AI路径
```

Web页面和API同源；网关仅代理固定loopback后端，剥离敏感头，不开放CORS、不转发任意URL。API必须TLS/Bearer、限定Host/Origin；会话8小时，凭据只在被忽略的本机配对文件和浏览器内存。CA与私钥不进入Web目录；用户手动信任项目CA，程序不改信任库/防火墙。底层API仍单用户进程内存，此网关不是多租户服务。详见 [WINDOWS_IPHONE_GATEWAY.md](WINDOWS_IPHONE_GATEWAY.md)。

Web媒体桥在用户操作后启用相机，限时等待并释放晚到流；后台/离页/撤回停止。截图先留内存，先可走纯本地validate，再由用户决定是否AI提交。Flutter加载本地CanvasKit与OFL中文字体，避免界面启动依赖外部字体CDN；语音服务仍可能处理外部音频，必须另行同意。Safari不支持此BLE控制入口，不能用Web页面冒充原生GATT连接。

iOS原生桥已注入适配factory：串行写入、通知、超时、断连/后台撤销和有界URLSession取帧；当前只提供API，扫描/选择/连接UI尚缺。原生AI API仍为原loopback开发配置，iPhone原生到Windows网关的配置/凭据入口需后续补齐，不假称已可整机使用。Codemagic配置静态通过但云任务/Swift编译未执行；无签名Runner.app不能直接安装iPhone。见 [IOS_CLOUD_BUILD.md](IOS_CLOUD_BUILD.md)。

设备媒体协议保留v1，新增a004/a005加密特征，响应以实际处理的request_id关联，不能把ATT ACK当完成。开发AP默认关闭；显式启用构建后还须物理长按30秒窗口，临时SSID/WPA2/token与最长120秒会话，单帧≤2MiB、15秒寿命、16KiB块、SHA256/请求关联。取消、撤销、断连、到期清理RAM；可能有最长2秒在途块，不能承诺物理即时停止。未审核相机仍锁定，不能生成假JPEG。默认/EYE/AP启用三配置实际编译、38项主机测试，不等于已建立真实AP或传图。AP镜像另需1500K factory分区，无OTA承诺。详见 [协议](../protocols/DEVICE_MEDIA_V1.md)、[固件报告](FIRMWARE_SPRINT03.md)。

Android平台继续使用原开发链路；中文光学HUD、显示控制器、镜片/佩戴与PCB仍并行推进且为首版必需。软件预览、像素栅格化、协议与交叉编译均不能替代这些验收。

## 关键决策（持续适用）
1. 不做眼镜端大模型推理；在功耗受限的设备端采集、压缩和控制；推理主要在手机/云端。
2. 不采用“ESP32-S3 直接驱动任意 MicroLED 波导”作为假定事实；先确认显示器接口、光学引擎和相应驱动。
3. BLE 可用于控制/HUD 小数据和低码率消息，但实时原始视频需评估 Wi-Fi 或采用眼镜端压缩和事件触发抓拍；带宽与续航必须实测。
4. F21 空间锚定是 R，首版不是头部六自由度 SLAM。
5. “可调近视”工程上先指用户处方镜片的可更换/验配方案，自动变焦不纳入 V1。
6. AI 任务必须要求用户确认。APP 和云后台未来都需要用户隔离、加密及真实数据删除流程。

## V1 端到端延迟预算（工程目标，尚未实测）
- 触发→抓拍: 300ms；设备→手机: 500ms；网络+模型：目标 2-5s；HUD 更新: 300ms；这是待验证的预算而非实测性能。
- 优先短句 HUD，翻译字幕和任务卡按照安全视野约束显示。
