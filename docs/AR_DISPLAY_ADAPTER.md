# AR 显示适配：可执行的中文 HUD 栅格化

验收日期：2026-11-11。对应 F15 中文HUD软件准备、F17/F20短句反馈。当前完成的是内存图片栅格化与显示适配契约，不代表 Halo、BLE 图片发送或眼镜光学显示通过。

## 已实现与验证

`app/hud_bitmap.py` 使用现有 Pillow 依赖绘制中文，返回实际像素字节与尺寸，不依赖AI Key。默认256×256，可选打包单色1bpp和8bit灰度。最多3条实际文字行，首行为不能被模型文字或自定义标题覆盖的来源标识，余下最多2行为短答；按像素宽度换行，超出行数显示省略号并设置 `truncated=true`。

| 来源 | 显示规则 |
|---|---|
| demo或simulated=true | 强制首行 `【模拟演示】`；即使其他元数据声称live也优先标模拟 |
| live | 必须同时provider=openai、simulated=false，首行 `【真实AI·预览】` |
| 无来源或local | 首行 `【本地预览】`，不能标为真实识别 |

来源标识来自调用方提供的HTTP结果元数据，不是模型鉴权证明。真实AI效果仍需合法服务端密钥、云端返回和图片人工核对；渲染器不会因为画出live标识就将该步骤计为真实识别成功。

2026-11-11实际执行：

```powershell
python -m unittest discover -s tests -p test_hud_bitmap.py -v
```

结果：**14/14通过，0 skipped，0.049秒**。覆盖实际中文栅格、不同文字不同像素、来源标识、最多3行、省略、缺字/缺字体错误、灰度阈值、MSB位序、奇数宽度行填充、尺寸边界、无落盘、默认拒绝发送、内存sink及错误长度/灰度格式拒绝。测试中的sink是明确内存替身，没有设备通信。

项目另已完成XiaoMi摄像头640/1920本地验收；这属于摄像采集证据，不扩展为光学显示或真实AI效果通过。本步骤只读取固定非敏感样张，没有打开摄像头或将个人内容保存到公开文件。

## 调用与字体

```python
from app.hud_bitmap import render_hud, BitmapDisplayAdapter

# 将 /api/ask 返回的 hud 字典传入，保留其mode/provider/simulated来源字段。
bitmap = render_hud(
    {"mode": "demo", "provider": "demo", "simulated": True,
     "lines": ["请按键拍摄", "结果显示在此"]},
    font_path="C:/Windows/Fonts/msyh.ttc",
    pixel_format="mono1_msb",
)
assert (bitmap.width, bitmap.height, len(bitmap.payload)) == (256, 256, 8192)
preview = bitmap.to_image()  # 仅内存Pillow Image；不自动save/send

adapter = BitmapDisplayAdapter()
assert not adapter.ready
# adapter.publish(bitmap) 将抛DisplayUnavailable；默认不会发送像素。
```

返回 `HudBitmap` 包含 `width`、`height`、`pixel_format`、`stride_bytes`、`payload: bytes`、实际 `lines`、`source`、`truncated`。一般渲染调用没有磁盘写入、网络请求或设备选择，也不记录文本日志。调用方应避免记录含私人内容的对象；本地缓冲生命周期由调用方控制。

字体优先由调用方显式传 `font_path`。未传时只尝试系统Windows目录的 `Fonts/msyh.ttc`（本机Microsoft YaHei可用），不下载、不复制或提交字库。没有可读字体、字体损坏或所需字符缺字时明确抛 `FontUnavailable` / `UnsupportedGlyph`，不会静默改用无法绘制中文的字体或输出缺字方框。其他系统应提供已获使用授权且包含所需中文字形的字体路径。字号默认24，可配置10–64；排版空间不够时明确报错。

## 与当前固件的边界

已核对 `firmware/main/display_adapter.h` 和 `.c`：C接口接受指针、字节长度、width、height；尺寸必须1–256，字节数必须 `ceil(width/8) * height`；没有reviewed sink时返回 `GL_DISPLAY_UNCONFIGURED`，不会调用驱动。

| Python像素格式 | 行布局 | 256×256字节数 | 当前固件 |
|---|---|---|---|
| `mono1_msb` | 从上到下逐行，每行从左到右；高位对应左侧像素；1为白、0为黑；每行独立补齐到字节 | 8192，stride=32 | 字节长度/尺寸契约匹配 |
| `gray8` | 从上到下逐行，每像素1字节；0黑、255白 | 65536，stride=256 | Python适配器明确拒绝直接投递，不能冒充1bpp |

单色转换显式阈值默认128，范围1–255，无随机抖动。9像素宽的每行占2字节；测试确认首行第0和第8像素为白时得到 `80 80`，下一行第7像素为白时得到 `01 00`，不会将行尾填充当成下一行。

**C接口目前只校验尺寸与长度，没有声明位序、黑白极性、旋转、厂商指令或像素格式字段。** `mono1_msb` 的MSB位序和极性是本主机实现的明确约定，尚不能声称已匹配任一真实屏幕驱动。后续sink必须逐项确认并按设备格式转换；若建立媒体传输协议，应携带像素格式/stride/尺寸/序号并按带宽和MTU实现分片、超时、取消，而不是直接一次BLE写入8192字节。

`BitmapDisplayAdapter(reviewed=True, sink=...)` 仅是调用方显式绑定已审核sink的接口；本模块没有绑定任何真实sink。固件 `main.c` 的默认显示适配器仍未配置；未假设ESP32-S3具有任意AR/MIPI显示能力。屏幕端也不依赖直接绘制多字节UTF-8，中文字形已在主机转成像素。

## 固定样张与视觉核验

```powershell
python -m app.hud_bitmap --sample
python -m app.hud_bitmap --sample --pixel-format gray8
```

只有该显式CLI样张模式写入磁盘，内容固定为 `【模拟演示】 / 请按键拍摄 / 结果显示在此`。输出为现有 `.gitignore` 已忽略的路径：

- `artifacts/private/ar/hud_demo_mono1_msb.png`、同名 `.bin` 与 `.json`。
- `artifacts/private/ar/hud_demo_gray8.png`、同名 `.bin` 与 `.json`。

已分别用 `view_image` 打开两张256×256 PNG：3行中文可辨，无乱码/裁切；首行模拟来源清晰；单色版为黑白栅格，灰度版保留字体抗锯齿。二进制长度分别8192与65536字节，metadata明确 `hardware_verified=false`、`delivered_to_device=false`。这些是软件像素证据，不是透视光学截图。

## 下一条显示验收

选择明确可用的AR显示控制器或官方Halo bitmap通道，确认像素格式、旋转与供电时序，绑定已审核sink后发送固定样张，再记录设备回执/实机照片、可读性、中文笔画、亮度与退出/取消行为。官方Halo emulator本步骤未安装或执行，旧Lua接口也未因此变成已验证；真实光学HUD、BLE媒体链路和Halo SDK适配仍需独立证据。缺少AI Key不阻塞这些显示接口与本地图像测试。
