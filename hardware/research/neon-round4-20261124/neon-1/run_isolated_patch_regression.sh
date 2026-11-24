#!/usr/bin/env bash
# Isolated regression test for controlled_baseline_eco_h02_to_r7_v2.patch + catalog-plan.json consistency
# Runs in a detached temporary git worktree (never modifies any controlled branch).
set -euo pipefail

REPO_ROOT="${1:-$(git rev-parse --show-toplevel)}"
PATCH_FILE="${2:-$(pwd)/controlled_baseline_eco_h02_to_r7_v2.patch}"
BASE_REF="${3:-origin/hardware/kimi-evt1-h03-r7-20261123}"

TMP_WT="$(mktemp -d /tmp/evt1_h03_patch_regression.XXXXXX)"
cleanup() {
  git -C "$REPO_ROOT" worktree remove --force "$TMP_WT" >/dev/null 2>&1 || rm -rf "$TMP_WT"
}
trap cleanup EXIT

echo "[1/5] Creating isolated detached worktree from $BASE_REF at $TMP_WT ..."
git -C "$REPO_ROOT" worktree add --detach "$TMP_WT" "$BASE_REF"

echo "[2/5] Pre-checking CAD_TERMINALS.csv patch (strict + whitespace check) ..."
git -C "$TMP_WT" apply --check --ignore-whitespace "$PATCH_FILE"
git -C "$TMP_WT" apply --ignore-whitespace "$PATCH_FILE"

echo "[3/5] Applying companion catalog-plan.json ECO-09 (retire R10) & ECO-14 (U12 6-pin) update in isolated worktree ..."
python3 - "$TMP_WT/hardware/evt1-native-eda-20261118/h02-native/catalog-plan.json" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
before = len(data["records"])

# ECO-09: retire R10 (R_ESP_BOOT, captureUniqueId 41bc0941336b1513)
records = [
    r for r in data["records"]
    if not (r.get("board") == "M-MAIN-L" and r.get("cadReference") == "R10" and r.get("sourceReference") == "R_ESP_BOOT")
]
assert len(records) == before - 1, f"Expected removing exactly 1 R10 record, before={before}, after={len(records)}"

# ECO-14: align U12 (U12_ESD_USB, captureUniqueId b6112465b0588c80) to 6-pin TPD2E001DRYR
u12_hits = 0
for r in records:
    if r.get("board") == "M-MAIN-L" and r.get("cadReference") == "U12" and r.get("sourceReference") == "U12_ESD_USB":
        r["controlledValue"] = "U12_ESD_USB | TPD2E001DRYR (ECO-14)"
        r["controlledManufacturerId"] = "TPD2E001DRYR"
        r["kicadFootprint"] = "TI_DRY0006A_USON-6_1.45x1.0mm"
        r["footprintSourceStatus"] = "PASS"
        r["footprintPins"] = ["1", "2", "3", "4", "5", "6"]
        u12_hits += 1
assert u12_hits == 1, f"Expected updating exactly 1 U12 record, hits={u12_hits}"

data["records"] = records
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"catalog-plan.json updated in isolated worktree: records {before} -> {len(records)}, U12 updated={u12_hits}")
PY

echo "[4/5] Running original PR #55 run_controlled_sch_audit.py against real .epro2 archives ..."
python3 "$TMP_WT/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/tools/run_controlled_sch_audit.py"

echo "[5/5] Inspecting real regression output (controlled-sch-audit.json) ..."
python3 - "$TMP_WT/hardware/evt1-native-eda-20261118/h03-kimi-r7-20261123/verification/controlled-sch-audit.json" <<'PY'
import json, sys
from pathlib import Path

out = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("integrated", "independent", "r7Baseline"):
    sec = out.get(key, {})
    print(json.dumps({
        "archive": key,
        "status": sec.get("status"),
        "resolvedComponents": sec.get("resolvedComponents"),
        "unresolvedComponents": sec.get("unresolvedComponents"),
        "terminalCount": sec.get("terminalCount"),
        "controlledTerminalCount": sec.get("controlledTerminalCount"),
        "terminalDifference": sec.get("terminalDifference"),
        "explicitNCCount": sec.get("explicitNCCount"),
        "controlledNCCount": sec.get("controlledNCCount"),
        "ncDifference": sec.get("ncDifference"),
        "archiveRawNCMarkers": sec.get("archiveRawNCMarkers"),
    }, indent=2, ensure_ascii=False))
PY
