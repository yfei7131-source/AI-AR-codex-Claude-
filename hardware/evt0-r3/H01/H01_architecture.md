# EVT-0 R3 系统设计

本次沿用 [PRD V2.0](../../../hardware-h01/AI_AR眼镜_首代功能需求与样机路线_PRD_V2.0.md)、[冻结需求](../../../docs/FEATURES_F01_F22.md)、[软件验收](../../../docs/TRACEABILITY.md)。[22项逐行分配](F01_F22_trace.csv)和[12项接口裁决](ICR_to_Codex.md)分别记录验收责任和具体接口。保留 16 P0、5 P1、1 预研；裸镜 50 g 目标、55 g 警戒，配镜后另称；25°C 指定工况皮肤接触面目标 ≤41°C，4h 不适 ≤2/10，均待实测。

**采集与手机。** EVT-0 使用 ESP32-S3-WROOM-1-N16R8 的 DVP/JPEG + BLE/Wi-Fi。EYE V2.2 原板是引脚参照；S3-CARRIER-A 是另一个开发板台架。USB/电池→BQ24072 OUT→3.3 V LDO 为 MCU 供电；受控相机轨、与模拟电源直接关联的外向指示灯、GPIO0 按键独立。J3/R16/R17/R18 初装 DNP。原 EYE OV2640 参考排线 J4 针 4/10/11 分别为 2.8/1.5/2.8 V，R2 的 J3 候选针 4/10/11 分别为 2.8/1.2/3.3 V。相同网络名称不会使三路电压等价。供应商须给出相机订货号、模组电路、FPC 触点方向/尺寸、工作和绝对额定值、RESET/PWDN 与时序，再确定选配料；更换 DVDD LDO 时另行评审。

**数据流。** IDF 5.4.3 + esp32-camera 2.0.16，见 `firmware/dependencies.lock`。短按/长按沿用 `button.c`，BLE v1 a002 8 B / a003 20 B；v2 加密 a004 20 B 写会话命令、a005 Read Long 回会话 JSON。原生 iOS `GlassesBleBridge.swift` 与 `DeviceImageTransfer.swift` 负责控制和 JPEG。开发 AP 默认禁用；启用后还需要物理窗口、加密会话和用户同意，每次仅传 RAM 单帧。设备发随机 AP 口令与短时 bearer；手机每次 Range 最多 16 KiB，验总长度及 SHA256 后 DELETE。用户另行同意才把图交给已有 AI 接口。Swift / iPhone / 实机电流与时延见 H05 待测；协议契约见 [DEVICE_MEDIA_V1](../../../protocols/DEVICE_MEDIA_V1.md)。

**眼前显示。** V1 必须经显示控制器、微显示与光学系统向眼前投像。M1 用一套完整 Brilliant Halo 验收，包括 VGA020 微显示和原厂光学系统，手机/主机走厂商 SDK；HUD 可绘区为圆形 256²。自研 M3 的 J4 作为隔离预留，收到匹配的光机+波导图纸、显示协议、电平、上电顺序、机械基准后再布其连接器。独立评估不会证明 J4 支持 Halo 或其他裸屏。[Brilliant 硬件](https://docs.brilliant.xyz/halo/hardware/)。

**已验证的软件通路。** 从仓库根执行下列命令，可复现 [Halo 台架适配工具](halo_hud.py)。它调用 `app.hud_bitmap.render_hud` 保留来源标识，192×128 文本区域居中置入 256 圆屏，1bpp MSB，索引 0 透明，先清屏。根据实际 Lua payload 对图像分条并检查每次 ACK。独立 Python 环境用于隔离 emulator 与主项目的 Pillow 版本。以下版本来自同一[官方 SDK 提交](https://github.com/brilliantlabsAR/brilliant_sdk/tree/9d17e96ce1b0f1d33d270315a3816d2e8cd0523b)。

```powershell
py -m venv "$env:TEMP/evt-halo-env"
$envPy = "$env:TEMP/evt-halo-env/Scripts/python.exe"
$base = 'git+https://github.com/brilliantlabsAR/brilliant_sdk.git@9d17e96ce1b0f1d33d270315a3816d2e8cd0523b'
& $envPy -m pip install ("halo-emulator @ " + $base + "#subdirectory=python/packages/halo_emulator") ("brilliant-ble @ " + $base + "#subdirectory=python/packages/brilliant_ble")
& $envPy -m hardware.evt0-r3.H01.halo_hud
```

本机官方 Halo Emulator 2.3.0 在 160/244/509 B 三种命令上限分别执行 60/32/17 条命令，65,536 个二值像素均与主机期望相同，帧哈希 `9119c9f34a572e20a4de3742c3f54b2c5d27b98f41aad0a17cc10cde9ac45786`。固定样张只包含演示中文；Windows 默认微软雅黑字体。真机在 Lua REPL 模式下可加 `--halo-name "设备实际名称"`，显示 5 秒后清除，按 H05 记录眼盒/可读率。光学实测及 iOS 中的 Halo 发送尚未执行。[Halo SDK](https://docs.brilliant.xyz/halo/halo-sdk-python/)。

**音频与续航。** F03 先在借用/复用的独立音频 EVB 做来电双向闭环，省去首轮自研射频和声学板；GPIO 只用于控制，[音频接口](audio-interface.md)。R3 优先节省常开电流：默认关闭开发 AP、摄像跟随事件、RAM 留存≤15 s、HUD 按事件更新。台架的原厂 Halo、BM83 EVB 与 S3 具有独立供电，各自的电池容量不能相加计算整机续航。[功耗预算](power_budget.csv) 区分数据手册工作点、设计预留和待测。穿戴版按电池侧各任务实测平均功率与占空比计算 `t = 可用Wh / Σ(任务占比 × 电池侧平均W)`；直到取得 cell、光机与声学负载前不报续航/生产成本。
