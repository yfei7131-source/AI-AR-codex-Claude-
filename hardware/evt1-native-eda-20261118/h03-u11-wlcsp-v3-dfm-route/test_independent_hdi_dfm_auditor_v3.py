#!/usr/bin/env python3
"""Unit & regression tests for independent_hdi_dfm_auditor_v3.py (PR #46).

Verifies:
  1. Synthetic edge-clearance, same-span via-to-via copper gap, same-span hole-wall,
     and opposite-span blind via (`BV_L1_L2` vs `BV_L5_L6`) geometry rules.
  2. PR #45 baseline (`139` blind microvias) passes V3 blind-via manufacturing checks
     with 0 violations and exact `PCB3 U11` 95-ball ring classification (`16/22/14/43`).
  3. PR #46 final `.epro2` passes V3 blind-via manufacturing checks + 0 physical/via-in-pad
     errors + exact `PCB3 U11` 95-ball classification.
"""

import unittest
from pathlib import Path
import sys

H03_PR46 = Path(__file__).resolve().parent
PACKAGE = H03_PR46.parent
sys.path[:0] = [
    str(PACKAGE / "h02-native"),
    str(PACKAGE / "h03-dfm-p0-closure"),
    str(PACKAGE / "h03-hdi-laser-wlcsp-route"),
    str(H03_PR46),
]

from independent_hdi_dfm_auditor_v3 import (
    audit_board_v3,
    audit_u11_wlcsp_95,
    center_to_outline_dist,
    pt_inside_polygon,
    via_layer_span,
)
from prepare_hierarchy import Archive


class TestIndependentHdiDfmAuditorV3(unittest.TestCase):
    def test_layer_span_disjointness(self):
        self.assertEqual(via_layer_span("BLIND", "BV_L1_L2"), {1, 15})
        self.assertEqual(via_layer_span("BLIND", "BV_L5_L6"), {18, 2})
        self.assertFalse(bool(via_layer_span("BLIND", "BV_L1_L2") & via_layer_span("BLIND", "BV_L5_L6")))
        self.assertTrue(bool(via_layer_span("BLIND", "BV_L1_L2") & via_layer_span("NORMAL", "")))

    def test_stepped_polygon_distance_and_inside(self):
        poly = [
            (0.0, 0.0), (0.0, 1811.0236), (228.3465, 1811.0236),
            (228.3465, 551.1811), (322.8346, 551.1811),
            (322.8346, 165.3543), (228.3465, 165.3543), (228.3465, 0.0),
        ]
        # Inside wider protrusion tab
        self.assertTrue(pt_inside_polygon(poly, 280.0, 350.0))
        self.assertGreater(center_to_outline_dist(poly, 280.0, 350.0), 40.0)
        # Outside stepped notch (y > 551.1811, x > 228.3465)
        self.assertFalse(pt_inside_polygon(poly, 280.0, 900.0))
        self.assertLess(center_to_outline_dist(poly, 280.0, 900.0), 0.0)

    def test_pr45_baseline_v3_audit_and_u11_rings(self):
        pr45_dir = PACKAGE / "h03-hdi-laser-wlcsp-route"
        epro = pr45_dir / "native/ZY_AIAR_EVT1_H03_3BOARD_LASER_WLCSP_MECR01_NOT_FOR_FAB.epro2"
        dumps = pr45_dir / "evidence/post-route"
        arc = Archive(epro)

        total_blinds = 0
        for b in ("PCB1", "PCB2", "PCB3"):
            res = audit_board_v3(b, arc, dumps / f"{b}-post.dump.json")
            v3 = res["extended_blind_via_manufacturing_audit_v3"]
            total_blinds += v3["total_blind_vias"]
            self.assertEqual(v3["violations"]["total_v3_blind_via_violations"], 0, f"{b}: {v3['violations']}")
            self.assertGreaterEqual(v3["measured_min_ring_mil"], 3.0)
            self.assertGreaterEqual(v3["measured_min_cu_to_edge_mil"], 11.811)
            self.assertGreaterEqual(v3["measured_min_same_span_vv_cu_gap_mil"], 6.0)
            self.assertGreaterEqual(v3["measured_min_same_span_vv_hole_wall_mil"], 8.0)
            self.assertEqual(res["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0)
            self.assertEqual(res["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 0)
            if b == "PCB3":
                u11 = res["u11_wlcsp_95_audit"]
                self.assertEqual(u11["total_balls"], 95)
                self.assertEqual(u11["outer_perimeter_depth0_active"], 16)
                self.assertEqual(u11["ring1_depth1_active"], 22)
                self.assertEqual(u11["deep_inner_depth2plus_active"], 14)
                self.assertEqual(u11["nc_unassigned_balls"], 43)
                self.assertEqual(u11["inner_balls_blocked_under_std_1stage_hdi_6mil"], 36)
        self.assertEqual(total_blinds, 139)

    def test_pr46_deliverable_v3_audit(self):
        epro = H03_PR46 / "native/ZY_AIAR_EVT1_H03_3BOARD_U11_V3_DFM_MECR01_NOT_FOR_FAB.epro2"
        dumps = H03_PR46 / "evidence/post-route"
        if not epro.exists():
            self.skipTest("PR46 .epro2 not built yet")
        arc = Archive(epro)
        for b in ("PCB1", "PCB2", "PCB3"):
            res = audit_board_v3(b, arc, dumps / f"{b}-post.dump.json")
            v3 = res["extended_blind_via_manufacturing_audit_v3"]
            self.assertEqual(v3["violations"]["total_v3_blind_via_violations"], 0, f"{b}: {v3['violations']}")
            self.assertGreaterEqual(v3["measured_min_ring_mil"], 3.0)
            self.assertGreaterEqual(v3["measured_min_cu_to_edge_mil"], 11.811)
            self.assertGreaterEqual(v3["measured_min_same_span_vv_cu_gap_mil"], 6.0)
            self.assertGreaterEqual(v3["measured_min_same_span_vv_hole_wall_mil"], 8.0)
            self.assertEqual(res["by_classification"].get("TRUE_PHYSICAL_VIOLATION", 0), 0)
            self.assertEqual(res["by_classification"].get("REAL_DFM_VIA_TOUCHES_SMD_PAD", 0), 0)
            self.assertEqual(res["by_classification"].get("RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK", 0), 0)
        u11 = audit_u11_wlcsp_95(dumps / "PCB3-post.dump.json")
        self.assertEqual(u11["total_balls"], 95)
        self.assertEqual(u11["outer_perimeter_depth0_active"], 16)
        self.assertEqual(u11["ring1_depth1_active"], 22)
        self.assertEqual(u11["deep_inner_depth2plus_active"], 14)
        self.assertEqual(u11["nc_unassigned_balls"], 43)


if __name__ == "__main__":
    unittest.main()
