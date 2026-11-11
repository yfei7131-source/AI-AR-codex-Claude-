# 本地 HTTP API 契约 v0.3

2026-11-10。保留既有 `/api/*` 路径，`events.schema.json` 仍仅为设备消息草案，未实现 BLE 分包。服务为单用户、内存态 localhost 原型，不能直接部署公网/LAN。默认 127.0.0.1:8765；拒绝异源写请求和非本机 Host。无密钥时不会伪造 AI 成功响应。

Sprint03没有放宽此后端限制：iPhone Flutter Web通过独立 [本地TLS/Bearer网关](../docs/WINDOWS_IPHONE_GATEWAY.md) 访问相同API。网关验证同源/Host/限时凭据后，仅转发固定loopback后端并剥离外部认证头。设备BLE/Wi-Fi媒体是独立的 [DEVICE_MEDIA_V1](DEVICE_MEDIA_V1.md)，不使用此API传输设备控制。

## Health

`GET /api/health` 始终报告服务器可用性 `ok`，`ready` 只表示供应商本地配置有效，不证明远端鉴权、模型可用或网络连通。字段：`provider`=demo/openai，`mode`=demo/live，`ready`，`configuration_error`（无凭据），`max_image_bytes`=2097152，`request_timeout_seconds`（供客户端设等待预算）。未知供应商配置报未就绪，不自动回退 Demo。

## 视觉问答 / OCR翻译 / 对话

`POST /api/ask`，`Content-Type: application/json`，JSON 对象，总请求体 1B–3MiB：

```json
{"mode":"live","kind":"translate","question":"翻译画面中的文字","image_data":"data:image/png;base64,<base64>","consent":true}
```

- `mode`：demo 或 live；旧客户端省略时采用服务启动配置。浏览器/验收工具始终显式发送。Demo 即使服务配置为 live 也必须显式选择；Live 在服务未配置 openai 时返回 503。
- `kind`：vision/translate/chat；vision/translate 必须有图片；chat 可无图。
- `question`：≤500字字符串，vision/chat 不得为空；translate 空串使用默认问题。
- `image_data`：仅 JPEG/PNG base64 data URL，禁止远程图片URL，原始文件≤2MiB且≤1600万像素；校验 Base64、实际格式与 MIME 一致、文件结构和像素可解码。只发送校正方向后的首帧像素，移除 EXIF/GPS/文本元数据、其他帧与尾随字节；清理后同样≤2MiB。不保存本地媒体文件。
- `consent`：带图片时必须是布尔 `true`；字符串和数字均拒绝。此声明表示客户端采集了用户同意，不能替代原生权限或硬件指示灯。相机预览同意、上传同意和浏览器语音服务同意在 UI 分开处理。

成功 `200`：`answer` 为完整文字；`hud` 最多3行，每行≤28字符，超出以省略号提示，`truncated` 标示截断；`provider`、`mode`、`simulated`、`request_id` 同时返回并复制到 HUD。Demo 答案标“模拟演示”；Live 不使用固定回答兜底。

错误：`{error,code,hud,request_id}`，无 `answer`。常见 `400 IMAGE_REQUIRED/INVALID_IMAGE/INVALID_REQUEST`，`403 CONSENT_REQUIRED/ORIGIN_DENIED`，`413 BODY_TOO_LARGE`，`415 INVALID_CONTENT_TYPE`，`503 AI_NOT_CONFIGURED/AI_CONFIG_INVALID`，`502 AI_HTTP_ERROR/AI_UNREACHABLE/AI_INCOMPLETE/AI_EMPTY_RESPONSE/AI_REFUSAL/INVALID_AI_RESPONSE`，`504 AI_TIMEOUT`，`409 REQUEST_SUPERSEDED`。当前有效识别错误同步到 HUD；已被删除、新识别或任务卡替代的旧请求不会覆盖新 HUD。

上游固定为官方 HTTPS Responses API，不跟随重定向。使用 `input_image`，OCR `detail=high`、视觉问答 `auto`，`store:false`、只接收已完成且有文字的回答。默认 socket 无活动超时12s，1–30s可配；明确 HTTP 429/500/502/503/504 可等待0.25s重试，attempts=1或2。网络错误/超时不自动重试，也不回退 Demo。`request_timeout_seconds` 为通常连接预算（默认25s），不是严格总deadline：慢滴连接可能延长上游读取；浏览器在预算+15s后中止等待。用户取消不能保证撤销已发出的云端处理/费用。云端质量、保留政策和实测P95独立验收。

## 状态、笔记、任务及删除

原有 `GET /api/state`，`POST /api/notes {text}`（≤2000字），`POST /api/tasks/draft {text}`（≤500字），`POST /api/tasks/confirm {id}` 保持路径。任务确认只产生 `confirmed_local_only`，不会调用外部系统；笔记为进程内状态，重启丢失。浏览器保存前明确核对确认。

`POST /api/privacy/delete {}` 清除服务器进程内笔记/任务/HUD；浏览器还停止相机/语音、清除图片/输入/授权勾选、丢弃迟到响应。删除前已进入服务的慢上传/推理不能在删除后恢复状态；删除不控制已发往云端的数据、浏览器语音服务或其他页面/进程。请求到达服务器之前的操作无法由服务端归类，需要客户端停止发送。当前无账号隔离、持久存储或导出实现。

## Sprint02增量（兼容既有客户端）

- health新增 `api_version=0.3`、`capabilities` 和非敏感 `model`，Key不返回客户端。修改后端后必须重启；旧进程可能仍提供新静态页面但执行旧Python模块。
- translate可发送 `output_format:"ocr"`、`source_language:"auto"|"zh-CN"|"en"`、`target_language:"zh-CN"|"en"`。成功时新增 `ocr:{original_text,translated_text,source_language,target_language,uncertain}`；原文完整保留供人工核对，HUD只显示短译文。服务端用严格JSON Schema并再次本地校验，坏结构返回502 INVALID_OCR_RESPONSE；无字/看不清必须标uncertain。Demo不虚构原文。旧text格式仍保留原answer/hud结构，目标语言同样生效。
- ask可附 `client_request_id`（1–80安全字符），`POST /api/requests/cancel {client_request_id}` 可记录取消，包含尚未上传完的请求ID。返回 `cancelled:true,was_active,scope:"local_result_only"`；晚到ask以409 REQUEST_CANCELLED/REQUEST_SUPERSEDED失败且不更新HUD。取消记录最多256个，由隐私删除清空；新请求生成新UUID。在途推理最多32个（含旧客户端无ID请求）。客户端仍需丢弃迟到响应。此端点不保证终止供应商处理/计费。
- `POST /api/media/validate {image_data,consent:true}` 是**纯本地**上传验收：复用JPEG/PNG解码/去元数据，返回 `validated:true,scope:"local_only",cloud_sent:false,image:{width,height,format,sanitized_bytes,sanitized_sha256},request_id`。无供应商调用、不保存图片；不能把此成功计为真实AI验收。CLI可在独立的私有忽略目录保留明确授权的摄像头帧与metadata。
- 手机开发阶段通过USB `adb reverse tcp:8765 tcp:8765` 使用相同loopback API；不为迁就模拟器而开放无鉴权LAN服务。iOS真机联网、TLS与身份认证仍需专门适配。
