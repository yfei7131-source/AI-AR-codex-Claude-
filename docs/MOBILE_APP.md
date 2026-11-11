# Flutter 手机中枢 — Sprint 02

此页保留Sprint02历史构建与工具安装证据。当前Windows+iPhone开发入口、iOS原生接口和平台限制见 [IPHONE_WEB.md](IPHONE_WEB.md)、[WINDOWS_IPHONE_GATEWAY.md](WINDOWS_IPHONE_GATEWAY.md)、[IOS_CLOUD_BUILD.md](IOS_CLOUD_BUILD.md) 及 [Sprint03报告](SPRINT_03.md)。本页“尚未实现”的BLE/Web/iOS描述仅代表Sprint02时点，当前三层状态以需求矩阵为准。

2026-11-11。沿用 `app/server.py` 的 localhost HTTP API，不向 App、固件或 Git 传递云端密钥。工程位于 `mobile/`，Android 优先，保留 iOS 和 Web 平台文件。构建不能替代手机实测。

## 本次软件路径

系统相机 / 手动选择图片 → 手机内存预览 → 用户单独同意提交 → `/api/ask` → 供应商来源校验 → 手机 HUD 预览。默认显式 DEMO；选择 live 后，服务未配置密钥、鉴权失败、超时或响应来源不符都会报错，不回退 DEMO。

`kind=translate` 使用 `output_format=ocr`，显示独立 `original_text` 和 `translated_text`，原文语言支持自动/英文/简体中文，译文语言支持英文/简体中文；不确定标记与原文保留供人工核对。未得到符合结构的 OCR 响应时拒绝当作 OCR 成功。没有密钥时只能验收本地软件契约，不能验收真实 OCR 质量。

`HubController` 给请求分配 UUID，同时在本地维护操作版本。取消、模式切换、换图和删除使迟到结果失效；取消还调用 `/api/requests/cancel`，但不保证撤销已发送到供应商的处理或费用。不存在后台自动拍摄或自动上传。

`GlassesDeviceAdapter` 与 `HudDisplayAdapter` 分离设备控制和显示投递。当前默认 `UnconfiguredDeviceAdapter` 如实返回 disconnected；`PhonePreviewHudAdapter` 仅手机预览。`UnconfiguredOpticalHudAdapter` 明确拒绝发送，不能把 UI 文字当成光学 AR 或 BLE 发送成功。中文光学显示需要后续栅格化与官方 SDK/设备验证。

## 运行

先在电脑上从项目根目录启动现有 Python 服务：

```powershell
python -m app.server
```

Android 模拟器或 USB 真机启用开发者调试后：

```powershell
adb devices
adb reverse tcp:8765 tcp:8765
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8765
```

App 与服务默认都只访问 loopback。不要把 API 改为 `10.0.2.2` 或 LAN IP 来绕过服务端 Host/来源限制；使用 `adb reverse`。手机断开 USB/adb 后该通道失效。`ready` 只是服务本地配置状态，不证明供应商鉴权或设备连接通过。

```powershell
flutter analyze
flutter test
flutter build apk --debug --target-platform android-arm64
flutter build web
```

iOS 平台源码保留。需要 macOS、Xcode、签名、相机权限与手机到本地 API 的受控网络通道后单独验证；Windows 不能构建 iOS。Web 构建验证只证明 Dart/Flutter 前端可编译，当前本地服务没有为不同端口的 Flutter Web 提供 CORS，因此不能据此称 Web 原生相机或跨源 API 联调已通过。

## 隐私与权限

- App 勾选同意后才调用系统相机/图库，平台权限由系统与官方 `image_picker` 处理；不声明无需求的麦克风、位置或蓝牙权限。
- 图片在点击识别时才提交；使用 `requestFullMetadata:false`，服务端继续做真实像素解码和元数据清理。
- 相机返回的本次缓存文件读取后尝试立即删除；不删除图库原图。系统相机应用或系统图库独立生成的副本不由此 App 控制。
- 删除清除 App 当前内存图、输入、同意标记以及服务进程内笔记/任务/HUD；不声称云端或系统图库一并删除。
- Android 返回前进程被系统回收时，不自动恢复并上传 `retrieveLostData`，用户需重新选图/授权。待补专门的可见恢复流程。
- 眼镜硬件摄像供电指示仍是独立验收，不由 App 文案替代。

## BLE 候选契约

与固件工程共用 service `8f13a001-6c55-4b8e-9d51-2f76a4b10000`，control `...a002` 加密写，status `...a003` 加密读/通知。控制8字节：v1/u8、opcode/u8、request ID/u16 LE、argument/u32 LE；op1状态、2拍摄、3取消、4同意(0/1)、5清日志，其他操作 argument 必须0。

状态20字节：版本、state、flags、last_error、request ID/u16 LE、电量(255未知)、日志数、uptime/u32 LE、拍摄计数/u32 LE、错误计数/u32 LE。未知状态/错误码保留数值；flags 区分连接、同意、板卡配置和物理隐私验证。App 只实现 codec 和适配接口，没有进行设备扫描、配对、GATT 加密或媒体传输。JPEG 不能视为已通过这个控制通道发送。

## 官方依据

Flutter 工具链安装采用 [Flutter 手动安装说明](https://docs.flutter.dev/install/manual)、[Android 工具链说明](https://docs.flutter.dev/platform-integration/android/setup)；系统拍摄使用 Flutter 官方发布的 [image_picker](https://pub.dev/packages/image_picker)。实际依赖版本以 `mobile/pubspec.lock` 为准。

## 验证记录

2026-11-11：`flutter analyze --no-pub` **No issues found**；`flutter test --no-pub --reporter expanded` **18/18通过**，包括 API 来源/结构化 OCR、同意、超时、取消、删除并发、BLE 编解码、光学适配拒绝伪投递，以及2个真实 Flutter widget 测试。两处 widget 测试初次因600像素视口滚动定位失败，修复后全部通过。

`flutter build web --no-pub --no-wasm-dry-run` 成功，产物 `mobile/build/web/index.html`、`main.dart.js`。这是完整 App 的 Web 编译产物，不能冒充 Android 安装或 BLE/光学显示。Material 构建提示缺少可选 Cupertino 字体，未阻止构建，iOS 视觉效果仍未验收。

**Android debug APK 实际构建成功**：`flutter build apk --debug --target-platform android-arm64 --no-pub`，首次成功259.1秒，最终增量构建8.3秒、exit0。最终产物 `mobile/build/app/outputs/flutter-apk/app-debug.apk`，93,360,689字节，SHA256 `37e55067127b0c360f47019be47d793ef04d20fc774be027a27201c9bea0cac5`。最终包ZIP CRC检查通过；aapt2确认包名 `org.aiarglasses.ai_ar_glasses`、版本0.2.0/code2、minSdk24、target/compileSdk36、ABI仅arm64-v8a；apksigner验证debug签名v2通过。**未安装手机/模拟器，不是实机相机或光学显示验收。**

`pubspec.yaml` 最低工具版本已对齐锁文件（Dart≥3.13、Flutter≥3.44），未改变运行时功能或依赖版本；之后 `pub get --offline`、analyze、18项tests再次通过，并完成最终APK增量重打包。当前源码/锁文件哈希与工具版本见 `mobile/evidence/apk-inspection.json`，全部最终APK检查使用上面的93,360,689字节产物。

构建曾遇到的真实问题：初次Gradle发行包下载超时，改用同一官方9.3.1的较小bin发行包并核对官方SHA256 `b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06`；Java未自动继承Windows代理，按本次进程传入后进入Maven。一次 `builder-9.1.0.jar` TLS `bad_record_mac`，重试成功并核对官方SHA1；Kotlin若干jar握手中断，以同一官方地址预取12个jar并逐个核对官方SHA1（`mobile/evidence/gradle-prefetch.json`）。NDK28.2.13676358已安装。成功构建保留SDK XML版本/旧Kotlin插件弃用提示；未禁用证书验证或修改第三方插件源码。

为诊断网络做的直接Gradle离线运行也保留记录：曾因未下载运行依赖失败，后因缺少CMake3.22.1失败，不把该诊断称为成功。正常Flutter CLI构建已实际成功；网络恢复/本机SDK缓存齐备后优先使用上面的Flutter命令。`tool/prepare-gradle-cache.ps1` 对发生中断索引的Kotlin坐标提供官方POM/module/jar校验与本地Maven恢复，仅作用于明确指定的任务Gradle缓存，不保证一次准备任意全新机器的全部离线依赖。

### 本机工具与复现边界

工具只安装到项目外 `C:/codex-tools/`，没有永久改系统PATH。Flutter官方发行清单请求404、Git clone连接reset，改用官方GitHub `stable`源码ZIP：ZIP注释原始commit `c197ca5199e9ee5661e865596c9c07294dfab51c`，固定engine `89c39edfdfae2949f6806e4a315c0c08522238b7`，Dart **3.13.7**。源码包不含Git元数据，安装时建立了本地Git元数据和本地版本标签 `3.47.0-0.0.pre`，用Dart编译了官方Flutter CLI kernel；CLI显示的本地frameworkRevision不是上游commit。工具日志见 `mobile/evidence/flutter-version.txt`。

中文项目路径触发本版 Dart LSP `FormatException: Unterminated string`，使用ASCII junction `C:/codex-tools/glasses-mobile`指向原工程后分析通过。junction不是另存一份源码。JDK17/Android SDK/Gradle cache均放ASCII路径。本机复现：

```powershell
$env:FLUTTER_ROOT = 'C:\codex-tools\flutter'
$env:JAVA_HOME = 'C:\codex-tools\jdk-17.0.21+9'
$env:ANDROID_HOME = 'C:\codex-tools\android-sdk'
$env:GRADLE_USER_HOME = 'C:\codex-tools\gradle-cache'
$env:PATH = "$env:FLUTTER_ROOT\bin;$env:JAVA_HOME\bin;$env:PATH"
$env:JAVA_TOOL_OPTIONS = '-Dfile.encoding=UTF-8'
# 仅当网络需要系统代理时，不永久修改JVM/系统配置
$buildProxy = [Net.WebRequest]::DefaultWebProxy.GetProxy([Uri]'https://dl.google.com')
if ($buildProxy.Host -ne 'dl.google.com') {
  $env:JAVA_TOOL_OPTIONS += " -Dhttps.proxyHost=$($buildProxy.Host) -Dhttps.proxyPort=$($buildProxy.Port) -Dhttp.proxyHost=$($buildProxy.Host) -Dhttp.proxyPort=$($buildProxy.Port) -Dhttp.nonProxyHosts=repo.maven.apache.org|localhost|127.* -Dorg.gradle.internal.http.socketTimeout=15000 -Dorg.gradle.internal.http.connectionTimeout=10000"
}
# 从项目根执行一次，目录已存在时不重复创建
if (!(Test-Path C:\codex-tools\glasses-mobile)) {
  New-Item -ItemType Junction -Path C:\codex-tools\glasses-mobile -Value (Resolve-Path .\mobile).Path
}
Set-Location C:\codex-tools\glasses-mobile
flutter --no-version-check --suppress-analytics analyze --no-pub
flutter --no-version-check --suppress-analytics test --no-pub
flutter --no-version-check --suppress-analytics build apk --debug --target-platform android-arm64 --no-pub
```

只有遇到对应Kotlin中断缓存问题才运行（仍从官方HTTPS校验下载，不禁用证书）：

```powershell
.\tool\prepare-gradle-cache.ps1 -GradleUserHome $env:GRADLE_USER_HOME -RepositoryRoot C:\codex-tools\verified-maven
```

另两份并行预取证据为 `runtime-androidx-prefetch.json` 与 `runtime-flutter-prefetch.json`：AndroidX/Kotlin文件使用官方SHA256/SHA1；Flutter GCS不提供独立SHA文件，明确以官方HTTPS响应 `x-goog-hash` 的MD5校验完整内容，另记录本地SHA256，未称其为官方SHA256。大件180,753,519字节最终完成并校验；这些是构建依赖，不含用户媒体。

命令输出在 `mobile/evidence/flutter-analyze.txt`、`flutter-test.txt`、`flutter-build-web.txt`、`flutter-build-apk.txt`。`adb devices` 当前为空，没有Android手机/模拟器安装运行证据。原生语音输入/TTS、任务卡UI、持久离线恢复、真实BLE连接/加密、眼镜媒体传输、iOS、真实供应商和光学AR仍需分别实现或验收；不因本次软件构建标记为完成。
