import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import independent_hdi_dfm_auditor_v4 as v4


def via(x, hole=4.0, diameter=10.0, net="GND", span=frozenset({1, 15}), kind="BLIND"):
    return {"x": x, "y": 15.0, "net": net, "hole_mil": hole,
            "diam_mil": diameter, "span": span, "viaType": kind}


class V4DatumTests(unittest.TestCase):
    def test_outline_separates_hole_wall_and_copper_land(self):
        outline = [(0, 0), (0, 40), (40, 40), (40, 0)]
        center, hole_edge, copper_edge = v4.edge_metrics(via(16.0), outline)
        self.assertEqual((center, hole_edge, copper_edge), (15.0, 13.0, 10.0))
        outline = [(0, 0), (0, 90), (90, 90), (90, 0)]
        sample = {**via(16.0), "y": 30.0}
        center, hole_edge, copper_edge = v4.edge_metrics(sample, outline)
        self.assertEqual((center, hole_edge, copper_edge), (16.0, 14.0, 11.0))
        self.assertFalse(v4.below_limit(hole_edge, v4.MIN_BLIND_EDGE_HOLE_MIL))
        self.assertTrue(v4.below_limit(copper_edge, v4.MIN_BLIND_EDGE_CU_MIL))

    def test_exact_threshold_is_not_rounded_before_screening(self):
        outline = [(0, 0), (0, 90), (90, 90), (90, 0)]
        edge = v4.MIN_BLIND_EDGE_HOLE_MIL
        sample = {**via(edge + 2), "y": 30.0}
        self.assertFalse(v4.below_limit(v4.edge_metrics(sample, outline)[1], edge))
        sample["x"] -= 0.0001
        self.assertTrue(v4.below_limit(v4.edge_metrics(sample, outline)[1], edge))

    def test_unequal_via_pitch_conversion_preserves_distinct_radii(self):
        sample = via(19.0, hole=6.0, diameter=12.0, net="VSYS",
                     span=frozenset(v4.COPPER_LAYER_ORDER), kind="NORMAL")
        row = v4.pair_metrics(via(0.0), sample)
        self.assertEqual(row["span_relation"], "overlapping_unlike_spans")
        self.assertEqual((row["center_pitch_mil"], row["hole_wall_mil"], row["cu_gap_mil"]), (19.0, 14.0, 8.0))
        self.assertAlmostEqual(row["equivalent_hole_pitch_limit_mil"], 5 + 0.240 / 0.0254)
        self.assertEqual(row["equivalent_cu_pitch_limit_mil"], 17.0)
        self.assertEqual(row["shared_layers"], [1, 15])

    def test_staggered_pair_uses_shared_layer_and_same_net_threshold(self):
        row = v4.pair_metrics(via(0.0), via(15.0, span=v4.layer_interval(15, 16)))
        self.assertEqual((row["shared_layers"], row["span_relation"]), ([15], "adjacent_spans"))
        self.assertTrue(row["same_net"])
        self.assertFalse(row["stack_review"])
        self.assertAlmostEqual(row["hole_wall_limit_mil"], 0.130 / 0.0254)
        self.assertAlmostEqual(row["equivalent_hole_pitch_limit_mil"], 4 + 0.130 / 0.0254)

    def test_disjoint_spans_do_not_create_projected_conflicts(self):
        self.assertIsNone(v4.pair_metrics(via(0), via(0, net="VSYS", span=v4.layer_interval(18, 2))))
        self.assertEqual(v4.layer_interval(17, 15), frozenset({15, 16, 17}))
        self.assertEqual(v4.layer_interval(17, 48), frozenset())

    def test_deliberate_stacks_need_qualification_and_are_not_silently_passed(self):
        collinear = v4.pair_metrics(via(0), via(0, span=v4.layer_interval(15, 16)))
        self.assertTrue(collinear["stack_review"])
        self.assertIsNone(collinear["hole_wall_limit_mil"])
        unlike = v4.pair_metrics(via(0), via(0, span=v4.layer_interval(15, 16), net="VSYS"))
        self.assertFalse(unlike["stack_review"])
        self.assertTrue(v4.below_limit(unlike["hole_wall_mil"], unlike["hole_wall_limit_mil"]))

    def test_archive_dump_mismatch_and_unknown_span_are_visible(self):
        via_record = SimpleNamespace(
            header={"type": "VIA", "id": "via-1"},
            payload={"viaType": "BLIND", "ruleName": "unknown", "centerX": 2.0, "centerY": 3.0,
                     "holeDiameter": 4.0, "viaDiameter": 10.0, "netName": "GND"},
        )
        doc = SimpleNamespace(records=[via_record])
        mirror = {"primitiveId": "via-1", "x": 2.0, "y": 3.0,
                  "holeDiameter": 4.0, "diameter": 10.0, "net": "GND"}
        dump = {"copperLayers": 6, "copper": {"vias": [mirror]}}
        self.assertEqual(v4.read_vias(doc, dump)[0]["span"], frozenset())
        mirror["diameter"] = 11.0
        with self.assertRaisesRegex(ValueError, "differ for via"):
            v4.read_vias(doc, dump)


class V4Pr46Regression(unittest.TestCase):
    def test_every_pr46_blind_via_is_ledgered(self):
        source = v4.PACKAGE / "h03-u11-wlcsp-v3-dfm-route"
        archive = v4.Archive(source / "native/ZY_AIAR_EVT1_H03_3BOARD_U11_V3_DFM_MECR01_NOT_FOR_FAB.epro2")
        checked = 0
        with TemporaryDirectory() as folder:
            for board, count, guard in (("PCB1", 62, 4), ("PCB2", 40, 0), ("PCB3", 39, 2)):
                with self.subTest(board=board):
                    ledger = Path(folder) / f"{board}-vias.csv"
                    dump = source / "evidence/post-route" / f"{board}-post.dump.json"
                    report = v4.audit_board_v4(board, archive, dump, blind_csv=ledger)["v4_official_jlcpcb_hdi_audit"]
                    self.assertEqual(report["total_blind_vias"], count)
                    limits = report["violations"]
                    self.assertEqual(limits["jlc_blind_hole_edge_below_0p35mm"], 0)
                    self.assertEqual(limits["evt1_blind_copper_edge_guard_below_0p35mm"], guard)
                    self.assertEqual(limits["total_v4_violations"], guard)
                    with ledger.open(encoding="utf-8", newline="") as stream:
                        rows = list(csv.DictReader(stream))
                    self.assertEqual(len(rows), count)
                    self.assertEqual(len({r["via_id"] for r in rows}), count)
                    self.assertTrue(all(r["jlc_hole_edge_ge_0p35mm"] == "PASS" for r in rows))
                    checked += count
        self.assertEqual(checked, 141)


if __name__ == "__main__":
    unittest.main()
