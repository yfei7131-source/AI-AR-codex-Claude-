"""Rev D1 primary-datasheet power corrections. NOT FOR FAB.

Called after the recovered Claude migration. Mutates net and bom in place.
Pin numbers are for the exact packages here, never symbols from another variant.
"""


def apply_power_corrections(net, bom):
    fields = list(bom[0])
    by = {r['Item_ID']: r for r in bom}
    L, R, B = 'M-MAIN-L', 'M-AUD-R', 'M-OPT-BRIDGE'

    def row(n, v, board, ref, pin, fn, role, bid, note='', ipk=''):
        return dict(Net=n, Domain_V=str(v), Board=board, RefDes=ref, Pin=str(pin),
                    Pin_Function=fn, Role=role, BOM_Line=bid, I_Peak_A=str(ipk), Note=note)

    def part(ref, board, value, category='Passive', mass='0.001', footprint='0201 (0.6x0.3 mm)',
             w='0.6', h='0.3', z='0.3', source='', status='SELECTED_VALUE_MPN_OPEN'):
        bid = 'BOM-D1-PWR-' + ref
        if bid in by:
            return bid
        p = {k: '' for k in fields}
        p.update(Item_ID=bid, RefDes=ref, Board_Zone=board, Side='TBD_LAYOUT',
                 Body_Width_X_mm=w, Body_Length_Y_mm=h, Body_Height_Z_mm=z,
                 Category=category, MPN=value, Manufacturer='TBD', Package_Footprint=footprint,
                 Key_Electrical_Specs=value, Qty='1', Unit_Mass_g=mass,
                 Verification_Status=status + '; mass estimated, layout not verified', Datasheet_URL=source,
                 Rev_D1_Change='Explicit Rev D1 power peripheral; both terminals recorded; placement OPEN')
        bom.append(p); by[bid] = p
        return bid

    newrefs = {'U4_OR', 'Q_CHG_ISO_R', 'Q_CHG_MUTE_R', 'R_ISO_GATE', 'R_ISO_PD',
               'R_MUTE_GATE', 'R_MUTE_PD', 'BAT_L', 'BAT_R'}
    caps = [
        ('C_CHG_L_IN', L, 'VBUS_5V', 5, '1uF 25V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_CHG_L_SYS', L, 'VOUT_L_PPATH', 4.5, '10uF 25V X5R; effective >1uF', '0603 (1.6x0.8 mm)', '0.006'),
        ('C_CHG_L_BAT', L, 'VBAT_L', 4.2, '1uF 10V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_CHG_R_IN', R, 'VBUS_5V', 5, '1uF 25V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_CHG_R_OUT', R, 'VBAT_R_RET', 4.2, '1uF 10V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_OR_IN1', L, 'VOUT_L_PPATH', 4.5, '1uF 10V X7R', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_OR_IN2', L, 'VBAT_R_ISOLATED', 4.2, '1uF 10V X7R', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_OR_OUT', L, 'VSYS', 4.5, '1uF 10V X7R', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_BB_IN', L, 'VSYS', 4.5, '10uF 10V X5R; effective >=4uF', '0603 (1.6x0.8 mm)', '0.006'),
        ('C_BB_OUT', L, '3V3_SYS', 3.3, '22uF 10V X5R; effective >=7uF', '0603 (1.6x0.8 mm)', '0.006'),
        ('C_BK_IN', L, 'VSYS', 4.5, '4.7uF 10V X5R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
        ('C_BK_OUT', L, '1V8_SYS', 1.8, '10uF 6.3V X5R; effective 3..40uF', '0402 (1.0x0.5 mm)', '0.003'),
    ]
    # Each LDO has local input/output capacitance. These do not replace remote bulk capacitors.
    for tag, board, vin, vout, voltage in [
        ('1V2F', B, 'VSYS', '1V2_FPGA_CORE', 1.2),
        ('1V8F', B, 'VSYS', '1V8_FPGA_IO', 1.8),
        ('OPT', B, 'VSYS', 'AVDD_OPT_BIAS', 'BLOCKED_VENDOR'),
        ('LED', L, '3V3_SYS', 'LED_2V8', 2.8),
        ('DOVDD', L, '3V3_SYS', 'CAM_DOVDD_1V8', 1.8),
        ('DVDD', L, '3V3_SYS', 'CAM_DVDD_1V2', 1.2),
        ('AVDD', L, '3V3_SYS', 'CAM_AVDD_2V8', 2.8),
    ]:
        caps.extend([(f'C_LDO_{tag}_IN', board, vin, 4.5 if vin == 'VSYS' else 3.3,
                      '1uF 10V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003'),
                     (f'C_LDO_{tag}_OUT', board, vout, voltage,
                      '1uF 10V X7R; effective >=1uF', '0402 (1.0x0.5 mm)', '0.003')])
    newrefs.update(x[0] for x in caps)
    net[:] = [r for r in net if r['RefDes'] not in newrefs]

    # SLVSG04 Table 5-1. DRL is eight pins, not SOT-563-6.
    orpins = [('1', 'GND', 'GND', 0, 'SINK'), ('2', 'VOUT', 'VSYS', 4.5, 'SRC'),
              ('3', 'VIN1', 'VOUT_L_PPATH', 4.5, 'SINK'), ('4', '/ON', 'GND', 0, 'TIE'),
              ('5', 'GND', 'GND', 0, 'SINK'), ('6', 'VIN2', 'VBAT_R_ISOLATED', 4.2, 'SINK'),
              ('7', 'VOUT', 'VSYS', 4.5, 'SRC'), ('8', 'ST', 'NC_OR_ST', 0, 'NC')]
    for pin, fn, n, v, role in orpins:
        net.append(row(n, v, L, 'U4_OR', pin, fn, role, 'BOM-21',
                       'SLVSG04 Table 5-1; /ON tied GND, ST unused'))
    by['BOM-21'].update(Package_Footprint='SOT-8 DRL (2.1x1.6 mm, 0.5 mm pitch)',
                        Key_Electrical_Specs='LM66200 dual ideal diode; RON 40mOhm typical; 1/5 GND, 2/7 VOUT, 3 VIN1, 4 /ON=GND, 6 VIN2, 8 ST NC',
                        Verification_Status='PINMAP_VERIFIED_D1 SLVSG04 Table 5-1; PCB and load-step verification OPEN')

    # Correct the PG/STAT transposition in the interrupted migration.
    for r in net:
        if r['RefDes'] == 'U3_R' and r['Pin'] in ('5', '6'):
            r.update(Pin_Function='STAT' if r['Pin'] == '5' else '/PG',
                     Net='NC_CHG_R_STAT' if r['Pin'] == '5' else 'NC_CHG_R_PG')
        if r['RefDes'] == 'U4_1V8' and r['Pin'] == '5':
            r.update(Note='SLVSEC6D Table 1: TPS62840DLC 1.8V requires VSET to GND via 0-ohm link', Domain_V='0')
        if r['RefDes'] == 'R_VSET_1V8':
            r.update(Pin_Function='0 ohm (1.8V VSET strap)', Domain_V='0')
        if r['RefDes'] == 'U4_BB' and r['Pin'] == 'D1':
            r['Domain_V'] = '0.5'
        if r['RefDes'] == 'U4_1V8' and r['Pin'] in ('3', '6'):
            r['Domain_V'] = '0'
        if r['RefDes'] == 'U6_OPT_AVDD':
            r['Note'] += '; AVDD voltage and populated MPN remain BLK-JBD-04; 2.8V is conditional only'

    # A valid USB charge input exceeds the cell voltage, so this P-channel switch
    # disconnects the right battery from the system load even if left SYS droops.
    # Source=cell, drain=OR input: body diode blocks cell-to-system while OFF.
    qiso = part('Q_CHG_ISO_R', L, 'PMV65XP', 'P_MOS_Charger_Load_Isolation', '0.008',
                'SOT23 (1 G, 2 S, 3 D)', '2.9', '1.3', '1.1',
                'https://assets.nexperia.com/documents/data-sheet/PMV65XP.pdf', 'PINMAP_VERIFIED_CIRCUIT_UNMEASURED')
    qm = part('Q_CHG_MUTE_R', R, '2N7002', 'N_MOS_USB_Audio_Mute', '0.008',
              'SOT23 (1 G, 2 S, 3 D)', '2.9', '1.3', '1.1',
              'https://assets.nexperia.com/documents/data-sheet/2N7002.pdf', 'PINMAP_VERIFIED_CIRCUIT_UNMEASURED')
    net.extend([row('CHG_ISO_GATE', 5, L, 'Q_CHG_ISO_R', 1, 'G', 'RCV', qiso),
                row('VBAT_R_RET', 4.2, L, 'Q_CHG_ISO_R', 2, 'S', 'PASSIVE', qiso),
                row('VBAT_R_ISOLATED', 4.2, L, 'Q_CHG_ISO_R', 3, 'D', 'PASSIVE', qiso),
                row('CHG_MUTE_GATE', 5, R, 'Q_CHG_MUTE_R', 1, 'G', 'RCV', qm),
                row('GND', 0, R, 'Q_CHG_MUTE_R', 2, 'S', 'PASSIVE', qm),
                row('AMP_R_SD_MODE', 1.06, R, 'Q_CHG_MUTE_R', 3, 'D', 'DRV_OD', qm,
                    'VBUS present forces right MAX98357A shutdown; 69.8k limits nRF GPIO current')])
    for ref, board, n1, n2, val in [
        ('R_ISO_GATE', L, 'VBUS_5V', 'CHG_ISO_GATE', '100 ohm 1%'),
        ('R_ISO_PD', L, 'CHG_ISO_GATE', 'GND', '100k 1%'),
        ('R_MUTE_GATE', R, 'VBUS_5V', 'CHG_MUTE_GATE', '100 ohm 1%'),
        ('R_MUTE_PD', R, 'CHG_MUTE_GATE', 'GND', '100k 1%')]:
        bid = part(ref, board, val)
        net.extend([row(n1, 5, board, ref, 1, val, 'PASSIVE', bid),
                    row(n2, 0 if n2 == 'GND' else 5, board, ref, 2, val, 'PASSIVE', bid)])

    for ref, board, n, voltage, val, fp, mass in caps:
        bid = part(ref, board, val, 'Capacitor_Power_Decoupling', mass, fp,
                   '1.6' if '0603' in fp else '1.0', '0.8' if '0603' in fp else '0.5',
                   '0.9' if '0603' in fp else '0.65')
        net.extend([row(n, voltage, board, ref, 1, val, 'PASSIVE', bid, 'place at corresponding IC pins; DC-bias curve approval OPEN'),
                    row('GND', 0, board, ref, 2, val, 'PASSIVE', bid)])

    # The old BOM-59 lump is now itemized; retaining its mass would double count.
    if 'BOM-59' in by:
        by['BOM-59'].update(Qty='0', Unit_Mass_g='0', Verification_Status='SUPERSEDED_BY_ITEMIZED_PWR_CAPACITORS',
                            Rev_D1_Change='C_CHG_L_IN/SYS/BAT itemized; do not populate this cluster separately')
    by['BOM-20'].update(Pad_Pitch_mm='0.40', Body_Width_X_mm='1.04', Body_Length_Y_mm='1.59',
                        Body_Height_Z_mm='0.50', Package_Footprint='DSBGA-8 YBG0008-C01; 0.4 mm pitch; 1.610x1.060x0.5 mm max',
                        Key_Electrical_Specs='BQ25180: A1 /INT NC, A2 IN, B1 SCL, B2 SYS, C1 SDA, C2 BAT, D1 TS/MR, D2 GND; I2C 0x6A. Candidate 110mAh pack profile: VBAT_CTRL 0x46 (4.20V), ICHG_CTRL 0x20 (50mA), SYS_REG 0x40 (4.5V); TS protection retained, watchdog policy in CHARGER_CONFIGURATION_REV_D1.json. Pack charge rating NOT verified.',
                        Verification_Status='PINMAP_VERIFIED_D1 SLUSE99C Table6-1; YBG0008-C01 drawing 4229296/A; PACK_QUALIFICATION_OPEN')
    by['BOM-37'].update(Key_Electrical_Specs='BQ25170DSGR: 1 IN, 2 ISET (5.49k), 3 TS, 4 GND, 5 STAT NC, 6 /PG NC, 7 VSET (27k), 8 OUT, EP GND. Candidate110mAh charge: nominal54.64mA, 4.20V; pack rating and NTC must be approved. USB isolates OUT from system and mutes right amplifier.',
                        Rev_D1_Change='Physical pins verified:1IN,2ISET,3TS,4GND,5STAT,6/PG,7VSET,8OUT,EPGND. Corrected interrupted migration STAT/PG transposition;5.49kISET and27kVSET retained for110mAh candidate pending pack approval.',
                        Verification_Status='PINMAP_VERIFIED_D1 SLUSDJ8A Table5-1; charge transient/pack qualification OPEN')
    by['BOM-06'].update(Body_Height_Z_mm='0.625', Pad_Pitch_mm='0.40',
                        Package_Footprint='DSBGA-15 YFF0015; body max2.285x1.374x0.625mm, 0.4mm pitch',
                        Key_Electrical_Specs='TPS63805YFFR: 0.5V FB, Rtop560k/Rbottom100k =>3.300V nominal; 0.47uH effective0.37..0.57uH; CIN effective>=4uF, COUT effective>=7uF at3.3V. Current-limited fault inductor qualification OPEN.')
    by['BOM-07'].update(MPN='MPN_TBD (0.47uH effective0.37..0.57uH over temperature/DC current)',
                        Key_Electrical_Specs='Candidate2016 inductors not qualified. TPS63805 boost switch peak limit up to5.75A; characterize saturation, transient peak and loss; do not assume4.5A Isat is sufficient.',
                        Verification_Status='OPEN_INDUCTOR_LOAD_QUALIFICATION')
    by['BOM-08'].update(Body_Width_X_mm='1.50', Body_Length_Y_mm='2.00', Body_Height_Z_mm='1.00',
                        Package_Footprint='VSON-HR-8 DLC0008B;1.5x2.0mm nominal,1mm max height,0.5mm pitch',
                        Key_Electrical_Specs='TPS62840DLC:1GND,2VIN,3MODE=GND,4EN=VSYS,5VSET=GND via0ohm,6STOP=GND,7SW,8VOS=1V8_SYS;2.2uH (effective1.51..2.9uH); CIN4.7uF,COUT10uF (effective3..40uF).',
                        Verification_Status='PINMAP_VERIFIED_D1 SLVSEC6D pp4-6/Table1; currentDLC0008B envelope used')

    # Mandatory protected-pack boundary, not an invented internal PCM pin map.
    for ref, board, bid, power, ntc in [('BAT_L', L, 'BOM-43', 'VBAT_L', 'NTC_TS_L'),
                                         ('BAT_R', R, 'BOM-44', 'VBAT_R_RET', 'NTC_TS_R')]:
        net.extend([row(power, 4.2, board, ref, 'P+', 'protected pack positive', 'BIDIR', bid,
                        'Required external protected-pack contract; raw cell connection PROHIBITED'),
                    row('GND', 0, board, ref, 'P-', 'protected pack negative', 'BIDIR', bid),
                    row(ntc, 'NTC_ANALOG', board, ref, 'NTC', '10k NTC at cell', 'PASSIVE', bid,
                        '103AT-compatible R/T curve required; curve and exact pack pin order OPEN'),
                    row('GND', 0, board, ref, 'NTC_RETURN', 'NTC return', 'PASSIVE', bid)])
        by[bid]['Key_Electrical_Specs'] += '; MUST be a qualified protected1S pack with independent OVP/UVP/overcurrent/short-circuit PCM and cell-mounted10k NTC. Connector pin order, trip limits, current rating and mass require vendor approval. GRP3911040 is a CELL candidate, not proof of supplied PCM.'
        by[bid]['Verification_Status'] = 'BLOCKED_PROTECTED_PACK_NTC_AND_CURRENT_QUALIFICATION'


def validate_power(net):
    """Independent public-pin-table checks and peripheral continuity checks."""
    idx = {(r['RefDes'], r['Pin']): r for r in net}
    expected = {
        'U3_L': {'A1':'/INT','A2':'IN','B1':'SCL','B2':'SYS','C1':'SDA','C2':'BAT','D1':'TS/MR','D2':'GND'},
        'U3_R': {'1':'IN','2':'ISET','3':'TS','4':'GND','5':'STAT','6':'/PG','7':'VSET','8':'OUT','EP':'Thermal pad'},
        'U4_OR': {'1':'GND','2':'VOUT','3':'VIN1','4':'/ON','5':'GND','6':'VIN2','7':'VOUT','8':'ST'},
        'U4_BB': {'A1':'EN','B1':'MODE','C1':'AGND','D1':'FB','E1':'PG','A2':'VIN','A3':'VIN','B2':'L1','B3':'L1','C2':'GND','C3':'GND','D2':'L2','D3':'L2','E2':'VOUT','E3':'VOUT'},
        'U4_1V8': {'1':'GND','2':'VIN','3':'MODE','4':'EN','5':'VSET','6':'STOP','7':'SW','8':'VOS'},
    }
    for ref, pins in expected.items():
        actual = {r['Pin']: r['Pin_Function'] for r in net if r['RefDes'] == ref}
        assert actual == pins, (ref, actual, pins)
    assert idx['U4_OR','6']['Net'] == 'VBAT_R_ISOLATED'
    assert idx['Q_CHG_ISO_R','2']['Net'] == 'VBAT_R_RET'
    assert idx['Q_CHG_ISO_R','3']['Net'] == 'VBAT_R_ISOLATED'
    assert idx['Q_CHG_MUTE_R','3']['Net'] == 'AMP_R_SD_MODE'
    assert idx['R_VSET_1V8','2']['Net'] == 'GND'
    assert '0 ohm' in idx['R_VSET_1V8','1']['Pin_Function']
    for r in net:
        if r['BOM_Line'].startswith('BOM-D1-PWR-C_'):
            assert (r['RefDes'], '1') in idx and (r['RefDes'], '2') in idx
            assert idx[r['RefDes'], '2']['Net'] == 'GND'
    return {'pin_tables': len(expected), 'explicit_power_caps': sum(1 for ref,p in idx if ref.startswith('C_') and idx[ref,p]['BOM_Line'].startswith('BOM-D1-PWR-') and p=='1'),
            'status':'PASS_STATIC_ONLY', 'physical_measurements':False}
