# Device Media V1 / BLE Session V2

状态：Sprint03实现契约，尚无ESP32↔iPhone物理链路验收。所有现有板卡profile的物理采集审核标志保持false，设备不会生成模拟JPEG冒充采集。Safari没有本项目的Web Bluetooth路径；使用iOS CoreBluetooth + 本地Wi-Fi URLSession。

## BLE兼容与主动配对

原服务 `8f13a001-6c55-4b8e-9d51-2f76a4b10000`、v1控制a002（8byte）和状态a003（20byte）保持不变。JPEG不进入BLE。新增：

- a004：加密Write，V2会话控制20byte：`[version=2:u8, opcode:u8, request_id:u16LE, ttl_ms:u32LE, reserved:12bytes=0]`；op=1 open、2 query、3 revoke。open的ttl=1000..120000；其他必须0。未知版本/op/保留字段直接拒绝。
- a005：加密Read Long，UTF-8 JSON≤512byte，无notify。`{"version":2,"request_id":0,"ready":false,"error":"disabled"}`；成功则 `ready:true` 并附 `ssid`、`passphrase`、`base_url:"http://192.168.4.1"`、64hex `token`、`expires_in_ms`。兼容新增的 `request_id` 是**最后已实际处理的v2命令ID**，初始0；ready与error快照均携带。ATT写ACK只表示已接收/入队，不能据此判定处理完成。

固件编译开关 `CONFIG_GL_MEDIA_DEV_AP` 默认n；即使编译启用，也需设备按键长按≥3s开启30s物理配对窗口后用户在原生App点击连接媒体链路。原1s长按仍撤销采集同意和会话；3s动作随后开启新的配对窗口。open消耗一次窗口。无窗口、无BLE连接/加密或开关关闭不得返回凭据或启动AP。SSID/32hex WPA2口令/64hex token每会话随机生成，不写NVS、不打日志；AP只准1个station，无NAT/外网转发/Bonjour。

App串行操作a004/a005：open或query完成后读取完整a005；勿在一次Read Long中并发改会话。JSON中的TTL是该控制操作的快照，读取不会续租；设备始终按自己的绝对deadline拒绝过期token。复用同一个open请求ID不延长活跃会话。revoke与v1 cancel/consent(false)、BLE断连均立即撤token、清帧；物理窗口不能由App远程打开。

原生App必须有界轮询a005，先匹配本次v2命令的 `request_id` 再接受ready或终态错误；旧ID快照只能等待，不能接受旧ready或误报旧错误。open终态错误为 `disabled`、`ble_required`、`pairing_required`、`wifi_start_failed`；等待期间不得重发open续租。显式v2 revoke实际清理完成后，固定返回匹配ID的 `ready:false,error:"revoked"`（包括编译禁用的幂等清理），不能把仅ATT ACK描述为已确认撤销。物理/断连/HTTP到期等非v2操作保留最近已处理v2 ID，不伪造新的请求ID。

开发AP是WPA2本地HTTP传输，尚非生产版端到端TLS/设备所有权认证。BLE为SC-only Just Works，未证明MITM防护。不得据此宣称隐私或安全认证通过。

## 本地HTTP拉取

所有HTTP请求都需要 `Authorization: Bearer <64hex token>`，仅Host `192.168.4.1[:80]`，不接受浏览器Origin，不允许重定向/外部地址。服务没有接收上传的PUT/POST，也不会向云端上传。图像链为设备JPEG→本地iPhone拉取→用户另行同意后由手机使用既有AI链路；第二次上传不由设备会话授权替代。

`GET /v1/media/status`：200 `application/json`，`Cache-Control:no-store`。

```json
{"version":1,"source":"device","captured":false,"frame":null}
```

只有真实camera callback通过物理审核与运行时同意gate，并将完整JPEG放入RAM后才能返回：

```json
{"version":1,"source":"device","captured":true,"frame":{"frame_id":1,"request_id":12,"length":12345,"sha256":"64hex","mime":"image/jpeg","captured":true,"expires_in_ms":15000}}
```

frame_id为非零uint32计数，request_id关联v1 capture；最大2MiB、单帧RAM留存≤15s，不写Flash/SD/NVS。下一帧替换或删除/取消/断连/到期时覆盖清零原buffer。无帧不能标captured；不会用图片fixture填设备状态。

`GET /v1/media/frame/{frame_id}` 必须有单一闭区间Range，例如 `Range: bytes=0-16383`。每次最多16384byte；禁止suffix/open-ended/multi-range。成功206，`Content-Type:image/jpeg`、`Content-Range:bytes start-end/total`、`ETag:"<sha256>"`、`Cache-Control:no-store`。客户端按metadata长度逐块拉取，拼接后校验长度与SHA256；不符立即丢弃。无权/过期401、无该帧404、缺Range/格式/越界/过大416。每块均重新验token和帧ID；撤销不允许继续取下一块。已发送到手机的字节无法由设备删除，iOS须在取消/断连后清理接收buffer。

`DELETE /v1/media/frame/{frame_id}`：有权且帧匹配时204，清零该帧但不撤当前会话token；失败401/404。App校验完成后主动DELETE，设备TTL仍作为兜底。Session到期、v2 revoke、v1 cancel/consent(false)、BLE断连或Wi-Fi station断连时整会话撤销并停止AP/HTTP；设备HTTP socket收发超时2s。已经授权进入发送的一个≤16KiB块是不可收回的在途事务；撤销最多等待该块2s socket超时，之后不能再读下一块，不能宣称硬件瞬停。

接口不会将HTTP写成功、BLE ATT成功或可编译固件标为已拍摄。当前所有板卡应持续返回无帧；采集解锁必须另提交已审核物理指示联动profile及实测证据。
