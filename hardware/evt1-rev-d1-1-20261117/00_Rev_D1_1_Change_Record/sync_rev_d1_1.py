"""Synchronize interface artifacts; unknown JBD/physical parameters remain BLOCKED."""
import csv,json,hashlib
from pathlib import Path

def rd(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def wr(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def js(p,data):p.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf8'))

def sync(stage,base,net,bom):
    tbl=stage/'02_BOM_PINMAP_ICD_Blocked';arch=stage/'01_Architecture_and_Interfaces';e=stage/'04_Verification_Evidence'
    by={r['Item_ID']:r for r in bom};instances=[]
    for ref in sorted({r['RefDes'] for r in net}):
        rows=[r for r in net if r['RefDes']==ref];ids=sorted({r['BOM_Line'] for r in rows})
        b=by[ids[0]]
        instances.append(dict(RefDes=ref,BOM_Line=';'.join(ids),Board=rows[0]['Board'],Terminal_Count=len(rows),
          Owner_MPN=b['MPN'],Terminal_Functions='; '.join(f"{r['Pin']}:{r['Pin_Function']}" for r in rows),Selection_Status=b['Verification_Status']))
    wr(tbl/'BOM_COMPONENT_INSTANCES_REV_D1_1.csv',instances)
    (tbl/'BOM_COMPONENT_INSTANCES_REV_D1.csv').unlink(missing_ok=True)
    cfg=json.loads((arch/'SYSTEM_BUDGETS_V1_0.json').read_text(encoding='utf8'))
    cfg.update(document_version='V1.3-EVT1-RevD1.1-20261117',release_status='NOT_FOR_FAB')
    cfg['10_rev_d1_1_safety_contract']={
      'status':'SOURCE_AND_SIMULATION_ONLY; see BLOCKED physical gates',
      'baseline_pr21_commit':'ff7ccf93fb6ebce289e6a262adcea4e77c8d4928',
      'gemini_comparison_commit':'94b50cf66c149f0b5a613edd8e15f18cd2a0eb15',
      'd3_polarity':'unchanged: idleHIGH /1us LOW per60Hz frame; heldLOW forOPT_PWR_REQ=0',
      'logical_poweroff':'host-domain async assertion,48MHz synchronous release plusgenuineVSYNC rearm; command-onlyOFF/ON cannotrestartD3afterOFF; outputclocks/CS/data idle wheninhibited',
      'heartbeat':'continues withSCAN_EN=0; external hardware must detect stuckHIGH and stuckLOW',
      'reset':'CRESET_B retainsactiveLOW; externaloutputclamps anddefaultpulldown replace Schottky discharge intoGPIO',
      'forbidden_claims':['CDONEaloneprovesuserclock','idealSchottky0.22Vguaranteed','ENoffequalsAVDDdischarged','NDArailofftimeguaranteed'],
      'physical_gates':['JBD AVDDvalue/load/capacitance/powerdown ordering unknown','nativeCAD/ERC/DRC','reset/supply/PG/timercorner bench qualification'],
      'source':'AVDD_HARDWARE_SOURCE_REVIEW.md and test_rev_d1_1_avdd_safety.py'}
    seq=cfg['4_fpga_uwg30_pinout_and_rtl_timing'].get('optical_avdd_sequencer')
    # Retire all RC guarantee text; retain the unrelated iCE40 supply sequence.
    fp=cfg['4_fpga_uwg30_pinout_and_rtl_timing']
    def retire(d):
        if isinstance(d,dict):
            for k in list(d):
                if k=='optical_avdd_sequencer':d[k]={'status':'SUPERSEDED_REV_D1_1','source':'10_rev_d1_1_safety_contract'}
                else:retire(d[k])
        elif isinstance(d,list):
            for x in d:retire(x)
    retire(fp)
    oldids={r['Item_ID'] for r in rd(base/'02_BOM_PINMAP_ICD_Blocked/BOM_V1_0_FROZEN.csv')}
    delta=sum(float(r['Unit_Mass_g'] or 0)*float(r['Qty'] or 0) for r in bom if r['Item_ID'] not in oldids)
    allowance=max(0.03,delta)
    mass=cfg['8_rev_d1_mass_plan']
    cfg['11_rev_d1_1_budget_delta']={'safety_peripheral_estimate_g':round(delta,5),'planning_mass_allowance_g':round(allowance,5),
      'current_estimate_g':round(mass['current_analytical_estimate_g']+allowance,4),
      'conditional_integration_including_reserve_g':round(mass['candidate_including_contingency_g']+allowance,4),
      'physical_mass_verified':False,'power_delta':'OPEN: sum timer/supervisor/translator active currents + pull loads using vendor max; actual power unmeasured',
      'optics':'binocular transparentAR retained; no optics or battery removal'}
    js(arch/'SYSTEM_BUDGETS_V1_0.json',cfg)
    budget=cfg['11_rev_d1_1_budget_delta']
    wr(tbl/'MASS_PLAN_REV_D1_1.csv',[
      {'Case':'Current source estimate with safety allowance','Mass_g':budget['current_estimate_g'],'Status':'UNMEASURED'},
      {'Case':'Conditional integration including0.50g contingency','Mass_g':budget['conditional_integration_including_reserve_g'],'Status':'CONDITIONAL_CAPS_UNMEASURED'}])
    icd=rd(tbl/'ICD_INTERFACE_CONTROL_TABLE.csv')
    for row in icd:
        row['Rev_D1_1_Control']='D3 polarity unchanged; AVDD topology and OPT_CTRL OFF handling superseded by ICD Rev D1.1; no JBD power sequencing qualified'
    wr(tbl/'ICD_INTERFACE_CONTROL_TABLE.csv',icd)
    blocked=rd(tbl/'BLOCKED_ITEMS_CHECKLIST.csv')
    for row in blocked:
        if row['Blocker_ID']=='BLK-RevC-01':
            row.update(Status_Tag='PR21_CI_PASSED; D1_1_CI_REQUIRED',Current_Engineering_State='Baseline CI passed; new safety RTL and power models require current branch CI evidence')
    for ident,description in [
      ('BLK-D11-PHY','No physical reset/configfailure/VSYNC-loss/brownout/poweroff tests; model/RTL results cannot close benchgate.'),
      ('BLK-D11-JBD','AVDD voltage,load,current,capacitance,absolute limits and relative rail-off timing require JBD NDA; EN-low does not prove safe rail discharge.'),
      ('BLK-D11-CORNER','Timer/supervisor/translator/inputslew/outputleakage and rampbounds must be qualified acrossvoltage,temperature,process and actuallayout.'),
      ('BLK-D11-OFF-HOLD','Sub-filter shortOFF doesnotprovephysicalAVDDshutdown/discharge. MinimumOFFhold needs supervisor maximumlatency andJBDrail/loadlimits; edgeactivity alone isnot frame/authenticity safetycertification.'),
      ('BLK-D11-CAD','New hardware interlock components not placed/routed; nativeERC/DRC/DFM andmechanical clearance unavailable.')]:
        blocked.append(dict(Blocker_ID=ident,Status_Tag='BLOCKED',Subsystem='AVDD_SAFETY',Item_Description=description,
          Root_Cause='Required physical/original-vendor data unavailable',Current_Engineering_State='NOT_FOR_FAB',Resolution_Path='See safety source review and KIMI Rev D1.1 update list'))
    wr(tbl/'BLOCKED_ITEMS_CHECKLIST.csv',blocked)
    js(e/'REV_D1_1_PROVENANCE.json',{'baseline_commit':cfg['10_rev_d1_1_safety_contract']['baseline_pr21_commit'],
      'gemini_commit':cfg['10_rev_d1_1_safety_contract']['gemini_comparison_commit'],
      'gemini_archive_branch':'archive/gemini-evt1-revc-94b50cf-20261117',
      'status':'NOT_FOR_FAB','claim_scope':'file topology,behavioural models,actual native FPGA tools; never bench or vendor NDA qualification'})
    # Authoritative documents are authored in the change directory, copied here
    # so generator and reviewed delivery cannot silently diverge.
    source=Path(__file__).resolve().parent
    for filename in ['ICD_FPGA_HOST_OPTICS_SPEC_REV_D1_1.md','KIMI_REV_D1_1_UPDATE_CHECKLIST.md']:
        (arch/filename).write_bytes((source/filename).read_bytes())
    for filename in ['ICD_FPGA_HOST_OPTICS_SPEC_REV_D1.md','KIMI_ENGINEERING_HANDOFF_REV_D1.md']:
        (arch/filename).unlink(missing_ok=True)
    (stage/'README_START_HERE.md').write_bytes('''# 智元跃动 AI/AR V1.0 — EVT-1 Rev D1.1

**NOT FOR FAB / NOT_FOR_FAB**。保持双目透明AR和40g产品目标。本轮只修改确认的AVDD联锁与关电逻辑，Rev D1基线保留在同级evt1-rev-d1-20261117。

权威电气表：02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv；PINMAP逐针派生。先读01_Architecture_and_Interfaces/KIMI_REV_D1_1_UPDATE_CHECKLIST.md和ICD Rev D1.1。

可复现：python 00_Rev_D1_1_Change_Record/rev_d1_1_apply.py；python 05_Verification_Scripts/check_rev_d1_1_reproducibility.py；python 05_Verification_Scripts/verify_rev_d1_1_electrical.py；python 05_Verification_Scripts/test_rev_d1_1_avdd_safety.py --require-ngspice；make -C 03_FPGA_RTL all。

PASS仅表示对应测试覆盖的文件、逻辑或模型通过。物理电路、JBD参数、原生CAD/ERC/DRC、掉电轨序和实测仍BLOCKED。CI日志和完整ZIP分别交付；不得据此投板。
'''.encode('utf8'))
