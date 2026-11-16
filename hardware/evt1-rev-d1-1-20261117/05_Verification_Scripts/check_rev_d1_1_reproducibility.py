#!/usr/bin/env python3
"""Two clean Rev D1.1 generations plus rerun; immutable Rev D1 and active source comparison."""
import hashlib,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def main():
    base=ROOT.parent/'evt1-rev-d1-20261117';before=hashes(base)
    driver=ROOT/'00_Rev_D1_1_Change_Record/rev_d1_1_apply.py'
    with tempfile.TemporaryDirectory(prefix='d11-repeat-') as td:
        a,b=Path(td)/'a',Path(td)/'b'
        for p in [a,b]:subprocess.run([sys.executable,str(driver),'--baseline',str(base),'--output',str(p)],check=True)
        ha,hb=hashes(a),hashes(b);assert ha==hb,'Two clean outputs differ'
        subprocess.run([sys.executable,str(driver),'--baseline',str(base),'--output',str(a)],check=True)
        assert hashes(a)==ha,'Repeat application differs'
        assert hashes(base)==before,'Rev D1 baseline changed'
        drift=[p for p,sha in ha.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha]
        assert not drift,f'Active generated files differ: {drift}'
        print(f'PASS: {len(ha)}files byte-identical across2clean builds+rerun; active source matches; {len(before)}Rev D1 files unchanged')
    return 0
if __name__=='__main__':raise SystemExit(main())
