# AI/AR Glasses 手机中枢

真实 Flutter 应用，支持系统拍摄/选图、图片预览、独立上传同意、视觉问答、OCR 原文与译文、显式 demo/live、本地 HUD 预览、取消与隐私删除。沿用项目 Python localhost API；云端密钥只由 Python 服务读取。

```powershell
flutter pub get
flutter analyze
flutter test
adb reverse tcp:8765 tcp:8765
flutter run
flutter build apk --debug --target-platform android-arm64
```

API 默认 `http://127.0.0.1:8765`。先从项目根运行 `python -m app.server`。未配置密钥时选择 DEMO，真实模式失败不会生成模拟回答。

`lib/api.dart` 对接既有契约；`controller.dart` 控制同意和迟到结果；`device_adapter.dart` 为候选 BLE 控制帧/状态 codec，当前设备为 disconnected；`hud_adapter.dart` 区分手机预览与尚未配置的光学显示。

运行步骤、Windows 中文路径/代理处理、工具来源、验证结果和边界见 [MOBILE_APP.md](../docs/MOBILE_APP.md)。`evidence/` 保存实际命令输出。相机真机、BLE、光学 AR 和 iOS 需要独立验收，不能用手机预览或 Web 构建替代。
