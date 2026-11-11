# 首个端到端验收脚本

1. `python -m unittest discover -s tests -v` 全部成功。
2. `python -m app.server`，打开 `http://127.0.0.1:8765`。
3. 显式选 DEMO 与「视觉识别」，同意本地相机预览后开启并采集，或选择有效 JPG/PNG；核对当前帧并同意提交图片后执行识别。Demo 应显示【模拟演示】；未同意/无图不能发送。
4. 选「AR 翻译」，翻译反馈显示在 HUD 叠加层，且标注真实/模拟来源。
5. 输入「查看某台设备温度」生成任务卡，在点击确认前状态必须 `awaiting_confirmation`；点击后应为 `confirmed_local_only`，不可假定已操作设备。
6. 保存一条笔记，读取状态，再执行删除；笔记、任务数组应为空。
7. 服务端设 `AI_PROVIDER=openai` 和合法密钥并重启；UI显式选择真实AI。用允许传云的非敏感外文标签图片执行 translate：核对原文、译文和HUD来源，不能只以HTTP200计正确率。运行 `python tools/verify_live.py --image C:/test/label.png --consent-upload --kind translate` 验契约；另测vision图片问答。**此项需要网络/密钥，本轮未执行真实云推理**。
8. 运行 Halo emulator 并截屏 `halo/main.lua`；检查按钮事件是否发出 `CAPTURE`。**此项需要安装上游 emulator，本包暂未验证**。
9. 真实 AR 眼镜硬件上显示字幕属于下一 Gate B；禁止将浏览器预览当作该门槛通过。

10. Live 缺Key时服务仍可打开，health ready=false、识别返回503并显示配置错误；断网/超时/拒绝/坏响应显示错误HUD，绝不能显示Demo答案。切回Demo必须用户主动选择。
11. 识别处理中删除隐私数据、撤回上传授权或生成任务卡：旧结果不能重新覆盖HUD/恢复私人文字；取消只能停止本地等待，不保证撤回已发云端请求。
12. 保存语音笔记前核对转写并明确确认；无浏览器ASR/TTS能力时退化键盘/文字。测试麦克风拒绝权限/停止、相机后台关闭与晚到权限结果释放轨道。浏览器语音服务可能上传音频，不能称为本地ASR。

2026-11-10 已验证的范围与证据见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。自动测试使用明确桩数据；UI 图片上传测试使用合成标签；真实摄像头、真实AI成功、语音服务与光学显示未验。质量/时延目标见需求矩阵，不把测试桩运行速度填入云端P95。
