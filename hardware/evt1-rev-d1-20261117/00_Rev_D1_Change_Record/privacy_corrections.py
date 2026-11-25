"""Expand inherited privacy analog symbols into real physical terminals. NOT FOR FAB."""


def apply_privacy_corrections(net, bom):
    by = {r['Item_ID']: r for r in bom}
    fields = list(bom[0])
    board = 'M-MAIN-L'
    replaced = {'U7_INA', 'U7_WIN', 'R_PRIV_RC', 'C_PRIV_RC', 'R_WIN_TOP',
                'R_WIN_MID', 'R_WIN_BOT', 'C_INA_SUPPLY', 'C_WIN_SUPPLY'}
    net[:] = [r for r in net if r['RefDes'] not in replaced]

    def row(n, v, ref, pin, fn, role, bid, note=''):
        return dict(Net=n, Domain_V=str(v), Board=board, RefDes=ref, Pin=str(pin), Pin_Function=fn,
                    Role=role, BOM_Line=bid, I_Peak_A='', Note=note)

    def passive(ref, val, mass='0.001', fp='0201 (0.6x0.3mm)', w='0.6', length='0.3', z='0.3'):
        bid = 'BOM-D1-PRIV-' + ref
        r = {f:'' for f in fields}
        r.update(Item_ID=bid, RefDes=ref, Board_Zone=board, Side='UNPLACED', Center_X_mm='TBD', Center_Y_mm='TBD',
                 Body_Width_X_mm=w, Body_Length_Y_mm=length, Body_Height_Z_mm=z, Category='Privacy_Analog_Peripheral',
                 MPN=val, Manufacturer='TBD', Package_Footprint=fp, Key_Electrical_Specs=val, Qty='1', Unit_Mass_g=mass,
                 Verification_Status='EXPLICIT_VALUE_D1; MPN/bias/layout qualification OPEN; mass estimate',
                 Rev_D1_Change='Expanded inherited privacy analog circuit; not measured')
        if bid not in by: bom.append(r); by[bid] = r
        return bid

    # INA185A4IDRLR, SBOS378A Table4-1 (DRL column, not DCK).
    ina = [('1', 'OUT', 'V_INA_OUT', 3.3, 'DRV'),
           ('2', 'GND', 'GND', 0, 'SINK'),
           ('3', 'IN+', 'LED_2V8', 2.8, 'RCV'),
           ('4', 'IN-', 'ISENSE_N', 2.8, 'RCV'),
           ('5', 'REF', 'GND', 0, 'TIE'),
           ('6', 'VS', '3V3_SYS', 3.3, 'SINK')]
    net.extend(row(n,v,'U7_INA',p,fn,role,'BOM-22','TI SBOS378A Table4-1 DRL; REF=GND for positive-current unidirectional sensing')
               for p,fn,n,v,role in ina)

    # TLV7042DSGR SLVSE13J Table4-2. Both outputs are open drain.
    # A pulls down below the lower boundary; B pulls down above the upper boundary.
    comp = [('1','OUTA','PRIV_WINDOW_OK',3.3,'DRV_OD'),
            ('2','INA-','PRIV_VTH_L',1.091,'RCV'),
            ('3','INA+','V_INA_OUT',3.3,'RCV'),
            ('4','VEE','GND',0,'SINK'),
            ('5','INB+','PRIV_VTH_H',2.182,'RCV'),
            ('6','INB-','V_INA_OUT',3.3,'RCV'),
            ('7','OUTB','PRIV_WINDOW_OK',3.3,'DRV_OD'),
            ('8','VCC','3V3_SYS',3.3,'SINK'),
            ('EP','Thermal pad','GND',0,'SINK')]
    net.extend(row(n,v,'U7_WIN',p,fn,role,'BOM-23','TI SLVSE13J Table4-2/DSG figure4-6; wire-AND open-drain outputs')
               for p,fn,n,v,role in comp)

    for ref,n1,v1,n2,v2,val in [
        ('R_WIN_TOP','3V3_SYS',3.3,'PRIV_VTH_H',2.182,'33.2k 1%'),
        ('R_WIN_MID','PRIV_VTH_H',2.182,'PRIV_VTH_L',1.091,'32.4k 1%'),
        ('R_WIN_BOT','PRIV_VTH_L',1.091,'GND',0,'32.4k 1%'),
        ('R_PRIV_RC','PRIV_WINDOW_OK',3.3,'PRIV_WINDOW_OK_F',3.3,'1k 1%')]:
        bid=passive(ref,val)
        net.extend([row(n1,v1,ref,1,val,'PASSIVE',bid),row(n2,v2,ref,2,val,'PASSIVE',bid)])
    for ref,n,v,val in [
        ('C_PRIV_RC','PRIV_WINDOW_OK_F',3.3,'1uF 10V X7R; local discharge tau1ms; pullup charge tau11ms including10k'),
        ('C_INA_SUPPLY','3V3_SYS',3.3,'100nF 10V X7R at U7_INA VS/GND'),
        ('C_WIN_SUPPLY','3V3_SYS',3.3,'100nF 10V X7R at U7_WIN VCC/VEE')]:
        bid=passive(ref,val,'0.003','0402 (1.0x0.5mm)','1.0','0.5','0.65')
        net.extend([row(n,v,ref,1,val,'PASSIVE',bid),row('GND',0,ref,2,val,'PASSIVE',bid)])

    # The inherited dynamic pullup remains V_INA_OUT, not the3.3V rail.
    # The source collapses when LED current is absent, avoiding a permanent high pullup.
    pu = [r for r in net if r['RefDes']=='R_PRIV_PU']
    for r in pu:
        r['Pin_Function']='10k 1%; dynamic pullup from V_INA_OUT'
        if r['Pin']=='1': r['Net']='PRIV_WINDOW_OK'
        if r['Pin']=='2': r['Net']='V_INA_OUT'
    if not any(r['Pin']=='2' for r in pu):
        net.append(row('V_INA_OUT',3.3,'R_PRIV_PU',2,'10k 1%; dynamic pullup from V_INA_OUT','PASSIVE','BOM-24'))
    by['BOM-22'].update(Package_Footprint='SOT-563-6 DRL;1OUT,2GND,3IN+,4IN-,5REF,6VS',
        Key_Electrical_Specs='INA185A4IDRLR gain200V/V; VS=3V3_SYS, REF/GND=GND; IN+=LED_2V8, IN-=ISENSE_N across2.20ohm; OUT=V_INA_OUT; explicit100nF bypass',
        Datasheet_URL='https://www.ti.com/lit/ds/symlink/ina185.pdf',
        Verification_Status='SOURCE_CHECKED_D1 TI SBOS378A Table4-1 DRL; analog/POR/fault verification OPEN',
        Rev_D1_Change='Expanded all6physical pins, ground reference, supply and bypass; no synthetic analog ports')
    by['BOM-23'].update(Package_Footprint='WSON-8 DSG with GND EP;1OUTA,2INA-,3INA+,4VEE,5INB+,6INB-,7OUTB,8VCC',
        Key_Electrical_Specs='TLV7042DSGR open-drain window comparator. A:(+=INAout,-=1.091V), B:(+=2.182V,-=INAout); both outputs PRIV_WINDOW_OK; VCC3.3V, VEE/EPGND.33.2k/32.4k/32.4k divider;10k pullup fromINAout;1k/1uF nominal1ms local discharge/11ms pullup-charge time constants.',
        Datasheet_URL='https://www.ti.com/lit/ds/symlink/tlv7042.pdf',
        Verification_Status='SOURCE_CHECKED_D1 TI SLVSE13J Table4-2 and DSG figure4-6; analog/POR/fault verification OPEN',
        Rev_D1_Change='Real8pins+EP; explicit lower/upper comparator inputs, divider, supplies, bypass and filter')


def validate_privacy(net):
    idx={(r['RefDes'],r['Pin']):r for r in net}
    assert {r['Pin']:r['Pin_Function'] for r in net if r['RefDes']=='U7_INA'} == {
        '1':'OUT','2':'GND','3':'IN+','4':'IN-','5':'REF','6':'VS'}
    assert {r['Pin']:r['Pin_Function'] for r in net if r['RefDes']=='U7_WIN'} == {
        '1':'OUTA','2':'INA-','3':'INA+','4':'VEE','5':'INB+','6':'INB-','7':'OUTB','8':'VCC','EP':'Thermal pad'}
    expected={('U7_INA','1'):'V_INA_OUT',('U7_INA','2'):'GND',
              ('U7_INA','3'):'LED_2V8',('U7_INA','4'):'ISENSE_N',
              ('U7_INA','5'):'GND',('U7_INA','6'):'3V3_SYS',
              ('U7_WIN','2'):'PRIV_VTH_L',('U7_WIN','3'):'V_INA_OUT',
              ('U7_WIN','5'):'PRIV_VTH_H',('U7_WIN','6'):'V_INA_OUT',
              ('U7_WIN','1'):'PRIV_WINDOW_OK',('U7_WIN','7'):'PRIV_WINDOW_OK',
              ('U7_WIN','4'):'GND',('U7_WIN','8'):'3V3_SYS',('U7_WIN','EP'):'GND',
              ('R_PRIV_PU','1'):'PRIV_WINDOW_OK',('R_PRIV_PU','2'):'V_INA_OUT',
              ('R_PRIV_RC','1'):'PRIV_WINDOW_OK',('R_PRIV_RC','2'):'PRIV_WINDOW_OK_F',
              ('R_WIN_TOP','1'):'3V3_SYS',('R_WIN_TOP','2'):'PRIV_VTH_H',
              ('R_WIN_MID','1'):'PRIV_VTH_H',('R_WIN_MID','2'):'PRIV_VTH_L',
              ('R_WIN_BOT','1'):'PRIV_VTH_L',('R_WIN_BOT','2'):'GND',
              ('C_PRIV_RC','1'):'PRIV_WINDOW_OK_F',('C_PRIV_RC','2'):'GND'}
    for k,n in expected.items():assert idx[k]['Net']==n,(k,idx[k]['Net'],n)
    for ref,val in [('R_WIN_TOP','33.2k 1%'),('R_WIN_MID','32.4k 1%'),
                    ('R_WIN_BOT','32.4k 1%'),('R_PRIV_RC','1k 1%')]:
        assert all(idx[ref,p]['Pin_Function']==val for p in ['1','2'])
    lo=3.3*32400/(33200+32400+32400)
    hi=3.3*(32400+32400)/(33200+32400+32400)
    outputs=[]
    for value in [0,0.5,1.6,2.5,3.3]:
        # Compare voltages by actual input net mapping; open drain high means released.
        volt={'PRIV_VTH_L':lo,'PRIV_VTH_H':hi,'V_INA_OUT':value}
        a=volt[idx['U7_WIN','3']['Net']]>volt[idx['U7_WIN','2']['Net']]
        b=volt[idx['U7_WIN','5']['Net']]>volt[idx['U7_WIN','6']['Net']]
        outputs.append(a and b)
    assert outputs==[False,False,True,False,False],outputs
    return {'status':'PASS_STATIC_ONLY','ina_physical_pins':6,'comparator_physical_pins_with_ep':9,
            'nominal_window_v':[lo,hi],'nominal_local_discharge_tau_ms':1.0,
            'nominal_pullup_charge_tau_ms':11.0,'physical_fault_verification':False}
