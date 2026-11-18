#!/usr/bin/env python3
"""Resolve exact EasyEDA device identities; never equate identity with land approval."""
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parent
OUT = ROOT / "evidence" / "library-identity"
CLI = Path.home() / ".local/bin/easyeda.exe"
PROJECT = "cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662"


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def usable_mpn(value):
    return (len(value) <= 80 and "TBD" not in value and " + " not in value
            and " OR " not in value and not value.startswith("0201 ")
            and not value.startswith("Nordic ") and not value.startswith("5x ")
            and not re.match(r"^\d+(?:\.\d+)?(?:[kKmMuUnp]|\s)", value))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bom = list(csv.DictReader((PACKAGE / "Inputs/effective_bom.csv").open(encoding="utf-8-sig", newline="")))
    mpns = sorted({row["MPN"] for row in bom if usable_mpn(row["MPN"])})
    audit = []
    for index, mpn in enumerate(mpns, 1):
        token = hashlib.sha256(mpn.encode()).hexdigest()[:12]
        target = OUT / f"{index:02d}-{token}-search.json"
        if target.exists():
            response = json.loads(target.read_text(encoding="utf-8"))
        else:
            command = [str(CLI), "lib", "search", "--query", mpn, "--limit", "20", "--project", PROJECT]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            (OUT / f"{index:02d}-{token}-search.log").write_text("$ " + " ".join(command) + "\n" + result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                audit.append({"mpn": mpn, "status": "UNVERIFIED", "reason": "library query failed"})
                print(f"{index}/{len(mpns)} QUERY-FAIL {mpn}", flush=True)
                continue
            response = json.loads(result.stdout)
            target.write_text(result.stdout, encoding="utf-8")
        hits = response.get("result", {}).get("components", [])
        exact = [row for row in hits if normalized(mpn) in {normalized(row.get("manufacturerId", "")), normalized(row.get("name", ""))}]
        candidates = []
        for row in exact:
            candidates.append({key: row.get(key) for key in ("uuid", "libraryUuid", "name", "manufacturer", "manufacturerId", "lcsc", "footprintName")})
        status = "EXACT_IDENTITY_ONLY" if len(candidates) == 1 else ("BLOCKED" if not candidates else "UNVERIFIED")
        reason = {"EXACT_IDENTITY_ONLY": "Unique exact MPN record; physical pins and copper pads not yet checked.",
                  "BLOCKED": "No exact MPN match in returned library records.",
                  "UNVERIFIED": "Multiple exact MPN records; no default-first selection allowed."}[status]
        audit.append({"mpn": mpn, "status": status, "reason": reason, "returnedCount": len(hits), "exactCandidates": candidates})
        print(f"{index}/{len(mpns)} {status} {mpn}: {len(candidates)} exact / {len(hits)} returned", flush=True)
        (OUT / "identity-audit.json").write_text(json.dumps({
            "scope": "Exact library identity only. Symbol-pin, footprint-pad, supplier, mask, assembly and fit remain separate.",
            "projectUuid": PROJECT, "mpnsQueried": len(mpns), "parts": audit}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
