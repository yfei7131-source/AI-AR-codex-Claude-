# Sprint-02：20图验收准备与执行证据

日期：2026-11-10。对应 F17 OCR 翻译、F20 视觉问答、F15 HUD 软件契约；不代表眼镜光学显示或摄像头实机验收。

## 当前结果

- 已准备10项 vision、10项 translate，共20张非敏感合成输入及逐项可核对预期。翻译集含5张英文原文→中文、5张中文原文→English；manifest版本为 `sprint02-2-bidirectional`。
- 本机没有可用云端密钥。实际启动 `AI_PROVIDER=openai`、`OPENAI_API_KEY` 为空的 `python -m app.server`，批量工具读 health 后得到 **20 blocked、0 success**，退出码2，没有提交图片或调用云模型。
- 本地私有证据：初版 `artifacts/private/acceptance/server_missing_key_report.json`；双向集复验 `artifacts/private/acceptance/bidirectional_missing_key_report.json`。文件及图片均位于现有 `.gitignore` 的 `artifacts/private/` 范围内。
- `python -m unittest discover -s tests -p test_acceptance_suite.py -v`：双向集更新后14/14通过。故障注入只在测试传输层实现，不能写成真实云模型、断网硬件或准确率通过。
- 双向集更新后 `python -m unittest discover -s tests -v`：73/73通过（2.845秒）。之后若新增功能，以最新全量测试记录为准。
- 合成图片 T07、V02 已实际查看，T07中文版本重新生成后再次查看，标签和图形清晰、无截断。本轮真实云模型识别、自然场景准确率及光学HUD均未验收。用户随后已明确授权非敏感本地拍照，XiaoMi Webcam的浏览器640×480和DirectShow1920×1080采集→本地预览/上传校验已通过；证据仅在 `artifacts/private/camera/`，不能把这条本地摄像成功计入20图真实AI通过数。

## 数据集范围

跟踪文件为 `tools/acceptance/manifest.json`，记录问题、原文、中文参考及可见事实，不包含图片或base64。`tools/acceptance/generate.py` 使用 Pillow 和系统字体重新生成输入；生成目录为 `artifacts/private/acceptance/images/`，无需下载素材。

所有图均带有 `SYNTHETIC FIXTURE / NOT A CAMERA PHOTO` 标识。vision 是颜色/几何形状/位置/数量图，不是实物识别场景。translate 是清晰印刷标签，没有反光、倾斜、距离、噪声及自然背景。即使未来20项全部通过，也只能证明这套清晰合成集表现，不能替代PRD中自然场景100图问答、50标签关键字段和50轮P95时延验收。

| 项目 | 预期核对内容 |
|---|---|
| V01–V10 | 10组不同颜色、数量、形状和相对位置；逐项事实及标识见manifest |
| T01 | KEEP DOOR CLOSED → 请保持门关闭 |
| T02 | INPUT: 5 V DC / MAX CURRENT: 2 A → 输入直流5伏 / 最大2安 |
| T03 | NO ENTRY / AUTHORIZED PERSONNEL ONLY → 禁止进入 / 仅限授权人员 |
| T04 | CAUTION / HOT SURFACE → 注意 / 高温表面 |
| T05 | SHELF B / SLOT 03 → B货架 / 03号位 |
| T06 | 交货日期 / 2026-11-20 → DELIVERY DATE / 2026-11-20 |
| T07 | 电池：3.7 伏 / 容量：500 毫安时 → BATTERY: 3.7 V / CAPACITY: 500 mAh |
| T08 | 电量低 / 请充电 → LOW BATTERY / PLEASE CHARGE |
| T09 | 营业时间 09:00 - 18:00 / 周一休息 → OPEN 09:00 - 18:00 / CLOSED ON MONDAY |
| T10 | 按下启动键 / 等待绿灯亮起 → PRESS START / WAIT FOR GREEN LIGHT |

标签是合成测试数据，不是设备安全说明或真实电池规格。

## 复现命令

从项目根目录执行：

```powershell
python -m tools.acceptance.generate
python -m unittest discover -s tests -p test_acceptance_suite.py -v
python -m tools.acceptance.run --help
```

先在服务端按 `.env.example` 和 README 配置真实AI环境并启动服务；客户端工具不读取或接受API Key。然后明确同意这20张合成图上传：

```powershell
python -m tools.acceptance.run --consent-upload
```

默认只把状态、请求ID、耗时、OCR原文逐行命中布尔值等元数据写入私有报告，不输出或保存图片、问题/答案原文及密钥。未加同意参数时，20项都记为blocked，连health都不请求；health未就绪或为demo时，20项blocked，不执行 `/api/ask`。只允许loopback目标，禁用代理和HTTP重定向。重复执行会生成新的报告文件，避免静默覆盖旧报告。

人工核对需要保留真实模型原文时，单独明确开启：

```powershell
python -m tools.acceptance.run --consent-upload --record-answers --report artifacts/private/acceptance/review_run.json
```

此时报告保存完整answer、HUD，以及translate的 `ocr.original_text`、`ocr.translated_text`、语言与不确定性；不会将原文截断为HUD短句。runner按每张manifest的 `source_language` 和 `target_language` 发请求，返回的目标语言必须匹配该张样本，不能把English目标默默当成中文。报告只能写在 `artifacts/private/acceptance/` 内。不要将私有报告或将来真实用户图片加入版本控制。

## 结果与证据含义

| 状态/字段 | 含义 |
|---|---|
| blocked | 未尝试该图；例如缺少同意、live未就绪、预检失败或整批已取消 |
| success | API明确声明live/openai/simulated=false，且answer、HUD、request_id及结构化OCR契约有效；不是识别正确性通过 |
| failed | 本地坏图/缺图、HTTP失败、拒绝、坏JSON、demo冒充或不合约响应 |
| timeout | 独立记录上传、模型或客户端socket超时 |
| cancelled | 用户中断或服务端取消/被新请求替代 |
| disconnected | 本地连接丢失或服务端明确AI不可达 |
| evidence_origin=local_live_api | 实际访问本地服务的live入口；只有success且cloud_response_received=true才收到标为真实模型的回答。本轮20项均blocked、cloud_response_received=false |
| evidence_origin=injected_test_transport | 单元测试专用替身；即使契约成功，也不能算真实云证据，不能人工打分升级为真实证据 |
| elapsed_seconds | 客户端本次API步骤耗时；不是拍摄到光学HUD端到端时延，不填入PRD P95 |

客户端 Ctrl+C 会停止后续图片，当前项记cancelled，并尝试 `POST /api/requests/cancel`；取消只能约束本地等待/旧HUD写入，不能承诺撤销已发云端请求或取消账单。测试覆盖此分支，但没有声称完成真实云端取消。

## 人工评分

所有结果初始为 `human_score=unknown`。OCR原文逐行命中是可核对提示，不自动判定翻译质量；同义译文可接受，数字、单位、日期、标识不得改变。vision逐条核对manifest事实，不能添加不存在的物体；不确定结果应明确表达。根据原图和已记录原文逐项判pass/fail，无法判断维持unknown。

```powershell
python -m tools.acceptance.score --report artifacts/private/acceptance/review_run.json --id T01 --score pass
python -m tools.acceptance.score --report artifacts/private/acceptance/review_run.json --id V01 --score fail
```

仅真实live API契约success可人工评分；blocked、失败和测试注入结果不可评分。准确率分母仅为显式人工评分pass+fail，未评unknown不算通过，未评分时准确率为null。需同时报告已评数量、unknown数量和合成集限制。本轮准确率为null，20项均unknown。

## 尚需真实验收

配置有效服务端密钥及网络后，运行20图并保存明确授权的原始回答，逐项人工核对；再扩展至允许上传的自然场景数据集。摄像授权、真实拍摄指示、AR光学显示、连续语音和最终产品质量仍需独立实机证据。密钥阻塞不能用测试注入或demo答案补齐。
