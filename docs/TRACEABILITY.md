# V1.0 完整需求追踪矩阵

更新日期：2026-11-11。来源：`FEATURES_F01_F22.md`（冻结 ID/级别）、上级目录 PRD V2.0（交互与量化验收）、`AGENTS.md`（工程红线）。不调整 16 P0、5 P1、1 R，不将 AR 显示降为后续功能。

状态按完整产品功能统计：**已实现**=全部验收有对应真实证据；**部分实现**=存在可运行软件或适配代码但缺关键链路/实测；**未实现**=只有文档/建议或无对应代码。Sprint01为0已实现/11部分/11未实现；Sprint02因F11新增固件连接/错误状态代码，当前为 **0 已实现 / 12 部分实现 / 10 未实现**。原生App与固件的代码、测试、真实环境状态在下方三层矩阵分别列出，不将构建通过当作整机验收。

## F01–F22 追踪

| ID / 级别 | 需求及验收条件 | 场景 / 工作包 | 初审 → 当前 | 现有实现与测试证据 | 尚缺的验收与下一步 |
|---|---|---|---|---|---|
| F01 / P0 | 近视/远视/散光处方镜片；左右独立、HUD 清楚且不遮挡 | ME-01 / Gate D | 未实现 → 未实现 | `hardware/PCB_CHECKLIST.md`、PRD 处方约束；无样镜 | 眼距/眼盒/顶点距/镜片插片结构、专业验配、左右眼处方与 HUD 可读性试戴记录 |
| F02 / P0 | 鼻梁/太阳穴/耳后舒适与重心；4h 不适≤2/10 为内部目标 | ME-01 / Gate D | 未实现 → 未实现 | 机械要求仅文档；无重量/温升/压力数据 | 可调鼻托镜腿、不同头型与普通镜架对照、验配整镜重量/重心及接触温升实测 |
| F03 / P0 | 蓝牙开放式音频、接听/通话与短播报 | FW-02 / Gate C | 未实现 → 未实现 | 浏览器 TTS 只验证手机/PC侧播放，非眼镜通话 | 独立音频无线方案、手机 HFP/通话路由、回声/降噪/扬声器保护；S3 BLE 不等于经典蓝牙音频 |
| F04 / P0 | 按键/触控启动、取消与重复拍摄 | S1 / AR-01、FW-01 | 部分 → 部分 | `web/index.html` 手机按钮；`halo/main.lua` 单击发送 `CAPTURE`，Lua 尚未运行 | 官方 emulator、手机 BLE 接收、物理按键消抖/取消/超时/重复触发与相机联动 |
| F05 / P0 | ASR→上下文对话→TTS，无擅自执行 | SW-01、SW-02、FW-02 | 部分 → 部分 | `app/provider.py` chat、浏览器语音调用；`test_vision.VisionHttpTest.test_chat_without_image`；T06语音同意/退化与不自动提交测试 | 连续对话上下文、真实 ASR/TTS 端到端、噪声/拒绝权限/中断、语音隐私；浏览器支持性需人工实测 |
| F06 / P0 | 主动语音随手记，转写核对确认后保存，手机可查看删除 | SW-01、SW-02 | 部分 → 部分 | `app/core.py:Memory.note/wipe`；`test_note_lifecycle`；T05删除并发保护、T06保存笔记前确认 | 原生录音/ASR、用户编辑确认实测、持久化/导出、设备端输入及删除范围核验 |
| F07 / P0 | 从笔记/画面提摘要、日期和任务，原文可追溯 | S3 / SW-02 | 未实现 → 未实现 | 手写任务草稿不是 AI 内容整理，无结构化提取实现 | 提取 schema、来源片段、日期/时区/歧义确认、与标注文本对照测试 |
| F08 / P0 | 待确认→明确确认→真实白名单动作；幂等、失败可追溯 | S3 / SW-01、SW-02 | 部分 → 部分 | `Memory.draft_task/confirm_task`；`test_task_cannot_execute_without_confirmation`、`test_task_consent`；只 `confirmed_local_only` | 真实日历/任务适配器、授权与幂等、撤销、持久审计、失败/重试测试；不可声称已写入外部系统 |
| F09 / P0 | 原生手机 App：发现/配对、相机/音频权限、图像与状态同步 | S1–S3 / SW-02 | 部分 → 部分 | 原Flutter工程继续开发：iPhone Web媒体/TLS、iOS BLE/媒体API、Codemagic任务；当前证据见SPRINT_03 | iPhone实测、Swift编译、原生扫描选择UI/网关凭据入口、BLE真实配对/图传；Android保留USB开发链路 |
| F10 / P0 | 显式采集/传云同意、硬件指示、停止、删除/导出与范围 | 全场景 / SW-03、FW-01 | 部分 → 部分 | `app/images.py`去元数据、`test_delete`、T01图像清理、T04同意/同源、T05删除并发、T06关闭相机和语音同意 | 物理灯与采集供电/活动联动、原生权限撤回、持久数据导出/删除、供应商保留规则、多人/账号隔离 |
| F11 / P0 | 电量/连接/充电状态、固件升级、错误日志 | FW-01、FW-02 / Gate C | 未实现 → 部分 | `firmware/`ESP-IDF工程、20byte状态与数字错误环日志、BLE连接及有线构建/烧录流程；电量明确unknown | 真实电池计量、充电/连接遥测、OTA回滚/断电与配对实测；编译不等于设备通过 |
| F12 / P1 | 用户同意后断网暂存、恢复同步与冲突处理 | SW-02 | 未实现 → 未实现 | 进程内笔记不是持久离线队列 | 加密暂存、寿命/容量/删除范围、幂等同步与冲突/重启/断网测试 |
| F13 / P1 | 指定语言语音转写→翻译→音频反馈 | M2 / SW-02、FW-02 | 未实现 → 未实现 | 图片翻译和最终语音输入不能代替语音翻译流水线 | 语音分段、源/目标语言、真实翻译/播报、噪声/多人/超时验收 |
| F14 / P1 | 字号、语言、音量、亮度、提示及通知偏好 | SW-02、AR-02 | 未实现 → 未实现 | 运行模式切换不等于用户偏好设置 | 设置模型/持久化、手机到眼镜同步、范围/默认值/重启测试及显示亮度实测 |
| F15 / P0 | AR 光学 HUD，最多3行；室内/强光与眼盒可读性 | 全场景 / AR-01、AR-02 | 部分 → 部分 | `app/core.py:to_hud`、浏览器预览、Lua ASCII；`test_hud`和`test_vision.ImageTest.test_hud_three_lines_and_truncation`；T08浏览器截图 | 真实光学显示、中文栅格化、HUD位置/亮度/安全视野、佩戴阅读率≥90%内部目标实测 |
| F16 / P1 | 主动开启同语实时字幕，可停止、非全天监听 | M2 / SW-02、AR-02 | 未实现 → 未实现 | 单次 ASR 最终文本填输入框，未实现流式字幕 | interim/final 分段、延迟/纠错、取消、噪声/多人字幕与 HUD 帧更新测试 |
| F17 / P0 | 图像 OCR→可核对原文/译文→简短 HUD，标不确定 | S2 / SW-01、SW-03、AR-02 | 部分 → 部分 | `provider.py`真实图像/OCR提示词与`detail:high`；T02供应商payload、T04 HTTP、T06浏览器translate传图、T07实测工具契约 | 配 Key 真实 OCR 翻译照片验收、标注数据集、原文核对、中文光学 HUD；不能以固定 Demo 文案计准确率 |
| F18 / P1 | 步行简短转向导航，无 SLAM/驾车承诺 | SW-02、AR-02 | 未实现 → 未实现 | 无路线/定位/导航代码 | 手机定位授权、路线提供者/偏航、地图许可、步行场景与失败提示测试 |
| F19 / P0 | HUD 待确认任务卡、按键反馈、真实成功/失败 | S3 / SW-01、AR-02 | 部分 → 部分 | `Memory.last_hud`、浏览器确认任务卡；`test_task_consent`，T05旧AI不能覆盖新任务卡 | 真实光学任务卡与物理确认、外部执行结果、取消/失败/重复点击处理 |
| F20 / P0 | 主动摄像→上传→真实视觉理解/问答→HUD与语音 | S1 / SW-01、SW-03、FW-01 | 部分 → 部分 | 保留web/API/provider/HUD；新增Flutter Web同源摄像上传、iOS与ESP32有界JPEG通道；契约/构建见SPRINT_03 | 真实AI评分/P95、iPhone/ESP32采集与传图、光学HUD/眼镜播报；Mock只验证契约，固件相机仍锁定 |
| F21 / R | 空间锚定/6DoF/SLAM仅预研，不计V1交付 | 独立研究 | 未实现 → 未实现 | 架构已明确排除首代交付；无研究实现 | 单独定义可行性、数据集/跟踪/功耗评估，不能据浏览器叠加宣称空间锚定 |
| F22 / P0 | 按键/触控/手机/语音控制HUD继续、关闭、确认 | 全场景 / SW-01、AR-01、AR-02 | 部分 → 部分 | 手机网页交互与 Lua CAPTURE 示例；本地任务确认测试 | 物理输入与 HUD 生命周期、退出/取消、语音确认约束、断连/重复事件/一致状态验证 |

## Sprint03 三层状态（代码 / 自动验证 / 真实环境）

“部分”说明只完成相应子链路，不代表整项功能完成。当前证据见 [SPRINT_03.md](SPRINT_03.md)、[IPHONE_WEB.md](IPHONE_WEB.md)、[IOS_CLOUD_BUILD.md](IOS_CLOUD_BUILD.md)、[FIRMWARE_SPRINT03.md](FIRMWARE_SPRINT03.md)。Sprint02与下方Sprint01 T01–T08保留为历史，不作为本轮全量计数。整机统计仍为0已实现/12部分/10未实现。

| ID | 代码完成层级 | 测试通过层级 | 真实环境验收层级 |
|---|---|---|---|
| F01 | 未开始实体镜片/验配实现 | 未运行光学测试 | 待镜片/光学样机，P0保持 |
| F02 | 只有机械审查约束 | 未运行佩戴/温升/配重试验 | 待试戴及人体工学数据，P0保持 |
| F03 | 无眼镜通话/音频实现 | 未运行音频硬件测试 | 待独立音频/HFP方案；S3 BLE不替代 |
| F04 | 部分：手机/网页输入、固件消抖/长按取消、AP物理开启窗口 | 38项固件Host涵盖控制/撤销/媒体；三配置构建 | 物理按键+相机/窗口联动待板级实测 |
| F05 | 部分：chat、Web ASR/TTS桥/单独同意；未完成上下文 | JS媒体桥19项涵盖语音能力/同意/停止/退化；非声学测试 | iPhone ASR/TTS及真实AI待验，原生录音/播报尚未实现 |
| F06 | 部分：浏览器笔记确认/进程内存；原生录音未做 | 保存确认/删除回归通过 | 原生录音、持久化与导出待验 |
| F07 | 未实现AI摘要/日期/任务提取 | 无真实提取测试 | 待实现和模型验收 |
| F08 | 部分：本地显式确认，保持confirmed_local_only | 确认前不执行/重复确认拒绝通过 | 外部白名单动作/撤销仍未实现 |
| F09 | Flutter Web相机/预览/AI/HUD、同源TLS配对；iOS CoreBluetooth/媒体API、CI任务 | analyze无问题、Flutter41项、Web桥19项；Web/Android实际构建，iOS仅配置/schema检查 | iPhone Safari、Swift云编译/安装、BLE实机待验；原生扫描/选择UI及原生网关凭据入口缺失 |
| F10 | 部分：独立同意、清元数据/内存、TLS/Bearer会话、固件锁与媒体清理 | Python102项含12项真实本地TLS；固件撤销/到期、Flutter迟到保护通过 | Windows LAN可信TLS/鉴权/本地validate已测；Sprint02 XiaoMi已验；手机信任/权限与物理灯待验 |
| F11 | 部分：状态/连接/数字错误日志、开发AP会话；battery=unknown | 固件38项Host，默认/EYE/AP启用三配置真实编译 | 电量/充电/OTA/断电与真实无线状态待验 |
| F12 | 未实现持久离线队列/冲突同步 | 无持久离线测试 | 待实现 |
| F13 | 未实现语音分段翻译流水线 | 无语音翻译验收 | 待实现 |
| F14 | OCR任务语言参数已支持；用户持久偏好系统未实现 | 中英目标参数契约通过，不计偏好系统通过 | 字号/音量/亮度/偏好同步待验 |
| F15 | 部分：3行HUD、显示适配、中文256×256栅格化；真实光学驱动未配置 | 中文bitmap14项、HUD截断与未配置显示拒绝测试通过；固定样张已目视核验 | 真实AR光学强光/室内/眼盒可读性未验，P0保持 |
| F16 | 未实现流式同语字幕 | 单次ASR不能算流式测试 | 待实现 |
| F17 | 双向OCR原文/译文/不确定性/HUD，Flutter Web同接口展示 | Python/Dart隔离桩契约通过；10OCR图准备，真实云blocked | 无Key，真实OCR/翻译质量待验；iPhone展示待实测 |
| F18 | 未实现导航 | 无路线/定位测试 | 待实现 |
| F19 | 部分：网页任务卡与状态；未集成真光学卡片 | 旧AI不覆盖新任务卡/本地确认通过 | 物理卡片确认与外部真实执行待验 |
| F20 | 摄像/安全上传/视觉/HUD软件路径；固件与iOS有界JPEG传输接口 | Web构建、Python/Dart/JS契约、C媒体18项；10视觉图准备，真实云blocked | Sprint02 XiaoMi→localhost已验；iPhone/设备JPEG/真实AI/光学HUD待验；相机锁未解除 |
| F21 | 无空间锚定实现，仅R研究项 | 未运行SLAM测试 | 不计首代交付 |
| F22 | 部分：手机/网页取消、BLE v1控制+v2会话、固件输入与撤销 | 跨语言帧/状态、取消/去重/权限/会话回归；Swift未编译 | App↔真BLE↔相机/光学显示整体链路待验 |

## 场景及横向需求（Sprint01起持续追踪）

| 验收 ID | 覆盖需求 | 测试与门槛 | 当前证据 / 缺口 |
|---|---|---|---|
| S1 / 即拍即问 | F04/F09/F10/F15/F20/F22 | 主动取景→同意→真实图像→真实AI→短答HUD；取消、无图、无Key、断网、坏图均有明确失败 | 本轮在现有软件主路径上补契约；真实模型、相机和光学设备证据分开归档 |
| S2 / AR翻译 | F10/F15/F17/F22 | 50张清晰标签/铭牌逐字段评分；OCR关键字段≥95%为目标；不清晰输入标不确定 | Mock响应不能计作OCR/翻译样本；待Key与真实照片数据集 |
| S3 / 看见即行动 | F07/F08/F19/F22 | 当前画面来源可追溯→提取→内容核对→用户确认→真实写入→撤销/失败 | 现仅手写草稿→本地确认；外部任务执行成功率≥99%目标尚未测 |
| Q01 / 真实与模拟隔离 | F05/F17/F20 | 响应、HUD与播报来源一致；live缺配置/出错不得返回Demo答案 | T03/T04/T06/T07明确mode/simulated与失败不降级；T08实际浏览器缺Key错误 |
| Q02 / 图像边界 | F09/F10/F20 | JPEG/PNG、0/1/2MiB、坏Base64/MIME/截断、显式同意、请求限长 | T01严格解码/元数据清理与0/1/2MiB边界，T04同意/无图，T06本地文件边界；不是整机隐私认证 |
| Q03 / 时延可靠性 | F04/F09/F15/F20/F22 | 固定网络/手机/模型≥50轮，拍摄到HUD P95≤6s内部目标；超时/退出覆盖100% | T03有限HTTP重试、超时不重试；T06前端超时/旧结果保护。测试耗时不是真实AI端到端延迟 |
| Q04 / 视觉质量 | F17/F20 | 100张预选图像，问题与人工参考答案固定；可用回答≥90%内部目标 | 未做真实评分；需区分清晰度/光照/距离并记录模型版本 |
| Q05 / 隐私删除 | F06/F08/F10/F12 | 停止媒体、清理本地状态、说明浏览器/服务/供应商边界；删除中在途响应不得重新显示 | T05后端在途推理/慢上传删除失效，T06浏览器图片/相机/语音清理和迟到响应拒绝；云端删除不在本地按钮范围 |
| Q06 / 佩戴及温升 | F01/F02/F03/F10/F15 | 裸镜目标≤50g、警戒55g；验配整镜另称重；25°C指定工况皮肤接触面≤41°C内部目标 | 全部待实测；这些为PRD内部目标，最终适用标准和安全边界需专业审查 |
| Q07 / 第三方与PCB | F01/F02/F03/F09/F11/F15 | 固定版本/许可、可买BOM、Pin Map、电源/结构审查、ERC/DRC后才导出制造文件 | 无第三方工程复制；现仍开发板/独立显示评估阶段，见 `HARDWARE_ARCHITECTURE.md` |

## 基线与本轮证据索引

- 初审测试精确名称、9/9原始结果和各目录审查见 `AUDIT_BASELINE.md`。
- 本轮改动、测试命令与真实输出、缺Key/工具/硬件的限制见 `DEVELOPMENT_LOG.md`。
- 真实供应商测试应单独记录日期、模型、`request_id`、输入类型与非敏感摘要，不提交 Key、个人图片或音频；未执行时明确写“未运行”。
- 软件完成子能力可以在日志标“测试通过”，本矩阵整机功能仅在剩余验收全部有证据后升级“已实现”。

Sprint01历史结果：Python **48/48**，其包装执行 **21/21 Node**，不能相加。输出保留在 [`evidence/unittest.txt`](evidence/unittest.txt)、[`evidence/web-tests.txt`](evidence/web-tests.txt)。当前Sprint03为Python102项（包装旧网页Node25项）、Flutter41项、新Web桥JS19项、固件Host38项，精确边界见本轮报告。以下精确名称可直接在对应文件定位。

| 索引 | 代码/测试文件与精确测试名 | 覆盖范围及验证边界 |
|---|---|---|
| T01 / 图像 | `tests/test_vision.py:ImageTest`：`test_valid_jpeg_png`、`test_metadata_and_trailing_bytes_removed`、`test_reject_empty_fake_base64_url_and_mime`、`test_reject_truncated_jpeg_and_png`、`test_two_mib_limit`、`test_pixel_limit`、`test_hud_three_lines_and_truncation` | Pillow完整解码、JPEG/PNG MIME一致性；0/1/2MiB及超限、16MP上限；移除PNG元数据/尾随内容；HUD3行及省略号。图像由测试生成，不含个人媒体；不证明OCR准确率 |
| T02 / 供应商payload | `tests/test_vision.py:ProviderTest.test_live_payload_image_store_false_and_ocr_detail`、`test_live_requires_image` | 截获Responses请求验证图片原样进入供应商适配层、`store:false`、OCR `detail:high`；供应商网络为Mock，不代表服务端鉴权/模型识别通过 |
| T03 / 供应商失败 | `tests/test_vision.py:ProviderTest`：`test_unknown_provider_never_falls_back`、`test_retry_transient_http_only`、`test_auth_failure_not_retried_or_leaked`、`test_timeout_no_retry`、`test_bad_empty_incomplete_and_refusal`、`test_invalid_json_and_network`、`test_invalid_timeout_config` | 未知配置不降级；暂态HTTP有限重试，鉴权/超时不自动重试；拒答、未完成、空响应、坏JSON/网络失败可见且不泄露上游敏感内容 |
| T04 / HTTP契约 | `tests/test_vision.py:VisionHttpTest`：`test_demo_marked_in_response_and_hud`、`test_live_in_demo_server_cannot_succeed`、`test_live_adapter_to_http_hud_contract`、`test_consent_missing_false_or_truthy_rejected`、`test_image_required_and_malformed`、`test_mode_kind_and_question_types`、`test_chat_without_image`、`test_origin_and_content_type`、`test_errors_update_hud` | 启动真实localhost HTTP服务器；live适配层响应仍为离线桩。验证传图、严格boolean同意、来源、503缺配置、同源及错误HUD；`simulated:false`仅为live路由契约，不是本次真实推理证据 |
| T05 / 后端并发 | `tests/test_vision.py:VisionHttpTest.test_privacy_delete_discards_inflight_result`、`test_privacy_delete_invalidates_slow_upload_before_mutation`、`test_task_hud_supersedes_old_inference` | 删除后在途AI/慢上传不能回填HUD或笔记；新任务卡使旧AI请求409失效。线程与socket模拟并发，不涉及真实摄像硬件 |
| T06 / 浏览器交互 | `tests/web_client.test.cjs`，由 `tests/test_web_client.py:WebClientTest.test_browser_interaction_contracts` 包装；含 `camera capture remains local until explicit recognition; vision sends actual frame`、`live OCR sends chosen image with translate kind and shows live HUD source`、`live never accepts a demo response or silently retries demo`、`cloud failure replaces old result on HUD and prevents stale speech`、`client timeout produces error HUD with no unbounded spinner` 等21项 | Node DOM/相机/云端桩执行实际网页脚本：主动采集/上传同意、来源校验、超时、语音退化与确认保存、撤回/后台/离页停止轨道、删除和任务操作拒绝旧响应。相机帧与语音为测试替身，不代表物理摄像头/麦克风验收 |
| T07 / 真实验收工具自身 | `tests/test_verify_live.py:LiveVerifierTest`：`test_live_contract_sends_image_and_explicit_consent`、`test_consent_required_before_read_or_network`、`test_demo_or_unready_health_never_uploads`、`test_rejects_demo_or_malformed_success`、`test_rejects_nonlocal_or_ambiguous_urls`、`test_rejects_redirect`、`test_timeout_and_http_error_are_safe_failures`、`test_nonimage_and_oversized_are_rejected`、`test_cli_output_contains_metadata_only`、`test_invalid_json_is_safe_failure` | 验证 `tools/verify_live.py` 不向Demo上传、不接受伪live成功、只连本机、不跟随重定向、摘要不打印图像/回答。10项全部使用FakeOpener，真实API成功验收尚未运行 |
| T08 / 实际浏览器证据 | [`evidence/live-missing-key.jpg`](evidence/live-missing-key.jpg)、[`evidence/demo-image-hud.jpg`](evidence/demo-image-hud.jpg)、[`evidence/synthetic-label.png`](evidence/synthetic-label.png) | 已目视核对：前者在live的chat操作显示缺`OPENAI_API_KEY`错误HUD；后者选择合成STOP标签走Demo翻译，HUD和结果明确“模拟演示，不是真实识别”。不证明相机实际采集、真实OCR/翻译或光学AR；HTTP503另由T04断言 |

Sprint01独立复核：冻结22个ID无遗漏、无重复；P0=16、P1=5、R=1，当时11部分/11未实现。Sprint02增加F11为部分实现，当前12部分/10未实现（含R项F21）。语音最终文本填入输入框不计F16流式字幕；浏览器TTS不计F03蓝牙通话；手写任务草稿不计F07 AI整理；本地确认不计F08外部执行完成。
