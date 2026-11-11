import 'dart:math';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'device_adapter.dart';
import 'hud_adapter.dart';

String newRequestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

class HubController extends ChangeNotifier {
  HubController(
    this.api, {
    GlassesDeviceAdapter? device,
    HudDisplayAdapter? display,
  }) : device = device ?? UnconfiguredDeviceAdapter(),
       display = display ?? PhonePreviewHudAdapter();
  final GlassesApi api;
  final GlassesDeviceAdapter device;
  final HudDisplayAdapter display;
  String mode = 'demo',
      kind = 'vision',
      sourceLanguage = 'auto',
      targetLanguage = 'zh-CN';
  bool captureConsent = false,
      uploadConsent = false,
      busy = false,
      ready = false;
  String status = '尚未连接本地 API', error = '', hudTitle = '等待输入';
  String hudSource = '尚无AI结果';
  List<String> hudLines = ['拍摄后识别，结果将在此显示'];
  Uint8List? frame;
  String mime = 'image/jpeg';
  Map<String, dynamic>? result;
  int maxImageBytes = 2097152, _epoch = 0;
  String? _activeId;
  bool _disposed = false;
  void changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> refreshHealth() async {
    try {
      final health = await api.health();
      ready = health['ready'] == true;
      status = 'API ${health['provider']} · ${ready ? '本地配置就绪' : '未就绪'}';
      if (!ready && health['configuration_error'] is String) {
        status += '\n${health['configuration_error']}';
      }
      if (health['max_image_bytes'] is int) {
        maxImageBytes = health['max_image_bytes'] as int;
      }
    } catch (failure) {
      ready = false;
      status = failure.toString();
    }
    changed();
  }

  void setMode(String value) {
    if (!['demo', 'live'].contains(value)) throw ArgumentError('无效模式');
    cancel();
    mode = value;
    result = null;
    error = '';
    hudTitle = '等待识别';
    hudSource = '尚无AI结果';
    hudLines = ['模式已切换，请重新识别'];
    changed();
  }

  void setKind(String value) {
    cancel();
    kind = value;
    result = null;
    hudTitle = '等待输入';
    hudSource = '尚无AI结果';
    hudLines = ['请选择画面或输入问题'];
    changed();
  }

  void setFrame(Uint8List bytes, String contentType) {
    cancel();
    frame = null;
    result = null;
    if (!['image/jpeg', 'image/png'].contains(contentType) ||
        bytes.isEmpty ||
        bytes.length > maxImageBytes) {
      throw ApiFailure(
        '需要非空 JPEG/PNG 图片，且不超过 ${(maxImageBytes / 1048576).toStringAsFixed(1)}MiB',
      );
    }
    frame = Uint8List.fromList(bytes);
    mime = contentType;
    result = null;
    error = '';
    hudTitle = '图片已采集';
    hudSource = '本地采集，尚未上传';
    hudLines = ['图片仅在内存，授权后点击识别'];
    changed();
  }

  void showError(Object failure) {
    error = failure.toString();
    hudTitle = '操作失败';
    hudSource = '本地操作反馈';
    hudLines = [error];
    changed();
  }

  Future<void> validateLocal() async {
    cancel();
    final epoch = _epoch;
    result = null;
    error = '';
    if (frame == null || !uploadConsent) {
      showError(
        ApiFailure(frame == null ? '请先拍摄或选择图片' : '请先同意把图片提交到Windows本地服务校验'),
      );
      return;
    }
    busy = true;
    hudTitle = '正在本地校验';
    hudSource = '本地校验，不调用AI';
    hudLines = ['仅提交至本地网关，不调用云端AI'];
    changed();
    try {
      final checked = await api.validateImage(frame!, mime, true);
      if (epoch != _epoch || _disposed) return;
      final image = checked['image'] as Map;
      hudTitle = '本地上传校验通过';
      hudLines = [
        '${image['width']} × ${image['height']} · ${image['format']}',
        '未发送云端，未进行AI识别',
      ];
      status = '本地解码/清理通过；不是OCR或真实AI验收';
    } catch (failure) {
      if (epoch == _epoch && !_disposed) {
        error = failure.toString();
        hudTitle = '本地校验失败';
        hudLines = [error];
      }
    } finally {
      if (epoch == _epoch && !_disposed) {
        busy = false;
        changed();
      }
    }
  }

  Future<void> ask(String question) async {
    cancel();
    final epoch = _epoch;
    result = null;
    error = '';
    if (kind != 'chat' && (frame == null || !uploadConsent)) {
      showError(ApiFailure(frame == null ? '请先拍摄或选择图片' : '请先同意本次上传图片'));
      return;
    }
    if (kind != 'translate' && question.trim().isEmpty) {
      showError(ApiFailure('请输入问题'));
      return;
    }
    if (question.length > 500) {
      showError(ApiFailure('问题不得超过500字'));
      return;
    }
    final id = newRequestId();
    _activeId = id;
    busy = true;
    hudTitle = '正在处理';
    hudSource = mode == 'live' ? '真实AI请求中' : '模拟演示请求中';
    hudLines = [mode == 'live' ? '正在请求真实 AI' : '模拟演示，不分析图片'];
    changed();
    try {
      final answer = await api.ask(
        mode: mode,
        kind: kind,
        question: question.trim(),
        requestId: id,
        image: kind == 'chat' ? null : frame,
        mime: mime,
        consent: uploadConsent,
        sourceLanguage: sourceLanguage,
        targetLanguage: targetLanguage,
      );
      if (epoch != _epoch || _disposed) return;
      result = answer;
      hudSource = mode == 'live' ? '真实AI · openai' : '模拟演示 · demo';
      final hud = answer['hud'] as Map;
      hudTitle = hud['title'] is String ? hud['title'] as String : '识别结果';
      hudLines = (hud['lines'] as List).map((line) => line.toString()).toList();
      await display.show(
        HudFrame(
          title: hudTitle,
          lines: List.unmodifiable(hudLines),
          mode: mode,
          simulated: mode == 'demo',
        ),
      );
    } catch (failure) {
      if (epoch != _epoch || _disposed) return;
      error = failure.toString();
      hudTitle = '识别失败';
      hudSource = mode == 'live' ? '真实AI请求失败，未得到结果' : '模拟演示请求失败';
      hudLines = [error];
      // Timeout/cancel does not imply cloud inference or billing was reversed.
      if (failure is ApiFailure && failure.code == 'CLIENT_TIMEOUT') {
        _cancelRemote(id);
      }
    } finally {
      if (epoch == _epoch && !_disposed) {
        busy = false;
        _activeId = null;
        changed();
      }
    }
  }

  void _cancelRemote(String id) {
    api.cancel(id).catchError((Object _) {
      /* Local epoch still rejects late results. */
    });
  }

  void cancel() {
    ++_epoch;
    final id = _activeId;
    _activeId = null;
    busy = false;
    if (id != null) _cancelRemote(id);
  }

  void cancelByUser() {
    cancel();
    result = null;
    error = '';
    hudTitle = '已取消等待';
    hudSource = '已取消，未得到新结果';
    hudLines = ['迟到结果不会显示；云端处理可能继续'];
    changed();
  }

  Future<void> wipe() async {
    cancel();
    final epoch = _epoch;
    frame = null;
    result = null;
    captureConsent = false;
    uploadConsent = false;
    error = '';
    hudTitle = '本地画面已清除';
    hudSource = '本地删除反馈';
    hudLines = ['正在请求清除服务器内存'];
    changed();
    try {
      await display.clear();
      await api.wipe();
      if (epoch != _epoch || _disposed) return;
      hudLines = ['本地和服务器内存已清除；云端数据不在范围内'];
    } catch (failure) {
      if (epoch != _epoch || _disposed) return;
      error = failure.toString();
      hudLines = ['服务器删除失败，请重试'];
    }
    changed();
  }

  @override
  void dispose() {
    cancel();
    _disposed = true;
    api.close();
    super.dispose();
  }
}
