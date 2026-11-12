"""Bench-only optical HUD exercise. The only CLI payload is a fixed Chinese demo."""
import argparse
import asyncio
import hashlib
from app.hud_bitmap import render_hud

WIDTH, HEIGHT = 192, 128
X, Y = 33, 65  # 1-based; the whole active rectangle fits in the circular display.
SAMPLE = {"mode": "demo", "simulated": True, "lines": ["按键确认", "取消关闭"]}


def draw_commands(bitmap, limit):
    """Generate bounded ASCII Lua commands from MSB-first, byte-aligned mono rows."""
    if (bitmap.width, bitmap.height, bitmap.pixel_format) != (WIDTH, HEIGHT, "mono1_msb"):
        raise ValueError("Render a centered 192x128 mono HUD first")
    stride = bitmap.stride_bytes
    # Use the largest Y coordinate and account for each escaped byte plus the ACK.
    header = f"frame.display.bitmap({X},{Y+HEIGHT-1},{WIDTH},2,0,'"
    tail = "');print('ok')"
    band_rows = (limit - len(header) - len(tail)) // (stride * 4)
    if band_rows < 1:
        raise ValueError("Negotiated payload too small for one bitmap row")
    yield "frame.display.power_save(false);frame.display.clear();print('ok')"
    yield "frame.display.assign_color(1,255,255,255);print('ok')"
    for row in range(0, HEIGHT, band_rows):
        pixels = bitmap.payload[row*stride:(row+band_rows)*stride]
        if any(pixels):
            escaped = "".join(f"\\x{v:02x}" for v in pixels)
            yield f"frame.display.bitmap({X},{Y+row},{WIDTH},2,0,'{escaped}{tail}"


def emulate(bitmap, limit):
    from halo_emulator import HaloEmulator
    from PIL import Image, ImageChops
    expected = Image.new("1", (256, 256), 0)
    expected.paste(bitmap.to_image(), (X-1, Y-1))
    if not expected.getbbox():
        raise ValueError("Empty HUD sample")
    with HaloEmulator(print_handler=lambda _: None) as emu:
        emu.connect()
        commands = list(draw_commands(bitmap, limit))
        for command in commands:
            if len(command.encode("ascii")) > limit:
                raise ValueError("Command exceeds negotiated payload")
            emu.execute_lua(command)
        frame = emu.get_framebuffer().convert("L").point(lambda v: 255 if v > 127 else 0, "1")
        if ImageChops.difference(expected, frame).getbbox():
            raise ValueError("Virtual optical framebuffer differs from host HUD pixels")
        print(f"Halo emulator: {len(commands)} commands, limit={limit}, pixel-perfect=65536/65536,"
              f" sha256={hashlib.sha256(frame.tobytes()).hexdigest()}, physical=false")


async def show_on_bench(bitmap, name):
    from brilliant_ble import BrilliantBle, BrilliantDeviceType
    device = BrilliantBle()
    await device.connect(name=name)
    try:
        if device.type != BrilliantDeviceType.HALO:
            raise ValueError("Select a Halo display")
        clear = "frame.display.clear();print('ok')"
        try:
            for command in draw_commands(bitmap, device.max_lua_payload()):
                ack = await device.send_lua(command, await_print=True)
                if str(ack).strip() != "ok":
                    raise RuntimeError("Unexpected Lua response")
            print("Lua acknowledged draw commands. Observe the optical image for 5 seconds.")
            await asyncio.sleep(5)
        finally:
            await device.send_lua(clear, await_print=True)
    finally:
        await device.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--halo-name", help="opt in to a named bench Halo in Lua REPL mode")
    parser.add_argument("--font", help="Chinese TrueType/OpenType font path")
    args = parser.parse_args()
    bitmap = render_hud(SAMPLE, width=WIDTH, height=HEIGHT, font_size=20, font_path=args.font)
    if args.halo_name:
        asyncio.run(show_on_bench(bitmap, args.halo_name))
    else:
        for limit in (160, 244, 509):
            emulate(bitmap, limit)


if __name__ == "__main__":
    main()

