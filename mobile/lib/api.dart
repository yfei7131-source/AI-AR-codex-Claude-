import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiFailure implements Exception {
  ApiFailure(this.message, {this.code = 'CLIENT_ERROR'});
  final String message;
  final String code;
  @override
  String toString() => message;
}

class GlassesApi {
  GlassesApi({http.Client? client, String? baseUrl, Uri? webOrigin})
    : client = client ?? http.Client(),
      base = _baseUri(baseUrl, webOrigin) {
    if (!(kIsWeb || webOrigin != null) &&
        (base.scheme != 'http' ||
            !['127.0.0.1', 'localhost', '::1'].contains(base.host) ||
            base.userInfo.isNotEmpty ||
            base.path.isNotEmpty && base.path != '/' ||
            base.hasQuery ||
            base.hasFragment)) {
      throw ArgumentError(
        'API_BASE_URL 必须为 localhost HTTP 地址；Android 请使用 adb reverse',
      );
    }
  }
  final http.Client client;
  final Uri base;
  String? _sessionToken;
  bool get hasSessionToken => _sessionToken != null;
  Duration timeout = const Duration(seconds: 40);

  static Uri _baseUri(String? override, Uri? webOrigin) {
    if (kIsWeb || webOrigin != null) {
      final origin = webOrigin ?? Uri.base;
      final loopback = ['localhost', '127.0.0.1', '::1'].contains(origin.host);
      if ((origin.scheme != 'https' &&
              !(origin.scheme == 'http' && loopback)) ||
          origin.userInfo.isNotEmpty) {
        throw ArgumentError('手机Web需要已信任的同源HTTPS；仅本机localhost可使用HTTP');
      }
      final base = Uri.parse(origin.origin);
      if (override != null && Uri.parse(override).origin != base.origin) {
        throw ArgumentError('Web API必须与当前页面同源，不能向其他主机发送会话凭据');
      }
      return base;
    }
    return Uri.parse(
      override ??
          const String.fromEnvironment(
            'API_BASE_URL',
            defaultValue: 'http://127.0.0.1:8765',
          ),
    );
  }

  void setSessionToken(String? value) {
    if (value == null || value.isEmpty) {
      _sessionToken = null;
      return;
    }
    if (!RegExp(r'^[A-Za-z0-9_-]{1,512}$').hasMatch(value)) {
      throw ArgumentError('配对会话凭据格式无效，请重新打开Windows生成的链接');
    }
    _sessionToken = value;
  }

  Future<Map<String, dynamic>> request(
    String path, [
    Map<String, dynamic>? data,
  ]) async {
    try {
      if (!RegExp(r'^[a-z]+(?:/[a-z]+)*$').hasMatch(path)) {
        throw ArgumentError('无效API路径');
      }
      final url = base.replace(path: '/api/$path');
      final headers = <String, String>{
        if (data != null) 'Content-Type': 'application/json',
        if (_sessionToken != null) 'Authorization': 'Bearer $_sessionToken',
      };
      final response =
          await (data == null
                  ? client.get(url, headers: headers)
                  : client.post(url, headers: headers, body: jsonEncode(data)))
              .timeout(timeout);
      final Object? decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiFailure(
          decoded['error'] is String ? decoded['error'] as String : '服务请求失败',
          code: decoded['code'] is String
              ? decoded['code'] as String
              : 'HTTP_ERROR',
        );
      }
      return decoded;
    } on TimeoutException {
      throw ApiFailure(
        '请求超时；未获得结果，请检查网络后手动重试。云端处理可能仍在继续。',
        code: 'CLIENT_TIMEOUT',
      );
    } on FormatException {
      throw ApiFailure('服务响应格式无效', code: 'INVALID_RESPONSE');
    } on http.ClientException {
      throw ApiFailure(
        kIsWeb
            ? '同源服务连接失败；检查Windows网关、HTTPS信任与配对会话'
            : '本地 API 连接失败；检查服务与 adb reverse',
        code: 'CONNECTION_FAILED',
      );
    }
  }

  Future<Map<String, dynamic>> health() async {
    final data = await request('health');
    final seconds = data['request_timeout_seconds'];
    if (seconds is num && seconds > 0 && seconds < 300) {
      timeout = Duration(milliseconds: ((seconds + 15) * 1000).round());
    }
    return data;
  }

  Future<Map<String, dynamic>> ask({
    required String mode,
    required String kind,
    required String question,
    required String requestId,
    Uint8List? image,
    String mime = 'image/jpeg',
    bool consent = false,
    String sourceLanguage = 'auto',
    String targetLanguage = 'zh-CN',
  }) async {
    final data = await request('ask', {
      'mode': mode,
      'kind': kind,
      'question': question,
      'client_request_id': requestId,
      'image_data': image == null
          ? null
          : 'data:$mime;base64,${base64Encode(image)}',
      'consent': consent,
      if (kind == 'translate') ...{
        'output_format': 'ocr',
        'source_language': sourceLanguage,
        'target_language': targetLanguage,
      },
    });
    if (data['mode'] != mode ||
        data['simulated'] != (mode == 'demo') ||
        data['provider'] != (mode == 'demo' ? 'demo' : 'openai')) {
      throw ApiFailure('回答来源与所选模式不一致，已拒绝展示', code: 'SOURCE_MISMATCH');
    }
    if (data['answer'] is! String ||
        data['hud'] is! Map ||
        (data['hud'] as Map)['lines'] is! List) {
      throw ApiFailure('服务缺少有效回答或 HUD', code: 'INVALID_RESPONSE');
    }
    if (kind == 'translate') {
      final ocr = data['ocr'];
      if (ocr is! Map ||
          ocr['original_text'] is! String ||
          ocr['translated_text'] is! String ||
          ocr['source_language'] is! String ||
          ocr['target_language'] != targetLanguage ||
          ocr['uncertain'] is! bool) {
        throw ApiFailure('OCR 结构不完整，不能把普通回答当作文字识别结果', code: 'INVALID_OCR');
      }
    }
    return data;
  }

  Future<void> cancel(String id) async {
    await request('requests/cancel', {'client_request_id': id});
  }

  Future<void> wipe() async {
    await request('privacy/delete', {});
  }

  Future<Map<String, dynamic>> validateImage(
    Uint8List image,
    String mime,
    bool consent,
  ) async {
    final response = await request('media/validate', {
      'image_data': 'data:$mime;base64,${base64Encode(image)}',
      'consent': consent,
    });
    if (response['validated'] != true ||
        response['scope'] != 'local_only' ||
        response['cloud_sent'] != false ||
        response['image'] is! Map) {
      throw ApiFailure(
        '本地校验响应范围不符，不能视作本地验收通过',
        code: 'INVALID_VALIDATION_SCOPE',
      );
    }
    return response;
  }

  void close() {
    _sessionToken = null;
    client.close();
  }
}
