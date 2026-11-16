"""Rev D1.1 AVDD source-circuit corrections. NOT FOR FAB; no hardware qualification."""

SAFE_PINS = {
 'U_AVDD_LS': {'1':'VCCA','2':'A1','3':'A2','4':'GND','5':'DIR','6':'B2','7':'B1','8':'VCCB'},
 'U_AVDD_WD': {'1':'TRIG','2':'GND','3':'SET','4':'DIV','5':'V+','6':'OUT'},
 'U_AVDD_IO_PG': {'1':'SENSE','2':'GND','3':'MR','4':'VDD','5':'CT','6':'RESET'},
 'U_AVDD_SYS_PG': {'1':'SENSE','2':'GND','3':'MR','4':'VDD','5':'CT','6':'RESET'},
 'U_AVDD_SYS_CLAMP': {'1':'SENSE','2':'GND','3':'MR','4':'VDD','5':'CT','6':'RESET'},
 'U_AVDD_CLEAR_OD': {'1':'1A','2':'GND','3':'2A','4':'2Y','5':'VCC','6':'1Y'},
 'U_AVDD_SCHMITT': {'1':'1A','2':'GND','3':'2A','4':'2Y','5':'VCC','6':'1Y'},
 'U_AVDD_QUAL': {'1':'CLK','2':'GND','3':'D','4':'Q','5':'VCC','6':'CLR'},
 'U_AVDD_EN_OD': {'1':'1A','2':'GND','3':'2A','4':'2Y','5':'VCC','6':'1Y'},
}

def apply_avdd_safety_corrections(net, bom):
    """Mutate only the new D1.1 candidate; D1 source package is never an output."""
    fields=list(bom[0]); by={r['Item_ID']:r for r in bom}; board='M-OPT-BRIDGE'
    def part(ref,mpn,category='AVDD_Safety',w='1.0',l='1.0',h='0.5',pitch='TBD',mass='0.001',source='',notes=''):
        bid='BOM-D11-'+ref
        b={k:'' for k in fields}
        b.update(Item_ID=bid,RefDes=ref,Board_Zone=board,Side='UNPLACED',Center_X_mm='TBD',Center_Y_mm='TBD',
          Body_Width_X_mm=w,Body_Length_Y_mm=l,Body_Height_Z_mm=h,Pad_Pitch_mm=pitch,Category=category,MPN=mpn,
          Manufacturer='See source ledger',Package_Footprint=notes,Key_Electrical_Specs=notes,Qty='1',Unit_Mass_g=mass,
          Verification_Status='SOURCE_CHECKED_CANDIDATE; full PVT/transient/layout/physical qualification BLOCKED',
          Datasheet_URL=source,Rev_D1_Change='D1.1 safety addition; mass estimate only')
        bom.append(b);by[bid]=b;return bid
    def put(ref,pin,fn,n,role='RCV',bid=None,v='VSYS_DOMAIN',note=''):
        if v=='VSYS_DOMAIN':v='0' if n=='GND' or n.startswith('NC_') else ('1.8' if n in ['1V8_FPGA_IO','FPGA_CDONE_VSYNC_N','FPGA_CRESET_B'] else '4.5')
        net.append(dict(Net=n,Domain_V=str(v),Board=board,RefDes=ref,Pin=str(pin),Pin_Function=fn,Role=role,
          BOM_Line=bid or 'BOM-D11-'+ref,I_Peak_A='',Note=note))
    def passive(ref,val,n1,n2,category='Resistor',role='PASSIVE',mass='0.001',note=''):
        cap=category=='Capacitor'
        bid=part(ref,val,category,w='1.0' if cap else '0.6',l='0.5' if cap else '0.3',h='0.5' if cap else '0.3',pitch='TBD',mass=mass,notes=('0402 capacitor' if cap else '0201 resistor')+' candidate; exact procurement MPN/DC bias/assembly qualification OPEN; '+note)
        put(ref,1,val,n1,role,bid,note=note);put(ref,2,val,n2,'PASSIVE',bid,note=note)
    # Eliminate the capacitor-to-reset diode charge injection path, not merely rename it.
    remove={'R_SEQ','C_SEQ','D_SEQ','TP_AVDD_SAFE'}|set(SAFE_PINS)
    net[:]=[r for r in net if r['RefDes'] not in remove and not r['RefDes'].startswith(('R_AVDD_','C_AVDD_'))]
    ti='https://www.ti.com/lit/ds/symlink/'
    specs=[
      ('U_AVDD_LS','SN74LVC2T45DCUR','2.3','2.0','0.9','0.5','0.003',ti+'sn74lvc2t45.pdf','VSSOP-8 DCU; VCCA=1V8_FPGA_IO, VCCB=VSYS, A-to-B DIR=VCCA'),
      ('U_AVDD_WD','LTC6993IS6-2#TRPBF','2.9','1.6','1.0','0.95','0.006','https://www.analog.com/media/en/technical-documentation/data-sheets/LTC6993-6993-1-6993-2-6993-3-6993-4.pdf','S6 TSOT-23-6; rising-edge retriggerable; DIVCODE4, positive OUT, NDIV4096, RSET402k1%'),
      ('U_AVDD_IO_PG','TPS389018DSET','1.5','1.5','0.8','0.5','0.002',ti+'tps3890.pdf','DSE WSON-6; SENSE1V8_FPGA_IO; MR=translatedCRESET; OD RESET'),
      ('U_AVDD_SYS_PG','TPS389025DSET','1.5','1.5','0.8','0.5','0.002',ti+'tps3890.pdf','DSE WSON-6; SENSEVSYS; MR=filtered translatedD3; OD RESET toPG_NODE'),
      ('U_AVDD_SYS_CLAMP','TPS389025DSET','1.5','1.5','0.8','0.5','0.002',ti+'tps3890.pdf','Independent DSE WSON-6 supervisor, direct OD RESET to LDO EN, including below digital-logic operating range'),
      ('U_AVDD_CLEAR_OD','74LVC2G07GS','1.0','1.0','0.35','0.35','0.001','https://assets.nexperia.com/documents/data-sheet/74LVC2G07.pdf','SOT1202 XSON6; two OD outputs share QUAL_RC to clear on watchdog or PG fault; IOZ2uA/channel'),
      ('U_AVDD_SCHMITT','SN74LVC2G17DCKR','2.0','1.25','1.1','0.65','0.002',ti+'sn74lvc2g17.pdf','SC70-6 DCK; channel1 cleans PG_NODE rise, channel2 qualifies slow RC clear release'),
      ('U_AVDD_QUAL','SN74LVC1G175DCKR','2.0','1.25','1.1','0.65','0.002',ti+'sn74lvc1g175.pdf','SC70-6 DCK; risingD3 CLK, D=VSYS; CLR=Schmitt-qualified delayed arm; asynchronous clear'),
      ('U_AVDD_EN_OD','74LVC2G07GS','1.0','1.0','0.35','0.35','0.001','https://assets.nexperia.com/documents/data-sheet/74LVC2G07.pdf','SOT1202 XSON6; two OD outputs clamp LDO EN on PG fault or qualification absent'),
    ]
    for ref,mpn,w,l,h,pitch,mass,url,notes in specs:part(ref,mpn,w=w,l=l,h=h,pitch=pitch,mass=mass,source=url,notes=notes)
    ls=[(1,'VCCA','1V8_FPGA_IO','SINK'),(2,'A1','FPGA_CDONE_VSYNC_N','RCV'),(3,'A2','FPGA_CRESET_B','RCV'),
        (4,'GND','GND','SINK'),(5,'DIR','1V8_FPGA_IO','TIE'),(6,'B2','AVDD_CRESET_VSYS','DRV'),(7,'B1','AVDD_D3_VSYS','DRV'),(8,'VCCB','VSYS','SINK')]
    for p,fn,n,role in ls:put('U_AVDD_LS',p,fn,n,role)
    for p,fn,n,role in [(1,'TRIG','AVDD_D3_VSYS','RCV'),(2,'GND','GND','SINK'),(3,'SET','AVDD_WD_SET','PASSIVE'),
       (4,'DIV','AVDD_WD_DIV','PASSIVE'),(5,'V+','VSYS','SINK'),(6,'OUT','AVDD_WD_Q','DRV')]:put('U_AVDD_WD',p,fn,n,role)
    for ref,sense,mr,out in [('U_AVDD_IO_PG','1V8_FPGA_IO','AVDD_CRESET_VSYS','AVDD_PG_NODE'),
      ('U_AVDD_SYS_PG','VSYS','AVDD_REQ_FILTER','AVDD_PG_NODE'),('U_AVDD_SYS_CLAMP','VSYS','VSYS','OPT_AVDD_EN')]:
        for p,fn,n,role in [(1,'SENSE',sense,'RCV'),(2,'GND','GND','SINK'),(3,'MR',mr,'RCV'),(4,'VDD','VSYS','SINK'),
          (5,'CT','NC_'+ref+'_CT','NC'),(6,'RESET',out,'DRV_OD')]:put(ref,p,fn,n,role,note='CT unpopulated: response/release timings are nominal, not guaranteed board fault latency')
    for p,fn,n,role in [(1,'1A','AVDD_WD_Q','RCV'),(2,'GND','GND','SINK'),(3,'2A','AVDD_PG_OK','RCV'),
      (4,'2Y','AVDD_QUAL_RC','DRV_OD'),(5,'VCC','VSYS','SINK'),(6,'1Y','AVDD_QUAL_RC','DRV_OD')]:put('U_AVDD_CLEAR_OD',p,fn,n,role)
    for p,fn,n,role in [(1,'1A','AVDD_PG_NODE','RCV'),(2,'GND','GND','SINK'),(3,'2A','AVDD_QUAL_RC','RCV'),
      (4,'2Y','AVDD_QUAL_CLR_N','DRV'),(5,'VCC','VSYS','SINK'),(6,'1Y','AVDD_PG_OK','DRV')]:put('U_AVDD_SCHMITT',p,fn,n,role)
    for p,fn,n,role in [(1,'CLK','AVDD_D3_VSYS','RCV'),(2,'GND','GND','SINK'),(3,'D','VSYS','TIE'),
      (4,'Q','AVDD_PULSE_QUAL','DRV'),(5,'VCC','VSYS','SINK'),(6,'CLR','AVDD_QUAL_CLR_N','RCV')]:put('U_AVDD_QUAL',p,fn,n,role)
    for p,fn,n,role in [(1,'1A','AVDD_PG_OK','RCV'),(2,'GND','GND','SINK'),(3,'2A','AVDD_PULSE_QUAL','RCV'),
      (4,'2Y','OPT_AVDD_EN','DRV_OD'),(5,'VCC','VSYS','SINK'),(6,'1Y','OPT_AVDD_EN','DRV_OD')]:put('U_AVDD_EN_OD',p,fn,n,role)
    for ref,val,a,b,role in [
      ('R_AVDD_WD_SET','402k1%','AVDD_WD_SET','GND','PASSIVE'),
      ('R_AVDD_WD_DIV_H','1.00M1%','VSYS','AVDD_WD_DIV','PASSIVE'),('R_AVDD_WD_DIV_L','392k1%','AVDD_WD_DIV','GND','PASSIVE'),
      ('R_AVDD_D3_PD','100k1%','AVDD_D3_VSYS','GND','PULLDOWN'),('R_AVDD_CRST_PD','100k1%','AVDD_CRESET_VSYS','GND','PULLDOWN'),
      ('R_AVDD_PG_PU','10k1%','AVDD_PG_NODE','VSYS','PULLUP'),
      ('R_AVDD_REQ_FILTER','10k1%','AVDD_D3_VSYS','AVDD_REQ_FILTER','PASSIVE'),
      ('R_AVDD_QUAL_PU','10k1%','AVDD_WD_Q','AVDD_QUAL_RC','PULLUP'),
      ('R_AVDD_EN_FEED','68k1%','AVDD_WD_Q','OPT_AVDD_EN','PASSIVE'),('R_AVDD_EN_PD','330k1%','OPT_AVDD_EN','GND','PULLDOWN')]:passive(ref,val,a,b,role=role)
    passive('C_AVDD_REQ_FILTER','10nF C0G 5%','AVDD_REQ_FILTER','GND','Capacitor')
    passive('C_AVDD_QUAL','100nF X7R10V; effective50..110nF qualification OPEN','AVDD_QUAL_RC','GND','Capacitor')
    for ref in SAFE_PINS:
        passive('C_AVDD_'+ref+'_V','100nF X7R 10V','VSYS','GND','Capacitor')
    passive('C_AVDD_LS_A','100nF X7R 6.3V','1V8_FPGA_IO','GND','Capacitor')
    pad=part('TP_AVDD_SAFE','PCB test pads, fixture geometry TBD','Test_Pads',w='2.5',l='2.5',h='0',pitch='TBD',mass='0',notes='Nine explicit probe nodes; placement/capacitive loading and fixture geometry OPEN')
    for p,n in enumerate(['FPGA_CDONE_VSYNC_N','FPGA_CRESET_B','AVDD_WD_Q','AVDD_PG_NODE','AVDD_QUAL_CLR_N','AVDD_PULSE_QUAL','OPT_AVDD_EN','AVDD_OPT_BIAS','GND'],1):
        put('TP_AVDD_SAFE',p,'Probe '+n,n,'PASSIVE',pad,v='NDA_UNSPECIFIED' if n=='AVDD_OPT_BIAS' else 'VSYS_DOMAIN',note='AVDD output voltage remains BLK-JBD-04; probe loading must be included in qualification')
    # Safe default on bridge if translator source is unpowered/high-Z. Remove old pullup.
    for r in net:
        if r['RefDes']=='R_CRST_PU':r['RefDes']='R_CRST_PD';r['Pin_Function']='10k reset pulldown';r['Role']='PULLDOWN' if r['Pin']=='1' else 'PASSIVE';r['Note']='D1.1 FPGA reset defaults LOW; no discharge diode injecting current into reset'
        if r['RefDes']=='R_CRST_PD' and r['Pin']=='2':r.update(Net='GND',Domain_V='0')
        if r['RefDes']=='U6_OPT_AVDD' and r['Pin']=='3':r.update(Domain_V='4.5',Note='D1.1 watchdog, completed-heartbeat qualifier and independent UVLO clamps. LDO output value remains JBD BLOCKED.')
    by['BOM-33']['MPN']='R_PLL(100R)+C_PLL(4.7uF/100nF)+R_VPP(10R)+C_VPP(4.7uF)+R_SS_PD(10k)+R_CRST_PD(10k)+R_CDONE_PU(4.7k)+10xR_DAMP(22R)+2xR_OPTCS_PU(10k)'
    by['BOM-33']['Key_Electrical_Specs']='FPGA PLL/config/VPP and optical-series damping only; former R_SEQ/C_SEQ/D_SEQ removed. AVDD watchdog/qualification/supervisor peripherals are explicit BOM-D11 components.'
    by['BOM-33']['Rev_D1_Change'] += '; D1.1 removes R_SEQ/C_SEQ/D_SEQ; explicit AVDD watchdog/qualifier BOM lines replace the old RC gate'
    by['BOM-45']['Key_Electrical_Specs']='TLV755P DQN candidate; EN driven only by D1.1 explicit watchdog/qualification/interlock; VHI1.0V/VLO0.3V; output voltage, off sequencing and fitted MPN remain BLK-JBD-04.'
    # SBVS320D Table4-1 requires the DQN central thermal pad grounded as well as pin2.
    for ref in ['U4_1V2','U4_1V8F','U6_OPT_AVDD','U5_LED2V8','U6_CAM_DOVDD','U6_CAM_DVDD','U6_CAM_AVDD']:
        rs=[r for r in net if r['RefDes']==ref]
        if rs and not any(r['Pin']=='EP' for r in rs):
            x=dict(rs[0]);x.update(Pin='EP',Pin_Function='Thermal pad',Net='GND',Domain_V='0',Role='SINK',Note='SBVS320D Table4-1: DQN thermal pad internally GND, PCB ground connection required');net.append(x)
    validate_avdd_safety(net)

def validate_avdd_safety(net):
    idx={(r['RefDes'],r['Pin']):r for r in net}
    for ref,pins in SAFE_PINS.items():
        actual={r['Pin']:r['Pin_Function'] for r in net if r['RefDes']==ref}
        assert actual==pins,(ref,actual,pins)
    for ref in ['R_SEQ','C_SEQ','D_SEQ','R_CRST_PU']:assert not any(r['RefDes']==ref for r in net),ref
    checks={('U_AVDD_LS','2'):'FPGA_CDONE_VSYNC_N',('U_AVDD_LS','3'):'FPGA_CRESET_B',
      ('U_AVDD_WD','1'):'AVDD_D3_VSYS',('U_AVDD_QUAL','1'):'AVDD_D3_VSYS',('U_AVDD_QUAL','6'):'AVDD_QUAL_CLR_N',
      ('U_AVDD_SCHMITT','3'):'AVDD_QUAL_RC',('U_AVDD_SCHMITT','4'):'AVDD_QUAL_CLR_N',
      ('U_AVDD_CLEAR_OD','4'):'AVDD_QUAL_RC',('U_AVDD_CLEAR_OD','6'):'AVDD_QUAL_RC',
      ('U_AVDD_EN_OD','4'):'OPT_AVDD_EN',('U_AVDD_EN_OD','6'):'OPT_AVDD_EN',
      ('U_AVDD_SYS_CLAMP','6'):'OPT_AVDD_EN',('U_AVDD_IO_PG','1'):'1V8_FPGA_IO',
      ('U_AVDD_IO_PG','3'):'AVDD_CRESET_VSYS',('U_AVDD_SYS_PG','3'):'AVDD_REQ_FILTER',
      ('R_CRST_PD','2'):'GND',('U6_OPT_AVDD','EP'):'GND'}
    for k,v in checks.items():assert idx[k]['Net']==v,(k,idx[k]['Net'],v)
    for ref in [r['RefDes'] for r in net if r['RefDes'].startswith(('R_AVDD_','C_AVDD_'))]:
        assert len([r for r in net if r['RefDes']==ref])==2,ref
    return {'status':'PASS_SOURCE_TOPOLOGY_ONLY','new_ic_packages':len(SAFE_PINS),'physical_safety_status':'BLOCKED','removed_reset_injection_diode':True,'new_thermal_pad_connections':7}
