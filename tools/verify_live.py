"""Opt-in live API -> browser HUD contract check; never a hardware/quality test.

Example (from the project root):
    python tools/verify_live.py --image C:/test/label.png --consent-upload --kind translate

No API key, image, or model answer is written to output or disk by this tool.
The image is sent to the local server and, in live mode, its AI provider.
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import math
from pathlib import Path
import re
import time
from urllib import error, request
from urllib.parse import urlsplit


MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


class VerificationError(Exception):
    """A failure that is safe to print without exposing request/response data."""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a personal image outside the selected local service.
        raise VerificationError("server redirects are prohibited")


def local_base_url(value: str) -> str:
    """Allow literal loopback hosts only; canonicalize localhost without DNS."""
    try:
        url = urlsplit(value)
        if (url.scheme not in ("http", "https") or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError
        host = url.hostname
        if host == "localhost":
            host = "127.0.0.1"
        address = ipaddress.ip_address(host or "")
        if not address.is_loopback:
            raise ValueError
        port = url.port
        if port == 0:
            raise ValueError
    except ValueError as exc:
        raise VerificationError("base URL must be an HTTP(S) loopback origin") from exc
    host_text = f"[{host}]" if address.version == 6 else host
    return f"{url.scheme}://{host_text}" + (f":{port}" if port else "")


def image_data_url(path: Path) -> str:
    try:
        # Bounded read also handles a file that grows after its stat.
        with path.open("rb") as stream:
            raw = stream.read(MAX_IMAGE_BYTES + 1)
    except OSError as exc:
        raise VerificationError("cannot read the selected image file") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise VerificationError("image must contain 1 byte to 2 MiB")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    else:
        raise VerificationError("only JPEG or PNG images are allowed")
    # Full decoding/validation is the server's responsibility.
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def request_json(opener, url: str, timeout: float, payload=None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise VerificationError("server response exceeded the size limit")
            result = json.loads(raw)
    except error.HTTPError as exc:
        exc.close()
        raise VerificationError(f"local server returned HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise VerificationError("local server connection failed or timed out") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise VerificationError("local server returned invalid JSON") from exc
    if not isinstance(result, dict) or "error" in result:
        raise VerificationError("local server returned an error or invalid response")
    return result


def verify(base_url: str, image: Path, consent_upload: bool, kind="vision",
           question="请简述画面中可以确认的内容。", timeout=95.0) -> dict:
    if consent_upload is not True:
        raise VerificationError("--consent-upload is required before sending an image to AI")
    if kind not in ("vision", "translate"):
        raise VerificationError("kind must be vision or translate")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise VerificationError("question must contain 1 to 500 characters")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 300:
        raise VerificationError("timeout must be 1 to 300 seconds")
    origin = local_base_url(base_url)
    # No proxy is needed for loopback; disabling it avoids sending media to an
    # environment-configured proxy.
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    health = request_json(opener, origin + "/api/health", min(timeout, 10))
    if health.get("ready") is not True or health.get("provider") != "openai" or health.get("mode") != "live":
        raise VerificationError("live OpenAI mode is not ready; configure the server, never fall back to demo")
    picture = image_data_url(image)
    started = time.monotonic()
    result = request_json(opener, origin + "/api/ask", timeout, {
        "mode": "live", "kind": kind, "question": question,
        "image_data": picture, "consent": True,
    })
    elapsed = time.monotonic() - started
    if result.get("mode") != "live" or result.get("simulated") is not False or result.get("provider") != "openai":
        raise VerificationError("response was not explicitly marked as real OpenAI output")
    hud = result.get("hud")
    answer = result.get("answer")
    lines = hud.get("lines") if isinstance(hud, dict) else None
    if (not isinstance(answer, str) or not answer.strip() or not isinstance(lines, list)
            or not lines or any(not isinstance(line, str) or not line.strip() for line in lines)):
        raise VerificationError("response did not include a nonempty answer and HUD text")
    request_id = result.get("request_id")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", request_id):
        raise VerificationError("response did not include a valid request ID")
    # Return only safe metadata, never answer text or image data.
    return {"request_id": request_id, "elapsed_seconds": round(elapsed, 3)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, type=Path, help="a local JPEG/PNG, maximum 2 MiB")
    parser.add_argument("--consent-upload", action="store_true", help="allow this image to be sent to the local server and its AI provider")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="loopback HTTP(S) origin only")
    parser.add_argument("--kind", choices=("vision", "translate"), default="vision")
    parser.add_argument("--question", default="请简述画面中可以确认的内容。")
    parser.add_argument("--timeout", type=float, default=95, help="AI request timeout in seconds (1-300, default 95)")
    args = parser.parse_args(argv)
    try:
        result = verify(args.base_url, args.image, args.consent_upload, args.kind, args.question, args.timeout)
    except VerificationError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: live API -> HUD contract; request_id={result['request_id']}; elapsed_seconds={result['elapsed_seconds']}")
    print("This verifies the API contract, not AI accuracy, camera capture, or an optical/hardware display.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
