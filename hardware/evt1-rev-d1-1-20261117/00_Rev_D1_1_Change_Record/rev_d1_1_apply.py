#!/usr/bin/env python3
"""Generate isolated Rev D1.1 from immutable PR21 Rev D1. NOT FOR FAB."""
import argparse,csv,difflib,hashlib,importlib.util,json,shutil,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
      for p in sorted(root.rglob('*'),key=lambda p:p.relative_to(root).as_posix())
      if p.is_file() and '__pycache__' not in p.parts}

def rd(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def wr(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,default=HERE.parent.parent/'evt1-rev-d1-20261117')
    p.add_argument('--output',type=Path,default=HERE.parent)
    a=p.parse_args();base=a.baseline.resolve();out=a.output.resolve()
    if base==out or base in out.parents or out in base.parents:raise SystemExit('Separate baseline/output required')
    before=hashes(base)
    for line in (base/'SHA256SUMS.txt').read_text(encoding='utf8').splitlines():
        expected,rel=line.split(maxsplit=1)
        if hashlib.sha256((base/rel.strip()).read_bytes()).hexdigest()!=expected:raise SystemExit('Rev D1 source mismatch: '+rel)
    with tempfile.TemporaryDirectory(prefix='evt1-d11-') as td:
        stage=Path(td)/'package'
        shutil.copytree(base,stage,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.rmtree(stage/'00_Rev_D1_Change_Record')
        shutil.rmtree(stage/'04_Verification_Evidence');(stage/'04_Verification_Evidence').mkdir()
        shutil.copytree(HERE,stage/HERE.name,ignore=shutil.ignore_patterns('__pycache__'))
        for dirname in ['03_FPGA_RTL','05_Verification_Scripts']:
            for f in (HERE.parent/dirname).iterdir():
                if f.is_file() and f.suffix not in ['.vvp','.json','.asc','.rpt','.log']:
                    shutil.copy2(f,stage/dirname/f.name)
        tbl=stage/'02_BOM_PINMAP_ICD_Blocked'
        net=rd(tbl/'NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv');bom=rd(tbl/'BOM_V1_0_FROZEN.csv')
        spec=importlib.util.spec_from_file_location('avdd',HERE/'avdd_safety_corrections.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        result=m.apply_avdd_safety_corrections(net,bom)
        if result is not None:net,bom=result
        spec=importlib.util.spec_from_file_location('sync',HERE/'sync_rev_d1_1.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.sync(stage,base,net,bom)
        wr(tbl/'NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv',net);wr(tbl/'BOM_V1_0_FROZEN.csv',bom)
        pm=[dict(Chip_Ref=r['RefDes'],Pin_ID=r['Pin'],Pin_Name=r['Pin_Function'],Signal_Net_Name=r['Net'],
          Direction=r['Role'],Voltage_Domain=r['Domain_V'],Board=r['Board'],BOM_Line=r['BOM_Line'],
          Datasheet_Verification_Note=r['Note'],Rev_D1_1_Status='SOURCE_DERIVED; NOT_FOR_FAB') for r in net]
        wr(tbl/'PINMAP_V1_0_FROZEN.csv',pm)
        obsolete=['02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv',
          '02_BOM_PINMAP_ICD_Blocked/BOM_COMPONENT_INSTANCES_REV_D1.csv',
          '02_BOM_PINMAP_ICD_Blocked/MASS_PLAN_REV_D1.csv',
          '01_Architecture_and_Interfaces/ICD_FPGA_HOST_OPTICS_SPEC_REV_D1.md',
          '01_Architecture_and_Interfaces/KIMI_ENGINEERING_HANDOFF_REV_D1.md',
          '05_Verification_Scripts/verify_rev_d1_electrical.py','05_Verification_Scripts/check_rev_d1_reproducibility.py']
        for rel in obsolete:
            (stage/rel).unlink(missing_ok=True)
        (stage/'.gitattributes').write_bytes(b'# Preserve source bytes; unified-diff empty context lines require a space.\n* -text\n*.patch -whitespace\n')
        # Keep original FPGA baseline files byte-exact. Authored changes use LF everywhere.
        inherited={'ice40up5k_uwg30_rev_c.pcf','ice40_spram_ebr_sim.v','tb_evt1_ar_display_fpga_bridge_rev_c.v'}
        for f in stage.rglob('*'):
            if f.is_file() and f.name not in inherited and f.suffix in ['.py','.json','.md','.csv','.v','.txt','.yml']:
                f.write_bytes(f.read_bytes().replace(b'\r\n',b'\n').rstrip()+b'\n')
        # Reviewable delta of corresponding electrical/RTL/interfaces. Avoid
        # recursive comparison of the generated patch or verification outputs.
        pairs=[('02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv','02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv'),
          ('01_Architecture_and_Interfaces/ICD_FPGA_HOST_OPTICS_SPEC_REV_D1.md','01_Architecture_and_Interfaces/ICD_FPGA_HOST_OPTICS_SPEC_REV_D1_1.md')]
        for rel in ['03_FPGA_RTL/evt1_ar_display_fpga_bridge_rev_c.v','03_FPGA_RTL/Makefile','03_FPGA_RTL/tb_evt1_ar_display_fpga_bridge_rev_c.v',
          '02_BOM_PINMAP_ICD_Blocked/BOM_V1_0_FROZEN.csv','02_BOM_PINMAP_ICD_Blocked/PINMAP_V1_0_FROZEN.csv',
          '02_BOM_PINMAP_ICD_Blocked/ICD_INTERFACE_CONTROL_TABLE.csv','02_BOM_PINMAP_ICD_Blocked/BLOCKED_ITEMS_CHECKLIST.csv',
          '01_Architecture_and_Interfaces/SYSTEM_BUDGETS_V1_0.json']:
            pairs.append((rel,rel))
        diff=[]
        for old,new in pairs:
            diff.extend(difflib.unified_diff((base/old).read_text(encoding='utf8').splitlines(True),
              (stage/new).read_text(encoding='utf8').splitlines(True),fromfile='a/'+old,tofile='b/'+new))
        (stage/HERE.name/'DIFF_REV_D1_TO_D1_1.patch').write_bytes(''.join(diff).replace('\r\n','\n').encode('utf8'))
        (stage/'SHA256SUMS.txt').unlink(missing_ok=True)
        source=hashes(stage)
        (stage/'SHA256SUMS.txt').write_bytes(''.join(f'{sha}  {rel}\n' for rel,sha in source.items()).encode('utf8'))
        out.mkdir(parents=True,exist_ok=True)
        for f in stage.rglob('*'):
            if f.is_file():
                target=out/f.relative_to(stage);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        # Remove only superseded artifacts inside explicitly selected D1.1 output.
        for rel in obsolete:
            (out/rel).unlink(missing_ok=True)
        old=out/'00_Rev_D1_Change_Record'
        if old.exists():shutil.rmtree(old)
        assert before==hashes(base),'Rev D1 baseline changed'
        print(f'Generated Rev D1.1: {len(net)} terminals / {len(bom)} BOM owners; {len(source)} source files; {len(before)} baseline files unchanged')
    return 0

if __name__=='__main__':raise SystemExit(main())
