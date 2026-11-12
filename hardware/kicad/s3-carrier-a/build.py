"""Check the carrier against the wiring table and firmware, then plot this board only."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAME = "s3-carrier-a"
SCH = NAME + ".kicad_sch"
PCB = NAME + ".kicad_pcb"


def check_netlist(xml_path):
    with (HERE / "pinmap.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    expected = {(r["ref"], r["pin"]): r["net"] for r in rows if r["net"] != "-"}
    actual = {}
    for net in ET.parse(xml_path).findall("./nets/net"):
        name = net.attrib["name"].removeprefix("/")
        if name.startswith("unconnected-"):
            continue
        for node in net.findall("node"):
            actual[node.attrib["ref"], node.attrib["pin"]] = name
    if expected != actual:
        raise ValueError(f"Pin/net mismatch: {expected.items() ^ actual.items()}")
    gpios = {r["net"]: int(r["pin_name"][2:]) for r in rows
             if r["ref"] == "J1" and r["net"] != "-" and r["pin_name"].startswith("IO")}
    ordered_nets = ["XCLK", "SCCB_SDA", "SCCB_SCL", *(f"D{i}" for i in range(8)),
                    "VSYNC", "HREF", "PCLK"]
    board_c = (REPO / "firmware/main/board.c").read_text(encoding="utf-8")
    profile = re.search(r'"devkitc_v1\.1_s3_carrier_a",\s*true,\s*false,\s*0,(.*?);', board_c, re.S)
    if not profile or list(map(int, re.findall(r"\d+", profile[1]))) != [gpios[n] for n in ordered_nets]:
        raise ValueError("S3 carrier pin order, button assignment or privacy lock differs from board.c")
    return len(actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default="kicad-cli")
    parser.add_argument("--out", type=Path, required=True, help="New empty output directory")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("--out must be empty to avoid mixing revisions")

    def run(*argv):
        subprocess.run([args.cli, *map(str, argv)], cwd=HERE, check=True)

    version = subprocess.check_output([args.cli, "version"], text=True).strip()
    run("sch", "erc", "--severity-all", "--exit-code-violations", "-o", output / "erc.rpt", SCH)
    run("pcb", "drc", "--severity-all", "--schematic-parity", "--exit-code-violations",
        "-o", output / "drc.rpt", PCB)
    netlist = output / "netlist.xml"
    run("sch", "export", "netlist", "--format", "kicadxml", "-o", netlist, SCH)
    pads = check_netlist(netlist)
    plots = output / "gerber"
    plots.mkdir()
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
    run("pcb", "export", "gerbers", "-l", layers, "-o", plots, PCB)
    run("pcb", "export", "drill", "-o", plots, PCB)
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "-o", output / "placement.csv", PCB)
    run("sch", "export", "pdf", "-o", output / "schematic.pdf", SCH)
    run("pcb", "export", "pdf", "-l", "F.Fab,F.Silkscreen,Edge.Cuts", "--mode-single",
        "-o", output / "assembly.pdf", PCB)
    files = [HERE / f for f in (SCH, PCB, NAME + ".kicad_pro", "Carrier.kicad_sym", "pinmap.csv")]
    checks = {"cli": version, "connected_pads": pads, "firmware_pinmap_matches": True,
              "hardware_tested": False, "release": "bench engineering review",
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (output / "verification.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

