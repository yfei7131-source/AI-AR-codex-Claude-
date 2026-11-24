#!/usr/bin/env python3
"""Automated test suite for W4 PCB1 (118 components) J2/J3 audit & witness footprint."""
import os
import unittest
from pathlib import Path

from w4_pcb1_j2_j3_audit import run_w4_audit

IN_DIR = Path(os.environ.get("W4_IN_DIR", str(Path(__file__).parent.parent / "w4_in")))


class TestW4Pcb1Audit(unittest.TestCase):
    def test_real_r9_pcb1_118_components_and_j2_j3_blockers(self):
        fp_out = Path(__file__).parent / "footprints" / "J2_BM28B0.6-24DS_2-0.35V_53_C5577343_WITNESS.kicad_mod"
        res = run_w4_audit(
            IN_DIR / "PCB1-copper.json",
            IN_DIR / "PCB1-erc.json",
            IN_DIR / "PCB1-drc.json",
            fp_out,
        )
        inv = res["baseline_inventory"]
        self.assertEqual(inv["components_count"], 118)
        self.assertEqual(inv["copper_lines_count"], 830)
        self.assertEqual(inv["copper_vias_count"], 97)
        self.assertEqual(inv["erc_fatal_count"], 4)
        self.assertIn("J2", inv["erc_missfootprint_refs"])
        self.assertIn("J3", inv["erc_missfootprint_refs"])
        self.assertEqual(inv["drc_counts"]["Netlist Error"], 1)

        # J2 witness footprint file generated with 28 pads
        self.assertTrue(fp_out.exists())
        fp_txt = fp_out.read_text(encoding="utf-8")
        self.assertEqual(fp_txt.count("(pad "), 28)
        self.assertGreater(res["j2_j_cam_audit"]["legal_assembly_windows_found"], 0)
        self.assertIn("BLOCKED", res["j2_j_cam_audit"]["binding_status"])

        # J3 width overflow confirmed (> 1.0 mm) and stays BLOCKED
        self.assertGreater(res["j3_j_chg_audit"]["width_overflow_mm"], 1.0)
        self.assertIn("BLOCKED", res["j3_j_chg_audit"]["binding_status"])
        self.assertFalse(res["cloud_import_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
