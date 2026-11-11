# 接管与开发日志

## 2026-11-11 · Sprint03 Windows+iPhone

沿用既有工程，新增Flutter Web getUserMedia/ASR/TTS桥、同源TLS配对网关、Codemagic无签名任务、iOS CoreBluetooth/URLSession与ESP32临时BLE/Wi-Fi JPEG协议。根README/AGENTS、架构和22项三层矩阵同步；0完成/12部分/10未实现不变，光学AR/镜片/佩戴/PCB仍为P0。

实际完成本地TLS与Windows WLAN smoke（合成图片，cloud_sent:false）、Flutter Web与Android构建、固件三配置编译及各层自动测试。发现并修复静态路径隔离/Windows端口复用问题，跨端ACK与实际处理异步需要request_id关联与有界只读等待；最终数量/哈希见 [SPRINT_03.md](SPRINT_03.md) 及其证据，不把旧日志升级为当前通过。

本轮没有API Key、Mac/Android设备、远程仓库或Codemagic连接，未调用真实AI、未运行云构建/Swift编译、未实测iPhone或烧录眼镜。私钥/配对文件仅本机忽略目录，测试不改系统信任/防火墙、不发送照片外部。原生UI/安装、硬件无线/采集与光学/机械仍按报告明确待验。

## 2026-11-10—11 · Sprint02

本轮保留现有架构和22项冻结需求，新增实际Flutter项目、ESP-IDF工程、8/20byte BLE控制/状态契约、中文HUD栅格化、结构化双向OCR与取消、本地摄像验收及20图批量工具。Git已建立并保留Sprint01基线，密钥/真实图片/详细报告/构建缓存均排除。完整代码、测试、真实环境三层结果和剩余阻塞见 [SPRINT_02.md](SPRINT_02.md)。

2026-11-11复核：Python90项、其中包装执行Node25项通过；固件Host20项、默认与EYE两profile交叉编译通过；Flutter静态分析与18项测试通过，具体平台构建最终状态见 [MOBILE_APP.md](MOBILE_APP.md)。中文HUD14项已包含在Python90项内，不重复计数。

用户明确本轮不提供Key且不再询问，因此真实AI20图均blocked/unknown，不能写成质量通过。用户另明确授权非敏感XiaoMi Webcam本地测试，实际浏览器640×480与DirectShow1920×1080采集/本地预览/上传校验通过，相机已关闭，未上传外部服务。AR光学显示、手机/眼镜实机、镜片/机械及PCB仍待验。

## 2026-11-10 · Sprint-01 真实视觉软件闭环

目标：保留现有 Python localhost API / 浏览器手机中枢 / Halo 分层，完成可接真实模型的「当前图像→上传→视觉理解或OCR翻译→HUD反馈」软件链路；Demo 与真实结果明确隔离。硬件、原生 App 与云端效果单独验收。

### 接管审查

- 已读取根 AGENTS/README、docs、app、firmware、hardware、halo、protocols、tests、web 全部初始文件，以及上级 PRD V2.0。初始9项 unittest 全通过；原测试不证明真实图像理解。
- 整机功能：0已实现、11部分实现、11未实现，逐项条件和证据见 [TRACEABILITY.md](TRACEABILITY.md)。22项冻结要求完整保留，16P0/5P1/1R；特别保留 F15/F17/F19/F20/F22 首代P0。
- 初审发现：视觉可无图、只验字符串长度、缺少显式上传同意、Live缺配置阻止服务启动、无统一错误HUD、HUD最多5行违反PRD最多3行。任务仅本地确认，F07无真实提取，F05无会话上下文，Flutter/ESP32/光学显示未实现。
- 根目录没有 `.git`；未创建或伪造 commit。原始 app/web/tests/docs/protocols/README/启动脚本已备份到上级 `.ai-glasses-backups/20261110-baseline`，需要回滚时先停止新服务再按文件恢复。

### 实现与验证

| 子能力 | 本轮实现 | 验证证据与边界 |
|---|---|---|
| 图像采集/选择 | 相机独立同意、采集当前静态帧、预览后点击提交；本地文件可替代相机 | Node测试模拟相机/权限；真实浏览器用合成标签测试选择/提交；未启用用户真实摄像头 |
| 图片传输与安全 | JSON请求≤3MiB，JPEG/PNG原始及清理后≤2MiB，≤1600万像素，实际解码/MIME核验，清除EXIF/GPS/PNG元数据/尾随内容并校正方向 | `test_vision.ImageTest`：有效JPEG/PNG、0/1/2MiB、超限、坏Base64/MIME/截断/像素、元数据与尾随字节 |
| 真实视觉问答与OCR翻译 | 保留Responses适配，强制有图和consent=true；OCR high detail，要求可核对原文/译文与不确定提示；store:false；服务端环境变量密钥 | Provider与真实本地HTTP集成使用明确响应桩；证明图片进入适配器且文本回到HUD，不能计为真实模型成功/准确率 |
| Demo/Live隔离 | 请求与响应mode/provider/simulated/request_id，HUD/结果/播报明确来源；Live失败不回退 | HTTP与21项Node契约；浏览器Live无Key错误、主动切Demo标模拟；未知provider拒绝 |
| 异常和重试 | 缺Key服务仍能启动并报告ready=false；503配置错误、504模型超时、断网/坏响应/拒绝/空结果均失败；只对明确暂态HTTP最多两次attempt | Provider失败路径测试；全新子进程无Key启动后health及503验证；未使用有效Key连接云端 |
| HUD反馈 | loading/result/error、最多3行×28字符和截断提示，详细回答保留在页面 | 核心/HTTP/Node测试；实际浏览器页面与来源截图 |
| 并发及隐私 | 删除时停止浏览器媒体/清理帧/输入/授权；服务在读请求体前记录隐私epoch；旧上传/旧推理不恢复已删状态；任务卡替代旧推理 | 复现并修复慢上传删除后恢复笔记、旧推理覆盖新任务卡；socket+thread同步回归和前端迟到响应测试 |
| 语音与确认 | 浏览器语音服务另行同意，单次识别可停止；转写先核对，保存前确认；播报只读有效结果并标明Demo；任务仍confirmed_local_only | Node语音能力/同意/退化/笔记确认测试；未验证真实麦克风、浏览器ASR服务、TTS声学或眼镜音频 |
| 验收工具 | `tools/verify_live.py`需--consent-upload，限定loopback、禁止代理/重定向、严格拒绝Demo，只输出metadata | 10项工具测试与--help通过；真实图片+有效Key验收未运行 |
| 硬件架构 | ESP32-S3/相机/音频/电池/独立AR显示拆分、物理灯、电源/Pin Map/测量门槛，机械及配镜P0 | 官方资料核验与文档审查；无最终PCB/Gerber，没编造GPIO、实测功耗或器件报价 |

补充：上游超时是socket无活动限制，不是严格总deadline；浏览器另有等待上限。取消不会保证撤销已经到达供应商的处理或费用。当前仅localhost单用户进程内存，不支持手机LAN直连、账号隔离或持久化。完整契约见 [HTTP_API.md](../protocols/HTTP_API.md)。

### 最终执行结果

环境：Windows；Python 3.14.6，Pillow 12.2.0，Node v24.22.1。日期按 Asia/Shanghai。无 OPENAI_API_KEY；未找到 Flutter、Lua、Halo emulator。全部测试默认隔离网络，不保存个人媒体。

| 命令 / 检查 | 实际结果 | 原始证据 |
|---|---|---|
| 接管前 `python -m unittest discover -s tests -v` | 9/9通过，0.550s | [AUDIT_BASELINE.md](AUDIT_BASELINE.md)记录初始输出 |
| 最终同命令 | 48/48通过、无skip；其中1项入口运行21项Node测试，不能再把这21项当成额外Python用例 | [unittest.txt](evidence/unittest.txt) |
| `node --test tests/web_client.test.cjs` | 21/21通过，无skip、无fail | [web-tests.txt](evidence/web-tests.txt) |
| `python tools/verify_live.py --help` | exit 0 | [live-verifier-help.txt](evidence/live-verifier-help.txt) |
| 全新子进程设置AI_PROVIDER=openai、Key为空 | health ready=false；POST返回503 AI_NOT_CONFIGURED；无answer | [validation-summary.json](evidence/validation-summary.json) |
| PowerShell Parser检查start-live.ps1 | PASS，无语法错误 | 本轮执行输出；脚本不包含Key |
| F01–F22矩阵静态检查 | 22项无重复；16P0/5P1/1R | [TRACEABILITY.md](TRACEABILITY.md) |
| 交付文件校验 | 文档本地链接存在；文本未发现API Key形状的凭据；源码SHA-256清单已生成 | [source-sha256.json](evidence/source-sha256.json)，不含自身/二进制截图/缓存 |
| 实际浏览器 | 真实模式缺Key清晰失败；主动切Demo后图片提交更新HUD并标注模拟，再切Live仍失败 | [缺Key截图](evidence/live-missing-key.jpg)、[Demo图像HUD截图](evidence/demo-image-hud.jpg)；图片为[合成标签](evidence/synthetic-label.png)，不是识别样本 |

浏览器检查使用隔离端口8876，因为原8765已有进程；没有终止用户原进程。检查后已停止本轮测试服务，未留下假定为最新的旧后端。重新启动时应确认端口和后端版本；仅刷新网页不会重新加载Python后端模块。

### 尚未验收及可直接复现的下一步

1. 在服务端终端配置 OPENAI_API_KEY（不要写进源码或聊天），设 AI_PROVIDER=openai，按README重启；用可传云非敏感图分别运行 vision 与 translate。自动化工具只能验接口，还需人工逐字段核对OCR/译文/视觉答案。
2. 用真实摄像头完成单帧采集与授权拒绝/撤回测试；建立固定图像及人工答案集，再测≥50轮各阶段延迟。当前无真实AI成功率、OCR准确率或P95数据。
3. SW-02 Flutter手机工程与BLE适配尚未开始；现有浏览器不是手机原生App。AR-01官方emulator尚未安装/执行，Lua示例保持未验证。AR-02真实中文光学HUD需设备和栅格化链路。
4. F05上下文、F07摘要/任务提取、F08真实白名单外部执行、F11遥测/升级、P1增强仍按矩阵推进；外部动作保留显式确认，不把本地确认当外部成功。
5. ESP32-S3开发板/OV2640/音频/电池及独立AR显示先做实测，按硬件架构门槛固定Pin Map/功耗/显示方案，再进入原理图/ERC/DRC与PCB；佩戴/配镜始终为P0。
