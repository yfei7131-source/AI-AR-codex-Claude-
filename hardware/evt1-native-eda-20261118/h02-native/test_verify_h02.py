"""Exercise board scope, actual partition comparison and prior-return regressions."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_catalog_plan import classification
from verify_h02 import PACKAGE, audit, export_digest, graph_diff, parse_protel


class H02VerifierTest(unittest.TestCase):
    def test_raw_groups_retain_partition_identity(self):
        expected = {"GND": {("U1", "1"), ("R2", "2")},
                    "VSYS": {("U1", "2"), ("C1", "PWR1")}}
        text = "[\nU1\nQFN\n]\n(\n GND\n U1-1\n R2-2 4k7 Passive\n)\n(\nVSYS\nU1-2\nC1-PWR1\n)\n"
        components, groups = parse_protel(text)
        self.assertEqual(components, [{"designator": "U1", "convert_to_pcb": None}])
        self.assertEqual(graph_diff(expected, groups)["status"], "PASS")

        # Same complete labels/pins after flattening, different electrical groups.
        repeated = text.replace(" U1-1\n R2-2", " U1-1\n)\n(\nGND\n R2-2")
        bad = graph_diff(expected, parse_protel(repeated)[1])
        self.assertEqual(bad["status"], "FAIL")
        self.assertEqual(bad["physical_partition_status"], "FAIL")
        self.assertEqual(bad["net_differences"][0]["native_group_ids"], [1, 2])
        self.assertEqual(bad["net_differences"][0]["missing_members"], [])
        self.assertEqual(bad["net_differences"][0]["unexpected_members"], [])
        alias = graph_diff(expected, parse_protel(text.replace(" GND", " EVT1_#FLG01_SUPPLY_ORIGIN"))[1])
        self.assertEqual(alias["status"], "FAIL")
        self.assertEqual(alias["physical_partition_status"], "PASS")
        self.assertEqual(alias["equivalent_renamed_groups"][0]["controlled"], "GND")

    def test_duplicate_members_and_nc_not_conflated(self):
        expected = {"GND": {("R1", "1"), ("R2", "1")}}
        native = [("GND", [("R1", "1"), ("R2", "1"), ("R2", "1")]), ("N", [("U1", "P1")])]
        report = graph_diff(expected, native)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["duplicate_members"][0]["member"], ("R2", "1"))
        self.assertEqual(report["net_differences"][0]["unexpected_members"], [("U1", "P1")])

    def test_export_bound_to_bytes_and_context(self):
        with TemporaryDirectory() as directory:
            file = Path(directory) / "board.net"
            content = b"(\nGND\nC1-2\nU1-3\n)\n"
            file.write_bytes(content)
            sha = hashlib.sha256(content).hexdigest()
            receipt = {"ok": True, "result": {"artifactId": "a"},
                       "context": {"documentType": "schematic", "projectUuid": "expected", "documentUuid": "root"},
                       "artifacts": [{"id": "a", "kind": "schematic_netlist", "sha256": sha, "size": len(content)}]}
            self.assertEqual(export_digest(file, receipt, "expected", "root", "schematic_netlist"), sha)
            with self.assertRaises(ValueError):
                export_digest(file, receipt, "expected", "child", "schematic_netlist")
            file.write_bytes(content.replace(b"U1-3", b"U1-4"))
            with self.assertRaises(ValueError):
                export_digest(file, receipt, "expected", "root", "schematic_netlist")

    def test_mpn_diagnostics_ignore_generic_and_clustered_text(self):
        self.assertEqual(classification({"MPN": "22uF X7R 6.3V"}, "C_SAMPLE", "BOARD")[:2],
                         ("PASSIVE_DESCRIPTOR", ""))
        self.assertEqual(classification({"MPN": "ERA-2AEB2R2X"}, "R_SENSE", "BOARD")[:2],
                         ("ORDERING_BLOCKED", ""))
        self.assertEqual(classification({"MPN": "BM28B0.6-10DS/2-0.35V(53)"}, "J_DISP_L", "BOARD")[:2],
                         ("EXACT_ID", "BM28B0.6-10DS/2-0.35V(53)"))

    def test_actual_pr33_report_cannot_promote_legacy_labels(self):
        folder = PACKAGE / "kimi-h02-return/partial-current-coherent"
        report = audit(PACKAGE, folder)
        self.assertEqual(report["page_terminal_labels"]["named_terminal_parity"], "PASS")
        self.assertEqual(report["page_terminal_labels"]["expected_nc_markers"], 92)
        self.assertEqual(report["board_document_registry"]["status"], "FAIL")
        self.assertEqual(report["native_exact_identity_and_selection"]["legacy_literal_coverage"]["present"], 172)
        self.assertEqual(report["native_exact_identity_and_selection"]["exact_field_mismatches"][0]["component"],
                         ("M-MAIN-L", "L2"))
        scope = report["board_native_membership"]
        self.assertEqual([v["status"] for v in scope.values()], ["BLOCKED"] * 3)
        self.assertEqual(sum(v["expected_net_groups"] for v in scope.values()), 201)
        self.assertEqual(sum(v["expected_connected_board_pins"] for v in scope.values()), 971)

    def test_actual_candidate_proves_groups_and_retains_erc_failure(self):
        directory = Path(__file__).resolve().parent / "evidence/native-C"
        report = audit(PACKAGE, directory)
        self.assertEqual(report["board_document_registry"]["status"], "PASS")
        self.assertEqual({b: r["status"] for b, r in report["board_native_membership"].items()},
                         {"M-MAIN-L": "PASS", "M-OPT-BRIDGE": "PASS", "M-AUD-R": "PASS"})
        self.assertEqual(report["page_terminal_labels"]["expected_nc_markers"], 92)
        self.assertEqual(report["page_terminal_labels"]["marker_files"], 16)
        archive = report["persistence_and_archive"]
        self.assertEqual(archive["archived_terminal_identifiers_verified"], 1075)
        self.assertEqual(archive["archived_explicit_nc_verified"], 92)
        self.assertEqual(archive["catalog_fields_verified"], 52)
        self.assertEqual(report["strict_erc"]["status"], "FAIL")
        self.assertEqual(report["acceptance"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
