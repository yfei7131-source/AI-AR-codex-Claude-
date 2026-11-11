/* Browser capability adapter. No API keys, uploads, persistence, or fake devices. */
(() => {
  'use strict';
  let video, stream = null, cameraEpoch = 0, opening = false;
  let recognition = null, speechTimer = null, listener = null;
  const emit = (type, data = {}) => listener?.(JSON.stringify({type, ...data}));
  const videoElement = () => {
    if (!video) {
      video = document.createElement('video');
      video.autoplay = true; video.muted = true; video.playsInline = true;
      video.setAttribute('playsinline', ''); video.setAttribute('aria-label', '本地摄像头预览');
      video.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#07131b;';
    }
    return video;
  };
  function stopCamera() {
    ++cameraEpoch; opening = false;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    if (video) { video.pause(); video.srcObject = null; }
    emit('camera-stopped');
  }
  function stopSpeech() {
    clearTimeout(speechTimer); speechTimer = null;
    if (recognition) { const previous = recognition; recognition = null; try { previous.abort(); } catch (_) {} }
    window.speechSynthesis?.cancel(); emit('speech-stopped');
  }
  const recognitionType = () => window.SpeechRecognition || window.webkitSpeechRecognition;
  function capabilities() {
    return JSON.stringify({
      web:true, secure:window.isSecureContext === true,
      camera:!!navigator.mediaDevices?.getUserMedia,
      recognition:!!recognitionType(),
      synthesis:!!(window.speechSynthesis && window.SpeechSynthesisUtterance),
    });
  }
  async function startCamera(consent) {
    if (consent !== true) throw Error('请先同意启动本地摄像头');
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw Error('摄像预览需要已信任的HTTPS安全页面；也可手动选择照片');
    stopCamera(); const epoch = cameraEpoch; opening = true;
    let timedOut = false;
    const pending = navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false});
    let permissionTimer, playTimer;
    // Permission promises may remain pending indefinitely. Late streams must be released.
    const permissionTimeout = new Promise((_, reject) => { permissionTimer=setTimeout(() => {
      if (epoch === cameraEpoch) { timedOut = true; stopCamera(); }
      reject(Error('摄像授权等待超过15秒；请检查Safari权限后重试'));
    },15000); });
    pending.then(late => { if (timedOut || epoch !== cameraEpoch) late.getTracks().forEach(track => track.stop()); }, () => {});
    try {
      const selected = await Promise.race([pending, permissionTimeout]);
      clearTimeout(permissionTimer);
      if (timedOut || epoch !== cameraEpoch) throw Error('摄像头请求已取消');
      stream = selected;
      selected.getTracks().forEach(track => track.addEventListener?.('ended', () => { if (stream === selected) stopCamera(); }, {once:true}));
      const element = videoElement(); element.srcObject = selected;
      await Promise.race([element.play(), new Promise((_, reject) => { playTimer=setTimeout(() => reject(Error('摄像预览未就绪，请重试或选择照片')),8000); })]);
      if (epoch !== cameraEpoch) throw Error('摄像头请求已取消');
      opening = false; emit('camera-started'); return 'started';
    } catch (error) {
      if (epoch === cameraEpoch) stopCamera();
      throw error;
    } finally { clearTimeout(permissionTimer); clearTimeout(playTimer); }
  }
  function captureFrame(consent) {
    if (consent !== true) throw Error('请先同意采集本地摄像头画面');
    const element = videoElement();
    if (!stream || !element.videoWidth || !element.videoHeight) throw Error('摄像头尚未就绪，请稍候或选择照片');
    const canvas = document.createElement('canvas');
    canvas.width = Math.min(element.videoWidth,1280);
    canvas.height = Math.round(element.videoHeight * canvas.width / element.videoWidth);
    canvas.getContext('2d').drawImage(element,0,0,canvas.width,canvas.height);
    return canvas.toDataURL('image/jpeg',.8);
  }
  function startSpeech(consent) {
    if (consent !== true) throw Error('请先同意浏览器语音服务，音频可能发送到浏览器供应商');
    const Recognition = recognitionType();
    if (!Recognition) throw Error('当前浏览器不支持语音识别，请用键盘输入');
    stopSpeech(); const current = new Recognition(); recognition = current;
    current.lang = 'zh-CN'; current.continuous = false; current.interimResults = false;
    current.onresult = event => {
      if (recognition === current) emit('speech-result',{text:event.results[0][0].transcript});
    };
    current.onerror = event => {
      if (recognition === current) { emit('speech-error',{message:'语音识别失败：'+event.error+'；请改用文字输入'}); stopSpeech(); }
    };
    current.onend = () => { if (recognition === current) { recognition = null; clearTimeout(speechTimer); emit('speech-stopped'); } };
    try { current.start(); emit('speech-started'); }
    catch (error) { recognition = null; throw error; }
    speechTimer = setTimeout(() => { if (recognition === current) { stopSpeech(); emit('speech-error',{message:'语音识别已在30秒后停止，请检查权限或使用文字输入'}); } },30000);
  }
  function speak(text) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) throw Error('当前浏览器不支持播报，请阅读HUD文字');
    if (!text) throw Error('尚无可播报的有效结果');
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text); utterance.lang = 'zh-CN';
    utterance.onerror = () => emit('speech-error',{message:'语音播报失败，结果仍可在HUD阅读'});
    window.speechSynthesis.speak(utterance);
  }
  function consumeFragment() {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const token = params.get('pair') || params.get('session_token') || params.get('token') || '';
    if (token) window.history.replaceState(null,'',window.location.pathname+window.location.search);
    return token;
  }
  // Strip the secret before Flutter routing/bootstrap can observe or log the URL fragment.
  let pendingSessionToken = consumeFragment();
  function takeSessionToken() { const token=pendingSessionToken;pendingSessionToken='';return token; }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { stopCamera(); stopSpeech(); emit('page-hidden'); }
  });
  window.addEventListener('pagehide', () => { stopCamera(); stopSpeech(); emit('page-hidden'); });
  window.aiarBrowser = {
    capabilities, videoElement, startCamera, captureFrame, stopCamera, startSpeech, stopSpeech, speak, takeSessionToken,
    setEventHandler:callback => { listener = callback; },
    cameraActive:() => !!stream, cameraOpening:() => opening,
    setBootStatus:text => { const status=document.getElementById?.('aiarBootStatus');if(status) status.textContent=text; },
    finishBoot:() => { const status=document.getElementById?.('aiarBootStatus');if(status) status.remove(); },
  };
})();
