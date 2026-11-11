# Sprint02 实现与验证报告

执行：2026-11-10，2026-11-11继续复核。保留22项冻结需求（16 P0、5 P1、1 R）与既有Python/浏览器架构。真实AR光学显示、镜片适配、舒适佩戴和最终PCB保持首代必需门槛。

## A · 真实接口与本地摄像

用户明确本轮不提供API Key，继续所有不依赖密钥的任务；随后明确授权XiaoMi Webcam拍摄非敏感内容，禁止向外部服务上传。服务端环境检查只记录配置是否存在，不打印凭据。进程/用户/系统范围均未检测到Key；保留完整OpenAI适配、模型配置模板和真实模式失败不降级行为。

代码新增：严格结构化OCR（独立原文/中英双向译文/不确定性）、客户端请求UUID取消、迟到结果保护、32在途请求上限、纯本地 `/api/media/validate`、浏览器15秒相机打开超时及晚到轨道释放。旧API与text响应兼容；text翻译目标语言被忽略的问题也已修复。

| 场景 | 实际结果 | 证据与限制 |
|---|---|---|
| 浏览器真实摄像 | XiaoMi Webcam取景→JPEG采集→预览→localhost上传校验通过，640×480；随后关闭相机流 | 私有 `artifacts/private/camera/browser-camera-summary.json`、`browser-xiaomi-capture.jpg`；`cloud_sent:false`、非AI验收 |
| 系统视频接口 | DirectShow明确选择XiaoMi Webcam→JPEG→localhost校验通过，1920×1080 | 私有camera目录中的capture JSON/JPEG；首轮输出路径兼容问题后改为ASCII相对输出成功，无音频采集 |
| 未同意上传 | 实际浏览器拒绝提交，显示本地验证失败；勾选后才成功 | 真实UI操作及Node/API回归；照片没有发送供应商 |
| 真AI成功与质量 | **未运行** | 用户本轮无Key；不能以Demo、HTTP桩或本地图片校验代替 |
| 10视觉+10OCR | 合成图和预期原文已准备；OCR含5英→中、5中→英；实际缺Key批量报告20 blocked、0 success | `tools/acceptance/manifest.json` 可跟踪；生成图/详细报告仅在私有忽略目录；人工评分unknown，准确率null |
| 失败/超时/断网/取消 | 分类代码与测试通过；localhost实际取消旧结果通过自动集成测试 | AI错误/超时/断网为明确测试注入，不能记为真实云端或物理断网实测；本地取消不保证撤销云端费用 |

本地拍照复现（先启动本地服务，使用自行安装且支持DirectShow的FFmpeg；不得拍摄未获准内容）：

```powershell
python tools/capture_local.py --ffmpeg C:/codex-tools/camera-deps/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v9.0.2.exe --device "XiaoMi Webcam" --consent-local --base-url http://127.0.0.1:8765
```

该CLI只连loopback `/api/media/validate`，输出和照片在 `artifacts/private/camera/`；无需Key，不调用AI。当前机器可选辅助工具imageio-ffmpeg 0.8.1装于项目外，不是项目运行的强制依赖。真实API工具和人工评分步骤见 [AI_ACCEPTANCE_SPRINT02.md](AI_ACCEPTANCE_SPRINT02.md)。

## B · 手机原生工程

`mobile/` 是真实 `flutter create` 生成的Android/iOS/Web项目，含系统相机/图库入口、独立同意、内存预览、API问答、双向OCR原文译文、HUD预览、取消/删除与真实设备状态边界。没有云Key，没有假BLE连接；控制与20byte状态编解码对齐固件协议。

Flutter静态分析无问题，18项API/controller/codec/HUD/widget测试通过。**Android arm64调试APK与Web均实际构建成功**；APK在 `mobile/build/app/outputs/flutter-apk/app-debug.apk`，二进制不提交Git。历史构建曾因Gradle发行包超时、Java TLS下载和不完整缓存索引失败，最终从相同官方源预取并校验依赖、限定任务缓存和代理后构建通过；保留失败证据，不将旧失败或Web构建冒充Android通过。工具来源、源码/产物hash与完整命令见 [MOBILE_APP.md](MOBILE_APP.md)。Android通过USB adb reverse接原localhost API；iOS平台文件保留，但Windows没有进行iOS构建。手机安装、真机相机权限与BLE配对仍需独立验收。

## C · ESP32-S3 与AR适配

ESP-IDF v5.4.3工程已实现相机适配、物理按钮、设备状态、NimBLE加密控制、数字错误环日志与1bpp显示适配；默认未选板，S3-EYE v2.2 GPIO仅来自官方原理图。两个profile均 `privacy_interlock_verified=false`，未审核物理指示联动前不允许启动相机。不配置音频GPIO、不虚构电量、不声称JPEG已通过BLE传输。

- Host C：**20/20通过**，含协议边界、撤销/去重/旧epoch、错误环日志、未配置显示拒绝。
- ESP32-S3默认：实际构建成功，591168字节，SHA256 `802ece34e1a226ac72064a98ecf2ca6f999d23ae5aabaefbbf78a7dbe7f01df6`。
- S3-EYE v2.2：实际构建成功，599840字节，SHA256 `24df911794730442e81a283cfe5b56477481f01833fc8abd5e5bd77b9b41e85b`。
- 2026-11-11复算：两份bin和各18个源码hash均匹配；未烧录、未实机验证。编译器/依赖许可及完整重建命令见 [FIRMWARE_SPRINT02.md](FIRMWARE_SPRINT02.md) 和 [firmware/README](../firmware/README.md)。
- 中文HUD：`app/hud_bitmap.py` 真正生成256×256中文像素，1bpp为8192B，gray8为65536B；**14/14测试通过**，固定非敏感样张已目视核验。未审核/未配置sink拒绝投递；没有Halo emulator、BLE显示投递或光学AR通过证据。详见 [AR_DISPLAY_ADAPTER.md](AR_DISPLAY_ADAPTER.md)。

## D · 质量与版本管理

Git已初始化，基线提交 `4876399`、`8dc1e76` 保留Sprint01。SDK、密钥、本地图片/回答、构建缓存、APK/bin均忽略；系统字体未复制入项目。`tools/check_repository.py` 检查Git实际暂存内容，不能只检查工作区后遗漏已暂存密钥。全部功能的代码/测试/真实环境三层状态见 [TRACEABILITY.md](TRACEABILITY.md)，整机统计为0完成、12部分、10未实现，F11由无代码升级为部分。

最终全量Python：**90/90通过**，其中1个入口包含 **25/25 Node交互测试**，二者不能简单相加为115项独立Python测试。Flutter18项与固件20项另属不同运行时；原始输出仅用于本地复核，最终摘要随源码记录。

```powershell
python -m unittest discover -s tests -v
node --test tests/web_client.test.cjs
python firmware/tests/run_host.py --cc C:/codex-tools/glasses-host/ziglang/zig.exe
python tools/check_repository.py
```

构建、测试与源码hash需要同时匹配；没有实际输出时不得升级为通过。旧Python进程可能读取新静态页面但仍运行旧模块，复现时检查health `api_version=0.3` 并重启对应服务。

## 剩余缺陷与下一阶段阻塞

1. 真实视觉/OCR的20图模型回答与人工评分待后续服务端Key；当前不阻断其他开发，不再重复询问。
2. Android安装/权限、iOS构建、App↔BLE真实扫描/配对/GATT、ESP32相机与物理灯、电池/音频实测需要对应设备。当前App设备适配默认disconnected，固件Just Works开发配对没有MITM/所有权策略，不能当产品安全验收。
3. JPEG无线媒体尚未实现；固件有摄像适配但所有profile仍锁定。先审核具体板卡/指示联动，再开发媒体通道，不能为演示绕过门控。
4. 中文bitmap与1bpp尺寸已对齐；位序/极性/旋转和传输格式还需真实显示驱动确认。光学AR、镜片、佩戴及PCB门槛均未降级。
5. F05会话上下文、F07 AI整理、F08外部实际执行、OTA、离线同步及其他P1项按矩阵继续推进。任务仍 `confirmed_local_only`。
