"""Regression for the checked-in bridge geometry gate and original failure."""

import json
import subprocess
import sys
import unittest

from check_bridge_placement import Box, HERE, SERIALIZATION_MM


class BridgePlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = HERE / "check_bridge_placement.py"
        cls.result = subprocess.run([sys.executable, str(script), "--check", "--strict"],
                                    capture_output=True, text=True, encoding="utf-8", check=False)
        cls.audit = json.loads((HERE / "evidence" / "bridge_placement.json").read_text(encoding="utf-8"))

    def test_strict_status_and_native_collision(self):
        self.assertEqual(self.result.returncode, 1, self.result.stderr)
        self.assertIn("geometry evidence reproduced", self.result.stdout)
        self.assertEqual(self.audit["archiveGeometryAgreement"], "PASS")
        self.assertEqual(self.audit["existingSnapshotStatus"], "FAIL")
        self.assertEqual(self.audit["placementClosure"], "BLOCKED")
        self.assertIn({"kind": "reservedSpace", "ref": "U8", "reserve": "J_BRIDGE_IN",
                       "layer": 2, "gapMm": 0.0}, self.audit["violations"])

    def test_original_and_privacy_occupied_search(self):
        before = self.audit["independentSearch"]
        after = self.audit["independentSearchWithPrivacyReservation"]
        self.assertEqual(sum(r["anchorsWithAllExistingObjectsFixed"] for r in before["U10"]), 54)
        for ref in ("U8", "U10", "U14"):
            self.assertEqual(sum(r["anchorsWithAllExistingObjectsFixed"] for r in after[ref]), 0)
        self.assertAlmostEqual(self.audit["copperEdgeMinimumMm"], .254)
        self.assertGreater(before["U8"][0]["copperWidthMm"], self.audit["widthAvailableForCopperMm"])

    def test_connector_manufacturer_bounds(self):
        connectors = self.audit["manufacturerConnectorEnvelopeAnalysis"]
        rows = {row["ref"]: row for row in connectors["orientations"]}
        self.assertAlmostEqual(rows["J_DISP_L"]["bodyMarginAtBaselineAnchorMm"], -.075, delta=SERIALIZATION_MM)
        self.assertAlmostEqual(rows["J_BRIDGE_IN"]["bodyMarginAtBaselineAnchorMm"], -.325, delta=SERIALIZATION_MM)
        self.assertEqual({ref["ref"] for ref in rows["J_DISP_L"]["projectedConflictRefs"]},
                         {"U13", "D3_PRIV_NOMINAL_BODY"})
        self.assertEqual({ref["ref"] for ref in rows["J_DISP_R"]["projectedConflictRefs"]}, {"U7"})
        trunk = connectors["trunkBeforeClock"]
        self.assertEqual(trunk["status"], "FAIL")
        self.assertAlmostEqual(trunk["lengthDeficitMm"], .32808)
        self.assertLess(trunk["availableRightLateralWidthMm"], trunk["requiredBodyWidthMm"])

    def test_copper_and_placement_margins_are_distinct(self):
        board = Box(0, 0, 4.2, 22)
        body = Box(.05, 1, 4.15, 2)
        pad_span = Box(.175, 1, 4.025, 2)
        self.assertGreater(board.inset(body), 0)
        self.assertLess(board.inset(pad_span), .254)


if __name__ == "__main__":
    unittest.main()
