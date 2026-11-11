// Browser logic in a Node VM: contract tests, not physical camera/cloud validation.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const frame = 'data:image/jpeg;base64,/9j/2Q==';
const health = {provider:'demo', mode:'demo', ready:true, max_image_bytes:2097152, request_timeout_seconds:45};
const answer = mode => ({provider:mode === 'live' ? 'openai' : 'demo', mode, simulated:mode === 'demo', answer:'回答示例', hud:{title:'眼前识别',lines:['回答示例']}});
const response = (body, ok = true) => ({ok, status:ok ? 200 : 502, json:async () => body});
const tick = () => new Promise(setImmediate);

class Element {
  constructor() { this.value = ''; this.checked = false; this.style = {}; this.children = []; this.disabled = false; this.files = []; this.videoWidth = 640; this.videoHeight = 480; }
  set textContent(text) { this.text = text; this.children = []; }
  get textContent() { return this.text || ''; }
  replaceChildren(...items) { this.children = items; this.text = ''; }
  appendChild(item) { this.children.push(item); }
  removeAttribute(name) { delete this[name]; }
  click() { return this.onclick?.(); }
  getContext() { return {drawImage:() => {}}; }
  toDataURL() { return frame; }
}
async function browser(options = {}) {
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element()]));
  elements.providerMode.value = 'demo'; elements.mode.value = 'vision'; elements.question.value = '这是什么？';
  const calls = [], events = {}, documentEvents = {}, spoken = [];
  let stopped = 0, mediaCalls = 0, confirmed = options.confirm !== false;
  const track = {stop:() => { ++stopped; }};
  const window = {addEventListener:(event, handler) => { events[event] = handler; }, speechSynthesis:{cancel:() => {}, speak:speech => spoken.push(speech.text)}, SpeechSynthesisUtterance:class {constructor(text) {this.text=text;}}};
  const document = {getElementById:id => elements[id], createElement:() => new Element(), createTextNode:text => ({textContent:text}), addEventListener:(event, handler) => { documentEvents[event] = handler; }, hidden:false};
  const context = vm.createContext({document, window, navigator:{mediaDevices:{getUserMedia:async () => { ++mediaCalls; return options.streamPromise || {getTracks:() => [track]}; }}},
    AbortController, setTimeout:(fn,ms) => setTimeout(fn,options.fastCameraTimeout && ms===15000 ? 5 : ms), clearTimeout, confirm:() => confirmed,
    FileReader:class {readAsDataURL(file) {this.result=file.data || frame; this.onload();}},
    Image:class {set src(value) {this.onload();}},
    fetch:async (url, request) => {
      const body = request.body ? JSON.parse(request.body) : undefined;
      calls.push({url, request, body});
      if (url === '/api/health') return options.healthPromise || response(options.health || health);
      if (options.fetch) return options.fetch(url, request, body);
      if (url === '/api/ask') return response(answer(body.mode));
      if (url === '/api/privacy/delete') return response({cleared:true});
      if (url === '/api/notes') return response({note:{text:body.text}});
      throw Error('Unexpected URL ' + url);
    }
  });
  vm.runInContext(script, context, {filename:'web/index.html'}); await tick();
  return {elements, calls, window, document, events, documentEvents, spoken, context, get stopped(){return stopped;}, get mediaCalls(){return mediaCalls;}, setConfirm:value => {confirmed=value;}};
}
function upload(app) { app.elements.file.files = [{type:'image/jpeg',size:20,data:frame}]; app.elements.file.onchange(); }
function live(app) { app.elements.providerMode.value = 'live'; app.elements.providerMode.onchange(); }

test('camera refuses access without explicit local consent', async () => {
  const app = await browser(); await app.elements.cameraBtn.onclick();
  assert.equal(app.mediaCalls, 0); assert.match(app.elements.result.textContent, /请先同意/);
});
test('camera capture remains local until explicit recognition; vision sends actual frame', async () => {
  const app = await browser(); app.elements.cameraConsent.checked = true;
  await app.elements.cameraBtn.onclick(); app.elements.captureBtn.onclick();
  assert.equal(app.elements.still.src, frame); assert.equal(app.calls.filter(call => call.url === '/api/ask').length, 0);
  app.elements.uploadConsent.checked = true; await app.elements.askBtn.onclick();
  const sent = app.calls.find(call => call.url === '/api/ask').body;
  assert.equal(sent.image_data, frame); assert.equal(sent.consent,true); assert.equal(sent.mode,'demo');
  assert.match(app.elements.hudSource.textContent,/模拟演示/);
});
test('live OCR sends chosen image with translate kind and shows live HUD source', async () => {
  const app = await browser(); upload(app); live(app); app.elements.mode.value = 'translate'; app.elements.uploadConsent.checked = true;
  await app.elements.askBtn.onclick();
  const sent = app.calls.find(call => call.url === '/api/ask').body;
  assert.equal(sent.image_data,frame); assert.equal(sent.kind,'translate'); assert.equal(sent.mode,'live');
  assert.match(app.elements.hudSource.textContent,/真实 AI · openai/); assert.equal(app.elements.hudLines.children[0].textContent,'回答示例');
});
test('no image or no upload consent means no request', async () => {
  const app = await browser(); upload(app); await app.elements.askBtn.onclick();
  assert.match(app.elements.result.textContent,/请先同意/);
  app.elements.uploadConsent.checked = true; app.elements.clearFrameBtn.onclick(); await app.elements.askBtn.onclick();
  assert.match(app.elements.result.textContent,/需要图片/); assert.equal(app.calls.filter(call => call.url === '/api/ask').length,0);
});
test('chat omits images and does not require image consent', async () => {
  const app = await browser(); upload(app); app.elements.mode.value = 'chat'; await app.elements.askBtn.onclick();
  const sent = app.calls.find(call => call.url === '/api/ask').body;
  assert.equal(sent.image_data,null); assert.equal(sent.consent,false);
});
test('live never accepts a demo response or silently retries demo', async () => {
  const app = await browser({fetch:async () => response(answer('demo'))});
  app.elements.mode.value = 'chat'; live(app); await app.elements.askBtn.onclick(); app.elements.speakBtn.onclick();
  assert.match(app.elements.hudTitle.textContent,/失败/); assert.equal(app.spoken.length,0);
  const asks = app.calls.filter(call => call.url === '/api/ask'); assert.equal(asks.length,1); assert.equal(asks[0].body.mode,'live');
});
test('live accepts only the configured openai provider identity', async () => {
  const app = await browser({fetch:async () => response({...answer('live'),provider:'unknown-provider'})});
  app.elements.mode.value='chat'; live(app); await app.elements.askBtn.onclick();
  assert.match(app.elements.result.textContent,/来源与请求模式不一致/); assert.equal(app.elements.hudTitle.textContent,'识别失败');
});
test('cloud failure replaces old result on HUD and prevents stale speech', async () => {
  let count = 0;
  const app = await browser({fetch:async () => ++count === 1 ? response(answer('live')) : response({error:'未配置密钥',code:'configuration_error',hud:{title:'配置错误',lines:['需要密钥']}},false)});
  app.elements.mode.value='chat'; live(app); await app.elements.askBtn.onclick(); await app.elements.askBtn.onclick(); app.elements.speakBtn.onclick();
  assert.equal(app.elements.hudTitle.textContent,'配置错误'); assert.match(app.elements.hudSource.textContent,/未获得结果/); assert.equal(app.spoken.length,0);
});
test('client timeout produces error HUD with no unbounded spinner', async () => {
  const app = await browser({fetch:async (_url, request) => new Promise((_resolve,reject) => request.signal.addEventListener('abort', () => reject(Error('aborted'))))});
  vm.runInContext('requestTimeoutMs = 5',app.context); app.elements.mode.value='chat'; await app.elements.askBtn.onclick();
  assert.match(app.elements.result.textContent,/请求超时/); assert.equal(app.elements.hudTitle.textContent,'识别失败'); assert.equal(app.elements.askBtn.disabled,false);
});
test('deleting while inference runs clears frame and rejects late result', async () => {
  let resolveAsk;
  const app = await browser({fetch:async url => url === '/api/ask' ? new Promise(resolve => {resolveAsk=resolve;}) : response({cleared:true})});
  upload(app); app.elements.uploadConsent.checked=true; const pending = app.elements.askBtn.onclick(); await tick();
  await app.elements.deleteBtn.onclick(); resolveAsk(response(answer('demo'))); await pending;
  assert.equal(app.elements.hudTitle.textContent,'已清除'); assert.equal(app.elements.still.src,undefined); assert.equal(app.elements.uploadConsent.checked,false); assert.equal(app.elements.question.value,'');
});
test('deleting rejects a pending task response so old private text cannot reappear', async () => {
  let resolveTask;
  const app = await browser({fetch:async url => url === '/api/tasks/draft' ? new Promise(resolve => {resolveTask=resolve;}) : response({cleared:true})});
  app.elements.taskText.value='私有待办'; const pending=app.elements.draftBtn.onclick(); await tick();
  await app.elements.deleteBtn.onclick(); resolveTask(response({task:{id:'old',text:'私有待办'},hud:{title:'待确认',lines:['私有待办']}})); await pending;
  assert.equal(app.elements.hudTitle.textContent,'已清除'); assert.equal(app.elements.pending.textContent,'无待确认任务');
});
test('drafting task supersedes earlier inference so late error cannot replace task HUD', async () => {
  let resolveAsk;
  const app=await browser({fetch:async url => {
    if (url === '/api/ask') return new Promise(resolve => {resolveAsk=resolve;});
    if (url === '/api/tasks/draft') return response({task:{id:'task-1',text:'检查设备'},hud:{title:'任务待确认',lines:['检查设备']}});
    throw Error('Unexpected URL '+url);
  }});
  app.elements.mode.value='chat'; const pending=app.elements.askBtn.onclick(); await tick();
  app.elements.taskText.value='检查设备'; await app.elements.draftBtn.onclick();
  resolveAsk(response({error:'请求已被新操作替代',code:'superseded',hud:{title:'旧请求失败',lines:['旧请求']}},false)); await pending;
  assert.equal(app.elements.hudTitle.textContent,'任务待确认'); assert.match(app.elements.hudSource.textContent,/待用户确认/); assert.equal(app.elements.askBtn.disabled,false);
});
test('confirming task supersedes earlier inference so late result cannot replace confirmed HUD', async () => {
  let resolveAsk;
  const app=await browser({fetch:async url => {
    if (url === '/api/ask') return new Promise(resolve => {resolveAsk=resolve;});
    if (url === '/api/tasks/draft') return response({task:{id:'task-1',text:'检查设备'},hud:{title:'任务待确认',lines:['检查设备']}});
    if (url === '/api/tasks/confirm') return response({task:{id:'task-1',status:'confirmed_local_only'},hud:{title:'已确认（未外部执行）',lines:['检查设备']}});
    throw Error('Unexpected URL '+url);
  }});
  await app.elements.draftBtn.onclick(); const confirmButton=app.elements.pending.children[1];
  app.elements.mode.value='chat'; const pending=app.elements.askBtn.onclick(); await tick();
  await confirmButton.onclick(); resolveAsk(response(answer('demo'))); await pending;
  assert.equal(app.elements.hudTitle.textContent,'已确认（未外部执行）'); assert.match(app.elements.hudSource.textContent,/未外部执行/); assert.equal(app.elements.pending.textContent,'已确认，但未调用任何外部系统');
});
test('privacy revoke or page exit closes camera tracks', async () => {
  const app = await browser(); app.elements.cameraConsent.checked=true; await app.elements.cameraBtn.onclick();
  app.elements.cameraConsent.checked=false; app.elements.cameraConsent.onchange(); assert.equal(app.stopped,1);
  app.elements.cameraConsent.checked=true; await app.elements.cameraBtn.onclick(); app.events.pagehide(); assert.equal(app.stopped,2);
});
test('camera permission resolved after revocation immediately closes stream', async () => {
  let resolveStream; const streamPromise = new Promise(resolve => {resolveStream=resolve;});
  const app = await browser({streamPromise}); app.elements.cameraConsent.checked=true; const opening=app.elements.cameraBtn.onclick();
  app.elements.cameraConsent.checked=false; app.elements.cameraConsent.onchange();
  let stopped=0; resolveStream({getTracks:() => [{stop:() => {++stopped;}}]}); await opening;
  assert.equal(stopped,1); assert.equal(app.elements.video.srcObject,null);
});
test('background tab stops camera; selected file also closes camera', async () => {
  const app=await browser(); app.elements.cameraConsent.checked=true; await app.elements.cameraBtn.onclick();
  app.document.hidden=true; app.documentEvents.visibilitychange(); assert.equal(app.stopped,1);
  app.document.hidden=false; await app.elements.cameraBtn.onclick(); upload(app); assert.equal(app.stopped,2);
});
test('unsupported voice input and speech fall back to readable text', async () => {
  const app = await browser(); app.elements.micBtn.onclick(); assert.match(app.elements.result.textContent,/不支持语音识别/);
  delete app.window.speechSynthesis; app.elements.speakBtn.onclick(); assert.match(app.elements.result.textContent,/阅读 HUD/);
});
test('voice requires consent and does not automatically save or submit transcript', async () => {
  const app = await browser(); let started=0, current;
  app.window.SpeechRecognition=class {constructor(){current=this;} start(){++started;} abort(){}};
  app.elements.micBtn.onclick(); assert.equal(started,0);
  app.elements.speechConsent.checked=true; app.elements.micBtn.onclick(); assert.equal(started,1);
  current.onresult({results:[[{transcript:'确认后保存'}]]}); assert.equal(app.elements.question.value,'确认后保存');
  assert.equal(app.calls.filter(call => call.url !== '/api/health').length,0);
});
test('saving notes requires explicit confirmation', async () => {
  const app = await browser({confirm:false}); await app.elements.noteBtn.onclick(); assert.equal(app.calls.filter(call => call.url === '/api/notes').length,0);
  app.setConfirm(true); await app.elements.noteBtn.onclick(); assert.equal(app.calls.filter(call => call.url === '/api/notes').length,1);
});
test('health config failure displays readiness without replacing user mode choice', async () => {
  let resolveHealth; const healthPromise=new Promise(resolve => {resolveHealth=resolve;});
  const app=await browser({healthPromise}); live(app);
  resolveHealth(response({...health,mode:'demo',ready:false,configuration_error:'OPENAI_API_KEY 未配置'})); await tick();
  assert.equal(app.elements.providerMode.value,'live'); assert.match(app.elements.health.textContent,/未就绪/); assert.match(app.elements.result.textContent,/未配置/);
});
test('empty, unsupported, and oversized files cannot become upload frames', async () => {
  const app=await browser();
  for (const file of [{type:'image/jpeg',size:0},{type:'image/gif',size:20},{type:'image/png',size:2097153}]) {
    app.elements.file.files=[file]; app.elements.file.onchange(); app.elements.uploadConsent.checked=true; await app.elements.askBtn.onclick();
  }
  assert.equal(app.calls.filter(call => call.url === '/api/ask').length,0);
});

test('OCR explicitly requests preserved original and selected English translation', async () => {
  const app=await browser(); upload(app); app.elements.mode.value='translate';
  app.elements.targetLanguage.value='en'; app.elements.uploadConsent.checked=true;
  await app.elements.askBtn.onclick();
  const payload=app.calls.find(call => call.url==='/api/ask').body;
  assert.equal(payload.output_format,'ocr'); assert.equal(payload.target_language,'en');
  assert.match(payload.client_request_id,/^web-/);
});

test('explicit cancel sends matching ID and ignores a late answer', async () => {
  let complete;
  const app=await browser({fetch:(url,req,body) => url==='/api/ask'
    ? new Promise(resolve => {complete=resolve;}) : response({cancelled:true})});
  app.elements.mode.value='chat'; const pending=app.elements.askBtn.onclick();
  const id=app.calls.find(call => call.url==='/api/ask').body.client_request_id;
  app.elements.cancelBtn.onclick();
  assert.equal(app.calls.find(call => call.url==='/api/requests/cancel').body.client_request_id,id);
  complete(response(answer('demo'))); await pending;
  assert.equal(app.elements.hudTitle.textContent,'已取消'); assert.equal(app.elements.cancelBtn.disabled,true);
});

test('pending camera permission times out and closes a stream arriving later', async () => {
  let open; const promise=new Promise(resolve=>{open=resolve;}); let closed=0;
  const app=await browser({streamPromise:promise,fastCameraTimeout:true});
  app.elements.cameraConsent.checked=true; await app.elements.cameraBtn.onclick();
  assert.match(app.elements.result.textContent,/超时/);
  open({getTracks:()=>[{stop:()=>{++closed;}}]}); await tick();
  assert.equal(closed,1); assert.equal(app.elements.video.srcObject,undefined);
});

test('local validation has independent consent and never invokes AI endpoint', async () => {
  const app=await browser({fetch:(url)=>{
    assert.equal(url,'/api/media/validate');
    return response({validated:true,scope:'local_only',cloud_sent:false,image:{width:640,height:480,format:'JPEG'},request_id:'local-test'});
  }}); upload(app); await app.elements.localValidateBtn.onclick();
  assert.equal(app.calls.filter(call=>call.url==='/api/media/validate').length,0);
  app.elements.uploadConsent.checked=true; await app.elements.localValidateBtn.onclick();
  assert.match(app.elements.result.textContent,/未请求AI/);
  assert.equal(app.calls.filter(call=>call.url==='/api/ask').length,0);
});
