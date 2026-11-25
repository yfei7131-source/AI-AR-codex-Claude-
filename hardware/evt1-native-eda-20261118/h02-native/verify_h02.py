#!/usr/bin/env python3
"""Audit H02 page labels, board-wide native net membership and BOM evidence independently."""

import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import re
import sys

from build_catalog_plan import classification

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_eda_return", PACKAGE / "closure/verify_eda_return.py")
PR31 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PR31)
SEVERITY = {"PASS": 0, "UNVERIFIED": 1, "BLOCKED": 2, "FAIL": 3}
PIN_TOKEN = re.compile(r"^([A-Za-z0-9_]+)-([A-Za-z0-9_.+-]+)(?:\s|$)")


def worse(*states):
    return max(states, key=SEVERITY.__getitem__)


def context_ok(receipt, project, page=None):
    context = receipt.get("context", {})
    return (receipt.get("ok") is True and context.get("projectUuid") == project
            and (page is None or (context.get("documentUuid") == page
                                  and context.get("documentType") == "schematic")))


def parse_protel(text):
    """Consume each native Protel2 group separately, even with duplicate printed labels."""
    components, groups = [], []
    opening = None
    contents = []
    for line in text.splitlines():
        item = line.strip()
        if not item:
            continue
        if opening is None:
            if item in ("[", "("):
                opening = item
                contents = []
            elif item.upper() not in ("PROTEL NETLIST", "PROTEL NETLIST 2.0", "PROTEL NETLIST FORMAT 2.0"):
                raise ValueError(f"Unexpected top-level Protel2 record {item[:80]!r}")
        elif item == {"[": "]", "(": ")"}[opening]:
            if not contents:
                raise ValueError("Empty Protel2 block")
            if opening == "[":
                if contents[0] == "DESIGNATOR":
                    if len(contents) < 2:
                        raise ValueError("Protel2 component omits designator")
                    designator = contents[1]
                else:
                    designator = contents[0]
                pcb_values = [contents[i+1].lower() for i, key in enumerate(contents[:-1]) if key == "Convert to PCB"]
                pcb_of = {"yes": True, "no": False}
                if len(pcb_values) > 1 or (pcb_values and pcb_values[0] not in pcb_of):
                    raise ValueError(f"Ambiguous Protel2 Convert to PCB field: {designator}")
                components.append({"designator": designator,
                                   "convert_to_pcb": pcb_of[pcb_values[0]] if pcb_values else None})
            else:
                label, *nodes = contents
                members = []
                for node in nodes:
                    match = PIN_TOKEN.match(node)
                    if not match:
                        raise ValueError(f"Invalid component-pin token {node[:80]!r}")
                    members.append(match.groups())
                groups.append((label, members))
            opening = None
        else:
            contents.append(item)
    if opening is not None or not groups:
        raise ValueError("Incomplete Protel2 export or no native net groups")
    return components, groups


def expected_graph(terms, board, *, include_external=False):
    groups = defaultdict(set)
    for (b, ref, pin), row in terms.items():
        if b == board and (row["PCB_Use"] == "BOARD" or include_external) and row["Local_State"] == "CONNECTED":
            net = row["CAD_Net"]
            if not net:
                raise ValueError(f"Connected controlled terminal without CAD_Net: {board}/{ref}.{pin}")
            groups[net].add((ref, pin))
    return dict(groups)


def graph_diff(expected, raw_groups):
    observed_by_label = defaultdict(list)
    occurrences = defaultdict(list)
    for identity, (label, members) in enumerate(raw_groups, start=1):
        for member in members:
            occurrences[member].append(identity)
        observed_by_label[label].append((identity, set(members)))
    findings = []
    for label in sorted(expected.keys() | observed_by_label.keys()):
        want = expected.get(label, set())
        records = observed_by_label[label]
        actual = set().union(*(members for _, members in records))
        if len(records) != 1 or want != actual:
            findings.append({
                "net": label, "native_group_ids": [i for i, _ in records],
                "missing_members": sorted(want - actual), "unexpected_members": sorted(actual - want),
            })
    duplicate = [{"member": m, "records": ids} for m, ids in sorted(occurrences.items()) if len(ids) > 1]
    membership_index = defaultdict(list)
    for identity, (label, members) in enumerate(raw_groups, start=1):
        membership_index[frozenset(members)].append((identity, label))
    equivalent = {}
    for name, want in sorted(expected.items()):
        possible = membership_index[frozenset(want)]
        if len(possible) == 1:
            equivalent[name] = possible[0]
    same_partition = (len(equivalent) == len(expected) == len(raw_groups)
                      and len({identity for identity, _ in equivalent.values()}) == len(raw_groups)
                      and not duplicate)
    aliases = [{"controlled": net, "native_label": name, "native_group_id": identity}
               for net, (identity, name) in equivalent.items() if net != name]
    return {"status": "FAIL" if findings or duplicate else "PASS",
            "physical_partition_status": "PASS" if same_partition else "FAIL",
            "compiled_names_status": "FAIL" if findings or duplicate else "PASS", "equivalent_renamed_groups": aliases,
            "expected_net_groups": len(expected), "observed_net_groups": len(raw_groups),
            "expected_connected_board_pins": sum(len(group) for group in expected.values()),
            "observed_unique_members": len(occurrences), "net_differences": findings, "duplicate_members": duplicate}


def inventory(directory, manifest):
    paths = [directory / name for name in ("lceda-boards.json", "lceda-pages.json")]
    if not all(path.is_file() for path in paths):
        return {}, {"status": "BLOCKED", "reason": "Native board and page registry receipts are required."}
    project = manifest["project_id"]
    boards, pages = (PR31.read_json(path) for path in paths)
    if not all(context_ok(result, project) for result in (boards, pages)):
        raise ValueError("Registry does not describe the captured project")
    by_name = PR31.index(boards["result"]["boards"], lambda row: row["name"])
    by_page = PR31.index(pages["result"]["pages"], lambda row: row["uuid"])
    results, identifiers = {}, defaultdict(list)
    for board, name in PR31.BOARDS.items():
        entity = by_name.get(name, {})
        parent = entity.get("schematicUuid")
        pcb = entity.get("pcbUuid")
        if pcb:
            identifiers["pcb", pcb].append(board)
        if parent:
            identifiers["schematic", parent].append(board)
        assigned = set(manifest["boards"][board])
        native = {page for page, record in by_page.items() if parent and record.get("parentSchematicUuid") == parent}
        outside, extra = sorted(assigned - native), sorted(native - assigned)
        state = "FAIL" if outside or extra else "PASS" if parent and pcb else "BLOCKED"
        results[board] = {"status": state, "schematic_scope": "FAIL" if outside or extra else "PASS",
                          "schematic_uuid": parent, "pcb_uuid": pcb,
                          "declared_pages": sorted(assigned), "native_parent_pages": sorted(native),
                          "pages_outside_bound_schematic": outside, "undeclared_native_pages": extra}
    extra_boards = sorted(by_name.keys() - set(PR31.BOARDS.values()))
    all_declared = {page for row in results.values() for page in row["declared_pages"]}
    orphan_pages = sorted(by_page.keys() - all_declared)
    shared = [{"type": kind, "uuid": uuid, "boards": members}
              for (kind, uuid), members in sorted(identifiers.items()) if len(members) > 1]
    pcb_path = directory / "lceda-pcbs.json"
    pcb_inventory = {"status": "BLOCKED", "reason": "Independent native PCB-document registry missing."}
    if pcb_path.is_file():
        receipt = PR31.read_json(pcb_path)
        if not context_ok(receipt, project):
            raise ValueError("PCB document registry does not describe the captured project")
        documents = PR31.index(receipt["result"]["pcbs"], lambda row: row["uuid"])
        if any(doc.get("parentProjectUuid") != project for doc in documents.values()):
            raise ValueError("PCB document belongs to a different project")
        bound = {row["pcb_uuid"] for row in results.values() if row["pcb_uuid"]}
        missing, extra = sorted(bound - documents.keys()), sorted(documents.keys() - bound)
        pcb_inventory = {"status": "FAIL" if missing or extra else "PASS",
                         "missing_bound_pcbs": missing, "extra_unbound_pcbs": extra, "native_pcb_count": len(documents)}
    topology = "FAIL" if extra_boards or orphan_pages or shared else "PASS"
    return results, {"status": worse(topology, *(row["status"] for row in results.values())),
                     "boards": results, "extra_boards": extra_boards, "undeclared_pages": orphan_pages,
                     "shared_board_documents": shared, "pcb_document_inventory": pcb_inventory}


def export_digest(path, response, project, page, kind):
    if not context_ok(response, project, page):
        raise ValueError(f"Export receipt targets another project or page: {path.name}")
    artifact_id = response.get("result", {}).get("artifactId")
    artifacts = [item for item in response.get("artifacts", [])
                 if artifact_id and item.get("id") == artifact_id and item.get("kind") == kind]
    sha = PR31.sha256(path)
    if len(artifacts) != 1 or artifacts[0].get("sha256") != sha or artifacts[0].get("size") != path.stat().st_size:
        raise ValueError(f"Artifact digest, kind or byte count disagrees with receipt: {path.name}")
    return sha


def board_membership(directory, manifest, terms, bindings):
    result = {}
    for board in PR31.BOARDS:
        wanted = expected_graph(terms, board)
        members = directory / "board-netlists" / f"{board}.net"
        receipt_path = members.with_suffix(".protel2.response.json")
        if not receipt_path.is_file():
            receipt_path = members.with_suffix(".response.json")
        expected_scope = {"expected_net_groups": len(wanted),
                          "expected_connected_board_pins": sum(map(len, wanted.values()))}
        if not members.is_file() or not receipt_path.is_file():
            result[board] = {"status": "BLOCKED", **expected_scope,
                             "reason": "No official native board Protel2 net group export and receipt pair."}
            continue
        response = PR31.read_json(receipt_path)
        page = response.get("context", {}).get("documentUuid")
        if page not in manifest["boards"][board]:
            raise ValueError(f"Protel2 receipt targets a page from a different registry group: {board}")
        sha = export_digest(members, response, manifest["project_id"], page, "schematic_netlist")
        registered = bindings.get(board, {})
        if registered.get("schematic_scope") != "PASS" or page not in registered["native_parent_pages"]:
            result[board] = {"status": "BLOCKED", **expected_scope, "native_export_sha256": sha,
                             "reason": "Active document does not belong to a complete registered board schematic."}
            continue
        blob = members.read_bytes()
        encoding = "utf-16" if blob.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        components, groups = parse_protel(blob.decode(encoding))
        full_graph = graph_diff(expected_graph(terms, board, include_external=True), groups)
        by_ref = PR31.index(components, lambda row: row["designator"])
        controlled_flags = {ref: row["PCB_Use"] == "BOARD" for (b, ref, _), row in terms.items() if b == board}
        bad_flags, missing = [], []
        for ref, expected in sorted(controlled_flags.items()):
            observed = by_ref.get(ref, {}).get("convert_to_pcb")
            if type(observed) is not bool:
                missing.append(ref)
            elif observed != expected:
                bad_flags.append({"component": ref, "expected": expected, "observed": observed})
        extra_refs = sorted(by_ref.keys() - controlled_flags.keys())
        flag_status = "FAIL" if bad_flags or extra_refs else "BLOCKED" if missing else "PASS"
        board_groups = [(label, [member for member in group if by_ref.get(member[0], {}).get("convert_to_pcb") is True])
                        for label, group in groups]
        # External-only native nets still participate in the complete schematic audit.
        diff = graph_diff(wanted, [(label, group) for label, group in board_groups if group])
        if flag_status != "PASS" and diff["status"] == "PASS":
            diff["status"] = flag_status
        diff["status"] = worse(diff["status"], flag_status, full_graph["status"])
        result[board] = {**diff, "native_export_sha256": sha,
                         "all_schematic_membership_including_external": full_graph,
                         "native_component_count": len(components),
                         "native_pcb_projection_flags": {"status": flag_status, "missing": missing,
                                                         "incorrect": bad_flags, "extra_refs": extra_refs}}
    return result


def procurement_and_fields(source, terms, parts, directory, manifest):
    bom = PR31.index(PR31.read_csv(source / "Inputs/effective_bom.csv"), lambda row: row["Item_ID"])
    owners = {key[:2]: row["BOM_Line"] for key, row in terms.items()}
    actual = {}
    for board, pages in manifest["boards"].items():
        for page in pages:
            raw = directory / "pins" / f"{page}.json"
            if not raw.is_file():
                continue
            evidence = PR31.read_json(raw)
            if not context_ok(evidence, manifest["project_id"], page):
                raise ValueError(f"Native component context mismatch at {page}")
            for item in evidence["result"]["components"]:
                if item.get("componentType") != "part" or not item.get("designator"):
                    continue
                key = (board, item["designator"])
                if key in actual:
                    raise ValueError(f"Duplicate raw board-scoped ref {key!r}")
                actual[key] = item
    legacy, exact, open_items, copper_features, stray_catalog_fields = [], [], [], [], []
    missing_native_footprint = []
    for key, part in sorted(parts.items()):
        if part["pcb_use"] != "BOARD":
            continue
        owner = bom[owners[key]]
        wanted = owner["MPN"].strip()
        native = actual.get(key, {})
        observed_mpn = native.get("manufacturerId")
        if part["footprint"] and not (native.get("footprint") or {}).get("uuid"):
            missing_native_footprint.append(key)
        if wanted and "TBD" not in wanted.upper():
            legacy.append(observed_mpn == wanted)
        if part["source_ref"].startswith("TP_"):
            copper_features.append(key)
            continue
        kind, selected, _ = classification(owner, part["source_ref"], part["pcb_use"])
        if not selected and observed_mpn:
            stray_catalog_fields.append({"component": key, "observed": observed_mpn, "classification": kind})
        if selected:
            exact.append({"component": key, "expected": selected, "observed": observed_mpn,
                          "match": observed_mpn == selected})
        if (not selected or not owner["Manufacturer"] or "TBD" in owner["Manufacturer"].upper()
                or owner["Verification_Status"].startswith(("BLOCKED", "OPEN"))):
            open_items.append({"component": key, "source_reference": part["source_ref"], "owner": owners[key],
                               "selection_status": owner["Verification_Status"]})
    mismatch = [row for row in exact if row["observed"] and not row["match"]]
    missing = [row["component"] for row in exact if not row["observed"]]
    return {
        "exact_identity_field_status": "FAIL" if mismatch else "BLOCKED" if missing else "PASS",
        "procurement_selection_status": "BLOCKED" if open_items else "PASS",
        "exact_candidate_fields_present": sum(row["match"] for row in exact),
        "exact_candidate_fields_expected": len(exact), "exact_candidates_missing": missing,
        "exact_candidate_fields_by_ref": exact,
        "exact_field_mismatches": mismatch, "unselected_or_unqualified_source_parts": open_items,
        "stray_catalog_fields": stray_catalog_fields,
        "pcb_features_without_order_codes": copper_features,
        "missing_native_footprint_uuid": missing_native_footprint,
        "legacy_literal_coverage": {"present": sum(legacy), "expected": len(legacy),
                                    "scope": "Field-text replication includes generic values and cluster descriptions."},
    }


def board_bom_coverage(directory, manifest, selection, bindings):
    results = {}
    for board in PR31.BOARDS:
        csv_path = directory / "board-boms" / f"{board}.csv"
        response_path = csv_path.with_suffix(".response.json")
        if not csv_path.is_file() or not response_path.is_file():
            results[board] = {"status": "BLOCKED", "reason": "No raw native board BOM export and receipt pair."}
            continue
        response = PR31.read_json(response_path)
        page = response.get("context", {}).get("documentUuid")
        if page not in manifest["boards"][board]:
            raise ValueError(f"BOM receipt targets a page from a different registry group: {board}")
        sha = export_digest(csv_path, response, manifest["project_id"], page, "schematic_bom")
        if bindings.get(board, {}).get("schematic_scope") != "PASS":
            results[board] = {"status": "BLOCKED", "native_bom_export_sha256": sha,
                              "reason": "Native board BOM does not have complete registered schematic scope."}
            continue
        rows = PR31.read_native_bom(csv_path)
        native = PR31.index(((ref.strip(), row["Manufacturer Part"].strip())
                             for row in rows for ref in row["Designator"].replace(";", ",").split(",")
                             if ref.strip()), lambda entry: entry[0])
        bad, missing = [], []
        for item in selection["exact_candidate_fields_by_ref"]:
            owner, ref = item["component"]
            if owner != board:
                continue
            actual = native.get(ref, ("", ""))[1]
            if not actual:
                missing.append(ref)
            elif actual != item["expected"]:
                bad.append({"component": ref, "expected": item["expected"], "observed": actual})
        results[board] = {"status": "FAIL" if bad else "BLOCKED" if missing else "PASS",
                          "native_bom_export_sha256": sha, "exact_mpn_missing": missing, "exact_mpn_mismatches": bad}
    return results


def audit(source, directory):
    terms, parts = PR31.baseline(source)
    manifest = PR31.read_json(directory / "board_pages.json")
    registered, binding_report = inventory(directory, manifest)
    page = PR31.compare_schematic(terms, parts, directory)
    graph = board_membership(directory, manifest, terms, registered)
    selection = procurement_and_fields(source, terms, parts, directory, manifest)
    board_bom = board_bom_coverage(directory, manifest, selection, registered)
    footprints_unqualified = sorted(key for key, part in parts.items()
                                    if part["pcb_use"] == "BOARD" and not part["footprint"])
    page_erc = PR31.strict_erc(directory)
    # Legacy reports may lack byte-bound context and overlap board-level calls.
    strict_context_missing = sorted(p for p in page_erc.get("reports", {})
                                    if not context_ok(PR31.read_json(directory / "erc" / f"{p}.json"),
                                                      manifest["project_id"], p))
    if strict_context_missing and page_erc["status"] == "PASS":
        page_erc["status"] = "BLOCKED"
    partial_summary = directory / "summary.json"
    final_capture = {"status": "BLOCKED", "reason": "No coherent save → reload → full native capture and restored archive proof."}
    if partial_summary.is_file():
        sample = PR31.read_json(partial_summary)
        if sample.get("captureModel"):
            final_capture["reported_capture_model"] = sample["captureModel"]
    proof = directory / "archive-verification.json"
    state = directory / "capture-state.json"
    if proof.is_file() and state.is_file():
        archive = PR31.read_json(proof)
        raw = PR31.read_json(directory / "archive-response.json")
        synced = (raw.get("ok") is True and archive.get("status") == "PASS"
                  and archive.get("project_id") == raw["result"].get("uuid") == manifest["project_id"]
                  and archive.get("persisted_sha256") == raw["result"].get("artifactSha256"))
        if synced:
            final_capture = {**archive, "live_page_capture": PR31.read_json(state)}
    missing_bom = [name for name in page["missing_exports"] if name.startswith("bom/")]
    bom_exports = {"status": "BLOCKED" if missing_bom else "PASS", "missing": missing_bom,
                   "scope": "Availability and parse of native BOM CSV. Separate from the exact identity and procurement checks."}
    states = [binding_report["status"], binding_report.get("pcb_document_inventory", {}).get("status", "BLOCKED"),
              page["named_terminal_parity"], page["schematic_pcb_flags"]["status"],
              page["schematic_footprints"]["status"], selection["exact_identity_field_status"],
              selection["procurement_selection_status"], page_erc["status"], final_capture["status"],
              *[row["status"] for row in graph.values()], *[row["status"] for row in board_bom.values()]]
    if footprints_unqualified or selection["missing_native_footprint_uuid"]:
        states.append("BLOCKED")
    return {
        "status": worse(*states), "acceptance": "BLOCKED",
        "scope": "Decoded official native manufacturing net-group membership, page labels and BOM diagnostics. PCB routing and manufacture retain their separate gate.",
        "project_id": manifest["project_id"], "source_coherence": "PASS",
        "controlled_sha256": {name: PR31.sha256(source / name) for name in
                              ("Inputs/effective_bom.csv", "Inputs/effective_netlist.csv",
                               "Inputs/effective_pinmap.csv", "kicad/CAD_TERMINALS.csv", "FOOTPRINT_MAP.csv")},
        "page_terminal_labels": {key: value for key, value in page.items() if key != "bom"},
        "board_document_registry": binding_report, "board_native_membership": graph,
        "native_exact_identity_and_selection": selection,
        "board_native_bom": board_bom, "page_bom_export_coverage": bom_exports,
        "source_footprint_blockers": footprints_unqualified, "strict_erc": page_erc,
        "strict_erc_missing_raw_project_page_context": strict_context_missing,
        "persistence_and_archive": final_capture,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PACKAGE)
    parser.add_argument("--schematic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.source, args.schematic)
    except (KeyError, TypeError, ValueError, OSError) as error:
        result = {"status": "FAIL", "acceptance": "BLOCKED", "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{result['status']}: H02 acceptance {result['acceptance']}")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "UNVERIFIED": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
