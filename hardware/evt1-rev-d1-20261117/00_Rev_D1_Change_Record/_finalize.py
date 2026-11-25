"""Derived documents/tables from the corrected netlist. No CAD or hardware claims."""
import csv,json,hashlib
from pathlib import Path

def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def writecsv(p,rows,fields=None):
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

def js(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def complete_peripherals(net,tbl):
    # Rev D encoded several pull returns and series resistors only in prose.
    # Expand those into real two-terminal edges without changing FPGA ports.
    bias={'R_CRST_A_PD':'GND','R_DIR1_PU':'3V3_SYS',
      'R_I2C_SCL_3V3':'3V3_SYS','R_I2C_SDA_3V3':'3V3_SYS',
      'R_I2C_SCL_1V8':'1V8_SYS','R_I2C_SDA_1V8':'1V8_SYS',
      'R_SCCB_SCL':'CAM_DOVDD_1V8','R_SCCB_SDA':'CAM_DOVDD_1V8',
      'R_PRIV_PU':'V_INA_OUT','C_XREQ':'GND','R_XREQ_BLEED':'GND',
      'R_CAMRST':'CAM_DOVDD_1V8','R_CAMPWDN':'GND','R_IPC_PU':'1V8_SYS'}
    for ref,n in bias.items():
        rows=[r for r in net if r['RefDes']==ref]
        if len(rows)==1:
            r=dict(rows[0]);r.update(Pin='2',Net=n,Role='PASSIVE',Note='Explicit return expanded from inherited Rev D function text')
            if n=='GND':r['Domain_V']='0'
            net.append(r)
    rst=next(r for r in net if r['RefDes']=='R_CAMRST')
    rst['Pin_Function']='10k 1% (POR pullup)'
    for pin,n in [('1','CAM_RESET_N'),('2','GND')]:
        r=dict(rst);r.update(RefDes='C_CAMRST',Pin=pin,Net=n,Role='PASSIVE',Pin_Function='100nF POR capacitor',Note='Explicit camera reset RC capacitor')
        if n=='GND':r['Domain_V']='0'
        net.append(r)
    conn=readcsv(tbl/'CONNECTOR_PINOUT_REV_D.csv')
    for r in list(net):
        if r['RefDes'].startswith('R_DAMP_') and len([x for x in net if x['RefDes']==r['RefDes']])==1:
            out=r['Net']+'_PANEL'
            nr=dict(r);nr.update(Pin='2',Net=out,Role='PASSIVE',Note='Panel-side series damping terminal; FPGA-side net/PCF unchanged')
            net.append(nr)
            for c in net:
                if c['RefDes'] in ['J_DISP_L','J_DISP_R'] and c['Net']==r['Net']:c['Net']=out
            for c in conn:
                if c['RefDes'] in ['J_DISP_L','J_DISP_R'] and c['Net']==r['Net']:c['Net']=out
    writecsv(tbl/'CONNECTOR_PINOUT_REV_D.csv',conn)
    # Antenna tuning pi is a physical 0-ohm link plus two DNP shunt sites.
    # No unverified RF L/C value is populated by this migration.
    virtual=[r for r in net if r['RefDes']=='RN_ESP_RF']
    if virtual:
        net[:]=[r for r in net if r['RefDes']!='RN_ESP_RF']
        for ref,n1,n2,val in [('R_ESP_RF0','ESP_RF_ANT','ESP_ANT_FEED','0 ohm RF link; tune after VNA'),
          ('C_ESP_TUNE1','ESP_RF_ANT','GND','DNP shunt tuning capacitor'),('C_ESP_TUNE2','ESP_ANT_FEED','GND','DNP shunt tuning capacitor')]:
            for pin,n in [('1',n1),('2',n2)]:
                r=dict(virtual[0]);r.update(RefDes=ref,Pin=pin,Net=n,Pin_Function=val,Role='PASSIVE',Note='Explicit ESP antenna-tuning pi; DNP capacitors do not imply a physical shunt')
                net.append(r)

def finalize(stage,baseline,net,bom):
    tbl=stage/'02_BOM_PINMAP_ICD_Blocked'; arch=stage/'01_Architecture_and_Interfaces'
    complete_peripherals(net,tbl)
    oldbom={x['Item_ID']:x for x in readcsv(baseline/'02_BOM_PINMAP_ICD_Blocked/BOM_V1_0_FROZEN.csv')}
    # Keep original placement envelopes pending real layout. Recovered shortened
    # board coordinates had never been saved or checked against all new passives.
    for b in bom:
        old=oldbom.get(b['Item_ID'])
        if old:
            for k in ['Side','Center_X_mm','Center_Y_mm']:
                b[k]=old[k]
            if b['Item_ID']=='BOM-14':
                b['Body_Width_X_mm']=old['Body_Width_X_mm'];b['Body_Length_Y_mm']=old['Body_Length_Y_mm']
            b['Rev_D1_Change']=b.get('Rev_D1_Change','').replace('M-MAIN-L shrinks 46.0 -> 41.6 mm','41.6 mm board is only a candidate; 46 mm retained pending CAD')
        else:
            b['Center_X_mm']='TBD';b['Center_Y_mm']='TBD';b['Side']='UNPLACED'
        # Clear over-broad legacy claims; per-pin source ledgers carry real scope.
        if b.get('Verification_Status','').startswith(('VERIFIED_D1','FROZEN','DESIGN_RULE_D1')):
            b['Verification_Status']='SOURCE_CHECKED_D1; footprint/layout/physical validation pending'
        if 'TLV755' in b['MPN']:
            b.update(Package_Footprint='X2SON-4 DQN 1.00x1.00mm nominal;0.65mm pitch;0.40mm max height',
                     Pad_Pitch_mm='0.65',Body_Height_Z_mm='0.40')
        if b['Item_ID']=='BOM-45':
            b.update(MPN='MPN_TBD (TLV755P DQN family; AVDD voltage requires BLK-JBD-04)',
                     Verification_Status='BLOCKED_JBD_AVDD_VALUE; public control pins/thresholds checked; no output voltage frozen')
    # Remove obsolete narrative PINMAP; one row per netlist terminal prevents
    # the previous aggregate-field migration from silently keeping Rev D pins.
    pm=[]
    for r in net:
        pm.append(dict(Chip_Ref=r['RefDes'],Pin_ID=r['Pin'],Pin_Name=r['Pin_Function'],
          Signal_Net_Name=r['Net'],Direction=r['Role'],Voltage_Domain=r['Domain_V'],
          Board=r['Board'],BOM_Line=r['BOM_Line'],Datasheet_Verification_Note=r['Note'],
          Rev_D1_Status='SOURCE_NETLIST_DERIVED; NOT_FOR_FAB'))
    writecsv(tbl/'PINMAP_V1_0_FROZEN.csv',pm)
    # Every explicit auxiliary terminal remains traceable to the owning BOM line.
    by={b['Item_ID']:b for b in bom};instances=[]
    for ref in sorted({r['RefDes'] for r in net}):
        rs=[r for r in net if r['RefDes']==ref];ids=sorted({r['BOM_Line'] for r in rs})
        b=by[ids[0]]
        instances.append(dict(RefDes=ref,BOM_Line=';'.join(ids),Board=rs[0]['Board'],
          Terminal_Count=len(rs),Owner_MPN=b['MPN'],
          Terminal_Functions='; '.join(f"{r['Pin']}:{r['Pin_Function']}" for r in rs),
          Selection_Status=b['Verification_Status']))
    writecsv(tbl/'BOM_COMPONENT_INSTANCES_REV_D1.csv',instances)
    cfg=json.loads((arch/'SYSTEM_BUDGETS_V1_0.json').read_text(encoding='utf8'))
    cfg['document_version']='V1.2-EVT1-RevD1-20261117'
    cfg['release_status']='NOT_FOR_FAB'
    p=cfg['2_dual_battery_catalog_and_power_tree']
    p['left_charger']={'mpn':'BQ25180YBGR','vbat_reg_v':4.2,'sys_reg_v':4.5,
      'charge_current_target_ma':50,'programming':'readback-verified I2C initialization per POWER_SOURCE_REVIEW.md; reset defaults are not the design target',
      'ntc':'independent protected-pack NTC; do not copy old BQ24074 thresholds',
      'qualification':'OPEN: cell PCM/NTC and hot/cold faults, watchdog and battery-only behavior require bench tests'}
    p['buck_boost_3v3'].update(mpn='TPS63805YFFR',vin_min_v=1.3)
    p['buck_boost_3v3'].pop('uvlo_stop_v',None)
    p['buck_boost_3v3']['undervoltage_qualification']='No2.8V systemUVLO is implemented by tied-EN converter; qualified protected-cell PCM must provide cell undervoltage isolation, with system shutdown policy verified on bench'
    p['ideal_diode_oring'].update(rdson_mohm=40.0)
    p['right_charger']['qualification']='OPEN: verify termination/safety timer in every cable/load/switchover state; see power source review'
    s=cfg['6_power_thermal_mass_and_cog_budgets']
    shell=s['rev_d_missing_items_estimate']['temple_shell_model']
    shell_each=sum(x['perimeter_mm']*x['length_mm'] for x in shell['segments'])*shell['wall_mm']*shell['density_g_cm3']/1000*1.05
    base=sum(x['mass_g'] for x in s['subassemblies'])+2*shell_each+sum(x['mass_g'] for x in s['rev_d_missing_items_estimate']['other_items'])
    reserve_electronics=0.20  # planning allowance, never an observed mass delta
    current=base+reserve_electronics
    # No optical, battery or right PCBA/counterweight reduction is credited.
    frame0=s['subassemblies'][0]['mass_g']
    candidate=current-(frame0-9.55)-2*(shell_each-1.80)-(0.40-0.35)-(0.50-0.40)
    candidate_with_reserve=candidate+0.50
    cfg['8_rev_d1_mass_plan']={
      'status':'OPEN_UNMEASURED; conditional engineering estimate only',
      'current_analytical_estimate_g':round(current,4),
      'inherited_rev_d_estimate_g':round(base,4),
      'new_electronics_allowance_g':reserve_electronics,
      'candidate_nominal_g':round(candidate,4),'contingency_g':0.50,
      'candidate_including_contingency_g':round(candidate_with_reserve,4),
      'target_g':39.5,'physical_mass_verified':False,
      'caps_g':{'front_frame_and_hinges':9.55,'each_temple_shell':1.80,'all_fpc_and_stiffeners':0.35,'fasteners_adhesive_mesh':0.40},
      'shell_geometry_candidate':{'material':'PA12','density_g_cm3':1.01,'wall_mm':0.45,
        'segments':shell['segments'],'end_allowance_factor':1.05,'rib_allowance_each_g':0.03,
        'calculated_each_g':round(shell_each*0.45/0.60+0.03,4),
        'qualification':'candidate thin-wall shell only; molding, stiffness, drop/hinge fatigue and skin-thermal validation required; no actual CAD geometry claimed'},
      'basis':'Rev D ledger retained; capped PA12-shell/frame/FPC integration proposal; electronics +0.20g allowance. No credit for board shortening, battery substitution, reduced optics or removal of hidden counterweight.',
      'closure':'vendor module masses + native assembly CAD volume/materials + weighed complete binocular assembly; prescription lenses additional if outside scope'}
    for v in s['scenarios'].values():
        v['inherited_rev_d_power_mw']=v['power_mw']
        v['rev_d1_increment_allowance_mw']=40.0
        v['power_mw']+=40.0
        v['basis']='planning upper estimate: inherited profile +40mW allowance; JBD current and SoC/radio duty cycles unmeasured'
        v['runtime_h_at_85pct_energy']=round(p['total_energy_wh']*0.85/(v['power_mw']/1000),3)
    s['measurement_status']='UNVERIFIED; do not use legacy thermal/runtime figures as measured values'
    boards=cfg['5_hdi_pcb_and_complete_bom_3d_placement']['boards']
    for board in boards.values():
        board['placement_status']='INHERITED_ENVELOPE_ONLY; all changed footprints require native CAD re-placement and DRC'
        for c in board['components']:
            candidates=[b for b in bom if c['ref'] in [v.strip() for v in b['RefDes'].split(',')]]
            if len(candidates)==1:
                b=candidates[0]
                for key,bk in [('w_mm','Body_Width_X_mm'),('l_mm','Body_Length_Y_mm'),('h_mm','Body_Height_Z_mm')]:
                    try:c[key]=float(b[bk])
                    except ValueError:pass
    cfg['9_rev_d1_layout_gate']={'status':'NOT_FOR_FAB','active_board_length_l_mm':46.0,
      'shortened_board_candidate_l_mm':41.6,'shortening_mass_credit_g':0,
      'unplaced_new_refs':[b['RefDes'] for b in bom if b['Side']=='UNPLACED'],
      'rules':'6-layer 2+2+2 HDI inherited; WLCSP breakout, decoupling ownership, RF reference geometry, no hinge vias/components, copper IR/thermal and complete placement/DRC must be checked in native CAD',
      'stackup_status':'candidate stack, supplier impedance and microvia reliability not qualified'}
    js(arch/'SYSTEM_BUDGETS_V1_0.json',cfg)
    mass=cfg['8_rev_d1_mass_plan']
    writecsv(tbl/'MASS_PLAN_REV_D1.csv',[{'Case':'Current estimate','Mass_g':mass['current_analytical_estimate_g'],'Status':'UNMEASURED'},
      {'Case':'Conditional integration nominal','Mass_g':mass['candidate_nominal_g'],'Status':'PROPOSED_CAPS'},
      {'Case':'Conditional integration including 0.50g reserve','Mass_g':mass['candidate_including_contingency_g'],'Status':'OPEN_REQUIRES_CAD_AND_WEIGHING'}])
    # Connector topology is unchanged; create an explicit D1 name for consumers.
    shutil_src=tbl/'CONNECTOR_PINOUT_REV_D.csv'
    (tbl/'CONNECTOR_PINOUT_REV_D1.csv').write_bytes(shutil_src.read_bytes())
    tr=json.loads((tbl/'TRANSLATOR_BANKS_REV_D.json').read_text(encoding='utf8'))
    if 'U8_CAM_ISO2' in tr:
        for bank in tr['U8_CAM_ISO2']['banks'].values():
            for ch in bank['ch']:
                if ch[0]==4:
                    ch[1]='CAM_DOVDD_1V8';ch[2]='CAM_DOVDD_OK_3V3'
    js(tbl/'TRANSLATOR_BANKS_REV_D1.json',tr)
    cfg['1_soc_and_audio_architecture']['sn74axc8t245_transceivers']=tr
    cfg['1_soc_and_audio_architecture']['nrf5340_configuration']='Official CMAA config3 reference circuitry; see SOC_SOURCE_REVIEW and explicit NETLIST; firmware mode must match fitted inductors'
    cfg['3_camera_privacy_and_anti_backpower_model']['sccb_isolator']='PCA9306 VREF2/EN explicitly clamped LOW by U8_CAM_SCCB_EN when DOVDD absent; CAM_ISO2 ch4 senses gated rail; verify ramp/startup/partial-power states'
    cfg['3_camera_privacy_and_anti_backpower_model']['rev_d1_filter_analysis']={'local_discharge_tau_ms':1.0,'charge_tau_with_pullup_ms':11.0,'status':'nominal RC calculation; not guaranteed fault response or a measured result'}
    js(arch/'SYSTEM_BUDGETS_V1_0.json',cfg)
    # Bridge now uses the always-on1.8V pins for mic/IMU, not just FPC pass-through.
    for r in net:
        if r['RefDes']=='J_BRIDGE_IN' and r['Net']=='1V8_SYS':r['Note']='Rev D1 bridge IMU/mic supply tap; not NC_TRUNK_PASS'
    conn=readcsv(tbl/'CONNECTOR_PINOUT_REV_D1.csv')
    for r in conn:
        if r['RefDes']=='J_BRIDGE_IN' and r['Net']=='1V8_SYS':r['Note']='Rev D1 bridge IMU/mic supply tap'
    writecsv(tbl/'CONNECTOR_PINOUT_REV_D1.csv',conn)
    # Re-derive PINMAP after the bridge connector annotation correction.
    for p,r in zip(pm,net):p['Datasheet_Verification_Note']=r['Note']
    writecsv(tbl/'PINMAP_V1_0_FROZEN.csv',pm)
    icd=readcsv(tbl/'ICD_INTERFACE_CONTROL_TABLE.csv')
    for row in icd:
        for k,v in row.items():
            row[k]=v.replace('NETLIST_ELECTRICAL_CONNECTION_REV_D.csv','NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv').replace('BQ24074','BQ25180').replace('TPS63802','TPS63805')
        row['Rev_D1_Control']='PINMAP/NETLIST Rev D1 physical terminals authoritative; inherited functional interface unless superseded by ICD Rev D1'
    writecsv(tbl/'ICD_INTERFACE_CONTROL_TABLE.csv',icd)
    blocked=readcsv(tbl/'BLOCKED_ITEMS_CHECKLIST.csv')
    bf=list(blocked[0])
    for b in blocked:
        if b['Blocker_ID']=='BLK-RevC-01':
            b.update(Status_Tag='BASELINE_CI_PASSED; REV_D1_CI_REQUIRED',
                     Root_Cause='Historical environment restriction superseded by real GitHub CI on PR #20.',
                     Current_Engineering_State='Rev D unchanged FPGA passed Actions run 43906082409 on commit 882242f. Rev D1 workflow reruns the exact same sources; inspect current D1 check status.')
        if b['Blocker_ID']=='KIMI-RevD-04':
            b.update(Status_Tag='CLOSED_SOURCE_ONLY',Current_Engineering_State='95/95 CMAA balls mapped from Nordic PS; PSEL, supply and RF/reference peripherals explicit. Physical layout, firmware and radio verification remain OPEN.',Resolution_Path='Use Rev D1 NETLIST and SOC_SOURCE_REVIEW; do not remap from the obsolete Rev D aggregate rows.')
        if b['Blocker_ID']=='UNV-RevD-01':
            b.update(Status_Tag='OPEN_UNMEASURED',Current_Engineering_State=f'Rev D1 current estimate {current:.4f}g; conditional integration estimate {candidate_with_reserve:.4f}g including contingency. No weighing or CAD proof.',Resolution_Path='Meet documented integration caps and confirm complete binocular assembly mass; retain optical/vendor mass uncertainty.')
    # Preserve all supplier NDA entries verbatim; append engineering qualification gates.
    for ident,detail in [
      ('D1-MASS-01',f'Current estimate {current:.3f}g. Conditional integration including reserve {candidate_with_reserve:.3f}g; not weighed.'),
      ('D1-CAD-01','No editable Rev D1 schematic/PCB/STEP, ERC/DRC or routed layout; new peripheral parts remain unplaced.'),
      ('D1-BAT-01','Independent protected-pack PCM/NTC selection, cell C-rate, faults, temperature, charging termination/load switchover and transient qualification.'),
      ('D1-RF-01','nRF and ESP antenna layout, matching, crystal load/tolerance, RF tuning and regulatory qualification.'),
      ('D1-PWR-01','Capacitor derating, inductor effective L/current, supply ramp, load transients, FPGA sequence and thermal verification.'),
      ('D1-AUD-01','nRF I2S routing/peripheral limits, real LE Audio phone support, clock timing and acoustic bring-up.'),
      ('D1-CAM-01','Final camera sensor/RESET/PWDN and privacy fault tests; no final module or timing qualification.')]:
        d={k:'' for k in bf};d.update(Blocker_ID=ident,Status_Tag='OPEN',Subsystem=ident.split('-')[1],
            Item_Description=detail,Current_Engineering_State='NOT_FOR_FAB',Resolution_Path='See source review and KIMI Rev D1 handoff; physical/native qualification required')
        blocked.append(d)
    writecsv(tbl/'BLOCKED_ITEMS_CHECKLIST.csv',blocked)
    provenance={'baseline_commit':'882242fa598aa3f24537442ce39fe5be2521341b','baseline_pr':20,
      'claude_transcript':'Claude-对话记录-最近3天-2026-11-16 (1).html, updated 2026-11-17 01:10',
      'transcript_sha256':'7dc3b96c07bc6f1d36760738b6327e7396c29f951969dfa2b8675d55cbb31fa9',
      'rev_d_zip_sha256':'552377cf9c5e3d703c794aab2f7e109e451b93aea2472fd005587aac81dd8617',
      'recovery':'Recovered both heredoc scripts; fixed shared-namespace orchestration, repeat-run source isolation, schema-derived fields and per-terminal PINMAP; author corrections run before final write.',
      'fpga':'03_FPGA_RTL byte-identical to PR20; CI reruns existing FPGA implementation only'}
    js(stage/'04_Verification_Evidence/REV_D1_PROVENANCE.json',provenance)
    (stage/'README_START_HERE.md').write_text('''# 智元跃动 AI/AR V1.0 — EVT-1 Rev D1

**NOT FOR FAB / NOT_FOR_FAB**。双目透明 AR；40g 产品目标保持。源于 PR #20 / 882242f，恢复 Claude 2026-11-17 01:10 中断脚本。本包交付实际 CSV 电气工程、可重现迁移、原版 FPGA 和验证工具；尚无 Rev D1 原生 CAD 或实物验证。

先读 `01_Architecture_and_Interfaces/KIMI_ENGINEERING_HANDOFF_REV_D1.md`。权威输入为 `02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv`，PINMAP 每行从同一终端生成。旧文件名 FROZEN 不代表制造冻结。Rev D 原包保存在仓库同级目录 `evt1-rev-d-claude-20261117`。

运行：`python 00_Rev_D1_Change_Record/rev_d1_apply.py`；`python 05_Verification_Scripts/verify_rev_d1_electrical.py`；`python 05_Verification_Scripts/check_rev_d1_reproducibility.py`。迁移始终读取干净 Rev D，不向其写入。FPGA 保留 `make -C 03_FPGA_RTL all`。
''',encoding='utf8')
    (arch/'ICD_FPGA_HOST_OPTICS_SPEC_REV_D1.md').write_text('''# EVT-1 Rev D1 接口控制 — NOT FOR FAB

逐针权威：NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv、PINMAP_V1_0_FROZEN.csv；连接器：CONNECTOR_PINOUT_REV_D1.csv。

电源：两枚独立受保护 4.2V/110mAh 电池，不直接并联；左 BQ25180 的 SYS 与右受保护电池经 LM66200 选择到 VSYS。BQ25180 替代超出低充电电流推荐范围的 BQ24074。右 BQ25170 充电与负载状态必须按 POWER_SOURCE_REVIEW 审查。TPS63805 产生 3V3_SYS；TPS62840 产生 1V8_SYS（VSET=GND）。各器件 NC、接地、反馈、NTC 与外围以逐针表为准。充电初始化、watchdog、过压/欠压及电芯限值尚需固件和台架验收。

iCE40UP 电源顺序保持 Rev D：VSYS→1V2_FPGA_CORE→100Ω滤波1V2_FPGA_PLL→U4_1V8F使能→1V8_FPGA_IO→10Ω/4.7µF VPP。光机 AVDD 由 D3/CDONE 与 OPT_PWR_REQ 联锁，经原 Rev D RC/二极管网络；保持 NOT FOR FAB，JBD AVDD 值不能由本文件冻结。

FPGA、PCF、TB、Makefile 均与 PR #20 相同。A0/A1 立即写；A2/A3 防撕裂写；A4 OPT_CTRL：bit0 SCAN_EN、bit1 OPT_PWR_REQ、bit2 RAW_ARM。默认 SCAN_EN=0、OPT_PWR_REQ=1。RAW_ARM 仅在已停止扫描后接受，下个 CS 事务镜像两眼并在 CS 上升沿解除；无法独立初始化某一眼。初始化需等 CDONE 及 AVDD 建立 ≥21ms，先停扫描，再发送受 NDA 控制的初始化事务，最后打开扫描；禁止猜测 JBD 内容。

连接器针位和跨板干线继承 Rev D；BM28 电源触点 5A，信号触点 0.3A。VBAT_R_RET/GND 不借信号触点承载峰值电流。跨铰链 FPC 需连续地、供电压降计算、动态弯折寿命和无过孔弯折区审查。实际铜宽和阻抗需由板厂叠层复核。

音频：nRF5340 为唯一 I2S 主机，ESP32 从机；PDM_CLK 仅由 ESP32 产生。MAX98357A WLP 球位已纠正，右 SD_MODE 经69.8k，左右增益接地。nRF 32MHz晶振、RF网络、去耦和SWD在电气表显式连接；原厂参考值与待选项见 SOC_SOURCE_REVIEW。

摄像隐私硬件联锁继承 Rev D：XCLK 活动→CAM_PWR_REQ→LED/电流窗口→相机 LDO。相机 I/O 供电隔离、SCCB 使能、RESET/PWDN 的新审查结论见 AUDIO_TRANSLATOR_SOURCE_REVIEW；最终传感器未知，禁止宣称隐私实测通过。

BLK-JBD-01..05 全部保留：FPC针序、初始化、0x32命令、AVDD/STEP、单眼独立寄存器要求。任何传输模型通过均不替代这些资料。
''',encoding='utf8')
    (arch/'KIMI_ENGINEERING_HANDOFF_REV_D1.md').write_text(f'''# KIMI 工程交接 — Rev D1 / NOT FOR FAB

输入顺序：Rev D1 NETLIST → 每针 PINMAP → CONNECTOR_PINOUT_REV_D1 → TRANSLATOR_BANKS_REV_D1 → BOM + BOM_COMPONENT_INSTANCES → ICD Rev D1。`00_Rev_D1_Change_Record` 的三份原厂审查说明解释修正与保留阻断；不要沿用 Rev D 聚合引脚或旧验证状态。

原理图逐针导入并展开所有外围实例，不得把 RN_* 文字簇当成已连接电路；所有电源、地、去耦回路、晶振、RF、调试、EN、反馈、NTC、NC 都需要原生图元回读。保护电池接口为采购约束，尚非选定 PCM 的裸电芯设计。电气表不是可投板原理图。

6层2+2+2 HDI 候选沿用；M-MAIN-L 保留46mm，41.6mm仅为紧凑化候选，未计减重。新外围全部需原生摆放，按实际封装庭院与焊盘重跑冲突、ERC、DRC及供应商DFM。nRF晶振与RF匹配贴近芯片；电源开关回路最小；FB远离SW；去耦就近连接地；RF天线禁铜区与匹配参考几何必须复核。铰链动态区禁元件、过孔及补强端应力集中，回流地不得跨分割。

质量：当前分析估算 {current:.3f}g；前框/铰链≤9.55g、每腿壳≤1.80g、FPC/补强≤0.35g、紧固/胶/网布≤0.40g 的集成方案，含0.50g余量后估算 {candidate_with_reserve:.3f}g。该数是有条件设计预算；没有减少双目光机、电池或既有右PCBA/配重账，未虚构减重或称重。候选必须由带材料的装配CAD与实物质量闭环。

固件：更新 nRF PSEL 到逐针表，使用32MHz HFXO、按晶体CL配置电容、LFRC校准、原厂CMAA Config3电感供电配置（仅装配LC后启用VREGMAIN/VREGRADIO DC/DC）；校验该I2S外设对所选GPIO的限制。ESP32 CHIP_PU 10k/1µF，GPIO0提供下载夹具；启动时相机I/O隔离状态要实测。BQ25180 上电必须读取/配置/回读目标电流、4.2V、电源路径与watchdog；不能把复位默认当50mA配置。FPGA下载及CDONE后≥49个SCK、OPT_CTRL/RAW流程均保持Rev D。

验收：运行Python电气检查和重复生成检查；GitHub CI运行原FPGA真实仿真/综合/PnR/STA及D1电气检查。通过仅覆盖源文件结构、计算和FPGA工具，不能代表原生CAD、RF、充电、热、声学、AR光学或实物通过。剩余工作见 BLOCKED_ITEMS_CHECKLIST.csv。
''',encoding='utf8')
