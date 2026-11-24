#!/usr/bin/env python3
"""Automated test suite for R9 W5 PCB2 (86 components, 419 lines, 47 vias, 232 DRC opens)."""
import copy
import json
import os
import unittest
from pathlib import Path

from h03_r9_pcb2_joint_relayout import (
    InvalidPolygonPadError,
    KNOWN_CONFLICT_GND_ID,
    MissingCopperDataError,
    load_copper_json,
    parse_pad_geometry,
    run_verification,
)

W5_IN = Path(os.environ.get("W5_IN_DIR", str(Path(__file__).parent.parent / "w5_in")))


class TestW5R9Pcb2RealData(unittest.TestCase):
    def test_real_r9_pcb2_86_419_47_and_c11_solve(self):
        copper_p = W5_IN / "PCB2-copper.json"
        erc_p = W5_IN / "PCB2-erc.json"
        drc_p = W5_IN / "PCB2-drc.json"

        erc = json.loads(erc_p.read_text(encoding="utf-8"))
        drc = json.loads(drc_p.read_text(encoding="utf-8"))
        self.assertEqual(erc["result"]["fatal"], 0)
        self.assertEqual(drc["counts"]["Connection Error"], 232)

        res = run_verification(copper_p)
        inv = res["full_board_inventory"]
        self.assertEqual(inv["components_count"], 86)
        self.assertEqual(inv["copper_lines_count"], 419)
        self.assertEqual(inv["copper_vias_count"], 47)
        self.assertEqual(inv["polygon_pads_count"], 16)
        self.assertEqual(res["verification_scope"], "OFFLINE_FULL_COPPER_GEOMETRY_SCREEN_NOT_NATIVE_DRC")
        self.assertFalse(res["full_board_native_drc_completed"])

        # Missing planes & via spans explicitly flagged
        flags = res["missing_data_flags"]
        self.assertIn("l2_gnd_plane_geometry", flags)
        self.assertIn("l5_gnd_plane_geometry", flags)
        self.assertIn("via_layer_span_metadata", flags)

        # Known conflict d4ca5cb6211b4cf9 confirmed & S3 rejected
        self.assertTrue(res["known_conflict_gnd_track"]["round3_conflict_confirmed"])
        self.assertEqual(res["scenarios"]["S1_zero_shift_l6_only"]["passing_count"], 0)
        self.assertEqual(res["scenarios"]["S3_round3_shift_audit"]["passing_count"], 0)

        # S2 zero-IC-shift L6 open pocket + L4 stereo VSYS + BV_L5_L6 GND yields 80 clean candidates
        s2 = res["scenarios"]["S2_zero_shift_l6_pocket_l4_stereo"]
        self.assertTrue(s2["shift_envelopes_clean"])
        self.assertEqual(s2["passing_count"], 80)
        top = s2["passing_top5"][0]
        self.assertEqual(top["center_mil"], [90, 366])
        self.assertEqual(top["gnd_bv_l5_l6_mil"], [63.38, 366.0])
        self.assertEqual(top["mk2_overlap_sqmil"], 0.0)
        self.assertGreaterEqual(top["avdd_req_filter_gap_mil"], 11.8)
        self.assertGreaterEqual(top["gnd_via_hole_wall_gap_mil"], 11.811)
        self.assertGreaterEqual(top["min_l6_comp_gap_mil"], 6.0)

    def test_fail_fast_missing_data(self):
        base = json.loads((W5_IN / "PCB2-copper.json").read_text(encoding="utf-8"))
        tmp = Path(__file__).parent / "_tmp_w5_bad.json"
        try:
            bad = copy.deepcopy(base)
            del bad["outline"]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)
            with self.assertRaises(InvalidPolygonPadError):
                parse_pad_geometry(
                    {"padNumber": "5", "net": "GND", "layer": 2, "shape": ["POLYGON", [0, 0, "L", 5, 0]]},
                    "MK2",
                )
        finally:
            if tmp.exists():
                tmp.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
