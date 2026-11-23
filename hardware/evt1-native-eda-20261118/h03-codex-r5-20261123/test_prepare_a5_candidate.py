import tempfile
import unittest
from pathlib import Path

from prepare_a5_candidate import A5_VIA, DOC, VIA_ID, generate, load, records


BASE = Path(__file__).resolve().parent.parent / "h03-codex-r4-20261123/native"


class A5CandidateTest(unittest.TestCase):
    def test_same_scope_with_only_a5_blind_via_added(self):
        source, = BASE.glob("*.epro2")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "candidate.epro2"
            report = generate(source, output)
            footprint = records(load(output).documents[DOC])
            via = footprint["VIA", VIA_ID]
            self.assertEqual((via["centerX"], via["centerY"]), A5_VIA)
            self.assertEqual((via["viaType"], via["ruleName"], via["holeDiameter"], via["viaDiameter"]),
                             ("BLIND", "BV_L1_L2", 4, 10))
            self.assertEqual(via, report["via"])

    def test_existing_candidate_id_is_rejected_without_new_archive(self):
        source, = BASE.glob("*.epro2")
        with tempfile.TemporaryDirectory() as folder:
            first, second = (Path(folder) / f"{name}.epro2" for name in ("first", "second"))
            generate(source, first)
            with self.assertRaisesRegex(ValueError, "already taken"):
                generate(first, second)
            self.assertFalse(second.exists())
