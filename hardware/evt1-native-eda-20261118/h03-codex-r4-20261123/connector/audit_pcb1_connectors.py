#!/usr/bin/env python3
"""Read J_CAM and J_CHG symbol wiring and placement directly from EasyEDA Pro."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile


PCB1 = ("PCB", "8fbc3cae65886fe5")
INTERFACE_PAGE = ("SCH_PAGE", "89cd87358a17e3c2")
EXACT_HIROSE_PAGE = "https://www.hirose.com/en/product/p/CL0673-5025-0-53"
REFS = {"J2": "J_CAM", "J3": "J_CHG"}


def read_documents(project):
    documents = {}
    with ZipFile(project) as archive:
        stream, = [name for name in archive.namelist() if name.endswith(".epru")]
        for row in archive.read(stream).splitlines():
            if not row:
                continue
            header, body = row.split(b"||", 1)
            header = json.loads(header)
            body = body.removesuffix(b"|")
            if not body:
                if header["type"] != "PRIMITIVE":
                    raise ValueError(f"Unexpected empty native record {header}")
                continue
            payload = json.loads(body)
            if header["type"] == "DOCHEAD":
                key = (payload["docType"], payload["uuid"])
                if key in documents:
                    raise ValueError(f"Duplicate native document {key}")
                document = documents[key] = []
            document.append((header, payload))
    return documents


def attributes(document, parent):
    return {
        payload["key"]: payload["value"]
        for header, payload in document
        if header["type"] == "ATTR" and payload.get("parentId") == parent
    }


def position(x, y):
    return round(x, 6), round(y, 6)


def read_connector(documents, ref):
    schematic = documents[INTERFACE_PAGE]
    instance_id, = [
        payload["parentId"]
        for header, payload in schematic
        if header["type"] == "ATTR" and payload["key"] == "Designator" and payload["value"] == ref
    ]
    component, = [
        payload for header, payload in schematic if header.get("id") == instance_id
    ]
    fields = attributes(schematic, instance_id)
    if component["isMirror"] or component["rotation"] or fields["EVT1 Source Ref"] != REFS[ref]:
        raise ValueError(f"{ref}: unexpected symbol identity or transform")
    device, = [
        payload["attributes"]
        for header, payload in documents["DEVICE", fields["Device"]]
        if header["type"] == "META"
    ]
    symbol = documents["SYMBOL", fields["Symbol"]]
    wire_at_contact = {}
    for header, line in schematic:
        if header["type"] != "LINE":
            continue
        net = attributes(schematic, line["lineGroup"]).get("NET")
        if net:
            for prefix in ("start", "end"):
                point = position(line[prefix + "X"], line[prefix + "Y"])
                wire_at_contact.setdefault(point, []).append((line["lineGroup"], net))
    contacts = []
    for header, pin in symbol:
        if header["type"] != "PIN":
            continue
        pin_fields = attributes(symbol, header["id"])
        point = position(component["x"] + pin["x"], component["y"] + pin["y"])
        (wire, net), = wire_at_contact[point]
        contacts.append({
            "pin": pin_fields["Pin Number"], "name": pin_fields["Pin Name"],
            "pin_id": header["id"], "wire_id": wire, "sch_endpoint": point, "net": net,
        })
    placed = [
        header["id"]
        for header, payload in documents[PCB1]
        if header["type"] == "COMPONENT"
        and (payload["attrs"].get("Unique ID") == fields["Unique ID"]
             or attributes(documents[PCB1], header["id"]).get("Designator") == ref)
    ]
    return {
        "ref": ref, "logical_ref": fields["EVT1 Source Ref"], "sch_instance": instance_id,
        "unique_id": fields["Unique ID"], "device": fields["Device"], "symbol": fields["Symbol"],
        "mpn": device["MPN"], "instance_convert_to_pcb": fields.get("Convert to PCB"),
        "instance_footprint": fields.get("Footprint"), "device_footprint": device["Footprint"],
        "instance_origin_footprint": fields.get("Origin Footprint"),
        "instance_source": fields.get("UserDocLink"), "device_source": device.get("UserDocLink"),
        "needs_exact_source": ref == "J2" and fields.get("UserDocLink") != EXACT_HIROSE_PAGE,
        "pcb_component_ids": placed, "contacts": contacts,
    }


def check_camera_anchor(documents, dump_path):
    """Screen the Hirose body at the inherited assembly anchor against top-side placement."""
    dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    capture = dump["capture"]
    if not capture["identityVerified"] or capture["documentUuid"] != PCB1[1]:
        raise ValueError("PCB dump has unverified PCB1 identity")
    top_layer, = [
        payload["layerId"] for header, payload in documents[PCB1]
        if header["type"] == "LAYER" and payload["layerType"] == "TOP"
    ]
    mm_per_mil = 0.0254
    low_x, low_y, high_x, high_y = (coordinate / mm_per_mil for coordinate in (2.05, 15.60, 3.75, 22.40))
    overlap = []
    for component in dump["components"]:
        if component["layer"] != top_layer:
            continue
        box = component["bbox"]
        width = min(high_x, box["maxX"]) - max(low_x, box["minX"])
        length = min(high_y, box["maxY"]) - max(low_y, box["minY"])
        if width > 0 and length > 0:
            pads_inside = [
                pad["padNumber"] for pad in component["pads"]
                if low_x < pad["x"] < high_x and low_y < pad["y"] < high_y
            ]
            overlap.append({
                "ref": component["designator"], "component_id": component["primitiveId"],
                "bbox_overlap_mm": [round(width * mm_per_mil, 3), round(length * mm_per_mil, 3)],
                "pad_centers_inside_body_projection": pads_inside,
            })
    return {
        "capture_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
        "capture_semantic_sha256": dump["semanticSha256"],
        "top_layer": top_layer, "anchor_xy_mm": [2.90, 19.00],
        "body_projection_xyxy_mm": [2.05, 15.60, 3.75, 22.40],
        "overlaps": sorted(overlap, key=lambda row: row["ref"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("native_package", type=Path, help="Repository's evt1-native-eda-20261118 directory")
    parser.add_argument("--pcb1-dump", type=Path, help="Native PCB1 copper dump of the same design")
    args = parser.parse_args()
    documents = read_documents(args.project)
    connectors = [read_connector(documents, ref) for ref in REFS]
    actual = {
        (connector["ref"], pin["pin"]): pin["net"]
        for connector in connectors for pin in connector["contacts"]
    }
    sys.path.insert(0, str(args.native_package / "h02-native"))
    from verify_h02 import parse_protel

    reference_path = (
        "h03-v4-dfm-u11-2n2-route/evidence/takeover/independent/board-netlists/M-MAIN-L.net"
    )
    reference_file = args.native_package / reference_path
    components, groups = parse_protel(reference_file.read_text(encoding="utf-8-sig"))
    reference = {member: name for name, members in groups for member in members if member[0] in REFS}
    if actual != reference or len(actual) != 30:
        raise ValueError(f"Native versus inherited Protel2 mismatch: {actual.items() ^ reference.items()}")
    reference_convert = {item["designator"]: item["convert_to_pcb"] for item in components}
    for connector in connectors:
        connector["inherited_export_convert_to_pcb"] = reference_convert[connector["ref"]]

    legacy_path = "kicad/CAD_TERMINALS.csv"
    with (args.native_package / legacy_path).open(encoding="utf-8-sig", newline="") as stream:
        legacy = {
            (row[1], row[3]): row[5] for row in csv.reader(stream)
            if row and row[0] == "M-MAIN-L" and row[1] in REFS and row[2] == REFS[row[1]]
        }
    if legacy.keys() != actual.keys():
        raise ValueError("Legacy controlled map has different terminal coverage")
    legacy_delta = [
        {"ref": ref, "pin": pin, "legacy": legacy[ref, pin], "native": actual[ref, pin]}
        for ref, pin in actual if legacy[ref, pin] != actual[ref, pin]
    ]
    expected_eco = {"ref": "J3", "pin": "1", "legacy": "VBUS_5V", "native": "VBUS_5V_USB"}
    if legacy_delta != [expected_eco]:
        raise ValueError(f"Unexpected legacy delta against ECO-07: {legacy_delta}")
    report = {
        "archive_name": args.project.name,
        "archive_sha256": hashlib.sha256(args.project.read_bytes()).hexdigest(),
        "pcb": PCB1[1], "sch_page": INTERFACE_PAGE[1],
        "inherited_protel_file": reference_path,
        "inherited_protel_comparison": "30 matching contacts",
        "legacy_controlled_file": legacy_path,
        "legacy_controlled_delta": legacy_delta,
        "legacy_delta_authority": "h02-reve-h03-bridge/REV_E_NETLIST_AND_ECO_DIFF.md ECO-07",
        "connectors": connectors,
    }
    if args.pcb1_dump:
        report["camera_anchor_screen"] = check_camera_anchor(documents, args.pcb1_dump)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
