# Windows + iPhone：Safari 手机中枢

2026-11-11。继续使用现有 `mobile/` Flutter 工程，新增同源HTTPS、浏览器摄像头与语音能力适配。无需Mac或开发者会员即可在Safari打开此Web应用；这不等于原生iOS App安装，也不提供Safari眼镜BLE连接。

## 从Windows打开

在项目根目录先构建现有应用，再启动项目网关（LAN地址替换成Windows当前私网IPv4；默认127.0.0.1只能本机访问）：

```powershell
cd mobile
flutter build web --no-wasm-dry-run --no-web-resources-cdn
cd ..
python -m app.phone_gateway --lan-ip 192.168.1.20 --serve-ca
```

网关把Flutter静态文件和 `/api/*` 放在同一HTTPS源，不把Python后端直接开放到LAN。Windows/iPhone需能在局域网互通；本工具不会自动修改防火墙或系统信任。

首次使用时，由用户在iPhone手动安装并信任本机生成的本地CA，核对网关输出的CA SHA256指纹后再信任；公有CA证书可由可选的HTTP证书端点获取，私钥不分发。具体信任操作参见 [Apple证书说明](https://support.apple.com/en-us/102390)。证书警告被跳过不代表已获得可信安全上下文，不能据此保证相机可用。打开私有忽略目录 `artifacts/private/iphone/` 中的配对二维码或链接，不把链接/二维码提交Git或转发给他人。

链接格式为 `https://<Windows地址>:9443/#pair=<本次会话>`。页面脚本在Flutter启动前立即移除fragment，将会话一次性交给Dart；只保存在进程内存中，不写query、localStorage或请求JSON。每个API请求使用 `Authorization: Bearer ...`。没有链接时可在页面输入本次Windows配对会话，输入框遮挡内容、提交后清空；这里不是填写AI API Key。会话过期或网关重启后需要新的链接。全部 `/api/*` 都需要网关认证，公共 `/gateway/health` 不含凭据。

## 实际交互

1. 同意设备采集后点击“开启摄像头预览”。使用 `getUserMedia`，只请求视频、偏好后置摄像头，`playsinline`/muted预览；不在开启时上传。
2. 点击“抓拍当前画面”把当前像素转为JPEG内存预览。也可手动选择JPEG/PNG照片，浏览器不支持直接摄像时保留选图退化。原生Android仍使用已有系统相机/图库入口。
3. 单独同意提交图片，再点击“仅校验上传，不调用AI”。调用 `/api/media/validate`，必须收到 `validated=true,scope=local_only,cloud_sent=false` 才显示本地成功；没有API Key也能验收采集/上传/解码，不把它叫AI或OCR成功。
4. 视觉问答与OCR翻译使用既有 `/api/ask`；默认明确DEMO。选择真实AI后失败不回退，密钥仍只放Windows/Python服务。OCR保留原文、译文、检测语言与不确定标记供人工核对。
5. 浏览器提供SpeechRecognition/WebKit前缀能力时，先单独同意麦克风与可能发送至浏览器供应商的音频处理，再点“语音转文字”。结果只进入可编辑输入框，用户核对后点击才提交给AI或保存；不支持/拒权/服务失败时使用键盘。30秒自动停止。
6. 浏览器提供speechSynthesis时，可主动朗读有效结果；DEMO播报带“模拟演示”。不同Safari/iOS版本、系统设置、权限与浏览器语音服务可能影响结果，不承诺所有Safari版本支持；按钮能力检测不等于实机验收。

摄像授权等待上限15秒、视频播放就绪8秒；用户不响应或权限拒绝均显示失败。关闭、撤销采集同意、换到图库、切换后台、pagehide和组件销毁都会停止媒体轨道与语音，不自动重开。迟到的摄像流会立即释放；取消/删除使旧API结果不能覆盖新HUD。删除也清除Flutter图片缓存中的当前显示引用，并停止摄像/语音；系统图库、浏览器供应商语音服务和云端保留不由本地按钮控制。

HUD是手机预览；Safari Web不支持本项目眼镜BLE。页面不显示虚构的蓝牙连接、电量或光学投递状态；原生BLE和光学HUD适配保持独立。`main`已注入仅iOS启用的原生设备factory，但目前没有扫描/选择/连接的原生BLE UI入口，只有adapter API；仍需后续接入显式用户操作，不能称为已可操作的原生设备配对流程。

## 本地中文资源

`mobile/web/fonts/NotoSansSC.ttf` 来自Google Fonts官方Noto Sans SC目录，未修改字体二进制，17,772,300字节；SHA256 `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`。已读取并保留SIL OFL1.1许可与版权，来源/哈希在同目录 `SOURCE.json`，完整许可在 `OFL.txt`。

应用用同源FontLoader注册该字体，启动状态可见，加载失败时给出本地资源错误。`flutter_bootstrap.js` 明确将CanvasKit和后备字体URL限定到当前网关源；构建使用 `--no-web-resources-cdn`，不依赖gstatic的中文字形下载。不在本字体覆盖范围的特殊字符仍需另行验证；没有把字体支持等同于所有Unicode/emoji均已验收。

## 自动化与验证边界

复用本机现有Flutter/Dart工具与ASCII junction `C:/codex-tools/glasses-mobile`，未重建工程或把密钥放客户端：

```powershell
flutter analyze --no-pub
flutter test --no-pub --reporter expanded
node --test test/browser_bridge.test.cjs
flutter build web --no-pub --no-wasm-dry-run --no-web-resources-cdn
```

新加8项Flutter API/controller测试：同源限制、Bearer仅header、注入拒绝、纯本地校验与同意、无AI配置可用、拒绝错误cloud范围、删除并发；浏览器JS契约覆盖采集/语音能力检测、授权、超时、迟到流、track结束、后台清理、fragment剥离和同源资源配置。测试中的摄像流/语音是明确的API桩，不能当作iPhone或眼镜实机结果。

最终命令输出在 `mobile/evidence/iphone-web-analyze.txt`、`iphone-web-flutter-tests.txt`、`iphone-web-media-tests.txt`、`iphone-web-build.txt`；本轮汇总和产物哈希在 `iphone-web-validation.json`。实际iPhone Safari的证书信任、相机、麦克风、语音、安装到主屏幕与移动网络场景均未在此环境验证；真实AI、原生BLE和光学AR也没有因此标记完成。

最终结果（含原生ACK/撤销关联修复后的冻结Dart）：analyze **No issues found（5.9秒）**；Flutter **41/41通过**（原中枢18 + Web API/controller8 + 原生BLE桥接15）；JS VM媒体/授权/同源引导契约 **19/19通过**；最终自包含Web构建 **30.6秒成功**。`build/web` 已包含字体、OFL许可、browser bridge与同源CanvasKit Wasm。同份冻结源也完成Android arm64 debug增量构建（11.9秒），独立证据见 `mobile/evidence/sprint03-android/`，没有用它替代手机安装运行。构建仍给出可选Cupertino图标字体提示，未阻止构建；没有把该提示或编译成功当作iPhone视觉效果已验收。纯本地校验HUD有独立来源标签，即使选择live也不会把它标成真实AI结果。

实现依据为 [Dart JS interop](https://dart.dev/interop/js-interop/usage)、[Flutter HtmlElementView](https://api.flutter.dev/flutter/widgets/HtmlElementView-class.html) 和 [WebKit媒体示例](https://webkit.org/blog/11353/mediarecorder-api/)；能力与权限始终在运行时检测，不根据浏览器名称模拟成功。
