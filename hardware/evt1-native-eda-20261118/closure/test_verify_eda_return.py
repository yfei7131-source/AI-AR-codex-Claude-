import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import verify_eda_return as checker


CAPTURE = Path(__file__).resolve().parent / "evidence/jlc-import"


class EasyEDAEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terminals, cls.parts = checker.baseline(checker.PACKAGE)

    def test_native_schematic_nets_and_nc_by_board(self):
        result = checker.compare_schematic(self.terminals, self.parts, CAPTURE)
        self.assertEqual(result["named_terminal_parity"], "PASS")
        self.assertEqual({board: row["observed"] for board, row in result["board_counts"].items()},
                         {"M-MAIN-L": 524, "M-OPT-BRIDGE": 315, "M-AUD-R": 236})
        self.assertEqual(result["expected_nc_markers"], 92)
        self.assertEqual(result["unverified_nc_markers"], 0)
        self.assertEqual(result["bom"]["status"], "BLOCKED")
        self.assertEqual(len(result["schematic_footprints"]["missing"]), 114)
        self.assertEqual(result["schematic_pcb_flags"]["status"], "FAIL")
        self.assertEqual({tuple(item["component"]) for item in result["schematic_pcb_flags"]["mismatches"]},
                         {("M-AUD-R", "BAT1"), ("M-AUD-R", "SPK1"), ("M-MAIN-L", "BAT1"), ("M-MAIN-L", "SPK1")})

    def test_known_scope_and_native_erc_failures(self):
        self.assertEqual(checker.compare_bindings(CAPTURE)["status"], "FAIL")
        erc = checker.strict_erc(CAPTURE)
        self.assertEqual(erc["status"], "FAIL")
        self.assertEqual(erc["reported_calls"], 21)
        self.assertEqual(erc["failed_calls"], 21)
        self.assertEqual(erc["reported_findings_by_rule"]["MISSFOOTPRINT"], 506)

    def test_partial_pcb_does_not_pass(self):
        result = checker.compare_pcb(self.terminals, self.parts, checker.PACKAGE / "kimi-return/native/restored-readback")
        self.assertTrue(all(board["status"] == "BLOCKED" for board in result.values()))
        self.assertEqual(sum(board["observed_components"] for board in result.values()), 35)
        self.assertEqual(sum(board["overlapping_terminal_identifiers"] for board in result.values()), 393)

    def test_disconnected_pin_is_distinct_from_nc_and_missing_page(self):
        manifest = checker.read_json(CAPTURE / "board_pages.json")
        page = manifest["boards"]["M-AUD-R"][0]
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / "capture"
            shutil.copytree(CAPTURE, data)
            path = data / "sch" / f"{page}.json"
            wire = checker.read_json(path)
            removed = wire["connections"].pop(0)
            path.write_text(json.dumps(wire), encoding="utf-8")
            invalid = checker.compare_schematic(self.terminals, self.parts, data)
            self.assertEqual(invalid["named_terminal_parity"], "FAIL")
            self.assertTrue(any(item.get("observed_net") == "" and item["terminal"][2] == removed["pinNumber"]
                                for item in invalid["net_or_nc_mismatches"]))
            path.unlink()
            incomplete = checker.compare_schematic(self.terminals, self.parts, data)
            self.assertEqual(incomplete["named_terminal_parity"], "BLOCKED")
            self.assertGreater(len(incomplete["missing_terminals"]), 0)

    def test_utf16_and_utf8_bom_fields(self):
        sample = "Designator\tManufacturer Part\tFootprint\r\nU1\t假设料号\tSOT\r\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bom.csv"
            for encoding in ("utf-16", "utf-8-sig"):
                with self.subTest(encoding=encoding):
                    path.write_bytes(sample.encode(encoding))
                    self.assertEqual(checker.read_native_bom(path)[0]["Manufacturer Part"], "假设料号")

    def test_cli_preserves_fail_and_emits_platform_independent_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            result = subprocess.run([sys.executable, checker.__file__, "--schematic", str(CAPTURE), "--pcb",
                                     str(checker.PACKAGE / "kimi-return/native/restored-readback"),
                                     "--output", str(path)], capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr.decode(errors="replace"))
            self.assertEqual(json.loads(path.read_bytes())["status"], "FAIL")
            self.assertNotIn(b"\r\n", path.read_bytes())


if __name__ == "__main__":
    unittest.main()
