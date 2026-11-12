"""Revalidate existing IDF build evidence without building or flashing a board.

Uses local artifact paths recorded by firmware/tools/build_idf.py. A match proves
that recorded source and binary bytes remain available; it is not a new build or
an electrical/physical capture test.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    firmware = root / "firmware"
    current_sources = {p.relative_to(firmware).as_posix()
                       for p in (firmware / "main").rglob("*") if p.is_file()}
    current_sources.update(p.name for p in firmware.glob("sdkconfig*.defaults"))
    current_sources.add("CMakeLists.txt")
    variants = ("unconfigured", "eye-v22", "evt0-r3", "evt0-r3-ap")
    results = []
    for variant in variants:
        manifest = firmware / "evidence" / f"build-{variant}.json"
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        recorded_sources = set(data["source_sha256"])
        mismatches = [name for name, expected in data["source_sha256"].items()
                      if not (firmware / name).is_file()
                      or sha256(firmware / name) != expected]
        binary = Path(data["binary_path"])
        binary_matches = (binary.is_file()
                          and binary.stat().st_size == data["binary_bytes"]
                          and sha256(binary) == data["binary_sha256"])
        log = firmware / "evidence" / f"idf-{variant}.txt"
        completed = "Project build complete." in log.read_text(encoding="utf-8-sig")
        result = {
            "variant": variant,
            "manifest": manifest.relative_to(root).as_posix(),
            "manifest_sha256": sha256(manifest),
            "source_files_checked": len(data["source_sha256"]),
            "source_file_set_matches": current_sources == recorded_sources,
            "unrecorded_current_sources": sorted(current_sources - recorded_sources),
            "source_hash_mismatches": mismatches,
            "binary_bytes": data["binary_bytes"],
            "binary_sha256": data["binary_sha256"],
            "local_binary_matches": binary_matches,
            "prior_build_log_completed": completed,
            "prior_build_log_sha256": sha256(log),
            "build_succeeded_recorded": data["build_succeeded"],
            "hardware_verified": data["hardware_verified"],
            "flashed": data["flashed"],
        }
        result["passed"] = (not mismatches and current_sources == recorded_sources
                            and binary_matches and completed
                            and data["build_succeeded"]
                            and not data["hardware_verified"] and not data["flashed"])
        results.append(result)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "revalidation_of_existing_build_evidence_no_rebuild_no_flash",
        "variants": results,
        "passed": all(item["passed"] for item in results),
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
