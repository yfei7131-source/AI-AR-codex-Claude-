"""Replay the unchanged PR47 V4 blind-via audit on current native R4 captures."""

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from u11.audit_r3_u11 import load

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "h03-v4-dfm-u11-2n2-route"))

from independent_hdi_dfm_auditor_v4 import audit_board_v4  # noqa: E402


def replay(out_dir):
    archive_path, = (HERE / "native").glob("*.epro2")
    archive = SimpleNamespace(
        path=archive_path,
        documents={key: SimpleNamespace(records=rows)
                   for key, rows in load(archive_path).documents.items()},
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for index, suffix in enumerate(("after", "restore", "restore"), 1):
        board = f"PCB{index}"
        dump = HERE / "verification" / f"pcb{index}-{suffix}-copper.json"
        result = audit_board_v4(board, archive, dump, blind_csv=out_dir / f"{board}-blind-vias.csv")
        results[board] = result["v4_official_jlcpcb_hdi_audit"]
    counts = [item["total_blind_vias"] for item in results.values()]
    if counts != [61, 40, 40]:
        raise ValueError(f"Unexpected blind via distribution: {counts}")
    (out_dir / "report.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    for board, item in replay(parser.parse_args().out_dir).items():
        print(board, item["total_blind_vias"], json.dumps(item["violations"], sort_keys=True))
