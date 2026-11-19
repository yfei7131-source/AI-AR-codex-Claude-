#!/usr/bin/env python3
"""Run real Icarus against pinned PR25 and the repaired host control decoder.

Needs git history containing PR25 (Actions checkout fetch-depth:0), or an
explicit --baseline-rtl export. No duplicate baseline RTL is checked in.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE_REF = '97ee1f6733416099f842dca00389ab50f3568c96'
RTL_PATH = 'hardware/evt1-rev-d1-1-20261117/03_FPGA_RTL/evt1_ar_display_fpga_bridge_rev_c.v'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', default=BASELINE_REF)
    parser.add_argument('--baseline-rtl', type=Path)
    args = parser.parse_args()
    report = {'scope': 'Native user-mode serial decoder/FIFO tests; NOT FOR FAB',
              'baseline_ref': args.baseline_ref, 'results': [],
              'physical_pad_CDC_optical_qualification': 'BLOCKED'}
    missing = [tool for tool in ['iverilog', 'vvp'] if not shutil.which(tool)]
    if missing:
        report.update(result='BLOCKED', reason='Native tools absent: '+', '.join(missing))
        (HERE/'host_framing_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
        print(report['reason'])
        return 2
    if args.baseline_rtl:
        baseline = args.baseline_rtl.read_bytes()
        report['baseline_source'] = str(args.baseline_rtl.resolve())
    else:
        git = subprocess.run(['git', 'show', f'{args.baseline_ref}:{RTL_PATH}'], cwd=HERE,
                             capture_output=True)
        if git.returncode:
            report.update(result='BLOCKED', reason='Pinned PR25 source unavailable; fetch history or pass --baseline-rtl')
            (HERE/'host_framing_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
            print(report['reason'])
            print(git.stderr.decode('utf8', errors='replace'))
            return 2
        baseline = git.stdout
        report['baseline_source'] = f'git:{args.baseline_ref}:{RTL_PATH}'
    try:
        with tempfile.TemporaryDirectory(prefix='evt1-host-framing-') as directory:
            prior = Path(directory)/'pr25_baseline.v'
            prior.write_bytes(baseline)
            for name, source, defines, marker in [
                ('host_framing_baseline_witness', prior, ['-DBASELINE_EXPECT_RESERVED_BUG'],
                 'BASELINE_PR25_RESERVED_CTRL_BUG: PASS'),
                ('host_framing_fixed', HERE/'evt1_ar_display_fpga_bridge_rev_c.v', [],
                 'EVT1_HOST_FRAMING_RESULT: PASS'),
            ]:
                output = Path(directory)/(name+'.vvp')
                command = ['iverilog', '-g2005', '-Wall', '-s', 'tb_evt1_host_framing',
                           *defines, '-o', str(output), str(source),
                           str(HERE/'ice40_spram_ebr_sim.v'), str(HERE/'tb_evt1_host_framing.v')]
                compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
                (HERE/(name+'_compile.log')).write_text(compiled.stdout+compiled.stderr, encoding='utf8')
                if compiled.returncode:
                    raise RuntimeError(f'{name} compile failed:\n'+compiled.stdout+compiled.stderr)
                executed = subprocess.run(['vvp', str(output)], capture_output=True, text=True, timeout=180)
                (HERE/(name+'.log')).write_text(executed.stdout+executed.stderr, encoding='utf8')
                print(executed.stdout, end='')
                if executed.returncode or marker not in executed.stdout:
                    raise RuntimeError(f'{name} failed marker/exit check:\n'+executed.stderr)
                report['results'].append({'case': name, 'result': 'PASS', 'marker': marker,
                    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'compile_command': command, 'run_command': ['vvp', str(output)]})
        report['result'] = 'PASS'
        print('HOST_FRAMING_NATIVE_SUITE: PASS (pinned defect witnessed; repaired decoder and CS recovery verified)')
        return 0
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        report.update(result='FAIL', reason=str(error))
        print(str(error))
        return 1
    finally:
        (HERE/'host_framing_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    raise SystemExit(main())
