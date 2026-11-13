"""Cross-check the reference harness against the actual firmware and frozen feature table."""
import csv
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read_rows(name):
    with (HERE / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    pins = read_rows("eye-v22-j4.csv")
    if [int(row["pin"]) for row in pins] != list(range(1, 25)):
        raise ValueError("Expected J4 pins 1 through 24 exactly once")
    wired = {r["firmware_signal"]: int(r["gpio"]) for r in pins if r["gpio"]}
    board = (ROOT / "firmware/main/board.c").read_text(encoding="utf-8")
    pattern = (r'"esp32_s3_eye_mb_v2\.2",\s*true,\s*false,\s*(\d+),\s*(\d+),\s*(\d+),'
               r'\s*(\d+),\s*\{([^}]+)\},\s*(\d+),\s*(\d+),\s*(\d+)')
    profile = re.search(pattern, board)
    if not profile:
        raise ValueError("Re-review the EYE profile and interlock before changing this check")
    button, xclk, sda, scl, data, vsync, href, pclk = profile.groups()
    firmware = dict(zip(["xclk", "sda", "scl", "vsync", "href", "pclk"],
                        map(int, [xclk, sda, scl, vsync, href, pclk])))
    firmware.update({f"d{i}": int(pin) for i, pin in enumerate(data.split(","))})
    if wired != firmware or button != "0" or len(set(wired.values())) != 14:
        raise ValueError("Actual firmware and the reviewed EYE signal allocation differ")
    frozen = (ROOT / "docs/FEATURES_F01_F22.md").read_text(encoding="utf-8")
    expected = re.findall(r'^\| (F\d{2}) \| [^|]+ \| (P0|P1|R) \|', frozen, re.M)
    feature_rows = read_rows("feature-handoff.csv")
    actual = [(row["id"], row["priority"]) for row in feature_rows]
    if actual != expected or Counter(level for _, level in actual) != {"P0":16, "P1":5, "R":1}:
        raise ValueError("Hardware handoff and frozen product requirements differ")
    loads = read_rows("power-budget.csv")
    power = sum(float(r["rail_v"]) * int(r["allocated_peak_ma"]) / 1000 for r in loads)
    print(f"J4: {len(pins)} pins, {len(wired)} firmware signals, button=0, interlock locked")
    print(f"Features: {len(actual)} consistent with frozen table (16 P0, 5 P1, 1 R)")
    print(f"Design allocation at 3.3 V: {power:.3f} W; 3.0 V pack at assumed 85% efficiency: "
          f"{power / 3.0 / 0.85:.3f} A; audio/optics excluded. No measurements.")


if __name__ == "__main__":
    main()

