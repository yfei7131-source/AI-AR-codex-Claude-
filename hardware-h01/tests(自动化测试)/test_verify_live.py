"""Live verifier tests use explicit fakes; they do not contact an AI provider."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib import error

from tools import verify_live as live


class FakeResponse(io.BytesIO):
    pass


class FakeOpener:
    def __init__(self, health=None, answer=None):
        self.health = health if health is not None else {"ready": True, "provider": "openai", "mode": "live"}
        self.answer = answer if answer is not None else {
            "answer": "FAKE CONTRACT RESPONSE", "hud": {"lines": ["FAKE CONTRACT RESPONSE"]},
            "mode": "live", "simulated": False, "provider": "openai", "request_id": "fake_contract_01",
        }
        self.requests = []

    def open(self, req, timeout):
        self.requests.append(req)
        payload = self.health if req.full_url.endswith("/api/health") else self.answer
        return FakeResponse(json.dumps(payload).encode())


class LiveVerifierTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / "fake-contract.png"
        # Header-only fixture is sufficient to exercise this CLI's transport;
        # the server is responsible for full image decoding and validation.
        self.image.write_bytes(b"\x89PNG\r\n\x1a\nFAKE_CONTRACT_FIXTURE")
        self.origin = "http://127.0.0.1:8765"

    def run_fake(self, opener):
        with patch.object(live.request, "build_opener", return_value=opener):
            return live.verify(self.origin, self.image, True)

    def test_live_contract_sends_image_and_explicit_consent(self):
        opener = FakeOpener()
        result = self.run_fake(opener)
        payload = json.loads(opener.requests[1].data)
        self.assertEqual(payload["mode"], "live")
        self.assertIs(payload["consent"], True)
        self.assertTrue(payload["image_data"].startswith("data:image/png;base64,"))
        self.assertEqual(result["request_id"], "fake_contract_01")
        self.assertNotIn("answer", result)
        self.assertNotIn("image_data", result)

    def test_consent_required_before_read_or_network(self):
        with patch.object(live.request, "build_opener") as build:
            with self.assertRaisesRegex(live.VerificationError, "consent-upload"):
                live.verify(self.origin, Path("missing-image.png"), False)
            build.assert_not_called()

    def test_demo_or_unready_health_never_uploads(self):
        for health in ({"ready": True, "provider": "demo", "mode": "demo"},
                       {"ready": False, "provider": "openai", "mode": "live"}):
            with self.subTest(health=health):
                opener = FakeOpener(health=health)
                with self.assertRaisesRegex(live.VerificationError, "never fall back"):
                    self.run_fake(opener)
                self.assertEqual(len(opener.requests), 1)

    def test_rejects_demo_or_malformed_success(self):
        for changes in ({"simulated": True}, {"provider": "demo"}, {"mode": "demo"},
                        {"answer": ""}, {"hud": {"lines": []}}, {"hud": {"lines": [None]}},
                        {"request_id": "unsafe\nID"}, {"error": "private response"}):
            with self.subTest(changes=changes):
                opener = FakeOpener()
                opener.answer.update(changes)
                with self.assertRaises(live.VerificationError):
                    self.run_fake(opener)

    def test_rejects_nonlocal_or_ambiguous_urls(self):
        for url in ("https://api.openai.com", "http://192.168.0.1:8765", "file:///tmp/a",
                    "http://user:password@localhost:8765", "http://localhost:8765/path",
                    "http://localhost:8765?secret=value", "http://localhost:0", "http://localhost:bad"):
            with self.subTest(url=url), self.assertRaises(live.VerificationError):
                live.local_base_url(url)
        self.assertEqual(live.local_base_url("http://localhost:8765/"), self.origin)
        self.assertEqual(live.local_base_url("http://[::1]:8765"), "http://[::1]:8765")

    def test_rejects_redirect(self):
        with self.assertRaisesRegex(live.VerificationError, "redirects"):
            live.NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://remote.invalid")

    def test_timeout_and_http_error_are_safe_failures(self):
        for failure in (TimeoutError("private detail"), error.URLError("private detail"),
                        error.HTTPError(self.origin, 502, "private detail", {}, io.BytesIO(b"private body"))):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(live.request.OpenerDirector, "open", side_effect=failure):
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        code = live.main(["--image", str(self.image), "--consent-upload"])
                self.assertEqual(code, 1)
                self.assertNotIn("private", output.getvalue())
                self.assertIn("FAIL", output.getvalue())

    def test_nonimage_and_oversized_are_rejected(self):
        for content in (b"not an image", b"\x89PNG\r\n\x1a\n" + b"x" * live.MAX_IMAGE_BYTES):
            self.image.write_bytes(content)
            with self.assertRaises(live.VerificationError):
                live.image_data_url(self.image)

    def test_cli_output_contains_metadata_only(self):
        with patch.object(live.request, "build_opener", return_value=FakeOpener()):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = live.main(["--image", str(self.image), "--consent-upload", "--kind", "translate"])
        self.assertEqual(code, 0)
        self.assertIn("fake_contract_01", output.getvalue())
        self.assertNotIn("FAKE CONTRACT RESPONSE", output.getvalue())
        self.assertNotIn("data:image", output.getvalue())
        self.assertIn("not AI accuracy", output.getvalue())

    def test_invalid_json_is_safe_failure(self):
        class InvalidJsonOpener:
            def open(self, req, timeout):
                return FakeResponse(b"private invalid content")
        with self.assertRaisesRegex(live.VerificationError, "invalid JSON"):
            live.request_json(InvalidJsonOpener(), self.origin, 1)


if __name__ == "__main__":
    unittest.main()
