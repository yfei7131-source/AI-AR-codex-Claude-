"""Regression checks on committed R11 native input and capture bytes."""
import argparse
from collections import Counter
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from extract_p2 import BOARDS, build_board, native_documents, read_json


class NativeCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents, cls.editor = native_documents(args.archive)

    def board(self, name, root):
        uuid, doc = next(
            (uuid, doc) for (kind, uuid), doc in self.documents.items()
            if kind == "PCB" and doc["META"]["META"]["title"] == name
        )
        return build_board(name, uuid, doc, self.documents,
                           root / f"{name}-copper.json", root / f"{name}.net")

    def test_r11_native_inventory(self):
        expected = [(118, 507, 851, 98, 62, 6, 322),
                    (86, 328, 434, 49, 42, 0, 227),
                    (53, 239, 409, 54, 42, 6, 127)]
        keys = ("components", "pads", "tracks", "vias", "blindVias", "keepouts", "connectionErrors")
        for name, wanted in zip(BOARDS, expected, strict=True):
            with self.subTest(board=name):
                data, counts, _ = self.board(name, args.captures)
                self.assertEqual(tuple(counts[k] for k in keys), wanted)
                self.assertEqual([p["net"] for p in data["copper"]["planes"]], ["GND", "GND"])
                self.assertTrue(all(p["voidRings"] for p in data["copper"]["planes"]))
                spans = Counter(tuple(v["drillSpanLayerIds"]) for v in data["copper"]["vias"])
                self.assertEqual(set(spans), {(1, 15), (18, 2), (1, 15, 16, 17, 18, 2)})

    def test_p2_manifest(self):
        manifest = read_json(args.bundle / "manifest.json")
        self.assertEqual(manifest["nativeArchiveSha256"], sha256(args.archive.read_bytes()).hexdigest())
        for name, digest in manifest["fileSha256"].items():
            self.assertEqual(sha256((args.bundle / name).read_bytes()).hexdigest(), digest)

    def test_reject_wrong_capture_identity(self):
        live = read_json(args.captures / "PCB1-copper.json")
        live["capture"]["documentUuid"] = "wrong-board"
        with TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "PCB1-copper.json").write_text(json.dumps(live), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "identity unverified"):
                self.board("PCB1", path)

    def test_reject_drifted_pad_net(self):
        live = read_json(args.captures / "PCB1-copper.json")
        live["components"][0]["pads"][0]["net"] = "SOURCE_DRIFT"
        with TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "PCB1-copper.json").write_text(json.dumps(live), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "pad/net disagreement"):
                self.board("PCB1", path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--captures", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    unittest.main(argv=[__file__, "-v"])
