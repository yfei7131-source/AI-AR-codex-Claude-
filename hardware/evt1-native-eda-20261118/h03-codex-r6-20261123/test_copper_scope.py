import unittest

from apply_widths import compare_routes


def line(start, end, width=4):
    return {"net":"GND","layer":1,"lineWidth":width,
            "startX":start[0],"startY":start[1],"endX":end[0],"endY":end[1]}


class GeometryScopeTest(unittest.TestCase):
    def test_tee_normalization_preserves_centerline(self):
        original=[line((0,0),(20,0))]
        actual=[line((0,0),(7,0)),line((7,0),(20,0))]
        compare_routes(original,actual)

    def test_open_gap_fails_the_comparison(self):
        original=[line((0,0),(20,0))]
        split=[line((0,0),(7,0)),line((7.25,0),(20,0))]
        with self.assertRaisesRegex(ValueError,"copper union differs"):
            compare_routes(original,split,tolerance=0.02)

    def test_different_width_cannot_hide_even_with_equal_centerline(self):
        with self.assertRaisesRegex(ValueError,"net, layer or track width"):
            compare_routes([line((0,0),(20,0),4)],[line((0,0),(20,0),3)])

    def test_off_axis_branch_fails_the_comparison(self):
        with self.assertRaisesRegex(ValueError,"copper union differs"):
            compare_routes([line((0,0),(20,0))],
                           [line((0,0),(7,0)),line((7,0),(20,0.08))],tolerance=0.02)
