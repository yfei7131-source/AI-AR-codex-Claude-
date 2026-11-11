import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'api.dart';
import 'browser_media.dart';
import 'controller.dart';
import 'media_cleanup.dart';
import 'native_ble_adapter.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await prepareBrowserUi();
  } catch (_) {
    return;
  }
  runApp(
    HubApp(
      controller: HubController(
        GlassesApi(),
        device: createNativeDeviceAdapter(),
      ),
    ),
  );
  WidgetsBinding.instance.addPostFrameCallback((_) => finishBrowserBoot());
}

class HubApp extends StatelessWidget {
  const HubApp({super.key, required this.controller});
  final HubController controller;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'AI/AR Glasses',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      fontFamily: browserFontFamily(),
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff16796d),
        brightness: Brightness.dark,
      ),
      useMaterial3: true,
    ),
    home: HubScreen(controller: controller),
  );
}

class HubScreen extends StatefulWidget {
  const HubScreen({super.key, required this.controller});
  final HubController controller;
  @override
  State<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends State<HubScreen> with WidgetsBindingObserver {
  final question = TextEditingController(text: '眼前这是什么？');
  final sessionInput = TextEditingController();
  bool picking = false;
  int captureEpoch = 0;
  late final BrowserMedia browser;
  bool cameraStarting = false, speechConsent = false, listening = false;
  HubController get hub => widget.controller;
  @override
  void initState() {
    super.initState();
    browser = BrowserMedia();
    final session = browser.takeSessionToken();
    if (session.isNotEmpty) {
      try {
        hub.api.setSessionToken(session);
      } catch (failure) {
        hub.showError(failure);
      }
    }
    browser.listen((event) {
      if (!mounted) return;
      switch (event['type']) {
        case 'camera-started':
          cameraStarting = false;
        case 'camera-stopped':
          cameraStarting = false;
        case 'speech-started':
          listening = true;
        case 'speech-stopped':
          listening = false;
        case 'speech-result':
          question.text = event['text'] as String;
          hub.status = '语音已转为文字，请核对后点击提交；未自动发送给AI';
          hub.changed();
        case 'speech-error':
          hub.showError(ApiFailure(event['message'] as String));
        case 'page-hidden':
          ++captureEpoch;
          hub.cancelByUser();
      }
      setState(() {});
    });
    WidgetsBinding.instance.addObserver(this);
    hub.addListener(redraw);
    hub.refreshHealth();
  }

  void redraw() {
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // The system camera owns its preview lifecycle. No microphone or persistent camera stream is opened here.
    if (!picking &&
        (state == AppLifecycleState.paused ||
            state == AppLifecycleState.hidden)) {
      ++captureEpoch;
      browser.stopCamera();
      browser.stopSpeech();
      hub.cancelByUser();
    }
  }

  @override
  void dispose() {
    ++captureEpoch;
    browser.dispose();
    WidgetsBinding.instance.removeObserver(this);
    hub.removeListener(redraw);
    question.dispose();
    sessionInput.dispose();
    super.dispose();
  }

  Future<void> pick(ImageSource source) async {
    if (!hub.captureConsent) {
      hub.showError(ApiFailure('请先同意拍摄或读取本地图片'));
      return;
    }
    if (picking) return;
    browser.stopCamera();
    browser.stopSpeech();
    final epoch = ++captureEpoch;
    setState(() {
      picking = true;
    });
    try {
      final file = await ImagePicker().pickImage(
        source: source,
        maxWidth: 1280,
        maxHeight: 1280,
        imageQuality: 80,
        requestFullMetadata: false,
      );
      if (file == null) return;
      try {
        final bytes = await file.readAsBytes();
        if (!mounted || epoch != captureEpoch || !hub.captureConsent) return;
        final mime =
            bytes.length >= 8 &&
                bytes[0] == 137 &&
                bytes[1] == 80 &&
                bytes[2] == 78 &&
                bytes[3] == 71
            ? 'image/png'
            : bytes.length >= 2 && bytes[0] == 255 && bytes[1] == 216
            ? 'image/jpeg'
            : '';
        hub.setFrame(bytes, mime);
      } finally {
        if (source == ImageSource.camera) await deleteCapturedCache(file.path);
      }
    } catch (failure) {
      if (mounted && epoch == captureEpoch) hub.showError(failure);
    } finally {
      if (mounted) {
        setState(() {
          picking = false;
        });
      }
    }
  }

  Future<void> toggleCamera() async {
    if (browser.cameraActive || cameraStarting) {
      ++captureEpoch;
      browser.stopCamera();
      setState(() {
        cameraStarting = false;
      });
      return;
    }
    if (!hub.captureConsent) {
      hub.showError(ApiFailure('请先同意启动本地摄像头'));
      return;
    }
    final epoch = ++captureEpoch;
    setState(() {
      cameraStarting = true;
    });
    try {
      await browser.startCamera(hub.captureConsent);
    } catch (failure) {
      if (mounted && epoch == captureEpoch) {
        hub.showError(ApiFailure(failure.toString()));
      }
    } finally {
      if (mounted && epoch == captureEpoch) {
        setState(() {
          cameraStarting = false;
        });
      }
    }
  }

  void captureBrowser() {
    try {
      browser.stopSpeech();
      final frame = browser.captureFrame(hub.captureConsent);
      hub.setFrame(base64Decode(frame.split(',').last), 'image/jpeg');
    } catch (failure) {
      hub.showError(failure);
    }
  }

  void toggleSpeech() {
    try {
      if (listening) {
        browser.stopSpeech();
        return;
      }
      browser.startSpeech(speechConsent);
    } catch (failure) {
      hub.showError(failure);
    }
  }

  Future<bool> confirm(String message) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('请确认'),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('确认'),
            ),
          ],
        ),
      ) ??
      false;
  @override
  Widget build(BuildContext context) {
    final ocr = hub.result?['ocr'];
    return Scaffold(
      appBar: AppBar(title: const Text('AI / AR GLASSES · V1.0')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '手机中枢 · 即拍即问与文字翻译',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(hub.status, key: const Key('api-status')),
            TextButton(
              onPressed: hub.refreshHealth,
              child: const Text('检查本地 API'),
            ),
            Text(
              browser.isWeb
                  ? '眼镜设备：未连接 · Safari Web不支持眼镜BLE；需要原生适配器'
                  : '眼镜设备：${hub.device.connection.name} · BLE 实机传输未配置',
              key: const Key('device-status'),
            ),
            const Text('HUD 为手机预览；尚未发送到光学 AR 显示。电量/连接状态不使用模拟数值。'),
            const Text('当前显示：手机HUD预览 · 光学AR显示未连接'),
            if (browser.isWeb)
              Text(
                hub.api.hasSessionToken
                    ? '已加载本次配对会话（仅内存）'
                    : '尚无配对会话；请打开Windows生成的HTTPS配对链接',
              ),
            if (browser.isWeb && !hub.api.hasSessionToken) ...[
              TextField(
                controller: sessionInput,
                key: const Key('pair-session'),
                obscureText: true,
                enableSuggestions: false,
                autocorrect: false,
                enableIMEPersonalizedLearning: false,
                autofillHints: const [],
                decoration: const InputDecoration(
                  labelText: 'Windows配对会话凭据（不是AI密钥）',
                ),
              ),
              OutlinedButton(
                onPressed: () {
                  try {
                    hub.api.setSessionToken(sessionInput.text.trim());
                    sessionInput.clear();
                    hub.refreshHealth();
                    setState(() {});
                  } catch (failure) {
                    hub.showError(failure);
                  }
                },
                child: const Text('使用本次配对会话'),
              ),
            ],
            if (browser.isWeb && !browser.secure)
              const Text('当前页面不是安全上下文，无法直接预览摄像头；请检查HTTPS信任或手动选照片。'),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: hub.mode,
              key: ValueKey('mode-${hub.mode}'),
              decoration: const InputDecoration(labelText: 'AI 服务模式'),
              items: const [
                DropdownMenuItem(value: 'demo', child: Text('DEMO · 不分析图像')),
                DropdownMenuItem(value: 'live', child: Text('真实 AI · 仅云端结果')),
              ],
              onChanged: (value) {
                if (value != null) hub.setMode(value);
                browser.stopSpeech();
              },
            ),
            DropdownButtonFormField<String>(
              initialValue: hub.kind,
              key: ValueKey('kind-${hub.kind}'),
              decoration: const InputDecoration(labelText: '功能'),
              items: const [
                DropdownMenuItem(value: 'vision', child: Text('视觉识别 / 图像问答')),
                DropdownMenuItem(value: 'translate', child: Text('OCR + 翻译')),
                DropdownMenuItem(value: 'chat', child: Text('文字对话')),
              ],
              onChanged: (value) {
                if (value != null) hub.setKind(value);
                browser.stopSpeech();
              },
            ),
            if (hub.kind == 'translate') ...[
              DropdownButtonFormField<String>(
                initialValue: hub.sourceLanguage,
                decoration: const InputDecoration(labelText: '原文语言'),
                items: const [
                  DropdownMenuItem(value: 'auto', child: Text('自动检测')),
                  DropdownMenuItem(value: 'en', child: Text('English')),
                  DropdownMenuItem(value: 'zh-CN', child: Text('简体中文')),
                ],
                onChanged: (value) {
                  if (value != null) {
                    hub.sourceLanguage = value;
                    hub.cancelByUser();
                  }
                },
              ),
              DropdownButtonFormField<String>(
                initialValue: hub.targetLanguage,
                decoration: const InputDecoration(labelText: '译文语言'),
                items: const [
                  DropdownMenuItem(value: 'zh-CN', child: Text('简体中文')),
                  DropdownMenuItem(value: 'en', child: Text('English')),
                ],
                onChanged: (value) {
                  if (value != null) {
                    hub.targetLanguage = value;
                    hub.cancelByUser();
                  }
                },
              ),
            ],
            CheckboxListTile(
              key: const Key('capture-consent'),
              contentPadding: EdgeInsets.zero,
              title: const Text('同意调用系统相机或读取我选择的图片'),
              value: hub.captureConsent,
              onChanged: (value) {
                hub.captureConsent = value ?? false;
                if (!hub.captureConsent) {
                  ++captureEpoch;
                  browser.stopCamera();
                }
                hub.changed();
              },
            ),
            Wrap(
              spacing: 8,
              children: [
                if (browser.isWeb) ...[
                  FilledButton.tonal(
                    key: const Key('browser-camera'),
                    onPressed: toggleCamera,
                    child: Text(
                      browser.cameraActive || cameraStarting
                          ? '关闭摄像头'
                          : '开启摄像头预览',
                    ),
                  ),
                  OutlinedButton(
                    onPressed: browser.cameraActive ? captureBrowser : null,
                    child: const Text('抓拍当前画面'),
                  ),
                ] else
                  FilledButton.tonal(
                    onPressed: picking ? null : () => pick(ImageSource.camera),
                    child: const Text('拍摄图片'),
                  ),
                OutlinedButton(
                  onPressed: picking ? null : () => pick(ImageSource.gallery),
                  child: const Text('选择图片'),
                ),
              ],
            ),
            if (browser.isWeb && browser.cameraAvailable) ...[
              Text(
                cameraStarting
                    ? '等待摄像头授权（最多15秒）'
                    : browser.cameraActive
                    ? '摄像头运行中 · 仅本地预览'
                    : '摄像头已关闭',
              ),
              SizedBox(height: 220, child: browser.preview()),
            ],
            if (hub.frame != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Image.memory(
                  hub.frame!,
                  height: 220,
                  fit: BoxFit.contain,
                  gaplessPlayback: false,
                ),
              ),
            CheckboxListTile(
              key: const Key('upload-consent'),
              contentPadding: EdgeInsets.zero,
              title: const Text('同意点击按钮时提交当前图片到本地服务；真实AI识别将转发至云端'),
              value: hub.uploadConsent,
              onChanged: (value) {
                hub.uploadConsent = value ?? false;
                if (!hub.uploadConsent) {
                  hub.cancelByUser();
                } else {
                  hub.changed();
                }
              },
            ),
            TextField(
              controller: question,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: '问题 / 核对后的文字',
                border: OutlineInputBorder(),
              ),
            ),
            if (browser.isWeb) ...[
              CheckboxListTile(
                key: const Key('speech-consent'),
                contentPadding: EdgeInsets.zero,
                title: const Text('同意浏览器麦克风语音识别，音频可能发送到浏览器供应商'),
                value: speechConsent,
                onChanged: (value) {
                  speechConsent = value ?? false;
                  if (!speechConsent) browser.stopSpeech();
                  setState(() {});
                },
              ),
              Text(
                '语音输入：${browser.recognitionAvailable ? '浏览器提供此能力，仍需实际权限/服务可用' : '不支持，请使用键盘'}；播报：${browser.synthesisAvailable ? '可尝试' : '不支持，请阅读文字'}。Safari支持随系统版本和设置变化。',
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: browser.recognitionAvailable
                        ? toggleSpeech
                        : null,
                    child: Text(listening ? '停止语音输入' : '语音转文字'),
                  ),
                  OutlinedButton(
                    onPressed: browser.synthesisAvailable && hub.result != null
                        ? () {
                            try {
                              browser.speak(
                                '${hub.result!['simulated'] == true ? '模拟演示：' : ''}${hub.result!['answer']}',
                              );
                            } catch (failure) {
                              hub.showError(failure);
                            }
                          }
                        : null,
                    child: const Text('朗读结果'),
                  ),
                ],
              ),
            ],
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  key: const Key('validate-local'),
                  onPressed: hub.busy
                      ? null
                      : () {
                          browser.stopSpeech();
                          hub.validateLocal();
                        },
                  child: const Text('仅校验上传，不调用AI'),
                ),
                FilledButton(
                  key: const Key('ask'),
                  onPressed: hub.busy
                      ? null
                      : () {
                          browser.stopSpeech();
                          hub.ask(question.text);
                        },
                  child: Text(
                    hub.kind == 'translate' ? 'OCR 并翻译到 HUD' : '识别并投射到 HUD',
                  ),
                ),
                if (hub.busy)
                  OutlinedButton(
                    onPressed: hub.cancelByUser,
                    child: const Text('取消等待'),
                  ),
              ],
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${hub.hudSource} · 手机 HUD 预览',
                      key: const Key('hud-source'),
                    ),
                    Text(
                      hub.hudTitle,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    for (final line in hub.hudLines) Text(line),
                    if (hub.busy) const LinearProgressIndicator(),
                  ],
                ),
              ),
            ),
            if (hub.result != null)
              SelectableText(
                hub.result!['answer'] as String,
                key: const Key('full-answer'),
              ),
            if (ocr is Map) ...[
              const Text('OCR 原文（请人工核对）'),
              SelectableText(
                ocr['original_text'] as String,
                key: const Key('ocr-original'),
              ),
              const Text('译文'),
              SelectableText(
                ocr['translated_text'] as String,
                key: const Key('ocr-translation'),
              ),
              Text(
                '来源语言：${ocr['source_language']} · 目标语言：${ocr['target_language']} · 不确定：${ocr['uncertain']}',
              ),
            ],
            if (hub.error.isNotEmpty)
              Text(
                hub.error,
                key: const Key('error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () async {
                if (await confirm('确认保存核对后的文字到本地 API 进程内？\n${question.text}')) {
                  try {
                    await hub.api.request('notes', {'text': question.text});
                    if (mounted) {
                      hub.status = '笔记已保存（进程内，重启丢失）';
                      hub.changed();
                    }
                  } catch (failure) {
                    hub.showError(failure);
                  }
                }
              },
              child: const Text('确认并保存文字笔记'),
            ),
            OutlinedButton(
              onPressed: () async {
                if (await confirm('清除当前内存图片、输入和服务端笔记/任务/HUD？不删除云端数据或图库原图。')) {
                  ++captureEpoch;
                  browser.stopCamera();
                  browser.stopSpeech();
                  speechConsent = false;
                  question.clear();
                  await hub.wipe();
                  PaintingBinding.instance.imageCache.clear();
                  PaintingBinding.instance.imageCache.clearLiveImages();
                }
              },
              child: const Text('清除本地原型数据'),
            ),
            const Text(
              '密钥仅配置于 Python 服务环境；App 不接收 API Key。图片提交前不离开手机；系统相机/图库可能另有缓存，删除按钮不控制系统图库。',
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}
