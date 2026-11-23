"""Verify U11 in the Gemini R3 native export against the inherited Nordic audit."""
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile


PCB3 = ("PCB", "1db01a36f669a47a")
PCB3_U11 = "fb9a90e154948529"
U11_FOOTPRINT = ("FOOTPRINT", "ddd711692e399705")
U11_SCH = ("SCH_PAGE", "07dc7dde94c1bf76")
MM_PER_MIL = 0.0254


def load(path):
    documents = {}
    with ZipFile(path) as archive:
        stream, = [name for name in archive.namelist() if name.endswith(".epru")]
        for line in archive.read(stream).splitlines():
            header, raw = line.split(b"||", 1)
            record = json.loads(header)
            if raw == b"|":
                if record["type"] != "PRIMITIVE":
                    raise ValueError(f"Unexpected empty payload {record}")
                body = None
            else:
                body = json.loads(raw.removesuffix(b"|"))
            if record["type"] == "DOCHEAD":
                key = (body["docType"], body["uuid"])
                if key in documents:
                    raise ValueError(f"Duplicate native document {key}")
                documents[key] = []
            documents[key].append(SimpleNamespace(header=record, payload=body))
    return SimpleNamespace(documents=documents)


def records(document):
    return {
        (r.header["type"], r.header["id"]): r.payload
        for r in document
        if r.header["type"] != "DOCHEAD"
    }


def count_delta(left, right):
    changes = Counter()
    for key in set(left) | set(right):
        if key not in left or key not in right or left[key] != right[key]:
            changes[key[0]] += 1
    return dict(sorted(changes.items()))


def segment_distance(x, y, track):
    ax, ay = track["startX"], track["startY"]
    dx, dy = track["endX"] - ax, track["endY"] - ay
    length_squared = dx * dx + dy * dy
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length_squared)) if length_squared else 0
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def audit(r3, r2, reference=None):
    same_scope = count_delta(records(r2.documents[PCB3]), records(r3.documents[PCB3]))
    footprint_delta = count_delta(records(r2.documents[U11_FOOTPRINT]), records(r3.documents[U11_FOOTPRINT]))
    schematic_delta = count_delta(records(r2.documents[U11_SCH]), records(r3.documents[U11_SCH]))

    source = SimpleNamespace(documents={key: SimpleNamespace(records=value) for key, value in r3.documents.items()})
    sch, names, nc, _ = aur.symbol_inventory(source)
    board = records(r3.documents[PCB3])
    u11 = board["COMPONENT", PCB3_U11]
    assert (u11["attrs"]["Unique ID"], u11["layerId"], u11["angle"]) == (sch["Unique ID"], 1, 90)
    assert u11["attrs"]["Manufacturer Part"] == sch["Manufacturer Part"] == aur.MPN
    footprint, = [p["value"] for (kind, _), p in board.items()
                  if kind == "ATTR" and p["parentId"] == PCB3_U11 and p["key"] == "Footprint"]
    assert footprint == U11_FOOTPRINT[1]
    pads = {}
    for (kind, pad_id), p in records(r3.documents[U11_FOOTPRINT]).items():
        if kind == "PAD":
            assert p["num"] not in pads
            pads[p["num"]] = (pad_id, p)
    assert set(pads) == set(names) == set(aur.PIN_MAP)
    actual_nets = {}
    for (kind, record_id), p in board.items():
        if kind == "PAD_NET":
            _, parent, ball, pad_id = json.loads(record_id)
            if parent == PCB3_U11:
                assert ball not in actual_nets and pads[ball][0] == pad_id
                actual_nets[ball] = p["padNet"]

    top_tracks = {id_: l for (kind, id_), l in board.items() if kind == "LINE" and l["layerId"] == 1}
    vias = {id_: p for (kind, id_), p in board.items() if kind == "VIA"}
    blind = board["RULE", '["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
    top_blind = {v["name"] for v in blind if 1 in (v["staLayerId"], v["endLayerId"])}
    top_vias = {id_: p for id_, p in vias.items() if p["viaType"] == "NORMAL" or p["ruleName"] in top_blind}
    rows = []
    for ball, name in aur.PIN_MAP.items():
        _, pad = pads[ball]
        default = pad["defaultPad"]
        diameter = default["width"]
        assert default["padType"] == "ELLIPSE" and diameter == default["height"] == 7.677
        role, expected, _ = aur.contract(ball, name)
        actual = actual_nets.get(ball, "")
        assert actual == expected and (ball in nc) == (not expected)
        assert names[ball].split("/")[0] == name
        row, col = aur.position(ball)
        assert abs(pad["centerX"] * MM_PER_MIL - (col - 5.5) * aur.PITCH_MM) < 0.0002
        assert abs(pad["centerY"] * MM_PER_MIL - (5 - row) * aur.PITCH_MM) < 0.0002
        x, y = u11["x"] - pad["centerY"], u11["y"] + pad["centerX"]
        same_net_tracks = sorted(
            id_ for id_, l in top_tracks.items()
            if actual and l["netName"] == actual and segment_distance(x, y, l) <= (diameter + l["width"]) / 2
        )
        same_net_vias = sorted(
            id_ for id_, v in top_vias.items()
            if actual and v["netName"] == actual
            and math.hypot(x - v["centerX"], y - v["centerY"]) <= (diameter + v["viaDiameter"]) / 2
        )
        centered_vias = [
            id_ for id_, v in top_vias.items()
            if math.hypot(x - v["centerX"], y - v["centerY"]) < 0.02
        ]
        nearest, gap = aur.clearance(ball, diameter * MM_PER_MIL)
        depth = min(row, len(aur.GRID_ROWS) - 1 - row, col, aur.GRID_COLUMNS - 1 - col)
        rows.append({"ball": ball, "nordic_pin": name, "config3_role": role,
                     "native_pcb_net": actual, "native_sch_explicit_nc": ball in nc,
                     "center_x_mil": round(x, 5), "center_y_mil": round(y, 5),
                     "land_diameter_mil": diameter, "ring_depth": depth,
                     "nearest_foreign_or_unassigned_land": nearest, "centered_trial_gap_mm": gap,
                     "same_net_top_line_contacts": " ".join(same_net_tracks),
                     "same_net_top_via_contacts": " ".join(same_net_vias),
                     "existing_centered_via_ids": " ".join(centered_vias)})
    inner = [r for r in rows if r["native_pcb_net"] and r["ring_depth"]]
    failed = [r["ball"] for r in inner if r["centered_trial_gap_mm"] < aur.CLEARANCE_MM]
    current_centered = [r for r in rows if r["existing_centered_via_ids"]]
    width = Counter(l["width"] for l in top_tracks.values())
    report = {
        "scope": "Offline read of original R3 native archive. Contact means shared same-net copper geometry for listed primitives, with no claim of whole-net connectivity.",
        "r2_to_r3_pcb3_changed_records_by_type": same_scope,
        "r2_to_r3_u11_footprint_changed_records_by_type": footprint_delta,
        "r2_to_r3_u11_schematic_page_changed_records_by_type": schematic_delta,
        "pcb_uuid": PCB3[1],
        "footprint_uuid": U11_FOOTPRINT[1],
        "schematic_page_uuid": U11_SCH[1],
        "u11_primitive_id": PCB3_U11,
        "u11_pose": {k: u11[k] for k in ("x", "y", "angle", "layerId")},
        "all_balls_match_inherited_nordic_config3_mapping": len(rows),
        "balls_with_pcb_nets": sum(bool(r["native_pcb_net"]) for r in rows),
        "schematic_nc_balls_match_pcb_unassigned": len(nc),
        "u11_role_counts": dict(sorted(Counter(r["config3_role"] for r in rows).items())),
        "inner_balls_with_nets": len(inner),
        "inner_balls_failing_locked_6mil_clearance_with_0p2274mm_centered_via": failed,
        "existing_pads_with_centered_vias": {r["ball"]: r["existing_centered_via_ids"] for r in current_centered},
        "active_balls_with_direct_track_or_via_contact": sum(bool(r["same_net_top_line_contacts"] or r["same_net_top_via_contacts"]) for r in rows),
        "top_track_width_histogram_mil": dict(sorted(width.items())),
        "pcb3_copper_layers": {json.loads(id_)[1]: p["layerType"] for (kind, id_), p in board.items()
                              if kind == "LAYER" and p["use"] and p["layerType"] in {"TOP", "BOTTOM", "SIGNAL", "PLANE"}},
        "pcb3_blind_via_rules": blind,
        "pcb3_physical_layer_ids": sorted(json.loads(id_)[1] for (kind, id_) in board if kind == "LAYER_PHYS"),
        "pcb3_blind_via_aperture_and_pad_counts": dict(sorted(Counter(
            f"{p['ruleName']} {p['holeDiameter']} / {p['viaDiameter']} mil"
            for p in vias.values() if p["viaType"] == "BLIND"
        ).items())),
        "pcb3_existing_centered_via_geometry": {r["ball"]: [top_vias[id_] for id_ in r["existing_centered_via_ids"].split()] for r in current_centered},
        "manufacturing": "BLOCKED",
    }
    if reference is not None:
        refb = records(reference.documents[PCB3])
        selected_types = {"LINE", "VIA", "PAD_NET", "RULE", "LAYER", "LAYER_PHYS", "REGION", "POLY"}
        report["pr47_reference_to_r3_pcb3_selected_changed_records"] = count_delta(
            {k: v for k, v in refb.items() if k[0] in selected_types},
            {k: v for k, v in board.items() if k[0] in selected_types},
        )
        report["pr47_reference_to_r3_u11_footprint_changed_records"] = count_delta(
            records(reference.documents[U11_FOOTPRINT]), records(r3.documents[U11_FOOTPRINT]))
    return report, rows


if __name__ == "__main__":
    r3_path, r2_path, reference_path, inherited_audit, output_folder = map(Path, sys.argv[1:])
    sys.path.insert(0, str(inherited_audit))
    import audit_u11 as aur

    report, rows = audit(load(r3_path), load(r2_path), load(reference_path))
    report["r3_epro2_sha256"] = hashlib.sha256(r3_path.read_bytes()).hexdigest()
    (output_folder / "r3-u11-native-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    with (output_folder / "r3-u11-95ball-native.csv").open("w", newline="", encoding="utf8") as dst:
        writer = csv.DictWriter(dst, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in report.items() if k not in {"pcb3_existing_centered_via_geometry", "inner_balls_failing_locked_6mil_clearance_with_0p2274mm_centered_via"}}, indent=2))
    print(f"Inner active balls failing centered-via necessary geometry: {len(report['inner_balls_failing_locked_6mil_clearance_with_0p2274mm_centered_via'])}")
