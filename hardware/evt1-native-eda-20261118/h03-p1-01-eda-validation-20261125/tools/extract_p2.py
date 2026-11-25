"""Build versioned P2 routing inputs from matching EasyEDA Pro evidence."""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from zipfile import ZipFile

BOARDS = ("PCB1", "PCB2", "PCB3")
# EasyEDA native IDs are nonmonotonic in physical copper order.
COPPER_ORDER = (1, 15, 16, 17, 18, 2)
OUTER_COPPER = (1, 2)
BOARD_CUTOUT_LAYER = 12
CAPTURE_COORDINATE_TOLERANCE_MIL = 0.1
SCHEMATIC_PAGES = {"PCB1": "4d38590959875927", "PCB2": "e00fbca5c08cc114", "PCB3": "e98944c2045546cf"}
DUMP_CATEGORIES = {
    "LINE": "lines", "ARC": "arcs", "VIA": "vias", "REGION": "regions",
    "FILL": "fills", "POUR": "pours", "POURED": "poured",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, obj, *, compact=False):
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      indent=None if compact else 2, separators=(",", ":") if compact else None)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def native_documents(archive):
    docs = {}
    with ZipFile(archive) as bundle:
        require(bundle.testzip() is None, "Native archive CRC failure")
        streams = [n for n in bundle.namelist() if n.endswith(".epru")]
        require(len(streams) == 1, "Expected one native EPRU stream")
        metadata = json.loads(bundle.read("project2.json"))
        for row in bundle.read(streams[0]).splitlines():
            raw_header, payload = row.split(b"||", 1)
            header = json.loads(raw_header)
            record_type = header["type"]
            if payload == b"|":
                require(record_type == "PRIMITIVE", f"Unsupported empty record {header}")
                continue
            value = json.loads(payload.removesuffix(b"|"))
            if record_type == "DOCHEAD":
                key = (value["docType"], value["uuid"])
                require(key not in docs, f"Duplicate native document {key}")
                document = defaultdict(dict)
                docs[key] = document
                continue
            if key[0] not in {"PCB", "FOOTPRINT"}:
                continue
            primitive = header.get("id")
            # P2 consumes only persistent PCB and footprint objects and rule records.
            require(primitive not in document[record_type], f"Duplicate native record {key} {header}")
            document[record_type][primitive] = value
    return docs, metadata["editorVersion"]


def keyed_rows(native_records):
    return [{"id": key, **row} for key, row in sorted(native_records.items())]


def index_rows(rows, key, label):
    indexed = {v[key]: v for v in rows}
    require(len(indexed) == len(rows), f"Duplicate identifiers in {label}")
    return indexed


def point_to_board(point, component):
    angle = math.radians(component["angle"])
    x, y = point
    if component["layerId"] == 2:
        y = -y
    return [
        component["x"] + x * math.cos(angle) - y * math.sin(angle),
        component["y"] + x * math.sin(angle) + y * math.cos(angle),
    ]


def polyline_points(path):
    commands = [x for x in path if isinstance(x, str)]
    require(commands in ([], ["L"]), f"Unsupported polyline path commands {commands}")
    coords = [x for x in path if not isinstance(x, str)]
    return [list(point) for point in zip(coords[::2], coords[1::2], strict=True)]


def mapped_ring(path, component):
    return [point_to_board(point, component) for point in polyline_points(path)]


def angle_delta(x, y):
    return abs((x - y + 180) % 360 - 180)


def pad_geometry(pad, component, native_pad):
    definition = native_pad["defaultPad"]
    kind = definition["padType"]
    require(kind == pad["shape"][0], f"{pad['primitiveId']} copper shape mismatch")
    sign = 1 if component["layerId"] == 1 else -1
    angle = (component["angle"] + sign * native_pad["padAngle"]) % 360
    local = (native_pad["centerX"], native_pad["centerY"])
    pad_anchor = point_to_board(local, component)
    require(math.dist(pad_anchor, (pad["x"], pad["y"])) <= CAPTURE_COORDINATE_TOLERANCE_MIL,
            f"{pad['primitiveId']} pad center differs from validated footprint pose")
    require(angle_delta(angle, pad["rotation"]) < 0.01, f"{pad['primitiveId']} pad rotation mismatch")
    require(not pad["specialPadPresent"] and not native_pad.get("specialPad"),
            f"{pad['primitiveId']} needs per-layer pad geometry extraction")
    require(math.hypot(native_pad.get("padOffsetX", 0), native_pad.get("padOffsetY", 0)) <= 0.02,
            f"{pad['primitiveId']} needs pad-offset geometry extraction")
    if kind == "POLYGON":
        ring = mapped_ring(definition["path"], component)
        captured = polyline_points(pad["shape"][1])
        require(len(ring) == len(captured) and any(
            all(math.dist(a, b) <= 0.01 for a, b in zip(ring, path))
            for path in (captured, captured[::-1])),
                f"{pad['primitiveId']} polygon coordinates disagree with native readback")
        shape = {"kind": kind, "ring": ring}
    else:
        require(kind in {"RECT", "ELLIPSE", "OVAL"}, f"Unsupported copper shape {kind}")
        for field, live in zip(("width", "height"), pad["shape"][1:3]):
            require(abs(definition[field] - live) <= 0.051, f"{pad['primitiveId']} {field} mismatch")
        shape = {"kind": kind, "center": pad_anchor, "rotationDeg": angle,
                 "widthMil": definition["width"], "heightMil": definition["height"],
                 "nativePadOffsetBoundMil": math.hypot(native_pad.get("padOffsetX", 0), native_pad.get("padOffsetY", 0))}
        if kind == "RECT":
            shape["radiusMil"] = definition.get("radius", 0)
    return shape


def native_components(doc, documents, captured_rows):
    captured = index_rows(captured_rows, "primitiveId", "components")
    entities = doc["COMPONENT"]
    require(entities.keys() == captured.keys(), "Component identities differ from native archive")
    attrs = defaultdict(dict)
    for row in doc["ATTR"].values():
        attrs[row["parentId"]][row["key"]] = row["value"]
    pad_nets = {}
    for key, row in doc["PAD_NET"].items():
        _, component_id, pad_number, footprint_pad = json.loads(key)
        key = (component_id, footprint_pad)
        require(key not in pad_nets, f"Duplicate PAD_NET {key}")
        pad_nets[key] = (pad_number, row)
    matched_nets = set()
    components, cutouts, mechanical = [], [], []
    for pid, native in sorted(entities.items()):
        seen = captured[pid]
        require(native["layerId"] == seen["layer"] and native["layerId"] in OUTER_COPPER,
                f"{pid} layer mismatch")
        require(math.dist((native["x"], native["y"]), (seen["x"], seen["y"])) < 1e-6
                and angle_delta(native["angle"], seen["rotation"]) < 0.01, f"{pid} pose mismatch")
        require(native["attrs"]["Unique ID"] == seen["uniqueId"]
                and attrs[pid]["Designator"] == seen["designator"], f"{pid} identity mismatch")
        require(seen["availability"].get("pads") == "available", f"{pid} pads unavailable")
        footprint_id = attrs[pid]["Footprint"]
        footprint = documents["FOOTPRINT", footprint_id]
        captured_pads = index_rows(seen["pads"], "primitiveId", f"{pid} pads")
        require({pid + v for v in footprint["PAD"]} == captured_pads.keys(), f"{pid} pad coverage drift")
        pads = []
        for fp_pad_id, fp_pad in sorted(footprint["PAD"].items()):
            pad_id = pid + fp_pad_id
            live = captured_pads[pad_id]
            pad_number, binding = pad_nets[pid, fp_pad_id]
            matched_nets.add((pid, fp_pad_id))
            require(live["padNumber"] == pad_number == fp_pad["num"] and live["net"] == binding["padNet"],
                    f"{pad_id} pad/net disagreement")
            require(set(live["availability"].values()) == {"available"}, f"{pad_id} pad geometry unavailable")
            layer = live["layer"]
            require(layer == native["layerId"] if fp_pad["layerId"] == 1 else layer == fp_pad["layerId"],
                    f"{pad_id} layer differs from footprint pose")
            require(not fp_pad.get("unusedInnerLayers"), f"{pad_id} unused inner lands require resolution")
            hole = fp_pad.get("hole")
            if hole and not (hole["width"] or hole["height"]):
                hole = None
            # A few live polygon pads report a small ROUND value absent from the
            # native footprint pad. Store both fields without making these holes.
            pads.append({
                "id": pad_id, "footprintPadId": fp_pad_id, "number": pad_number,
                "net": binding["padNet"] or None, "layer": layer,
                "copperLayerIds": list(COPPER_ORDER) if layer == BOARD_CUTOUT_LAYER else [layer],
                "shape": pad_geometry(live, native, fp_pad),
                "instancePin": native.get("pinSwapInfo", {}).get(pad_id),
                "padBindingNative": binding, "footprintPadNative": fp_pad,
                "nativeHole": hole, "editorHoleReadback": live.get("hole"),
                "editorAnchorMil": [live["x"], live["y"]],
                "editorHoleGeometry": live.get("holeGeometry"),
                "editorShapeBBox": live.get("shapeBBox"),
            })
        for record_type in ("POLY", "FILL"):
            for shape_id, shape in footprint.get(record_type, {}).items():
                if shape["layerId"] == BOARD_CUTOUT_LAYER:
                    path = shape["path"]
                    require(path[0] == "CIRCLE" and len(path) == 4, f"Unsupported footprint cutout {shape_id}")
                    cutouts.append({"componentId": pid, "designator": seen["designator"], "id": shape_id,
                                    "kind": "CIRCLE", "centerMil": point_to_board(path[1:3], native),
                                    "radiusMil": path[3], "lineWidthMil": shape["width"], "native": shape})
                if (record_type, shape["layerId"]) in {("FILL", 9), ("POLY", 48)}:
                    mechanical.append({"componentId": pid, "id": shape_id, "native": shape,
                                       "placementTransform": "mirrorY if bottom, then rotate and translate"})
        components.append({
            "id": pid, "uniqueId": seen["uniqueId"], "designator": seen["designator"],
            "device": seen["device"], "name": seen["name"], "footprintId": footprint_id,
            "x": native["x"], "y": native["y"], "rotationDeg": native["angle"], "layer": native["layerId"],
            "locked": native["locked"], "bbox": seen["bbox"], "pads": pads,
        })
    require(matched_nets == pad_nets.keys(), "Archive contains unresolved pad bindings")
    return components, cutouts, mechanical


def compare_copper(doc, live):
    verification = {}
    require(set(live["availability"].values()) == {"available"}, "Copper capture incomplete")
    for native_type, category in DUMP_CATEGORIES.items():
        rows = index_rows(live[category], "primitiveId", category)
        native = doc.get(native_type, {})
        require(rows.keys() <= native.keys(), f"{category} contains objects absent from archive")
        archive_only = sorted(native.keys() - rows.keys())
        if native_type == "LINE":
            for pid in archive_only:
                v = native[pid]
                length = math.dist((v["startX"], v["startY"]), (v["endX"], v["endY"]))
                require(length < 0.15, f"Archive line missing from capture is not sub-resolution: {pid}")
        else:
            require(not archive_only, f"{category} archive objects absent from capture: {archive_only}")
        for pid, captured in rows.items():
            record = native[pid]
            fields = {
                "LINE": {"layer": "layerId", "net": "netName", "lineWidth": "width", "locked": "locked",
                         "startX": "startX", "startY": "startY", "endX": "endX", "endY": "endY"},
                "VIA": {"x": "centerX", "y": "centerY", "net": "netName", "diameter": "viaDiameter",
                        "holeDiameter": "holeDiameter", "locked": "locked"},
                "REGION": {"layer": "layerId", "lineWidth": "width", "locked": "locked"},
            }.get(native_type, {})
            for live_key, native_key in fields.items():
                a, b = captured[live_key], record[native_key]
                agree = math.isclose(a, b, rel_tol=0, abs_tol=1e-8) if type(a) in (int, float) else a == b
                require(agree, f"{category} {pid} disagrees on {live_key}: {a} vs {b}")
            if native_type == "REGION":
                require(captured["geometryAvailable"] and [captured["source"]] == record["path"],
                        f"{category} {pid} path mismatch")
        verification[category] = {"archive": len(native), "editor": len(rows), "archiveOnlyIds": archive_only}
    return verification


def normalize_copper(doc):
    vias = keyed_rows(doc["VIA"])
    span_defs = doc["RULE"]['["RULE","BLIND","blindVia"]']["ruleContext"]["blinds"]["content"]
    rule_by_name = index_rows(span_defs, "name", "blind span rules")
    for v in vias:
        if v["viaType"] == "NORMAL":
            span = list(COPPER_ORDER)
        else:
            require(v["viaType"] in {"BLIND", "BURIED"} and v["ruleName"] in rule_by_name,
                    f"{v['id']} via layer span unknown")
            rule = rule_by_name[v["ruleName"]]
            start, stop = sorted(COPPER_ORDER.index(rule[k]) for k in ("staLayerId", "endLayerId"))
            span = list(COPPER_ORDER[start:stop + 1])
        require(set(v.get("unusedInnerLayers", [])) <= set(span[1:-1]),
                f"{v['id']} has invalid omitted layers")
        v["drillSpanLayerIds"] = span
        v["copperLayerIds"] = [layer for layer in span if layer not in v.get("unusedInnerLayers", [])]
    planes = []
    for key, block in sorted(doc["LAYER_FILL"].items()):
        for index, v in enumerate(block["fill"]):
            ring, *cutouts = [polyline_points(path) for path in v["path"]]
            planes.append({"id": f"{key}:{index}", "layerId": v["layerId"], "net": v["netName"],
                           "outerRing": ring, "voidRings": cutouts, "native": v})
    require({p["layerId"] for p in planes} == {15, 18}, "Expected materialized L2/L5 copper")
    return {"tracks": keyed_rows(doc["LINE"]), "arcs": keyed_rows(doc.get("ARC", {})), "vias": vias,
            "planes": planes, "pours": keyed_rows(doc.get("POUR", {})),
            "poured": keyed_rows(doc.get("POURED", {})), "fills": keyed_rows(doc.get("FILL", {}))}, span_defs


def build_board(name, uuid, doc, documents, capture_path, netlist_path):
    live = read_json(capture_path)
    capture = live["capture"]
    require(capture["documentUuid"] == uuid and capture["identityVerified"] is True
            and capture["documentType"] == "pcb", f"{name} editable document identity unverified")
    for k in ("components", "copper", "layers", "outline", "routedLines", "rules"):
        require(live["availability"][k] == "available", f"{name} {k} unavailable")
    require(live["copperLayers"] == len(COPPER_ORDER), f"{name} copper layer count mismatch")
    native_layers = {v["layerId"]: v for v in doc["LAYER"].values() if v["use"]}
    layer_rows = [native_layers[i] for i in COPPER_ORDER]
    require([v["layerType"] for v in layer_rows] == ["TOP", "PLANE", "SIGNAL", "SIGNAL", "PLANE", "BOTTOM"],
            f"{name} native stack layer role mismatch")
    physical = keyed_rows(doc["LAYER_PHYS"])
    # Missing rows on a logical copper layer are retained as explicit gaps.
    physical_layer_ids = {json.loads(row["id"])[1] for row in physical}
    canvas = doc["CANVAS"]["CANVAS"]
    require(canvas["unit"] == "mil" and canvas["originX"] == canvas["originY"] == 0,
            f"{name} requires a nonzero origin transform")
    outlines = [v for v in keyed_rows(doc["POLY"]) if v["layerId"] == 11]
    require(len(outlines) == 1, f"{name} unsupported outline structure")
    ring = polyline_points(outlines[0]["path"])
    require(ring[0] == ring[-1] and set(map(tuple, ring[:-1])) == set(map(tuple, live["outline"]["points"])),
            f"{name} archive and editor outline coordinates disagree")
    components, cutouts, mechanical = native_components(doc, documents, live["components"])
    copper_verification = compare_copper(doc, live["copper"])
    copper, spans = normalize_copper(doc)
    keepouts = [dict(row, rings=[polyline_points(p) for p in row["path"]])
                for row in keyed_rows(doc.get("REGION", {})) if row["regionType"] == "PROHIBIT"]
    classification = defaultdict(list)
    for c in components:
        for p in c["pads"]:
            classification[p["net"]].append(p["id"])
    copper_members = defaultdict(list)
    for category in ("tracks", "vias", "arcs"):
        for obj in copper[category]:
            copper_members[obj["netName"] or None].append(obj["id"])
    pin_and_copper_names = set(classification) | set(copper_members)
    def net_key(value):
        return value.casefold() if value is not None else None

    observed_names = {net_key(name): name for name in pin_and_copper_names}
    require(len(observed_names) == len(pin_and_copper_names), f"{name} ambiguous observed net case aliases")
    declaration_names = {net_key(json.loads(key)[1] or None) for key in doc["NET"]}
    require(declaration_names >= set(observed_names), f"{name} copper or pad assigned to undeclared net")
    require(len(declaration_names) == len(doc["NET"]), f"{name} ambiguous native net declarations")
    net_rows = []
    for declaration_id, declaration in sorted(doc["NET"].items()):
        declared = json.loads(declaration_id)[1] or None
        actual = observed_names.get(net_key(declared), declared)
        net_rows.append({"name": actual, "declaredNativeName": declared, "native": declaration,
                         "padIds": classification.get(actual, []), "copperIds": copper_members.get(actual, [])})
    net_names = {n["name"] for n in net_rows}
    netlist_raw = netlist_path.read_bytes()
    require(netlist_raw.decode("utf-8-sig").startswith("PROTEL NETLIST 2.0"),
            f"{name} expected native Protel 2.0 netlist")
    netlist_receipt = read_json(capture_path.parent / f"{name}-netlist.json")
    require(netlist_receipt["ok"] and netlist_receipt["result"]["netlistType"] == "Protel2"
            and netlist_receipt["context"]["projectUuid"] == capture["projectUuid"]
            and netlist_receipt["context"]["documentUuid"] == SCHEMATIC_PAGES[name]
            and any(a.get("sha256") == digest(netlist_raw) for a in netlist_receipt["artifacts"]),
            f"{name} schematic netlist receipt mismatch")
    erc_file = capture_path.parent / f"{name}-erc.json"
    drc_file = capture_path.parent / f"{name}-drc.json"
    erc = read_json(erc_file)["result"]
    drc = read_json(drc_file)
    require(erc["strict"] and erc["detailsAvailable"] and erc["countsAvailable"],
            f"{name} strict ERC evidence incomplete")
    require(drc.get("nativeResult") is not None and isinstance(drc.get("violations"), list)
            and sum(drc["counts"].values()) == len(drc["violations"]),
            f"{name} strict DRC evidence incomplete")
    data = {
        "schemaVersion": "zyd-p2-pcb/1", "board": name, "documentUuid": uuid,
        "nativeBoardUuid": doc["META"]["META"]["board"],
        "coordinates": {"unit": "mil", "mmPerMil": 0.0254, "yAxis": "up",
                        "nativeOrigin": [0, 0], "canvas": canvas},
        "outline": {"ring": ring, "native": outlines[0], "editorBBox": live["outline"]["bbox"]},
        "layers": {"topToBottom": layer_rows, "nativePhysicalRecords": physical,
                   "missingPhysicalCopperLayerRecords": [i for i in COPPER_ORDER if i not in physical_layer_ids],
                   "blockedPhysicalStack": "Native physical records lack inner copper/dielectrics; do not infer the approved 0.80 mm HDI stack."},
        "components": components, "footprintCutouts": cutouts, "footprintMechanicalSource": mechanical,
        "nativeDRCObjects": drc["violations"],
        "boardKeepouts": keepouts, "copper": copper, "nets": net_rows,
        "nativeConstraints": {
            "editorRuleSummary": live["rules"], "nativeRules": keyed_rows(doc["RULE"]),
            "nativeRuleTemplates": keyed_rows(doc["RULE_TEMPLATE"]), "viaSpanRules": spans,
            "values": "Board coordinates are mil. Preserve archive rule unit tags and native numeric fields without converting.",
        },
        "sources": {
            "captureFileSha256": digest(capture_path.read_bytes()),
            "captureSemanticSha256ReportedByCLI": live["semanticSha256"],
            "captureProjectUuid": capture["projectUuid"], "captureRangeUtc": [capture["startedAt"], capture["completedAt"]],
            "nativeProtel2Sha256": digest(netlist_raw), "strictERCFileSha256": digest(erc_file.read_bytes()),
            "strictDRCFileSha256": digest(drc_file.read_bytes()),
        },
        "coverage": {
            "componentPadsMatchByNativeId": True, "copperArchiveVersusEditor": copper_verification,
            "powerPlaneGeometry": "Native LAYER_FILL rings including voids; EasyEDA copper dump listed zero such planes.",
            "polygonPadsWithHoleReadbackButNoNativePadDrill": sum(
                p["shape"]["kind"] == "POLYGON" and bool(p["editorHoleReadback"]) and not p["nativeHole"]
                for c in components for p in c["pads"]),
            "strictERC": erc["summary"], "strictDRC": drc["counts"],
            "limitations": ["PCB-mode body bbox and footprint assembly paths do not establish enclosure clearance.",
                            "Empty PCB pad nets are represented by null. NC is a separate schematic property.",
                            "Board keepouts cover persisted REGION PROHIBIT, not enclosure or supplier zones."],
        },
    }
    counts = {"components": len(components), "pads": sum(len(c["pads"]) for c in components),
              "assignedPads": sum(bool(p["net"]) for c in components for p in c["pads"]),
              "uniqueAssignedDesignatorPadNumbers": len({
                  (c["designator"], p["number"]) for c in components for p in c["pads"] if p["net"]
              }),
              "namedNets": len(net_names - {None}), "tracks": len(copper["tracks"]), "vias": len(copper["vias"]),
              "blindVias": sum(v["viaType"] == "BLIND" for v in copper["vias"]), "keepouts": len(keepouts),
              "planePolygons": len(copper["planes"]), "footprintCutouts": len(cutouts),
              "connectionErrors": drc["counts"].get("Connection Error", 0)}
    return data, counts, netlist_raw


def editor_readback(data, directory):
    """Attach verified editor layer and per-net rule assignment receipts."""
    name = data["board"]
    for kind in ("rules", "stackup"):
        path = directory / f"{name}-{kind}.json"
        receipt = read_json(path)
        context = receipt["context"]
        require(receipt["ok"] is True and context["documentType"] == "pcb"
                and context["projectUuid"] == data["sources"]["captureProjectUuid"]
                and context["documentUuid"] == data["documentUuid"],
                f"{name} {kind} receipt did not target the captured board")
        result = receipt["result"]
        data["sources"][f"online{kind.capitalize()}ReceiptSha256"] = digest(path.read_bytes())
        if kind == "stackup":
            layers = {row["id"]: row for row in result["layers"]}
            selected = [layers[i] for i in COPPER_ORDER]
            require(result["copperLayerCount"] == len(COPPER_ORDER)
                    and [v["type"] for v in selected] == ["SIGNAL", "PLANE", "SIGNAL", "SIGNAL", "PLANE", "SIGNAL"],
                    f"{name} logical layer readback differs from EPRU")
            data["layers"]["editorLogicalCopperLayers"] = selected
            continue
        names = {row["name"].casefold() for row in result["netRules"]}
        require(names == {row["name"].casefold() for row in data["nets"] if row["name"]},
                f"{name} per-net rule assignment list differs from native NET inventory")
        data["nativeConstraints"]["editorNetRuleConfiguration"] = result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--readback-dir", type=Path, help="Verified editor PCB rules and stackup receipts")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--capture-class", required=True, choices=("fresh-native-import", "r11-milestone-native"))
    args = parser.parse_args()
    require(args.archive_sha256.isascii() and len(args.archive_sha256) == 64
            and digest(args.archive.read_bytes()) == args.archive_sha256, "Native archive SHA-256 mismatch")
    require(len(args.source_commit) == 40 and set(args.source_commit) <= set("0123456789abcdef"), "Expected Git SHA")
    documents, version = native_documents(args.archive)
    pcbs = {doc["META"]["META"]["title"]: (uuid, doc) for (kind, uuid), doc in documents.items() if kind == "PCB"}
    require(set(pcbs) == set(BOARDS), f"Unexpected EPRO PCB document titles: {set(pcbs)}")
    summary, results, projects = {}, {}, set()
    for board in BOARDS:
        data, counts, protel = build_board(board, *pcbs[board], documents,
                                           args.capture_dir / f"{board}-copper.json",
                                           args.capture_dir / f"{board}.net")
        if args.readback_dir is not None:
            editor_readback(data, args.readback_dir)
        projects.add(data["sources"]["captureProjectUuid"])
        results[board] = data, counts, protel
    require(len(projects) == 1, "Mixed project UUIDs across three board captures")
    args.out.mkdir(parents=True, exist_ok=False)
    manifest_files = {}
    for board, (data, counts, protel) in results.items():
        geometry_file = args.out / f"{board}.json"
        write_json(geometry_file, data, compact=True)
        netlist_file = args.out / f"{board}.net"
        netlist_file.write_bytes(protel)
        for path in (geometry_file, netlist_file):
            manifest_files[path.name] = digest(path.read_bytes())
        summary[board] = counts
    manifest = {
        "schemaVersion": "zyd-p2-manifest/1", "status": "NOT FOR FAB", "sourceCommit": args.source_commit,
        "nativeArchiveSha256": args.archive_sha256, "editorArchiveVersion": version, "captureClass": args.capture_class,
        "captureProjectUuid": next(iter(projects)), "boardCounts": summary, "fileSha256": manifest_files,
        "frozenRequirements": {"productMassTargetG": 40, "trueBinocularTransparentAR": True,
                               "targetHDIStackThicknessMm": 0.80, "layout": "high-density", "fabApproval": False},
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
