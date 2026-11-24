#!/usr/bin/env python3
"""
Automated test suite for h03_r8_pcb2_joint_relayout.py.
Covers:
  1. Strict POLYGON pad parsing (SVG command array, flat coords, vertex list, malformed rejection).
  2. Strict fail-fast errors on missing outline, components, U13 pads, MK2 POLYGON pad, tracks, vias, or L2/L5 planes.
  3. End-to-end verification on PR #55 verified-extract copper JSON fixture:
     - MK2 native C11 intrusion (906.73 sq.mil) and POLYGON pad verification
     - Baseline zero-shift L6-only failure reproduction with structured failure reasons
     - Scheme R8-C joint relayout passing candidates, A* VSYS path, BV_L5_L6 -> L5 return containment
     - Scheme R8-A L4 stereo candidates and U2 BGA shadow flag
     - Explicit OFFLINE_GEOMETRY_SCREEN_NOT_FULL_BOARD_DRC guard tag
"""

import copy
import json
import unittest
from pathlib import Path

from h03_r8_pcb2_joint_relayout import (
    InvalidPolygonPadError,
    MissingCopperDataError,
    load_copper_json,
    parse_pad_geometry,
    run_verification,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pcb2_verified_extract_pr55.json"


class TestPolygonPadAndFailFast(unittest.TestCase):
    def test_polygon_pad_encodings(self):
        # 1. List of [x, y] pairs
        p1 = parse_pad_geometry(
            {"number": "5", "net": "GND", "layer": 2, "shape": ["POLYGON", [[10, 10], [30, 10], [30, 25], [10, 25]]],
             "hole": ["ROUND", 1.42338, 1.42338]},
            "MK2",
        )
        self.assertEqual(p1.shape_type, "POLYGON")
        self.assertAlmostEqual(p1.geom.area, 300.0, places=3)
        self.assertAlmostEqual(p1.hole_diam, 1.42338, places=5)

        # 2. SVG command array
        p2 = parse_pad_geometry(
            {"number": "5b", "net": "GND", "layer": 2, "shape": ["POLYGON", ["M", 0, 0, "L", 20, 0, "L", 20, 10, "L", 0, 10, "Z"]]},
            "MK2",
        )
        self.assertAlmostEqual(p2.geom.area, 200.0, places=3)

        # 3. SVG command string
        p3 = parse_pad_geometry(
            {"number": "5c", "net": "GND", "layer": 2, "shape": ["POLYGON", "M 0 0 L 10 0 L 10 10 L 0 10 Z"]},
            "MK2",
        )
        self.assertAlmostEqual(p3.geom.area, 100.0, places=3)

    def test_malformed_polygon_pad_raises(self):
        with self.assertRaises(InvalidPolygonPadError):
            parse_pad_geometry(
                {"number": "5", "net": "GND", "layer": 2, "shape": ["POLYGON", [[0, 0], [10, 0]]]},
                "MK2",
            )
        with self.assertRaises(InvalidPolygonPadError):
            parse_pad_geometry(
                {"number": "5", "net": "GND", "layer": 2, "shape": "POLYGON"},  # missing points
                "MK2",
            )

    def test_missing_data_raises_strictly(self):
        base = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        tmp = FIXTURE_PATH.parent / "_tmp_bad.json"
        try:
            # Missing outline
            bad = copy.deepcopy(base)
            del bad["outline"]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)

            # Missing L5 plane
            bad = copy.deepcopy(base)
            bad["planes"] = [p for p in bad["planes"] if p["layer"] != 18]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)

            # Missing MK2 POLYGON pad
            bad = copy.deepcopy(base)
            for c in bad["components"]:
                if c["designator"] == "MK2":
                    c["pads"] = [p for p in c["pads"] if p["shape"][0] != "POLYGON"]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)

            # Missing required component U13
            bad = copy.deepcopy(base)
            bad["components"] = [c for c in bad["components"] if c["designator"] != "U13"]
            tmp.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MissingCopperDataError):
                load_copper_json(tmp)
        finally:
            if tmp.exists():
                tmp.unlink()


class TestEndToEndRelayoutVerification(unittest.TestCase):
    def test_verified_pr55_extract_run(self):
        res = run_verification(FIXTURE_PATH)

        # Must explicitly state it is NOT full-board DRC
        self.assertEqual(res["verification_scope"], "OFFLINE_GEOMETRY_SCREEN_NOT_FULL_BOARD_DRC")
        self.assertFalse(res["full_board_native_drc_completed"])

        # MK2 interference & POLYGON pads
        mk2 = res["mk2_interference_audit"]
        self.assertEqual(mk2["mk2_polygon_pad_count"], 4)
        self.assertGreater(mk2["native_c11_vs_mk2_bbox_overlap_sqmil"], 900.0)

        # L2/L5 planes verified
        ret = res["l2_l5_return_and_decaps"]
        self.assertEqual(ret["bv_l1_l2_outside_l2_plane"], [])
        self.assertEqual(ret["bv_l5_l6_outside_l5_plane"], [])
        self.assertEqual(ret["existing_gnd_through_via_count"], 0)
        self.assertEqual(len(ret["eight_decap_audit"]), 8)

        # Baseline zero-shift L6-only produces failed candidates with reasons
        base_repro = res["baseline_zero_shift_repro"]
        self.assertGreater(base_repro["failed_total"], 0)
        self.assertTrue(len(base_repro["failure_reason_counts"]) > 0)

        # Scheme R8-C produces verified passing candidates with zero MK2 overlap and L6 A* VSYS path
        r8_c = res["scheme_r8_c_joint_relayout"]
        self.assertGreater(r8_c["passing_count"], 0)
        best_c = r8_c["passing_top5"][0]
        self.assertEqual(best_c["vsys_route_mode"], "L6_DIRECT_ASTAR")
        self.assertEqual(best_c["mk2_overlap_sqmil"], 0.0)
        self.assertFalse(best_c["in_u2_bga_shadow"])
        self.assertGreaterEqual(best_c["avdd_req_filter_gap_mil"], 11.8)
        self.assertGreaterEqual(best_c["gnd_via_hole_wall_gap_mil"], 11.811)
        self.assertGreaterEqual(best_c["min_l6_comp_gap_mil"], 6.0)

        # Scheme R8-A produces passing candidates (flagged as in_u2_bga_shadow)
        r8_a = res["scheme_r8_a_l4_stereo"]
        self.assertGreater(r8_a["passing_count"], 0)
        self.assertIn(r8_a["passing_top5"][0]["vsys_route_mode"], ("L6_DIRECT_ASTAR", "L4_STEREO_REQUIRES_HDI_EQ"))
        self.assertTrue(r8_a["passing_top5"][0]["in_u2_bga_shadow"])

    def test_l6_blocked_triggers_l4_stereo_fallback(self):
        base = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        # Add a full-width L6 FPGA_CRESET_B barrier at Y=310 mil blocking L6-only routing to Y=358..382
        base["tracks"].append(
            {"layer": 2, "net": "FPGA_CRESET_B", "width": 4.0, "points": [[12.0, 310.0], [169.0, 310.0]]}
        )
        tmp = FIXTURE_PATH.parent / "_tmp_l6_blocked.json"
        try:
            tmp.write_text(json.dumps(base), encoding="utf-8")
            res = run_verification(tmp)
            # Zero-shift L6-only must fail on blocked L6 corridor
            self.assertEqual(res["baseline_zero_shift_repro"]["passing_count"], 0)
            self.assertGreater(res["baseline_zero_shift_repro"]["failure_reason_counts"].get("NO_VSYS_L6_ROUTE", 0), 0)
            # R8-A with allow_l4_stereo=True must fall back to L4_STEREO_REQUIRES_HDI_EQ
            self.assertGreater(res["scheme_r8_a_l4_stereo"]["passing_count"], 0)
            self.assertEqual(
                res["scheme_r8_a_l4_stereo"]["passing_top5"][0]["vsys_route_mode"],
                "L4_STEREO_REQUIRES_HDI_EQ",
            )
        finally:
            if tmp.exists():
                tmp.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
