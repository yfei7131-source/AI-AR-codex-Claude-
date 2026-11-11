import unittest
from unittest.mock import patch
from tools.capture_local import capture
from tools.verify_live import VerificationError


class LocalCaptureTest(unittest.TestCase):
    def test_consent_is_checked_before_files_or_camera(self):
        with patch("tools.capture_local.subprocess.run") as run:
            with self.assertRaises(VerificationError):
                capture("missing.exe", "XiaoMi Webcam", False, "http://127.0.0.1:8765")
            run.assert_not_called()

    def test_cloud_destination_is_refused_before_camera(self):
        with patch("tools.capture_local.subprocess.run") as run:
            with self.assertRaises(VerificationError):
                capture("missing.exe", "XiaoMi Webcam", True, "https://example.com")
            run.assert_not_called()
