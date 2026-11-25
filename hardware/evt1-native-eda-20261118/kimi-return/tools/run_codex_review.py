#!/usr/bin/env python3
"""Run Codex's review tool with external output and preserve its real verdict."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
TOOL = ROOT.parent / "tools" / "review_kimi_return.py"
KICAD = REPO / ".tools" / "kicad" / "unpacked" / "bin" / "kicad-cli.exe"
EXTERNAL = REPO / ".tools" / "review-kimi-return"
DELIVERY = ROOT / "evidence" / "codex-review"


def main():
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    DELIVERY.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(TOOL), str(ROOT), "--output", str(EXTERNAL),
               "--kicad-cli", str(KICAD)]
    completed = subprocess.run(command, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=300)
    transcript = ("$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr
                  + f"\nACTUAL_EXIT_CODE={completed.returncode}\n")
    (DELIVERY / "review-command.log").write_text(transcript, encoding="utf-8")
    source = EXTERNAL / "KIMI_NATIVE_REVIEW.json"
    if source.is_file():
        shutil.copyfile(source, DELIVERY / "KIMI_NATIVE_REVIEW.json")
        review = json.loads(source.read_text(encoding="utf-8"))
        print(json.dumps({"actualExitCode": completed.returncode,
                          "nativeReview": review.get("native_review"),
                          "manufacturing": review.get("manufacturing")}, indent=2))
    else:
        print(f"Review output missing; actual exit {completed.returncode}", file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
