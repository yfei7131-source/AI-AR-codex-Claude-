#!/usr/bin/env python3
"""Flag non-atomic controlled MPN text before attempting native BOM writes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RETURN = ROOT / "hardware/evt1-native-eda-20261118/kimi-h02-return"
plan = json.loads((RETURN / "repair-plan.json").read_text(encoding="utf-8"))
flagged = []
for record in plan["records"]:
    mpn = record["controlled"]["mpn"]
    if mpn and (len(mpn) > 80 or " + " in mpn or "\n" in mpn):
        flagged.append({"board": record["board"], "cadReference": record["cadReference"],
                        "pageUuid": record["pageUuid"], "primitiveId": record["primitiveId"],
                        "uniqueId": record["uniqueId"], "length": len(mpn), "controlledMpn": mpn,
                        "reason": "Controlled BOM MPN cell contains a multi-part/design-note expression, not an atomic orderable MPN."})
report = {"status": "REVIEW_REQUIRED" if flagged else "PASS", "flaggedCount": len(flagged), "records": flagged}
path = RETURN / "field-repair/controlled-mpn-review.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"flaggedCount": len(flagged), "items": [[r["board"], r["cadReference"], r["length"]] for r in flagged]}, ensure_ascii=False, indent=2))
