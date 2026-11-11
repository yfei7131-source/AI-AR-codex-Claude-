import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/widgets.dart';
import 'package:flutter/services.dart';

@JS('aiarBrowser.capabilities')
external JSString _capabilities();
@JS('aiarBrowser.videoElement')
external JSObject _videoElement();
@JS('aiarBrowser.startCamera')
external JSPromise<JSString> _startCamera(JSBoolean consent);
@JS('aiarBrowser.captureFrame')
external JSString _captureFrame(JSBoolean consent);
@JS('aiarBrowser.stopCamera')
external void _stopCamera();
@JS('aiarBrowser.startSpeech')
external void _startSpeech(JSBoolean consent);
@JS('aiarBrowser.stopSpeech')
external void _stopSpeech();
@JS('aiarBrowser.speak')
external void _speak(JSString text);
@JS('aiarBrowser.cameraActive')
external JSBoolean _cameraActive();
@JS('aiarBrowser.setEventHandler')
external void _setHandler(JSFunction callback);
@JS('aiarBrowser.takeSessionToken')
external JSString _takeSessionToken();
@JS('aiarBrowser.setBootStatus')
external void _setBootStatus(JSString text);
@JS('aiarBrowser.finishBoot')
external void _finishBoot();

bool _fontReady = false;
Future<void> prepareBrowserUi() async {
  _setBootStatus('正在加载本地中文界面资源…'.toJS);
  try {
    final loader = FontLoader('AIARNotoSC')
      ..addFont(NetworkAssetBundle(Uri.base).load('/fonts/NotoSansSC.ttf'));
    await loader.load().timeout(const Duration(seconds: 30));
    _fontReady = true;
  } catch (_) {
    _setBootStatus('本地字体资源加载失败，请检查Windows网关是否完整提供应用资源后重新打开页面。'.toJS);
    rethrow;
  }
}

void finishBrowserBoot() => _finishBoot();
String? browserFontFamily() => _fontReady ? 'AIARNotoSC' : null;

class BrowserMedia {
  bool _disposed = false;
  final Map<String, dynamic> _caps =
      jsonDecode(_capabilities().toDart) as Map<String, dynamic>;
  static bool _registered = false;
  bool get isWeb => true;
  bool get cameraAvailable => _caps['camera'] == true;
  bool get recognitionAvailable => _caps['recognition'] == true;
  bool get synthesisAvailable => _caps['synthesis'] == true;
  bool get secure => _caps['secure'] == true;
  bool get cameraActive => _cameraActive().toDart;
  String takeSessionToken() => _takeSessionToken().toDart;
  void listen(void Function(Map<String, dynamic>) callback) {
    _setHandler(
      ((JSString json) {
        if (!_disposed) {
          callback(jsonDecode(json.toDart) as Map<String, dynamic>);
        }
      }).toJS,
    );
  }

  Widget preview() {
    if (!_registered) {
      ui_web.platformViewRegistry.registerViewFactory(
        'aiar-local-camera',
        (int id) => _videoElement(),
      );
      _registered = true;
    }
    return const HtmlElementView(viewType: 'aiar-local-camera');
  }

  Future<void> startCamera(bool consent) async {
    await _startCamera(consent.toJS).toDart;
  }

  String captureFrame(bool consent) => _captureFrame(consent.toJS).toDart;
  void stopCamera() => _stopCamera();
  void startSpeech(bool consent) => _startSpeech(consent.toJS);
  void stopSpeech() => _stopSpeech();
  void speak(String text) => _speak(text.toJS);
  void dispose() {
    _disposed = true;
    _stopCamera();
    _stopSpeech();
    _setHandler(((JSString _) {}).toJS);
  }
}
