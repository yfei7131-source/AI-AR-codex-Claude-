"""Record explicit human judgments without treating unknown samples as passes.

python -m tools.acceptance.score --report artifacts/private/acceptance/latest_report.json --id T01 --score pass
Review the image, manifest's expected facts, and an opted-in recorded answer first.
Only local live API successes are eligible; injected/blocked samples cannot be scored.
"""
import argparse
import json
from tools.acceptance.run import private_report_path, summary
from tools.verify_live import VerificationError


def score_report(report, identifier, score):
    if score not in ("pass", "fail", "unknown"):
        raise ValueError("score must be pass, fail or unknown")
    item = next((item for item in report["results"] if item["id"] == identifier), None)
    if item is None:
        raise ValueError("sample ID is not in this report")
    if item["status"] != "success" or item["evidence_origin"] != "local_live_api":
        raise ValueError("only real live API successes can receive manual quality judgments")
    item["human_score"] = score
    report["summary"] = summary(report["results"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--score", choices=("pass", "fail", "unknown"), required=True)
    args = parser.parse_args(argv)
    try:
        path = private_report_path(args.report)
        report = json.loads(path.read_text(encoding="utf-8"))
        score_report(report, args.id, args.score)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, VerificationError):
        print("FAIL: report is unavailable or sample is not eligible for human scoring.")
        return 1
    print("Recorded explicit human score; all unreviewed samples remain unknown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
