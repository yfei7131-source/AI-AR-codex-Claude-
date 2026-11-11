import 'dart:typed_data';

enum DeviceConnection { unknown, disconnected, connecting, connected }

/// Transport contract only: no fabricated BLE connection, battery or HUD delivery.
abstract interface class GlassesDeviceAdapter {
  DeviceConnection get connection;
  Future<void> connect();
  Future<void> disconnect();
  Future<void> writeControl(Uint8List bytes);
}

class UnconfiguredDeviceAdapter implements GlassesDeviceAdapter {
  @override
  DeviceConnection get connection => DeviceConnection.disconnected;
  @override
  Future<void> connect() async => throw UnsupportedError('BLE 实机传输未配置');
  @override
  Future<void> disconnect() async {}
  @override
  Future<void> writeControl(Uint8List bytes) async => throw StateError('设备未连接');
}

enum ControlOpcode {
  status(1),
  capture(2),
  cancel(3),
  consent(4),
  clearLog(5);

  const ControlOpcode(this.value);
  final int value;
}

/// Candidate ESP32 protocol; JPEG media is not carried by this control packet.
class DeviceControl {
  static const serviceUuid = '8f13a001-6c55-4b8e-9d51-2f76a4b10000';
  static const controlUuid = '8f13a002-6c55-4b8e-9d51-2f76a4b10000';
  static const statusUuid = '8f13a003-6c55-4b8e-9d51-2f76a4b10000';
  static const mediaControlUuid = '8f13a004-6c55-4b8e-9d51-2f76a4b10000';
  static const mediaInfoUuid = '8f13a005-6c55-4b8e-9d51-2f76a4b10000';
  static Uint8List encode(
    ControlOpcode opcode,
    int requestId, {
    int argument = 0,
  }) {
    if (requestId < 0 ||
        requestId > 65535 ||
        argument < 0 ||
        argument > 0xffffffff ||
        (opcode == ControlOpcode.consent ? argument > 1 : argument != 0)) {
      throw ArgumentError('控制帧参数超出范围');
    }
    final bytes = ByteData(8)
      ..setUint8(0, 1)
      ..setUint8(1, opcode.value)
      ..setUint16(2, requestId, Endian.little)
      ..setUint32(4, argument, Endian.little);
    return bytes.buffer.asUint8List();
  }
}

/// Values preserve unknown future firmware codes rather than inventing a status.
class DeviceStatus {
  DeviceStatus._(
    this.state,
    this.flags,
    this.lastError,
    this.requestId,
    this.batteryPercent,
    this.logCount,
    this.uptimeMs,
    this.captures,
    this.errorCount,
  );
  final int state,
      flags,
      lastError,
      requestId,
      logCount,
      uptimeMs,
      captures,
      errorCount;
  final int? batteryPercent;
  bool get connected => flags & 1 != 0;
  bool get consent => flags & 2 != 0;
  bool get boardConfigured => flags & 4 != 0;
  bool get physicalPrivacyVerified => flags & 8 != 0;
  String get stateLabel =>
      const {0: 'idle', 1: 'capturing', 2: 'error'}[state] ?? 'unknown($state)';
  String get errorLabel =>
      const {
        0: 'OK',
        1: 'BAD_FRAME',
        2: 'BOARD_MISSING',
        3: 'PRIVACY_UNVERIFIED',
        4: 'NOT_CONNECTED',
        5: 'NO_CONSENT',
        6: 'BUSY',
        7: 'CAMERA_FAILED',
        8: 'MEDIA_NOT_CONFIGURED',
        9: 'DUPLICATE',
        10: 'QUEUE_FULL',
      }[lastError] ??
      'unknown($lastError)';
  factory DeviceStatus.decode(Uint8List frame) {
    if (frame.length != 20 ||
        frame[0] != 1 ||
        (frame[6] > 100 && frame[6] != 255)) {
      throw const FormatException('无效 BLE 状态帧');
    }
    final bytes = ByteData.sublistView(frame);
    return DeviceStatus._(
      frame[1],
      frame[2],
      frame[3],
      bytes.getUint16(4, Endian.little),
      frame[6] == 255 ? null : frame[6],
      frame[7],
      bytes.getUint32(8, Endian.little),
      bytes.getUint32(12, Endian.little),
      bytes.getUint32(16, Endian.little),
    );
  }
}
