"""Offline contract/integration tests; no real model or physical HUD involved."""
import base64
import io
import json
import threading
import socket
import http.client
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch, Mock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from app import server
from app.core import Memory, to_hud
from app.images import validate_image, MAX_IMAGE_BYTES
from app.provider import DemoProvider, OpenAIProvider, ProviderError, build_provider


def picture(fmt="PNG", size=(3, 3)):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format=fmt)
    return "data:image/" + ("jpeg" if fmt == "JPEG" else "png") + ";base64," + base64.b64encode(out.getvalue()).decode()


class ImageTest(unittest.TestCase):
    def test_valid_jpeg_png(self):
        for fmt in ("JPEG", "PNG"):
            data = picture(fmt)
            sanitized = validate_image(data)
            self.assertTrue(sanitized.startswith(data.split(',')[0] + ','))
            self.assertEqual(validate_image(sanitized), sanitized)

    def test_metadata_and_trailing_bytes_removed(self):
        out = io.BytesIO()
        metadata = PngInfo()
        metadata.add_text("location", "PRIVATE LOCATION")
        Image.new("RGB", (3, 3), "white").save(out, format="PNG", pnginfo=metadata)
        raw = out.getvalue() + b"PRIVATE TRAILING CONTENT"
        sanitized = validate_image("data:image/png;base64," + base64.b64encode(raw).decode())
        clean = base64.b64decode(sanitized.split(",")[1])
        self.assertNotIn(b"PRIVATE", clean)

    def test_reject_empty_fake_base64_url_and_mime(self):
        for data in (None, 123, "", "https://example.com/p.png", "data:image/png;base64,", "data:image/png;base64,@@@", "data:image/png;base64,aGVsbG8=", picture().replace("image/png", "image/jpeg")):
            with self.subTest(data=str(data)[:40]), self.assertRaises(ValueError):
                validate_image(data)

    def test_reject_truncated_jpeg_and_png(self):
        for fmt in ("JPEG", "PNG"):
            data = picture(fmt)
            head, body = data.split(",")
            bad = head + "," + base64.b64encode(base64.b64decode(body)[:40]).decode()
            with self.assertRaises(ValueError):
                validate_image(bad)

    def test_two_mib_limit(self):
        # Pad a valid PNG to exercise decoded size boundary, without a private image.
        head, body = picture().split(",")
        raw = base64.b64decode(body)
        valid = raw + b"\0" * (MAX_IMAGE_BYTES - len(raw))
        for length in (1024 * 1024, MAX_IMAGE_BYTES):
            self.assertEqual(validate_image(head + "," + base64.b64encode(valid[:length]).decode())[:15], "data:image/png;")
        with self.assertRaises(ValueError):
            validate_image(head + "," + base64.b64encode(valid + b"x").decode())

    def test_pixel_limit(self):
        with self.assertRaises(ValueError):
            validate_image(picture(size=(4001, 4000)))

    def test_hud_three_lines_and_truncation(self):
        hud = to_hud("vision", "结果" * 100)
        self.assertEqual(len(hud["lines"]), 3)
        self.assertTrue(hud["truncated"])
        self.assertTrue(hud["lines"][-1].endswith("…"))


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"OPENAI_API_KEY": "unit-test-placeholder", "AI_TIMEOUT_SECONDS": "1", "AI_MAX_ATTEMPTS": "2"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.provider = OpenAIProvider()

    def response(self, value):
        result = Mock()
        result.__enter__ = Mock(return_value=result)
        result.__exit__ = Mock(return_value=False)
        result.read.return_value = json.dumps(value).encode()
        return result

    def good(self):
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "测试桩：原文 STOP；译文 停止"}]}]}

    def test_live_payload_image_store_false_and_ocr_detail(self):
        self.provider._open = Mock(return_value=self.response(self.good()))
        image = picture()
        answer = self.provider.respond("翻译", image, "translate")
        req = self.provider._open.call_args.args[0]
        payload = json.loads(req.data)
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
        self.assertIs(payload["store"], False)
        content = payload["input"][0]["content"]
        self.assertEqual(content[1], {"type": "input_image", "image_url": image, "detail": "high"})
        self.assertIn("STOP", answer)

    def test_live_requires_image(self):
        self.provider._open = Mock()
        for kind in ("vision", "translate"):
            with self.assertRaises(ProviderError):
                self.provider.respond("问", None, kind)
        self.provider._open.assert_not_called()

    def test_unknown_provider_never_falls_back(self):
        with patch.dict("os.environ", {"AI_PROVIDER": "typo"}), self.assertRaises(ProviderError):
            build_provider()

    def test_retry_transient_http_only(self):
        exc = HTTPError("url", 503, "service down", {}, io.BytesIO(b"secret upstream body"))
        self.provider._open = Mock(side_effect=[exc, self.response(self.good())])
        with patch("app.provider.time.sleep"):
            self.assertIn("STOP", self.provider.respond("问", picture()))
        self.assertEqual(self.provider._open.call_count, 2)

    def test_auth_failure_not_retried_or_leaked(self):
        self.provider._open = Mock(side_effect=HTTPError("url", 401, "secret-key", {}, io.BytesIO(b"private")))
        with self.assertRaises(ProviderError) as ctx:
            self.provider.respond("问", picture())
        self.assertEqual(self.provider._open.call_count, 1)
        self.assertNotIn("secret", str(ctx.exception))
        self.assertNotIn("private", str(ctx.exception))

    def test_timeout_no_retry(self):
        for exc in (TimeoutError(), URLError(TimeoutError())):
            self.provider._open = Mock(side_effect=exc)
            with self.assertRaises(ProviderError) as ctx:
                self.provider.respond("问", picture())
            self.assertEqual(ctx.exception.status, 504)
            self.assertEqual(self.provider._open.call_count, 1)

    def test_bad_empty_incomplete_and_refusal(self):
        for result in ([], {"status": "incomplete"}, {"status": "completed", "output": []},
                       {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]},
                       {"status": "completed", "output": "wrong"}):
            with self.subTest(result=result), self.assertRaises(ProviderError):
                self.provider._open = Mock(return_value=self.response(result))
                self.provider.respond("问", picture())

    def test_invalid_json_and_network(self):
        broken = self.response({})
        broken.read.return_value = b"not json"
        for stub in (Mock(return_value=broken), Mock(side_effect=URLError("private network detail"))):
            self.provider._open = stub
            with self.assertRaises(ProviderError):
                self.provider.respond("问", picture())

    def test_invalid_timeout_config(self):
        with patch.dict("os.environ", {"AI_TIMEOUT_SECONDS": "nan"}), self.assertRaises(ProviderError):
            OpenAIProvider()


class VisionHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.url = "http://127.0.0.1:" + str(cls.http.server_port)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def setUp(self):
        self.patch = patch.multiple(server, PROVIDER=DemoProvider(), CONFIG_ERROR=None, STATE=Memory())
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def post(self, data, path="/api/ask", headers=None):
        req = Request(self.url + path, data=json.dumps(data).encode(), headers=headers or {"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.load(resp)
        except HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def payload(self, **overrides):
        return dict({"mode": "demo", "kind": "vision", "question": "这是什么", "image_data": picture(), "consent": True}, **overrides)

    def test_demo_marked_in_response_and_hud(self):
        status, result = self.post(self.payload())
        self.assertEqual(status, 200)
        self.assertTrue(result["simulated"])
        self.assertEqual(result["hud"]["mode"], "demo")
        self.assertIn("模拟", result["answer"])

    def test_live_in_demo_server_cannot_succeed(self):
        status, result = self.post(self.payload(mode="live"))
        self.assertEqual((status, result["code"]), (503, "AI_NOT_CONFIGURED"))
        self.assertNotIn("answer", result)

    def test_live_adapter_to_http_hud_contract(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-placeholder"}):
            live = OpenAIProvider()
        result = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": "离线测试桩视觉答复"}]}]}
        response = io.BytesIO(json.dumps(result).encode())
        live._open = Mock(return_value=response)
        with patch.object(server, "PROVIDER", live):
            status, obj = self.post(self.payload(mode="live"))
        self.assertEqual(status, 200)
        self.assertFalse(obj["simulated"])
        self.assertEqual(obj["provider"], "openai")
        self.assertEqual(obj["hud"]["request_id"], obj["request_id"])
        with urlopen(self.url + "/api/state") as resp:
            self.assertEqual(json.load(resp)["hud"], obj["hud"])

    def test_consent_missing_false_or_truthy_rejected(self):
        for value in (None, False, "true", 1):
            status, obj = self.post(self.payload(consent=value))
            self.assertEqual((status, obj["code"]), (403, "CONSENT_REQUIRED"))

    def test_image_required_and_malformed(self):
        for kind in ("vision", "translate"):
            status, obj = self.post(self.payload(kind=kind, image_data=None))
            self.assertEqual((status, obj["code"]), (400, "IMAGE_REQUIRED"))
        status, obj = self.post(self.payload(image_data="data:image/png;base64,aGVsbG8="))
        self.assertEqual((status, obj["code"]), (400, "INVALID_IMAGE"))

    def test_mode_kind_and_question_types(self):
        for fields in ({"mode": "openai"}, {"kind": "bad"}, {"question": []}, {"question": "x" * 501}):
            self.assertEqual(self.post(self.payload(**fields))[0], 400)

    def test_chat_without_image(self):
        self.assertEqual(self.post({"kind": "chat", "question": "你好", "mode": "demo"})[0], 200)

    def test_origin_and_content_type(self):
        self.assertEqual(self.post(self.payload(), headers={"Content-Type": "application/json", "Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.post(self.payload(), headers={"Content-Type": "text/plain"})[0], 415)

    def test_errors_update_hud(self):
        _, result = self.post(self.payload(image_data=None))
        with urlopen(self.url + "/api/state") as resp:
            self.assertEqual(json.load(resp)["hud"], result["hud"])

    def test_privacy_delete_discards_inflight_result(self):
        started, release = threading.Event(), threading.Event()
        class Blocking(DemoProvider):
            def respond(self, *args):
                started.set()
                release.wait(3)
                return "late private result"
        result = []
        with patch.object(server, "PROVIDER", Blocking()):
            # Demo is explicitly local; substitute its constructor to block inference.
            with patch.object(server, "DemoProvider", Blocking):
                worker = threading.Thread(target=lambda: result.append(self.post(self.payload())))
                worker.start()
                try:
                    self.assertTrue(started.wait(2))
                    self.assertEqual(self.post({}, "/api/privacy/delete")[0], 200)
                finally:
                    release.set()
                    worker.join(5)
        self.assertEqual(result[0][0], 409)
        self.assertEqual(server.STATE.last_hud["title"], "数据已清除")
        self.assertNotIn("late private", json.dumps(result))

    def test_privacy_delete_invalidates_slow_upload_before_mutation(self):
        body = json.dumps({"text": "old private note"}).encode()
        with socket.create_connection(("127.0.0.1", self.http.server_port), timeout=3) as client:
            head = (f"POST /api/notes HTTP/1.1\r\nHost: 127.0.0.1:{self.http.server_port}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode()
            original = server.Handler._local_request
            entered = threading.Event()
            def observed(handler):
                if handler.path == "/api/notes":
                    entered.set()
                return original(handler)
            with patch.object(server.Handler, "_local_request", observed):
                client.sendall(head + body[:1])
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.post({}, "/api/privacy/delete")[0], 200)
                client.sendall(body[1:])
                response = http.client.HTTPResponse(client)
                response.begin()
                self.assertEqual(response.status, 409)
                response.read()
        self.assertEqual(server.STATE.notes, [])

    def test_task_hud_supersedes_old_inference(self):
        started, release = threading.Event(), threading.Event()
        class Blocking(DemoProvider):
            def respond(self, *args):
                started.set()
                release.wait(3)
                return "old vision result"
        result = []
        with patch.object(server, "DemoProvider", Blocking):
            worker = threading.Thread(target=lambda: result.append(self.post(self.payload())))
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.post({"text": "new task"}, "/api/tasks/draft")[0], 201)
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(result[0][0], 409)
        self.assertEqual(server.STATE.last_hud["kind"], "task")


if __name__ == "__main__":
    unittest.main()
