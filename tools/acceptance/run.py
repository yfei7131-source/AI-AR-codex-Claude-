"""Batch 10 vision + 10 OCR/translation fixtures against an explicitly live API.

Prepare: python -m tools.acceptance.generate
Run: python -m tools.acceptance.run --consent-upload
Opt in to saving model text: add --record-answers (ignored private report only).
No cloud key is read by this client. A passing API contract is not an accuracy score.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from http.client import HTTPException
import json
import math
from pathlib import Path
import re
import socket
import time
from urllib import error, request
from uuid import uuid4

from tools.verify_live import local_base_url, image_data_url, NoRedirect, VerificationError, MAX_RESPONSE_BYTES
from tools.acceptance.generate import load_manifest, DEFAULT_IMAGE_DIR, PRIVATE_ROOT

STATUSES = ("blocked", "success", "failed", "timeout", "cancelled", "disconnected")


class TransportFailure(Exception):
    """Only safe codes are retained; upstream error bodies are never logged."""
    def __init__(self, status, code):
        super().__init__(code)
        self.status = status
        self.code = code


def classified(code, status=None):
    if code in ("AI_TIMEOUT", "UPLOAD_TIMEOUT") or status in (408, 504):
        return "timeout"
    if code in ("REQUEST_SUPERSEDED", "REQUEST_CANCELLED"):
        return "cancelled"
    if code in ("AI_UNREACHABLE", "CONNECTION_LOST"):
        return "disconnected"
    return "failed"


class LocalTransport:
    def __init__(self, origin, timeout):
        self.origin, self.timeout = origin, timeout
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())

    def call(self, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(self.origin + "/api/" + path, data=body,
                              headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=min(self.timeout, 10) if path == "health" else self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            try:
                raw = exc.read(MAX_RESPONSE_BYTES + 1)
                parsed = json.loads(raw) if len(raw) <= MAX_RESPONSE_BYTES else {}
                code = parsed.get("code") if isinstance(parsed, dict) else None
            except (ValueError, OSError, HTTPException):
                code = None
            finally:
                exc.close()
            code = code if isinstance(code, str) and re.fullmatch(r"[A-Z_]{1,50}", code) else "HTTP_ERROR"
            raise TransportFailure(classified(code, exc.code), code) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TransportFailure("timeout", "SOCKET_TIMEOUT") from exc
        except error.URLError as exc:
            is_timeout = isinstance(exc.reason, (TimeoutError, socket.timeout))
            raise TransportFailure("timeout" if is_timeout else "disconnected",
                                   "SOCKET_TIMEOUT" if is_timeout else "CONNECTION_LOST") from exc
        except (OSError, HTTPException) as exc:
            raise TransportFailure("disconnected", "CONNECTION_LOST") from exc
        except VerificationError as exc:
            raise TransportFailure("failed", "REDIRECT_DENIED") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TransportFailure("failed", "RESPONSE_TOO_LARGE")
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise TransportFailure("failed", "INVALID_JSON") from exc
        if not isinstance(parsed, dict):
            raise TransportFailure("failed", "INVALID_RESPONSE")
        if "error" in parsed:
            code = parsed.get("code", "API_ERROR")
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z_]{1,50}", code):
                code = "API_ERROR"
            raise TransportFailure(classified(code), code)
        return parsed


def validate_live_result(result, kind, target_language="zh-CN"):
    if (result.get("provider") != "openai" or result.get("mode") != "live"
            or result.get("simulated") is not False):
        raise TransportFailure("failed", "DEMO_OR_UNMARKED_RESPONSE")
    answer, hud, identifier = result.get("answer"), result.get("hud"), result.get("request_id")
    lines = hud.get("lines") if isinstance(hud, dict) else None
    if (not isinstance(answer, str) or not answer.strip() or not isinstance(lines, list) or not lines
            or any(not isinstance(line, str) or not line.strip() for line in lines)
            or not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", identifier)):
        raise TransportFailure("failed", "INVALID_HUD_CONTRACT")
    if kind == "translate":
        ocr = result.get("ocr")
        if (not isinstance(ocr, dict) or not isinstance(ocr.get("original_text"), str)
                or not isinstance(ocr.get("translated_text"), str)
                or ocr.get("source_language") not in ("zh-CN", "en", "mixed", "unknown")
                or target_language not in ("zh-CN", "en")
                or ocr.get("target_language") != target_language or not isinstance(ocr.get("uncertain"), bool)):
            raise TransportFailure("failed", "INVALID_OCR_CONTRACT")


def summary(results):
    counts = {status: 0 for status in STATUSES}
    counts.update(Counter(item["status"] for item in results))
    reviewed = [r for r in results if r["status"] == "success" and r["evidence_origin"] == "local_live_api"
                and r.get("human_score") in ("pass", "fail")]
    passed = sum(r["human_score"] == "pass" for r in reviewed)
    return {"counts": counts, "reviewed_quality_samples": len(reviewed),
            "quality_passes": passed,
            "quality_accuracy_on_reviewed_samples": passed / len(reviewed) if reviewed else None,
            "quality_unknown_samples": sum(r.get("human_score", "unknown") == "unknown" for r in results),
            "note": "success counts API/HUD contracts only; quality requires manual review. Synthetic fixtures do not measure natural-scene accuracy."}


def run_suite(consent_upload=False, *, base_url="http://127.0.0.1:8765", image_dir=DEFAULT_IMAGE_DIR,
              timeout=95, record_answers=False, manifest=None, transport=None):
    """Injected transports exist for tests only and can never count as cloud evidence."""
    origin = local_base_url(base_url)
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 300:
        raise VerificationError("timeout must be 1 to 300 seconds")
    manifest = manifest or load_manifest()
    injected = transport is not None
    client = transport if injected else LocalTransport(origin, timeout)
    evidence = "injected_test_transport" if injected else "local_live_api"
    results = [{"id": s["id"], "kind": s["kind"], "source": "synthetic_fixture",
                "evidence_origin": evidence, "status": "blocked", "code": "NOT_RUN",
                "human_score": "unknown", "cloud_response_received": False} for s in manifest["samples"]]
    for sample, result in zip(manifest["samples"], results):
        if sample["kind"] == "translate":
            result["target_language"] = sample["target_language"]
    report = {"suite": "sprint02-20-synthetic-fixtures", "manifest_version": manifest["version"],
              "created_at_utc": datetime.now(timezone.utc).isoformat(), "source": "synthetic_fixture",
              "evidence_origin": evidence, "answers_recorded": bool(record_answers),
              "limitation": manifest["limitation"], "results": results}
    blocked_code = None
    if consent_upload is not True:
        blocked_code = "UPLOAD_CONSENT_REQUIRED"
    else:
        try:
            health = client.call("health")
            if health.get("ready") is not True or health.get("provider") != "openai" or health.get("mode") != "live":
                blocked_code = "LIVE_AI_NOT_READY"
        except TransportFailure as exc:
            blocked_code = "HEALTH_" + exc.status.upper()
        except KeyboardInterrupt:
            blocked_code = "RUN_CANCELLED_BEFORE_UPLOAD"
    if blocked_code:
        for result in results:
            result["code"] = blocked_code
        report["summary"] = summary(results)
        return report
    for index, (sample, item) in enumerate(zip(manifest["samples"], results)):
        client_id = "acceptance_" + uuid4().hex
        started = time.monotonic()
        try:
            image = image_data_url(Path(image_dir) / sample["image"])
            payload = {"mode": "live", "kind": sample["kind"], "question": sample["question"],
                       "image_data": image, "consent": True, "client_request_id": client_id}
            if sample["kind"] == "translate":
                payload.update({"output_format": "ocr", "source_language": sample["source_language"],
                                "target_language": sample["target_language"]})
            response = client.call("ask", payload)
            validate_live_result(response, sample["kind"], sample.get("target_language", "zh-CN"))
            item.update({"status": "success", "code": "LIVE_CONTRACT_OK" if not injected else "INJECTED_CONTRACT_OK",
                         "request_id": response["request_id"], "cloud_response_received": not injected})
            if sample["kind"] == "translate":
                ocr = response["ocr"]
                normalized = " ".join(ocr["original_text"].casefold().split())
                item["ocr_expected_lines_present"] = [" ".join(text.casefold().split()) in normalized
                                                      for text in sample["expected"]["text"]]
                item["ocr_uncertain"] = ocr["uncertain"]
            if record_answers:
                item["answer"] = response["answer"]
                item["hud"] = response["hud"]
                if sample["kind"] == "translate":
                    item["ocr"] = response["ocr"]
        except VerificationError:
            item.update({"status": "failed", "code": "LOCAL_IMAGE_INVALID_OR_MISSING"})
        except TransportFailure as exc:
            item.update({"status": exc.status, "code": exc.code})
        except KeyboardInterrupt:
            item.update({"status": "cancelled", "code": "USER_CANCELLED"})
            try:
                client.call("requests/cancel", {"client_request_id": client_id})
                item["local_cancel_requested"] = True
            except (TransportFailure, KeyboardInterrupt):
                item["local_cancel_requested"] = False
            item["cancellation_note"] = "Stopping local waiting cannot retract a cloud request or guarantee billing cancellation."
            for remaining in results[index + 1:]:
                remaining["code"] = "RUN_CANCELLED"
            break
        finally:
            item["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["summary"] = summary(results)
    return report


def private_report_path(path):
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(PRIVATE_ROOT.resolve())
    except ValueError as exc:
        raise VerificationError("reports must remain under ignored artifacts/private/acceptance") from exc
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--consent-upload", action="store_true")
    parser.add_argument("--record-answers", action="store_true", help="explicitly save real model text in the ignored report")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=float, default=95)
    parser.add_argument("--report", type=Path, default=PRIVATE_ROOT / "latest_report.json")
    args = parser.parse_args(argv)
    try:
        path = private_report_path(args.report)
        report = run_suite(args.consent_upload, base_url=args.base_url, timeout=args.timeout,
                           record_answers=args.record_answers)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive per-run evidence; prevent silent overwrites of earlier reviewed runs.
        if path.exists():
            path = path.with_name(path.stem + "_" + uuid4().hex[:8] + path.suffix)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (VerificationError, OSError, ValueError) as exc:
        print("FAIL: acceptance preparation/configuration failed; no result was claimed.")
        return 1
    print(json.dumps({"counts": report["summary"]["counts"], "quality": "unknown until manually reviewed",
                      "evidence_origin": report["evidence_origin"],
                      "report": str(path.relative_to(PRIVATE_ROOT.parents[2]))}, ensure_ascii=False))
    return 0 if report["summary"]["counts"]["success"] == 20 else 2


if __name__ == "__main__":
    raise SystemExit(main())
