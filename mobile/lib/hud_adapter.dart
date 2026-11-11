enum HudTarget { phonePreview, opticalGlasses }

class HudFrame {
  const HudFrame({
    required this.title,
    required this.lines,
    required this.mode,
    required this.simulated,
  });
  final String title;
  final List<String> lines;
  final String mode;
  final bool simulated;
}

abstract interface class HudDisplayAdapter {
  HudTarget get target;
  bool get available;
  Future<void> show(HudFrame frame);
  Future<void> clear();
}

/// Local phone preview only; neither BLE nor optical AR delivery is implied.
class PhonePreviewHudAdapter implements HudDisplayAdapter {
  HudFrame? lastFrame;
  @override
  HudTarget get target => HudTarget.phonePreview;
  @override
  bool get available => true;
  @override
  Future<void> show(HudFrame frame) async {
    lastFrame = frame;
  }

  @override
  Future<void> clear() async {
    lastFrame = null;
  }
}

/// Extension point for a tested Halo/optical transport and Chinese rasterizer.
class UnconfiguredOpticalHudAdapter implements HudDisplayAdapter {
  @override
  HudTarget get target => HudTarget.opticalGlasses;
  @override
  bool get available => false;
  @override
  Future<void> show(HudFrame frame) async =>
      throw UnsupportedError('光学 HUD 传输/中文栅格化未配置，不能发送');
  @override
  Future<void> clear() async => throw UnsupportedError('光学 HUD 未连接，无法确认已清屏');
}
