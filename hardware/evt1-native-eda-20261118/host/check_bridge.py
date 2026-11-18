#!/usr/bin/env python3
"""Drive the checked-in FPGA model with packets from the host encoder."""

import subprocess
import tempfile
from pathlib import Path

from bridge_packets import frame_write, optical_control, qio_nibbles


HERE = Path(__file__).resolve().parent
RTL = HERE.parents[1] / "evt1-rev-d1-1-20261117" / "03_FPGA_RTL"


def main() -> None:
    transactions = [
        frame_write(eye="left", start_word=0x123, words=[0x1234, 0x5678], tear_guard=False),
        frame_write(eye="right", start_word=0x4AFF, words=[0xBEEF], tear_guard=True),
        optical_control(power=True, arm_raw=True),
        # Synthetic 0xA4-shaped RAW payload. It must mirror to both eyes
        # without decoding as power-off. No panel command is implied.
        optical_control(power=False),
        optical_control(power=False),
    ]
    expected = ["a0012312345678", "a34affbeef", "a400000006", "a400000000", "a400000000"]
    if [payload.hex() for payload in transactions] != expected:
        raise AssertionError("wire octets differ from the independent protocol fixtures")
    invalid = [
        lambda: frame_write(eye="left", start_word=19199, words=[1, 2], tear_guard=False),
        lambda: frame_write(eye="right", start_word=0, words=[], tear_guard=False),
        lambda: optical_control(power=False, scan=True),
        lambda: optical_control(power=True, scan=True, arm_raw=True),
    ]
    for encode in invalid:
        try:
            encode()
        except ValueError:
            continue
        raise AssertionError("invalid host request was encoded")

    with tempfile.TemporaryDirectory(prefix="evt1-host-wire-") as directory:
        work = Path(directory)
        # 0x10 means CS high with SCK low. The rest are QIO nibbles.
        stream = [value for payload in transactions for value in (*qio_nibbles(payload), 16)]
        (work / "host_wire.hex").write_bytes("".join(f"{value:02x}\n" for value in stream).encode())
        compile_cmd = [
            "iverilog", "-g2005", "-Wall", "-s", "tb_evt1_host_wire", "-o", "sim.vvp",
            str(RTL / "evt1_ar_display_fpga_bridge_rev_c.v"),
            str(RTL / "ice40_spram_ebr_sim.v"), str(HERE / "tb_evt1_host_wire.v"),
        ]
        subprocess.run(compile_cmd, cwd=work, check=True, timeout=60)
        result = subprocess.run(["vvp", "sim.vvp"], cwd=work, check=True, timeout=60,
                                capture_output=True, text=True)
        print(result.stdout, end="")
        if "HOST_WIRE_PASS" not in result.stdout:
            raise AssertionError("RTL did not reach the host wire success assertion")


if __name__ == "__main__":
    main()
