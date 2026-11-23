import json
from pathlib import Path
import unittest

from verify_pcb1_spur import measure, point_to_segment, segment_distance

FIXTURE = Path(__file__).parent / "verification/pcb1-before-copper.json"


class GroundSpurTest(unittest.TestCase):
    def dump(self):
        return json.loads(FIXTURE.read_bytes())

    def test_capsule_uses_endpoint_when_projection_falls_past_it(self):
        self.assertEqual(point_to_segment((6, 4), (0, 0), (3, 0)), 5)
        self.assertEqual(segment_distance((0, 0), (5, 5), (0, 5), (5, 0)), 0)
        self.assertEqual(segment_distance((0, 0), (3, 0), (2, 0), (5, 0)), 0)

    def test_original_dangling_spur_and_e85_clearance(self):
        proof = measure(self.dump())
        self.assertEqual(len(proof["touching_copper"]), 3)
        self.assertEqual(proof["e85_copper_edge_gap_mil"]["4"], 4.968509)

    def test_refuses_when_pad_contacts_free_end(self):
        board = self.dump()
        board["components"].append({"pads": [{
            "primitiveId": "simulated-pad", "layer": 2, "net": "GND",
            "x": 45.0501, "y": 1391.7324, "width": 5, "height": 5,
        }]})
        with self.assertRaisesRegex(ValueError, "Unexpected touching copper"):
            measure(board)

    def test_refuses_incomplete_area_copper_evidence(self):
        board = self.dump()
        board["copper"]["availability"]["poured"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Incomplete copper capture"):
            measure(board)
