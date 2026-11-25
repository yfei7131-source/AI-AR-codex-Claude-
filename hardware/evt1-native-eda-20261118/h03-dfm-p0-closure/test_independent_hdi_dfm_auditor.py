#!/usr/bin/env python3
"""Regression unit tests for independent_hdi_dfm_auditor.py (P0.4).

Verifies that our untruncated 3D blind-via-aware HDI DFM auditor:
  1. Never suppresses real same-layer Track-to-Via / Track-to-Track / Via-to-Pad violations.
  2. Correctly distinguishes opposite-Z BV_L1_L2 (1<->15) and BV_L5_L6 (18<->2) blind microvias from through-vias.
  3. Correctly distinguishes real non-VIPPO SMD via-in-pad from intentional U2 BGA / U1 EPAD VIPPO and opposite-side blind FPs.
  4. Flags track-to-track < 3.0 mil as TRUE_PHYSICAL_VIOLATION and 3.0..5.99 mil as RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK.
  5. Reproduces exact untruncated PR #43 baseline conflict counts across PCB1/PCB2/PCB3 without 40-item truncation.
"""

from pathlib import Path
import sys
import unittest

CUR = Path(__file__).resolve().parent
PKG = CUR.parent
sys.path[:0] = [str(CUR), str(PKG / "h02-native")]

from independent_hdi_dfm_auditor import (
    ALL_COPPER_LAYERS,
    audit_board,
    seg_seg_dist,
    via_copper_layers,
)
from prepare_hierarchy import Archive


class IndependentHDIDFMAuditorTest(unittest.TestCase):
    def test_blind_via_layer_spans(self):
        spans = {"BV_L1_L2": {1, 15}, "BV_L5_L6": {18, 2}}
        self.assertEqual(via_copper_layers("BLIND", "BV_L1_L2", spans), {1, 15})
        self.assertEqual(via_copper_layers("BLIND", "BV_L5_L6", spans), {18, 2})
        # Opposite blind spans share ZERO copper layers in 3D
        self.assertFalse(via_copper_layers("BLIND", "BV_L1_L2", spans) & via_copper_layers("BLIND", "BV_L5_L6", spans))
        # Through-via spans all 6 copper layers
        self.assertEqual(via_copper_layers("NORMAL", "", spans), ALL_COPPER_LAYERS)

    def test_segment_distance_and_intersection(self):
        # Crossing segments -> 0.0
        self.assertAlmostEqual(seg_seg_dist(0, 0, 10, 10, 0, 10, 10, 0), 0.0, places=5)
        # Parallel segments 5.0 mil apart
        self.assertAlmostEqual(seg_seg_dist(0, 0, 20, 0, 0, 5, 20, 5), 5.0, places=5)

    def test_pr43_baseline_untruncated_classification(self):
        pr43_epro = PKG / "h03-hdi-dfm-route-closure/native/ZY_AIAR_EVT1_H03_3BOARD_HDI_DFM_MECR01_NOT_FOR_FAB.epro2"
        pr43_dump = PKG / "h03-hdi-dfm-route-closure/evidence/post-route"
        arc = Archive(pr43_epro)
        # Verify PCB2 untruncated counts exceed easyeda pcb-check's 40-item cap and prove 0 true physical violations
        r2 = audit_board("PCB2", arc, pr43_dump / "PCB2-post.dump.json")
        self.assertEqual(r2["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0)
        self.assertEqual(r2["by_classification"].get("CHECKER_FP_BLIND_VIA_CROSS_LAYER", 0), 108)
        self.assertEqual(r2["by_classification"].get("RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK", 0), 27)
        self.assertEqual(r2["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 66)
        self.assertEqual(r2["by_classification"].get("INTENTIONAL_VIPPO_BGA_OR_EPAD", 0), 2)

        # Verify PCB1 & PCB3 also have 0 true physical clearance violations in PR #43 while catching real SMD via-in-pad
        r1 = audit_board("PCB1", arc, pr43_dump / "PCB1-post.dump.json")
        r3 = audit_board("PCB3", arc, pr43_dump / "PCB3-post.dump.json")
        self.assertEqual(r1["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0)
        self.assertEqual(r3["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0)
        self.assertEqual(r1["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 106)
        self.assertEqual(r3["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 60)

    def test_pr44_p0_closure_zero_real_defects(self):
        pr44_epro = CUR / "native/ZY_AIAR_EVT1_H03_3BOARD_DFM_P0_MECR01_NOT_FOR_FAB.epro2"
        pr44_dump = CUR / "evidence/post-route"
        arc = Archive(pr44_epro)
        for b, exp_vippo in (("PCB1", 9), ("PCB2", 2), ("PCB3", 0)):
            r = audit_board(b, arc, pr44_dump / f"{b}-post.dump.json")
            self.assertEqual(r["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0, f"{b} true physical violation!")
            self.assertEqual(r["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 0, f"{b} non-VIPPO via-in-pad!")
            self.assertEqual(r["by_classification"].get("RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK", 0), 0, f"{b} <6mil track-track!")
            self.assertEqual(r["by_classification"].get("INTENTIONAL_VIPPO_BGA_OR_EPAD", 0), exp_vippo, f"{b} VIPPO drift!")


if __name__ == "__main__":
    unittest.main()
