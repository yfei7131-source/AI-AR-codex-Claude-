"""Vendor checked Rev D1 audio/translator corrections; source-only, NOT FOR FAB.

Called after recovered Rev D1 migration. Mutates NETLIST/BOM lists in place.
See AUDIO_TRANSLATOR_SOURCE_REVIEW.md for evidence and remaining verification.
"""

RJW_PINS = {
    '1': 'DIR1', '2': 'A1', '3': 'A2', '4': 'A3', '5': 'A4',
    '6': 'A5', '7': 'A6', '8': 'A7', '9': 'A8', '10': 'DIR2',
    '11': 'GND', '12': 'GND', '13': 'B8', '14': 'B7', '15': 'B6',
    '16': 'B5', '17': 'B4', '18': 'B3', '19': 'B2', '20': 'B1',
    '21': 'OE', '22': 'VCCB', '23': 'VCCB', '24': 'VCCA',
}
RSV_PINS = {
    '1': '1OE', '2': 'VCCB', '3': 'VCCA', '4': '1DIR', '5': '2DIR',
    '6': '1A1', '7': '1A2', '8': '2A1', '9': '2A2', '10': 'GND',
    '11': 'GND', '12': '2B2', '13': '2B1', '14': '1B2', '15': '1B1', '16': '2OE',
}
DQE_PINS = {'1': 'GND', '2': 'VREF1', '3': 'SCL1', '4': 'SDA1',
            '5': 'SDA2', '6': 'SCL2', '7': 'VREF2', '8': 'EN'}
WLP_PINS = {'A1': 'SD_MODE', 'A2': 'VDD', 'A3': 'OUTP', 'B1': 'DIN',
            'B2': 'GAIN_SLOT', 'B3': 'OUTN', 'C1': 'BCLK', 'C2': 'GND', 'C3': 'LRCLK'}
DPW_PINS = {'1': 'NC', '2': 'A', '3': 'GND', '4': 'Y', '5': 'VCC'}
DSF_SWITCH_PINS = {'1': 'B2', '2': 'GND', '3': 'B1', '4': 'A', '5': 'VCC', '6': 'S'}
PHYSICAL_PINS = {**{r: RJW_PINS for r in ('U8_LS1', 'U8_PDM_LS', 'U8_CAM_ISO1', 'U8_CAM_ISO2')},
                 'U8_AUD_LS2': RSV_PINS, 'U8_LS3': DQE_PINS, 'U8_LS4': DQE_PINS,
                 'U10_AMP_L': WLP_PINS, 'U10_AMP_R': WLP_PINS,
                 'U8_CAM_SCCB_EN': DPW_PINS, 'U10_SD_BUF': DSF_SWITCH_PINS,
                 **{r: {'1': 'DATA', '2': 'VDD', '3': 'CLOCK', '4': 'SELECT', '5': 'GND'}
                    for r in ('MK1_L', 'MK2_C', 'MK3_R')}}


def _row(net, domain, board, ref, pin, function, role, bom, note=''):
    return dict(Net=net, Domain_V=str(domain), Board=board, RefDes=ref,
                Pin=str(pin), Pin_Function=function, Role=role, BOM_Line=bom,
                I_Peak_A='', Note=note)


def _upsert_bom(bom, item, **fields):
    matches = [r for r in bom if r['Item_ID'] == item]
    assert len(matches) <= 1, item
    if matches:
        row = matches[0]
    else:
        row = {k: '' for k in bom[0]}
        row.update(Item_ID=item, Qty='1', Rev_D_Change='new in Rev D1')
        bom.append(row)
    row.update(fields)


def update_translator_banks(tr):
    """Companion update; channel numbers remain logical, NETLIST has physical pins."""
    bank = tr['U8_CAM_ISO2']['banks']['1']['ch']
    assert len(bank) == 4
    bank[3] = [4, 'CAM_DOVDD_1V8', 'CAM_DOVDD_OK_3V3']
    tr['U8_CAM_ISO2']['rev_d1_note'] = (
        'A4 senses local VCCA; B4 has 10k pulldown and drives U8_CAM_SCCB_EN. '
        'Power-off Ioff plus explicit EN clamp; PCA9306 VREF1=0 alone is not isolation.')
    for ref in tr:
        if isinstance(tr[ref], dict) and ref.startswith('U8_'):
            tr[ref]['physical_pin_source'] = 'AUDIO_TRANSLATOR_SOURCE_REVIEW.md; NETLIST physical pin IDs'
            for group in tr[ref].get('banks', {}).values():
                for channel in group.get('ch', []):
                    for side in (1, 2):
                        if channel[side].startswith('TIE_GND_'):
                            channel[side] = 'GND'


def apply_audio_translator_corrections(net, bom):
    left, bridge, right = 'M-MAIN-L', 'M-OPT-BRIDGE', 'M-AUD-R'
    item = 'BOM-D1-AT03'

    def put(n, v, bd, ref, pin, fn, role='PASSIVE', line=item, note=''):
        net[:] = [r for r in net if (r['RefDes'], r['Pin']) != (ref, str(pin))]
        net.append(_row(n, v, bd, ref, pin, fn, role, line, note))

    def passive(ref, value, a, b, bd, va, vb=0, role='PASSIVE', note=''):
        put(a, va, bd, ref, '1', value, role, note=note)
        put(b, vb, bd, ref, '2', value, note=note)

    # The recovered mapping is vendor-correct. Assert complete physical identity,
    # do not mask a mapping failure with duplicate symbolic rows.
    for ref in ('U8_LS1', 'U8_PDM_LS', 'U8_CAM_ISO1', 'U8_CAM_ISO2', 'U8_AUD_LS2',
                'U8_LS3', 'U8_LS4', 'U10_AMP_L', 'U10_AMP_R'):
        rows = [r for r in net if r['RefDes'] == ref]
        expected = PHYSICAL_PINS[ref]
        assert {r['Pin'] for r in rows} == set(expected), (ref, 'physical pin coverage')
        assert len(rows) == len(expected), (ref, 'duplicate pin')
        for row in rows:
            row['Pin_Function'] = expected[row['Pin']]
            if row['Net'].startswith('TIE_GND_'):
                row.update(Net='GND', Domain_V='0', Role='TIE')
                row['Note'] += '; actual ground net, not an unconnected alias'
            if row['Net'] == 'GND':
                row['Domain_V'] = '0'

    # Explicit supply bypass; pins 22+23 share one tightly local VCCB capacitor.
    for ref, a, b in (
        ('U8_LS1', '3V3_SYS', '1V8_FPGA_IO'),
        ('U8_PDM_LS', '1V8_SYS', '3V3_SYS'),
        ('U8_CAM_ISO1', 'CAM_DOVDD_1V8', '3V3_SYS'),
        ('U8_CAM_ISO2', 'CAM_DOVDD_1V8', '3V3_SYS'),
        ('U8_AUD_LS2', '1V8_SYS', '3V3_SYS'),
    ):
        for suffix, rail in (('A', a), ('B', b)):
            passive('C_' + ref + '_' + suffix, '100nF X7R 6.3V 0201', rail, 'GND', left,
                    3.3 if rail == '3V3_SYS' else 1.8, note='TI power-supply recommendations: nearest VCC/GND pins')
    # Missing second terminals in Rev D were descriptions, not electrical edges.
    for ref in ('R_LS1_A4', 'R_LS1_B4'):
        row = next(r for r in net if r['RefDes'] == ref and r['Pin'] == '1')
        put('GND', 0, left, ref, '2', '100k 1%', line=row['BOM_Line'])

    # Mixed-rail shared PDM bus can feed an unpowered bridge microphone. All
    # microphones now use the same always-on 1V8_SYS; clock-off is the sleep mode.
    for row in net:
        if row['RefDes'] == 'MK2_C' and row['Pin'] in ('2', '4'):
            row.update(Net='1V8_SYS', Domain_V='1.8')
            row['Note'] = 'Rev D1: common PDM supply; do not use delayed FPGA rail'
        if row['RefDes'] == 'J_BRIDGE_IN' and row['Pin'] in ('P4', 'P5'):
            row['Note'] = 'Rev D1: connect 1V8_SYS locally for bridge microphone (no longer NC_TRUNK_PASS)'
    for ref, bd in (('MK1_L', left), ('MK2_C', bridge), ('MK3_R', right)):
        passive('C_' + ref, '100nF X7R 6.3V 0201', '1V8_SYS', 'GND', bd, 1.8,
                note='Infineon IM69D130 Table4/Figure10: close to pin2')

    # Camera PCA9306: merely removing VREF1 does not force EN low. Reuse the
    # spare A4->B4 channel as a rail detector with defined OFF state, then clamp
    # EN+VREF2 with a non-inverting open-drain buffer powered by the same 3V3 bus.
    put('CAM_DOVDD_1V8', 1.8, left, 'U8_CAM_ISO2', '5', 'A4', 'RCV', 'BOM-18',
        'Rev D1: VCCA rail-sense input; not a spare tied-low channel')
    put('CAM_DOVDD_OK_3V3', 3.3, left, 'U8_CAM_ISO2', '17', 'B4', 'DRV', 'BOM-18',
        'Hi-Z below VCCA 100mV; R_CAM_DOVDD_OK_PD defines OFF low')
    passive('R_CAM_DOVDD_OK_PD', '10k 1%', 'CAM_DOVDD_OK_3V3', 'GND', left, 3.3,
            role='PULLDOWN', note='10k*2uA worst-case AXC Ioff =20mV; buffer input leakage <=5uA adds50mV')
    passive('R_CAM_DOVDD_BLEED', '100k 1%', 'CAM_DOVDD_1V8', 'GND', left, 1.8,
            role='PULLDOWN', note='defined OFF rail; PCA9306 bias leakage sink per SCPS113O 8.1.7')
    for pin, fn, n, v, role in (
        ('1', 'NC', 'NC_CAM_SCCB_EN_1', 0, 'NC'),
        ('2', 'A', 'CAM_DOVDD_OK_3V3', 3.3, 'RCV'),
        ('3', 'GND', 'GND', 0, 'SINK'),
        ('4', 'Y', 'LS4_VREF2_EN', 2.4, 'DRV_OD'),
        ('5', 'VCC', '3V3_SYS', 3.3, 'SINK'),
    ):
        put(n, v, left, 'U8_CAM_SCCB_EN', pin, fn, role, 'BOM-D1-AT01',
            'SN74LVC1G07DPWR: A low forces PCA9306 EN low; A high releases the 200k bias')
    passive('C_CAM_SCCB_EN', '100nF X7R 6.3V 0201', '3V3_SYS', 'GND', left, 3.3)
    for row in net:
        if row['RefDes'] == 'U8_LS4' and row['Pin'] in ('2', '7', '8'):
            row['Note'] = 'Explicit U8_CAM_SCCB_EN clamp required; VREF1=0 alone is NOT isolation'
        if row['Net'] in ('LS3_VREF2_EN', 'LS4_VREF2_EN'):
            row['Domain_V'] = '2.4' # self-biased ~VREF1+Vth, not a hard 3.3-V supply
    passive('R_LS3_VREF_BLEED', '100k 1%', '1V8_SYS', 'GND', left, 1.8,
            role='PULLDOWN', note='PCA9306 8.1.7 bias leakage path; about32uW nominal')

    # nRF GPIO VOH=VDD-0.4 does not prove >1.5V left-channel selection. An SPDT
    # selects actual GND/1V8_SYS locally, avoiding the generic logic VOL=.1V
    # limit which does not prove <MAX98357 B0min=.08V shutdown. No extra contact.
    for row in net:
        if row['RefDes'] == 'U11_BLE' and row['Net'] == 'AMP_SD_MODE_1V8':
            row['Net'] = 'AMP_SD_REQ_1V8'
            row['Note'] += '; local U10_SD_BUF SPDT selects GND or 1V8_SYS'
    for pin, fn, n, v, role in (
        ('1', 'B2', '1V8_SYS', 1.8, 'PASSIVE'),
        ('2', 'GND', 'GND', 0, 'SINK'), ('3', 'B1', 'GND', 0, 'PASSIVE'),
        ('4', 'A', 'AMP_SD_MODE_1V8', 1.8, 'DRV'),
        ('5', 'VCC', '1V8_SYS', 1.8, 'SINK'),
        ('6', 'S', 'AMP_SD_REQ_1V8', 1.8, 'RCV'),
    ):
        put(n, v, right, 'U10_SD_BUF', pin, fn, role, 'BOM-D1-AT02',
            'SN74LVC1G3157DSFR SPDT; S=0 connects A toGND; S=1 connects A to1V8_SYS; conservative140ohm full-range bound')
    passive('R_AMP_REQ_PD', '47k 1%', 'AMP_SD_REQ_1V8', 'GND', right, 1.8,
            role='PULLDOWN', note='defined reset OFF; <=2uA input leakage creates<=95mV')
    passive('C_AMP_SD_BUF', '100nF X7R 6.3V 0201', '1V8_SYS', 'GND', right, 1.8)
    for ref, bd, rail in (('U10_AMP_L', left, 'VSYS'), ('U10_AMP_R', right, 'VBAT_R_RET')):
        passive('C_' + ref + '_HF', '100nF X7R 10V 0201', rail, 'GND', bd, 4.5,
                note='ADI supply input p33: directly at A2/C2')
        passive('C_' + ref + '_BULK', '10uF X5R 10V 0402', rail, 'GND', bd, 4.5,
                note='check effective capacitance at actual DC bias and local pulse load')
    for name in ('I2S_BCLK_1V8', 'I2S_LRCLK_1V8', 'I2S_AMP_DIN_1V8'):
        passive('R_IDLE_' + name, '100k 1%', name, 'GND', right, 1.8, role='PULLDOWN',
                note='defined I2S idle while nRF pins are inputs; master remains nRF only')

    for bid in ('BOM-14', 'BOM-34', 'BOM-39'):
        row = next(r for r in bom if r['Item_ID'] == bid)
        row['Datasheet_URL'] = 'https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf'
        row['Verification_Status'] = 'SOURCE_CHECKED_D1; IM69D130 v1.0 pp7-12; vendor lists not-for-new-design'
        row['Key_Electrical_Specs'] = '1 DATA,2 VDD=1V8_SYS,3 CLOCK,4 SELECT (L/R opposite on D0),5 GND;100nF local;3.072MHz duty48..52%;13ns rise/fall; clock-off low <=1uA'
    for bid in ('BOM-04', 'BOM-38'):
        row = next(r for r in bom if r['Item_ID'] == bid)
        row['Rev_D1_Change'] += '; SD_MODE now buffered by U10_SD_BUF; local 100nF+10uF explicit'
        row['Verification_Status'] = 'SOURCE_CHECKED_D1 ADI Rev13 pp7,15,17,33; not physical verification'
    row = next(r for r in bom if r['Item_ID'] == 'BOM-48')
    row['Rev_D1_Change'] += '; VREF1=0 is not sufficient: explicit rail detector and EN clamp added'
    row['Key_Electrical_Specs'] = 'PCA9306DQER physical1..8; EN/VREF2 joined,200k to3V3_SYS; U8_CAM_SCCB_EN pulls common node low when DOVDD off;4.7k camera-side pulls toDOVDD'
    gate_common = dict(Side='BOTTOM', Center_X_mm='TBD', Center_Y_mm='TBD',
                       Body_Width_X_mm='0.80', Body_Length_Y_mm='0.80', Body_Height_Z_mm='0.40',
                       Pad_Pitch_mm='0.50', Manufacturer='Texas Instruments',
                       Package_Footprint='DPW0005A X2SON-5 0.8x0.8mm; max height0.4mm; pin1 NC',
                       Unit_Mass_g='0.001', Verification_Status='SOURCE_CHECKED_D1; mass estimate, placement unverified')
    _upsert_bom(bom, 'BOM-D1-AT01', **gate_common, RefDes='U8_CAM_SCCB_EN', Board_Zone=left,
                Category='Camera_SCCB_OFF_Clamp', MPN='SN74LVC1G07DPWR',
                Key_Electrical_Specs='VCC=3V3_SYS;2A=CAM_DOVDD_OK_3V3;4Y(open-drain)=LS4_VREF2_EN;3GND;5VCC;1NC',
                Datasheet_URL='https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf',
                Rev_D1_Change='Explicit PCA9306 OFF clamp; reuse CAM_ISO2 channel4; do not drive EN high directly')
    switch_common = dict(gate_common)
    switch_common.update(Body_Width_X_mm='1.00', Body_Length_Y_mm='1.00',
                         Body_Height_Z_mm='0.40', Pad_Pitch_mm='0.35',
                         Package_Footprint='DSF0006A X2SON-6 1x1mm;0.35mm pitch;maxheight0.4mm')
    _upsert_bom(bom, 'BOM-D1-AT02', **switch_common, RefDes='U10_SD_BUF', Board_Zone=right,
                Category='Audio_SD_Mode_Rail_Selector', MPN='SN74LVC1G3157DSFR',
                Key_Electrical_Specs='1B2=1V8_SYS;2GND;3B1=GND;4A=AMP_SD_MODE_1V8;5VCC=1V8_SYS;6S=AMP_SD_REQ_1V8;47k S pulldown',
                Datasheet_URL='https://www.ti.com/lit/ds/symlink/sn74lvc1g3157.pdf',
                Rev_D1_Change='SPDT selects physicalGND/1V8_SYS for MAX98357A mode; resolves genericVOL0.1V vsB0min0.08V; retain69.8k right resistor')
    refs = sorted({r['RefDes'] for r in net if r['BOM_Line'] == item})
    _upsert_bom(bom, item, RefDes=';'.join(refs), Board_Zone='M-MAIN-L;M-OPT-BRIDGE;M-AUD-R',
                Side='BOTH', Category='Explicit_Audio_Translator_Passives', MPN='0201 R/C + two0402 10uF capacitors; exact MPNs require bias/assembly qualification',
                Manufacturer='TBD', Package_Footprint='0201/0402; see each NETLIST RefDes for value and node pair',
                Unit_Mass_g='0.008', Verification_Status='DESIGN_ESTIMATE_D1; cluster allowance, not measured',
                Key_Electrical_Specs='Explicit translator decoupling, mic bypass, amp bypass, bias bleeds and boot pulls; no new allowance claimed as measured mass',
                Rev_D1_Change='Replaces descriptive-only peripheral notes with two-terminal circuit edges')
    verify_audio_translators(net)


def verify_audio_translators(net):
    """Topology/identity assertions only, not analog or board validation."""
    idx = {(r['RefDes'], r['Pin']): r for r in net}
    for ref, pins in PHYSICAL_PINS.items():
        rows = [r for r in net if r['RefDes'] == ref]
        assert len(rows) == len(pins), (ref, len(rows), len(pins))
        assert {r['Pin'] for r in rows} == set(pins), ref
        assert all(idx[ref, p]['Pin_Function'] == fn for p, fn in pins.items()), ref
    assert idx['U8_CAM_ISO2', '5']['Net'] == 'CAM_DOVDD_1V8'
    assert idx['U8_CAM_ISO2', '17']['Net'] == idx['U8_CAM_SCCB_EN', '2']['Net']
    assert idx['U8_CAM_SCCB_EN', '4']['Net'] == idx['U8_LS4', '7']['Net'] == idx['U8_LS4', '8']['Net']
    assert idx['U8_CAM_SCCB_EN', '5']['Net'] == '3V3_SYS'
    assert idx['U10_SD_BUF', '4']['Net'] == idx['U10_AMP_L', 'A1']['Net'] == 'AMP_SD_MODE_1V8'
    assert idx['U10_SD_BUF', '1']['Net'] == idx['U10_SD_BUF', '5']['Net'] == '1V8_SYS'
    assert idx['U10_SD_BUF', '2']['Net'] == idx['U10_SD_BUF', '3']['Net'] == 'GND'
    assert idx['U10_SD_BUF', '6']['Net'] == 'AMP_SD_REQ_1V8'
    assert all(idx[r, '2']['Net'] == '1V8_SYS' for r in ('MK1_L', 'MK2_C', 'MK3_R'))
    for ref, dir1, dir2 in (
        ('U8_LS1', 'QSPI_DIR1_EN', '3V3_SYS'),
        ('U8_PDM_LS', '1V8_SYS', 'GND'),
        ('U8_CAM_ISO1', 'CAM_DOVDD_1V8', 'CAM_DOVDD_1V8'),
        ('U8_CAM_ISO2', 'CAM_DOVDD_1V8', 'GND'),
    ):
        assert idx[ref, '1']['Net'] == dir1 and idx[ref, '10']['Net'] == dir2, ref
        assert idx[ref, '21']['Net'] == 'GND', ref
    assert idx['U8_AUD_LS2', '1']['Net'] == idx['U8_AUD_LS2', '16']['Net'] == 'GND'
    assert idx['R_SDR', '1']['Net'] == 'AMP_SD_MODE_1V8'
    assert idx['R_SDR', '2']['Net'] == idx['U10_AMP_R', 'A1']['Net'] == 'AMP_R_SD_MODE'
    assert '69.8k' in idx['R_SDR', '1']['Pin_Function']
    for ref in ('MK1_L', 'MK2_C', 'MK3_R'):
        assert idx['C_' + ref, '1']['Net'] == '1V8_SYS'
        assert idx['C_' + ref, '2']['Net'] == 'GND'
    for ref in ('U10_AMP_L', 'U10_AMP_R'):
        for suffix in ('HF', 'BULK'):
            assert idx['C_' + ref + '_' + suffix, '1']['Net'] == idx[ref, 'A2']['Net']
            assert idx['C_' + ref + '_' + suffix, '2']['Net'] == 'GND'
    # TI SCES424O pp6-8: use conservative140ohm full-signal-range bound at1.65V,
    # <=1uA off +<=1uA on leakage. Source-derived settled DC bounds only.
    low = 1.8 * .98 - 35e-6 * 140
    high = 1.8 * 1.02
    right_min = low * 92 / (92 + 69.8 * 1.01)
    right_max = high * 108 / (108 + 69.8 * .99)
    off_max = 2e-6 * 140
    assert low > 1.5 and right_min > .825 and right_max < 1.245 and off_max < .08
    assert 1.8*.98 - .4 > .75*1.8*.98 # Nordic source limit vs SPDT VIH
    assert .4 < .25*1.8*.98          # Nordic source limit vs SPDT VIL
    return dict(left_min_V=round(low, 6), right_min_V=round(right_min, 6),
                right_max_V=round(right_max, 6), off_max_local_V=off_max,
                rail_tolerance_assumption_percent=2,
                scope='source topology and DC high-level selection; OFF transients require bench validation')
