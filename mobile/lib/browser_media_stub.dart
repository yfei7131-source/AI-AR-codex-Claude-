import 'package:flutter/widgets.dart';

Future<void> prepareBrowserUi() async {}
void finishBrowserBoot() {}
String? browserFontFamily() => null;

class BrowserMedia {
  bool get isWeb => false;
  bool get cameraAvailable => false;
  bool get recognitionAvailable => false;
  bool get synthesisAvailable => false;
  bool get secure => true;
  bool get cameraActive => false;
  String takeSessionToken() => '';
  void listen(void Function(Map<String, dynamic>) callback) {}
  Widget preview() => const SizedBox.shrink();
  Future<void> startCamera(bool consent) async =>
      throw UnsupportedError('原生平台使用系统相机');
  String captureFrame(bool consent) => throw UnsupportedError('原生平台使用系统相机');
  void stopCamera() {}
  void startSpeech(bool consent) =>
      throw UnsupportedError('此原生版本尚无语音适配，请使用文字输入');
  void stopSpeech() {}
  void speak(String text) => throw UnsupportedError('此原生版本尚无语音适配，请阅读HUD');
  void dispose() {}
}
