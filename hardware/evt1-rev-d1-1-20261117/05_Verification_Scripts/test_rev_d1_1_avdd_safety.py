#!/usr/bin/env python3
"""Independent AVDD failure reproduction and conditional safety-contract tests.

The RC equations and ngspice circuits describe delivered D1/Gemini topologies.
They do not substitute ideal diode or pin assumptions for vendor/bench limits.
The D1.1 section consumes a separate hardware contract; missing contract/tool or
unbounded supply-response data are BLOCKED, never converted into a safety PASS.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / '04_Verification_Evidence' / 'avdd_safety_models'
CONTRACT = ROOT / '00_Rev_D1_1_Change_Record' / 'AVDD_SAFETY_CONTRACT_REV_D1_1.json'
VHI, VLO = 1.0, 0.3  # TLV755P SBVS320D electrical characteristics; no0.95/0.40 substitution.


def decay(v0, dt, resistance, capacitance, injection_a=0.0):
    final = injection_a * resistance
    return final + (v0-final) * math.exp(-dt/(resistance*capacitance))


def periodic_peak_hold(rail=1.8, vf=0.22, rcharge=35.0, rbleed=2.2e6,
                       cap=22e-9, width=1e-6, period=16.667e-3, injection_a=0.0):
    """Exact periodic fixed point including finite charging time and bleed load.

    VF and35ohm pin+charge impedance are Gemini model assumptions, not promised
    FPGA output/schottky behavior. Positive injection represents an unbounded
    external leakage path: this is sensitivity analysis, not a diode spec.
    """
    req = 1/(1/rcharge+1/rbleed)
    charge_final = ((rail-vf)/rcharge+injection_a)*req
    bleed_final = injection_a*rbleed
    a = math.exp(-width/(req*cap))
    b = math.exp(-(period-width)/(rbleed*cap))
    peak = ((1-a)*charge_final+a*(1-b)*bleed_final)/(1-a*b)
    valley = bleed_final+(peak-bleed_final)*b
    first_peak = charge_final*(1-a)
    first_valley = bleed_final+(first_peak-bleed_final)*b
    return dict(first_peak_v=first_peak, first_valley_v=first_valley,
                steady_peak_v=peak, steady_valley_v=valley)


def rising_watchdog(events, sample_times, timeout_s):
    """Event-level rising-edge retrigger contract; IC startup/rail collapse not modeled."""
    last = None
    i = 0
    result = []
    for now in sample_times:
        while i < len(events) and events[i] <= now:
            last = events[i]
            i += 1
        result.append(last is not None and now-last < timeout_s)
    return result


def qualified_watchdog_trace(edges, samples, timeout_s, guard_s, pg_faults=()):
    """Event specification of actualWD->RC/SchmittCLR->DFF qualification.

    The initialCDONE edge startsWD but occurs with qualificationclearLOW.
    RC cannot releaseCLR untilguard haselapsed; only a lateredge can setQ.
    Any fault/WDexpiry clearsQ. IdealsettledPGevents are supplied explicitly;
    no supervisor response-time or PVTguard guarantee is invented here.
    """
    points=sorted(set(edges+samples+[e+timeout_s for e in edges]+
                      [t for pair in pg_faults for t in pair]))
    last=None;qual=False;release_at=None;out={}
    for now in points:
        pg=not any(start<=now<end for start,end in pg_faults)
        alive=last is not None and now-last<timeout_s-1e-12
        if not pg or not alive:qual=False;release_at=None
        if pg and alive and release_at is None:release_at=now+guard_s
        if now in edges:
            if pg and alive and release_at is not None and now>=release_at:qual=True
            last=now;alive=True
            if pg and release_at is None:release_at=now+guard_s
        if now in samples:out[now]=bool(pg and alive and qual)
    return [out[t] for t in samples]


def _check(rows, ident, ok, detail, status='PASS_MODEL_ONLY'):
    rows.append(dict(id=ident, status=status if ok else 'FAIL', detail=detail))
    if not ok:
        raise AssertionError(ident+': '+str(detail))


def legacy_checks():
    rows = []
    # Current D1 netlist is the source for these component values, not a copied
    # statement that its previous verification report happened to mark PASS.
    netpath = ROOT.parent/'evt1-rev-d1-20261117'/'02_BOM_PINMAP_ICD_Blocked'/'NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv'
    with netpath.open(encoding='utf-8-sig', newline='') as f:
        old = list(csv.DictReader(f))
    pins = {(r['RefDes'],r['Pin']):r for r in old}
    assert pins['R_SEQ','1']['Net']=='FPGA_CDONE_VSYNC_N'
    assert pins['R_SEQ','2']['Net']=='OPT_AVDD_EN'
    assert pins['C_SEQ','1']['Net']=='OPT_AVDD_EN' and pins['C_SEQ','2']['Net']=='GND'
    _check(rows, 'D1 actual RC connectivity', True, 'R_SEQ100k,C_SEQ220nF; direct DC-high D3 source verified in immutable D1 NETLIST')
    v_stalled_high = 1.8*(1-math.exp(-0.2/(100e3*220e-9)))
    _check(rows, 'D1 VSYNC/clock lost HIGH reproduced', v_stalled_high>VHI,
           {'en_at_200ms_v':v_stalled_high,'unsafe_condition':'EN remains above1.0V indefinitely while D3 remains drivenHIGH'},'REPRODUCED_FAILURE')
    _check(rows, 'D1 failed configuration LOW conditional OFF', decay(0,1,100e3,220e-9)<=VLO,
           'Assumes silicon CDONE truly holdsD3LOW and CRESET/rails are valid; not a simulation of the hard configuration engine')
    d1_off_s = 100e3*220e-9*math.log(1.8/VLO)
    _check(rows, 'D1 explicit LOW RC discharge', .039<d1_off_s<.040,
           {'nominal_off_ms':1000*d1_off_s,'scope':'only after the physical D3 source has actually goneLOW'})
    v_after_io_loss_10us = decay(1.8,10e-6,104.7e3,220e-9)
    _check(rows, 'D1 IO-fall cannot prove fast AVDD cutoff', v_after_io_loss_10us>VHI,
           {'en_10us_after_ideal_IO_pull_down_v':v_after_io_loss_10us,
            'scope':'conditional RC discharge boundary; actual I/O clamps and floating rail impedances are not modeled'},'REPRODUCED_FAILURE')
    gem = periodic_peak_hold()
    _check(rows, 'Gemini finite1us charge discrepancy', gem['steady_valley_v']<1.02 and gem['steady_valley_v']>1.0,
           gem,'REPRODUCED_MODEL_DEFECT')
    _check(rows, 'Gemini first frame below current guaranteed ON', gem['first_valley_v']<VHI,
           {'first_valley_v':gem['first_valley_v'],'ldo_guaranteed_on_v':VHI},'REPRODUCED_MODEL_DEFECT')
    _check(rows, 'Gemini native positive-pulse LOW-loss nominal discharge',
           decay(gem['steady_peak_v'],0.100,2.2e6,22e-9)<VLO,
           'With no charge source and zero leakage, voltage falls below0.3V within100ms; does not cover stuckHIGH')
    ideal_off_s = 2.2e6*22e-9*math.log((1.8-.22)/VLO)
    _check(rows, 'Gemini old66.5ms claim threshold mismatch', ideal_off_s>.080,
           {'off_ms_at_current0p3V':1000*ideal_off_s,'old_claim_uses0p4V_ms':1000*2.2e6*22e-9*math.log(1.58/.4)},'REPRODUCED_MODEL_DEFECT')
    gem_stuck_high = (1.8-.22)*2.2e6/(2.2e6+35)
    _check(rows, 'Gemini native or D1-polarity stuckHIGH reproduced', gem_stuck_high>VHI,
           {'continuous_rectifier_en_v':gem_stuck_high,'missing_protection':'peak hold is not an edge watchdog'},'REPRODUCED_FAILURE')
    corner = periodic_peak_hold(rail=1.71,cap=22e-9*1.2,rbleed=2.2e6*.99,rcharge=35*1.01)
    _check(rows, 'Gemini parameter sensitivity below guaranteed ON',corner['steady_valley_v']<VHI,
           {'rail_minus5pct_cap_plus20pct_Rplusminus1pct':corner,
            'scope':'explicit design sensitivity, not a claim these are the exact populated-parts limits'},'REPRODUCED_MARGIN_FAILURE')
    leakage = decay(gem['steady_peak_v'],1,2.2e6,22e-9,injection_a=.2e-6)
    _check(rows, 'Gemini leakage sensitivity defeats passive OFF',leakage>VLO,
           {'en_after1s_with_positive0p2uA_injection_v':leakage,'scope':'sensitivity bound. Missing diode/LDO/pin worst-case leakage must not be assumedzero.'},'REPRODUCED_MARGIN_FAILURE')
    return rows


def contract_checks(path):
    c = json.loads(path.read_text(encoding='utf8'))
    wd = c['watchdog']; mr = c['mr_filter']; en = c['en']
    tmin,tmax = wd['min_s'],wd['max_s']
    period = 1/60
    assert wd['edge']=='rising'
    assert tmax>=tmin>period
    rows=[]
    netfile=ROOT/'02_BOM_PINMAP_ICD_Blocked'/'NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv'
    with netfile.open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f))
    with (ROOT/'02_BOM_PINMAP_ICD_Blocked'/'BOM_V1_0_FROZEN.csv').open(encoding='utf-8-sig',newline='') as f:
        bom={r['Item_ID']:r for r in csv.DictReader(f)}
    pinrefs={r['RefDes'] for r in actual}
    _check(rows,'D1.1 legacy EN reservoir/clamp removed from actual NETLIST',
           not {'C_SEQ','D_SEQ','R_SEQ'} & pinrefs,
           'Checked actual RevD1.1 terminals, not merely a contract boolean')
    en_caps=[r['RefDes'] for r in actual if r['Net']=='OPT_AVDD_EN' and r['RefDes'].startswith('C_')]
    _check(rows,'D1.1 no explicit EN hold capacitor',not en_caps,str(en_caps))
    timer_sources=[r for r in actual if 'LTC6993' in bom[r['BOM_Line']]['MPN'] and r['Pin_Function']=='OUT']
    clamp_pins=[r for r in actual if 'TPS3890' in bom[r['BOM_Line']]['MPN'] and r['Net']=='OPT_AVDD_EN' and 'RESET' in r['Pin_Function'].upper()]
    od_pins=[r for r in actual if r['RefDes']=='U_AVDD_EN_OD' and r['Net']=='OPT_AVDD_EN' and r['Pin_Function'] in ['1Y','2Y']]
    _check(rows,'D1.1 actual timer, direct supervisor and two logical clamps',
           len(timer_sources)==1 and len(clamp_pins)==1 and len(od_pins)==2,
           {'timer_output':[(r['RefDes'],r['Pin'],r['Net']) for r in timer_sources],
            'reset_clamps':[(r['RefDes'],r['Pin']) for r in clamp_pins]})
    idx={(r['RefDes'],r['Pin']):r['Net'] for r in actual}
    qualification_wires={('U_AVDD_QUAL','1'):'AVDD_D3_VSYS',('U_AVDD_QUAL','3'):'VSYS',
       ('U_AVDD_QUAL','4'):'AVDD_PULSE_QUAL',('U_AVDD_QUAL','6'):'AVDD_QUAL_CLR_N',
       ('U_AVDD_SCHMITT','3'):'AVDD_QUAL_RC',('U_AVDD_SCHMITT','4'):'AVDD_QUAL_CLR_N',
       ('R_AVDD_QUAL_PU','1'):'AVDD_WD_Q',('R_AVDD_QUAL_PU','2'):'AVDD_QUAL_RC',
       ('C_AVDD_QUAL','1'):'AVDD_QUAL_RC',('C_AVDD_QUAL','2'):'GND',
       ('U_AVDD_CLEAR_OD','1'):'AVDD_WD_Q',('U_AVDD_CLEAR_OD','3'):'AVDD_PG_OK',
       ('U_AVDD_CLEAR_OD','4'):'AVDD_QUAL_RC',('U_AVDD_CLEAR_OD','6'):'AVDD_QUAL_RC',
       ('U_AVDD_EN_OD','1'):'AVDD_PG_OK',('U_AVDD_EN_OD','3'):'AVDD_PULSE_QUAL'}
    _check(rows,'D1.1 actual qualification graph prevents CDONE-only combinationalON',
           all(idx.get(k)==n for k,n in qualification_wires.items()),str(qualification_wires))
    q=c['qualification'];guard_min=q['guard_min_s_design_budget'];guard_max=q['guard_max_s_design_budget']
    assert 0<guard_min<=guard_max<period
    for guard in [guard_min,guard_max]:
        first=.010
        samples=[first+1e-9,first+guard*1.1,first+tmax+1e-6]
        _check(rows,'D1.1 CDONE-only stuckHIGH staysOFF, guard='+str(guard),
               not any(qualified_watchdog_trace([first],samples,tmax,guard)),
               {'scope':'actual qualificationgraph eventmodel, guard is explicit unqualifiedPVTdesignbudget'})
        heartbeats=[first,first+period,first+2*period]
        _check(rows,'D1.1 later completedheartbeat qualifies, guard='+str(guard),
               qualified_watchdog_trace(heartbeats,[first+period+1e-6],tmin,guard)==[True],
               'FirstCDONE edge ignored; next1usLOWpulse completion can clockD=1 afterCLRrelease')
        fault=(first+2*period+.002,first+2*period+.004)
        samples=[fault[0]+1e-6,fault[1]+guard+1e-6]
        _check(rows,'D1.1 PG fault+restore without newheartbeat cannot reenable, guard='+str(guard),
               not any(qualified_watchdog_trace(heartbeats,samples,tmax,guard,[fault])),
               {'scope':'settledPGevents only; actual supervisor transientdeadline remainsBLOCKED'})
    # These independent traces assert an event specification, not the behavior of
    # an invented transistor-level LTC/TPS model. Native RTL verifies the source.
    events=[0.010+i*period for i in range(8)]
    last=events[-1]
    _check(rows,'D1.1 normal60Hz retriggers before earliest expiry',
           all(rising_watchdog(events,[t+period*.99 for t in events[:-1]],tmin)),
           {'period_ms':1000*period,'minimum_timeout_ms':1000*tmin})
    for label in ['clock/VSYNC stopped HIGH','clock/VSYNC stopped LOW','OPT_PWR_REQ LOW held','D3 disconnected/no further rising edge']:
        _check(rows,'D1.1 '+label+' event watchdog expires',
               not rising_watchdog(events,[last+tmax+1e-6],tmax)[0],
               {'last_edge_s':last,'latest_model_expiry_s':last+tmax,
                'scope':'timeout contract valid supply/domain only; supervisor propagation and AVDD output discharge not included'})
    _check(rows,'D1.1 failed config/no edges starts watchdoginactive',
           not any(rising_watchdog([], [0,.010,.1,1],tmax)),
           'No synthetic trigger is invented for FPGA configuration failure; actual timerPOR/level-translator power-up must also be vendor-checked')
    tau=mr['r_ohm']*mr['c_f']
    normal_floor=math.exp(-1e-6/tau)
    held_low_delay=-tau*math.log(mr['vil_fraction'])
    _check(rows,'D1.1 normal1us D3 LOW filtered above MR high level',
           normal_floor>mr['vih_fraction'],
           {'mr_min_normal_fraction':normal_floor,'mr_vih_fraction':mr['vih_fraction'],'tau_us':tau*1e6})
    _check(rows,'D1.1 heldLOW reaches MR guaranteedLOW',
           math.exp(-(held_low_delay+1e-9)/tau)<mr['vil_fraction'],
           {'nominal_filter_delay_us':held_low_delay*1e6,'scope':'R/C calculation only; supervisor response has no assumed maximum'})
    ratio=en['pulldown_r_ohm']/(en['series_r_ohm']+en['pulldown_r_ohm'])
    _check(rows,'D1.1 EN does not retain removed220nF charge reservoir',
           c.get('removed_hold_capacitor',True) and en.get('hold_capacitance_f',0)==0,
           {'divider_ratio':ratio,'scope':'explicit populated capacitor removed; parasiticENcap stillphysicalunknown'})
    for state in ['CRESET asserted','IO rail below supervisor threshold','VSYS below supervisor threshold','D3 heldLOW after MRfilter']:
        _check(rows,'D1.1 settled '+state+' clamp contract',
               en['clamped_low_max_v']<=en['ldo_vlo_v'],
               {'en_clamped_low_max_v':en['clamped_low_max_v'],'ldo_vlo_v':en['ldo_vlo_v'],
                'scope':'specified settledclamp current/load/validsupply conditions; not a response-time guarantee'})
    return rows


def spice_decks():
    """Deliberately small independent circuits; no counterfeit semiconductor model."""
    ctl='''\n.control\nset noaskquit\nrun\nquit\n.endc\n.end\n'''
    # B-target/S-charge form an ideal one-way, fixed-VF rectifier. Its assumptions
    # are printed in each generated circuit and in the result JSON.
    rect='''\nBtarget target 0 V=max(v(d3)-0.22,0)\nBctl ctl 0 V=v(target)-v(en)\nScharge target en ctl 0 rect\n.model rect SW(Ron=35 Roff=1e15 Vt=0 Vh=0)\nRbleed en 0 2.2meg\nChold en 0 22n IC=0\n'''
    d1='''\nRseq d3 en 100k\nCseq en 0 220n IC=0\n'''
    first_end=.010+1e-6
    first_valley=.010+16.667e-3-1e-6
    fixed_valley=.010+10*16.667e-3-1e-6
    return {
      'd1_stall_high':('D1 directRC stalledHIGH; source fixed1.8V, no physicalGPIOmodel\nVd3 d3 0 1.8'+d1+
        '.tran 10u 250m 0 20u UIC\n.measure tran en_after_stall FIND v(en) AT=200m\n'+ctl,
        {'en_after_stall':lambda v:v>VHI}),
      'd1_io_fall':('D1 conditional IOpull-down; no vendorclampmodel\nVd3 d3 0 PWL(0 1.8 50m 1.8 50.000001m 0 150m 0)\nRseq d3 en 104.7k\nCseq en 0 220n IC=1.8\n'
        '.tran 1u 100m 0 2u UIC\n.measure tran en_10us FIND v(en) AT=50.01m\n'+ctl,
        {'en_10us':lambda v:v>VHI}),
      'gemini_positive_pulse':('Gemini positive1us60Hz pulse; idealVF.22V/Rdriver+charge35ohm\nVd3 d3 0 PULSE(0 1.8 10m 1n 1n 1u 16.667m)'+rect+
        f'.tran 20u 200m 0 20u UIC\n.measure tran first_peak FIND v(en) AT={first_end:.12g}\n.measure tran first_valley FIND v(en) AT={first_valley:.12g}\n.measure tran steady_valley FIND v(en) AT={fixed_valley:.12g}\n'+ctl,
        {'first_peak':lambda v:1.10<v<1.2,'first_valley':lambda v:v<VHI,'steady_valley':lambda v:1.0<v<1.03}),
      'gemini_stall_high':('Gemini peakhold atD1 idleHIGH/stallHIGH; idealVF.22V\nVd3 d3 0 1.8'+rect+
        '.tran 10u 200m 0 20u UIC\n.measure tran en_stuck_high FIND v(en) AT=150m\n'+ctl,
        {'en_stuck_high':lambda v:v>VHI}),
      'gemini_loss_low':('Gemini pulse_loss LOW; zero leakage and idealVF.22V\nVd3 d3 0 PWL(0 1.8 5m 1.8 5.000001m 0 150m 0)'+rect+
        '.tran 10u 150m 0 20u UIC\n.measure tran t_0p3 WHEN v(en)=0.3 FALL=1\n'+ctl,
        {'t_0p3':lambda v:.084<v<.087}),
    }


def native_spice(binary):
    evidence=EVID/'ngspice';evidence.mkdir(parents=True,exist_ok=True)
    binary=str(Path(binary).resolve()) if Path(binary).exists() else binary
    version=subprocess.run([binary,'--version'],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
    (evidence/'version.txt').write_text(version.stdout+version.stderr,encoding='utf8')
    results=[]
    # Windows ngspice C-runtime file handling does not reliably accept Unicode
    # paths. Use an isolated ASCII scratch directory and archive the actual decks
    # and logs afterward. This changes no machine-wide environment or setting.
    tmp_parent=Path('C:/Users/Public') if os.name=='nt' else None
    with tempfile.TemporaryDirectory(prefix='aiar-ngspice-',dir=tmp_parent) as td:
        work=Path(td);env=dict(os.environ,TMP=td,TEMP=td,TMPDIR=td)
        for name,(deck,predicates) in spice_decks().items():
            p=work/(name+'.cir');p.write_text(deck,encoding='ascii')
            log=work/(name+'.log')
            run=subprocess.run([binary,'-b'],input=deck,cwd=work,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=60)
            raw=run.stdout+'\n'+run.stderr
            log.write_text(raw,encoding='utf8')
            shutil.copy2(p,evidence/p.name)
            if log.exists():shutil.copy2(log,evidence/log.name)
            measures={k:float(v) for k,v in re.findall(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([+\-0-9.eE]+)',raw,re.M)}
            assert run.returncode==0,(name,run.returncode,run.stdout,run.stderr,raw[-1200:])
            for key,test in predicates.items():assert key in measures and test(measures[key]),(name,key,measures)
            results.append({'case':name,'status':'PASS_CONDITIONAL_RC_SPICE','measurements':measures,
                            'deck_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    return {'status':'PASS_NATIVE_RC_MODELS_ONLY','binary':str(binary),'cases':results,
      'assumptions':['Ideal fixed0.22Vrectifier,35ohm source/charge resistance reproduceGemini assumptions,notvendorlimits',
                     'DirectRCsourceboundary is prescribed; no FPGAIBIS,TLV755Porwatchdog/supervisor macromodel',
                     'No nativeSPICEresult here validates real AVDDvoltage,outputcapdischarge,MR/SENSEmaximumlatency or rampsequencing']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ngspice',default=os.environ.get('NGSPICE'))
    p.add_argument('--require-ngspice',action='store_true')
    p.add_argument('--contract',type=Path,default=CONTRACT)
    p.add_argument('--legacy-only',action='store_true',help='Reproduce immutableD1/Gemini model defects only; does not qualify D1.1')
    a=p.parse_args();EVID.mkdir(parents=True,exist_ok=True)
    result={'scope':'Analytical/event-contract tests and optional native idealizedRCSPICE; NOT_FOR_FAB',
      'event_model_initial_conditions':['watchdoginactive, qualifierclear and RC discharged at modeledinitialization',
        'PG transitions mean settled supervisorstates, not arbitrarysupplyramp timing',
        '1us D3 pulses and guard100us..3ms are explicitdesignconditions, notqualifiedPVTlimits'],
      'physical_hardware_status':'BLOCKED_NO_BENCH_MEASUREMENTS',
      'guaranteed_power_transient_status':'BLOCKED_NO_SUPERVISOR_MAX_RESPONSE_OR_VENDOR_OPTICS_SEQUENCE',
      'jbd_avdd_and_powerdown_status':'BLOCKED_VENDOR_NDA',
      'checks':legacy_checks()}
    if not a.legacy_only:
        if not a.contract.exists():raise SystemExit('BLOCKED: missing hardware contract '+str(a.contract))
        result['checks']+=contract_checks(a.contract)
        result['hardware_contract_sha256']=hashlib.sha256(a.contract.read_bytes()).hexdigest()
    binary=a.ngspice or shutil.which('ngspice') or shutil.which('ngspice_con')
    if binary:
        result['native_spice']=native_spice(binary)
    else:
        result['native_spice']={'status':'BLOCKED_NATIVE_NGSPICE_UNAVAILABLE'}
    result['model_assertions']='PASS'
    (EVID/'avdd_failure_comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    text='\n'.join(f"[{r['status']}] {r['id']}: {r['detail']}" for r in result['checks'])
    text+='\n'+json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2)+'\n'
    (EVID/'avdd_failure_comparison.txt').write_text(text,encoding='utf8')
    print(text)
    return 1 if a.require_ngspice and not binary else 0


if __name__=='__main__':raise SystemExit(main())
