#!/usr/bin/env python3
"""Check U11's primary-source production-artifact measurements from Nordic's ZIP."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from audit_u11 import REF_ZIP_URL


VENDOR_ZIP_SHA = "c6cc5cf123afa0ac2e2609b5793a3deecdfe33ecdbaaf44a4a7d0b78c065f60d"
GERBER_FLASH = re.compile(r"(?:X(-?\d+))?(?:Y(-?\d+))?(?:D0([123]))?\*")
DRILL_COORD = re.compile(r"(?:X(-?\d+))?(?:Y(-?\d+))?")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def gerber_flashes(source):
    if "%FSLAX24Y24*%" not in source or "%MOIN*%" not in source:
        raise ValueError("Expected original Nordic 2.4 inch artwork")
    apertures = {}
    flashes = defaultdict(list)
    x = y = tool = None
    for line in source.splitlines():
        if aperture := re.fullmatch(r"%ADD(\d+)C,([\d.]+)\*%", line):
            apertures[int(aperture[1])] = float(aperture[2]) * 25.4
        if tool_selection := re.fullmatch(r"D([1-9]\d+)\*", line):
            tool = int(tool_selection[1])
        if coordinate := GERBER_FLASH.fullmatch(line):
            if coordinate[1] is not None:
                x = int(coordinate[1])
            if coordinate[2] is not None:
                y = int(coordinate[2])
            if coordinate[3] == "3":
                flashes[tool].append((x, y))
    return apertures, flashes


def blind_drills(source):
    source = "\n".join(source.splitlines())
    if ";FILE_FORMAT=2:4" not in source or "INCH,TZ" not in source or ";TYPE=PLATED" not in source:
        raise ValueError("Expected plated Nordic 2.4 inch TX1 Excellon")
    tool_sizes = re.findall(r"^T\d+F\d+S\d+C([\d.]+)$", source, re.MULTILINE)
    if len(tool_sizes) != 1:
        raise ValueError("Unexpected TX1 drill-tool inventory")
    x = y = None
    coordinates = []
    for line in source.splitlines():
        if line and (xy := DRILL_COORD.fullmatch(line)):
            if xy[1] is not None:
                x = int(xy[1])
            if xy[2] is not None:
                y = int(xy[2])
            coordinates.append((x, y))
    return float(tool_sizes[0]) * 25.4, coordinates


def check_archive(path):
    if sha(path.read_bytes()) != VENDOR_ZIP_SHA:
        raise ValueError("Vendor archive differs from Nordic reference layout release 1.3")
    with ZipFile(path) as archive:
        files = {Path(name).name: archive.read(name) for name in archive.namelist()
                 if name.startswith("nRF5340-CMAA Reference Layout 1_0/")
                 and Path(name).name.startswith("nrf5340_cmaa_config3")}
    file = "nrf5340_cmaa_config3."
    copper_files = sorted(name for name in files if name.startswith(file) and
                          re.fullmatch(r"G(?:TL|BL|\d+)", name.removeprefix(file)))
    if copper_files != [file + suffix for suffix in ("G1", "G2", "GBL", "GTL")]:
        raise ValueError("Unexpected Nordic copper-layer export")
    top_apertures, top_flashes = gerber_flashes(files[file + "GTL"].decode("ascii"))
    mask_apertures, mask_flashes = gerber_flashes(files[file + "GTS"].decode("ascii"))
    drill_mm, drills = blind_drills(files[file + "TX1"].decode("ascii"))
    pads = set(mask_flashes[21])
    top = set(top_flashes[13])
    if len(pads) != 95 or not pads <= top or len(drills) != 30 or not set(drills) <= top:
        raise ValueError("Nordic copper, mask and drill flash cross-match changed")
    drill_report = "\n".join(files[file + "DRR"].decode("ascii").splitlines())
    layer_pairs = re.findall(r"^Layer Pair : (.*)$", drill_report, re.MULTILINE)
    if layer_pairs != ["Top Layer to Bottom Layer", "Top Layer to Mid Layer 1"] or not re.search(
            r"T2\s+10mil \(0\.249mm\)\s+Round\s+58\s+PTH", drill_report):
        raise ValueError("Nordic drill layer pairs or plated through count changed")
    coincidence_count = len(pads & set(drills))
    if coincidence_count != 11:
        raise ValueError("Nordic centered blind via count changed")
    ring = (top_apertures[13] - drill_mm) / 2
    proof_files = [*copper_files, file + "GTS", file + "TX1", file + "DRR", "nrf5340_cmaa_config3_schematic.pdf"]
    return {
        "source_url": REF_ZIP_URL, "zip_sha256": VENDOR_ZIP_SHA,
        "file_sha256": {name: sha(files[name]) for name in proof_files},
        "official_config3_copper_files": copper_files,
        "plated_through_layer_pair": layer_pairs[0], "plated_through_drill_count": 58,
        "blind_laser_layer_pair": layer_pairs[1], "blind_laser_count": len(drills),
        "blind_laser_centered_on_wlcsp_land_count": coincidence_count,
        "wlcsp_land_count": len(pads), "wlcsp_copper_aperture_mm": round(top_apertures[13], 5),
        "wlcsp_mask_aperture_mm": round(mask_apertures[21], 5), "blind_laser_nominal_drill_mm": round(drill_mm, 5),
        "derived_nominal_ring_mm": round(ring, 5), "derived_nominal_ring_mil": round(ring / 0.0254, 3),
        "scope": "Nordic Gerber artwork and nominal drill geometry; independent EVT-1 process and rule approval required.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Unmodified Nordic release 1.3 ZIP")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = json.dumps(check_archive(args.archive), indent=2) + "\n"
    output = Path(__file__).with_name("nordic-config3-artwork-verification.json")
    if args.check:
        if output.read_text(encoding="utf-8") != report:
            raise ValueError("Nordic artwork report differs from committed result")
    else:
        output.write_text(report, encoding="utf-8", newline="\n")
    print("Nordic Config 3 verified: 4 copper layers, one blind stage, 95 WLCSP mask/copper matches, 11 of 30 blind drills centered on WLCSP lands.")


if __name__ == "__main__":
    main()
