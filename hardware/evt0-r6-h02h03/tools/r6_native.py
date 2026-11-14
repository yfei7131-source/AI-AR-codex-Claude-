"""r6_native.py — Windows port of run_native_checks.sh (same steps, same outputs).
Runs REAL kicad-cli ERC / DRC(--schematic-parity --refill-zones) on a temp COPY of the project.
usage: python r6_native.py <evt0_core_dir> <out_dir> [--kicad-cli PATH]
Writes: kicad_version.txt, input_sha256.txt, erc.json/.rpt, drc.json, drc_after_refill.rpt,
        evt0_core.refilled.kicad_pcb, netlist.net, exit_codes.txt, summary.json
If kicad-cli is missing: writes NATIVE_STATUS.txt = NOT RUN and exits 2 (never fakes a pass)."""
import sys, os, json, shutil, subprocess, tempfile, hashlib, collections, datetime
from pathlib import Path
a = sys.argv[1:]
cli = None
if '--kicad-cli' in a:
    i = a.index('--kicad-cli'); cli = a[i + 1]; del a[i:i + 2]
prj, out = Path(a[0]).resolve(), Path(a[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
cli = cli or shutil.which('kicad-cli') or r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pro = next(prj.glob('*.kicad_pro')); base = pro.stem
sch, pcb = prj / f'{base}.kicad_sch', prj / f'{base}.kicad_pcb'
(out / 'input_sha256.txt').write_text(f'{sha(sch)}  {sch.name}\n{sha(pcb)}  {pcb.name}\n{sha(pro)}  {pro.name}\n'
                                      f'{sha(prj / (base + ".kicad_dru"))}  {base}.kicad_dru\n')
if not Path(cli).exists():
    (out / 'NATIVE_STATUS.txt').write_text(f'NOT RUN: kicad-cli not available ({datetime.datetime.now().isoformat()})\n'
                                           'ERC: NOT RUN\nDRC: NOT RUN\nzone refill: NOT RUN\n'); sys.exit(2)
def run(name, args):
    r = subprocess.run([cli] + args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (out / f'{name}.log').write_text(r.stdout + '\n--stderr--\n' + r.stderr, encoding='utf-8')
    codes.append(f'{name}_exit={r.returncode}'); return r.returncode
codes = []
(out / 'kicad_version.txt').write_text(subprocess.run([cli, 'version'], capture_output=True, text=True).stdout)
W = Path(tempfile.mkdtemp(prefix='zy_native_')); shutil.copytree(prj, W, dirs_exist_ok=True)
ws, wp = str(W / sch.name), str(W / pcb.name)
run('erc_json', ['sch', 'erc', '--severity-all', '--units', 'mm', '--format', 'json', '-o', str(out / 'erc.json'), ws])
run('erc_rpt', ['sch', 'erc', '--severity-all', '--units', 'mm', '--format', 'report', '-o', str(out / 'erc.rpt'), ws])
run('drc_json', ['pcb', 'drc', '--severity-all', '--schematic-parity', '--refill-zones', '--save-board', '--units', 'mm',
                 '--format', 'json', '-o', str(out / 'drc.json'), wp])
shutil.copy(wp, out / 'evt0_core.refilled.kicad_pcb')
run('drc_rpt', ['pcb', 'drc', '--severity-all', '--schematic-parity', '--units', 'mm', '--format', 'report',
                '-o', str(out / 'drc_after_refill.rpt'), wp])
run('netlist', ['sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out / 'netlist.net'), ws])
same = sha(sch) == (out / 'input_sha256.txt').read_text().split()[0] and sha(pcb) == (out / 'input_sha256.txt').read_text().split()[2]
codes.append(f'inputs_unchanged={same}')
(out / 'exit_codes.txt').write_text('\n'.join(codes) + '\n')
summ = {'kicad': (out / 'kicad_version.txt').read_text().strip(), 'exit_codes': codes}
try:
    e = json.load(open(out / 'erc.json', encoding='utf-8'))
    ev = [v for s in e.get('sheets', []) for v in s.get('violations', [])]
    summ['erc'] = {'total': len(ev), 'by_severity': dict(collections.Counter(v['severity'] for v in ev)),
                   'by_type': dict(collections.Counter(v['type'] for v in ev))}
except Exception as x: summ['erc'] = f'parse error {x}'
try:
    d = json.load(open(out / 'drc.json', encoding='utf-8'))
    vs = d.get('violations', [])
    summ['drc'] = {'violations': len(vs), 'by_severity': dict(collections.Counter(v['severity'] for v in vs)),
                   'by_type': dict(collections.Counter(v['type'] for v in vs)),
                   'unconnected_items': len(d.get('unconnected_items', [])),
                   'unconnected_by_net': dict(collections.Counter(
                       i.get('description', '').split('[')[-1].split(']')[0] if '[' in i.get('description', '') else '?'
                       for u in d.get('unconnected_items', []) for i in u.get('items', [])[:1])),
                   'schematic_parity': len(d.get('schematic_parity', [])),
                   'parity_by_type': dict(collections.Counter(v['type'] for v in d.get('schematic_parity', [])))}
except Exception as x: summ['drc'] = f'parse error {x}'
(out / 'summary.json').write_text(json.dumps(summ, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(summ, indent=1, ensure_ascii=False))
