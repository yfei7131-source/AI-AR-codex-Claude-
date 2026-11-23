"""Prepare a PR47-style native archive candidate with one reviewed U11 microvia."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "h03-codex-r4-20261123/u11"))
from audit_r3_u11 import load, records

DOC = ("PCB", "1db01a36f669a47a")
VIA_REFERENCE = "c05bf22129468014"
BOARD_RULE = '["RULE","BLIND","blindVia"]'
VIA_ID = "9b1de4f8a526c7d3"
A5_VIA = (32.6, 330.6)
A5_PAD = (33.46456, 341.53541)


def parsed(line):
    h, p = line.split(b"||", 1)
    return json.loads(h), p


def generate(source, destination):
    project = load(source)
    doc = project.documents[DOC]
    contents = records(doc)
    origin = contents["VIA", VIA_REFERENCE]
    match = [item for item in contents["RULE", BOARD_RULE]["ruleContext"]["blinds"]["content"]
             if item["name"] == "BV_L1_L2"]
    pad = contents["PAD_NET", '["PAD_NET","fb9a90e154948529","A5","nrfp114"]']
    if (origin["viaType"], origin["ruleName"], origin["netName"], origin["holeDiameter"],
            origin["viaDiameter"]) != ("BLIND", "BV_L1_L2", "GND", 4, 10):
        raise ValueError("The inherited via template has a different geometry or layer span")
    if len(match) != 1 or (match[0]["staLayerId"], match[0]["endLayerId"]) != (1, 15):
        raise ValueError("The inherited L1–L2 rule does not match the expected native span")
    if pad["padNet"] != "GND" or any(r.header.get("id") == VIA_ID for r in doc):
        raise ValueError("U11.A5 has the wrong net, or the planned via ID is already taken")
    new_via = origin | {"centerX": A5_VIA[0], "centerY": A5_VIA[1]}
    next_ticket = max(int(r.header.get("ticket", 0)) for r in doc) + 1
    header = {"type": "VIA", "ticket": next_ticket, "id": VIA_ID}
    row = "||".join(json.dumps(item, separators=(",", ":")) for item in (header, new_via)).encode() + b"|\n"

    with ZipFile(source) as before:
        stream, = [item for item in before.namelist() if item.endswith(".epru")]
        raw = before.read(stream)
        lines = raw.splitlines(keepends=True)
        active = False
        insertion = None
        for idx, line in enumerate(lines):
            h, b = parsed(line)
            if h["type"] == "DOCHEAD":
                if active:
                    insertion = idx
                    break
                p = json.loads(b.rstrip(b"\r\n").removesuffix(b"|"))
                active = (p["docType"], p["uuid"]) == DOC
        if insertion is None:
            if not active:
                raise ValueError("Could not locate PCB3")
            insertion = len(lines)
        preceding = b"".join(lines[:insertion])
        if not preceding.endswith(b"\n"):
            preceding = preceding.removesuffix(b"|") + b"|\n"
        edited = preceding + row + b"".join(lines[insertion:])
        with ZipFile(destination, "x") as out:
            out.comment = before.comment
            for item in before.infolist():
                out.writestr(item, edited if item.filename == stream else before.read(item))

    result = load(destination)
    for key in project.documents:
        expected = records(project.documents[key])
        observed = records(result.documents[key])
        if key == DOC:
            expected["VIA", VIA_ID] = new_via
        if observed != expected:
            raise ValueError(f"Unexpected change to {key}")
    return {"scope": "single 4/10 mil GND blind via candidate, followed by typed trace in native copy",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "candidate_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "document": DOC[1], "native_primitive_id": VIA_ID, "via": new_via,
            "planned_track": {"from_U11_A5": A5_PAD, "to_via": A5_VIA, "width_mil": 4}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.destination), indent=2))
