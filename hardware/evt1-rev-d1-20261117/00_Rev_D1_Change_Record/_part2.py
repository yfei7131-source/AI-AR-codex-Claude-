# ------------------------------------------------------------------ 3. BOM
BOM = TBL / "BOM_V1_0_FROZEN.csv"
bom = rd(BOM)
BF = list(dict.fromkeys(list(bom[0].keys()) + ["Rev_D1_Change"]))
by = {r["Item_ID"]: r for r in bom}
def upd(i, d1, **kw):
    by[i].update(kw); by[i]["Rev_D1_Change"] = d1
VD1 = "VERIFIED_D1 (vendor document re-read 2026-11-17; see DATASHEET_EVIDENCE_LEDGER {})"
upd("BOM-01", "ANT1 feed now explicit: U1_HOST Pin 1 LNA_IN -> RN_ESP_RF tuning pi -> ANT1 (SiP integrates RF match).",
    Key_Electrical_Specs="2.4 GHz chip antenna; fed from ESP32-S3-PICO-1 Pin 1 LNA_IN through RN_ESP_RF (antenna-tuning pi, values set on VNA)")
upd("BOM-02", "P0: CHIP_PU (Pin 4) was not connected in Rev D; datasheet forbids floating. Added RC (R_CHIP_PU/C_CHIP_PU) + TP_ESP_EN/TP_ESP_BOOT.",
    Verification_Status="PARTIAL_D1 (CHIP_PU and LNA_IN recovered; superseded by source corrections)")
upd("BOM-03", "Physical DQE pins mapped (1 GND..8 EN); VREF2+EN tied and pulled to 3V3 via R_LS3_EN 200k (Rev D tied VREF2/EN straight to 3V3_SYS in the netlist). Also carries BQ25180 (0x6A).",
    Verification_Status=VD1.format("DS-10"), Key_Electrical_Specs="PCA9306 DQE: 1 GND, 2 VREF1=1V8_SYS, 3 SCL1, 4 SDA1, 5 SDA2, 6 SCL2, 7 VREF2 + 8 EN = LS3_VREF2_EN (200k to 3V3_SYS); bus devices on 1.8 V side: ICM-42688-P 0x68, BQ25180 0x6A")
for i in ("BOM-04", "BOM-38"):
    side = "LEFT: SD_MODE direct from AMP_SD_MODE_1V8, VDD=VSYS" if i == "BOM-04" else "RIGHT: SD_MODE via 69.8k RSMALL, VDD=VBAT_R_RET"
    upd(i, "P0: Rev D/Rev C bump letters wrong on 6 of 9 bumps (VDD on OUTP bump A3, GAIN_SLOT on SD_MODE bump A1, LRCLK on GND bump C2). Corrected to ADI pin description; SD_MODE margins now use datasheet min/max trip points and RPD 92..108k.",
        Verification_Status=VD1.format("DS-08"),
        Key_Electrical_Specs="MAX98357A WLP-9: A1 SD_MODE, A2 VDD, A3 OUTP, B1 DIN, B2 GAIN_SLOT(=GND, 12 dB, tied to C2 without via), B3 OUTN, C1 BCLK, C2 GND, C3 LRCLK. " + side,
        Body_Width_X_mm="1.35", Body_Length_Y_mm="1.44")
upd("BOM-06", "P1: Rev D listed TPS63802DLAR with a 1.40x2.30 mm body; the DLA package is 3.0x2.0 mm. Same-family TPS63805YFFR (2.3x1.4 mm WCSP) fits the reserved area and keeps FB 560k/100k (VFB 0.5 V).",
    MPN="TPS63805YFFR", Package_Footprint="DSBGA-15 YFF 3x5 (2.3x1.4 mm, 0.4 mm pitch)", Body_Height_Z_mm="0.50", Pad_Pitch_mm="0.40",
    Key_Electrical_Specs="Buck-boost 3.30 V (0.5 V x (1+560k/100k)); VIN 1.3..5.5 V; L_eff 0.37..0.57 uH; COUT_eff >= 7 uF; A1 EN=VSYS, B1 MODE=GND, C1 AGND, D1 FB, E1 PG(NC), A2/A3 VIN, B2/B3 L1, C2/C3 GND, D2/D3 L2, E2/E3 VOUT",
    Verification_Status=VD1.format("DS-11"), Datasheet_URL="https://ti.com/lit/pdf/slvsds9")
upd("BOM-07", "P1: 1.0 uH is outside the TPS6380x effective-inductance window 0.37..0.57 uH; changed to 0.47 uH (TI typical application). Exact MPN to be confirmed in Murata catalogue.",
    MPN="0.47 uH 2016 metal-alloy, Isat >= 4.5 A (candidate Murata DFE201610E-R47M - verify)", Key_Electrical_Specs="0.47 uH, Isat >= 4.5 A (above TPS63805 boost switch limit), Rdc <= 40 mOhm target",
    Verification_Status="SELECTED_D1 (value per DS-11; MPN not yet verified)")
upd("BOM-08", "P2: DLC body is 1.5x2.0 mm (Rev D 1.5x1.5). VSET resistor + MODE/STOP/EN ties added to netlist.",
    Body_Length_Y_mm="2.00", Package_Footprint="SON-8 DLC (1.5x2.0 mm)",
    Key_Electrical_Specs="1.8 V buck; 1 GND, 2 VIN, 3 MODE=GND, 4 EN=VSYS, 5 VSET (RSET per SLVSEC6D Table 1), 6 STOP=GND, 7 SW, 8 VOS; L 2.2 uH, CIN 4.7 uF, COUT 10 uF",
    Verification_Status=VD1.format("DS-16") + " - pins 2/5/8 confirmed in text, 1/3/4/6/7 from pin figure")
upd("BOM-10", "Pad pitch corrected 0.35 -> 0.65 mm (same DQN package as BOM-11..13).", Pad_Pitch_mm="0.65")
upd("BOM-14", "MK1_L moved to BOTTOM (rotated 4.0x3.0) at y 26.10 so J_BTB_L can move to y 38.00 and M-MAIN-L shrinks 46.0 -> 41.6 mm. Sound port must sit under the top-side free window y 24.4..26.4 (orient port toward -Y). Height 1.20 mm per Infineon drawing; SELECT/GND pins now in netlist.",
    Side="BOTTOM", Center_Y_mm="26.10", Body_Width_X_mm="4.00", Body_Length_Y_mm="3.00", Body_Height_Z_mm="1.20",
    Package_Footprint="LGA-5 (4.00x3.00x1.20 mm; bottom port)", Verification_Status=VD1.format("DS-17"))
for i in ("BOM-34", "BOM-39"):
    upd(i, "Height 1.00 -> 1.20 mm (Infineon package drawing); SELECT/GND pins added to netlist.", Body_Height_Z_mm="1.20",
        Package_Footprint="LGA-5 (4.00x3.00x1.20 mm; bottom port)", Verification_Status=VD1.format("DS-17"))
upd("BOM-15", "Y 42.40 -> 38.00 (board shortened to 41.6 mm after MK1_L moved to BOTTOM). Contact map unchanged.", Center_Y_mm="38.00")
for i, nm in (("BOM-16", "U8_LS1"), ("BOM-17", "U8_CAM_ISO1"), ("BOM-18", "U8_CAM_ISO2"), ("BOM-19", "U8_PDM_LS")):
    upd(i, "Netlist now uses physical RJW pin numbers (1 DIR1, 2-9 A1-A8, 10 DIR2, 11/12 GND, 13-20 B8-B1, 21 OE, 22/23 VCCB, 24 VCCA); GND and second VCCB pin added.",
        Verification_Status=VD1.format("DS-05/DS-09"))
upd("BOM-20", "P0: BQ24074 RISET valid range is 590R..8.9k (ICHG >= 100 mA); Rev C/D used 16.2k (54.9 mA) - outside the datasheet. Replaced by BQ25180 (I2C, 5 mA..1 A, power path, SYS 4.4..4.9 V).",
    MPN="BQ25180YBGR", Package_Footprint="DSBGA-8 YBG (1.6x1.1 mm nominal; verify ball pitch on YBG drawing)", Center_X_mm="2.00", Center_Y_mm="22.90",
    Body_Width_X_mm="1.10", Body_Length_Y_mm="1.60", Body_Height_Z_mm="0.50", Pad_Pitch_mm="TBD(YBG drawing)", Unit_Mass_g="0.003",
    Key_Electrical_Specs="Firmware at every boot: ICHG_CTRL code 32 -> 50 mA (0.45C of 110 mAh), keep VBATREG 4.20 V (reset 0x46), SYS_REG 4.5 V (reset), WATCHDOG_SEL=11 (else registers revert to 10 mA default after 160 s), IBAT_OCP 1.5 A; A1 /INT NC, A2 IN, B1 SCL, B2 SYS, C1 SDA, C2 BAT, D1 TS/MR (pack NTC), D2 GND; I2C 0x6A",
    Verification_Status=VD1.format("DS-18"), Datasheet_URL="https://ti.com/lit/pdf/SLUSE99")
upd("BOM-21", "Re-placed y 30.50 -> 29.00 (bottom re-pack).", Center_Y_mm="29.00")
upd("BOM-22", "Re-placed y 35.50 -> 32.00.", Center_Y_mm="32.00")
upd("BOM-23", "Re-placed y 35.50 -> 32.00.", Center_Y_mm="32.00")
upd("BOM-24", "Re-placed y 40.00 -> 34.60. Cluster now also holds R_LS3_EN 200k, R_BB_FB1/2 560k/100k, R_VSET_1V8, R_CHIP_PU 10k + C_CHIP_PU 1 uF.",
    Center_Y_mm="34.60", MPN=by["BOM-24"]["MPN"] + " + R_LS3_EN 200k + R_BB_FB1 560k/R_BB_FB2 100k + R_VSET_1V8 + R_CHIP_PU 10k/C_CHIP_PU 1uF")
upd("BOM-30", "P1: Rev D wired FSYNC to pin 11 (RESV) and merged VDD/VDDIO on pin 8. Corrected: pin 9 INT2/FSYNC/CLKIN, 5 VDDIO, 8 VDD, 6 GND, 7 GND, 12 AP_CS=VDDIO (I2C), 1 AP_AD0=GND (0x68).",
    Key_Electrical_Specs="ICM-42688-P LGA-14: 1 AP_AD0=GND, 4 INT1 NC, 5 VDDIO, 6 GND, 7 RESV=GND, 8 VDD, 9 FSYNC<-D3 (falling edge), 12 AP_CS=VDDIO, 13 SCL, 14 SDA; 2/3/10/11 NC",
    Verification_Status="CROSS_CHECKED_D1 (two independent library reproductions of TDK DS-000347; confirm against DS-000347 sec.4.1 before tape-out; see DS-13)")
upd("BOM-35", "Feed explicit: nRF5340 ANT (D1) -> RN_BLE_RF match -> ANT2_BLE.")
upd("BOM-36", "P0: KIMI-RevD-04 closed: balls assigned from Nordic nRF5340 PS WLCSP table (I2S K5/K4/J4/J5 = P0.20/P0.22/P0.21/P0.19, UARTE K3/L3 = P1.04/P1.05, AMP_SD_MODE K2 = P0.24). Missing 32 MHz crystal (Y2_BLE), RF match, SWD/reset access, VDD/VSS/AVSS/DECx rows added.",
    Verification_Status=VD1.format("DS-14"), Datasheet_URL="https://docs.nordicsemi.com/bundle/ps_nrf5340/page/chapters/pin.html")
upd("BOM-37", "Pins mapped (1 IN, 2 ISET, 3 TS, 4 GND, 5 /PG, 6 STAT, 7 VSET, 8 OUT, EP). RISET 5.49k (range 375R..30k) and RVSET 27k (=4.20 V) re-checked against datasheet.",
    Verification_Status=VD1.format("DS-12"))
upd("BOM-47", "Physical RSV pins mapped (1 1OE, 2 VCCB, 3 VCCA, 4 1DIR, 5 2DIR, 6/7 1A1/1A2, 8/9 2A1/2A2, 10/11 GND, 12/13 2B2/2B1, 14/15 1B2/1B1, 16 2OE). Re-placed y 43.60 -> 37.60 rotated.",
    Center_Y_mm="37.60", Body_Width_X_mm="2.60", Body_Length_Y_mm="1.80", Verification_Status=VD1.format("DS-09"),
    Pad_Footprint_Note="", Package_Footprint="UQFN-16 RSV (2.6x1.8 mm, 0.4 mm pitch)")
by["BOM-47"].pop("Pad_Footprint_Note", None)
upd("BOM-48", "Physical DQE pins; VREF2+EN tied, 200k to 3V3 (R_LS4_EN in RN_CAM_REQ).", Verification_Status=VD1.format("DS-10"))
upd("BOM-49", "Cluster adds R_LS4_EN 200k.", MPN=by["BOM-49"]["MPN"] + " + R_LS4_EN 200k")
upd("BOM-53", "Cluster adds R_ISET_R 5.49k 1% and R_VSET_R 27k 1% for U3_R.", MPN=by["BOM-53"]["MPN"] + " + R_ISET_R 5.49k 1% + R_VSET_R 27k 1%")
for r in bom:
    r.setdefault("Rev_D1_Change", "")
def new(i, **kw):
    r = {k: "" for k in BF}; r.update(Item_ID=i, Qty="1", Rev_D_Change="n/a (new in Rev D1)"); r.update(kw); bom.append(r)
new("BOM-55", RefDes="Y2_BLE", Board_Zone="M-AUD-R", Side="BOTTOM", Center_X_mm="2.60", Center_Y_mm="7.00", Body_Width_X_mm="1.60",
    Body_Length_Y_mm="2.00", Body_Height_Z_mm="0.50", Pad_Pitch_mm="TBD", Category="Crystal_32MHz_BLE",
    MPN="MPN_TBD (32 MHz crystal meeting nRF5340 PS HFXO requirements: CL, ESR, total tolerance for BLE)", Manufacturer="TBD",
    Package_Footprint="2016 (2.0x1.6 mm) 4-pad, final per chosen MPN", Key_Electrical_Specs="XC1 (A1) / XC2 (A2) of U11_BLE; load caps per PS",
    Unit_Mass_g="0.005", Verification_Status="OPEN_SELECTION (requirement from DS-14; mass is an estimate)",
    Rev_D1_Change="P0: nRF5340 RADIO requires the 32 MHz crystal; Rev C/D BOM had none.")
new("BOM-56", RefDes="RN_BLE_RF", Board_Zone="M-AUD-R", Side="BOTTOM", Center_X_mm="2.60", Center_Y_mm="10.20", Body_Width_X_mm="3.60",
    Body_Length_Y_mm="1.60", Body_Height_Z_mm="0.35", Pad_Pitch_mm="0.40", Category="Passive_Cluster_BLE_RF_and_Decoupling",
    MPN="01005/0201 cluster: RF match (topology/values per nRF5340 PS reference circuitry, tuned on VNA) + DECA/DECD/DECN/DECR/DECRF/DECUSB + VDD decoupling per PS",
    Manufacturer="Murata / Yageo", Package_Footprint="01005/0201 cluster under U11_BLE (VIPPO)", Key_Electrical_Specs="values taken from PS reference BOM, not invented here",
    Unit_Mass_g="0.003", Verification_Status="DESIGN_RULE_D1 (values per DS-14 reference circuitry)", Rev_D1_Change="P0: nRF5340 decoupling and RF match were absent.")
new("BOM-57", RefDes="TP_SWD_R", Board_Zone="M-AUD-R", Side="BOTTOM", Center_X_mm="2.60", Center_Y_mm="14.00", Body_Width_X_mm="4.00",
    Body_Length_Y_mm="1.20", Body_Height_Z_mm="0.00", Pad_Pitch_mm="0.80", Category="Test_Pads_SWD", MPN="5x 0.6 mm pads (SWDIO, SWDCLK, nRESET, VTREF, GND) for pogo fixture",
    Manufacturer="PCB", Package_Footprint="pads", Key_Electrical_Specs="nRF5340 programming/debug access", Unit_Mass_g="0.000",
    Verification_Status="DESIGN_RULE_D1", Rev_D1_Change="P0: Rev D gave no way to program the nRF5340.")
new("BOM-58", RefDes="TP_ESP", Board_Zone="M-MAIN-L", Side="BOTTOM", Center_X_mm="2.90", Center_Y_mm="40.00", Body_Width_X_mm="2.40",
    Body_Length_Y_mm="1.00", Body_Height_Z_mm="0.00", Pad_Pitch_mm="0.80", Category="Test_Pads_ESP32", MPN="TP_ESP_EN (CHIP_PU) + TP_ESP_BOOT (GPIO0) pads",
    Manufacturer="PCB", Package_Footprint="pads", Key_Electrical_Specs="recovery: hold BOOT low while releasing EN", Unit_Mass_g="0.000",
    Verification_Status="DESIGN_RULE_D1", Rev_D1_Change="P0 companion to CHIP_PU fix.")
new("BOM-59", RefDes="RN_CHG_L", Board_Zone="M-MAIN-L", Side="BOTTOM", Center_X_mm="4.20", Center_Y_mm="22.90", Body_Width_X_mm="2.00",
    Body_Length_Y_mm="1.60", Body_Height_Z_mm="0.50", Pad_Pitch_mm="0.40", Category="Passive_Cluster_Charger_L",
    MPN="CIN 1 uF 25 V + CSYS 10 uF + CBAT 1 uF (BQ25180 Table 9-2; 25 V rating on IN/SYS per 9.2.2.1)", Manufacturer="Murata",
    Package_Footprint="0402/0201", Key_Electrical_Specs="effective C >= 1 uF after DC bias on IN/SYS/BAT", Unit_Mass_g="0.004",
    Verification_Status="DESIGN_RULE_D1 (DS-18)", Rev_D1_Change="New with BQ25180.")
for r in bom:
    if r["Item_ID"] == "BOM-43":
        r["Rev_D1_Change"] = "Left pack NTC now wired to TP_NTC_L -> BQ25180 TS/MR (TS must not float)."
wr(BOM, bom, BF)

# ------------------------------------------------------------------ 4. PINMAP
PM = TBL / "PINMAP_V1_0_FROZEN.csv"
pm = rd(PM)
PF = list(dict.fromkeys(list(pm[0].keys()) + ["Rev_D1_Status"]))
for r in pm:
    r["Rev_D1_Status"] = "UNCHANGED"
    c = r["Chip_Ref"]
    if c.startswith("U10_AMP_L"):
        r.update(Signal_Net_Name="A1:SD_MODE (L: AMP_SD_MODE_1V8 direct; R: via 69.8k), A2:VDD (L: VSYS, R: VBAT_R_RET), A3:OUTP, B1:DIN=I2S_AMP_DIN_1V8, B2:GAIN_SLOT=GND (12 dB, tied to C2), B3:OUTN, C1:BCLK, C2:GND, C3:LRCLK",
                 Datasheet_Verification_Note="ADI MAX98357A/B Rev 13 pin description (DS-08). SD_MODE trip points B0 0.08/0.16/0.355, B1 0.65/0.77/0.825, B2 1.245/1.4/1.5 V; RPD 92/100/108k", Rev_D1_Status="CORRECTED")
    elif c.startswith("MK1_L"):
        r.update(Datasheet_Verification_Note="Infineon IM69D130 DS v1.0 Table 7 (DS-17): 1 DATA, 2 VDD, 3 CLOCK, 4 SELECT, 5 GND; body 4.0x3.0x1.2 mm; tDV <= 100 ns", Rev_D1_Status="VERIFIED")
    elif c.startswith("U9_IMU"):
        r.update(Signal_Net_Name="U9_IMU: 1 AP_SDO/AP_AD0=GND (0x68), 2/3/10/11 RESV NC, 4 INT1 NC, 5 VDDIO=1V8_FPGA_IO, 6 GND, 7 RESV=GND, 8 VDD=1V8_FPGA_IO, 9 INT2/FSYNC/CLKIN=FPGA_CDONE_VSYNC_N (falling edge), 12 AP_CS=VDDIO (I2C), 13 SCL, 14 SDA; Y1_OSC: 1 STBY=1V8_FPGA_IO, 2 GND, 3 OUT=clk_48m->B3, 4 VDD=1V8_FPGA_IO",
                 Datasheet_Verification_Note="Rev D used pin 11 (RESV) for FSYNC, pin 9 as GND and pin 12 as INT1 - corrected (DS-13; confirm vs TDK DS-000347)", Rev_D1_Status="CORRECTED")
    elif c.startswith("U3_L"):
        r.update(Chip_Ref="U3_L (BQ25180), U3_R (BQ25170), U4_OR (LM66200), U4_BB (TPS63805), U4_1V8 (TPS62840), U4_1V2 (TLV75512)",
                 Signal_Net_Name="U3_L: A2 IN=VBUS_5V, B2 SYS=VOUT_L_PPATH(4.5 V)->U4_OR.VIN1, C2 BAT=VBAT_L, D1 TS/MR=NTC_TS_L, B1/C1 SCL/SDA=SYS_I2C_1V8 (0x6A); U3_R: 1 IN, 2 ISET 5.49k, 3 TS, 7 VSET 27k, 8 OUT=VBAT_R_RET; U4_BB: A2/A3 VIN=VSYS, E2/E3 VOUT=3V3_SYS, A1 EN=VSYS, B1 MODE=GND; U4_1V8: 2 VIN, 4 EN=VSYS, 5 VSET, 8 VOS=1V8_SYS",
                 Datasheet_Verification_Note="BQ24074 removed (RISET 16.2k outside 590R..8.9k). LM66200 pin numbers still to be mapped by KIMI (not re-read this round).", Rev_D1_Status="CORRECTED")
    elif c.startswith("U11_BLE"):
        r.update(Pin_ID="WLCSP-95 balls (Nordic PS Table 3)", Signal_Net_Name="K5 P0.20=I2S SCK->I2S_BCLK_1V8, K4 P0.22=LRCK->I2S_LRCLK_1V8, J4 P0.21=SDOUT->I2S_AMP_DIN_1V8, J5 P0.19=SDIN<-I2S_S3_DOUT_1V8, K3 P1.04=UARTE TXD->IPC_NRF_TX_1V8, L3 P1.05=UARTE RXD<-IPC_S3_TX_1V8, K2 P0.24=GPIO->AMP_SD_MODE_1V8; A1/A2 XC1/XC2=Y2_BLE 32 MHz; D1 ANT; F1/F2 SWD; G2 nRESET; VDD A3,B7,B10,D2,E11,H11,K1,L5,L11; VDDH B12",
                 Isolation_or_Translator="Native 1.8 V IO; balls frozen this round from the public PS (KIMI-RevD-04 closed)", Datasheet_Verification_Note="DS-14", Rev_D1_Status="FROZEN")
    elif c.startswith("U8_AUD_LS2"):
        r.update(Pin_ID="RSV: 1 1OE, 2 VCCB, 3 VCCA, 4 1DIR, 5 2DIR, 6 1A1, 7 1A2, 8 2A1, 9 2A2, 10/11 GND, 12 2B2, 13 2B1, 14 1B2, 15 1B1, 16 2OE",
                 Datasheet_Verification_Note="TI SCES877B Table 4-1 (DS-09)", Rev_D1_Status="FROZEN")
    elif c.startswith("U8_LS4"):
        r.update(Pin_ID="DQE: 1 GND, 2 VREF1, 3 SCL1, 4 SDA1, 5 SDA2, 6 SCL2, 7 VREF2, 8 EN", Signal_Net_Name="VREF1=CAM_DOVDD_1V8, VREF2+EN=LS4_VREF2_EN (200k to 3V3), SCL1/SDA1=CAM_SCCB_SCL/SDA (4.7k to DOVDD), SCL2/SDA2=SYS_I2C_SCL/SDA_3V3",
                 Datasheet_Verification_Note="TI SCPS113O (DS-10)", Rev_D1_Status="FROZEN")
pm.append({"Chip_Ref": "U1_HOST (ESP32-S3-PICO-1-N8R8)", "Pin_ID": "Pin 1, Pin 4", "Pin_Name": "LNA_IN, CHIP_PU",
           "Signal_Net_Name": "Pin 1 LNA_IN=ESP_RF_ANT->RN_ESP_RF->ANT1; Pin 4 CHIP_PU=ESP_CHIP_PU (10k to 3V3_SYS, 1 uF to GND, TP_ESP_EN)",
           "Direction": "RF / IN", "Voltage_Domain": "3.3V", "Isolation_or_Translator": "-", "Target_Destination": "ANT1 / reset RC",
           "Datasheet_Verification_Note": "Espressif ESP32-S3-PICO-1 Table 2-1: CHIP_PU must not float (DS-15)", "Rev_D_Status": "", "Rev_D1_Status": "NEW"})
wr(PM, pm, PF)
