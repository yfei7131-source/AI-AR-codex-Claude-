"""Compare native Protel2 pin-net relations to the measured PCB1 placed-pad graph."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

PCB1 = "8fbc3cae65886fe5"
APP_DOC = "4d38590959875927"
EXTERNAL_PARTS = {"BAT1", "SPK1"}


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(package, schematic, receipt, copper, drc):
    sys.path.insert(0, str(package / "h02-native"))
    from verify_h02 import parse_protel

    sent = json.loads(receipt.read_bytes())
    native = json.loads(copper.read_bytes())
    findings = json.loads(drc.read_bytes())
    if not sent["ok"] or sent["context"]["documentUuid"] != APP_DOC:
        raise ValueError("Unexpected schematic acquisition identity")
    net_artifacts = [item for item in sent["artifacts"] if item.get("kind") == "schematic_netlist"]
    if len(net_artifacts) != 1 or net_artifacts[0]["sha256"] != sha(schematic):
        raise ValueError("Protel2 file does not match its native library-artifact receipt")
    if not native["capture"]["identityVerified"] or native["capture"]["documentUuid"] != PCB1:
        raise ValueError("PCB1 is not tied to the identity-verified capture")

    schem, groups = parse_protel(schematic.read_text(encoding="utf-8-sig"))
    smb = {row["designator"]: row["convert_to_pcb"] for row in schem}
    pcb = {row["designator"]: row for row in native["components"]}
    if len(smb) != len(schem) or len(pcb) != len(native["components"]):
        raise ValueError("Duplicate component designator in one of the scopes")

    wanted = defaultdict(set)
    found = defaultdict(set)
    schematic_terminals = defaultdict(dict)
    for net, pins in groups:
        for designator, pad in pins:
            schematic_terminals[designator][pad] = net
            if designator in pcb:
                wanted[designator, pad].add(net)
    for designator, placed in pcb.items():
        for pad in placed["pads"]:
            if pad["net"]:
                found[designator, str(pad["padNumber"])].add(pad["net"])
    differences = [{"designator": designator, "pin": pin, "schematic": sorted(wanted[designator, pin]),
                    "pcb": sorted(found[designator, pin])}
                   for designator, pin in sorted(wanted.keys() | found.keys())
                   if wanted[designator, pin] != found[designator, pin]]
    missing, extra = smb.keys() - pcb.keys(), pcb.keys() - smb.keys()
    missing_eligible = {key: schematic_terminals[key] for key in sorted(missing) if smb[key] is True}
    external = [key for key in sorted(missing) if smb[key] is False]
    if set(external) != EXTERNAL_PARTS or any(smb[key] is None for key in missing):
        raise ValueError("Unexpected missing population status")
    errors = [x for x in findings["violations"] if x["rule"] == "Netlist Error"]
    return {"scope": "Exact ref/PCB-eligibility and nonempty ref-pin→net parity only. The native aggregate "
                     "DRC rule itself has no per-connector attribution.",
            "inputs": {"schematic_protel2_sha256": sha(schematic), "schematic_receipt_sha256": sha(receipt),
                       "copper_dump_sha256": sha(copper), "native_drc_sha256": sha(drc)},
            "designators": {"schematic": len(smb), "pcb": len(pcb),
                            "schematic_convert_to_pcb_counts": dict(Counter(str(x) for x in smb.values())),
                            "pcb_extras": sorted(extra), "missing_pcb_eligible": sorted(missing_eligible),
                            "intentional_external_parts": external},
            "matched_placed_terminals": sum(wanted[key] == found[key] for key in wanted.keys() | found.keys()),
            "native_named_net_groups": len(groups),
            "placed_pin_net_differences": differences,
            "missing_eligible_terminals": missing_eligible,
            "native_aggregate_netlist_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("package", "schematic", "receipt", "copper", "drc", "out"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    report = audit(args.package,args.schematic,args.receipt,args.copper,args.drc)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(report["designators"], "placed terminal differences", len(report["placed_pin_net_differences"]))
