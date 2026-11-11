import 'dart:async';

import 'package:ai_ar_glasses/device_adapter.dart';
import 'package:ai_ar_glasses/native_ble_adapter.dart';
import 'package:ai_ar_glasses/native_ble_codec.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

Uint8List statusBytes() {
  final value = Uint8List(20);
  value[0] = 1;
  value[2] = 1;
  value[6] = 255;
  return value;
}

Map<String, Object> leaseValues() => {
  'version': 2,
  'ready': true,
  'request_id': 3,
  'ssid': 'AIAR-TEST',
  'passphrase': 'nonsecret-test',
  'base_url': 'http://192.168.4.1',
  'token': 'a' * 64,
  'expires_in_ms': 30000,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('aiar/native_bridge_test');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
  });
  tearDown(() {
    messenger.setMockMethodCallHandler(channel, null);
    debugDefaultTargetPlatformOverride = null;
  });

  test('v1 control validation and v2 media bytes are exact little-endian', () {
    final consent = DeviceControl.encode(
      ControlOpcode.consent,
      0x1234,
      argument: 1,
    );
    NativeBleCodec.validateControl(consent);
    expect(consent, [1, 4, 0x34, 0x12, 1, 0, 0, 0]);
    final media = NativeBleCodec.mediaControl(1, 0x1234, ttlMs: 30000);
    expect(media.take(8), [2, 1, 0x34, 0x12, 0x30, 0x75, 0, 0]);
    expect(media.skip(8), List<int>.filled(12, 0));
    for (final bytes in [
      Uint8List(7),
      Uint8List.fromList([1, 4, 0, 0, 2, 0, 0, 0]),
    ]) {
      expect(
        () => NativeBleCodec.validateControl(bytes),
        throwsFormatException,
      );
    }
    expect(
      () => NativeBleCodec.mediaControl(1, 1, ttlMs: 120001),
      throwsArgumentError,
    );
    expect(
      () => NativeBleCodec.mediaControl(3, 1, ttlMs: 1000),
      throwsArgumentError,
    );
  });

  test(
    'scan needs consent and selecting a scanned id remains explicit',
    () async {
      final calls = <String>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call.method);
        return null;
      });
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await expectLater(adapter.startScan(consent: false), throwsStateError);
      await expectLater(adapter.connect(), throwsStateError);
      expect(calls, isEmpty);
      await adapter.startScan(consent: true);
      expect(calls, ['scan']);
      await adapter.dispose();
    },
  );

  test('connection waits for real native status instead of returning fabricated connected', () async {
    final pending = Completer<Object?>();
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'connect') return pending.future;
      return null;
    });
    final adapter = IosGlassesDeviceAdapter(
      methods: channel,
      nativeEvents: const Stream.empty(),
    );
    final connecting = adapter.connectTo('explicitly-selected-test-id');
    await Future<void>.delayed(Duration.zero);
    expect(adapter.connection, DeviceConnection.connecting);
    pending.complete({'connected': true, 'status': statusBytes()});
    await connecting;
    expect(adapter.connection, DeviceConnection.connected);
    expect(adapter.lastStatus?.batteryPercent, isNull);
    await adapter.disconnect();
    expect(adapter.connection, DeviceConnection.disconnected);
    await adapter.dispose();
  });

  test(
    'missing plugin and bad native acknowledgments never create a connection',
    () async {
      messenger.setMockMethodCallHandler(
        channel,
        (call) async => call.method == 'connect' ? {'connected': true} : null,
      );
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await expectLater(adapter.connectTo('test'), throwsFormatException);
      expect(adapter.connection, DeviceConnection.disconnected);
      await adapter.dispose();
      messenger.setMockMethodCallHandler(channel, null);
      final missing = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await expectLater(
        missing.startScan(consent: true),
        throwsUnsupportedError,
      );
    },
  );

  test(
    'unsupported Android uses unconfigured transport without native calls',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      expect(createNativeDeviceAdapter(), isA<UnconfiguredDeviceAdapter>());
      final adapter = IosGlassesDeviceAdapter(methods: channel);
      await expectLater(
        adapter.startScan(consent: true),
        throwsUnsupportedError,
      );
      expect(adapter.connection, DeviceConnection.disconnected);
    },
  );

  test(
    'native disconnect clears status and blocks subsequent control writes',
    () async {
      final nativeEvents = StreamController<dynamic>.broadcast();
      messenger.setMockMethodCallHandler(
        channel,
        (call) async => call.method == 'connect'
            ? {'connected': true, 'status': statusBytes()}
            : null,
      );
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: nativeEvents.stream,
      );
      await adapter.connectTo('test');
      nativeEvents.add({'type': 'connection', 'state': 'disconnected'});
      await Future<void>.delayed(Duration.zero);
      expect(adapter.connection, DeviceConnection.disconnected);
      expect(adapter.lastStatus, isNull);
      await expectLater(
        adapter.writeControl(DeviceControl.encode(ControlOpcode.capture, 2)),
        throwsStateError,
      );
      await adapter.dispose();
      await nativeEvents.close();
    },
  );

  test(
    'cancel uses actual v1 cancel control and native media cancellation',
    () async {
      final calls = <MethodCall>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call);
        return call.method == 'connect'
            ? {'connected': true, 'status': statusBytes()}
            : null;
      });
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await adapter.connectTo('test');
      await adapter.cancelFetch(42);
      expect(calls.map((c) => c.method), [
        'connect',
        'cancelFetch',
        'writeControl',
      ]);
      expect(
        calls.last.arguments,
        DeviceControl.encode(ControlOpcode.cancel, 42),
      );
      await adapter.dispose();
    },
  );

  test('media session validation rejects unready and non-device endpoints', () {
    final session = DeviceMediaSession.decode(leaseValues());
    expect(session.baseUrl.host, '192.168.4.1');
    expect(session.expiresInMs, 30000);
    expect(
      () => DeviceMediaSession.decode({'version': 2, 'ready': false}),
      throwsStateError,
    );
    for (final changes in [
      {'base_url': 'http://example.com'},
      {'token': 'short'},
      {'expires_in_ms': 120001},
    ]) {
      expect(
        () => DeviceMediaSession.decode({...leaseValues(), ...changes}),
        throwsFormatException,
      );
    }
  });

  test(
    'media revoke first cancels local fetch then sends exact v2 revoke',
    () async {
      final calls = <MethodCall>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call);
        if (call.method == 'connect') {
          return {'connected': true, 'status': statusBytes()};
        }
        if (call.method == 'mediaSession') {
          return {
            'version': 2,
            'request_id': 9,
            'ready': false,
            'error': 'revoked',
          };
        }
        return null;
      });
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await adapter.connectTo('test');
      await adapter.revokeMediaSession(9);
      expect(calls.map((call) => call.method), [
        'connect',
        'cancelFetch',
        'mediaSession',
      ]);
      expect(calls.last.arguments, NativeBleCodec.mediaControl(3, 9));
      await adapter.dispose();
    },
  );

  test(
    'fetch preserves consent, request association and explicit no_frame errors',
    () async {
      final calls = <MethodCall>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call);
        if (call.method == 'connect') {
          return {'connected': true, 'status': statusBytes()};
        }
        if (call.method == 'mediaSession') return leaseValues();
        if (call.method == 'fetchFrame') {
          throw PlatformException(
            code: 'NO_FRAME',
            message: 'No real device frame',
          );
        }
        return null;
      });
      final adapter = IosGlassesDeviceAdapter(
        methods: channel,
        nativeEvents: const Stream.empty(),
      );
      await adapter.connectTo('test');
      await expectLater(
        adapter.openMediaSession(3, consent: false),
        throwsStateError,
      );
      final session = await adapter.openMediaSession(3, consent: true);
      await expectLater(
        adapter.fetchFrame(session, 3, consent: false),
        throwsStateError,
      );
      await expectLater(
        adapter.fetchFrame(session, 3, consent: true),
        throwsA(isA<PlatformException>()),
      );
      final args = calls.last.arguments as Map<Object?, Object?>;
      expect(args['requestId'], 3);
      expect(args['consent'], true);
      await adapter.dispose();
    },
  );

  test('session snapshots wait for processed id and distinguish pending from terminal', () {
    final staleReady = {...leaseValues(), 'request_id': 2};
    expect(
      MediaSessionSnapshot.classify(staleReady, 3, 1),
      MediaSessionDisposition.wait,
    );
    for (final state in ['pairing_window_open', 'revoked']) {
      expect(
        MediaSessionSnapshot.classify(
          {'version': 2, 'request_id': 3, 'ready': false, 'error': state},
          3,
          1,
        ),
        MediaSessionDisposition.wait,
      );
    }
    for (final state in [
      'disabled',
      'ble_required',
      'pairing_required',
      'wifi_start_failed',
    ]) {
      expect(
        MediaSessionSnapshot.classify(
          {'version': 2, 'request_id': 3, 'ready': false, 'error': state},
          3,
          1,
        ),
        MediaSessionDisposition.terminal,
      );
    }
    expect(
      MediaSessionSnapshot.classify(leaseValues(), 3, 1),
      MediaSessionDisposition.ready,
    );
    expect(
      () => DeviceMediaSession.decode(staleReady, expectedRequestId: 3),
      throwsFormatException,
    );
    expect(
      () => NativeBleCodec.mediaControl(1, 0, ttlMs: 30000),
      throwsArgumentError,
    );
    expect(
      () => MediaSessionSnapshot.classify({'version': 2, 'ready': true}, 3, 1),
      throwsFormatException,
    );
  });

  test(
    'a revoke requires the exact processed request id and revoked state',
    () {
      final response = {
        'version': 2,
        'request_id': 9,
        'ready': false,
        'error': 'revoked',
      };
      expect(
        MediaSessionSnapshot.classify(response, 9, 3),
        MediaSessionDisposition.revoked,
      );
      expect(
        MediaSessionSnapshot.classify(response, 10, 3),
        MediaSessionDisposition.wait,
      );
      expect(
        MediaSessionSnapshot.classify(
          {...leaseValues(), 'request_id': 9},
          9,
          3,
        ),
        MediaSessionDisposition.wait,
      );
    },
  );

  test('open stays pending until native completion and cannot restore a late disconnected lease', () async {
    final pending = Completer<Object?>();
    var sessionWrites = 0;
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'connect') {
        return {'connected': true, 'status': statusBytes()};
      }
      if (call.method == 'mediaSession') {
        sessionWrites++;
        return pending.future;
      }
      return null;
    });
    final adapter = IosGlassesDeviceAdapter(
      methods: channel,
      nativeEvents: const Stream.empty(),
    );
    await adapter.connectTo('test');
    var completed = false;
    final opening = adapter.openMediaSession(3, consent: true).whenComplete(() {
      completed = true;
    });
    final rejected = expectLater(opening, throwsStateError);
    await Future<void>.delayed(Duration.zero);
    expect(completed, isFalse);
    await adapter.disconnect();
    pending.complete(leaseValues());
    await rejected;
    expect(sessionWrites, 1);
    expect(adapter.connection, DeviceConnection.disconnected);
    await adapter.dispose();
  });

  test('a bounded native frame timeout never automatically repeats capture or open', () async {
    final methods = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      methods.add(call.method);
      if (call.method == 'connect') {
        return {'connected': true, 'status': statusBytes()};
      }
      if (call.method == 'fetchFrame') {
        throw PlatformException(code: 'NO_FRAME_TIMEOUT');
      }
      return null;
    });
    final adapter = IosGlassesDeviceAdapter(
      methods: channel,
      nativeEvents: const Stream.empty(),
    );
    await adapter.connectTo('test');
    await expectLater(
      adapter.fetchFrame(
        DeviceMediaSession.decode(leaseValues()),
        3,
        consent: true,
      ),
      throwsA(isA<PlatformException>()),
    );
    expect(methods, ['connect', 'fetchFrame']);
    await adapter.dispose();
  });

  test('unverified or unrelated image is rejected and valid native result stays bytes', () {
    final values = <Object?, Object?>{
      'bytes': Uint8List.fromList([255, 216, 255, 217]),
      'mime': 'image/jpeg',
      'request_id': 3,
      'frame_id': 4,
      'sha256': 'b' * 64,
      'sha256_verified': true,
      'release_confirmed': false,
    };
    final frame = DeviceMediaFrame.decode(values, 3);
    expect(frame.bytes, [255, 216, 255, 217]);
    expect(frame.releaseConfirmed, isFalse);
    expect(() => DeviceMediaFrame.decode(values, 99), throwsFormatException);
    expect(
      () => DeviceMediaFrame.decode({...values, 'sha256_verified': false}, 3),
      throwsFormatException,
    );
    expect(
      () => DeviceMediaFrame.decode({...values, 'frame_id': 0}, 3),
      throwsFormatException,
    );
  });
}
