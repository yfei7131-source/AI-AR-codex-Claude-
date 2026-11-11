"""Opt-in Windows DirectShow still capture and loopback-only image validation.

Never calls AI. Requires a separately installed FFmpeg executable with dshow.
Images and reports must stay inside artifacts/private/camera (Git ignored).
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_live import local_base_url, NoRedirect, request_json, VerificationError

PRIVATE_ROOT = ROOT / "artifacts" / "private" / "camera"


def capture(ffmpeg, device, consent_local, base_url):
    if consent_local is not True:
        raise VerificationError("--consent-local is required; point camera at non-sensitive test content")
    origin = local_base_url(base_url)
    executable = Path(ffmpeg).resolve()
    if not executable.is_file() or not device.strip() or len(device) > 160:
        raise VerificationError("valid FFmpeg executable and exact camera device name are required")
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = PRIVATE_ROOT / ("capture-" + stamp + ".jpg")
    command = [str(executable), "-hide_banner", "-loglevel", "error", "-f", "dshow",
               "-i", "video=" + device, "-an", "-vf", "select=eq(n\\,5)",
               "-frames:v", "1", "-q:v", "3", "-update", "1", "-n", str(output.relative_to(ROOT))]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                timeout=20, cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError("camera capture failed or timed out; no cloud request was made") from exc
    if result.returncode or not output.exists():
        raise VerificationError("camera did not return a still frame; no cloud request was made")
    raw = output.read_bytes()
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise VerificationError("captured image empty or larger than 2 MiB")
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    response = request_json(opener, origin + "/api/media/validate", 10, {
        "image_data": "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii"), "consent": True})
    if response.get("validated") is not True or response.get("scope") != "local_only" or response.get("cloud_sent") is not False:
        raise VerificationError("local-only validation contract was not met")
    record = {"source": "physical_camera_directshow", "device": device, "captured_at_utc": stamp,
              "local_image": output.name, "capture_sha256": hashlib.sha256(raw).hexdigest(),
              "local_validation": response, "real_ai_verified": False,
              "browser_get_user_media_verified": False}
    report = PRIVATE_ROOT / ("capture-" + stamp + ".json")
    report.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record, output, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--device", default="XiaoMi Webcam")
    parser.add_argument("--consent-local", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args(argv)
    try:
        result, output, report = capture(args.ffmpeg, args.device, args.consent_local, args.base_url)
    except VerificationError as exc:
        print("FAIL: " + str(exc))
        return 1
    print("PASS: physical camera -> local JPEG -> localhost validation; cloud_sent=false")
    print("Image: " + str(output))
    print("Metadata: " + str(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
