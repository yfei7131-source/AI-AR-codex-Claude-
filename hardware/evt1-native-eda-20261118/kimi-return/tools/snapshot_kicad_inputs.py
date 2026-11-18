#!/usr/bin/env python3
"""Snapshot every supplied KiCad source and audit its controlled terminal mapping."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import sys

HERE = Path(__file__).resolve()
PACKAGE = HERE.parents[2]
OUT = HERE.parents[1] / "evidence"
sys.path.insert(0, str(PACKAGE / "tools"))
import verify_kicad  # noqa: E402


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def s_expression_balance(path):
    text = path.read_text(encoding="utf-8")
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return {"balanced": False, "reason": "unexpected closing parenthesis"}
    return {"balanced": depth == 0 and not quoted and not escaped,
            "final_depth": depth, "unterminated_string": quoted}


def main():
    source_rows = rows(PACKAGE / "Inputs/effective_netlist.csv")
    bom_rows = rows(PACKAGE / "Inputs/effective_bom.csv")
    footprint_rows = rows(PACKAGE / "FOOTPRINT_MAP.csv")
    cad_rows = rows(PACKAGE / "kicad/CAD_TERMINALS.csv")
    files = []
    for path in sorted((PACKAGE / "kicad").rglob("*")):
        if not path.is_file():
            continue
        item = {"path": path.relative_to(PACKAGE).as_posix(), "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix in {".kicad_sch", ".kicad_sym", ".kicad_mod"} or path.name in {"fp-lib-table", "sym-lib-table"}:
            item["s_expression"] = s_expression_balance(path)
        elif path.suffix in {".kicad_pro", ".kicad_prl"}:
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
                item["json_parse"] = "PASS"
            except (ValueError, UnicodeError) as exc:
                item["json_parse"] = f"FAIL: {exc}"
        files.append(item)
    errors = []
    try:
        verify_kicad.audit_manifest(cad_rows)
        terminal_manifest = "PASS"
    except Exception as exc:
        terminal_manifest = f"FAIL: {exc}"
        errors.append(str(exc))
    if any(not item.get("s_expression", {}).get("balanced", True) for item in files):
        errors.append("unbalanced KiCad S-expression")
    if any(str(item.get("json_parse", "PASS")).startswith("FAIL") for item in files):
        errors.append("invalid KiCad project JSON")
    identities = [(row["Board"], row["Source_RefDes"], row["Pin"]) for row in cad_rows]
    expected = {(row["Board"], row["RefDes"], row["Pin"]) for row in source_rows if row["Board"] in verify_kicad.BOARD_PROJECTS}
    if len(identities) != len(set(identities)) or set(identities) != expected:
        errors.append("CAD terminal identity coverage differs from effective inputs")
    result = {
        "baseline_commit": "cec8deab978c0a6e04bb2293291dd4b5f13ac43a",
        "scope": "Source snapshots, syntax checks and deterministic terminal-map audit; not native KiCad ERC or EasyEDA verification.",
        "source_terminal_count": len(source_rows),
        "bom_row_count": len(bom_rows),
        "footprint_row_count": len(footprint_rows),
        "footprint_status_counts": dict(Counter(row["Status"] for row in footprint_rows)),
        "cad_terminal_count": len(cad_rows),
        "cad_local_state_counts": dict(Counter(row["Local_State"] for row in cad_rows)),
        "board_terminal_counts": dict(Counter(row["Board"] for row in cad_rows)),
        "terminal_manifest": terminal_manifest,
        "file_count": len(files),
        "files": files,
        "errors": errors,
        "status": "FAIL" if errors else "PASS"
    }
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / "kicad-source-audit.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, ensure_ascii=False, indent=2))
    print(f"Snapshot: {destination}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
