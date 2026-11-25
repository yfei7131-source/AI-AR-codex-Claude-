from copy import deepcopy
import unittest

from audit_electrical_residuals import INHERITED, audit, netlist_comparison, read
from verify_gnd_branch import REDUNDANT, guard_plan


class NativeResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit()["boards"]

    def test_inherited_net_membership_and_warnings(self):
        for board, net_count, placed_count, pins, airwires in (
            ("PCB1", 112, 118, 477, 358), ("PCB2", 58, 86, 303, 238), ("PCB3", 37, 53, 191, 134)
        ):
            observed = self.report[board]
            comparison = observed["netlistCrosscheck"]
            self.assertTrue(observed["protelByteIdenticalToPr46"])
            self.assertEqual(observed["strictDrcInherited"], {"Connection Error": airwires, "Netlist Error": 1})
            self.assertEqual((comparison["protelNetGroups"], comparison["placedComponentCount"],
                              comparison["placedNamedTerminalsCompared"]), (net_count, placed_count, pins))
            for field in ("pcbOnly", "placedUidMismatches", "placedPadNetMismatches"):
                self.assertEqual(comparison[field], [], f"{board}/{field}")
        missing = [item["EVT1 Source Ref"] for item in self.report["PCB1"]["netlistCrosscheck"]["schematicOnly"]
                   if item["convert_to_pcb"]]
        self.assertEqual(missing, ["J_CAM", "J_CHG"])

    def test_residual_heuristics_and_owner_loop(self):
        self.assertEqual([len(board["decouplingReview"]) for board in self.report.values()], [3, 10, 0])
        caps = {r["ref"]: r for r in self.report["PCB2"]["decouplingReview"]}
        self.assertEqual({name for name, row in caps.items() if row["role"] == "timing-rc"}, {"C2", "C3"})
        self.assertEqual(caps["C11"]["actualLoopTarget"], {
            "ref": "U13", "source": "U_AVDD_SYS_PG", "pin": "4", "function": "VDD"
        })
        self.assertGreater(self.report["PCB2"]["c11SingleMoveScreen"]["candidatesInOutlineAndWithinDistance"], 90_000)
        self.assertEqual(self.report["PCB2"]["c11SingleMoveScreen"]["componentBboxClearCandidates"], [])

    def test_detects_placed_net_corruption(self):
        board_dump = read(INHERITED / "reimport-verify/PCB3-reimport.dump.json")
        placed = next(c for c in board_dump["components"] if c["designator"] == "U11")
        pad = next(p for p in placed["pads"] if p["padNumber"] == "C2")
        pad["net"] = "1V8_SYS"
        comparison, _ = netlist_comparison(INHERITED / "erc-3board/board-netlists/M-AUD-R.net", board_dump)
        self.assertEqual(comparison["placedPadNetMismatches"], [
            {"ref": "U11", "pin": "C2", "schematicNet": "GND", "pcbNets": ["1V8_SYS"]}
        ])

    def test_duplicate_path_accepts_fixture_and_fails_on_drift(self):
        board_dump = read(INHERITED / "reimport-verify/PCB3-reimport.dump.json")
        guard_plan(board_dump)
        wrong = deepcopy(board_dump)
        branch = next(line for line in wrong["copper"]["lines"] if line["primitiveId"] in REDUNDANT)
        branch["startX"] += 0.2
        with self.assertRaisesRegex(ValueError, "geometry changed"):
            guard_plan(wrong)


if __name__ == "__main__":
    unittest.main()
