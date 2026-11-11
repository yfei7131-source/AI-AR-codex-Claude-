"""Sprint02 OCR/cancellation integration: upstream is always an explicit stub."""
import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from app import server
from app.core import Memory
from app.provider import DemoProvider, OpenAIProvider, ProviderError, validate_ocr
from test_vision import picture


def ocr(target="en"):
    return {"original_text": "出口", "translated_text": "EXIT", "source_language": "zh-CN", "target_language": target, "uncertain": False}


class OcrProviderTest(unittest.TestCase):
    def test_strict_schema_and_original_preserved_both_targets(self):
        for target in ("en", "zh-CN"):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-placeholder"}):
                live = OpenAIProvider()
            expected = ocr(target)
            live._open = Mock(return_value=io.BytesIO(json.dumps({"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(expected)}]}]}).encode()))
            actual = live.respond("翻译", picture(), "translate", structured=True, target_language=target)
            self.assertEqual(actual, expected)
            payload = json.loads(live._open.call_args.args[0].data)
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertFalse(payload["store"])

    def test_ocr_rejects_malformed_and_unmarked_missing_original(self):
        for data in ({}, dict(ocr(), original_text=""), dict(ocr(), uncertain="false"), dict(ocr(), target_language="fr"), dict(ocr(), extra="x")):
            with self.subTest(data=data), self.assertRaises(ProviderError):
                validate_ocr(data, "en")
        self.assertTrue(validate_ocr(dict(ocr(), original_text="", uncertain=True), "en")["uncertain"])

    def test_demo_never_invents_original_text(self):
        result = DemoProvider().respond("test", picture(), "translate", structured=True, target_language="en")
        self.assertEqual(result["original_text"], "")
        self.assertTrue(result["uncertain"])
        self.assertIn("模拟", result["translated_text"])

    def test_legacy_text_translation_honors_english_target(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-placeholder"}):
            live = OpenAIProvider()
        live._open = Mock(return_value=io.BytesIO(json.dumps({"status":"completed", "output":[{"content":[{"type":"output_text","text":"EXIT"}]}]}).encode()))
        self.assertEqual(live.respond("translate", picture(), "translate", target_language="en"), "EXIT")
        self.assertIn("英文", json.loads(live._open.call_args.args[0].data)["instructions"])


class Sprint02HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def setUp(self):
        context = patch.multiple(server, PROVIDER=DemoProvider(), CONFIG_ERROR=None, STATE=Memory(), ACTIVE_REQUESTS={}, CANCELLED_REQUESTS=set())
        context.start()
        self.addCleanup(context.stop)

    def post(self, path, data):
        req = Request(self.base + "/api/" + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def test_ocr_contract_keeps_original_outside_short_hud(self):
        class Stub(DemoProvider):
            name, mode = "openai", "live"
            def respond(self, *args, **kwargs):
                return ocr(kwargs["target_language"])
        with patch.object(server, "PROVIDER", Stub()):
            status, result = self.post("ask", {"mode": "live", "kind": "translate", "image_data": picture(), "consent": True, "output_format": "ocr", "target_language": "en", "client_request_id": "ocr-1"})
        self.assertEqual(status, 200)
        self.assertEqual(result["ocr"]["original_text"], "出口")
        self.assertEqual(result["hud"]["lines"], ["EXIT"])
        self.assertFalse(result["simulated"])
        self.assertEqual(result["client_request_id"], "ocr-1")
        self.assertEqual(server.ACTIVE_REQUESTS, {})

    def test_ocr_options_and_client_id_validation(self):
        for fields in ({"output_format": "ocr", "kind": "chat"}, {"target_language": "fr"}, {"client_request_id": "bad\nheader"}):
            data = dict({"mode": "demo", "kind": "translate", "question": "test", "image_data": picture(), "consent": True}, **fields)
            self.assertEqual(self.post("ask", data)[0], 400)

    def test_cancel_discards_inflight_answer_and_does_not_wipe_notes(self):
        entered, release = threading.Event(), threading.Event()
        class Blocking(DemoProvider):
            def respond(self, *args, **kwargs):
                entered.set()
                release.wait(3)
                return "late answer must not display"
        result = []
        self.post("notes", {"text": "keep this note"})
        with patch.object(server, "DemoProvider", Blocking):
            worker = threading.Thread(target=lambda: result.append(self.post("ask", {"mode": "demo", "kind": "chat", "question": "test", "client_request_id": "cancel-1"})))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                status, cancelled = self.post("requests/cancel", {"client_request_id": "cancel-1"})
                self.assertEqual(status, 200)
                self.assertTrue(cancelled["was_active"])
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(result[0][0], 409)
        self.assertNotIn("answer", result[0][1])
        self.assertEqual(server.STATE.last_hud["kind"], "cancelled")
        self.assertEqual(len(server.STATE.notes), 1)

    def test_cancel_before_upload_finishes_and_repeated_cancel(self):
        for _ in range(2):
            self.assertTrue(self.post("requests/cancel", {"client_request_id": "not-yet-arrived"})[1]["cancelled"])
        status, result = self.post("ask", {"mode": "demo", "kind": "chat", "question": "test", "client_request_id": "not-yet-arrived"})
        self.assertEqual((status, result["code"]), (409, "REQUEST_CANCELLED"))

    def test_local_media_validation_never_calls_a_provider(self):
        with patch.object(server.DemoProvider, "respond", side_effect=AssertionError("provider must not be used")):
            status, result = self.post("media/validate", {"consent":True,"image_data":picture()})
        self.assertEqual(status, 200)
        self.assertFalse(result["cloud_sent"])
        self.assertEqual(result["scope"], "local_only")
        self.assertEqual(result["image"]["width"], 3)
        self.assertEqual(self.post("media/validate", {"consent":False,"image_data":picture()})[0], 403)
        self.assertEqual(self.post("media/validate", {"consent":True,"image_data":"invalid"})[0], 400)

    def test_inflight_limit_includes_legacy_requests_without_client_id(self):
        server.ACTIVE_REQUESTS.update({f"busy-{i}":(0,i) for i in range(32)})
        status, result = self.post("ask", {"mode":"demo","kind":"chat","question":"test"})
        self.assertEqual((status, result["code"]), (429, "REQUEST_BUSY"))


if __name__ == "__main__":
    unittest.main()
