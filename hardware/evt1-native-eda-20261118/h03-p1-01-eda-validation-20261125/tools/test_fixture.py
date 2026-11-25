"""Tests use real archived native geometry, DRC/ERC and independent re-import evidence."""

import copy
import os
from pathlib import Path
import tempfile
import unittest

import batch_gate as gate
import native_batch

native = gate.native


class NativeFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        packages = Path(native.__file__).resolve().parents[2]
        cls.source = next(packages.glob("h03-codex-r10*/*.epro2"))
        cls.dest = next(packages.glob("h03-codex-r11*/*.epro2"))
        cls.plan_file = Path(__file__).with_name("r11-fixture-plan.json")
        cls.plan = gate.parse_plan(cls.plan_file, cls.source)
        cls.before, cls.after = native.archive(cls.source), native.archive(cls.dest)
        cls.logs = cls.dest.parent / "logs"
        cls.review = Path(__file__).with_name("r11-fixture-audit.json")

    def test_scope_and_geometry_exactly_match_real_r11(self):
        changes = gate.check_archive(self.before, self.after, self.plan)
        self.assertEqual(sum(b["addedLines"] for b in changes.values()), 24)
        self.assertEqual(sum(b["addedBlindVias"] for b in changes.values()), 4)

    def test_deleting_a_protected_native_track_is_rejected(self):
        broken = copy.deepcopy(self.after)
        id = "PCB", native.PCB_IDS["PCB1"]
        key = next(k for k in self.before[id] if k[0] == "LINE")
        del broken[id][key]
        with self.assertRaisesRegex(ValueError, "native records were deleted"):
            gate.check_archive(self.before, broken, self.plan)

    def test_changing_native_rule_is_rejected(self):
        broken = copy.deepcopy(self.after)
        id = "PCB", native.PCB_IDS["PCB2"]
        key = next(k for k in self.before[id] if k[0] == "RULE")
        broken[id][key]["unexpectedRuleEdit"] = True
        with self.assertRaisesRegex(ValueError, "retained rule"):
            gate.check_archive(self.before, broken, self.plan)

    def test_low_width_preflight_fails_without_editor(self):
        plan = copy.deepcopy(self.plan)
        plan["boards"]["PCB3"]["routes"][0]["width"] = 1.96
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.json"
            native.write(path, plan)
            with self.assertRaisesRegex(ValueError, "route width"):
                gate.parse_plan(path, self.source)

    def test_stale_checkpoint_preflight_fails_without_editor(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            gate.parse_plan(self.plan_file, self.dest)

    def test_netlist_suppression_is_rejected(self):
        report = native.read(self.logs / "before/PCB1-drc.json")
        changed = copy.deepcopy(report)
        changed["violations"] = [v for v in changed["violations"] if v["rule"] != "Netlist Error"]
        del changed["counts"]["Netlist Error"]
        with self.assertRaisesRegex(ValueError, "outside planned connections"):
            gate.drc_gate(report, changed, self.plan["boards"]["PCB1"])

    def test_native_replay_rejects_empty_acceptance_before_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "trial"
            with self.assertRaisesRegex(ValueError, "matching independently re-imported"):
                native_batch.run(self.source, self.plan_file, target, "P1-ISOLATED-TEST", None, None, {})
            self.assertFalse(target.exists())

    def test_electric_and_independent_reimport_evidence(self):
        replica = os.environ.get("P101_R11_INDEPENDENT_EXPORT")
        if not replica:
            self.skipTest("Supply P101_R11_INDEPENDENT_EXPORT from the verified historical R11 re-import")
        evidence = gate.evidence(self.source, self.dest, self.plan_file, self.logs / "before", self.logs / "after",
                                 (Path(replica), self.logs / "reimport"), self.review)
        self.assertEqual(evidence["status"], "accepted-isolated")
        self.assertEqual(sum(b["connectionErrors"][-1] for b in evidence["boards"].values()), 676)


if __name__ == "__main__":
    unittest.main()
