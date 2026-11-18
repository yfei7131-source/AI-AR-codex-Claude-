"""Host reference encoder for the Rev D1.1 FPGA. Payloads are bytes, not SPI transactions."""

WORDS_PER_EYE = 19_200


def frame_write(*, eye: str, start_word: int, words: list[int], tear_guard: bool) -> bytes:
    """Encode a single CS-low write, with big-endian address and 16-bit pixel words."""
    if eye not in ("left", "right"):
        raise ValueError("eye must be left or right")
    if not words or start_word < 0 or start_word + len(words) > WORDS_PER_EYE:
        raise ValueError("write must fit the selected eye's 19,200 words")
    if any(not 0 <= word <= 0xFFFF for word in words):
        raise ValueError("pixel word outside 16-bit range")
    opcode = 0xA0 | int(eye == "right") | (int(tear_guard) << 1)
    return bytes([opcode]) + start_word.to_bytes(2, "big") + b"".join(
        word.to_bytes(2, "big") for word in words
    )


def optical_control(*, power: bool, scan: bool = False, arm_raw: bool = False) -> bytes:
    """Encode A4. RAW also requires the previous transaction to have stopped scanning."""
    if (scan or arm_raw) and not power:
        raise ValueError("scan and RAW require optical power permission")
    if scan and arm_raw:
        raise ValueError("RAW is only available with scan stopped")
    flags = int(scan) | (int(power) << 1) | (int(arm_raw) << 2)
    return bytes((0xA4, 0, 0, 0, flags))


def qio_nibbles(payload: bytes) -> tuple[int, ...]:
    """QIO[3:0] sampled on each rising SCK, high nibble before low nibble."""
    return tuple(nibble for byte in payload for nibble in (byte >> 4, byte & 0xf))
