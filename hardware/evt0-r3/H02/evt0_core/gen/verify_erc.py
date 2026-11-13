"""Run native ERC and compare all exported pins to design.py and KiCad library pads."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import design

project = Path(__file__).resolve().parents[1]
evidence = project.parents[1] / "evidence"
evidence.mkdir(exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--cli", default="kicad-cli")
    parser.add_argument("--share", type=Path, required=True, help="KiCad resource root containing template and footprints")
    args = parser.parse_args()
    version = subprocess.check_output([args.cli, "version"], text=True).strip()
    major = version.split(".")[0]
    share = args.share.resolve()
    os.chdir(project)
    sch = Path("evt0_core.kicad_sch")
    report = evidence / "evt0-erc.rpt"
    xml_path = project / "evidence" / "evt0_core.xml"
    xml_path.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as confdir:
        conf = Path(confdir) / f"{major}.0"
        conf.mkdir()
        for libtable in ("fp-lib-table","sym-lib-table"):
            shutil.copyfile(share/"template"/libtable, conf/libtable)
        env = dict(os.environ, KICAD_CONFIG_HOME=confdir)
        env[f"KICAD{major}_FOOTPRINT_DIR"] = str(share/"footprints")
        env[f"KICAD{major}_SYMBOL_DIR"] = str(share/"symbols")
        subprocess.run([args.cli, "sch", "erc", "--severity-all", "--exit-code-violations", "-o", report, sch], env=env, check=True)
        subprocess.run([args.cli, "sch", "export", "netlist", "--format", "kicadxml", "-o", xml_path, sch], env=env, check=True)
    # Scrub the one machine-local path in the export while preserving every connection.
    tree=ET.parse(xml_path)
    tree.find("./design/source").text=sch.name
    tree.write(xml_path,encoding="utf-8",xml_declaration=True)
    actual={}
    for net in tree.findall("./nets/net"):
        for node in net.findall("node"):
            key=(node.get("ref"),node.get("pin"))
            if key in actual:
                raise ValueError(f"Duplicate net assignment {key}")
            name=net.get("name")
            actual[key] = design.NC if name.startswith("unconnected-(") else name.removeprefix("/")
    expected={(p["ref"], pin): net for p in design.P if not p["ref"].startswith("#") for pin,net in p["nets"].items()}
    if actual != expected:
        raise ValueError(f"Netlist does not match design: {set(actual.items()) ^ set(expected.items())}")
    library_hashes={}
    for p in design.P:
        if p["ref"].startswith("#"):
            continue
        fp=p["fp"] or design.SYMS[p["sym"]]["fp"]
        lib,name=fp.split(":")
        filename=share/"footprints"/(lib+".pretty")/(name+".kicad_mod")
        pads=set(re.findall(r'\(pad\s+"([^"]+)"',filename.read_text(encoding="utf-8")))
        if set(p["nets"]) != pads:
            raise ValueError(f"{p['ref']} pad numbers mismatch: {pads ^ set(p['nets'])}")
        library_hashes[fp]=digest(filename)
    info={"kicad_cli_version":version,"material_components":len(tree.findall("./components/comp")),
          "numbered_pins_checked":len(actual),"connected_nets":len({v for v in actual.values() if v!=design.NC}),
          "erc_exit":0,"native_netlist_equals_source":True,
          "inputs_sha256":{str(path):digest(path) for path in (sch, Path("evt0_core.kicad_pro"), Path("aiar.kicad_sym"), Path("sym-lib-table"), Path("gen/design.py"), Path("gen/gen_kicad.py"))},
          "official_footprint_sha256":dict(sorted(library_hashes.items())), "netlist_sha256":digest(xml_path),"erc_report_sha256":digest(report)}
    (evidence/"evt0-erc-inputs.json").write_text(json.dumps(info,indent=2)+"\n",encoding='utf-8')
    print(f"{len(actual)} numbered pins / {len(library_hashes)} footprints matched")


if __name__ == "__main__":
    main()
