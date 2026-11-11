// Browser-media contracts in a VM. These do not claim iPhone, microphone or camera hardware validation.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/browser_bridge.js'),'utf8');
const tick=()=>new Promise(setImmediate);
function browser(options={}) {
  const timers=new Map(), events={}, documentEvents={}, mediaCalls=[], speech=[], reports=[], history=[];
  let timerId=0,now=0,stopped=0,paused=0,aborted=0,started=0,drawn=0,recognizer;
  const trackEvents={};
  const track={stop:()=>++stopped,addEventListener:(name,callback)=>{trackEvents[name]=callback;}};
  const stream={getTracks:()=>[track]};
  const video={style:{},setAttribute:(name,value)=>{video[name]=value;},videoWidth:1920,videoHeight:1080,pause:()=>++paused,play:()=>options.playPromise ?? Promise.resolve()};
  const document={hidden:false,createElement:name=>name==='video'?video:{getContext:()=>({drawImage:()=>++drawn}),toDataURL:()=> 'data:image/jpeg;base64,/9j/2Q=='},addEventListener:(name,callback)=>{documentEvents[name]=callback;}};
  const window={isSecureContext:options.secure!==false,location:{hash:options.fragment||'',pathname:'/',search:options.query||''},history:{replaceState:(_state,_title,url)=>{history.push(url);window.location.hash='';}},addEventListener:(name,callback)=>{events[name]=callback;}};
  if(options.recognition!==false) window.SpeechRecognition=class {
    constructor(){recognizer=this;}
    start(){++started;}
    abort(){++aborted;}
  };
  if(options.synthesis!==false) {
    window.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
    window.speechSynthesis={cancel:()=>{},speak:value=>speech.push(value.text)};
  }
  const navigator={mediaDevices:options.camera===false?undefined:{getUserMedia:async constraints=>{mediaCalls.push(constraints);return options.permissionPromise ?? stream;}}};
  const context=vm.createContext({window,document,navigator,URLSearchParams,setTimeout:(callback,ms)=>{const id=++timerId;timers.set(id,{at:now+ms,callback});return id;},clearTimeout:id=>timers.delete(id)});
  vm.runInContext(source,context,{filename:'browser_bridge.js'});
  const api=window.aiarBrowser;api.setEventHandler(json=>reports.push(JSON.parse(json)));
  return {api,window,document,video,events,documentEvents,mediaCalls,speech,reports,history,timers,stream,trackEvents,
    get stopped(){return stopped;},get paused(){return paused;},get aborted(){return aborted;},get started(){return started;},get drawn(){return drawn;},get recognizer(){return recognizer;},
    async advance(ms){now+=ms;for(const [id,timer] of [...timers]) if(timer.at<=now){timers.delete(id);timer.callback();}await tick();}
  };
}
test('pair fragment is removed before Flutter bootstraps and consumed only once',()=>{
  const app=browser({fragment:'#pair=session-token_123'});
  assert.equal(app.window.location.hash,'');assert.deepEqual(app.history,['/']);
  assert.equal(app.api.takeSessionToken(),'session-token_123');assert.equal(app.api.takeSessionToken(),'');
});
test('a query token is never treated as a pairing credential',()=>{
  const app=browser({query:'?token=do-not-read'});assert.equal(app.api.takeSessionToken(),'');assert.equal(app.history.length,0);
});
test('camera requires consent before invoking getUserMedia',async()=>{
  const app=browser();await assert.rejects(app.api.startCamera(false),/先同意/);assert.equal(app.mediaCalls.length,0);
});
test('insecure or unsupported camera offers photo fallback and does not acquire media',async()=>{
  for(const options of [{secure:false},{camera:false}]) {const app=browser(options);await assert.rejects(app.api.startCamera(true),/HTTPS/);assert.equal(app.mediaCalls.length,0);}
});
test('real browser acquisition contract requests video only, inline muted preview and canvas frame',async()=>{
  const app=browser();await app.api.startCamera(true);
  assert.equal(app.mediaCalls[0].audio,false);assert.equal(app.mediaCalls[0].video.facingMode.ideal,'environment');
  assert.equal(app.video.playsInline,true);assert.equal(app.video.muted,true);assert.equal(app.video.srcObject,app.stream);
  assert.equal(app.api.captureFrame(true),'data:image/jpeg;base64,/9j/2Q==');assert.equal(app.drawn,1);assert.equal(app.timers.size,0);
  app.api.stopCamera();assert.equal(app.stopped,1);assert.equal(app.video.srcObject,null);
});
test('capture without consent or an active ready stream fails without inventing pixels',async()=>{
  const app=browser();assert.throws(()=>app.api.captureFrame(true),/尚未就绪/);
  await app.api.startCamera(true);assert.throws(()=>app.api.captureFrame(false),/先同意/);app.api.stopCamera();
});
test('permission request expires after 15 seconds and a late stream is closed',async()=>{
  let resolve;const permissionPromise=new Promise(done=>{resolve=done;});const app=browser({permissionPromise});
  const pending=app.api.startCamera(true);const expected=assert.rejects(pending,/15秒/);
  await app.advance(15000);await expected;resolve(app.stream);await tick();assert.equal(app.stopped,1);assert.equal(app.api.cameraActive(),false);
});
test('stopping during pending permission closes late tracks and cannot start preview',async()=>{
  let resolve;const app=browser({permissionPromise:new Promise(done=>{resolve=done;})});
  const pending=app.api.startCamera(true);app.api.stopCamera();resolve(app.stream);await assert.rejects(pending,/已取消/);assert.equal(app.stopped,1);
});
test('a stalled video play expires and releases acquired stream',async()=>{
  const app=browser({playPromise:new Promise(()=>{})});const pending=app.api.startCamera(true);const expected=assert.rejects(pending,/未就绪/);
  await tick();await app.advance(8000);await expected;assert.equal(app.stopped,1);assert.equal(app.api.cameraActive(),false);
});
test('permission rejection is an error and never becomes a simulated frame',async()=>{
  const app=browser({permissionPromise:Promise.reject(Error('permission denied'))});await assert.rejects(app.api.startCamera(true),/permission denied/);assert.equal(app.api.cameraActive(),false);
});
test('page hidden stops camera, recognition and publishes lifecycle event',async()=>{
  const app=browser();await app.api.startCamera(true);app.api.startSpeech(true);app.document.hidden=true;app.documentEvents.visibilitychange();
  assert.equal(app.stopped,1);assert.equal(app.aborted,1);assert.equal(app.api.cameraActive(),false);assert.ok(app.reports.some(event=>event.type==='page-hidden'));
});
test('track-ended and pagehide stop devices without automatic restart',async()=>{
  const app=browser();await app.api.startCamera(true);app.trackEvents.ended();app.events.pagehide();assert.equal(app.stopped,1);assert.equal(app.mediaCalls.length,1);
});
test('recognition requires explicit audio processing consent',()=>{
  const app=browser();assert.throws(()=>app.api.startSpeech(false),/浏览器供应商/);assert.equal(app.started,0);
});
test('unsupported voice services are detected and fall back to text',()=>{
  const app=browser({recognition:false,synthesis:false});const caps=JSON.parse(app.api.capabilities());assert.equal(caps.recognition,false);assert.equal(caps.synthesis,false);
  assert.throws(()=>app.api.startSpeech(true),/键盘输入/);assert.throws(()=>app.api.speak('回答'),/阅读HUD/);
});
test('voice result only produces a transcript event; it does not call AI or save notes',()=>{
  const app=browser();app.api.startSpeech(true);assert.equal(app.started,1);app.recognizer.onresult({results:[[{transcript:'请先核对文字'}]]});
  assert.equal(app.reports.find(event=>event.type==='speech-result').text,'请先核对文字');app.api.stopSpeech();
});
test('recognition is bounded to 30 seconds and late callbacks are ignored',async()=>{
  const app=browser();app.api.startSpeech(true);const old=app.recognizer;await app.advance(30000);old.onresult({results:[[{transcript:'late'}]]});
  assert.equal(app.aborted,1);assert.equal(app.reports.filter(event=>event.type==='speech-result').length,0);assert.ok(app.reports.some(event=>event.type==='speech-error'));
});
test('TTS only reads an explicit non-empty result and supports cancellation',()=>{
  const app=browser();assert.throws(()=>app.api.speak(''),/尚无/);app.api.speak('模拟演示：回答');assert.deepEqual(app.speech,['模拟演示：回答']);app.api.stopSpeech();
});
test('stale recognition abort errors cannot interrupt page cleanup',async()=>{
  const app=browser();await app.api.startCamera(true);app.api.startSpeech(true);app.recognizer.abort=()=>{throw Error('already inactive');};
  assert.doesNotThrow(()=>app.events.pagehide());assert.equal(app.stopped,1);assert.ok(app.reports.some(event=>event.type==='page-hidden'));
});
test('Flutter loader explicitly uses only same-origin engine and fallback font URLs',()=>{
  const bootstrap=fs.readFileSync(path.join(__dirname,'../web/flutter_bootstrap.js'),'utf8').replace('{{flutter_js}}','').replace('{{flutter_build_config}}','');
  let config;
  vm.runInNewContext(bootstrap,{URL,document:{baseURI:'https://192.168.1.20:9443/'},_flutter:{loader:{load:value=>{config=value.config;}}}});
  assert.equal(config.canvasKitBaseUrl,'https://192.168.1.20:9443/canvaskit/');assert.equal(config.fontFallbackBaseUrl,'https://192.168.1.20:9443/fonts/fallback/');
});
