"""Audit R3 requirements and board allocation without regenerating ECAD files.

Exit 0 means the cross-document/source contract agrees. Open physical gates are
reported separately and always keep manufacturing_release and hardware_verified false.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESIGN = HERE.parent
REPO = HERE.parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    feature_path = REPO / "docs/FEATURES_F01_F22.md"
    trace_path = HERE / "F01_F22_trace.csv"
    profile_path = REPO / "firmware/main/board.c"
    board_h = REPO / "firmware/main/board.h"
    pinmap_path = DESIGN / "H02/evt0_core/pinmap_hw.csv"
    compat_path = DESIGN / "tools/check_fw_compat.py"
    ecad_path = DESIGN / "H02/evt0_core/gen/design.py"
    gates_path = HERE / "RELEASE_GATES.csv"

    authoritative = re.findall(r"^\| (F\d{2}) \| ([^|]+) \| (P0|P1|R) \|", feature_path.read_text(encoding="utf-8"), re.M)
    expected_ids = [f"F{n:02}" for n in range(1, 23)]
    require([row[0] for row in authoritative] == expected_ids, "authoritative F01-F22 IDs changed")
    traced = rows(trace_path)
    require([row["id"] for row in traced] == expected_ids, "trace IDs missing, duplicated or out of order")
    for (ident, label, priority), row in zip(authoritative, traced):
        require(row["feature"] == label.strip() and row["priority"] == priority, f"{ident}: requirement changed")
        require(all(row.get(key) for key in ("allocation", "interface", "source", "gate", "acceptance_gap")), f"{ident}: incomplete allocation")
        require((REPO / row["source"]).is_file(), f"{ident}: missing source {row['source']}")
    priorities = dict(Counter(row["priority"] for row in traced))
    require(priorities == {"P0": 16, "P1": 5, "R": 1}, "frozen priority counts differ")
    require(traced[20]["priority"] == "R", "F21 must remain research")

    compat = load_module("r3_compat_readonly", compat_path)
    pins = compat.parse_profile(REPO / "firmware/main", compat.DEFAULT)
    hw_rows = rows(pinmap_path)
    hw = {int(row["gpio"]): row["hw_net"] for row in hw_rows}
    require(len(hw) == len(hw_rows), "duplicate hardware GPIO")
    active = {field: gpio for field, gpio in pins.items() if gpio >= 0}
    require(len(active) == 22 and len(set(active.values())) == 22, "R3 needs 22 unique declared GPIOs")
    for field, gpio in active.items():
        require(hw.get(gpio) == compat.FIELD_NET[field], f"GPIO{gpio}: {field} differs from hardware")
    require(not ({35, 36, 37, 45, 46} & set(active.values())), "PSRAM/display strap reserved pins allocated")
    for macro in ("CONFIG_GL_BOARD_EYE_V22", "CONFIG_GL_BOARD_S3_CARRIER_A", compat.DEFAULT):
        compat.parse_profile(REPO / "firmware/main", macro)  # requires privacy=false
    source = compat.source(profile_path)
    default_branch = source.split("#else", 1)[1]
    require(re.search(r'"board_unconfigured"\s*,\s*false\s*,\s*false', default_branch), "default profile is not locked")

    ecad = load_module("r3_ecad_readonly", ecad_path)
    parts = {part["ref"]: part for part in ecad.P}
    require(len(parts) == len(ecad.P), "duplicate ECAD reference")
    for ref in ("J3", "J4", "R5", "R16", "R17", "R18", "R30", "R31", "R33", "R34", "R36"):
        require(parts.get(ref, {}).get("dnp") is True, f"{ref}: required initial DNP gate missing")
    require(not ({"JP2", "R32", "R8"} & set(parts)), "legacy camera override or fake NTC fitted")
    require(parts["J7"]["nets"] == {"1": "GND", "2": "AUD_UART_TX", "3": "AUD_UART_RX"}, "J7 is not isolated signal-only UART")
    require(parts["R33"]["nets"] == {"1": "U0TXD", "2": "AUD_UART_TX"}, "audio TX bridge mismatch")
    require(parts["R34"]["nets"] == {"1": "U0RXD", "2": "AUD_UART_RX"}, "audio RX bridge mismatch")
    require(parts["R6"]["nets"] == {"1": "CHG_TD", "2": "GND"}, "BQ24072 termination control changed")
    require(parts["R35"]["nets"] == {"1": "VBUS", "2": "CHG_CE_N"}, "default charge inhibit changed")
    gate_rows = rows(gates_path)
    require(len({row["id"] for row in gate_rows}) == len(gate_rows) and len(gate_rows) >= 8, "release gates missing or duplicated")
    require(all(row["status"] == "BLOCKED" and row["required_evidence"] for row in gate_rows), "open gate state/evidence missing")
    icr = (HERE / "ICR_to_Codex.md").read_text(encoding="utf-8")
    require(re.findall(r"^\| ICR-(\d{2}) \|", icr, re.M) == [f"{n:02}" for n in range(1, 13)], "ICR-01..12 incomplete")

    inputs = [feature_path, trace_path, profile_path, board_h, pinmap_path, compat_path, ecad_path, gates_path, Path(__file__)]
    return {
        "scope": "R3 H01 source and requirements contract; no ERC/DRC or physical hardware validation",
        "contract_passed": True,
        "feature_count": len(traced),
        "priority_counts": priorities,
        "gpio_assignments_matched": len(active),
        "locked_profiles": ["unconfigured", "eye-v22", "s3-carrier-a", "evt0-r3"],
        "ecad_declared_symbol_count": len(parts),
        "physical_component_count": sum(part["sym"] != "PWR_FLAG" for part in parts.values()),
        "open_release_gates": [row["id"] for row in gate_rows],
        "manufacturing_release": False,
        "hardware_verified": False,
        "source_sha256": {path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = audit()
    except (OSError, ValueError, KeyError, AttributeError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
