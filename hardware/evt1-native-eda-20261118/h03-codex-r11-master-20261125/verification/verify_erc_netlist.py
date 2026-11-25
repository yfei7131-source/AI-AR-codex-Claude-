"""Compare unaltered native ERC, Protel2 and PCB readbacks for a copper-only R11 ECO."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

DOCS = {
    "PCB1": ("8fbc3cae65886fe5", "4d38590959875927"),
    "PCB2": ("9ce45f14cb79dc9d", "e00fbca5c08cc114"),
    "PCB3": ("1db01a36f669a47a", "e98944c2045546cf"),
}

# Existing board-side solder lands from the native R10 design. A shared battery
# return land carries both pack negative and NTC return in this design.
ASSEMBLY_LANDS = {
    "PCB1": {"BAT1": {"P-": "TP1", "NTC_RETURN": "TP1", "P+": "TP2", "NTC": "TP5"},
             "SPK1": {"+": "TP7", "-": "TP6"}},
    "PCB3": {"BAT1": {"P-": "TP1", "NTC_RETURN": "TP1", "P+": "TP2", "NTC": "TP3"},
             "SPK1": {"+": "TP5", "-": "TP4"}},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def parse_protel(data):
    netlist = data.decode("utf-8-sig").replace("\r\n", "\n")
    require(netlist.startswith("PROTEL NETLIST 2.0\n"), "Unexpected netlist format")
    components = {}
    for block in re.findall(r"^\[\n(.*?)\n\] *$", netlist, re.M | re.S):
        values = block.splitlines()
        require(values[-2:] == ["", "*"], "Invalid component terminator")
        fields = values[:-2]
        require(len(fields) % 2 == 0, "Invalid Protel field pairs")
        record = dict(zip(fields[::2], fields[1::2]))
        ref = record["DESIGNATOR"]
        require(ref not in components and ref, f"Duplicate or blank ref {ref}")
        components[ref] = record
    pins = {}
    for block in re.findall(r"^\(\n(.*?)\n\) *$", netlist, re.M | re.S):
        name, *members = block.splitlines()
        for member in members:
            ref, pad = member.split()[0].split("-", 1)
            key = (ref, pad)
            require(ref in components and key not in pins, f"Invalid Protel pin {key}")
            pins[key] = name.strip()
    require(components and pins, "Empty netlist")
    return components, pins


def native_board(folder, board):
    def file(suffix):
        return folder / (board + suffix)
    pcb_uuid, sch_page_uuid = DOCS[board]
    copper = read(file("-copper.json"))
    identity = copper["capture"]
    require(identity["identityVerified"] and identity["documentUuid"] == pcb_uuid
            and not copper.get("partial"), f"{board} incomplete capture")
    project_uuid = identity["projectUuid"]
    data = file(".net").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    receipt = read(file("-netlist.json"))
    require(receipt["ok"] and receipt["result"]["netlistType"] == "Protel2"
            and receipt["artifacts"][0]["sha256"] == digest
            and receipt["context"]["projectUuid"] == project_uuid
            and receipt["context"]["documentUuid"] == sch_page_uuid,
            f"{board} invalid netlist provenance")
    devices, pins = parse_protel(data)
    placed = set()
    board_pins = defaultdict(set)
    for component in copper["components"]:
        ref = component["designator"]
        require(ref not in placed, f"Repeated placement {board}.{ref}")
        placed.add(ref)
        for pad in component["pads"]:
            if pad["net"]:
                board_pins[(ref, str(pad["padNumber"]))].add(pad["net"])
    eligible = {ref for ref, item in devices.items() if item["Convert to PCB"] == "yes"}
    external = set(devices) - eligible
    missing = eligible - placed
    require(placed <= eligible, f"{board} unexpected placements: {placed - eligible}")
    require(missing == ({"J2", "J3"} if board == "PCB1" else set()),
            f"{board} missing eligible set changed: {missing}")
    require(external == (set() if board == "PCB2" else {"BAT1", "SPK1"}),
            f"{board} unexpected excluded devices: {external}")
    named = {key: {net} for key, net in pins.items() if key[0] in placed}
    require(named == board_pins, f"{board} placed pin/net mismatch")
    constrained = {}
    for ref in sorted(external | missing):
        item = devices[ref]
        role = "off-board assembly" if ref in external else "unconfirmed on-board connector"
        require(not item["FOOTPRINT"] and item["Add into BOM"] == "yes",
                f"{board}.{ref} footprint or BOM changed")
        pin_map = {pad: net for (designator, pad), net in pins.items() if designator == ref}
        require(pin_map, f"{board}.{ref} terminal map empty")
        constrained[ref] = {"role": role, "convertToPCB": item["Convert to PCB"],
                            "addIntoBOM": item["Add into BOM"], "terminalNets": pin_map}
        if ref in external:
            lands = ASSEMBLY_LANDS[board][ref]
            require(set(lands) == set(pin_map), f"{board}.{ref} external pin coverage changed")
            for pin, land in lands.items():
                require(board_pins[land, "1"] == {pin_map[pin]},
                        f"{board}.{ref}.{pin} board-side termination changed")
            constrained[ref]["boardSideLands"] = {pin: f"{land}.1" for pin, land in lands.items()}
    erc = read(file("-erc.json"))["result"]
    require(erc["strict"] and erc["detailsAvailable"] and erc["countsAvailable"],
            f"{board} incomplete native ERC")
    objects = sorted((row["level"], row["rule"], obj["sheet"], obj["primitiveId"], obj["name"])
                     for row in erc["violations"] for obj in row["raw"]["primitives"])
    require({item[4] for item in objects} == set(constrained)
            and len(objects) == len(erc["violations"]) == erc["fatal"] == len(constrained)
            and all(item[:2] == ("fatal", "MISSFOOTPRINT") for item in objects),
            f"{board} ERC changed")
    drc = read(file("-drc.json"))
    errors = sorted((row["ruleName"], row["objType"], row["message"])
                    for row in drc["violations"] if row["rule"] == "Netlist Error")
    require(len(errors) == drc["counts"].get("Netlist Error", 0) == int(bool(missing)),
            f"{board} native netlist errors do not match outstanding interface")
    return {"netlistSha256": digest, "schematicDevices": len(devices), "pcbDevices": len(placed),
            "namedNetGroups": len(set(pins.values())), "matchedPlacedTerminals": len(named),
            "constrainedDevices": constrained, "strictERC": erc["summary"],
            "ercObjects": objects, "pcbNetlistErrors": errors}, project_uuid


def run(phases):
    expected = {}
    sources = []
    for index, phase in enumerate(phases):
        projects = set()
        for board in DOCS:
            result, project = native_board(phase, board)
            projects.add(project)
            if index == 0:
                expected[board] = result
            else:
                require(result == expected[board], f"{board} {phase} differs from {phases[0]}")
        require(len(projects) == 1, f"{phase} mixed projects")
        sources.append({"phase": phase.name, "nativeProject": projects.pop()})
    return {"releaseStatus": "NOT FOR FAB", "comparedCaptures": sources,
            "electricalNetlistAndERCMatch": True, "boards": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phases", type=Path, nargs="+", help="Reference, then each native capture directory")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.phases)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Matched native pin-net, BOM and ERC records from", len(args.phases), "capture(s)")
