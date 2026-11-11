import 'dart:typed_data';

/// Device control stays v1/8 bytes. Development Wi-Fi leases use a004 v2/20 bytes.
class NativeBleCodec {
  static void validateControl(Uint8List bytes) {
    if (bytes.length != 8 || bytes[0] != 1 || bytes[1] < 1 || bytes[1] > 5) {
      throw const FormatException('无效 BLE 控制帧');
    }
    final argument = ByteData.sublistView(bytes).getUint32(4, Endian.little);
    if (bytes[1] == 4 ? argument > 1 : argument != 0) {
      throw const FormatException('无效 BLE 控制参数');
    }
  }

  static Uint8List mediaControl(int operation, int requestId, {int ttlMs = 0}) {
    if (operation < 1 ||
        operation > 3 ||
        requestId < 1 ||
        requestId > 65535 ||
        (operation == 1 ? ttlMs < 1000 || ttlMs > 120000 : ttlMs != 0)) {
      throw ArgumentError('无效媒体会话参数');
    }
    final data = ByteData(20)
      ..setUint8(0, 2)
      ..setUint8(1, operation)
      ..setUint16(2, requestId, Endian.little)
      ..setUint32(4, ttlMs, Endian.little);
    return data.buffer.asUint8List();
  }
}

class DeviceMediaSession {
  DeviceMediaSession._(
    this.ssid,
    this.passphrase,
    this.baseUrl,
    this.token,
    this.expiresInMs,
  );
  final String ssid, passphrase, token;
  final Uri baseUrl;
  final int expiresInMs;

  factory DeviceMediaSession.decode(
    Map<Object?, Object?> value, {
    int? expectedRequestId,
  }) {
    if (expectedRequestId != null &&
        MediaSessionSnapshot.classify(value, expectedRequestId, 1) !=
            MediaSessionDisposition.ready) {
      throw const FormatException('媒体会话尚未完成或请求标识不匹配');
    }
    if (value['version'] != 2 || value['ready'] != true) {
      throw StateError('设备媒体未就绪；需要按键配对窗口、已加密BLE和已审核硬件');
    }
    final ssid = value['ssid'],
        passphrase = value['passphrase'],
        token = value['token'];
    final base = Uri.tryParse(
      value['base_url'] is String ? value['base_url'] as String : '',
    );
    final ttl = value['expires_in_ms'];
    final processedId = value['request_id'];
    if (ssid is! String ||
        ssid.isEmpty ||
        ssid.length > 32 ||
        passphrase is! String ||
        passphrase.length < 8 ||
        passphrase.length > 63 ||
        token is! String ||
        !RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(token) ||
        base == null ||
        base.scheme != 'http' ||
        base.host != '192.168.4.1' ||
        base.port != 80 ||
        base.userInfo.isNotEmpty ||
        (base.path.isNotEmpty && base.path != '/') ||
        base.hasQuery ||
        base.hasFragment ||
        processedId is! int ||
        processedId < 1 ||
        processedId > 65535 ||
        ttl is! int ||
        ttl < 1 ||
        ttl > 120000) {
      throw const FormatException('设备媒体会话格式无效');
    }
    return DeviceMediaSession._(ssid, passphrase, base, token, ttl);
  }
}

enum MediaSessionDisposition { wait, ready, revoked, terminal }

/// ATT write acknowledgment is not operation completion. Only the processed
/// request_id in a005 may complete the caller's current session operation.
class MediaSessionSnapshot {
  static MediaSessionDisposition classify(
    Map<Object?, Object?> value,
    int expectedRequestId,
    int operation,
  ) {
    if (value['version'] != 2 ||
        value['request_id'] is! int ||
        (value['request_id'] as int) < 0 ||
        (value['request_id'] as int) > 65535 ||
        value['ready'] is! bool ||
        expectedRequestId < 1 ||
        expectedRequestId > 65535 ||
        operation < 1 ||
        operation > 3) {
      throw const FormatException('媒体会话快照缺少有效协议/请求关联字段');
    }
    if (value['request_id'] != expectedRequestId) {
      return MediaSessionDisposition.wait;
    }
    if (operation == 3) {
      if (value['ready'] == false && value['error'] == 'revoked') {
        return MediaSessionDisposition.revoked;
      }
      return MediaSessionDisposition.wait;
    }
    if (value['ready'] == true) return MediaSessionDisposition.ready;
    final error = value['error'];
    if (error is! String) throw const FormatException('未就绪会话缺少明确状态');
    if ([
          'disabled',
          'ble_required',
          'pairing_required',
          'wifi_start_failed',
        ].contains(error) ||
        (operation == 2 && error == 'revoked')) {
      return MediaSessionDisposition.terminal;
    }
    if (['pairing_window_open', 'revoked'].contains(error)) {
      return MediaSessionDisposition.wait;
    }
    throw const FormatException('未知媒体会话状态');
  }
}

class DeviceMediaFrame {
  DeviceMediaFrame._(
    this.bytes,
    this.requestId,
    this.frameId,
    this.sha256,
    this.releaseConfirmed,
  );
  final Uint8List bytes;
  final int requestId, frameId;
  final String sha256;
  final bool releaseConfirmed;

  factory DeviceMediaFrame.decode(
    Map<Object?, Object?> value,
    int expectedRequestId,
  ) {
    final bytes = value['bytes'],
        hash = value['sha256'],
        frameId = value['frame_id'];
    if (bytes is! Uint8List ||
        bytes.length < 4 ||
        bytes.length > 2097152 ||
        bytes[0] != 0xff ||
        bytes[1] != 0xd8 ||
        bytes[2] != 0xff ||
        value['mime'] != 'image/jpeg' ||
        value['request_id'] != expectedRequestId ||
        value['sha256_verified'] != true ||
        hash is! String ||
        !RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(hash) ||
        frameId is! int ||
        frameId <= 0 ||
        frameId > 0xffffffff) {
      throw const FormatException('设备图片未通过完整性或请求关联检查');
    }
    return DeviceMediaFrame._(
      Uint8List.fromList(bytes),
      expectedRequestId,
      frameId,
      hash,
      value['release_confirmed'] == true,
    );
  }
}
