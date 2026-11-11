# ESP32-S3 设备固件（Sprint-03）

本目录现在是实际ESP-IDF工程，固定官方 **ESP-IDF v5.4.3**、`espressif/esp32-camera 2.0.16`，依赖解析结果见 `dependencies.lock`。保留主项目手机/云推理与独立AR显示架构。

Sprint03加入保持BLE v1兼容的v2媒体会话控制、默认禁用的开发Wi-Fi AP、短期token保护的本地HTTP JPEG分块拉取。完整协议见 [`protocols/DEVICE_MEDIA_V1.md`](../protocols/DEVICE_MEDIA_V1.md)，本轮证据见 [`docs/FIRMWARE_SPRINT03.md`](../docs/FIRMWARE_SPRINT03.md)。iPhone使用原生CoreBluetooth；本项目不声称Safari可以执行Web Bluetooth。

默认 `board_unconfigured` 不接触相机/音频/按键GPIO。可选择官方ESP32-S3-EYE-MB v2.2参考profile，但该板的GPIO3是电源LED，并非摄像采集联动指示；两种profile均固定 `privacy_interlock_verified=false`，所以**当前固件拒绝实际相机初始化/抓拍**。不能通过一个软件勾选宣称硬件隐私验收通过。

## 实现范围

| 模块 | 内容 | 边界 |
|---|---|---|
| `main/core.[ch]` | 固定版本控制协议、采集门控/取消/同意、状态、最近16请求去重、16条错误环日志 | 纯C可host编译；错误日志只有数字代码、时间和请求ID，不含媒体/文本；日志仅RAM，当前无BLE历史日志读取 |
| `main/ble_control.c` | NimBLE peripheral：加密write/read/notify、SC-only、bond store初始化、通知在host任务串行执行 | 仅BLE控制；Just Works没有MITM保护/所有权确认，设备绑定策略仍待实现；没有经典HFP/A2DP通话 |
| `main/button.c` | 官方profile的GPIO0运行时按键，30ms消抖、短按请求采集、1s长按撤同意并取消、3s打开30s物理配对窗口 | 默认无GPIO。GPIO0也是下载启动绑带，按住上电会影响启动；未硬件实测 |
| `main/camera_adapter.c` | 官方驱动JPEG/VGA/PSRAM适配、授权与初始化同锁、真实帧consumer、归还帧并deinit | 必须板卡+物理隐私联动审核；当前无profile放行。未来已审核采集可交给活动媒体会话的RAM帧存储；没有活动媒体会话则明确MEDIA_NOT_CONFIGURED |
| `main/main.c` | 事件队列、状态锁、epoch撤销保护、disconnect/撤同意/长按优先失效旧队列 | 防已出队的旧同意/旧结果恢复；硬件瞬停与取消时延仍需实测 |
| `main/display_adapter.[ch]` | 主机栅格化后的1bpp bitmap接口，最大256×256；默认拒绝未配置/未审核driver | 无ESP32-S3直驱AR/MIPI假设；未接光学显示，未执行Halo API |
| `main/media_core.[ch]` | v2控制帧校验、短期Bearer会话、帧ID/长度/哈希、单帧RAM留存、严格HTTP Range解析 | Host fixture验证存储/协议；不证明实际JPEG解码、无线传输或采集 |
| `main/media_service.c` | 官方esp_wifi/esp_http_server/mbedtls适配；主动物理配对后启动开发AP，认证状态/分块JPEG/DELETE | 编译开关默认禁用，全部相机profile仍锁定；无外部上传/Bonjour/NAT；WPA2+本地HTTP为开发链路，不是生产TLS/所有权验收 |

电量固定为unknown（编码255），无虚构电池百分比。音频、OTA、云API和AR光学驱动未实现；Wi-Fi/JPEG媒体适配已编码、默认禁用且未做物理链路验收。固件不存AI密钥，不提供设备向外部地址上传的接口。

## Host C测试

需要C11编译器。通用用法：

```powershell
python firmware/tests/run_host.py --cc gcc
```

本机已安装的独立工具路径：

```powershell
python firmware/tests/run_host.py --cc C:/codex-tools/glasses-host/ziglang/zig.exe
```

脚本调用Zig 0.13.0自带Clang前端，以 `-std=c11 -Wall -Wextra -Werror -pedantic` 编译实际C模块和两个测试exe后执行。当前 **38/38通过**：原20项核心/display测试，加18项v2/媒体存储/TTL/token/URI/Range/分块重组、清零和会话JSON请求ID关联测试；原协议长度/字节约200万组合断言仍保留。结果见 `evidence/host-tests-sprint03.txt`。媒体fixture仅含测试字节，不代表物理采集或完整JPEG解码通过。

## ESP-IDF交叉编译

已有官方v5.4.3工具环境时，**在ASCII且无空格路径的项目副本**中执行：

```powershell
idf.py set-target esp32s3
idf.py build
```

本仓库上级路径含中文/空格，因此提供 `tools/build_idf.py`，复制源文件到显式指定的ASCII工作目录后调用真实 `idf.py build`，不烧录、不删除目录、不自动安装工具。官方registry会下载固定camera依赖；首次构建需要网络。可复现本机命令（从项目根目录）：

```powershell
python firmware/tools/build_idf.py `
  --idf-root C:/codex-tools/glasses-idf/sdk/esp-idf-v5.4.3 `
  --workspace C:/codex-tools/glasses-idf/work `
  --python C:/codex-tools/glasses-idf/venv/Scripts/python.exe `
  --tools-root C:/codex-tools/glasses-idf `
  --tool-bin C:/codex-tools/glasses-idf/unpacked/xtensa-esp-elf/bin `
  --tool-bin C:/codex-tools/glasses-idf/unpacked/cmake-3.30.2-windows-x86_64/bin `
  --tool-bin C:/codex-tools/glasses-idf/unpacked `
  --tool-bin C:/codex-tools/glasses-idf/unpacked/esp32ulp-elf/bin
```

增加 `--board eye-v22` 在独立工作目录构建参考板profile；仍拒绝摄像采集。官方环境下等价默认配置选择为：

```powershell
idf.py -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.eye.defaults" build
```

不同profile请使用独立build/sdkconfig，避免旧配置覆盖defaults。wrapper分别写入 `work/unconfigured/project` 与 `work/eye-v22/project`，保留其构建产物。结果/源文件哈希在 `evidence/build-*.json`，实际输出在 `evidence/idf-*.txt`。真实交叉编译成功只说明工程可编译，不证明ESP32、BLE、传感器、指示灯或显示已实测；本轮没有烧录设备。

开发AP的显式编译检查使用另一独立ASCII工作目录，并在该目录的 `eye-v22/project/sdkconfig` 预置 `CONFIG_GL_MEDIA_DEV_AP=y` 及 `CONFIG_PARTITION_TABLE_SINGLE_APP_LARGE=y`，再以相同wrapper参数加 `--board eye-v22` 构建；不会改变源代码默认开关或解锁相机。AP开启的镜像超过默认1MiB app分区，参考板检查须选择官方1500K factory分区（无OTA；仅核对8MB EYE配置，不能推导其他板卡容量）。该检查的结果使用 `evidence/build-eye-v22-ap-enabled.json`、`evidence/idf-eye-v22-ap-enabled.txt` 单独记录，常规EYE关闭AP的结果仍保留。仅开启编译开关不会自动启动网络，仍需真实物理按键窗口及加密BLE显式open。

安装其他机器工具时使用官方 [v5.4.3 Windows安装说明](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32s3/get-started/windows-setup.html) 与 [工具清单](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32/api-guides/tools/idf-tools.html)，Python依赖遵循该版本官方constraints。不要把工具链、venv、managed_components或AI Key提交仓库。

## BLE v1控制契约

服务UUID `8f13a001-6c55-4b8e-9d51-2f76a4b10000`；控制write `8f13a002-6c55-4b8e-9d51-2f76a4b10000`；状态read/notify `8f13a003-6c55-4b8e-9d51-2f76a4b10000`。值固定8/20字节，适配最小23字节ATT MTU；所有多字节整数little-endian。不是 `protocols/events.schema.json` 已落地的声明；此为低层二进制控制适配，与app-level JSON事件分层。

控制8字节：

| 偏移 | 字段 |
|---|---|
| 0 | version，固定1 |
| 1 | opcode：1 status；2 capture；3 cancel；4 consent；5 clearlog |
| 2–3 | request_id，uint16，手机在连接内递增，最近16个普通变更请求去重 |
| 4–7 | argument，consent只允许0/1；其他命令必须0 |

示例：`01 04 01 00 01 00 00 00` 同意；`01 02 02 00 00 00 00 00` 抓拍请求；`01 04 03 00 00 00 00 00` 撤同意。重复ID的cancel/撤同意仍优先生效；status不消耗去重ID。无图像、音频、云密钥或外部任务执行命令。

状态20字节：

| 偏移 | 字段 |
|---|---|
| 0 | version=1 |
| 1 | state：0 idle，1 capturing，2 error |
| 2 | flags：bit0 connected，bit1 consent，bit2 board_configured，bit3 physical_privacy_verified |
| 3 | last_error，见下表；未知值保留原始整数 |
| 4–5 | request_id |
| 6 | battery_percent；255=unknown，本轮不测电量 |
| 7 | RAM错误环条目数，0–16 |
| 8–11 | uptime_ms（uint32会回绕） |
| 12–15 | 成功采集计数，当前profile应始终0 |
| 16–19 | 累计错误计数，清除环日志不重置累计值 |

错误：0 OK；1 BAD_FRAME；2 BOARD_MISSING；3 PRIVACY_UNVERIFIED；4 NOT_CONNECTED；5 NO_CONSENT；6 BUSY；7 CAMERA_FAILED；8 MEDIA_NOT_CONFIGURED；9 DUPLICATE；10 QUEUE_FULL；11 STALE_EVENT。传输层坏长度/版本/字段直接ATT错误，未必写入状态；DUPLICATE/STALE_EVENT是core返回值，未必覆盖最新last_error。先读配置/权限，再发命令，不能把ATT写成功当作已拍照/上传成功。

## 官方板级来源

[ESP32-S3-EYE-MB v2.2原理图](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-EYE-MB_20211201_V2.2.pdf)第3/4页与[官方BSP板卡描述](https://github.com/espressif/esp-bsp/blob/master/bsp/esp32_s3_eye/esp32_s3_eye.json)用于核对事实；未复制原理图/PCB。camera D0–D7=11/9/8/10/12/18/17/16，XCLK15，PCLK13，VSYNC6，HREF7，SCCB4/5；RESET/PWDN无可控GPIO。只适用于该板版次。麦克风虽有官方映射，本轮没有音频器件初始化，也不假设存在扬声器。

物理灯联动、板号/排线、功耗/温升、电源与AR光学显示仍按 `docs/HARDWARE_ARCHITECTURE.md`、`hardware/PCB_CHECKLIST.md`执行。不得把当前二进制直接称作可佩戴整机固件。
