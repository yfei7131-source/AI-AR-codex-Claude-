"""Compare the inherited independent V4 HDI and copper DFM audit on two native checkpoints."""

from __future__ import annotations

import argparse
import copy
import csv
import importlib.util
import json
import math
from pathlib import Path

import batch_gate as gate

native = gate.native
AUDITOR = "h03-v4-dfm-u11-2n2-route/independent_hdi_dfm_auditor_v4.py"
RISK = {"TRUE_PHYSICAL_VIOLATION", "REAL_DFM_VIA_TOUCHES_SMD_PAD", "RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK"}


def load_auditor():
    for parent in Path(__file__).resolve().parents:
        options = (parent / AUDITOR, parent / "evt1-h03-r11-master/hardware/evt1-native-eda-20261118" / AUDITOR)
        path = next((p for p in options if p.is_file()), None)
        if path:
            break
    else:
        raise ImportError("Inherited V4 independent auditor is absent")
    spec = importlib.util.spec_from_file_location("inherited_dfm", path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    from prepare_hierarchy import Record

    original = Record.__init__

    def read_record(self, line):
        header, payload = line.split(b"||", 1)
        if json.loads(header).get("type") == "PRIMITIVE" and payload.rstrip(b"\r\n") == b"|":
            self.header = json.loads(header)
            self.payload = None
            self.original = line
            self.tail = payload
            self._header = copy.deepcopy(self.header)
            self._payload = None
        else:
            original(self, line)

    Record.__init__ = read_record
    return audit


def risk_pairs(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {(row["pair_type"], row["obj1"], row["obj2"]): row for row in csv.DictReader(stream)
                if row["classification"] in RISK}


def round_pad_gap(row, dump, records):
    if row["pair_type"] not in ("Via-to-Pad(DiffNet)", "Track-to-Pad(DiffNet)") or row["shares_z_layer"] != "True":
        return None
    ref = row["obj2"].removeprefix("pad:").split("(", 1)[0]
    comp, pad_number = ref.rsplit(".", 1)
    pads = [p for c in dump["components"] if c["designator"] == comp for p in c["pads"] if str(p["padNumber"]) == pad_number]
    if len(pads) != 1:
        return None
    pad = pads[0]
    shape = pad["shape"]
    if pad.get("specialPadPresent") or len(shape) < 3 or shape[0] != "ELLIPSE" or shape[1] != shape[2]:
        return None
    p = pad["x"], pad["y"]
    kind, uid = row["obj1"].split("(", 1)[0].split(":", 1)
    if kind == "via":
        via = records["VIA", uid]
        gap = math.dist(p, (via["centerX"], via["centerY"])) - via["viaDiameter"]/2
    else:
        track = records["LINE", uid]
        gap = gate.point_distance(p, (track["startX"], track["startY"]), (track["endX"], track["endY"])) - track["width"]/2
    lower_bound = gap - shape[1]/2 - .15
    if lower_bound < 6.2:
        return None
    return {"padId": pad["primitiveId"], "copperId": uid, "nativePadShape": shape,
            "nativeNominalGapLowerBoundMil": round(lower_bound, 5), "minRequiredMil": 6.2}


def summarize(checkpoint, post, plan_path, baseline_dir, after_dir, output):
    plan = gate.parse_plan(plan_path, checkpoint)
    boards = tuple(native.PCB_IDS) if plan["level"] == "L3" else tuple(plan["boards"])
    source, dest = native.archive(checkpoint), native.archive(post)
    gate.check_archive(source, dest, plan)
    output.mkdir()
    audit = load_auditor()
    before, after = output / "baseline", output / "post"
    before.mkdir()
    after.mkdir()
    inherited, candidate = audit.Archive(checkpoint), audit.Archive(post)
    matrix, unresolved = {}, []
    for board in boards:
        doc = ("PCB", native.PCB_IDS[board])
        baseline_capture, current_capture = (folder / f"{board}-copper.json" for folder in (baseline_dir, after_dir))
        before_csv, after_csv = (folder / f"{board}-matrix.csv" for folder in (before, after))
        old = audit.audit_board_v4(board, inherited, baseline_capture, conflict_csv=before_csv)
        new = audit.audit_board_v4(board, candidate, current_capture, conflict_csv=after_csv)
        native.write(before / f"{board}-v4.json", old)
        native.write(after / f"{board}-v4.json", new)
        before_v4, after_v4 = (x["v4_official_jlcpcb_hdi_audit"]["violations"] for x in (old, new))
        if before_v4 != after_v4 or after_v4["total_v4_violations"]:
            unresolved.append({"board": board, "reason": "V4 hole/span/outline finding or changed diagnostics",
                               "before": before_v4, "after": after_v4})
        previous_pairs, observed = map(risk_pairs, (before_csv, after_csv))
        for k in sorted(observed.keys() & previous_pairs.keys()):
            p, c = previous_pairs[k], observed[k]
            if float(c["gap_mil"]) + .01 < float(p["gap_mil"]):
                unresolved.append({"board": board, "reason": "worse inherited DFM finding", "entry": c})
        gap_reconciliation = []
        for k in sorted(observed.keys() - previous_pairs.keys()):
            r = observed[k]
            verified = round_pad_gap(r, native.read(current_capture), dest[doc])
            if verified:
                gap_reconciliation.append(verified)
            else:
                unresolved.append({"board": board, "reason": "new DFM finding needs review", "entry": r})
        matrix[board] = {"inheritedFlags": len(observed.keys() & previous_pairs.keys()),
                         "circularCopperReconciliation": gap_reconciliation,
                         "v4NativeCheckpoints": [native.digest(baseline_capture), native.digest(current_capture)],
                         "rawV4ReportSha256": [native.digest(before / f"{board}-v4.json"), native.digest(after / f"{board}-v4.json")]}
    report = {"schemaVersion": 1, "method": "inherited-native-v4-hdi-and-copper-dfm",
              "scope": "V4 hole/outline/original-classified copper findings; no fab approval",
              "checkpointSha256": native.digest(checkpoint), "postSha256": native.digest(post),
              "planSha256": native.digest(plan_path), "boards": matrix, "unresolvedNewFindings": unresolved}
    native.write(output / "dfm-review.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("checkpoint", "post", "plan", "baseline-logs", "after-logs", "out"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.checkpoint, args.post, args.plan, args.baseline_logs, args.after_logs, args.out)
    print(f"Audited {len(result['boards'])} board(s); {len(result['unresolvedNewFindings'])} unresolved new findings")
    if result["unresolvedNewFindings"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
