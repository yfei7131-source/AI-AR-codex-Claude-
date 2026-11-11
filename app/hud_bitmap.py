"""In-memory Chinese HUD rasterization; no implicit display or network access.

The optional command line sample contains fixed, non-sensitive demo text only:
    python -m app.hud_bitmap --sample
It writes under ignored artifacts/private/ar. General render calls never write.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

PIXEL_FORMATS = ("mono1_msb", "gray8")
ROOT = Path(__file__).resolve().parents[1]


class HudBitmapError(ValueError):
    pass


class FontUnavailable(HudBitmapError):
    pass


class UnsupportedGlyph(HudBitmapError):
    pass


class DisplayUnavailable(HudBitmapError):
    pass


@dataclass(frozen=True)
class HudBitmap:
    width: int
    height: int
    pixel_format: str
    stride_bytes: int
    payload: bytes
    lines: tuple[str, ...] = ()
    source: str = "local"
    truncated: bool = False

    def to_image(self):
        """Return an in-memory preview; does not claim a device accepted pixels."""
        validate_bitmap(self)
        return Image.frombytes("1" if self.pixel_format == "mono1_msb" else "L",
                               (self.width, self.height), self.payload)


def validate_bitmap(bitmap):
    if (not isinstance(bitmap, HudBitmap) or type(bitmap.width) is not int or type(bitmap.height) is not int
            or not 1 <= bitmap.width <= 256 or not 1 <= bitmap.height <= 256
            or bitmap.pixel_format not in PIXEL_FORMATS):
        raise HudBitmapError("bitmap requires supported pixels and dimensions of 1–256")
    stride = (bitmap.width + 7) // 8 if bitmap.pixel_format == "mono1_msb" else bitmap.width
    if (bitmap.stride_bytes != stride or not isinstance(bitmap.payload, bytes)
            or len(bitmap.payload) != stride * bitmap.height):
        raise HudBitmapError("bitmap payload length or row stride is invalid")


def encode_image(image, *, pixel_format="mono1_msb", threshold=128):
    """Pack row-major pixels. mono1 uses MSB first and 1=white, 0=black."""
    if not isinstance(image, Image.Image) or not 1 <= image.width <= 256 or not 1 <= image.height <= 256:
        raise HudBitmapError("image dimensions must be 1–256")
    if pixel_format not in PIXEL_FORMATS or type(threshold) is not int or not 1 <= threshold <= 255:
        raise HudBitmapError("unsupported pixel format or threshold (1–255)")
    gray = image.convert("L")
    if pixel_format == "mono1_msb":
        pixels = gray.point(lambda value: 255 if value >= threshold else 0).convert("1", dither=Image.Dither.NONE)
        stride = (image.width + 7) // 8
    else:
        pixels, stride = gray, image.width
    return HudBitmap(image.width, image.height, pixel_format, stride, pixels.tobytes())


def load_font(font_path=None, font_size=24):
    if type(font_size) is not int or not 10 <= font_size <= 64:
        raise HudBitmapError("font_size must be an integer from 10 to 64")
    path = Path(font_path) if font_path is not None else Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
    if not path.is_file():
        raise FontUnavailable("a readable Chinese font is required; pass font_path explicitly")
    try:
        return ImageFont.truetype(str(path), font_size)
    except (OSError, ValueError) as exc:
        raise FontUnavailable("font_path could not be loaded as a TrueType/OpenType font") from exc


def require_glyphs(font, text):
    """Reject missing .notdef glyphs rather than silently drawing tofu boxes."""
    missing = font.getmask("\U0010ffff")
    missing_signature = (missing.size, bytes(missing))
    for character in set(text):
        if character.isspace():
            continue
        glyph = font.getmask(character)
        if (glyph.size, bytes(glyph)) == missing_signature or glyph.getbbox() is None:
            raise UnsupportedGlyph(f"font has no usable glyph for U+{ord(character):04X}")


def source_label(hud):
    mode, simulated = hud.get("mode"), hud.get("simulated")
    if mode == "demo" or simulated is True:
        return "demo", "【模拟演示】"
    if mode == "live":
        if simulated is not False or hud.get("provider") != "openai":
            raise HudBitmapError("live HUD requires provider=openai and simulated=false")
        return "live", "【真实AI·预览】"
    if mode not in (None, "local"):
        raise HudBitmapError("unsupported HUD source")
    return "local", "【本地预览】"


def fit_lines(text_lines, draw, font, width, budget):
    output, remainder = [], False
    for text in text_lines:
        text = " ".join(text.split())
        current = ""
        for character in text:
            if draw.textlength(current + character, font=font) > width:
                if not current:
                    raise HudBitmapError("a text glyph does not fit the available width")
                output.append(current)
                current = ""
            current += character
        if current:
            output.append(current)
    if len(output) > budget:
        remainder = True
        output = output[:budget]
        if output:
            while output[-1] and draw.textlength(output[-1] + "…", font=font) > width:
                output[-1] = output[-1][:-1]
            output[-1] += "…"
    return output, remainder


def render_hud(hud, *, font_path=None, font_size=24, width=256, height=256,
               pixel_format="mono1_msb", threshold=128, max_lines=3):
    """Render at most three text rows total, including a mandatory source row.

    Text remains only in the returned in-memory object. No title from model
    content can replace or truncate the mandatory source label.
    """
    if (not isinstance(hud, dict) or type(width) is not int or type(height) is not int
            or not 1 <= width <= 256 or not 1 <= height <= 256
            or type(max_lines) is not int or not 1 <= max_lines <= 3):
        raise HudBitmapError("HUD requires dimensions 1–256 and max_lines 1–3")
    content = hud.get("lines")
    if (not isinstance(content, (list, tuple)) or not content or len(content) > 32
            or any(not isinstance(text, str) for text in content)
            or sum(len(text) for text in content) > 8000):
        raise HudBitmapError("HUD lines must contain 1–32 text entries, at most 8000 characters")
    source, label = source_label(hud)
    font = load_font(font_path, font_size)
    require_glyphs(font, label + "…")
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    margin, gap = 12, 12
    available_width = width - 2 * margin
    if draw.textlength(label, font=font) > available_width:
        raise HudBitmapError("mandatory source label does not fit; increase width or reduce font_size")
    body, truncated = fit_lines(content, draw, font, available_width, max_lines - 1)
    lines = [label] + body
    require_glyphs(font, "".join(lines))
    bounds = [draw.textbbox((0, 0), text, font=font) for text in lines]
    row_height = max(box[3] - box[1] for box in bounds)
    if 2 * margin + len(lines) * row_height + (len(lines) - 1) * gap > height:
        raise HudBitmapError("HUD rows do not fit the available height; reduce font_size")
    y = margin
    for text, box in zip(lines, bounds):
        draw.text((margin - box[0], y - box[1]), text, font=font, fill=255)
        y += row_height + gap
    packed = encode_image(image, pixel_format=pixel_format, threshold=threshold)
    return HudBitmap(packed.width, packed.height, packed.pixel_format, packed.stride_bytes,
                     packed.payload, tuple(lines), source, truncated or bool(hud.get("truncated")))


@dataclass
class BitmapDisplayAdapter:
    """An unconfigured adapter refuses delivery. This module binds no device."""
    reviewed: bool = False
    sink: Callable[[bytes, int, int], bool] | None = None

    @property
    def ready(self):
        return self.reviewed is True and callable(self.sink)

    def publish(self, bitmap):
        if not self.ready:
            raise DisplayUnavailable("optical display is unconfigured or unreviewed; no pixels were sent")
        validate_bitmap(bitmap)
        if bitmap.pixel_format != "mono1_msb":
            raise HudBitmapError("the current firmware adapter accepts packed 1bpp only; convert gray8 explicitly")
        if self.sink(bitmap.payload, bitmap.width, bitmap.height) is not True:
            raise DisplayUnavailable("reviewed display sink did not confirm acceptance")
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", action="store_true", help="write fixed, non-sensitive Chinese demo sample only")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--pixel-format", choices=PIXEL_FORMATS, default="mono1_msb")
    args = parser.parse_args(argv)
    if not args.sample:
        parser.error("use --sample to generate the fixed demo; general HUD content is memory-only")
    try:
        bitmap = render_hud({"mode": "demo", "simulated": True, "provider": "demo",
                             "lines": ["请按键拍摄", "结果显示在此"]},
                            font_path=args.font, pixel_format=args.pixel_format)
        output = ROOT / "artifacts/private/ar"
        output.mkdir(parents=True, exist_ok=True)
        name = "hud_demo_" + bitmap.pixel_format
        bitmap.to_image().save(output / (name + ".png"))
        (output / (name + ".bin")).write_bytes(bitmap.payload)
        metadata = {"width": bitmap.width, "height": bitmap.height, "pixel_format": bitmap.pixel_format,
                    "stride_bytes": bitmap.stride_bytes, "payload_bytes": len(bitmap.payload),
                    "source": "demo", "hardware_verified": False, "delivered_to_device": False}
        (output / (name + ".json")).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    except (HudBitmapError, OSError):
        print("FAIL: Chinese rasterization/font or sample output is unavailable; no display result was claimed.")
        return 1
    print(f"Generated fixed demo: artifacts/private/ar/{name}.png; bytes={len(bitmap.payload)}; device_delivery=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
