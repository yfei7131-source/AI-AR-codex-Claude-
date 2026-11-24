#!/usr/bin/env python3
"""
Automated verification test suite for h03_r8_pcb2_joint_relayout.py.

Executes directly against the REAL R7 (before) and R8 (after) full-board
native PCB2-copper.json captures — NO simplified fixture impersonation.
"""

import copy
import json
import os
import unittest
from pathlib import Path

from h03_r8_pcb2_joint_relayout import (
    InvalidPolygonPadError,
    KNOWN_CONFLICT_GND_ID,
    MissingCopperDataError,
    load_copper_json,
    parse_pad_geometry,
    run_verification,
)

DEFAULT_R7 = Path(__file__).parent.parent / "r8_handoff_in" / "R8" / "logs" / "before" / "PCB2-copper.json"
DEFAULT_R8 = Path(__file__).parent.parent / "r8_handoff_in" / "R8" / "logs" / "after" / "PCB2-copper.json"
R7_PATH = Path(os.environ.get("PCB2_R7_COPPER_JSON", str(DEFAULT_R7)))
R8_PATH = Path(os.environ.get("PCB2_R8_COPPER_JSON", str(DEFAULT_R8)))


class TestRealR7AndR8FullBoard(unittest.TestCase):
    def test_real_r7_full_board_counts_and_run(self):
        self.assertTrue(R7_PATH.exists(), f"Real R7 copper JSON not found: {R7_PATH}")
        res = run_verification(R7_PATH)
        inv = res["full_board_inventory"]
        self.assertEqual(inv["components_count"], 86)
        self.assertEqual(inv["copper_lines_count"], 398)
        self.assertEqual(inv["copper_vias_count"], 47)
        self.assertEqual(inv["polygon_pads_count"], 16)
        self.assertEqual(res["verification_scope"], "OFFLINE_FULL_COPPER_GEOMETRY_SCREEN_NOT_NATIVE_DRC")
        self.assertFalse(res["full_board_native_drc_completed"])

    def test_real_r8_full_board_counts_conflicts_and_candidates(self):
        self.assertTrue(R8_PATH.exists(), f"Real R8 copper JSON not found: {R8_PATH}")
        res = run_verification(R8_PATH)

        # 1. Exact R8 full-board inventory (86 components, 406 lines, 47 vias, 16 POLYGON pads)
        inv = res["full_board_inventory"]
        self.assertEqual(inv["components_count"], 86)
        self.assertEqual(inv["copper_lines_count"], 406)
        self.assertEqual(inv["copper_vias_count"], 47)
        self.assertEqual(inv["polygon_pads_count"], 16)

        # 2. Missing plane & via-span data MUST be explicitly flagged (never assumed empty)
        flags = res["missing_data_flags"]
        self.assertIn("l2_gnd_plane_geometry", flags)
        self.assertIn("l5_gnd_plane_geometry", flags)
        self.assertIn("via_layer_span_metadata", flags)

        # 3. Known conflicting GND track d4ca5cb6211b4cf9 confirmed
        conf = res["known_conflict_gnd_track"]
        self.assertEqual(conf["primitiveId"], KNOWN_CONFLICT_GND_ID)
        self.assertTrue(conf["round3_conflict_confirmed"])
        self.assertEqual(conf["round3_vsys_path_clearance_mil"], 0.0)

        # 4. MK2 POLYGON pads & native C11 intrusion confirmed
        mk2 = res["mk2_interference_audit"]
        self.assertEqual(mk2["mk2_polygon_pad_count"], 4)
        self.assertGreater(mk2["native_c11_vs_mk2_bbox_overlap_sqmil"], 900.0)

        # 5. Zero-shift L6-only (S1) and Round-3 shift (S3) must fail (0 PASS) with explicit reasons
        s1 = res["scenarios"]["S1_zero_shift_l6_only"]
        self.assertEqual(s1["passing_count"], 0)
        self.assertGreater(s1["failed_total"], 0)

        s3 = res["scenarios"]["S3_round3_shift_audit"]
        self.assertEqual(s3["passing_count"], 0)
        self.assertFalse(s3["shift_envelopes_clean"])
        self.assertIn("KNOWN_GND_CONFLICT_d4ca5cb6211b4cf9", s3["failure_reason_counts"])

        # 6. S2 zero-shift L6 open pocket + L4 stereo yields 80 clean non-overlapping candidates
        s2 = res["scenarios"]["S2_zero_shift_l6_pocket_l4_stereo"]
        self.assertTrue(s2["shift_envelopes_clean"])
        self.assertEqual(s2["passing_count"], 80)
        top = s2["passing_top5"][0]
        self.assertEqual(top["mk2_overlap_sqmil"], 0.0)
        self.assertEqual(top["vsys_route_mode"], "L4_STEREO_REQUIRES_HDI_EQ")
        self.assertEqual(top["l5_plane_check"], "UNVERIFIED_MISSING_L5_PLANE_IN_COPPER_JSON")
        self.assertGreaterEqual(top["avdd_req_filter_gap_mil"], 11.8)
        self.assertGreaterEqual(top["gnd_via_hole_wall_gap_mil"], 11.811)
        self.assertGreaterEqual(top["min_l6_comp_gap_mil"], 6.0)

    def test_fail_fast_on_missing_or_corrupt_data(self):
        base = json.loads(R8_PATH.read_text(encoding="utf-8"))
        tmp = Path(__file__).parent / "_tmp_corrupt.json"
        try:
            # Missing outline
            bad = copy.deepcopy(base)
            del bad["outline"]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)

            # Missing copper.lines
            bad = copy.deepcopy(base)
            bad["copper"]["lines"] = []
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)

            # Corrupt POLYGON pad (<3 vertices)
            with self.assertRaises(InvalidPolygonPadError):
                parse_pad_geometry(
                    {"padNumber": "5", "net": "GND", "layer": 2, "shape": ["POLYGON", [0, 0, "L", 10, 0]]},
                    "MK2",
                )
        finally:
            if tmp.exists():
                tmp.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
