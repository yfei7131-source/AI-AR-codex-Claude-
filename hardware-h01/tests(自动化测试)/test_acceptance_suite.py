"""Batch-runner contracts only: all success/fault responses here are injected."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image
from tools.acceptance.generate import generate_images, load_manifest
from tools.acceptance import run
from tools.acceptance.score import score_report
from tools.verify_live import VerificationError


class InjectedTransport:
    """Test-only fault injector. Never represents a cloud API invocation."""
    def __init__(self, health=None, failures=None, response_changes=None):
        self.health = health if health is not None else {"ready": True, "provider": "openai", "mode": "live"}
        self.failures = failures or {}
        self.changes = response_changes or {}
        self.calls, self.asks = [], []
        self.manifest = load_manifest()

    def call(self, path, payload=None):
        self.calls.append(path)
        if path == "health":
            return self.health
        if path == "requests/cancel":
            return {"cancelled": True}
        self.asks.append(payload)
        index = len(self.asks) - 1
        if index in self.failures:
            raise self.failures[index]
        sample = self.manifest["samples"][index]
        result = {"provider": "openai", "mode": "live", "simulated": False,
                  "request_id": f"injected_{index}", "answer": "PRIVATE INJECTED ANSWER",
                  "hud": {"lines": ["PRIVATE INJECTED HUD"]}}
        if sample["kind"] == "translate":
            result["ocr"] = {"original_text": "\n".join(sample["expected"]["text"]),
                             "translated_text": "注入的译文，不是真实模型结果", "source_language": sample["source_language"],
                             "target_language": sample["target_language"], "uncertain": False}
        result.update(self.changes)
        return result


class AcceptanceSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.image_dir = Path(cls.directory.name)
        cls.manifest = load_manifest()
        generate_images(cls.manifest, cls.image_dir)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def execute(self, transport=None, **options):
        return run.run_suite(True, image_dir=self.image_dir,
                             transport=transport or InjectedTransport(), **options)

    def test_twenty_non_sensitive_fixtures_and_expected_text(self):
        self.assertEqual(len(self.manifest["samples"]), 20)
        self.assertEqual(sum(s["kind"] == "vision" for s in self.manifest["samples"]), 10)
        self.assertEqual(sum(s.get("target_language") == "en" for s in self.manifest["samples"]), 5)
        self.assertEqual(sum(s.get("target_language") == "zh-CN" for s in self.manifest["samples"]), 5)
        for sample in self.manifest["samples"]:
            self.assertTrue(sample["expected"]["text"])
            with Image.open(self.image_dir / sample["image"]) as image:
                image.load()
                self.assertEqual(image.size, (1200, 840))
            self.assertLess((self.image_dir / sample["image"]).stat().st_size, 2 * 1024 * 1024)

    def test_missing_consent_blocks_all_without_any_network(self):
        transport = InjectedTransport()
        result = run.run_suite(False, image_dir=Path("does-not-exist"), transport=transport)
        self.assertEqual(result["summary"]["counts"]["blocked"], 20)
        self.assertEqual(transport.calls, [])

    def test_missing_key_unready_or_demo_blocks_twenty_without_upload(self):
        for health in ({"ready": False, "provider": "openai", "mode": "live", "configuration_error": "missing key"},
                       {"ready": True, "provider": "demo", "mode": "demo"}):
            with self.subTest(health=health):
                transport = InjectedTransport(health=health)
                result = self.execute(transport)
                self.assertEqual(result["summary"]["counts"]["blocked"], 20)
                self.assertEqual(transport.calls, ["health"])
                self.assertEqual(transport.asks, [])

    def test_injected_successes_never_count_as_real_cloud_or_quality(self):
        transport = InjectedTransport()
        report = self.execute(transport)
        self.assertEqual(report["summary"]["counts"]["success"], 20)
        self.assertEqual(report["evidence_origin"], "injected_test_transport")
        self.assertTrue(all(not item["cloud_response_received"] for item in report["results"]))
        self.assertEqual(report["summary"]["quality_unknown_samples"], 20)
        self.assertIsNone(report["summary"]["quality_accuracy_on_reviewed_samples"])
        self.assertNotIn("PRIVATE INJECTED", json.dumps(report))
        self.assertNotIn("base64", json.dumps(report))
        for sample, payload in zip(self.manifest["samples"], transport.asks):
            self.assertEqual(payload["mode"], "live")
            self.assertIs(payload["consent"], True)
            self.assertTrue(payload["client_request_id"].startswith("acceptance_"))
            if payload["kind"] == "translate":
                self.assertEqual(payload["output_format"], "ocr")
                self.assertEqual(payload["target_language"], sample["target_language"])
                self.assertEqual(payload["source_language"], sample["source_language"])

    def test_answer_recording_is_explicit_and_includes_structured_ocr(self):
        report = self.execute(record_answers=True)
        self.assertTrue(report["answers_recorded"])
        self.assertEqual(report["results"][0]["answer"], "PRIVATE INJECTED ANSWER")
        self.assertEqual(report["results"][10]["ocr"]["original_text"], "KEEP DOOR CLOSED")
        self.assertIn("translated_text", report["results"][10]["ocr"])
        self.assertEqual(report["results"][10]["human_score"], "unknown")
        self.assertEqual(report["results"][15]["ocr"]["original_text"], "交货日期\n2026-11-20")
        self.assertEqual(report["results"][15]["ocr"]["target_language"], "en")

    def test_ocr_contract_rejects_wrong_target_in_both_directions(self):
        for target in ("en", "zh-CN"):
            with self.subTest(target=target):
                response = {"provider":"openai", "mode":"live", "simulated":False,
                            "answer":"INJECTED", "hud":{"lines":["INJECTED"]}, "request_id":"injected",
                            "ocr":{"original_text":"原文", "translated_text":"translation",
                                   "source_language":"zh-CN", "target_language":target, "uncertain":False}}
                run.validate_live_result(response, "translate", target)
                other = "en" if target == "zh-CN" else "zh-CN"
                with self.assertRaises(run.TransportFailure):
                    run.validate_live_result(response, "translate", other)

    def test_failure_timeout_cancel_disconnect_are_separate(self):
        transport = InjectedTransport(failures={
            0: run.TransportFailure("failed", "AI_REFUSAL"),
            1: run.TransportFailure("timeout", "AI_TIMEOUT"),
            2: run.TransportFailure("cancelled", "REQUEST_SUPERSEDED"),
            3: run.TransportFailure("disconnected", "CONNECTION_LOST"),
        })
        counts = self.execute(transport)["summary"]["counts"]
        self.assertEqual(counts, {"blocked": 0, "success": 16, "failed": 1, "timeout": 1,
                                  "cancelled": 1, "disconnected": 1})

    def test_keyboard_cancel_requests_local_cancel_and_stops_further_uploads(self):
        transport = InjectedTransport(failures={0: KeyboardInterrupt()})
        report = self.execute(transport)
        self.assertEqual(report["summary"]["counts"]["cancelled"], 1)
        self.assertEqual(report["summary"]["counts"]["blocked"], 19)
        self.assertEqual(len(transport.asks), 1)
        self.assertEqual(transport.calls, ["health", "ask", "requests/cancel"])
        self.assertTrue(report["results"][0]["local_cancel_requested"])

    def test_demo_or_invalid_contract_cannot_pass(self):
        for changes in ({"simulated": True}, {"mode": "demo"}, {"provider": "demo"},
                        {"answer": ""}, {"hud": {"lines": []}}, {"request_id": "bad\nID"}):
            with self.subTest(changes=changes):
                report = self.execute(InjectedTransport(response_changes=changes))
                self.assertEqual(report["summary"]["counts"]["failed"], 20)

    def test_translation_requires_structured_ocr_not_only_http_200(self):
        report = self.execute(InjectedTransport(response_changes={"ocr": None}))
        self.assertEqual(report["summary"]["counts"]["success"], 10)
        self.assertEqual(report["summary"]["counts"]["failed"], 10)

    def test_missing_image_is_local_failure(self):
        transport = InjectedTransport()
        result = run.run_suite(True, image_dir=Path("does-not-exist"), transport=transport)
        self.assertEqual(result["summary"]["counts"]["failed"], 20)
        self.assertEqual(transport.calls, ["health"])

    def test_human_quality_unknown_is_not_counted_in_accuracy(self):
        report = self.execute()
        with self.assertRaises(ValueError):
            score_report(report, "V01", "pass")  # injected result cannot become cloud evidence
        # Explicitly construct manual-review metadata, without making a network claim.
        samples = [dict(report["results"][0], evidence_origin="local_live_api", human_score="pass"),
                   dict(report["results"][1], evidence_origin="local_live_api", human_score="fail"),
                   dict(report["results"][2], evidence_origin="local_live_api", human_score="unknown")]
        stats = run.summary(samples)
        self.assertEqual(stats["reviewed_quality_samples"], 2)
        self.assertEqual(stats["quality_accuracy_on_reviewed_samples"], 0.5)
        self.assertEqual(stats["quality_unknown_samples"], 1)

    def test_private_report_output_and_loopback_are_enforced(self):
        with self.assertRaises(VerificationError):
            run.private_report_path(Path.cwd() / "public-answers.json")
        with self.assertRaises(VerificationError):
            run.run_suite(True, base_url="https://example.com", transport=InjectedTransport())

    def test_http_error_codes_and_network_are_classified_without_private_details(self):
        transport = run.LocalTransport("http://127.0.0.1:8765", 1)
        scenarios = [(HTTPError("url", 504, "private", {}, io.BytesIO(b'{"code":"AI_TIMEOUT","error":"private answer"}')), "timeout"),
                     (HTTPError("url", 409, "private", {}, io.BytesIO(b'{"code":"REQUEST_SUPERSEDED"}')), "cancelled"),
                     (URLError(TimeoutError("private")), "timeout"),
                     (URLError("private"), "disconnected")]
        for failure, expected in scenarios:
            with self.subTest(expected=expected), patch.object(transport.opener, "open", side_effect=failure):
                with self.assertRaises(run.TransportFailure) as context:
                    transport.call("ask", {})
                self.assertEqual(context.exception.status, expected)
                self.assertNotIn("private", str(context.exception))


if __name__ == "__main__":
    unittest.main()
