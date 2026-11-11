"""Bounded JPEG/PNG validation in memory; user images are never written."""
import base64
import binascii
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


def validate_image(data):
    if not isinstance(data, str):
        raise ValueError("图片必须是JPEG/PNG base64 data URL")
    if len(data) > 4 * ((MAX_IMAGE_BYTES + 2) // 3) + 32:
        raise ValueError("图片超过2MiB，请压缩后重试")
    header, sep, encoded = data.partition(",")
    expected = {"data:image/jpeg;base64": "JPEG", "data:image/png;base64": "PNG"}.get(header)
    if not sep or not expected or not encoded:
        raise ValueError("只允许非空JPEG/PNG base64 data URL")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("图片为空或超过2MiB")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != expected:
                    raise ValueError("图片内容与MIME类型不匹配")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("图片像素超过1600万，请缩小后重试")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                # Send only visible pixels, without EXIF/GPS, PNG metadata,
                # hidden animation frames or trailing bytes.
                clean = ImageOps.exif_transpose(image).convert("RGBA" if image.mode == "RGBA" or "transparency" in image.info else "RGB")
                if expected == "JPEG":
                    clean = clean.convert("RGB")
                clean.info.clear()
                output = io.BytesIO()
                clean.save(output, format=expected)
                sanitized = output.getvalue()
    except (binascii.Error, UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("图片无效、损坏或像素过大，请重新拍摄") from exc
    if len(sanitized) > MAX_IMAGE_BYTES:
        raise ValueError("图片清理后超过2MiB，请缩小后重试")
    return header + "," + base64.b64encode(sanitized).decode("ascii")
