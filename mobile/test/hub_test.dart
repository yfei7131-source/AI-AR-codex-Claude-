import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_ar_glasses/api.dart';
import 'package:ai_ar_glasses/controller.dart';
import 'package:ai_ar_glasses/device_adapter.dart';
import 'package:ai_ar_glasses/main.dart';
import 'package:ai_ar_glasses/hud_adapter.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> answer(String mode, {bool ocr = false}) => {
  'mode': mode,
  'provider': mode == 'live' ? 'openai' : 'demo',
  'simulated': mode == 'demo',
  'answer': mode == 'demo' ? '【模拟演示】' : '画面中的标牌',
  'hud': {
    'title': '眼前识别',
    'lines': ['画面中的标牌'],
  },
  if (ocr)
    'ocr': {
      'original_text': 'STOP',
      'translated_text': '停',
      'source_language': 'en',
      'target_language': 'zh-CN',
      'uncertain': false,
    },
};
http.Response json(Map<String, dynamic> body, [int status = 200]) =>
    http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );
final frame = Uint8List.fromList([
  255,
  216,
  255,
  217,
]); // Transport fixture; actual decoding belongs to server validation.
GlassesApi apiWith(Future<http.Response> Function(http.Request) handler) =>
    GlassesApi(client: MockClient(handler));

void main() {
  test('API restricts endpoints to loopback, without credentials', () {
    for (final address in [
      'https://example.com',
      'http://10.0.2.2:8765',
      'http://key@localhost:8765',
      'http://localhost:8765/api',
      'http://localhost:8765?key=secret',
    ]) {
      expect(() => GlassesApi(baseUrl: address), throwsArgumentError);
    }
    final api = GlassesApi();
    expect(api.base.host, '127.0.0.1');
    api.close();
  });
  test('live vision posts image, explicit consent, mode, client request id; no API key', () async {
    late http.Request sent;
    final api = apiWith((request) async {
      sent = request;
      return json(answer('live'));
    });
    await api.ask(
      mode: 'live',
      kind: 'vision',
      question: '这是什么',
      requestId: 'uuid',
      image: frame,
      consent: true,
    );
    final body = jsonDecode(sent.body) as Map;
    expect(body['mode'], 'live');
    expect(body['image_data'], 'data:image/jpeg;base64,${base64Encode(frame)}');
    expect(body['consent'], true);
    expect(body['client_request_id'], 'uuid');
    expect(sent.headers.containsKey('Authorization'), false);
    expect(sent.url.host, '127.0.0.1');
    api.close();
  });
  test(
    'OCR preserves original/translation and target language contract',
    () async {
      late Map body;
      final api = apiWith((request) async {
        body = jsonDecode(request.body) as Map;
        return json(answer('live', ocr: true));
      });
      final result = await api.ask(
        mode: 'live',
        kind: 'translate',
        question: '',
        requestId: 'uuid',
        image: frame,
        consent: true,
        sourceLanguage: 'en',
      );
      expect(body['output_format'], 'ocr');
      expect(body['source_language'], 'en');
      expect(body['target_language'], 'zh-CN');
      expect((result['ocr'] as Map)['original_text'], 'STOP');
      api.close();
    },
  );
  test('live cannot display demo, unknown provider or malformed OCR', () async {
    for (final invalid in [
      answer('demo'),
      {...answer('live'), 'provider': 'unknown'},
      answer('live'),
    ]) {
      final api = apiWith((_) async => json(invalid));
      await expectLater(
        api.ask(
          mode: 'live',
          kind: 'translate',
          question: '',
          requestId: 'uuid',
          image: frame,
          consent: true,
        ),
        throwsA(isA<ApiFailure>()),
      );
      api.close();
    }
  });
  test('API exposes configuration error without any demo fallback', () async {
    var count = 0;
    final api = apiWith((_) async {
      ++count;
      return json({
        'error': 'OPENAI_API_KEY 未配置',
        'code': 'AI_NOT_CONFIGURED',
      }, 503);
    });
    await expectLater(
      api.ask(mode: 'live', kind: 'chat', question: '你好', requestId: 'uuid'),
      throwsA(
        isA<ApiFailure>().having(
          (error) => error.code,
          'code',
          'AI_NOT_CONFIGURED',
        ),
      ),
    );
    expect(count, 1);
    api.close();
  });
  test('invalid JSON and request timeout become controlled errors', () async {
    final invalid = apiWith(
      (_) async => http.Response('<html>oops</html>', 200),
    );
    await expectLater(
      invalid.health(),
      throwsA(
        isA<ApiFailure>().having(
          (error) => error.code,
          'code',
          'INVALID_RESPONSE',
        ),
      ),
    );
    invalid.close();
    final timeout = apiWith((_) => Completer<http.Response>().future)
      ..timeout = const Duration(milliseconds: 1);
    await expectLater(
      timeout.health(),
      throwsA(
        isA<ApiFailure>().having(
          (error) => error.code,
          'code',
          'CLIENT_TIMEOUT',
        ),
      ),
    );
    timeout.close();
  });
  test(
    'health adjusts client timeout but does not claim cloud authenticated',
    () async {
      final api = apiWith(
        (_) async => json({
          'ready': true,
          'mode': 'live',
          'provider': 'openai',
          'request_timeout_seconds': 25,
        }),
      );
      await api.health();
      expect(api.timeout, const Duration(seconds: 40));
      api.close();
    },
  );
  test(
    'controller requires image consent and never sends before click',
    () async {
      var calls = 0;
      final hub = HubController(
        apiWith((_) async {
          ++calls;
          return json(answer('demo'));
        }),
      );
      hub.setFrame(frame, 'image/jpeg');
      expect(calls, 0);
      await hub.ask('图片是什么');
      expect(calls, 0);
      expect(hub.error, contains('同意'));
      hub.uploadConsent = true;
      await hub.ask('图片是什么');
      expect(calls, 1);
      expect(hub.result?['simulated'], true);
      hub.dispose();
    },
  );
  test(
    'controller image size and MIME validation protects local upload path',
    () {
      final hub = HubController(apiWith((_) async => json(answer('demo'))));
      hub.setFrame(frame, 'image/jpeg');
      expect(
        () => hub.setFrame(Uint8List(0), 'image/jpeg'),
        throwsA(isA<ApiFailure>()),
      );
      expect(hub.frame, isNull);
      expect(
        () => hub.setFrame(frame, 'image/gif'),
        throwsA(isA<ApiFailure>()),
      );
      expect(
        () => hub.setFrame(Uint8List(2097153), 'image/png'),
        throwsA(isA<ApiFailure>()),
      );
      hub.dispose();
    },
  );
  test(
    'cancel notifies backend UUID and ignores late inference result',
    () async {
      final pending = Completer<http.Response>();
      final requests = <Map>[];
      final hub = HubController(
        apiWith((request) async {
          if (request.url.path == '/api/ask') return pending.future;
          requests.add(jsonDecode(request.body) as Map);
          return json({'cancelled': true});
        }),
      );
      hub.kind = 'chat';
      final operation = hub.ask('你好');
      await Future<void>.delayed(Duration.zero);
      hub.cancelByUser();
      pending.complete(json(answer('demo')));
      await operation;
      await Future<void>.delayed(Duration.zero);
      expect(hub.result, isNull);
      expect(hub.hudTitle, '已取消等待');
      expect(
        requests.single['client_request_id'],
        matches(RegExp(r'^[0-9a-f-]{36}$')),
      );
      hub.dispose();
    },
  );
  test(
    'late privacy deletion response cannot overwrite a newer chosen image',
    () async {
      final deleted = Completer<http.Response>();
      final hub = HubController(apiWith((_) => deleted.future));
      final operation = hub.wipe();
      await Future<void>.delayed(Duration.zero);
      hub.setFrame(frame, 'image/jpeg');
      deleted.complete(json({'cleared': true}));
      await operation;
      expect(hub.hudTitle, '图片已采集');
      expect(hub.hudLines.single, contains('授权后点击识别'));
      expect(hub.frame, isNotNull);
      hub.dispose();
    },
  );
  test(
    'privacy wipe clears image and consents; late response cannot restore HUD',
    () async {
      final pending = Completer<http.Response>();
      final hub = HubController(
        apiWith(
          (request) async => request.url.path == '/api/ask'
              ? pending.future
              : json({'cleared': true}),
        ),
      );
      hub.setFrame(frame, 'image/jpeg');
      hub.captureConsent = true;
      hub.uploadConsent = true;
      final operation = hub.ask('是什么');
      await hub.wipe();
      pending.complete(json(answer('demo')));
      await operation;
      expect(hub.frame, isNull);
      expect(hub.captureConsent, false);
      expect(hub.uploadConsent, false);
      expect(hub.result, isNull);
      expect(hub.hudLines.single, contains('已清除'));
      hub.dispose();
    },
  );
  test(
    'device adapter remains honestly disconnected and refuses fake writes',
    () async {
      final adapter = UnconfiguredDeviceAdapter();
      expect(adapter.connection, DeviceConnection.disconnected);
      await expectLater(adapter.connect(), throwsUnsupportedError);
      await expectLater(adapter.writeControl(Uint8List(8)), throwsStateError);
    },
  );
  test('BLE control codec matches firmware 8-byte little endian contract', () {
    expect(DeviceControl.encode(ControlOpcode.capture, 0x1234), [
      1,
      2,
      0x34,
      0x12,
      0,
      0,
      0,
      0,
    ]);
    expect(DeviceControl.encode(ControlOpcode.consent, 1, argument: 1), [
      1,
      4,
      1,
      0,
      1,
      0,
      0,
      0,
    ]);
    expect(
      () => DeviceControl.encode(ControlOpcode.consent, 1, argument: 2),
      throwsArgumentError,
    );
    expect(
      () => DeviceControl.encode(ControlOpcode.status, 65536),
      throwsArgumentError,
    );
    expect(
      () => DeviceControl.encode(ControlOpcode.capture, 1, argument: 1),
      throwsArgumentError,
    );
  });
  test(
    'BLE status preserves unknown battery, privacy flag and firmware errors',
    () {
      final frame = Uint8List.fromList([
        1,
        2,
        7,
        3,
        0x34,
        0x12,
        255,
        4,
        0x12,
        0x34,
        0x56,
        0x78,
        2,
        0,
        0,
        0,
        3,
        0,
        0,
        0,
      ]);
      final status = DeviceStatus.decode(frame);
      expect(status.requestId, 0x1234);
      expect(status.batteryPercent, isNull);
      expect(status.uptimeMs, 0x78563412);
      expect(status.captures, 2);
      expect(status.errorCount, 3);
      expect(status.connected, true);
      expect(status.consent, true);
      expect(status.boardConfigured, true);
      expect(status.physicalPrivacyVerified, false);
      expect(status.errorLabel, 'PRIVACY_UNVERIFIED');
      frame[3] = 200;
      expect(DeviceStatus.decode(frame).errorLabel, 'unknown(200)');
      expect(() => DeviceStatus.decode(Uint8List(19)), throwsFormatException);
    },
  );
  test(
    'phone HUD adapter only previews, optical adapter cannot fake delivery',
    () async {
      final preview = PhonePreviewHudAdapter();
      const frame = HudFrame(
        title: '识别',
        lines: ['STOP'],
        mode: 'live',
        simulated: false,
      );
      await preview.show(frame);
      expect(preview.target, HudTarget.phonePreview);
      expect(preview.lastFrame, same(frame));
      await preview.clear();
      expect(preview.lastFrame, isNull);
      final optical = UnconfiguredOpticalHudAdapter();
      expect(optical.available, false);
      await expectLater(optical.show(frame), throwsUnsupportedError);
    },
  );
  testWidgets('App shows honest device state and image privacy controls', (
    tester,
  ) async {
    final hub = HubController(
      apiWith(
        (_) async => json({
          'ready': true,
          'provider': 'demo',
          'max_image_bytes': 2097152,
          'request_timeout_seconds': 25,
        }),
      ),
    );
    await tester.pumpWidget(HubApp(controller: hub));
    await tester.pumpAndSettle();
    expect(find.textContaining('disconnected'), findsOneWidget);
    expect(find.byKey(const Key('capture-consent')), findsOneWidget);
    expect(find.byKey(const Key('upload-consent')), findsOneWidget);
    expect(find.textContaining('DEMO'), findsWidgets);
    await tester.scrollUntilVisible(
      find.byKey(const Key('hud-source')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('手机 HUD 预览'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    hub.dispose();
  });
  testWidgets('App cannot submit visual request without a captured image', (
    tester,
  ) async {
    var askCalls = 0;
    final hub = HubController(
      apiWith((request) async {
        if (request.url.path == '/api/ask') ++askCalls;
        return json({'ready': true, 'provider': 'demo'});
      }),
    );
    await tester.pumpWidget(HubApp(controller: hub));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('ask')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.drag(find.byType(ListView), const Offset(0, -120));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('ask')));
    await tester.pumpAndSettle();
    expect(askCalls, 0);
    expect(hub.error, contains('拍摄'));
    await tester.pumpWidget(const SizedBox());
    hub.dispose();
  });
}
