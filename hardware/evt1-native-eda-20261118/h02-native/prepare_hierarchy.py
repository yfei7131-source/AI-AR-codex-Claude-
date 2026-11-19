#!/usr/bin/env python3
"""Build an isolated EasyEDA Pro native candidate from the saved V4 archives."""

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile


PACKAGE = Path(__file__).resolve().parent.parent
HIERARCHY = PACKAGE / "kimi-h02-return/hierarchy/hierarchy-capability.json"
BRIDGE_PAGE = "2abf127033234e68"
MISLINK = "73f2bfaeffaf2767_$e00fbca5c08cc114~ie54_$2d94cb183ed4ccdc"
ORPHAN_BOARD = "1c580e292d25633c"
PCB_BINDINGS = {
    "8fbc3cae65886fe5": "cd81ce9bbcc08faf",  # left main
    "9ce45f14cb79dc9d": "a7c73e3e94e7757c",  # optical bridge
    "1db01a36f669a47a": "3e4e5d87c113e90e",  # right audio
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Record:
    def __init__(self, line):
        header, payload = line.split(b"||", 1)
        body = payload.removesuffix(b"\n")
        self.header = json.loads(header)
        self.payload = json.loads(body.removesuffix(b"|"))
        self.tail = payload[len(body.removesuffix(b"|")):]
        self.original = line
        self._header = copy.deepcopy(self.header)
        self._payload = copy.deepcopy(self.payload)

    def encode(self):
        if self.header == self._header and self.payload == self._payload:
            return self.original
        return compact(self.header) + b"||" + compact(self.payload) + self.tail


class Document:
    def __init__(self, head):
        self.records = [head]

    @property
    def key(self):
        head = self.records[0].payload
        return head["docType"], head["uuid"]

    def one(self, kind):
        items = [record for record in self.records if record.header["type"] == kind]
        if len(items) != 1:
            raise ValueError(f"{self.key}: expected exactly one {kind}, found {len(items)}")
        return items[0]

    def encode(self):
        return b"".join(record.encode() for record in self.records)


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.documents = {}
        with ZipFile(self.path) as archive:
            files = [name for name in archive.namelist() if name.endswith(".epru")]
            if len(files) != 1 or "project2.json" not in archive.namelist():
                raise ValueError("Expected native V4 project2.json and one EPRU record stream")
            self.stream = files[0]
            source = archive.read(self.stream)
        document = None
        for line in source.splitlines(keepends=True):
            record = Record(line)
            if record.header["type"] == "DOCHEAD":
                document = Document(record)
                if document.key in self.documents:
                    raise ValueError(f"Duplicate native document {document.key}")
                self.documents[document.key] = document
            elif document is not None:
                document.records.append(record)
            else:
                raise ValueError("Unexpected record before first DOCHEAD")
        if self.encode() != source:
            raise ValueError("Input record stream failed byte-preserving parse")

    def encode(self):
        chunks = [document.encode() for document in self.documents.values()]
        # A native export may omit the separator after its very last record.
        # If a detached donor document becomes internal, reinsert that separator.
        return b"".join(chunk if chunk.endswith(b"\n") or index == len(chunks) - 1
                        else chunk.removesuffix(b"|") + b"|\n" for index, chunk in enumerate(chunks))

    def write(self, output):
        with ZipFile(self.path) as source, ZipFile(output, "x") as target:
            target.comment = source.comment
            for item in source.infolist():
                data = self.encode() if item.filename == self.stream else source.read(item)
                target.writestr(copy.copy(item), data)


def rehome_pages(archive):
    controlled = json.loads(HIERARCHY.read_text(encoding="utf-8"))["observedHierarchy"]
    rows = [(board, row) for board, result in controlled.items() for row in result["pages"]]
    page_ids = {row["pageUuid"] for _, row in rows}
    if len(rows) != 21 or page_ids != {uuid for kind, uuid in archive.documents if kind == "SCH_PAGE"}:
        raise ValueError("Archived page coverage differs from the controlled H02 capture")
    destination = {row["expectedParent"] for _, row in rows}
    obsolete = {row["observedParent"] for _, row in rows} - destination
    if len(destination) != 3 or len(obsolete) != 18:
        raise ValueError("Unexpected H02 expected or orphan schematic count")
    edits = []
    for board, row in rows:
        page = archive.documents["SCH_PAGE", row["pageUuid"]]
        old, new = row["observedParent"], row["expectedParent"]
        meta = page.one("META")
        if meta.payload["schematic"] != old:
            raise ValueError(f"Unexpected original parent for {page.key}")
        if old == new:
            continue
        def active_rules(schematic):
            return {r.header["id"]: r.payload for r in archive.documents["SCH", schematic].records
                    if r.header["type"] == "RULE"}

        if active_rules(old) != active_rules(new):
            raise ValueError(f"Moving {page.key} would change its schematic design rules")
        meta.payload["schematic"] = new
        placeholders = [r for r in page.records if r.header["type"] == "META_PLACEHOLDER"]
        for record in placeholders:
            prefix, separator, suffix = record.header["id"].partition("_")
            if prefix != old or not separator or not suffix:
                raise ValueError(f"Unexpected page placeholder identity for {page.key}")
            record.header["id"] = new + separator + suffix
        edits.append({"board": board, "page": page.key[1], "prior_parent": old,
                      "new_parent": new, "placeholder_count": len(placeholders)})
    discard = {("SCH", uuid) for uuid in obsolete} | {("BOARD", ORPHAN_BOARD)}
    remaining = b"".join(d.encode() for key, d in archive.documents.items() if key not in discard)
    for key in sorted(discard):
        if key[1].encode("ascii") in remaining:
            raise ValueError(f"Orphan still referenced by a retained document: {key}")
        expected = {"DOCHEAD": 1, "META": 1}
        if key[0] == "SCH":
            expected["RULE"] = 2
        if Counter(r.header["type"] for r in archive.documents[key].records) != expected:
            raise ValueError(f"Orphan document contains unexpected content: {key}")
        del archive.documents[key]
    return edits, sorted(discard)


def repair_bridge_instance(archive):
    page = archive.documents["SCH_PAGE", BRIDGE_PAGE]
    flag_primitives = {
        r.payload["value"]: r.payload["parentId"]
        for r in page.records if r.header["type"] == "ATTR"
        and r.payload.get("key") == "Designator" and re.fullmatch(r"#FLG0[1-5]", r.payload["value"])
    }
    source = (PACKAGE / "kicad/evt1-optical-bridge/06-supply-origins-1.kicad_sch").read_text(encoding="utf-8")
    flag_ids = dict(re.findall(r'\(symbol \(lib_id "EVT1:(#FLG0[1-5])_SUPPLY_ORIGIN"\)[^\n]*\(uuid "([0-9a-f-]+)"\)', source))
    if len(flag_primitives) != 5 or flag_primitives.keys() != flag_ids.keys():
        raise ValueError("Could not reconcile all five native bridge supply-origin flags")
    wrong = ("INSTANCE", MISLINK)
    fixed = ("INSTANCE", MISLINK.rsplit("_$", 1)[0] + "_$" + BRIDGE_PAGE)
    if fixed in archive.documents:
        raise ValueError("Corrected bridge INSTANCE key would collide")
    document = archive.documents[wrong]
    attrs = [r for r in document.records if r.header["type"] == "INSTANCE_ATTR"]
    if {r.payload.get("Designator"): r.header.get("id") for r in attrs} != flag_ids:
        raise ValueError("Bridge INSTANCE_ATTR values do not match the source symbol UUIDs")
    document.one("DOCHEAD").payload["uuid"] = fixed[1]
    archive.documents = {fixed if key == wrong else key: d for key, d in archive.documents.items()}
    return {"from": wrong[1], "to": fixed[1], "retained_flag_uuids": flag_ids, "target_primitives": flag_primitives}


def attach_pcb_donor(archive, donor):
    for uuid, board_uuid in PCB_BINDINGS.items():
        if ("BOARD", board_uuid) not in archive.documents:
            raise ValueError(f"Missing destination board {board_uuid}")
        pcb = donor.documents["PCB", uuid]
        metadata = pcb.one("META")
        old = metadata.payload["board"]
        if ("BOARD", old) not in donor.documents or metadata.payload.get("parent"):
            raise ValueError(f"Donor PCB {uuid} is not a top-level board document")
        metadata.payload["board"] = board_uuid
    types = {"DEVICE", "SYMBOL", "FOOTPRINT", "BLOB"}
    detached = {k: d for k, d in donor.documents.items() if k[0] in types or k[0] == "PCB" and k[1] in PCB_BINDINGS}
    collisions = archive.documents.keys() & detached.keys()
    if collisions:
        raise ValueError(f"Unexpected donor document collisions: {sorted(collisions)}")
    config = archive.documents.pop(("CONFIG", "CONFIG"))
    archive.documents.update(detached)
    archive.documents[config.key] = config
    return {"sha256": digest(donor.path), "docs_read": len(donor.documents),
            "documents_copied": dict(Counter(kind for kind, _ in detached)), "pcb_bindings": PCB_BINDINGS}


def validate_instances(archive):
    pages = {uuid: page for (kind, uuid), page in archive.documents.items() if kind == "SCH_PAGE"}
    parents = {uuid: page.one("META").payload["schematic"] for uuid, page in pages.items()}
    instances = [uuid for kind, uuid in archive.documents if kind == "INSTANCE"]
    for uuid in instances:
        schematic, placement, child = uuid.split("_$")
        page, component = placement.split("~")
        primitives = [r.header.get("id") for r in pages[page].records if r.header["type"] == "COMPONENT"]
        if parents[page] != schematic or parents[child] != schematic or component not in primitives:
            raise ValueError(f"Instance path crosses a board boundary or points at a missing placement: {uuid}")
    if len(instances) != 18 or sorted(Counter(parents.values()).values()) != [6, 7, 8]:
        raise ValueError("Candidate hierarchy does not contain 18 in-board instances under the three target schematics")
    return len(instances)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pcb-archive", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    original_sha = digest(args.source)
    archive = Archive(args.source)
    before = {key: doc.encode() for key, doc in archive.documents.items()}
    changes, removed = rehome_pages(archive)
    instance = repair_bridge_instance(archive)
    instance_count = validate_instances(archive)
    donor = attach_pcb_donor(archive, Archive(args.pcb_archive)) if args.pcb_archive else None
    archive.write(args.output)
    roundtrip = Archive(args.output)
    if roundtrip.encode() != archive.encode() or digest(args.source) != original_sha:
        raise ValueError("Archive round trip or protected input validation failed")
    retained = [key for key, doc in archive.documents.items() if before.get(key) == doc.encode()]
    revised = [key for key in archive.documents if key in before and key not in retained]
    report = {"offline_archive": "PASS", "native_import_and_electrical_verification": "UNVERIFIED",
              "source_sha256": original_sha, "archive_sha256": digest(args.output),
              "byte_identical_documents": len(retained), "altered_retained_documents": sorted(revised),
              "removed_orphan_documents": removed, "parent_updates": changes, "instance_path_update": instance,
              "validated_in_board_instances": instance_count, "schematic_rules_before_and_after": "PASS",
              "pcb_donor": donor}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
