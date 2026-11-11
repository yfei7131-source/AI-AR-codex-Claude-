import 'dart:async';
import 'dart:convert';

import 'package:ai_ar_glasses/api.dart';
import 'package:ai_ar_glasses/controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'hub_test.dart' as fixtures;

void main() {
  test('Web uses page HTTPS origin and strips route/query/fragment from API requests', () async {
    late http.Request sent;
    final api = GlassesApi(
      webOrigin: Uri.parse(
        'https://192.168.1.20:9443/app/?other=x#pair=secret',
      ),
      client: fixtures.apiWith((request) async {
        sent = request;
        return fixtures.json({'ok': true});
      }).client,
    );
    await api.health();
    expect(sent.url.toString(), 'https://192.168.1.20:9443/api/health');
    expect(sent.headers.containsKey('Authorization'), false);
    api.close();
  });
  test('Web refuses insecure LAN and a different API origin', () {
    expect(
      () => GlassesApi(webOrigin: Uri.parse('http://192.168.1.20:9443/')),
      throwsArgumentError,
    );
    expect(
      () => GlassesApi(
        webOrigin: Uri.parse('https://192.168.1.20:9443/'),
        baseUrl: 'https://evil.invalid',
      ),
      throwsArgumentError,
    );
    final api = GlassesApi(webOrigin: Uri.parse('http://localhost:8765/'));
    expect(api.base.host, 'localhost');
    api.close();
  });
  test('memory-only session is sent on GET and POST Authorization, never URL or JSON body', () async {
    final sent = <http.Request>[];
    final api = fixtures.apiWith((request) async {
      sent.add(request);
      return fixtures.json({'ok': true});
    });
    api.setSessionToken('pair-token_123');
    await api.health();
    await api.request('notes', {'text': 'test'});
    for (final request in sent) {
      expect(request.headers['Authorization'], 'Bearer pair-token_123');
      expect(request.url.toString(), isNot(contains('pair-token')));
      expect(request.body, isNot(contains('pair-token')));
    }
    api.setSessionToken(null);
    await api.health();
    expect(sent.last.headers.containsKey('Authorization'), false);
    api.close();
  });
  test('session rejects header injection and paths cannot escape relative API namespace', () async {
    final api = fixtures.apiWith((_) async => fixtures.json({'ok': true}));
    expect(
      () => api.setSessionToken('token\r\nOther: value'),
      throwsArgumentError,
    );
    await expectLater(api.request('../health'), throwsArgumentError);
    api.close();
  });
  test('local media validation explicitly sends consent and checks no-cloud response scope', () async {
    late http.Request sent;
    final api = fixtures.apiWith((request) async {
      sent = request;
      return fixtures.json({
        'validated': true,
        'scope': 'local_only',
        'cloud_sent': false,
        'image': {'width': 1, 'height': 1, 'format': 'JPEG'},
      });
    });
    await api.validateImage(fixtures.frame, 'image/jpeg', true);
    expect(sent.url.path, '/api/media/validate');
    expect((jsonDecode(sent.body) as Map)['consent'], true);
    expect((jsonDecode(sent.body) as Map).containsKey('mode'), false);
    api.close();
  });
  test(
    'validation cannot pass with cloud flag or missing local scope',
    () async {
      for (final invalid in [
        {
          'validated': true,
          'scope': 'local_only',
          'cloud_sent': true,
          'image': {},
        },
        {'validated': true, 'cloud_sent': false, 'image': {}},
      ]) {
        final api = fixtures.apiWith((_) async => fixtures.json(invalid));
        await expectLater(
          api.validateImage(fixtures.frame, 'image/jpeg', true),
          throwsA(isA<ApiFailure>()),
        );
        api.close();
      }
    },
  );
  test('controller local validation works without AI readiness and never calls ask', () async {
    final calls = <String>[];
    final hub = HubController(
      fixtures.apiWith((request) async {
        calls.add(request.url.path);
        return fixtures.json({
          'validated': true,
          'scope': 'local_only',
          'cloud_sent': false,
          'image': {'width': 640, 'height': 480, 'format': 'JPEG'},
        });
      }),
    );
    hub.ready = false;
    hub.setMode('live');
    hub.setFrame(fixtures.frame, 'image/jpeg');
    await hub.validateLocal();
    expect(calls, isEmpty);
    expect(hub.error, contains('同意'));
    hub.uploadConsent = true;
    await hub.validateLocal();
    expect(calls, ['/api/media/validate']);
    expect(hub.hudTitle, '本地上传校验通过');
    expect(hub.hudSource, '本地校验，不调用AI');
    expect(hub.result, isNull);
    expect(hub.hudLines.last, contains('未进行AI'));
    hub.dispose();
  });
  test(
    'cancel or privacy delete rejects a late local validation result',
    () async {
      final pending = Completer<http.Response>();
      final hub = HubController(
        fixtures.apiWith(
          (request) async => request.url.path == '/api/media/validate'
              ? pending.future
              : fixtures.json({'cleared': true}),
        ),
      );
      hub.setFrame(fixtures.frame, 'image/jpeg');
      hub.uploadConsent = true;
      final operation = hub.validateLocal();
      await hub.wipe();
      pending.complete(
        fixtures.json({
          'validated': true,
          'scope': 'local_only',
          'cloud_sent': false,
          'image': {},
        }),
      );
      await operation;
      expect(hub.frame, isNull);
      expect(hub.hudTitle, '本地画面已清除');
      expect(hub.result, isNull);
      hub.dispose();
    },
  );
}
