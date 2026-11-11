# Sprint-02 固件开发与验证记录

开发日期：2026-11-10；最终证据复核：2026-11-11（Asia/Shanghai）。本工作包将原有仅路线说明的 `firmware/` 建成ESP32-S3实际可交叉编译工程，保持手机/云AI推理与独立AR显示分层。工具与SDK安装于项目外 `C:/codex-tools/glasses-idf`；没有烧录、采购或生成最终PCB。

## 已编码能力与验证

| 功能 | 代码 | 实际验证 | 仍未验证 |
|---|---|---|---|
| 固定BLE控制/状态协议 | `firmware/main/core.c`、`ble_control.c` | Host执行C协议/state测试；ESP-IDF真实交叉编译 | 手机真实扫描/配对/GATT/重启重连与持久化 |
| 采集隐私门控 | `board.c`、`core.c`、`camera_adapter.c` | 无板卡、无物理灯审核、无连接/同意均拒绝；两种profile物理审核标志固定false | GPIO/相机真实采集、灯联动示波器核验、启动/故障/复位表现 |
| 按键 | `button.c` | 物理处理代码交叉编译；纯C短按/长按状态与撤同意测试 | GPIO0运行时按键、实际消抖/长按/启动绑带行为 |
| 取消/断连与旧事件保护 | `main.c`、`core.c` | 测试旧epoch同意拒绝、重复request_id撤同意生效、旧完成事件不计成功 | FreeRTOS/NimBLE实际调度、硬件终止时延 |
| 设备状态/错误日志 | `core.c` | 20byte LE状态、unknown电量、16条环日志溢出/顺序/清理 | 真实电池测量、OTA、BLE历史日志导出 |
| 相机适配 | `camera_adapter.c` | 官方camera组件固定依赖与适配器交叉编译；当前所有profile拒绝init | 真实OV2640 JPEG、清晰度/时延/PSRAM/功耗；JPEG无线媒体尚未实现 |
| AR display适配 | `display_adapter.c` | Host拒绝未配置/未审核sink；1bpp bitmap大小/边界；交叉编译 | 光学显示driver、中文主机栅格化到实机、供电/光学校准；未调用未经核验Halo API |

BLE服务与字节表完整见 `firmware/README.md`，手机适配器可按相同UUID和8/20byte LE契约对接。此协议是设备低层控制适配，不代表原app-level JSON协议或JPEG传输已完成。

## 真实构建与测试证据

可复现命令与完整安装路径见 `firmware/README.md`。结果文件：

- `firmware/evidence/host-tests.txt`：实际编译并运行纯C测试，**20/20通过**，编译选项含 `-Wall -Wextra -Werror -pedantic`；协议长度/版本/op组合约200万次断言。
- `firmware/evidence/idf-unconfigured.txt`：默认不配置板卡的真实 `idf.py reconfigure build` 成功输出，目标ESP32-S3。
- `firmware/evidence/idf-eye-v22.txt`：真实参考板profile构建完成1200/1200步骤、生成ESP32-S3镜像并通过分区容量检查。
- `firmware/evidence/build-*.json`：由构建脚本成功后生成bin路径、字节数、SHA256与对应源文件hash；`hardware_verified:false`、`flashed:false`固定明确边界。
- `firmware/dependencies.lock`：camera2.0.16、esp_jpeg1.3.2、IDF5.4.3及registry组件hash；许可核验见 `firmware/THIRD_PARTY.md`。

工具版本：ESP-IDF v5.4.3、Xtensa GCC14.2.0_20250730、CMake3.30.2、Ninja1.12.1、Python3.14（独立venv，官方v5.4 constraints）、Zig0.13.0 host Clang。上级中文/空格目录通过显式ASCII副本构建，不改项目目录布局。SDK源码内容未修改；官方release archive的本地Git设置忽略文件模式/子模块dirty扫描以避免解压后的跨平台扫描开销，该设置只在独立SDK副本生效。

### 最终交叉编译产物

| Profile | 实际结果 | 镜像字节数 | SHA256 |
|---|---|---|---|
| `unconfigured` | 成功；默认无板卡GPIO | 591168 | `802ece34e1a226ac72064a98ecf2ca6f999d23ae5aabaefbbf78a7dbe7f01df6` |
| `eye-v22` | 成功；S3-EYE参考管脚，摄像仍锁定 | 599840 | `24df911794730442e81a283cfe5b56477481f01833fc8abd5e5bd77b9b41e85b` |

2026-11-11独立复核：两个 `build-*.json` 均 `build_succeeded:true`，各18项源文件hash与当前仓库一致；重新读取实际 `.bin` 计算的字节数/hash与上表一致；生成的sdkconfig分别选择 `CONFIG_GL_BOARD_UNCONFIGURED=y` 与 `CONFIG_GL_BOARD_EYE_V22=y`；两个日志均包含 `Project build complete.`。因此无需重复下载工具链或重编译相同源码。实际bin保留在各metadata的 `binary_path` 所指ASCII工作目录，没有打包成眼镜实机交付，也未烧录。

本次日志包含一个非阻塞工具环境警告：`ESP_ROM_ELF_DIR`未设置，ROM符号的GDB初始化文件未生成。编译、链接、镜像生成和容量检查均已成功；后续使用ROM级调试前需补官方ROM ELF工具及环境变量，不将当前环境称为已完成JTAG/GDB实机调试。

## 本轮发现并修复

1. 单纯清空队列不能取消worker已出队的旧同意事件。现在事件入队、安全撤销和epoch检查同锁；旧epoch事件不再恢复权限，新增Host回归。
2. 请求去重不能阻止安全撤销。重复ID的cancel/consent(false)仍优先生效，新增Host回归；普通变更请求保持最近16个ID窗口。
3. 相机静态板级审核不足以说明当前仍有采集同意。适配器要求运行时授权gate，和初始化使用相同锁序列化；取消后旧结果不会登记成功。正在曝光的传感器能否立即停止仍需硬件实测，不声称软件锁实现物理瞬停。
4. NimBLE通知的连接句柄不能跨host/main任务混用。通知现在投递host事件队列后检查同一连接的加密状态再发送。
5. 仅配置NVS persist/bonding不足以初始化密钥存储。补官方v5.4.3支持的store_config初始化和store_status回调；真实重启后重新加密仍待设备测试。
6. Windows复制保留时间戳时新增源文件可能未触发已有CMake缓存重配置，曾导致display适配符号链接失败。构建wrapper改为每次显式 `reconfigure build`，并在构建前将metadata标记为未成功，防止失败后旧bin被误报为新结果；最终两profile成功产物均已按当前源码hash复核。

## 硬件与安全边界

官方S3-EYE参考板的电源LED不能冒充摄像采集指示灯。没有已验证的硬件联动profile，因此本轮抓拍功能有意保持锁定；不能在UI显示“已拍照/已上传”。即使将来加入审核通过profile，当前JPEG适配器在读取后立即归还帧并deinit，不落盘、不上传，并返回明确MEDIA_NOT_CONFIGURED状态。

BLE当前使用SC-only加密与Just Works配对；**没有**MITM保护、手机所有权确认、物理配对窗口或正式账号授权策略。只应作为受控开发链路，不能将WRITE_ENC或一次App同意标为产品安全验收完成。固件没有经典蓝牙音频、ASR/TTS、Wi-Fi媒体通道、OTA、电池电量计或实际AR驱动。

下一步需要实际开发板型号/版次、相机模组、联动物理指示方案与测量设备，先按 `HARDWARE_ARCHITECTURE.md` 验证，再开放新板级profile；随后真实手机BLE联调及JPEG媒体链路，最后连接独立光学显示。保留全部16项P0，不以本轮可编译固件替代F03/F10/F11/F15/F20整机验收。
