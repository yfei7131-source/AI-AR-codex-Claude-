# iOS 无签名云编译与真实设备接口

日期：2026-11-11。当前交付是 Codemagic 配置、Swift CoreBluetooth/URLSession 实现、Dart 桥接与本地测试。**本轮没有运行 Codemagic、没有编译Swift、没有生成可安装的iPhone包，也没有完成眼镜BLE/Wi-Fi实测。** Windows+iPhone、无Mac、无签名身份的条件保持如实记录。

## unsigned 工作流

项目根目录 `codemagic.yaml` 的 `ios-unsigned` 使用macOS M2、Flutter stable、Xcode latest、Node22，依次执行：

1. `validate_ios.py` 与macOS `plutil` 检查权限、plist和Xcode项目。
2. 明确检查Python3.12，创建venv并安装 `requirements.txt` 和 `requirements-gateway.txt`，运行全Python测试。
3. `node --test mobile/test/browser_bridge.test.cjs`，覆盖独立Web媒体桥测试。
4. `flutter pub get`、`flutter analyze`、`flutter test`。
5. `flutter build ios --release --no-codesign`，真实编译包括新增Swift源；完成后用 `ditto` 打包 `Runner.app.zip`，附SHA256及构建范围说明。

没有签名credentials、发布、TestFlight、IPA导出或自动触发器。Codemagic官方支持先做unsigned构建；后续签名属于独立步骤。[Codemagic unsigned示例](https://docs.codemagic.io/yaml-quick-start/first-signed-build/)

官方schema不接受 `environment.python` 字段，因此采用脚本强制Python3.12，避免静默使用不符合本项目依赖口径的解释器；官方当前macOS镜像列出的Python为3.12.7。Node版本通过schema支持的 `environment.node` 配置。[Codemagic配置字段](https://docs.codemagic.io/yaml-basic-configuration/yaml-getting-started/)、[macOS镜像说明](https://docs.codemagic.io/specs-macos/xcode-26-6/)

预期产物路径为 `mobile/build/ios/unsigned/Runner.app.zip`。**它是iOS device目标的未签名编译产物，不能直接装到iPhone，也不是iOS模拟器架构应用。** iPhone运行仍需要受信的开发签名、相应设备配置和合适的macOS/Xcode流程；本次没有购买会员或创建签名凭据。[Flutter iOS构建要求](https://docs.flutter.dev/deployment/ios)、[iPhone开发签名说明](https://docs.flutter.dev/platform-integration/ios/setup)

当前没有项目远程Git连接或Codemagic账号会话，因此只完成配置与静态验证，没有创建远程仓库、绑定账户或启动收费云任务。后续将此现有工程提交到用户选择的远程仓库并连接Codemagic后，手动选 `ios-unsigned` 执行；在看到真实日志前保持 `cloud_build_executed=false`。配置静态通过不证明云镜像可用、配额有效或Swift编译通过。

## iOS 原生桥接

新增 `mobile/ios/Runner/GlassesBleBridge.swift`、`DeviceImageTransfer.swift`，已加入Xcode Sources；`AppDelegate` 保留现有UIScene/implicit engine结构并注册通道。Flutter官方对应注册入口为 `didInitializeImplicitFlutterEngine`，消息通过MethodChannel/EventChannel传递。[Flutter平台通道](https://docs.flutter.dev/platform-integration/platform-channels)、[implicit engine注册示例](https://docs.flutter.dev/platform-integration/ios/platform-views)

- MethodChannel：`aiar/device`；EventChannel：`aiar/device_events`。
- Dart实现：`IosGlassesDeviceAdapter`；工厂 `createNativeDeviceAdapter()` 仅iOS返回该适配器，Android/Web仍返回原 `UnconfiguredDeviceAdapter`。
- 初始化桥接不会立刻创建CBCentralManager。只有用户明确同意 `startScan(consent:true)` 才扫描目标服务；用户选择扫描结果后调用 `connectTo(id)`，不会连接第一台设备。
- 连接先发现a001服务与a002/a003特征、订阅status并读取有效20字节状态，才返回ready；只有链路建立不能算已就绪。
- v1控制保持8字节、小端字段；status保持20字节，255电量继续表示unknown。控制写入采用 `.withResponse`，由真实delegate回调确认ATT写入；这不等于采集或外部动作执行成功。[Apple写入确认语义](https://developer.apple.com/documentation/corebluetooth/cbperipheral/writevalue(_:for:type:))
- 外设要求加密的GATT读写可能触发iOS系统配对；应用不提供伪造的“配对成功”状态。读取、订阅或写入失败均报错。CoreBluetooth没有本实现可查询的“已认证所有权/防MITM通过”结果，固件开发链路仍为SC Just Works，不能声称安全认证。[Apple CoreBluetooth](https://developer.apple.com/documentation/corebluetooth)
- 取消/撤同意优先清理本地图片接收与排队命令；断连、蓝牙关闭/重置、应用进入后台时取消接收、清理状态并断开BLE。没有后台录音、相机或蓝牙常驻声明。

常用Dart调用顺序：

```dart
final device = IosGlassesDeviceAdapter();
final subscription = device.events.listen((event) { /* 显示扫描结果或设备状态 */ });
await device.startScan(consent: true);
await device.connectTo(userSelectedIdentifier);
await device.writeControl(DeviceControl.encode(ControlOpcode.consent, 1, argument: 1));
await device.writeControl(DeviceControl.encode(ControlOpcode.capture, 2));
// 用户取消时使用新命令标识；不能把写入回执当作图片采集成功。
await device.cancelCapture(3);
await device.dispose();
await subscription.cancel();
```

当前手机界面保留原有UI；factory注入并不会自动增加完整扫描/选择设备页面。原生接口需要上述显式选择及权限流程，默认连接状态仍为disconnected。

## 设备Wi-Fi媒体接口

实现遵循 [DEVICE_MEDIA_V1.md](../protocols/DEVICE_MEDIA_V1.md)：a004/v2的20字节open/query/revoke帧、a005≤512字节Read Long会话JSON。设备需物理配对窗口、加密BLE及编译启用才能提供短时凭据；无帧期间有限等待，8秒后明确 `NO_FRAME_TIMEOUT`，不会用fixture补图。

`openMediaSession(requestId, consent:true)` 通过真实GATT操作读取会话；a005必须含设备最后实际处理v2命令的 `request_id`，不能用ATT ACK或旧ready快照确认本次open。原生客户端v2使用1–65535，保留0不用，因为0表示启动快照。SSID/WPA2口令/Bearer token只留在结果和内存，不广播到event、不写日志或磁盘。本版由用户在iPhone设置中加入临时设备Wi-Fi，没有静默加入网络或Hotspot entitlement。

`fetchFrame(session, requestId, consent:true)` 只接受 `http://192.168.4.1[:80]`，拒绝外部host、userinfo、query、fragment及重定向。URLSession采用ephemeral配置、无cache/cookie/credential storage，delegate按实际收到的字节执行上限。[Apple URLSessionDataDelegate](https://developer.apple.com/documentation/foundation/urlsessiondatadelegate)

媒体状态必须version1/source=device/captured=true；frame_id为非零uint32、request_id匹配、JPEG≤2MiB、TTL≤15秒。每块Range≤16384字节，逐块校验206、Content-Range、ETag和长度；完整拼接后使用CryptoKit SHA256核验，结果保持 `Uint8List`。读取成功后尝试DELETE释放设备帧，`release_confirmed` 如实表示回执；不能保证已发到手机的字节被设备删除。[Apple CryptoKit SHA256](https://developer.apple.com/documentation/cryptokit/sha256)

`cancelFetch(requestId)` 停止本地接收并发v1 cancel；`revokeMediaSession(requestId)` 先停止本地接收，再发v2 revoke。v2 revoke忽略旧会话快照，只有匹配其request_id且 `ready:false,error:revoked` 才返回设备处理确认。ATT回执只表示指令已入队；物理硬件、设备端到期和所有在途事务仍需实测。手机取得图片不等于同意发云端，既有AI上传同意必须另行检查。设备AP为开发WPA2+本地HTTP，不冒称端到端TLS。

### 异步ACK与旧结果修复

固件先ACK GATT写入、稍后由worker启动AP或采集，所以iOS不能只读一次就将旧 `pairing_window_open`、`revoked` 或旧ready当成本次结果。Swift现在只发送一次a004命令，然后每200毫秒串行读取a005，整体10秒上限：先核对已处理request_id；匹配后的open/query ready才成功，disabled/ble_required/pairing_required/wifi_start_failed立即报错，明确非终态只继续读，不重发open、不续租。撤销、断连、后台或超时会取消poll并使旧read generation失效；同一时刻最多一个Read Long，旧读返回不能完成新请求。Dart也再次检查expectedRequestId与本地epoch，防止断连后晚到凭据恢复状态。

紧跟capture ACK的 `fetchFrame` 每200毫秒读取HTTP status，最多8秒等待同一个v1采集request_id；无帧或其他请求的旧帧都不能交付。超时返回 `NO_FRAME_TIMEOUT`，不会自动再拍照或重新open。匹配帧后停止等待计时器，再执行原有TTL/Range/长度/SHA256流程。取消、撤销、断连与后台都释放本地接收引用并关闭后续轮询。该Swift行为已编写并检查源逻辑，尚未在Mac编译或iPhone实测；Dart测试只验证它能测试的关联/迟到/不重发契约。

## 权限边界

Info.plist新增 `NSBluetoothAlwaysUsageDescription`、`NSLocalNetworkUsageDescription`，保留现有相机和用户选图说明。目标iOS15，不添加无关后台录音或旧版蓝牙权限。系统本地网络权限没有本实现可查询的可靠预授权状态，接口返回“由实际请求结果判断”，不会猜测granted。[Apple蓝牙用途说明](https://developer.apple.com/documentation/bundleresources/information-property-list/nsbluetoothalwaysusagedescription)、[Apple本地网络用途说明](https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription)

固件明确没有Bonjour广告，本版使用固定AP地址，所以未声明虚构的 `NSBonjourServices`；将来实现具体浏览服务后再添加对应service type，不添加泛用发现权限。[Apple Bonjour服务声明](https://developer.apple.com/documentation/bundleresources/information-property-list/nsbonjourservices)

## 已执行的本地验证

| 检查 | 实际结果与范围 |
|---|---|
| `python mobile/ios/ci/validate_ios.py` | PASS：plist用途、无无关后台权限、源文件注册和唯一Xcode对象ID；不是Swift编译 |
| 官方Codemagic JSON schema | 当前最终YAML校验PASS，证据 `mobile/ios/ci/static_validation.json`；未运行CI |
| `flutter analyze --no-pub` | ASCII验证副本通过，No issues；原中文路径曾触发Dart LSP路径编码异常，所以没有用其失败输出当通过 |
| `flutter test --no-pub test/native_ble_test.dart` | 15/15：v1/v2编码、同意、显式连接、无plugin不假连、断连、取消、v2撤销确认、会话约束、旧request_id/非终态/终态分类、迟到凭据拒绝、无帧超时不重拍及非零frame_id/完整性元数据；通道为明确测试替身 |
| `node --test mobile/test/browser_bridge.test.cjs` | 19/19通过；独立Web桥合约测试，未称Safari实机或BLE通过 |
| Swift、CoreBluetooth、URLSession真实设备 | 未编译/未实测；须执行Codemagic编译任务并做签名后iPhone实测 |

官方schema确实检查结构，但不校验账号、付费权限、软件可用版本或credentials；本地测试替身也不能证明iPhone系统配对、局域网弹窗和真实吞吐。[Codemagic静态校验边界](https://docs.codemagic.io/partials/yaml-validate/)
