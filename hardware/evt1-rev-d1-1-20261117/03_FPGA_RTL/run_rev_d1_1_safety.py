#!/usr/bin/env python3
"""Real Icarus baseline-witness and repaired-user-RTL tests. No analog/hard-CDONE claim."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-rtl', type=Path,
        default=ROOT.parent.parent / 'evt1-rev-d1-20261117/03_FPGA_RTL/evt1_ar_display_fpga_bridge_rev_c.v')
    args = parser.parse_args()
    needed = ['iverilog', 'vvp']
    missing = [x for x in needed if not shutil.which(x)]
    if missing:
        print('BLOCKED_NATIVE_ICARUS: missing ' + ', '.join(missing))
        return 2
    baseline = args.baseline_rtl.resolve()
    if not baseline.is_file():
        raise SystemExit('Missing immutable Rev D1 baseline RTL: ' + str(baseline))
    results = []
    for case, source, defines, marker in [
        ('baseline_failure_witness', baseline, ['-DBASELINE_EXPECT_BUG'], 'BASELINE_D1_FAILURE_WITNESS: PASS'),
        ('rev_d1_1_user_rtl_safety', ROOT / 'evt1_ar_display_fpga_bridge_rev_c.v', [], 'REV_D1_1_SAFETY_TB_RESULT: PASS'),
    ]:
        executable = ROOT / (case + '.vvp')
        compile_cmd = ['iverilog', '-g2005', '-Wall', '-s', 'tb_evt1_rev_d1_1_safety',
            *defines, '-o', str(executable), str(source), str(ROOT/'ice40_spram_ebr_sim.v'),
            str(ROOT/'tb_evt1_rev_d1_1_safety.v')]
        compiled = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=120)
        (ROOT/(case+'_compile.log')).write_text(compiled.stdout+compiled.stderr, encoding='utf8')
        if compiled.returncode:
            print(compiled.stdout + compiled.stderr)
            raise SystemExit(compiled.returncode)
        run_cmd = ['vvp', str(executable)]
        run = subprocess.run(run_cmd, capture_output=True, text=True, timeout=300)
        (ROOT/(case+'.log')).write_text(run.stdout+run.stderr, encoding='utf8')
        print(run.stdout, end='')
        if run.returncode or marker not in run.stdout:
            print(run.stderr)
            raise SystemExit(run.returncode or 1)
        results.append(dict(case=case, status='PASS', marker=marker,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            compile_command=compile_cmd, run_command=run_cmd))
    report = dict(scope='Native Icarus user-mode RTL tests only. Baseline witness PASS proves a fault, not safety.',
        hard_configuration_reset_supply_states='BLOCKED_IN_USER_RTL_MODEL; separate board/supervisor model and physical qualification required',
        results=results, result='PASS')
    (ROOT/'rev_d1_1_rtl_safety_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print('REV_D1_1_NATIVE_SAFETY_SUITE: PASS (baseline fault reproduced; repaired user-mode RTL assertions passed)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
