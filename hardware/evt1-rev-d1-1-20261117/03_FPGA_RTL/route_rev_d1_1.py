#!/usr/bin/env python3
"""Bounded reproducible routing search; every accepted final clock and STA >=48MHz.

No RTL, PCF, constraints or clock rate is changed. Failed candidates and the
selected seed are retained. Early placement estimates are not routed timing.
"""
import argparse,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;TOP='evt1_ar_display_fpga_bridge_rev_c'

def clocks(text):
    # nextpnr prints placement estimates and final routed reports. The last
    # occurrence for each clock is its final result, never the best occurrence.
    return {name:float(value) for name,value in re.findall(r"Max frequency for clock\s+'([^']+)'[^:]*:\s*([0-9.]+) MHz",text)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',type=int,nargs='+',default=list(range(8)))
    p.add_argument('--frequency',type=float,default=48.0)
    a=p.parse_args()
    if a.frequency<48:raise SystemExit('The inherited48MHz timing target cannot be lowered')
    if not a.seeds or len(a.seeds)>16:raise SystemExit('Bounded routing seeds required')
    results=[];selected=None
    for seed in a.seeds:
        stem=f'route_seed_{seed}';log=ROOT/(stem+'.log');asc=ROOT/(stem+'.asc');sta=ROOT/(stem+'_sta.rpt')
        args=['nextpnr-ice40','--up5k','--package','uwg30','--pcf','ice40up5k_uwg30_rev_c.pcf',
          '--json',TOP+'.json','--asc',asc.name,'--freq',str(a.frequency),'--seed',str(seed),'-l',log.name]
        process=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=180)
        text=log.read_text(encoding='utf8') if log.exists() else process.stdout+process.stderr
        if not log.exists():log.write_text(text,encoding='utf8')
        frequencies=clocks(text)
        record={'seed':seed,'pnr_command':args,'pnr_exit':process.returncode,'final_routed_clocks_mhz':frequencies,
          'status':'FAIL_PNR_OR_FINAL_TIMING'}
        if process.returncode==0 and frequencies and min(frequencies.values())>=a.frequency and asc.is_file():
            args2=['icetime','-d','up5k','-P','uwg30','-p','ice40up5k_uwg30_rev_c.pcf','-c',str(a.frequency),'-t','-m','-r',sta.name,asc.name]
            timing=subprocess.run(args2,cwd=ROOT,capture_output=True,text=True,timeout=120)
            (ROOT/(stem+'_icetime.log')).write_text(timing.stdout+timing.stderr,encoding='utf8')
            values=[float(v) for v in re.findall(r'Total path delay:.*?([0-9.]+) MHz',sta.read_text(encoding='utf8') if sta.exists() else '')]
            record.update(icetime_command=args2,icetime_exit=timing.returncode,icetime_mhz=values,status='FAIL_ICETIME')
            if timing.returncode==0 and values and min(values)>=a.frequency:
                record['status']='PASS_ROUTED_AND_STA';selected=seed
                shutil.copy2(log,ROOT/'nextpnr_uwg30.log');shutil.copy2(asc,ROOT/(TOP+'.asc'));shutil.copy2(sta,ROOT/(TOP+'_sta.rpt'))
        results.append(record)
        print(json.dumps(record))
        if selected is not None:break
    report={'policy':'first seed in fixed ordered list passing final routed clocks AND independent icetime; no clock/PCF/RTL relaxation',
      'ordered_seed_candidates':a.seeds,'required_mhz':a.frequency,'selected_seed':selected,'attempts':results,
      'physical_board_status':'BLOCKED_NOT_FOR_FAB'}
    (ROOT/'route_search_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    if selected is None:raise SystemExit('FAIL: no candidate meets both48MHz gates')
    print(f'ROUTING_SEARCH: PASS seed={selected} (final routed clocks and icetime >= {a.frequency}MHz)')
    return 0

if __name__=='__main__':raise SystemExit(main())
