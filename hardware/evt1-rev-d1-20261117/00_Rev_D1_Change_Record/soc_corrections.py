"""Physical SoC/peripheral corrections. Pure deterministic in-place migration.

Sources and remaining constraints: SOC_SOURCE_REVIEW.md. No RTL changes.
"""

FIELDS = ('Net','Domain_V','Board','RefDes','Pin','Pin_Function','Role','BOM_Line','I_Peak_A','Note')
NRF_GPIO = {
 'C4':'P0.30','C5':'P0.31','C6':'P1.11','C7':'P1.12','C8':'P1.13','C9':'P1.14','C10':'P1.15',
 'D10':'P1.00','E2':'P0.29','E3':'P0.28','E4':'P1.10','E10':'P1.01','F3':'P1.08',
 'F10':'P0.05','F11':'P0.00/XL1','F12':'P0.01/XL2','G3':'P1.07','G10':'P0.04',
 'G11':'P0.02/NFC1','H1':'P0.27','H2':'P1.09','H3':'P0.23','H10':'P0.06','H12':'P0.03/NFC2',
 'J2':'P0.26','J3':'P1.06','J4':'P0.21','J5':'P0.19','J6':'P0.12','J7':'P0.11',
 'J8':'P0.10','J9':'P0.09','J10':'P0.07','J11':'P1.02','K2':'P0.24','K3':'P1.04',
 'K4':'P0.22','K5':'P0.20','K7':'P0.18','K8':'P0.16','K9':'P0.14','K10':'P0.13',
 'K12':'P1.03','L1':'P0.25','L3':'P1.05','L7':'P0.17','L9':'P0.15','L12':'P0.08'}
NRF_VDD = ('A3','B7','B10','D2','E11','H11','K1','L5','L11')
NRF_GND = ('A5','B2','B9','C2','D12','E5','E6','E7','E8','F5','F6','F7','F8','G6','G7','G8')
NRF_AGND = ('G5','K6','K11')
NRF_ACTIVE = {
 'K5':('I2S_BCLK_1V8','DRV','I2S SCK'), 'K4':('I2S_LRCLK_1V8','DRV','I2S LRCK'),
 'J4':('I2S_AMP_DIN_1V8','DRV','I2S SDOUT'), 'J5':('I2S_S3_DOUT_1V8','RCV','I2S SDIN'),
 'K3':('IPC_NRF_TX_1V8','DRV','UARTE TXD'), 'L3':('IPC_S3_TX_1V8','RCV','UARTE RXD; enable pull-up'),
 'K2':('AMP_SD_MODE_1V8','DRV','amplifier enable/select control')}


def apply_soc_corrections(net, bom):
    """Mutate net and BOM lists after recovered part1/part2 execution."""
    by = {r['Item_ID']:r for r in bom}
    def row(n,bd,ref,p,fn,role,bline,v='1.8',note=''):
        return dict(zip(FIELDS,(n,str(v),bd,ref,str(p),fn,role,bline,'',note)))
    def add(n,bd,ref,p,fn,role,bline,v='1.8',note=''):
        net.append(row(n,bd,ref,p,fn,role,bline,v,note))
    def passive(ref,value,n1,n2,bd,bline,v='1.8',note=''):
        add(n1,bd,ref,'1',value,'PASSIVE',bline,v,note)
        add(n2,bd,ref,'2',value,'PASSIVE',bline,'0' if n2=='GND' else v,note)
    def newbom(i,ref,bd,category,spec,footprint='0201/0402',mass='0.001',qty='1'):
        r={k:'' for k in bom[0]}
        r.update(Item_ID=i,RefDes=ref,Board_Zone=bd,Side='BOTTOM',Qty=qty,Category=category,
                 MPN=spec,Manufacturer='TBD (value/package selected; exact procurement MPN open)',
                 Package_Footprint=footprint,Key_Electrical_Specs=spec,Unit_Mass_g=mass,
                 Verification_Status='SOURCE_VERIFIED_D1; physical layout/MPN qualification open',
                 Rev_D1_Change='Explicit physical component from SoC source review; mass estimate only')
        if i in by: by[i].update(r)
        else: bom.append(r);by[i]=r
    L,A,B='M-MAIN-L','M-AUD-R','M-OPT-BRIDGE'

    # Replace virtual nRF cluster and incomplete SoC rows with Nordic CMAA
    # Reference Layout1.0 Config3, normal voltage, DCDC, noUSB. All95balls.
    net[:]=[r for r in net if r['RefDes'] not in ('U11_BLE','RN_BLE_RF','Y2_BLE','TP_SWD_R')
            and not r['RefDes'].startswith(('NRF_C','NRF_L','NRF_CT','C_IMU_','C_ESP_','R_ESP_'))]
    for ball,fn in NRF_GPIO.items():
        if ball in NRF_ACTIVE:
            n,role,nt=NRF_ACTIVE[ball]
            add(n,A,'U11_BLE',ball,fn,role,'BOM-36',note=nt+'; PSEL assignment; GPIO input disconnected when unused')
        else:
            add('NC_NRF_'+ball,A,'U11_BLE',ball,fn,'NC','BOM-36','0',
                'Unused GPIO; disable input and pulls; LFRC calibrated; NFC disabled for G11/H12')
    for ball in NRF_VDD:
        add('1V8_SYS',A,'U11_BLE',ball,'VDD','SINK','BOM-36',note='normal-voltage supply; local decoupling per Nordic config3')
    add('1V8_SYS',A,'U11_BLE','B12','VDDH','SINK','BOM-36',note='Tied VDD in normal-voltage mode; VREGH disabled automatically')
    for ball in NRF_GND+NRF_AGND:
        add('GND',A,'U11_BLE',ball,'AVSS' if ball in NRF_AGND else 'VSS','SINK','BOM-36','0')
    for ball,fn,n in (
        ('B1','DECRF','NRF_DECR_RF'),('B4','DECR','NRF_DECR_RF'),('B5','DECN','NRF_DECN'),
        ('B8','DECA','NRF_DECA'),('A7','DECD','NRF_DECD'),('B6','DCC','NRF_DCC'),
        ('A9','DCCD','NRF_DCCD'),('A1','XC1','BLE_XC1'),('A2','XC2','BLE_XC2'),('D1','ANT','BLE_RF_ANT')):
        add(n,A,'U11_BLE',ball,fn,'PASSIVE','BOM-36','0' if fn in ('ANT','XC1','XC2') else '1.0',
            'Nordic CMAA config3; DECR and DECRF intentionally share a decoupling node' if fn in ('DECR','DECRF') else '')
    add('GND',A,'U11_BLE','B11','VBUS','TIE','BOM-36','0','USB unused: grounded as Nordic CMAA config3')
    for ball,fn in (('C11','DECUSB'),('A11','D-'),('A12','D+'),('D11','DCCH')):
        add('NC_NRF_'+ball,A,'U11_BLE',ball,fn,'NC','BOM-36','0','USB/VREGH unused; Nordic CMAA config3')
    for ball,fn,n,role in (('F1','SWDIO','BLE_SWDIO','BIDIR'),('F2','SWDCLK','BLE_SWDCLK','RCV'),('G2','nRESET','BLE_NRESET','RCV')):
        add(n,A,'U11_BLE',ball,fn,role,'BOM-36',note='nRESET has internal pull-up' if ball=='G2' else '')
    assert len([r for r in net if r['RefDes']=='U11_BLE'])==95

    # Nordic reference labels C1..C14/L1..L4 retained with NRF_ prefix for traceability.
    for ix,value,n1,n2 in (
       (1,'0.7 pF NP0 +/-0.05 pF','BLE_RF_MID','GND'),
       (2,'1.0 uF X7S +/-10%','1V8_SYS','GND'),
       (3,'1.0 uF X7S +/-10%','NRF_DECR_RF','GND'),
       (4,'2.2 nF X7R +/-10%','NRF_DECR_RF','GND'),
       (5,'1.0 uF X7S +/-10%','NRF_DECD','GND'),
       (6,'100 nF X7S +/-10%','NRF_DECN','GND'),
       (7,'1.0 uF X7S +/-10%','NRF_DECA','GND'),
       (8,'100 nF X7S +/-10%','1V8_SYS','GND'),(9,'100 nF X7S +/-10%','1V8_SYS','GND'),
       (10,'1.0 uF X7S +/-10%','1V8_SYS','GND'),(11,'100 nF X7S +/-10%','1V8_SYS','GND'),
       (12,'100 nF X7S +/-10%','1V8_SYS','GND'),(13,'100 nF X7S +/-10%','1V8_SYS','GND'),
       (14,'1.0 uF X7S +/-10%','1V8_SYS','GND')):
        passive('NRF_C'+str(ix),value,n1,n2,A,'BOM-56',note='Nordic CMAA reference config3; package per source BOM')
    for ix,value,n1,n2 in ((1,'2.2 nH +/-5%','BLE_RF_MID','BLE_RF_ANT'),
                         (2,'2.2 nH +/-5%','BLE_ANT_FEED','BLE_RF_MID'),
                         (3,'10 uH >=50 mA +/-20%','NRF_DECR_RF','NRF_DCC'),
                         (4,'10 uH >=50 mA +/-20%','NRF_DECD','NRF_DCCD')):
        passive('NRF_L'+str(ix),value,n1,n2,A,'BOM-56',note='L1/L2=0201; L3/L4=0603 per Nordic config3; procurement/derating open')
    # Optional antenna-dependent C19 is intentionally not populated; no guessed RF tuning value.
    passive('NRF_CT19','DNP antenna tuning shunt','BLE_ANT_FEED','GND',A,'BOM-56',note='Nordic C19 DNP; antenna qualification/VNA pending')
    for pin,n in (('1','BLE_XC1'),('2','GND'),('3','BLE_XC2'),('4','GND')):
        add(n,A,'Y2_BLE',pin,'32 MHz crystal terminal' if pin in ('1','3') else 'metal case GND','PASSIVE','BOM-55','0',
            'Epson FA-128 pinout; internal nRF HFXO caps selected in firmware before HFXO start')
    for pin,n,fn in (('1','BLE_SWDIO','SWDIO'),('2','BLE_SWDCLK','SWDCLK'),('3','BLE_NRESET','nRESET'),('4','1V8_SYS','VTREF'),('5','GND','GND')):
        add(n,A,'TP_SWD_R',pin,fn,'PASSIVE','BOM-57','0' if n=='GND' else '1.8')
    by['BOM-36'].update(Key_Electrical_Specs='CMAA WLCSP95, all balls explicit; VDD+VDDH=1V8_SYS; Nordic CMAA Config3 DCDC normal voltage/noUSB; DECRF+DECR common; VBUS grounded, DECUSB/DCCH NC. VREGMAIN.DCDCEN=1, VREGRADIO.DCDCEN=1 only after populated LC verification.',
                        Verification_Status='SOURCE_VERIFIED_D1 (Nordic PS pin table3 and official CMAA config3 schematic); firmware/RF/PCB not validated')
    by['BOM-55'].update(MPN='FA-128 32 MHz 8 pF +/-10 ppm initial +/-10 ppm temperature; candidate Q22FA12800025 (ordering suffix/vendor controlled spec pending)',
                        Manufacturer='Epson',Package_Footprint='2016 4pad: 1/3 crystal, 2/4 grounded case',
                        Key_Electrical_Specs='32 MHz, CL=8pF, ESR<=60ohm; nominal +/-21ppm firstyear before loading error. Use internal capacitors calibrated from FICR; final PCB stray/load accuracy and active temperature range require measurement.',
                        Verification_Status='SELECTED_CANDIDATE_D1 (Epson catalog and FA-128 drawing); exact controlled order code/load trim open')
    by['BOM-56'].update(RefDes='NRF_C1..NRF_C14,NRF_L1..NRF_L4,NRF_CT19(DNP)',
                        MPN='Nordic CMAA config3 reference passives; exact procurement MPNs pending',
                        Key_Electrical_Specs='C1 0.7pF; C2/C3/C5/C7/C10/C14 1uF; C4 2.2nF; C6/C8/C9/C11/C12/C13 100nF; L1/L2 2.2nH; L3/L4 10uH50mA; CT19 DNP. Physical pins1/2 explicit.',
                        Unit_Mass_g='0.010',Verification_Status='SOURCE_VERIFIED_D1 values/topology; mass estimate + MPN/layout/RF qualification pending')

    # ESP supply pins: VDD_SPI is a regulated/output supply, not another generic3V3 input.
    old=[]
    for r in net:
        if r['RefDes']=='U1_HOST' and ('Pins ' in r['Pin'] or r['Pin_Function']=='VDD3P3/VDD_SPI/VDDA'):
            continue
        if r['RefDes']=='C_CHIP_PU' and r['Pin']=='2':continue
        if r['RefDes']=='U1_HOST':r['Pin']=r['Pin'].replace('Pin ','')
        old.append(r)
    net[:]=old
    for p,fn in (('2','VDD3P3'),('3','VDD3P3'),('20','VDD3P3_RTC'),('46','VDD3P3_CPU'),('55','VDDA'),('56','VDDA')):
        add('3V3_SYS',L,'U1_HOST',p,fn,'SINK','BOM-02','3.3','SiP3.0..3.6V; integrated local decoupling; external bulk C_ESP_BULK')
    add('ESP_VDD_SPI_3V3',L,'U1_HOST','29','VDD_SPI','SRC','BOM-02','3.3','Internal memory supply output; decouple, do not short to3V3_SYS; strapGPIO45=0 at reset')
    used={r['Pin'] for r in net if r['RefDes']=='U1_HOST'}
    nc={28:'SPICS1/PSRAM_RESERVED',30:'NC',31:'NC',32:'NC',33:'NC',34:'NC',35:'NC',38:'GPIO33',39:'GPIO34',40:'GPIO35',41:'GPIO36',42:'GPIO37',53:'NC',54:'NC'}
    for p,fn in nc.items():
        if str(p) not in used:add('NC_ESP_'+str(p),L,'U1_HOST',p,fn,'NC','BOM-02','0','N8R2:28PSRAM internal; unused GPIO38..42 board NC; N8R8 also internally reservesGPIO33..37')
    add('GND',L,'C_CHIP_PU','2','1 uF','PASSIVE','BOM-24','0','Completes CHIP_PU RC return')
    passive('C_ESP_BULK','22 uF nominal (DCbias qualification pending)','3V3_SYS','GND',L,'BOM-SOC-01','3.3','Espressif peripheral schematic bulk22uF; stable supply >=500mA')
    passive('C_ESP_VDD_SPI','1 uF','ESP_VDD_SPI_3V3','GND',L,'BOM-SOC-01','3.3','Local decoupling design allowance; qualify stable VDD_SPI per selected SiP')
    passive('R_ESP_BOOT','10k','QSPI_DIR1_EN','3V3_SYS',L,'BOM-SOC-01','3.3','GPIO0 boot pull-up; BOOT fixture pulls toGND')
    passive('R_ESP_STRAP45','100k','PDM_CLK_3V3','GND',L,'BOM-SOC-01','3.3','Keep flash3.3V strap low during reset; active PDM clock after reset')
    passive('R_ESP_STRAP46','100k','CAM_XCLK_3V3','GND',L,'BOM-SOC-01','3.3','GPIO46 low during download boot; drive XCLK only after reset strap hold')
    passive('R_ESP_STRAP3','100k','CAM_HREF_3V3','GND',L,'BOM-SOC-01','3.3','Deterministic GPIO3 JTAG strap while camera isolation holds')
    net[:]=[r for r in net if r['RefDes']!='RN_ESP_RF']
    passive('R_ESP_RF','0R initial series tuning link','ESP_RF_ANT','ESP_ANT_FEED',L,'BOM-SOC-01','0','SiP RFmatch internal; external antenna tune after VNA/OTA')
    passive('C_ESP_RF_IN','DNP antenna tuning shunt','ESP_RF_ANT','GND',L,'BOM-SOC-01','0','No invented antenna tuning capacitance')
    passive('C_ESP_RF_OUT','DNP antenna tuning shunt','ESP_ANT_FEED','GND',L,'BOM-SOC-01','0','No invented antenna tuning capacitance')
    newbom('BOM-SOC-01','C_ESP_BULK,C_ESP_VDD_SPI,R_ESP_BOOT,R_ESP_STRAP45,R_ESP_STRAP46,R_ESP_STRAP3,R_ESP_RF,C_ESP_RF_IN(DNP),C_ESP_RF_OUT(DNP)',L,
           'Explicit_host_support','22uF bulk +1uF VDD_SPI +10k GPIO0 pull-up +3x100k strap pull-down +0RRFseries +2DNPshunts',mass='0.007')
    by['BOM-02'].update(Verification_Status='SOURCE_VERIFIED_D1 physical pins1..57 and3.3V SiP; firmware/power integrity not tested',
                        Body_Height_Z_mm='1.06', Package_Footprint='LGA56+EP57 (7x7mm,0.4mm pitch,1.06mm maximumheight; Espressif package figure)', Key_Electrical_Specs='ESP32-S3-PICO-1-N8R8, LGA56+EP57 7x7x1.06mm. Inputs2/3/20/46/55/56=3V3_SYS.29VDD_SPI output only local1uF.4CHIP_PU10k/1uF RC; physical NC/PSRAM reserved pins explicit. Existing GPIO allocation retained; GPIO46 isI/O perS3datasheet.')
    # IMU and shared SYS I2C pull-ups must use the same always-on1V8 rail.
    for r in net:
        if r['RefDes']=='U9_IMU' and r['Pin'] in ('5','8','12'):
            r.update(Net='1V8_SYS',Domain_V='1.8',Note='Always-on SYS_I2C rail; removes delayed-rail backfeed; DS-000347sec4.1')
        if r['RefDes']=='U9_IMU' and r['Pin']=='9':
            r['Note']='FSYNC input: select PIN9_FUNCTION=01 before enabling any INT2 routes; FSYNC_CONFIG.POLARITY=1; no pull-up fromalways-on rail onto FPGA_CDONE_VSYNC_N; resetdefaultINT2 isopen-drain/disabled'
    for ref,value in (('C_IMU_VDD1','0.1 uF'),('C_IMU_VDD2','2.2 uF'),('C_IMU_VDDIO','10 nF')):
        passive(ref,value,'1V8_SYS','GND',B,'BOM-SOC-02','1.8','TDK DS-000347 sec4.2 typical operating circuit; close to corresponding pin5/8')
    newbom('BOM-SOC-02','C_IMU_VDD1,C_IMU_VDD2,C_IMU_VDDIO',B,'Explicit_IMU_support','0.1uF+2.2uF VDD,10nF VDDIO; effective capacitance/voltage qualify',mass='0.002')
    by['BOM-30'].update(Verification_Status='SOURCE_VERIFIED_D1 (TDK DS-000347 sec4.1/4.2, package3x2.5x0.91mm); hardware FSYNC not tested',
                        Key_Electrical_Specs='ICM-42688-P LGA14:1AD0 GND;2/3/10/11NC;4INT1NC;5VDDIO=1V8_SYS;6GND;7RESVGND;8VDD=1V8_SYS;9FSYNC FPGA_CDONE_VSYNC_N;12CS=1V8_SYS;13SCL;14SDA. Configure pin9 input FSYNC before any INT2 enable.')

    # Consistent nominal domain annotations; RF/crystal nodes carry noDCsupply.
    for r in net:
        if r['Net'].startswith(('BLE_RF_','BLE_ANT_','BLE_XC','ESP_RF_','ESP_ANT_')):
            r['Domain_V']='0'
        elif r['Net'].startswith('NRF_DEC') or r['Net'] in ('NRF_DCC','NRF_DCCD'):
            r['Domain_V']='1.0'

