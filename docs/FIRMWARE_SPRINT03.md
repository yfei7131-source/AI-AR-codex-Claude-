# Sprint03：ESP32-S3 BLE控制与本地JPEG媒体适配

日期：2026-11-11（Asia/Shanghai）。保留既有ESP-IDF v5.4.3工程、固定官方camera依赖、官方S3-EYE管脚及独立AR显示分层；没有修改GPIO、解锁物理采集或烧录。本轮完成的是可测试/可交叉编译的设备软件适配，ESP32↔iPhone物理BLE/Wi-Fi链路仍未验收。

## 实现与协议

- 原BLE v1服务、8byte控制和20byte状态保持兼容；新增独立a004/v2 20byte会话控制与a005加密JSON Read Long，不把JPEG塞进BLE。iOS需原生CoreBluetooth，Safari不是该设备控制链路。
- a005 ready/error均附最后实际处理的v2 `request_id`（初始0），与ATT入队ACK分开；原生端必须匹配本次ID后接受结果，旧快照只允许有界轮询等待。显式revoke确认返回匹配ID的 `ready:false,error:revoked`，不把旧ready会话误认作新open成功。
- `CONFIG_GL_MEDIA_DEV_AP`源码默认n。显式编译启用后仍需真实按键≥3s打开30s配对窗口，再由原生App通过加密BLE主动申请≤120s媒体租约；没有远程开启物理窗口的命令。
- 每次会话生成随机SSID、WPA2口令和256bit token，RAM保存、不打印/持久化。开发AP最多1个station，无Bonjour、NAT或外网转发；只提供本地 `192.168.4.1` HTTP拉取。
- 认证 `GET /v1/media/status`、≤16KiB单闭区间Range JPEG拉取、DELETE释放；metadata含frame_id、v1 capture request_id、字节数和SHA256。无权401，无帧404，坏Range416；每块重新检查租约。
- 单帧≤2MiB、RAM留存≤15s；替换/DELETE/超时覆盖清零，断连/取消/撤同意/租约过期同时撤token。不会向外部地址上传，手机后续提交AI仍需独立用户授权。
- 相机实际framebuffer仅在通过既有物理审核及运行时同意gate后进入consumer；两种现有profile均 `privacy_interlock_verified=false`，所以设备现在不会产生真实captured帧，更不会用fixture伪造帧。无帧状态必须 `captured:false,frame:null`。

字节、UUID、HTTP字段、取消及错误语义完整见 [`protocols/DEVICE_MEDIA_V1.md`](../protocols/DEVICE_MEDIA_V1.md)。该协议与iOS适配代理已对齐。

## 可复现验证

Host命令（项目根目录）：

```powershell
python firmware/tests/run_host.py --cc C:/codex-tools/glasses-host/ziglang/zig.exe
```

**38/38实际编译执行通过**：原20项核心/display测试，加18项媒体测试。实际输出保存在 [`firmware/evidence/host-tests-sprint03.txt`](../firmware/evidence/host-tests-sprint03.txt)。新测试覆盖v2保留字段/版本、ready/error JSON的精确ID与截断/注入拒绝、最近ID在过期/撤权后保留、严格Bearer、无效租约、过期与uptime回绕、未审核拒绝发布、JPEG头尾与存储边界、删除/撤权清零、帧ID更替、15s TTL、URI/Range溢出与分块重组。测试fixture验证存储/协议，未证明传感器采集、完整JPEG解码或无线吞吐。

两种profile的常规ESP-IDF命令沿用 [`firmware/README.md`](../firmware/README.md)，工具已位于项目外ASCII路径。wrapper执行 `idf.py reconfigure build`，生成实际镜像与分区容量检查，不执行flash。显式AP检查仅在独立构建目录的sdkconfig预置 `CONFIG_GL_MEDIA_DEV_AP=y`、`CONFIG_PARTITION_TABLE_SINGLE_APP_LARGE=y`（官方1500K factory，无OTA），不改源默认值或板级隐私标志；用于保证默认禁用分支的Wi-Fi/HTTP代码也实际链接。

### 编译结果

| Profile | 配置 | 镜像字节数 | SHA256 | 证据 |
|---|---|---|---|---|
| unconfigured | AP默认关闭；无GPIO | 717776 | `f7852e2e24d9b641fc0796d28b1e89e6e190e92b063970fc8c6ffac120a2b662` | `firmware/evidence/build-unconfigured.json` |
| eye-v22 | AP默认关闭；相机锁定 | 726608 | `03a17b76d3ddbd2ca9c1b8e9ed0dc868a70585eba0232f8e3ae8cfa8fff50440` | `firmware/evidence/build-eye-v22.json` |
| eye-v22显式AP检查 | AP编译开启；官方1500K factory；相机仍锁定 | 1059168 | `923713365127b08df8280603a3907271c5410ccb0ab71028ee9f09ec916e0729` | `firmware/evidence/build-eye-v22-ap-enabled.json` |

每份成功metadata包含对应源文件SHA256、实际bin路径与 `hardware_verified:false`、`flashed:false`；完整输出在相应 `idf-*.txt`。已实际复算三份镜像大小/hash，并逐份核对22项源文件hash均与当前仓库匹配；两个常规profile的AP开关关闭，额外AP检查开关开启且选择large factory分区，生成的sdkconfig亦已记录hash。聚合复核结果在 [`firmware/evidence/sprint03-verification.json`](../firmware/evidence/sprint03-verification.json)，常规EYE的metadata/日志完整保留，没有被AP检查覆盖。

首次显式AP检查已实际完成编译/链接，但生成镜像1058736B，默认1MiB factory分区溢出10160B，容量检查正确拒绝；失败原始输出保留在 `firmware/evidence/idf-eye-v22-ap-initial-size-failure.txt`。后续仅对独立AP-check目录选择官方1500K factory分区，参考已知8MB EYE配置，不改变普通两profile或引入OTA声明；不能据此推断其他开发板可直接烧录。

复现额外AP检查时使用新的独立目录，例如 `C:/codex-tools/glasses-idf/work-ap-enabled/eye-v22/project`，在其sdkconfig设置上述两个选项，再运行README同一wrapper命令、将 `--workspace` 指向 `C:/codex-tools/glasses-idf/work-ap-enabled` 并加 `--board eye-v22`。已有sdkconfig需确保普通 `PARTITION_TABLE_SINGLE_APP`选项关闭，`PARTITION_TABLE_FILENAME`为 `partitions_singleapp_large.csv`。wrapper按board命名输出，额外检查后应把该次metadata/日志另存为 `*-ap-enabled.*` 并保留常规EYE记录；本轮已完成这种隔离。镜像只在外部ASCII工作目录生成，没有运行AP、烧录或执行GPIO采集。

## 验证边界与后续门槛

开发链路使用WPA2与短期Bearer本地HTTP，BLE为SC-only Just Works；未提供生产版端到端TLS、MITM/所有权确认或安全认证。HTTP发送锁保护一个≤16KiB事务，撤权可能等待正在发送块的2s socket超时；已经送到手机的字节必须由iOS取消时清理，设备不能回收这些字节。

没有真实开发板、联动物理指示、电源或iPhone安装/配对证据，因此F04/F09/F10/F20/F22只推进设备软件适配，不升级整机验收。需先核验实际板卡、相机、灯与供电/活动联动，再新增审核通过profile；当前profile持续锁拍。随后验证iPhone加入AP、BLE断连/复位、Wi-Fi断连、租约到期、逐块丢包/重取、完整SHA256、清晰度/时延/功耗和真实光学HUD。

所用官方API依据：[`esp_http_server` v5.4.3](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32s3/api-reference/protocols/esp_http_server.html)、[ESP32-S3 Wi-Fi v5.4.3](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32s3/api-guides/wifi.html)。固定camera/SDK许可与版本继续见 `firmware/THIRD_PARTY.md`，未复制未核验第三方固件或PCB。
