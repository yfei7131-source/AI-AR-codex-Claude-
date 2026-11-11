import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'device_adapter.dart';
import 'native_ble_codec.dart';

/// Actual iOS platform bridge. No connection or battery value is simulated.
/// Android/Web remain unconfigured until their own native implementation exists.
class IosGlassesDeviceAdapter implements GlassesDeviceAdapter {
  IosGlassesDeviceAdapter({
    MethodChannel? methods,
    Stream<dynamic>? nativeEvents,
  }) : _methods = methods ?? const MethodChannel('aiar/device'),
       _injectedEvents = nativeEvents;
  final MethodChannel _methods;
  final Stream<dynamic>? _injectedEvents;
  final _events = StreamController<Map<Object?, Object?>>.broadcast();
  StreamSubscription<dynamic>? _subscription;
  DeviceConnection _connection = DeviceConnection.disconnected;
  DeviceStatus? lastStatus;
  String? _selectedId;
  bool _disposed = false;
  int _epoch = 0;
  bool get supported => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;
  @override
  DeviceConnection get connection => _connection;
  Stream<Map<Object?, Object?>> get events {
    _listen();
    return _events.stream;
  }

  void _listen() {
    if (_subscription != null || !supported || _disposed) return;
    _subscription =
        (_injectedEvents ??
                const EventChannel('aiar/device_events')
                    .receiveBroadcastStream())
            .listen(
              (dynamic value) {
                if (_disposed || value is! Map) return;
                final event = Map<Object?, Object?>.from(value);
                if (event['type'] == 'status') {
                  try {
                    final bytes = event['bytes'];
                    if (bytes is! Uint8List) {
                      throw const FormatException('原生状态必须是20字节');
                    }
                    lastStatus = DeviceStatus.decode(bytes);
                  } on FormatException catch (error) {
                    _events.addError(error);
                    return;
                  }
                }
                if (event['type'] == 'connection') {
                  final state = event['state'];
                  if (state == 'ready' && lastStatus?.connected == true) {
                    _connection = DeviceConnection.connected;
                  } else if (state == 'connecting' ||
                      state == 'link_connected') {
                    _connection = DeviceConnection.connecting;
                  } else if (state == 'disconnected') {
                    _epoch++;
                    _connection = DeviceConnection.disconnected;
                    lastStatus = null;
                  }
                }
                _events.add(event);
              },
              onError: (Object error) {
                if (!_disposed) _events.addError(error);
              },
            );
  }

  Future<T?> _call<T>(String method, [Object? arguments]) async {
    if (_disposed) throw StateError('设备适配器已关闭');
    if (!supported) throw UnsupportedError('此原生BLE适配器仅支持iOS；当前平台未配置');
    _listen();
    try {
      return await _methods.invokeMethod<T>(method, arguments);
    } on MissingPluginException {
      throw UnsupportedError('iOS原生BLE通道未注册，不能假装连接');
    }
  }

  Future<Map<Object?, Object?>> permissions() async =>
      (await _call<Map<Object?, Object?>>('permissions'))!;
  Future<void> startScan({required bool consent, int seconds = 10}) async {
    if (!consent) throw StateError('扫描蓝牙设备需要明确同意');
    if (seconds < 1 || seconds > 30) throw ArgumentError('扫描时长必须1–30秒');
    await _call<Object>('scan', {'consent': true, 'seconds': seconds});
  }

  Future<void> stopScan() async {
    await _call<Object>('stopScan');
  }

  Future<void> connectTo(String identifier) async {
    if (identifier.isEmpty) throw ArgumentError('请选择扫描到的设备');
    _selectedId = identifier;
    await connect();
  }

  @override
  Future<void> connect() async {
    if (_selectedId == null) throw StateError('请先扫描并明确选择设备');
    _connection = DeviceConnection.connecting;
    final epoch = _epoch;
    try {
      final reply = await _call<Map<Object?, Object?>>('connect', {
        'id': _selectedId,
      });
      final bytes = reply?['status'];
      if (epoch != _epoch) throw StateError('连接已被取消或断开');
      if (reply?['connected'] != true || bytes is! Uint8List) {
        throw const FormatException('设备未返回有效连接确认');
      }
      final status = DeviceStatus.decode(bytes);
      if (!status.connected) throw StateError('设备状态尚未连接');
      lastStatus = status;
      _connection = DeviceConnection.connected;
    } catch (_) {
      _connection = DeviceConnection.disconnected;
      rethrow;
    }
  }

  @override
  Future<void> disconnect() async {
    _epoch++;
    try {
      if (supported && !_disposed) await _call<Object>('disconnect');
    } finally {
      _connection = DeviceConnection.disconnected;
      lastStatus = null;
    }
  }

  @override
  Future<void> writeControl(Uint8List bytes) async {
    NativeBleCodec.validateControl(bytes);
    if (_connection != DeviceConnection.connected) throw StateError('BLE设备未就绪');
    if (bytes[1] == 3 || (bytes[1] == 4 && bytes[4] == 0)) _epoch++;
    await _call<Object>('writeControl', bytes);
  }

  Future<void> cancelCapture(int requestId) =>
      writeControl(DeviceControl.encode(ControlOpcode.cancel, requestId));
  Future<DeviceMediaSession> openMediaSession(
    int requestId, {
    required bool consent,
    int ttlMs = 30000,
  }) async {
    if (!consent) throw StateError('开启设备Wi-Fi媒体会话需要明确同意');
    if (_connection != DeviceConnection.connected) throw StateError('BLE设备未就绪');
    final command = NativeBleCodec.mediaControl(1, requestId, ttlMs: ttlMs);
    final epoch = _epoch;
    final value = await _call<Map<Object?, Object?>>('mediaSession', command);
    if (epoch != _epoch || _connection != DeviceConnection.connected) {
      throw StateError('媒体会话请求已取消');
    }
    if (value == null) throw const FormatException('没有媒体会话响应');
    return DeviceMediaSession.decode(value, expectedRequestId: requestId);
  }

  Future<DeviceMediaFrame> fetchFrame(
    DeviceMediaSession session,
    int requestId, {
    required bool consent,
  }) async {
    if (!consent) throw StateError('获取设备拍摄图片需要明确同意');
    if (requestId < 0 || requestId > 65535) throw ArgumentError('无效采集标识');
    if (_connection != DeviceConnection.connected) throw StateError('BLE设备未就绪');
    final epoch = _epoch;
    final value = await _call<Map<Object?, Object?>>('fetchFrame', {
      'baseUrl': session.baseUrl.toString(),
      'token': session.token,
      'requestId': requestId,
      'consent': true,
    });
    if (epoch != _epoch || _connection != DeviceConnection.connected) {
      throw StateError('设备图片接收已取消');
    }
    if (value == null) throw const FormatException('没有设备图片响应');
    return DeviceMediaFrame.decode(value, requestId);
  }

  Future<void> cancelFetch(int requestId) async {
    _epoch++;
    await _call<Object>('cancelFetch');
    if (_connection == DeviceConnection.connected) {
      await cancelCapture(requestId);
    }
  }

  Future<void> revokeMediaSession(int requestId) async {
    final command = NativeBleCodec.mediaControl(3, requestId);
    _epoch++;
    await _call<Object>('cancelFetch');
    if (_connection != DeviceConnection.connected) {
      throw StateError('本地接收已取消；BLE未连接，无法确认设备撤销');
    }
    final result = await _call<Map<Object?, Object?>>('mediaSession', command);
    if (result == null ||
        MediaSessionSnapshot.classify(result, requestId, 3) !=
            MediaSessionDisposition.revoked) {
      throw const FormatException('设备尚未确认对应媒体会话撤销');
    }
  }

  Future<void> dispose() async {
    if (_disposed) return;
    await disconnect();
    _disposed = true;
    await _subscription?.cancel();
    await _events.close();
  }
}

GlassesDeviceAdapter createNativeDeviceAdapter() =>
    !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS
    ? IosGlassesDeviceAdapter()
    : UnconfiguredDeviceAdapter();
