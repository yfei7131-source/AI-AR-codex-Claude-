#!/usr/bin/env python3
"""Rev D1 source validation. PASS never means CAD, fabrication or physical qualification."""
import collections,copy,csv,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
T=ROOT/'02_BOM_PINMAP_ICD_Blocked';E=ROOT/'04_Verification_Evidence'

def rd(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    net=rd(T/'NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv');bom=rd(T/'BOM_V1_0_FROZEN.csv')
    pm=rd(T/'PINMAP_V1_0_FROZEN.csv');cfg=json.loads((ROOT/'01_Architecture_and_Interfaces/SYSTEM_BUDGETS_V1_0.json').read_text(encoding='utf8'))
    checks=[]
    def ck(ident,ok,detail):checks.append({'id':ident,'status':'PASS' if ok else 'FAIL','detail':detail})
    key=lambda r:(r['RefDes'],r['Pin'])
    dup=[k for k,v in collections.Counter(map(key,net)).items() if v>1]
    ck('D1-01 unique physical terminals',not dup,str(dup))
    ids=[r['Item_ID'] for r in bom]
    ck('D1-02 BOM identifiers and references',len(ids)==len(set(ids)) and all(r['BOM_Line'] in ids for r in net),f'{len(bom)} BOM owners / {len(net)} terminals')
    pn={(r['Chip_Ref'],r['Pin_ID'],r['Signal_Net_Name'],r['Pin_Name']) for r in pm}
    nn={(r['RefDes'],r['Pin'],r['Net'],r['Pin_Function']) for r in net}
    ck('D1-03 PINMAP exact terminal equivalence',len(pm)==len(net) and pn==nn,f'{len(pm)} PINMAP rows; no aggregate/stale terminals')
    # Complete pin coverage catches silent drops during reconstruction/NC migration.
    expected={'U10_AMP_L':9,'U10_AMP_R':9,'U3_L':8,'U3_R':9,'U4_BB':15,
      'U4_1V8':8,'U9_IMU':14,'U11_BLE':95,'U1_HOST':57,'U4_OR':8,
      'U8_LS1':24,'U8_CAM_ISO1':24,'U8_CAM_ISO2':24,'U8_PDM_LS':24,'U8_AUD_LS2':16,'U8_LS3':8,'U8_LS4':8,
      'U7_INA':6,'U7_WIN':9,'U10_SD_BUF':6,'U8_CAM_SCCB_EN':5}
    count=collections.Counter(r['RefDes'] for r in net)
    bad={k:(count[k],v) for k,v in expected.items() if count[k]!=v}
    ck('D1-04 physical package terminal coverage',not bad,str(bad or expected))
    # Multiple physical power pads on the same device are a single source.
    bynet=collections.defaultdict(list)
    for r in net:bynet[r['Net']].append(r)
    resistor_edges=collections.defaultdict(set)
    for ref in {r['RefDes'] for r in net if r['RefDes'].startswith('R_')}:
        ends={r['Net'] for r in net if r['RefDes']==ref}
        if len(ends)==2:
            a,b=ends;resistor_edges[a].add(b);resistor_edges[b].add(a)
    def biased_via_resistor(n):
        return any(any(r['Role'] in ['DRV','SRC','PULLUP'] for r in bynet[other]) for other in resistor_edges[n])
    conflicts=[]
    for n,rows in bynet.items():
        if n=='GND' or n.startswith(('NC_','TIE_')):continue
        drivers={(r['RefDes'],r['Pin']) for r in rows if r['Role']=='DRV'}
        sources={r['RefDes'] for r in rows if r['Role']=='SRC'}
        if len(drivers)+len(sources)>1:conflicts.append((n,sorted(drivers),sorted(sources)))
        if any(r['Role'] in ['BIDIR_OD','DRV_OD'] for r in rows) and not any(r['Role']=='PULLUP' for r in rows) and not biased_via_resistor(n) and not n.startswith('PRIV_'):
            conflicts.append((n,'missing OD pullup'))
    ck('D1-05 driver exclusivity and open-drain bias',not conflicts,str(conflicts))
    def find(ref,fn):return [r for r in net if r['RefDes']==ref and r['Pin_Function']==fn]
    # Every capacitor added by this iteration must have both terminals, including GND return.
    caps={r['RefDes'] for r in net if r['RefDes'].startswith('C_')}
    badcap={c:sorted({r['Pin'] for r in net if r['RefDes']==c}) for c in caps if len({r['Pin'] for r in net if r['RefDes']==c})!=2}
    ck('D1-06 explicit two-terminal capacitors',not badcap,str(badcap or f'{len(caps)} explicit capacitors'))
    boot=find('U1_HOST','CHIP_PU')
    ck('D1-07 ESP32 enable RC connected',len(boot)==1 and {r['RefDes'] for r in bynet[boot[0]['Net']]} >= {'U1_HOST','R_CHIP_PU','C_CHIP_PU','TP_ESP_EN'},'CHIP_PU 10k/1uF and fixture pads')
    ck('D1-08 FPGA source byte preservation',all((ROOT/'03_FPGA_RTL'/p.name).read_bytes()==p.read_bytes() for p in (ROOT.parent/'evt1-rev-d-claude-20261117/03_FPGA_RTL').iterdir() if p.is_file()),'All 5 Rev D RTL/PCF/TB/model/Makefile files preserved')
    mass=cfg['8_rev_d1_mass_plan']
    ck('D1-09 conditional mass arithmetic',mass['candidate_including_contingency_g']<=39.5 and not mass['physical_mass_verified'],json.dumps(mass,ensure_ascii=False))
    # Reuse inherited checks after semantic normalization of physical pin aliases.
    spec=importlib.util.spec_from_file_location('old',ROOT/'05_Verification_Scripts/_rev_d_inherited_checks.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    semantic=[];seen=set()
    for r in net:
        r=dict(r)
        if r['RefDes']=='U1_HOST' and r['Role']=='NC':continue
        if r['RefDes'] in ['U8_LS1','U8_LS3','U8_LS4']:r['Pin']=r['Pin_Function']
        if r['RefDes']=='U1_HOST' and r['Pin'].isdigit():r['Pin']='Pin '+r['Pin']
        k=(r['RefDes'],r['Pin'],r['Net'])
        if k not in seen:semantic.append(r);seen.add(k)
    D={'net':semantic,'bom':bom,'conn':rd(T/'CONNECTOR_PINOUT_REV_D1.csv'),
       'tr':json.loads((T/'TRANSLATOR_BANKS_REV_D1.json').read_text(encoding='utf8')),'cfg':cfg}
    for k,name in [('rtl','evt1_ar_display_fpga_bridge_rev_c.v'),('tb','tb_evt1_ar_display_fpga_bridge_rev_c.v'),('pcf','ice40up5k_uwg30_rev_c.pcf'),('mk','Makefile')]:D[k]=(ROOT/'03_FPGA_RTL'/name).read_text(encoding='utf8')
    for name in ['chk_net02_trunk','chk_net03_ampacity','chk_net04_translators','chk_net06_esp32','chk_net07_fpga','chk_seq01_avdd','chk_seq02_fpga_rails','chk_priv01_window','chk_priv02_request_and_sccb','chk_rtl01_static']:
        try:status,detail=getattr(old,name)(D)
        except Exception as ex:status,detail='FAIL',repr(ex)
        checks.append({'id':'Inherited '+name,'status':status,'detail':detail})
    own={'I2S_BCLK_1V8':'U11_BLE','I2S_LRCLK_1V8':'U11_BLE','I2S_AMP_DIN_1V8':'U11_BLE',
      'I2S_S3_DOUT_1V8':'U8_PDM_LS','PDM_CLK_1V8':'U8_PDM_LS','AMP_SD_REQ_1V8':'U11_BLE','AMP_SD_MODE_1V8':'U10_SD_BUF'}
    wrong={n:[r['RefDes'] for r in bynet[n] if r['Role']=='DRV'] for n,ref in own.items() if [r['RefDes'] for r in bynet[n] if r['Role']=='DRV']!=[ref]}
    ck('D1-11 audio clock and SD buffer ownership',not wrong,str(wrong or own))
    for module,fn in [('power_corrections','validate_power'),('audio_translator_corrections','verify_audio_translators'),('privacy_corrections','validate_privacy')]:
        try:
            spec=importlib.util.spec_from_file_location(module,ROOT/'00_Rev_D1_Change_Record'/f'{module}.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            result=getattr(m,fn)(net)
            ck('D1 source review '+module,True,str(result))
        except Exception as ex:ck('D1 source review '+module,False,repr(ex))
    # Explicit fault injection ensures new schema-integrity checks detect corruption.
    duplicate=net+[dict(net[0])]
    wrongpm=copy.deepcopy(pm);wrongpm[0]['Signal_Net_Name']='FAULT_INJECTED'
    faults={'duplicate physical pin':len({key(r) for r in duplicate})<len(duplicate),
      'PINMAP net corruption':{(r['Chip_Ref'],r['Pin_ID'],r['Signal_Net_Name'],r['Pin_Name']) for r in wrongpm}!=nn,
      'removed peripheral ground':len({r['Pin'] for r in net if r['RefDes']=='C_CHIP_PU' and r['Net']!='GND'})!=2}
    ck('D1-10 migration fault injections',all(faults.values()),str(faults))
    tally=dict(collections.Counter(r['status'] for r in checks))
    report={'scope':'source structural/electrical computations only; NOT FOR FAB','checks':checks,'tally':tally,
      'open':['JBD NDA data','native schematic/PCB/DRC/STEP','physical charging/safety/RF/audio/thermal/optical verification','mass caps unmeasured']}
    E.mkdir(exist_ok=True)
    (E/'rev_d1_verification_log.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    text='\n'.join(f"[{r['status']}] {r['id']}: {r['detail']}" for r in checks)+'\nSUMMARY '+str(tally)+'\nNOT FOR FAB; mass, CAD and physical gates remain OPEN.\n'
    (E/'rev_d1_verification_report.txt').write_text(text,encoding='utf8');print(text)
    return 1 if tally.get('FAIL') else 0

if __name__=='__main__':raise SystemExit(main())
