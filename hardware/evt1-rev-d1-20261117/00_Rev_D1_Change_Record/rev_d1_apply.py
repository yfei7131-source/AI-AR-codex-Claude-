#!/usr/bin/env python3
"""Recover Claude's interrupted Rev D1 migration transactionally from PR #20.

python rev_d1_apply.py [--baseline REV_D_ROOT] [--output REV_D1_ROOT]
All processing happens in a temporary tree. The immutable Rev D manifest is
checked before processing. Reruns always start from Rev D, never from D1 BOMs.
"""
import argparse, csv, hashlib, importlib.util, json, runpy, shutil, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

def csvread(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def csvwrite(p, rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n',extrasaction='raise')
        w.writeheader();w.writerows(rows)

def manifest(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name!='SHA256SUMS.txt'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,default=HERE.parent.parent/'evt1-rev-d-claude-20261117')
    p.add_argument('--output',type=Path,default=HERE.parent)
    a=p.parse_args(); baseline=a.baseline.resolve();output=a.output.resolve()
    if baseline==output or baseline in output.parents or output in baseline.parents:
        raise SystemExit('Baseline/output must be separate sibling trees')
    checked=0
    for line in (baseline/'SHA256SUMS.txt').read_text().splitlines():
        sha,rel=line.split(maxsplit=1);rel=rel.strip().lstrip('*').removeprefix('./')
        if hashlib.sha256((baseline/rel).read_bytes()).hexdigest()!=sha:
            raise SystemExit(f'Baseline hash mismatch: {rel}')
        checked+=1
    print(f'Rev D source manifest: {checked}/{checked} OK')
    with tempfile.TemporaryDirectory(prefix='evt1-d1-') as tmp:
        stage=Path(tmp)/'package';shutil.copytree(baseline,stage)
        # Recovered scripts share a deliberate namespace; never import _part2 alone.
        ns=runpy.run_path(str(HERE/'_part1.py'),init_globals={'ROOT':stage})
        runpy.run_path(str(HERE/'_part2.py'),init_globals=ns)
        tables=stage/'02_BOM_PINMAP_ICD_Blocked'
        net=csvread(tables/'NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv')
        bom=csvread(tables/'BOM_V1_0_FROZEN.csv')
        for name,fn in [('power_corrections','apply_power_corrections'),
                        ('soc_corrections','apply_soc_corrections'),
                        ('audio_translator_corrections','apply_audio_translator_corrections'),
                        ('privacy_corrections','apply_privacy_corrections')]:
            spec=importlib.util.spec_from_file_location(name,HERE/f'{name}.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            result=getattr(mod,fn)(net,bom)
            if result is not None: net,bom=result
        spec=importlib.util.spec_from_file_location('finalize',HERE/'_finalize.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.finalize(stage,baseline,net,bom)
        csvwrite(tables/'NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv',net)
        csvwrite(tables/'BOM_V1_0_FROZEN.csv',bom)
        (stage/'05_Verification_Scripts/verify_rev_d_electrical.py').rename(stage/'05_Verification_Scripts/_rev_d_inherited_checks.py')
        # Keep all authored helpers, source ledgers and validation programs in output.
        shutil.copytree(HERE,stage/HERE.name,dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
        scripts=HERE.parent/'05_Verification_Scripts'
        for f in scripts.glob('*rev_d1*'):
            if f.is_file():shutil.copy2(f,stage/'05_Verification_Scripts'/f.name)
        for folder in ['00_Rev_D_Change_Record','99_RevC_Baseline']:
            shutil.rmtree(stage/folder)
        obsolete=['SHA256SUMS.txt','02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D.csv',
                  '05_Verification_Scripts/verify_rev_d_electrical.py',
                  '02_BOM_PINMAP_ICD_Blocked/CONNECTOR_PINOUT_REV_D.csv',
                  '02_BOM_PINMAP_ICD_Blocked/TRANSLATOR_BANKS_REV_D.json',
                  '01_Architecture_and_Interfaces/ICD_FPGA_HOST_OPTICS_SPEC_REV_D.md',
                  '01_Architecture_and_Interfaces/KIMI_ENGINEERING_HANDOFF_V1_1_REV_D.md',
                  '01_Architecture_and_Interfaces/CHANGELOG_EVT1_REV_C.md',
                  '04_Verification_Evidence/rev_d_verification_log.json',
                  '04_Verification_Evidence/rev_d_verification_report.txt']
        for f in obsolete:(stage/f).unlink(missing_ok=True)
        for f in stage.rglob('__pycache__'):shutil.rmtree(f)
        # Path.write_text uses CRLF on Windows. Canonicalize authored D1 text so
        # a Linux CI rebuild matches Windows byte-for-byte. Preserve inherited
        # FPGA/model/check modules and comparison data exactly as delivered.
        preserved={'01_Architecture_and_Interfaces/SOC_ARCHITECTURE_COMPARISON.csv',
          '05_Verification_Scripts/_rev_d_inherited_checks.py',
          '05_Verification_Scripts/rev_d_optctrl_protocol_model.py','.gitattributes'}
        for f in stage.rglob('*'):
            if f.is_file():
                rel=f.relative_to(stage).as_posix()
                if not rel.startswith('03_FPGA_RTL/') and rel not in preserved:
                    f.write_bytes(f.read_bytes().replace(b'\r\n',b'\n'))
        hashes=manifest(stage)
        (stage/'SHA256SUMS.txt').write_bytes(''.join(f'{sha}  {rel}\n' for rel,sha in hashes.items()).encode('utf8'))
        output.mkdir(parents=True,exist_ok=True)
        for f in stage.rglob('*'):
            if f.is_file():
                dest=output/f.relative_to(stage);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        # Remove obsolete files only within the explicitly selected D1 directory.
        for rel in obsolete:
            if rel!='SHA256SUMS.txt':(output/rel).unlink(missing_ok=True)
        for rel in ['00_Rev_D_Change_Record','99_RevC_Baseline']:
            old=output/rel
            if old.exists():shutil.rmtree(old)
        print(f'Rev D1 generated: {len(net)} netlist rows, {len(bom)} BOM rows; {len(hashes)} files')
        print(output)
    return 0

if __name__=='__main__':raise SystemExit(main())
