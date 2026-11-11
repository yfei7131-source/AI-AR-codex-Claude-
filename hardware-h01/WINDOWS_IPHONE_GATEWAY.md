# Windows → iPhone Safari 的本地 HTTPS 测试入口

沿用已有Flutter工程与Python API。iPhone上的localhost是手机自身，不能照搬Windows的127.0.0.1 URL；相机的getUserMedia需要安全上下文。见 [MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)、[WebKit说明](https://webkit.org/blog/7763/a-closer-look-into-webrtc/)。本方案只在家庭/开发局域网服务，不使用公网隧道或上传照片到托管站点。

## 运行

先按 [IPHONE_WEB.md](IPHONE_WEB.md) 构建现有 `mobile/`，不要重新create工程：

```powershell
python -m pip install -r requirements.txt -r requirements-gateway.txt
# Flutter环境设置与ASCII路径见MOBILE_APP.md/当前IPHONE_WEB.md
flutter build web --no-web-resources-cdn
```

第二条Flutter命令应在现有mobile目录执行。返回项目根目录，将实际Windows WLAN的私有IPv4传入：

```powershell
.\tools\start-iphone.ps1 -LanIp 192.168.1.3
# 等价：python -m app.phone_gateway --lan-ip 192.168.1.3 --serve-ca
```

IP是本轮检测值，网络变化时用 `Get-NetIPAddress -AddressFamily IPv4` 确认。网关9443是HTTPS，9444只下载公开的项目CA证书。程序内部启动当前版本API到随机loopback端口，不暴露原API到LAN、不要求先启动旧8765服务。可以显式 `--backend-url http://127.0.0.1:8765` 使用已有后端，但需自行确保版本；不能代理外部地址。

退出按Ctrl+C。若端口占用，选择 `--port 9445`（公开CA会用9446）；不要复用其他服务的证书或直接改成无认证HTTP。启动器不会永久修改PATH、Windows信任库或防火墙。若Windows提示私有网络访问，请由用户核对项目和端口；没有改变系统策略时，防火墙仍可能阻止iPhone连入。

## iPhone的首次信任与配对（需要用户在手机完成）

1. Windows和iPhone连接同一可互访局域网；关闭访客网络隔离。保持Windows网关运行。
2. Windows查看 `artifacts/private/iphone/tls/public-info.json` 中的CA SHA256指纹。这个指纹可公开，`*-key.pem`绝不能分享。
3. 用手机Safari访问 `http://192.168.1.3:9444/ca.cer`，它只提供公开CA证书。安装前通过Windows指纹核对来源；不要安装指纹不匹配的证书。
4. 按Apple官方流程在手机手动安装并启用该证书的SSL信任；仅下载/安装不等于已经信任。参见 [Apple手动证书信任说明](https://support.apple.com/en-us/102390) 和 [HTTPS测试服务器说明](https://developer.apple.com/library/archive/qa/qa1948/_index.html)。这一步让Safari信任本项目开发CA，是明确的信任配置，不会由程序替用户自动完成，也不会通过点击绕过安全警告来冒充成功。
5. 在Windows打开本机 `artifacts/private/iphone/pairing-qr.png`，用iPhone扫描；或自行读取 `pairing.txt` 的链接。该二维码/链接含本次会话凭据，仅在本机展示给测试手机，不提交Git、不贴到聊天或外部分享。
6. 页面在Flutter路由加载前剥离URL fragment，token只留内存，不写localStorage。相机与上传分别勾选同意；先测试「仅本地校验」，确认返回 `cloud_sent:false` 再选择是否使用AI模式。

无需Mac、Android或Apple开发者会员完成此Web测试。它不是原生iOS安装途径，也不让Safari获得Web Bluetooth能力。原生BLE源码与无签名云构建见 [IOS_CLOUD_BUILD.md](IOS_CLOUD_BUILD.md)。

## 访问控制及留存

- 静态Flutter文件和 `/gateway/health` 可在该私有地址访问；所有 `/api/*` 需要随机256bit Bearer token、匹配Host/Origin与TLS。拒绝Web根目录与私有目录重叠，解析后的资源再次检查保护路径与证书扩展名，拒绝Windows尾空格/尾点/数据流路径。监听端口独占，第二网关不能复用同一端口覆盖配对文件。
- token只通过配对链接fragment和Authorization header传递，不接受query token、不写请求日志、不传入原有后端。会话8小时到期，重启生成新token；刷新丢失内存token后需重新打开本机配对链接。
- 原API仍只收loopback JSON；网关不转发浏览器Origin、Cookie、Authorization或任意目标地址，拒绝上游重定向。API体限3MiB，响应限2MiB；图片继续执行原项目2MiB/16MP解码/清元数据规则。
- 证书有效期30天；开发CA一年。IP变化/证书到期时用新的 `--tls-dir artifacts/private/iphone/tls-new` 生成并重新手动信任。私有文件残缺或IP不匹配时拒绝覆盖旧密钥。测试结束后用户可以从iPhone删除项目证书/信任；程序不擅改手机或Windows信任设置。
- 没有AI Key时Live明确失败，Demo明确标模拟；本地媒体校验完全不调用供应商。语音识别可能由浏览器服务商处理音频，另行显式同意；不支持时保留文字输入。

## 已验证范围

`python -m unittest discover -s tests -p test_phone_gateway.py -v`：12项真实本地TLS测试通过，包括可信CA链、认证缺失/错误/到期、同源/Host、路径穿越、私有目录误配置/Windows路径别名、独占端口、媒体请求转发、限长、无敏感header转发、重定向拒绝与仅公开CA下载。测试使用合成输入和本地后端，不等于手机Safari或真实AI验收。

另在本机真实WLAN IPv4上验证可信TLS/主机名、最终Flutter首页、Bearer鉴权、合成80×50 PNG经现有后端validate及live无Key的503错误；`cloud_sent:false`，不曾修改系统信任库/防火墙。可提交的脱敏摘要见 [sprint03-windows-tls.json](evidence/sprint03-windows-tls.json)，不包含token或图像。

还需用户手机执行：HTTPS信任、安全上下文、前后摄像头/拒绝权限/停止、HUD/OCR结果、语音能力与网络错误。没有执行这几项之前只能标“代码与自动测试通过，iPhone待验”。
