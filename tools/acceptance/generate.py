"""Generate explicitly synthetic, non-sensitive fixtures into an ignored folder."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).with_name("manifest.json")
PRIVATE_ROOT = ROOT / "artifacts" / "private" / "acceptance"
DEFAULT_IMAGE_DIR = PRIVATE_ROOT / "images"
COLORS = {"red": "#d92929", "blue": "#1765d1", "green": "#128345", "yellow": "#f3d332",
          "orange": "#ef8018", "purple": "#8c43c5", "gray": "#7c8792"}


def load_manifest(path=DEFAULT_MANIFEST):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if manifest.get("source") != "synthetic_fixture" or len(samples) != 20:
        raise ValueError("manifest must identify exactly 20 synthetic fixtures")
    ids = set()
    for sample in samples:
        identifier = sample.get("id", "")
        if (identifier in ids or len(identifier) != 3 or identifier[0] not in "VT"
                or not identifier[1:].isdigit() or sample.get("image") != identifier + ".png"
                or sample.get("kind") not in ("vision", "translate")
                or not isinstance(sample.get("question"), str) or not sample["question"].strip()
                or not sample.get("expected", {}).get("text")):
            raise ValueError("invalid or duplicate fixture definition")
        if sample["kind"] == "vision" and not sample.get("shapes"):
            raise ValueError("vision fixture must define shapes")
        if sample["kind"] == "translate" and (sample.get("source_language") not in ("auto", "en", "zh-CN")
                                               or sample.get("target_language") not in ("en", "zh-CN")):
            raise ValueError("OCR fixtures must explicitly select supported source/target languages")
        ids.add(identifier)
    if sum(s["kind"] == "vision" for s in samples) != 10:
        raise ValueError("manifest must contain 10 vision and 10 translate fixtures")
    return manifest


def choose_font(size):
    for name in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def centered(draw, text, y, font, color="#17202a"):
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text(((1200 - bounds[2] + bounds[0]) / 2, y), text, font=font, fill=color)


def render(sample):
    image = Image.new("RGB", (1200, 840), "#f7f9fb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 92), fill="#17202a")
    centered(draw, "SYNTHETIC FIXTURE / NOT A CAMERA PHOTO", 15, choose_font(30), "white")
    centered(draw, sample["id"] + " - " + sample["kind"].upper(), 58, choose_font(18), "#c5d0df")
    if sample["kind"] == "translate":
        draw.rounded_rectangle((65, 200, 1135, 700), radius=20, fill="white", outline="#17202a", width=6)
        lines = sample["expected"]["text"]
        font_size = 64
        font = choose_font(font_size)
        while max(draw.textlength(line, font=font) for line in lines) > 1000:
            font_size -= 2
            font = choose_font(font_size)
        top = 420 - (len(lines) - 1) * 65
        for index, line in enumerate(lines):
            centered(draw, line, top + index * 130, font)
    else:
        for item in sample["shapes"]:
            left, top, right, bottom = item["box"]
            color = COLORS[item["color"]]
            if item["shape"] in ("circle", "ellipse"):
                draw.ellipse(item["box"], fill=color, outline="#26313d", width=4)
            elif item["shape"] == "rectangle":
                draw.rectangle(item["box"], fill=color, outline="#26313d", width=4)
            else:
                sides = 3 if item["shape"] == "triangle" else 5
                cx, cy = (left + right) / 2, (top + bottom) / 2
                points = [(cx + (right-left) / 2 * math.cos(-math.pi/2 + i*2*math.pi/sides),
                           cy + (bottom-top) / 2 * math.sin(-math.pi/2 + i*2*math.pi/sides)) for i in range(sides)]
                draw.polygon(points, fill=color, outline="#26313d", width=4)
            font = choose_font(26)
            width = draw.textlength(item["label"], font=font)
            draw.text(((left+right-width)/2, bottom+8), item["label"], fill="#17202a", font=font)
    centered(draw, "Non-sensitive generated test data; human scoring is required.", 798, choose_font(22))
    return image


def generate_images(manifest=None, image_dir=DEFAULT_IMAGE_DIR):
    manifest = manifest or load_manifest()
    image_dir = Path(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    for sample in manifest["samples"]:
        with render(sample) as image:
            image.save(image_dir / sample["image"], format="PNG")
    return len(manifest["samples"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    count = generate_images()
    print(f"Generated {count} synthetic fixtures in artifacts/private/acceptance/images (ignored).")
    print("This prepares input data; it is not a real AI or natural-scene acceptance result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
