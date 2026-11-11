"""Local prototype API: validated media, explicit source, privacy-safe HUD state."""
from __future__ import annotations
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit
from uuid import uuid4
from app.core import Memory, to_hud
from app.images import MAX_IMAGE_BYTES, validate_image
from app.provider import build_provider, DemoProvider, ProviderError

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
STATE = Memory()
LOCK = RLock()
CONFIG_ERROR = None
try:
    PROVIDER = build_provider()
except ProviderError as exc:
    PROVIDER, CONFIG_ERROR = None, exc
MAX_BODY = 3 * 1024 * 1024
EPOCH = 0
ASK_SEQUENCE = 0
ACTIVE_REQUESTS = {}
CANCELLED_REQUESTS = set()
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class Handler(BaseHTTPRequestHandler):
    server_version = "AIARPrototype/0.3"

    def log_message(self, format, *args):
        pass  # no request URLs, images, questions or model responses in logs

    def _json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _local_request(self):
        try:
            host = urlsplit("http://" + self.headers.get("Host", ""))
            if host.hostname not in LOCAL_HOSTS or host.port != self.server.server_port:
                return False
            origin = self.headers.get("Origin")
            if origin:
                parsed = urlsplit(origin)
                return parsed.scheme == "http" and parsed.netloc == host.netloc
            return self.headers.get("Sec-Fetch-Site") not in ("cross-site",)
        except ValueError:
            return False

    def do_GET(self):
        if not self._local_request():
            return self._json(403, {"error": "仅允许本机同源访问", "code": "ORIGIN_DENIED"})
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self._json(200, {
                "ok": True, "provider": PROVIDER.name if PROVIDER else os.getenv("AI_PROVIDER", "demo"),
                "api_version": "0.3", "capabilities": ["vision", "ocr_structured", "local_media_validation", "request_cancel"],
                "mode": PROVIDER.mode if PROVIDER else "live", "ready": PROVIDER is not None,
                "configuration_error": str(CONFIG_ERROR) if CONFIG_ERROR else None,
                "model": getattr(PROVIDER, "model", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
                "max_image_bytes": MAX_IMAGE_BYTES,
                "request_timeout_seconds": getattr(PROVIDER, "request_timeout_seconds", 25),
                "note": "本地原型；ready仅表示本地配置就绪，不代表云端鉴权或实机验证通过"})
        if path == "/api/state":
            with LOCK:
                return self._json(200, STATE.snapshot())
        if path not in ("/", "/index.html"):
            return self._json(404, {"error": "not_found"})
        raw = (WEB_ROOT / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        self.end_headers()
        self.wfile.write(raw)

    def _ask(self, data, request_id, token):
        kind = data.get("kind", "vision")
        if kind not in ("vision", "translate", "chat"):
            raise ValueError("无效模式")
        question = data.get("question", "")
        if not isinstance(question, str) or len(question) > 500:
            raise ValueError("问题必须是500字以内文本")
        question = question.strip()
        if not question and kind != "translate":
            raise ValueError("请输入问题")
        mode = data.get("mode", PROVIDER.mode if PROVIDER else "live")
        if mode not in ("demo", "live"):
            raise ValueError("mode仅支持demo或live")
        output_format = data.get("output_format", "text")
        source_language = data.get("source_language", "auto")
        target_language = data.get("target_language", "zh-CN")
        if output_format not in ("text", "ocr") or (output_format == "ocr" and kind != "translate"):
            raise ValueError("output_format=ocr仅用于translate")
        if source_language not in ("auto", "zh-CN", "en") or target_language not in ("zh-CN", "en"):
            raise ValueError("source_language支持auto/zh-CN/en；target_language支持zh-CN/en")
        if mode == "live":
            if not PROVIDER or PROVIDER.name != "openai":
                raise CONFIG_ERROR or ProviderError("真实AI未启用；请设置AI_PROVIDER=openai和OPENAI_API_KEY后重启", "AI_NOT_CONFIGURED", 503)
            provider = PROVIDER
        else:
            provider = DemoProvider()
        image = data.get("image_data")
        if kind != "chat" and not image:
            raise ProviderError("请先拍摄或上传图片，视觉识别和OCR翻译不能无图运行", "IMAGE_REQUIRED", 400)
        if image is not None:
            if data.get("consent") is not True:
                raise ProviderError("图片上传需要用户明确同意", "CONSENT_REQUIRED", 403)
            try:
                image = validate_image(image)
            except ValueError as exc:
                raise ProviderError(str(exc), "INVALID_IMAGE", 400) from exc
        with LOCK:
            if token != (EPOCH, ASK_SEQUENCE):
                raise ProviderError("请求已被新操作取消", "REQUEST_SUPERSEDED", 409)
        ocr = None
        if output_format == "ocr":
            ocr = provider.respond(question or "翻译画面中的文字", image, kind, structured=True,
                                   source_language=source_language, target_language=target_language)
            answer = ("【模拟演示】" if mode == "demo" else "") + "原文：" + (ocr["original_text"] or "未能确认") + "\n译文：" + ocr["translated_text"]
            if ocr["uncertain"]:
                answer += "\n识别存在不确定性，请核对原图"
        elif kind == "translate":
            answer = provider.respond(question or "翻译画面中的文字", image, kind,
                                      source_language=source_language, target_language=target_language)
        else:
            answer = provider.respond(question or "翻译画面中的文字", image, kind)
        hud_text = ocr["translated_text"] if ocr else answer
        if ocr and ocr["uncertain"]:
            hud_text = "【需核对】" + hud_text
        hud = to_hud(kind, hud_text)
        hud.update({"mode": mode, "provider": provider.name, "simulated": mode == "demo", "request_id": request_id})
        with LOCK:
            if token != (EPOCH, ASK_SEQUENCE):
                raise ProviderError("请求已被新请求或隐私删除取消", "REQUEST_SUPERSEDED", 409)
            STATE.last_hud = hud
        result = {"answer": answer, "hud": hud, "provider": provider.name,
                "mode": mode, "simulated": mode == "demo", "request_id": request_id}
        if ocr is not None:
            result["ocr"] = ocr
        if data.get("client_request_id"):
            result["client_request_id"] = data["client_request_id"]
        return result

    def do_POST(self):
        global EPOCH, ASK_SEQUENCE
        path = urlsplit(self.path).path
        request_id = uuid4().hex
        token = None
        with LOCK:
            started_epoch = EPOCH
        try:
            if not self._local_request():
                raise ProviderError("仅允许本机同源访问", "ORIGIN_DENIED", 403)
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise ProviderError("请求必须使用application/json", "INVALID_CONTENT_TYPE", 415)
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("不支持分块HTTP请求体")
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= MAX_BODY:
                raise ProviderError("请求体为空或超过3MiB", "BODY_TOO_LARGE", 413)
            self.connection.settimeout(10)
            raw = self.rfile.read(n)
            if len(raw) != n:
                raise ValueError("请求体不完整")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("请求必须是JSON对象")
            if path == "/api/ask":
                client_id = data.get("client_request_id")
                if client_id is not None and (not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", client_id)):
                    raise ValueError("client_request_id必须是1–80字符的安全标识")
                tracking_id = client_id or "server-" + request_id
                with LOCK:
                    if started_epoch != EPOCH:
                        raise ProviderError("请求已被隐私删除取消", "REQUEST_SUPERSEDED", 409)
                    if client_id in ACTIVE_REQUESTS:
                        raise ProviderError("该client_request_id已有在途请求", "DUPLICATE_REQUEST", 409)
                    if client_id in CANCELLED_REQUESTS:
                        raise ProviderError("该请求已取消，请为新请求生成新标识", "REQUEST_CANCELLED", 409)
                    if len(ACTIVE_REQUESTS) >= 32:
                        raise ProviderError("在途请求过多，请稍后重试", "REQUEST_BUSY", 429)
                    ASK_SEQUENCE += 1
                    token = (EPOCH, ASK_SEQUENCE)
                    ACTIVE_REQUESTS[tracking_id] = token
                try:
                    result = self._ask(data, request_id, token)
                finally:
                    with LOCK:
                        if ACTIVE_REQUESTS.get(tracking_id) == token:
                            ACTIVE_REQUESTS.pop(tracking_id)
                return self._json(200, result)
            with LOCK:
                if started_epoch != EPOCH:
                    raise ProviderError("请求已被隐私删除取消", "REQUEST_SUPERSEDED", 409)
                if path == "/api/notes":
                    note = STATE.note(self._text(data, "text", 2000))
                    return self._json(201, {"note": note})
                if path == "/api/media/validate":
                    if data.get("consent") is not True:
                        raise ProviderError("本地图片上传也需要明确同意", "CONSENT_REQUIRED", 403)
                    # Deliberately no provider call: local camera acceptance can
                    # run without a key and without sending a frame to the cloud.
                    import base64
                    import io
                    from PIL import Image
                    from hashlib import sha256
                    clean = validate_image(data.get("image_data"))
                    header, encoded = clean.split(",", 1)
                    raw_image = base64.b64decode(encoded)
                    with Image.open(io.BytesIO(raw_image)) as decoded:
                        metadata = {"width": decoded.width, "height": decoded.height, "format": decoded.format,
                                    "sanitized_bytes": len(raw_image), "sanitized_sha256": sha256(raw_image).hexdigest()}
                    return self._json(200, {"validated": True, "scope": "local_only", "cloud_sent": False,
                                            "image": metadata, "request_id": request_id})
                if path == "/api/requests/cancel":
                    client_id = self._text(data, "client_request_id", 80)
                    if not client_id or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", client_id):
                        raise ValueError("取消需要有效client_request_id")
                    if client_id not in CANCELLED_REQUESTS and len(CANCELLED_REQUESTS) >= 256:
                        raise ProviderError("取消记录容量已满，请清除本地原型数据后重试", "REQUEST_BUSY", 429)
                    CANCELLED_REQUESTS.add(client_id)
                    active_token = ACTIVE_REQUESTS.pop(client_id, None)
                    if active_token == (EPOCH, ASK_SEQUENCE):
                        ASK_SEQUENCE += 1
                        STATE.last_hud = to_hud("cancelled", "已取消本地请求；不能保证撤回已发出的云端处理")
                        STATE.last_hud["title"] = "已取消"
                    return self._json(200, {"cancelled": True, "was_active": active_token is not None, "client_request_id": client_id,
                                            "scope": "local_result_only", "hud": STATE.last_hud})
                if path == "/api/tasks/draft":
                    task = STATE.draft_task(self._text(data, "text", 500))
                    ASK_SEQUENCE += 1
                    return self._json(201, {"task": task, "hud": STATE.last_hud})
                if path == "/api/tasks/confirm":
                    task = STATE.confirm_task(self._text(data, "id", 80))
                    ASK_SEQUENCE += 1
                    return self._json(200, {"task": task, "hud": STATE.last_hud})
                if path == "/api/privacy/delete":
                    EPOCH += 1  # do not let an old inference repopulate a wiped HUD
                    ACTIVE_REQUESTS.clear()
                    CANCELLED_REQUESTS.clear()
                    return self._json(200, STATE.wipe())
            return self._json(404, {"error": "not_found"})
        except (ValueError, UnicodeError) as exc:
            self._failure(400, str(exc), "INVALID_REQUEST", path, request_id, token)
        except ProviderError as exc:
            self._failure(exc.status, str(exc), exc.code, path, request_id, token)
        except TimeoutError:
            self._failure(408, "请求上传超时", "UPLOAD_TIMEOUT", path, request_id, token)

    @staticmethod
    def _text(data, key, limit):
        value = data.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"{key}必须是{limit}字以内文本")
        return value

    def _failure(self, status, message, code, path, request_id, token):
        hud = to_hud("error", message)
        hud.update({"title": "请求失败", "request_id": request_id, "code": code})
        if path == "/api/ask" and token is not None:
            with LOCK:
                if token == (EPOCH, ASK_SEQUENCE):
                    STATE.last_hud = hud
        self._json(status, {"error": message, "code": code, "hud": hud, "request_id": request_id})


def main():
    port = int(os.getenv("PORT", "8765"))
    addr = os.getenv("BIND_HOST", "127.0.0.1")
    if addr not in ("127.0.0.1", "localhost"):
        raise SystemExit("当前API仅允许绑定IPv4 loopback；手机/LAN部署需要独立的HTTPS与身份认证适配")
    print(f"AI/AR Glasses V1: http://{addr}:{port} | provider={PROVIDER.name if PROVIDER else 'unavailable'}")
    if CONFIG_ERROR:
        print(str(CONFIG_ERROR))
    ThreadingHTTPServer((addr, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
