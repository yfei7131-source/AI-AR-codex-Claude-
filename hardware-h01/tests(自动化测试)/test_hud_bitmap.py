"""Real Pillow rasterization and memory sink contracts; no optical device."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app.hud_bitmap import (BitmapDisplayAdapter, DisplayUnavailable, FontUnavailable,
                            HudBitmap, HudBitmapError, UnsupportedGlyph, encode_image,
                            load_font, render_hud, require_glyphs, validate_bitmap)

FONT = Path(os.getenv("HUD_TEST_FONT", str(Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc")))


class PackedPixelsTest(unittest.TestCase):
    def test_mono_row_padding_msb_bit_order_and_polarity(self):
        image = Image.new("L", (9, 2), 0)
        image.putpixel((0, 0), 255)
        image.putpixel((8, 0), 255)
        image.putpixel((7, 1), 255)
        bitmap = encode_image(image)
        self.assertEqual(bitmap.stride_bytes, 2)
        self.assertEqual(bitmap.payload, bytes([0x80, 0x80, 0x01, 0x00]))
        preview = bitmap.to_image()
        self.assertEqual(preview.getpixel((0, 0)), 255)
        self.assertEqual(preview.getpixel((1, 0)), 0)
        self.assertEqual(preview.getpixel((7, 1)), 255)

    def test_gray8_preserves_values_and_threshold_is_explicit(self):
        image = Image.frombytes("L", (4, 1), bytes([0, 127, 128, 255]))
        gray = encode_image(image, pixel_format="gray8")
        self.assertEqual(gray.payload, bytes([0, 127, 128, 255]))
        self.assertEqual(gray.stride_bytes, 4)
        self.assertEqual(encode_image(image).payload, bytes([0x30]))
        self.assertEqual(encode_image(image, threshold=200).payload, bytes([0x10]))

    def test_payload_sizes_match_current_firmware_contract(self):
        image = Image.new("L", (256, 256), 255)
        mono, gray = encode_image(image), encode_image(image, pixel_format="gray8")
        self.assertEqual(len(mono.payload), ((mono.width + 7) // 8) * mono.height)
        self.assertEqual(len(mono.payload), 8192)
        self.assertEqual(len(gray.payload), 65536)

    def test_invalid_size_format_threshold_and_payload_are_rejected(self):
        for kwargs in ({"pixel_format":"rgb"}, {"threshold":0}, {"threshold":256}, {"threshold":True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(HudBitmapError):
                encode_image(Image.new("L", (10, 10)), **kwargs)
        with self.assertRaises(HudBitmapError):
            encode_image(Image.new("L", (257, 10)))
        for bitmap in (HudBitmap(9, 1, "mono1_msb", 1, b"\0"),
                       HudBitmap(256, 256, "mono1_msb", 32, b"short"),
                       HudBitmap(256, 256, "gray8", 256, b"short")):
            with self.assertRaises(HudBitmapError):
                validate_bitmap(bitmap)

    def test_unconfigured_or_unreviewed_adapter_never_calls_sink(self):
        sink = Mock(return_value=True)
        bitmap = encode_image(Image.new("L", (8, 1), 255))
        for adapter in (BitmapDisplayAdapter(), BitmapDisplayAdapter(False, sink),
                        BitmapDisplayAdapter(True, None)):
            with self.assertRaises(DisplayUnavailable):
                adapter.publish(bitmap)
        sink.assert_not_called()

    def test_reviewed_memory_sink_gets_exact_bytes_and_rejects_gray8(self):
        sink = Mock(return_value=True)  # explicit in-memory test, not real device delivery
        adapter = BitmapDisplayAdapter(True, sink)
        bitmap = encode_image(Image.new("L", (9, 1), 255))
        self.assertTrue(adapter.publish(bitmap))
        sink.assert_called_once_with(bitmap.payload, 9, 1)
        with self.assertRaises(HudBitmapError):
            adapter.publish(encode_image(Image.new("L", (9, 1)), pixel_format="gray8"))
        self.assertEqual(sink.call_count, 1)
        sink.return_value = False
        with self.assertRaises(DisplayUnavailable):
            adapter.publish(bitmap)

    def test_missing_or_invalid_font_is_explicit(self):
        with self.assertRaises(FontUnavailable):
            load_font("missing-chinese-font.ttf")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.ttf"
            path.write_text("not a font")
            with self.assertRaises(FontUnavailable):
                load_font(path)


@unittest.skipUnless(FONT.is_file(), "provide a real Chinese font through HUD_TEST_FONT")
class ChineseHudTest(unittest.TestCase):
    def render(self, lines=None, **options):
        return render_hud({"mode":"demo", "provider":"demo", "simulated":True,
                           "lines":lines or ["请按键拍摄", "结果显示在此"]}, font_path=FONT, **options)

    def test_chinese_demo_is_real_nonempty_raster_and_three_rows(self):
        bitmap = self.render()
        self.assertEqual(bitmap.lines, ("【模拟演示】", "请按键拍摄", "结果显示在此"))
        self.assertEqual(bitmap.source, "demo")
        self.assertEqual((bitmap.width, bitmap.height, len(bitmap.payload)), (256, 256, 8192))
        self.assertIsNotNone(bitmap.to_image().getbbox())
        self.assertFalse(bitmap.truncated)
        different = self.render(["测试中文显示", "可见内容不同"])
        self.assertNotEqual(bitmap.payload, different.payload)

    def test_demo_label_cannot_be_replaced_by_content_or_title(self):
        bitmap = render_hud({"mode":"live", "provider":"openai", "simulated":True,
                             "title":"真实识别成功", "lines":["模型返回的任意标题"]}, font_path=FONT)
        self.assertEqual(bitmap.source, "demo")
        self.assertEqual(bitmap.lines[0], "【模拟演示】")

    def test_long_text_wraps_with_ellipsis_and_maximum_three_total_rows(self):
        bitmap = self.render(["这是一段很长的中文内容，必须短句显示而不能越界。" * 10])
        self.assertTrue(bitmap.truncated)
        self.assertEqual(len(bitmap.lines), 3)
        self.assertTrue(bitmap.lines[-1].endswith("…"))
        for maximum in (1, 2, 3):
            self.assertLessEqual(len(self.render(["内容" * 100], max_lines=maximum).lines), maximum)

    def test_live_source_requires_explicit_origin_and_preserves_preview_boundary(self):
        bitmap = render_hud({"mode":"live", "provider":"openai", "simulated":False,
                             "lines":["原文已识别", "译文请核对"]}, font_path=FONT)
        self.assertEqual(bitmap.lines[0], "【真实AI·预览】")
        for source in ({"mode":"live"}, {"mode":"live", "provider":"demo", "simulated":False}):
            with self.subTest(source=source), self.assertRaises(HudBitmapError):
                render_hud(dict(source, lines=["内容"]), font_path=FONT)
        local = render_hud({"lines":["尚未连接显示"]}, font_path=FONT)
        self.assertEqual(local.source, "local")
        self.assertEqual(local.lines[0], "【本地预览】")

    def test_missing_glyph_never_silently_becomes_tofu(self):
        font = load_font(FONT)
        with self.assertRaises(UnsupportedGlyph):
            require_glyphs(font, "\U0010ffff")
        with self.assertRaises(UnsupportedGlyph):
            self.render(["\U0010ffff"])

    def test_render_does_not_write_or_send_anything(self):
        with (patch.object(Path, "write_bytes") as binary, patch.object(Path, "write_text") as text,
              patch.object(Image.Image, "save") as save):
            self.render()
        binary.assert_not_called()
        text.assert_not_called()
        save.assert_not_called()

    def test_invalid_input_or_layout_fails_explicitly(self):
        for options in ({"width":40}, {"height":20}, {"max_lines":4}, {"font_size":65}):
            with self.subTest(options=options), self.assertRaises(HudBitmapError):
                self.render(**options)
        for content in (None, "not a list", [], [3], ["x" * 8001]):
            with self.subTest(content=str(content)[:30]), self.assertRaises(HudBitmapError):
                render_hud({"lines":content}, font_path=FONT)


if __name__ == "__main__":
    unittest.main()
