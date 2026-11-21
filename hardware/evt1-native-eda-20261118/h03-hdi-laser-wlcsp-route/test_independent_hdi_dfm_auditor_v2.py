#!/usr/bin/env python3
"""Regression unit tests for independent_hdi_dfm_auditor_v2.py (PR #45).

Verifies:
  1. PR #44 baseline correctly flags all 154 under-3-mil-ring (4/8 mil, 2.0 mil ring) laser blind microvias
     across PCB1 (70), PCB2 (40), and PCB3 (44).
  2. PR #45 final exported .epro2 achieves ZERO under-3-mil-ring blind microvias (139/139 >= 3.0 mil / 0.0762 mm),
     ZERO TRUE_PHYSICAL_VIOLATION, ZERO REAL_DFM_VIA_TOUCHES_SMD_PAD, ZERO RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK,
     and ZERO illegal mechanical through-vias across all 3 boards.
"""

from pathlib import Path
import sys
import unittest

CUR = Path(__file__).resolve().parent
PKG = CUR.parent
sys.path[:0] = [str(CUR), str(PKG / "h02-native"), str(PKG / "h03-dfm-p0-closure")]

from independent_hdi_dfm_auditor_v2 import audit_board_v2
from prepare_hierarchy import Archive


class IndependentHDIDFMAuditorV2Test(unittest.TestCase):
    def test_pr44_catches_all_154_under_annular_ring_blind_vias(self):
        pr44_epro = PKG / "h03-dfm-p0-closure/native/ZY_AIAR_EVT1_H03_3BOARD_DFM_P0_MECR01_NOT_FOR_FAB.epro2"
        pr44_dump = PKG / "h03-dfm-p0-closure/evidence/post-route"
        arc = Archive(pr44_epro)
        expected = {"PCB1": 70, "PCB2": 40, "PCB3": 44}
        tot_under = 0
        for b, cnt in expected.items():
            r = audit_board_v2(b, arc, pr44_dump / f"{b}-post.dump.json")
            la = r["laser_blind_annular_ring_audit"]
            self.assertEqual(la["under_3mil_ring_blind_vias"], cnt, f"{b} PR44 under-ring count mismatch")
            self.assertAlmostEqual(la["min_blind_ring_mil"], 2.0, places=2)
            tot_under += la["under_3mil_ring_blind_vias"]
        self.assertEqual(tot_under, 154)

    def test_pr45_zero_under_ring_and_zero_physical_defects(self):
        pr45_epro = CUR / "native/ZY_AIAR_EVT1_H03_3BOARD_LASER_WLCSP_MECR01_NOT_FOR_FAB.epro2"
        pr45_dump = CUR / "evidence/post-route"
        arc = Archive(pr45_epro)
        expected_vippo = {"PCB1": 9, "PCB2": 2, "PCB3": 0}
        for b, vippo in expected_vippo.items():
            r = audit_board_v2(b, arc, pr45_dump / f"{b}-post.dump.json")
            cls = r["by_classification"]
            la = r["laser_blind_annular_ring_audit"]
            self.assertEqual(cls.get("TRUE_PHYSICAL_VIOLATION", 0), 0, f"{b} true physical violation")
            self.assertEqual(cls.get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 0, f"{b} non-VIPPO passive via-in-pad")
            self.assertEqual(cls.get("RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK", 0), 0, f"{b} <6 mil track pair")
            self.assertEqual(cls.get("INTENTIONAL_VIPPO_BGA_OR_EPAD", 0), vippo, f"{b} intentional VIPPO drift")
            self.assertEqual(la["under_3mil_ring_blind_vias"], 0, f"{b} under-3mil-ring blind via!")
            self.assertEqual(la["illegal_mech_through_vias"], 0, f"{b} illegal mechanical through-via!")
            self.assertGreaterEqual(la["min_blind_ring_mil"], 3.0, f"{b} blind annular ring < 3.0 mil!")
            self.assertGreaterEqual(la["min_blind_ring_mm"], 0.075, f"{b} blind annular ring < 0.075 mm!")


if __name__ == "__main__":
    unittest.main()
