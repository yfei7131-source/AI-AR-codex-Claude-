#!/usr/bin/env python3
"""Generate twice from clean Rev D, compare every produced byte, and check source immutability."""
import hashlib,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def main():
    baseline=ROOT.parent/'evt1-rev-d-claude-20261117';before=hashes(baseline)
    with tempfile.TemporaryDirectory(prefix='d1-repeat-') as td:
        a,b=Path(td)/'a',Path(td)/'b'
        for out in [a,b]:subprocess.run([sys.executable,str(ROOT/'00_Rev_D1_Change_Record/rev_d1_apply.py'),'--baseline',str(baseline),'--output',str(out)],check=True)
        ha,hb=hashes(a),hashes(b)
        assert ha==hb,'Independent clean-baseline outputs differ'
        subprocess.run([sys.executable,str(ROOT/'00_Rev_D1_Change_Record/rev_d1_apply.py'),'--baseline',str(baseline),'--output',str(a)],check=True)
        assert hashes(a)==ha,'Repeat application changed output'
        assert hashes(baseline)==before,'Migration changed Rev D source'
        # Compare every generated file to active package, excluding generated evidence.
        drift=[p for p,sha in ha.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha]
        assert not drift,f'Active generated files drifted: {drift}'
        print(f'PASS: {len(ha)} files byte-identical across 2 clean builds + rerun; active output matches; {len(before)} baseline files unchanged')
    return 0
if __name__=='__main__':raise SystemExit(main())
