"""Check the fabricated board against the camera-rail bench circuit, then plot."""
import argparse
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def check_netlist(path):
    expected = {
        "/VIN_3V3": {"J1.1", "J3.1"},
        "/CAM_3V3": {"J3.2", "J2.1", "R1.1", "C1.2"},
        "/LED_A": {"R1.2", "D1.2"},
        "/GND": {"J1.2", "J2.2", "D1.1", "C1.1"},
    }
    root = ET.parse(path).getroot()
    nets = {
        net.attrib["name"]: {
            f'{pin.attrib["ref"]}.{pin.attrib["pin"]}' for pin in net.findall("node")
        } for net in root.findall("./nets/net")
    }
    if nets != expected:
        raise ValueError(f"CAM-RAIL-A pin contract changed: {nets}")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--cli", default="kicad-cli")
    parser.add_argument("--out", required=True, type=Path,
                        help="New or empty directory for validation and fabrication outputs.")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("pick a new or empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(Path(__file__).resolve().parent)
    def run(*argv):
        subprocess.run([args.cli, *argv], check=True)
    pcb = "cam-rail-a.kicad_pcb"
    sch = "cam-rail-a.kicad_sch"
    run("sch", "erc", "--severity-all", "--exit-code-violations", "-o", output/"erc.rpt", sch)
    run("pcb", "drc", "--schematic-parity", "--severity-all", "--exit-code-violations", "-o", output/"drc.rpt", pcb)
    run("sch", "export", "netlist", "--format", "kicadxml", "-o", output/"schematic.xml", sch)
    check_netlist(output/"schematic.xml")
    run("sch", "export", "pdf", "-o", output/"schematic.pdf", sch)
    plots = output/"gerbers"
    plots.mkdir()
    run("pcb", "export", "gerbers", "--use-drill-file-origin", "--layers",
        "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,Edge.Cuts",
        "-o", str(plots)+os.sep, pcb)
    run("pcb", "export", "drill", "--drill-origin", "plot", "--excellon-units", "mm", "--format", "excellon", "-o", str(plots)+os.sep, pcb)
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--use-drill-file-origin",
        "-o", output/"placement-mm.csv", pcb)
    run("pcb", "export", "pdf", "--layers", "Edge.Cuts,F.Fab,F.Silkscreen,F.Cu",
        "-o", output/"assembly-top.pdf", pcb)
    run("pcb", "export", "step", "--drill-origin", "-o", output/"cam-rail-a.step", pcb)


if __name__ == "__main__":
    main()


