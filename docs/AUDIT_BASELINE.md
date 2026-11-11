# 2026-11-10 接管审查基线

本文件记录本轮改动前的工程现状；本轮开发结果以 `DEVELOPMENT_LOG.md`、`TRACEABILITY.md` 和实际测试输出为准。功能冻结基线为 `FEATURES_F01_F22.md`，结合上级目录 `AI_AR眼镜_首代功能需求与样机路线_PRD_V2.0.md` 的验收细节；保持 16 P0、5 P1、1 R，AR 显示保留首代 P0。

## 已读取范围

| 路径 | 初始内容与判断 |
|---|---|
| `AGENTS.md`、`README.md` | 强制真实/模拟分离、物理采集指示、显式任务确认、最小留存、硬件实测和 PCB 门槛；运行入口为 Python 本地服务 |
| `docs/` | 冻结功能、架构、Sprint-01、开源复用、验收步骤均存在；缺逐需求追踪矩阵与实际测试证据归档 |
| `app/` | `provider.py` 有 Demo/OpenAI Responses 两个适配器；`server.py` 提供本地 HTTP API；`core.py` 提供进程内笔记、任务、HUD，无数据库 |
| `web/` | 单页摄像头/文件上传/HUD/浏览器语音原型；摄像头及语音需浏览器人工验证，不能由后端单测证明 |
| `firmware/` | 仅路线说明，无 ESP-IDF/PlatformIO 固件工程，无采集、功耗、OTA 实测 |
| `hardware/` | 仅 `PCB_CHECKLIST.md`；无原理图、BOM、Pin Map、ERC/DRC、Gerber、板级电测 |
| `halo/` | Lua ASCII HUD 与 `CAPTURE` 回调示例；没有官方 emulator 输出、中文栅格化、BLE 配对/相机传输/实机显示证据 |
| `protocols/` | JSON Schema 草案覆盖事件外壳；无 BLE 分片/重传/MTU/加密及媒体契约实现，Lua 简化字符串不是该协议落地 |
| `tests/` | 2 个 unittest 文件共 9 个测试，无真实供应商调用、图像有效性、同意拒绝、超时、重试、浏览器/固件/实机验收 |

## 基线测试证据

从项目根目录执行：

```text
python -m unittest discover -s tests -v
Ran 9 tests in 0.550s
OK
```

实际执行日期为 2026-11-10；结果由主代理首次执行获取。测试名与覆盖边界：

| 测试 | 验证内容 | 不证明什么 |
|---|---|---|
| `test_core.CoreTest.test_note_lifecycle` | 文本去空格、内存保存/删除 | 语音准确率、持久化、云端删除 |
| `test_core.CoreTest.test_task_cannot_execute_without_confirmation` | 草稿待确认、确认后仅本地状态、重复确认失败 | 实际日历/外部执行与完整审计 |
| `test_core.CoreTest.test_hud` | 72 个字符按 28 字分成 3 行 | 任意长文本最多 3 行、光学可读性 |
| `test_core.CoreTest.test_mock_marked_as_simulation` | Demo 文案标识模拟 | 图像内容理解 |
| `test_core.CoreTest.test_require_key` | 缺 OpenAI Key 抛错 | 服务在缺密钥时能正常返回配置错误、有效账号可访问 |
| `test_http.HttpTest.test_health` | HTTP 健康检查可读 | 云端 readiness、设备在线 |
| `test_http.HttpTest.test_ask_hud` | Demo translate 返回 HUD 标题 | 真实图像、OCR 或翻译；此基线请求甚至未带图像 |
| `test_http.HttpTest.test_task_consent` | HTTP 草稿/本地确认 | 服务理解真实用户身份、实际外部动作 |
| `test_http.HttpTest.test_delete` | 本地笔记数组清空 | 摄像帧/浏览器/云端数据清除、并发请求不会回写 |

## 已实现的软件子能力

- localhost HTTP API、浏览器 HUD 预览、Demo 显著模拟文案、可选 OpenAI 调用代码。
- 进程内文字笔记保存/查看/删除；任务草稿与显式本地确认状态。
- 摄像头、文件读取、浏览器 ASR/TTS 调用代码已存在，初审没有对应执行证据，因此仅计为已编码。

这些子能力不构成任何一条完整 V1 整机功能验收。初审 F01–F22：完整已实现 **0**，部分实现 **11**，未实现 **11**（含 F21 预研项）；逐条见追踪矩阵。

## 优先修复的实际缺口

1. 服务端仅检查图像字符串长度，未强制视觉/翻译有图片，未做 Base64/文件签名/内容校验；未检查图像传云同意。
2. `AI_PROVIDER` 非 `openai` 的任意值静默进入 Demo；缺 Key 会在模块导入时失败；未提供独立 `mode` 和可机读 `simulated`，真实请求失败需明确禁止降级模拟。
3. 供应商固定 40 秒 socket 超时，无异常类型契约/有限重试/响应损坏处理；浏览器 fetch 无超时与取消，错误时旧 HUD 仍可能被误读。
4. PRD 要求 HUD 最多 3 行；初始 `to_hud` 可返回 5 行。全文应保留在手机侧，HUD 应限制长度并说明截断。
5. 摄像头与语音缺主动同意步骤；保存语音笔记缺内容确认；清除按钮未清除浏览器帧与语音状态；物理采集指示灯尚未实施。
6. 图像问答、OCR 翻译没有真实 API/标注数据集实测，不能将 Mock 契约测试转述为识别成功率或云端可用。
7. F05 无会话上下文，F07 摘要/结构化任务提取未实现，F08 仅 `confirmed_local_only`；不得显示“已外部执行”。
8. 原生手机 App、Halo emulator/实机、ESP32-S3 固件和 AR 光学显示均缺验证。ESP32-S3 BLE 与 F03 蓝牙通话能力需单独审查，见 `HARDWARE_ARCHITECTURE.md`。

## 验证升级规则

每个状态变更应记录代码、测试命令、实际输出、环境、日期及尚未覆盖项。供应商 Mock 只能证明适配/HTTP 契约；真实 API 成功还需用户授权的测试照片和密钥；Gate B 需真实光学设备。没有设备、工具或密钥的项目记为“未验证”，不以虚构截图或采样结果填补。
