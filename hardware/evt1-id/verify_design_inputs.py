"""Validate design-input consistency, never certify physical hardware or CAD."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=True)
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Source, target allocation and historical evidence consistency only",
              "design_input_contract_passed": False, "cad_ready": False,
              "hardware_tested": False, "manufacturing_release": False}
    used = []
    try:
        provenance = read_json(HERE / "references/provenance.json")
        for name, record in provenance["files"].items():
            path = HERE / name
            require(digest(path) == record["sha256"], "Input bytes changed: " + name)
            used.append(path)
        require(provenance["master_image_confirmed_by_user"] is True, "Mother image unconfirmed")
        budget = read_json(HERE / "MASS_BUDGET.json")
        allocated = sum(r["allocated_g"] for r in budget["items"])
        require(allocated == budget["mass_engineering_target_g"] == 50, "50 g allocation mismatch")
        require((budget["mass_challenge_g"], budget["mass_warning_g"]) == (40, 55), "Mass target changed")
        require(all(r["measured_g"] is None for r in budget["items"]), "Unreviewed measured masses")
        require(budget["mass_verified"] is False, "Unverified mass marked verified")
        assembly = read_json(HERE / "ASSEMBLY_INPUTS.json")
        require(all(assembly[k] is False for k in ("assembly_generated", "collision_verified",
                    "optical_path_verified", "manufacturing_release")), "Unverified CAD claim")
        require(len(assembly["parts"]) == 15, "Missing assembly modules")
        require(all(r["controlled_step"] is None and r["envelope_mm"] is None
                    for r in assembly["parts"]), "Unreviewed CAD geometry")
        interfaces = rows(HERE / "INTERFACES.csv")
        require(len(interfaces) == len({r["id"] for r in interfaces}) == 23, "Interface set changed")
        require(all(r["status"] == "BLOCKED_TBD" for r in interfaces), "Interface gate released")
        features = {f"F{i:02}" for i in range(1, 23)}
        architecture = (HERE / "HW_ARCHITECTURE.md").read_text(encoding="utf-8")
        require(features <= set(re.findall(r"F\d{2}", architecture)), "Missing feature allocation")
        require(features == set(re.findall(r"\| (F\d{2}) \|", (REPO / "docs/FEATURES_F01_F22.md")
                                          .read_text(encoding="utf-8"))), "Feature authority changed")
        power = rows(HERE / "POWER_BUDGET.csv")
        for row in power:
            for key in ("avg_power_W", "peak_power_W", "usable_energy_Wh", "capacity_mAh"):
                require(row[key] in ("TBD", "NA"), "Unqualified power value: " + row["ID"])
        r4 = REPO / "hardware/evt0-r4-review"
        before = read_json(r4 / "evidence/r3-source-before.json")["r3_file_sha256"]
        for name, expected in before.items():
            require(digest(REPO / "hardware/evt0-r3" / name) == expected, "R3 changed: " + name)
        summary = read_json(r4 / "evidence/pcb-verification.json")
        core = r4 / "H02/evt0_core"
        for name, expected in summary["inputs_sha256"].items():
            require(digest(core / name.replace("\\", "/")) == expected, "Stale R4 evidence: " + name)
        drc = read_json(core / "evidence/pcb-drc-final.json")
        require(len(drc["violations"]) == 15 and len(drc["unconnected_items"]) == 58
                and not drc["schematic_parity"], "R4 native result changed")
        require(summary["manufacturing_release"] is False and summary["script_exit_code"] == 5,
                "DRC failure concealed")
        board_text = (REPO / "firmware/main/board.c").read_text(encoding="utf-8")
        profiles = re.findall(r'static const gl_board board=\{"[^"]+",(true|false),(true|false)', board_text)
        require(len(profiles) == 4 and all(p[1] == "false" for p in profiles), "Privacy profile unlocked")
        result.update(design_input_contract_passed=True, references_matched=len(provenance["files"]),
                      master_image="ZY_AIAR_Glasses_ID_MASTER.png", mass_allocation_g=allocated,
                      mass_measured_g=None, interfaces_blocked=len(interfaces),
                      cad_modules_missing=len(assembly["parts"]), feature_count=len(features),
                      power_records=len(power), r3_files_unchanged=len(before),
                      r4_native_drc_exit=5, r4_rule_violations=15, r4_unconnected_items=58)
        used += [HERE / name for name in ("MASS_BUDGET.json", "ASSEMBLY_INPUTS.json", "INTERFACES.csv",
                 "POWER_BUDGET.csv", "HW_ARCHITECTURE.md", "OPTICS_SELECTION.md", "verify_design_inputs.py")]
        result["inputs_sha256"] = {str(p.relative_to(REPO)).replace("\\", "/"): digest(p) for p in used}
    except (ValueError, KeyError, OSError) as exc:
        result["error"] = str(exc)
    (evidence / "design-input-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                                                     encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["design_input_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
