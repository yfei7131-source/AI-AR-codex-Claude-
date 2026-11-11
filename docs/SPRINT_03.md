# Sprint03 实现与验证报告

2026-11-11，Windows+iPhone，无Mac/Android手机、暂不购买Apple会员。继续提交 `c5563b5` 的工程，没有重新create项目或替换Python/Flutter/ESP-IDF架构。22项冻结需求保持16 P0/5 P1/1 R，完整产品统计仍为0已实现/12部分/10未实现；AR光学、镜片、佩戴与PCB保持V1必需门槛。

## 本轮实际开发

| 工作包 | 代码与配置 | 自动验证与真实环境边界 |
|---|---|---|
| iPhone Flutter Web | 真实getUserMedia预览/静态JPEG、后置优先请求、同意/停止/超时/晚到流释放；HUD、双向OCR原文/译文、AI来源校验、ASR/TTS能力检测及文本退化 | Flutter与JS回归、真实Web构建通过；没有iPhone Safari摄像/语音实测，不把测试替身当手机验收 |
| Windows手机入口 | 新增`app.phone_gateway`，同源TLS/Bearer到既有loopback API；本机私有配对二维码/链接，手动信任CA，限时会话 | 真实TLS单测与WLAN地址烟测通过；没有自动装证书/改防火墙/公网隧道。合成图本地validate返回cloud_sent:false |
| iOS云构建 | 根`codemagic.yaml`含依赖、Python/Node/Dart测试、`flutter build ios --release --no-codesign`及Runner.app.zip/hash产物 | 官方schema及工程输入检查通过；没有远程仓库/Codemagic账号连接，云任务未执行、Swift未编译，无签名产物不能直接装iPhone |
| iOS原生接口 | CoreBluetooth扫描/显式连接/订阅/串行写/超时/断连清理；摄像/照片/蓝牙/本地网络用途；URLSession单帧分块、请求关联与SHA256 | Dart MethodChannel/EventStream测试替身通过；没有原生扫描选择UI，原生API仍为loopback开发配置，手机安装/系统配对/局域网权限待验 |
| ESP32-S3媒体 | 保留BLE v1控制/状态，新增v2临时会话；物理窗口后开发AP、随机WPA2/临时token、≤2MiB JPEG、15秒RAM留存、16KiB Range/校验/删除与撤销 | 纯C测试、默认/EYE/AP启用三配置真实交叉编译；未烧录或运行AP，未解锁未审核相机，未插入模拟设备图片 |
| Android兼容 | 保留原平台、系统相机/图库、USB adb reverse开发路径；Web桥用条件导入，原生iOS桥不假连Android | arm64 debug APK实际构建/包检查，当前产物以最终证据为准；无Android安装实测 |

Web资源使用同源CanvasKit及未修改的OFL Noto Sans SC中文字体，许可证与来源随项目保留。没有复制Windows商业系统字体。首次17.8MB字体加载可能较慢，目前没有iPhone时延/内存数据；不支持的Unicode/emoji仍可能缺字。

## 集成时修复的问题

1. Web原API默认127.0.0.1无法供iPhone直接使用；采用独立同源TLS/Bearer网关，底层API继续loopback，不开放无鉴权LAN或跨源凭据。
2. 独立复核发现静态目录误设为私有目录父级、Windows尾空格别名可越过扩展名检查；启动时禁止目录重叠，资源resolve后复查保护路径/扩展名，并拒绝尾空格、尾点和数据流路径，补回归测试。
3. Windows默认HTTPServer复用监听地址可能令两网关共用端口，新配对文件对应不到实际响应进程。WLAN烟测确实出现401，清理本轮残留进程后改为SO_EXCLUSIVEADDRUSE/禁用地址复用，端口冲突回归及重新烟测通过。
4. 设备GATT写ACK只代表命令入队，不能代表媒体会话/拍照已完成。跨端审查要求a005响应关联已处理的v2 request_id，iOS只读有界轮询，取帧等待同一拍照request_id，禁止靠自动重拍掩盖时序问题。最终验证边界以原生/固件报告为准，Swift仍待实际编译。
5. 最初AP开启构建超出原1MiB factory分区10160字节，保留当时真实失败日志；仅专用AP检查配置改用ESP-IDF官方1500K factory分区。最终加入请求关联后的镜像为1059168B，普通默认配置不变，不声称具备OTA空间/回滚能力。

## 运行与测试

Windows+iPhone从 [WINDOWS_IPHONE_GATEWAY.md](WINDOWS_IPHONE_GATEWAY.md) 开始，现有Flutter Web步骤见 [IPHONE_WEB.md](IPHONE_WEB.md)。用户自行在手机完成CA来源核对、SSL信任和相机/语音授权，程序不替用户信任未知证书。启动命令从项目根执行：

```powershell
python -m pip install -r requirements.txt -r requirements-gateway.txt
.\tools\start-iphone.ps1 -LanIp 192.168.1.3
```

IP为本轮Windows WLAN检测值；网络变化时先确认地址。先「仅本地校验」，测试图片保持本地，不得未经确认提交外部服务。Live无Key返回503 AI_NOT_CONFIGURED且没有answer，Demo明确模拟；语音识别可能经浏览器服务商，必须单独同意。本轮没有真实AI请求、20图质量评分或iPhone验收。

自动验证命令：

```powershell
python -m unittest discover -s tests -v
node --test mobile/test/browser_bridge.test.cjs
python firmware/tests/run_host.py --cc C:/codex-tools/glasses-host/ziglang/zig.exe
python mobile/ios/ci/validate_ios.py
python tools/check_repository.py
```

Flutter使用项目外工具与指向本工程的ASCII junction，不另存项目，环境命令见 [MOBILE_APP.md](MOBILE_APP.md)：

```powershell
cd C:/codex-tools/glasses-mobile
flutter analyze --no-pub
flutter test --no-pub
flutter build web --no-pub --no-wasm-dry-run --no-web-resources-cdn
flutter build apk --debug --target-platform android-arm64 --no-pub
```

最终验证结果：

| 命令/范围 | 实际结果 | 原始证据/摘要 |
|---|---|---|
| Python全量unittest | 102/102通过，无skip；含12项真实本地TLS与旧网页Node25项包装 | [sprint03-unittest.txt](evidence/sprint03-unittest.txt) |
| 新Web媒体桥Node测试 | 19/19通过；getUserMedia/Speech API使用明确替身 | [sprint03-web-bridge.txt](evidence/sprint03-web-bridge.txt) |
| Flutter analyze / test | No issues，41/41通过（原18+Web8+native15） | [分析](../mobile/evidence/iphone-web-analyze.txt)、[完整测试](../mobile/evidence/iphone-web-flutter-tests.txt) |
| Flutter Web | 同源资源构建成功，30.6s；JS 2,750,033B，SHA256 `0bbbdae8b1b770ae64c89a1b57f727f06694ea81dd5a84c4aad797bc5b91026c` | [Web验证JSON](../mobile/evidence/iphone-web-validation.json) |
| Android arm64 debug | 最终增量构建成功11.9s；APK 93,391,373B，SHA256 `fe9952542724846d88cbd0a18d592132368bf4dd1fade932915af5484c4d64f0`；ZIP CRC/包名/ABI/debug签名检查通过 | [Android最终摘要](../mobile/evidence/sprint03-android/summary.json) |
| 固件Host C | 38/38通过（原20+媒体18），没有硬件采集 | [sprint03-host-tests.txt](evidence/sprint03-host-tests.txt) |
| ESP32-S3交叉编译 | 默认717776B、EYE726608B、AP-large1059168B均成功；三份镜像和各22份源哈希由主代理独立复核 | [固件验证JSON](../firmware/evidence/sprint03-verification.json) |
| iOS配置/Codemagic | validate_ios.py PASS、官方schema PASS，最终YAML/Swift源哈希对应 | [static_validation.json](../mobile/ios/ci/static_validation.json) |
| Windows WLAN真实TLS | CA链/主机名/同源Flutter首页、Bearer401、80×50合成PNG本地validate、Live503无answer均通过 | [脱敏烟测JSON](evidence/sprint03-windows-tls.json) |

Python102包含旧网页Node25包装，不计为127项独立Python测试；新的媒体桥19项是另一套入口。中文bitmap14项也已包含在Python总数。TLS是真实本地传输，AI/媒体/MethodChannel隔离桩仍不代表供应商、iPhone或眼镜实机。云端/Swift编译、手机实际渲染/权限、BLE/AP硬件和光学AR一律未验收。原始源码哈希见 [sprint03-source-sha256.json](evidence/sprint03-source-sha256.json)，跨层摘要见 [sprint03-verification.json](evidence/sprint03-verification.json)。

## 文件与证据索引

- Web：`mobile/lib/{api,controller,main,browser_media*}.dart`、`mobile/web/{browser_bridge.js,flutter_bootstrap.js,fonts/}`、Dart/JS回归；[Web证据](../mobile/evidence/iphone-web-validation.json)。
- HTTPS：`app/{dev_tls,phone_gateway}.py`、`tools/start-iphone.ps1`、`requirements-gateway.txt`、`tests/test_phone_gateway.py`；[Windows烟测](evidence/sprint03-windows-tls.json)。
- iOS：`codemagic.yaml`、Runner Swift/Info.plist/Xcode配置、Dart native adapter/codec；[CI静态证据](../mobile/ios/ci/static_validation.json)、[实现说明](IOS_CLOUD_BUILD.md)。
- 固件：`media_core.*`、`media_service.*`及主循环/BLE/按键/相机适配；[构建聚合](../firmware/evidence/sprint03-verification.json)、[本轮报告](FIRMWARE_SPRINT03.md)、[媒体协议](../protocols/DEVICE_MEDIA_V1.md)。
- 质量：`.gitignore`与暂存快照检查补充证书/私钥排除；README/AGENTS、[架构](ARCHITECTURE.md)、[三层矩阵](TRACEABILITY.md)、开发日志同步更新。密钥、配对链接/二维码、图片、构建缓存、APK/bin不进入Git。

## 剩余问题与下一阶段

1. iPhone需实际执行Web信任/权限/拍照/停止/后台/语音与断网验收。Safari没有本项目BLE能力；Web不承担原生BLE实测。
2. 连接现有私有远程仓库和Codemagic后运行无签名云任务，修复实际Swift/Xcode问题。当前没有配置这些外部账户，也没有代用户发布或创建远程仓库。无签名编译不能替代签名安装，本轮不要求购买Apple会员。
3. 补原生扫描/选择/连接UI、受控网关地址/会话凭据入口、系统权限错误反馈；真实iOS安装、BLE加密/所有权策略、AP手动连接、JPEG吞吐/超时/撤销均需设备验证。Just Works开发配对仍不是产品所有权安全验收。
4. 相机及GPIO沿用官方选定板原理图，音频配置不臆造；完成物理灯供电/采集联动审核后才能解除固件采集锁。AP默认关闭、固定开发地址/短会话只用于受控开发，不是最终配网方案。
5. 后续用户配置服务端Key后执行10视觉+10OCR真实验收并人工核对，当前保留blocked/unknown，不重复询问。取消不保证撤销供应商处理/费用。
6. 独立AR显示驱动与中文bitmap真实投递、光学可读性、镜片验配、佩戴/电源/热测试继续为P0；原理图/Pin Map/ERC/DRC完成前不盲目导出PCB。上下文、AI整理、真实外部动作、OTA/离线/P1任务按冻结矩阵继续。
