# -*- coding: utf-8 -*-
"""EVT-0 core verification board - single source of truth for schematic/netlist/BOM.
Edit here, then run:  python3 gen_kicad.py   (regenerates .kicad_sch/.kicad_sym/netlist/BOM)
Status: R3 electrical review. See ../ELECTRICAL_REVIEW.md for population options and test gates."""

DS = {
 "esp": "https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf",
 "bq": "https://www.ti.com/lit/ds/symlink/bq24072.pdf",
 "tlv757": "https://www.ti.com/lit/ds/symlink/tlv757p.pdf",
 "tlv755": "https://www.ti.com/lit/ds/symlink/tlv755p.pdf",
 "usblc6": "https://www.st.com/resource/en/datasheet/usblc6-2.pdf",
 "bss138": "https://www.onsemi.com/pdf/datasheet/bss138-d.pdf",
 "dmg2305": "https://www.diodes.com/assets/Datasheets/DMG2305UX.pdf",
}
FP = {
 "R": "Resistor_SMD:R_0402_1005Metric", "C": "Capacitor_SMD:C_0402_1005Metric",
 "C0603": "Capacitor_SMD:C_0603_1608Metric", "C0805": "Capacitor_SMD:C_0805_2012Metric",
 "LED": "LED_SMD:LED_0603_1608Metric", "SOT235": "Package_TO_SOT_SMD:SOT-23-5",
 "SOT236": "Package_TO_SOT_SMD:SOT-23-6", "SOT23": "Package_TO_SOT_SMD:SOT-23",
 "D": "Diode_SMD:D_SOD-323",
}

# ---- IC / connector symbols: name -> prefix, footprint, datasheet, left pins, right pins
# pin = (number, name, electrical type)
SYMS = {}
def sym(name, prefix, fp, ds, left, right, desc=""):
    SYMS[name] = dict(prefix=prefix, fp=fp, ds=ds, left=left, right=right, desc=desc)

B = "bidirectional"
sym("ESP32-S3-WROOM-1", "U", "RF_Module:ESP32-S3-WROOM-1", DS["esp"],
 left=[("2","3V3","power_in"),("3","EN","input"),("27","IO0",B),("39","IO1",B),("38","IO2",B),("15","IO3",B),
       ("4","IO4",B),("5","IO5",B),("6","IO6",B),("7","IO7",B),("12","IO8",B),("17","IO9",B),("18","IO10",B),
       ("19","IO11",B),("20","IO12",B),("21","IO13",B),("22","IO14",B),("8","IO15",B),("9","IO16",B),("10","IO17",B),
       ("1","GND","power_in")],
 right=[("11","IO18",B),("13","IO19/USB_D-",B),("14","IO20/USB_D+",B),("23","IO21",B),
        ("28","IO35(PSRAM)","no_connect"),("29","IO36(PSRAM)","no_connect"),("30","IO37(PSRAM)","no_connect"),
        ("31","IO38",B),("32","IO39",B),("33","IO40",B),("34","IO41",B),("35","IO42",B),
        ("37","TXD0/IO43",B),("36","RXD0/IO44",B),("26","IO45",B),("16","IO46",B),("24","IO47",B),("25","IO48",B),
        ("40","GND","power_in"),("41","EPAD","power_in")],
 desc="Wi-Fi+BLE5 module, 16MB flash, 8MB octal PSRAM (IO35-37 reserved)")

sym("BQ24072RGT", "U", "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", DS["bq"],
 left=[("13","IN","power_in"),("4","~{CE}","input"),("6","EN1","input"),("5","EN2","input"),
       ("15","TD","input"),("12","ILIM","passive"),("16","ISET","passive"),("14","TMR","passive"),("8","VSS","power_in")],
 right=[("10","OUT","power_out"),("11","OUT","passive"),("2","BAT","bidirectional"),("3","BAT","bidirectional"),
        ("1","TS","input"),("7","~{PGOOD}","open_collector"),("9","~{CHG}","open_collector"),("17","EP","power_in")],
 desc="1-cell Li-ion linear charger with power path, NTC; pin 15 = TD (termination disable) on BQ24072/73. NO SYSOFF on this variant")

for v, nm in (("TLV75733PDBV", "3.3V 1A"), ("TLV75528PDBV", "2.8V 500mA"), ("TLV75512PDBV", "1.2V 500mA")):
    sym(v, "U", FP["SOT235"], DS["tlv757"] if "757" in v else DS["tlv755"],
        left=[("1","IN","power_in"),("3","EN","input"),("2","GND","power_in")],
        right=[("5","OUT","power_out"),("4","NC","no_connect")], desc="LDO " + nm)

sym("USBLC6-2SC6", "U", FP["SOT236"], DS["usblc6"],
 left=[("1","IO1","passive"),("3","IO2","passive"),("2","GND","power_in")],
 right=[("6","IO1","passive"),("4","IO2","passive"),("5","VBUS","power_in")], desc="USB ESD protection")

sym("USB_C_16P", "J", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "",
 left=[("A4","VBUS","passive"),("A9","VBUS","passive"),("B4","VBUS","passive"),("B9","VBUS","passive"),
       ("A5","CC1",B),("B5","CC2",B),("A8","SBU1","no_connect"),("B8","SBU2","no_connect")],
 right=[("A6","D+",B),("B6","D+",B),("A7","D-",B),("B7","D-",B),
        ("A1","GND","passive"),("A12","GND","passive"),("B1","GND","passive"),("B12","GND","passive"),("SH","SHIELD","passive")],
 desc="USB Type-C receptacle, USB2.0 16P")

sym("CAM_FPC24_DVP", "J", "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal", "",
 left=[(str(i), n, "passive") for i, n in [(1,"STROBE"),(2,"AGND"),(3,"SIOD"),(4,"AVDD"),(5,"SIOC"),(6,"RESET"),
        (7,"VSYNC"),(8,"PWDN"),(9,"HREF"),(10,"DVDD"),(11,"DOVDD"),(12,"Y9")]],
 right=[(str(i), n, "passive") for i, n in [(13,"XCLK"),(14,"Y8"),(15,"DGND"),(16,"Y7"),(17,"PCLK"),(18,"Y6"),
        (19,"Y2"),(20,"Y5"),(21,"Y3"),(22,"Y4"),(23,"Y1"),(24,"Y0")]] + [("MP","SHELL","passive")],
 desc="24P 0.5mm DVP camera FPC (common OV2640/OV3660/OV5640 pinout - VERIFY against module drawing)")

sym("NMOS_SOT23_GSD", "Q", FP["SOT23"], DS["bss138"],
 left=[("1","G","input")], right=[("3","D","passive"),("2","S","passive")], desc="N-MOSFET SOT-23, logic level, pin 1=G 2=S 3=D")
sym("PMOS_SOT23_GSD", "Q", FP["SOT23"], DS["dmg2305"],
 left=[("1","G","input")], right=[("2","S","passive"),("3","D","passive")], desc="P-MOSFET SOT-23, logic level, pin 1=G 2=S 3=D")

def hdr(n):
    name = "HDR_1x%02d" % n
    if name not in SYMS:
        fp = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical" % n
        sym(name, "J", fp, "", left=[], right=[(str(i), "P%d" % i, "passive") for i in range(1, n+1)], desc="pin header")
    return name
sym("JST_SH_3", "J", "Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal", "https://www.jst-mfg.com/product/pdf/eng/eSH.pdf",
    left=[], right=[("1","BAT+","passive"),("2","NTC","passive"),("3","BAT-","passive"),("MP","MP","passive")], desc="battery connector")

# ---- Parts
P = []
def part(ref, symname, value, nets, mpn="", mfr="", fp=None, dnp=False, note=""):
    P.append(dict(ref=ref, sym=symname, value=value, nets=nets, mpn=mpn, mfr=mfr, fp=fp, dnp=dnp, note=note))
NC = "__NC__"
def R(ref, val, a, b, **k): part(ref, "R", val, {"1": a, "2": b}, fp=FP["R"], **k)
def C(ref, val, a, b="GND", fp="C", **k): part(ref, "C", val, {"1": a, "2": b}, fp=FP[fp], **k)

# ===== USB-C / ESD =====
part("J1", "USB_C_16P", "USB-C 16P", {"A4":"VBUS","A9":"VBUS","B4":"VBUS","B9":"VBUS","A5":"CC1","B5":"CC2",
     "A8":NC,"B8":NC,"A6":"USB_DP","B6":"USB_DP","A7":"USB_DM","B7":"USB_DM","A1":"GND","A12":"GND","B1":"GND","B12":"GND","SH":"GND"},
     mpn="TYPE-C-31-M-12", mfr="Korean Hroparts Elec")
R("R1", "5.1k 1%", "CC1", "GND"); R("R2", "5.1k 1%", "CC2", "GND")
part("U2", "USBLC6-2SC6", "USBLC6-2SC6", {"1":"USB_DP","6":"USB_DP","3":"USB_DM","4":"USB_DM","2":"GND","5":"VBUS"},
     mpn="USBLC6-2SC6", mfr="STMicroelectronics")
part("D1", "D", "TVS 5V SOD-323", {"1":"VBUS","2":"GND"}, fp=FP["D"], mpn="TBD (5V standoff)", mfr="TBD", note="pin1=K, pin2=A")
# ===== Charger + power path =====
part("U3", "BQ24072RGT", "BQ24072RGTR", {"13":"VBUS","4":"CHG_CE_N","6":"CHG_EN1","5":"GND","15":"CHG_TD","12":"CHG_ILIM",
     "16":"CHG_ISET","14":NC,"8":"GND","10":"VSYS","11":"VSYS","2":"VBAT","3":"VBAT","1":"BAT_NTC","7":"CHG_PGOOD_N",
     "9":"CHG_STAT_N","17":"GND"}, mpn="BQ24072RGTR", mfr="Texas Instruments",
     note="R2-F1: pin15=TD tied to VSS (termination enabled). alt: BQ24073RGTR (OUT=4.4V, pin15 also TD). BQ24075/79 are NOT drop-in: pin15=SYSOFF, OUT=5.5V")
C("C1", "1uF 10V X5R", "VBUS"); C("C2", "4.7uF 10V X5R", "VBAT", fp="C0603"); C("C3", "10uF 10V X5R", "VSYS", fp="C0603")
R("R3", "10k", "CHG_EN1", "GND", note="EN2=0, EN1=0: USB100; do not run unbuffered radio from this supply")
R("R35", "10k", "VBUS", "CHG_CE_N", note="With valid input CE is high: charging disabled by default")
R("R36", "0R", "CHG_CE_N", "GND", dnp=True, note="Qualified pack only: ground CE to permit charging; requires evaluated NTC, load and R5")

R("R4", "1.6k 1%", "CHG_ILIM", "GND", note="TI SLUS810N: 1.1k..8k; unused in fixed USB100 mode")
R("R5", "5.9k 1%", "CHG_ISET", "GND", dnp=True, note="Open ISET disables charging. Fit only for qualified pack; 5.9k 1% programs 134..167mA before input, DPPM and thermal limits")
R("R6", "0R", "CHG_TD", "GND", note="R2-F1: TD strapped to VSS = charge termination ENABLED (TI datasheet: TD read at startup only, do not float). No ship mode on BQ24072; EVT-0 battery disconnect = pull JP1")
R("R7", "1k", "VBUS", "CHG_LED_A")
part("D2", "LED", "LED red 0603", {"1":"CHG_STAT_N","2":"CHG_LED_A"}, fp=FP["LED"], mpn="TBD", note="pin1=K, pin2=A")
# TS is exclusively connected to the matched pack thermistor; no on-board NTC bypass.
part("J2", "JST_SH_3", "BAT 1S LiPo", {"1":"VBAT_CONN","2":"BAT_NTC","3":"GND","MP":"GND"}, mpn="SM03B-SRSS-TB", mfr="JST")
part("JP1", hdr(2), "I_BAT measure", {"1":"VBAT_CONN","2":"VBAT"}, note="jumper / ammeter insertion point for H05")
R("R9", "1M 1%", "VBAT", "VBAT_ADC"); R("R10", "1M 1%", "VBAT_ADC", "GND"); C("C4", "100nF", "VBAT_ADC")
# ===== 3V3 system rail =====
part("U4", "TLV75733PDBV", "TLV75733PDBVR", {"1":"VSYS","3":"VSYS","2":"GND","5":"3V3","4":NC},
     mpn="TLV75733PDBVR", mfr="Texas Instruments", note="Low-VBAT dropout and dissipation constrain usable range. No second-source substitution approved.")
C("C5", "1uF 10V", "VSYS"); C("C6", "1uF 10V", "3V3"); C("C7", "22uF 6.3V X5R", "3V3", fp="C0805"); C("C8", "22uF 6.3V X5R", "3V3", fp="C0805")
# ===== MCU =====
esp = {"2":"3V3","3":"EN","27":"KEY_BOOT","39":"VBAT_ADC","38":"MIC_SD","15":"CAM_PWR_EN","4":"CAM_SIOD","5":"CAM_SIOC",
 "6":"CAM_VSYNC","7":"CAM_HREF","12":"CAM_Y4","17":"CAM_Y3","18":"CAM_Y5","19":"CAM_Y2","20":"CAM_Y6","21":"CAM_PCLK_R",
 "22":"DISP_RST","8":"CAM_XCLK_R","9":"CAM_Y9","10":"CAM_Y8","1":"GND","11":"CAM_Y7","13":"USB_DM","14":"USB_DP",
 "23":"DISP_CS","28":NC,"29":NC,"30":NC,"31":"DISP_D0","32":"DISP_D1","33":"DISP_D2","34":"MIC_SCK","35":"MIC_WS",
 "37":"U0TXD","36":"U0RXD","26":"DISP_PWR_EN","16":"STRAP46","24":"DISP_CLK","25":"DISP_D3","40":"GND","41":"GND"}
part("U1", "ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8", esp, mpn="ESP32-S3-WROOM-1-N16R8", mfr="Espressif Systems")
C("C9", "100nF", "3V3"); C("C10", "10uF 10V", "3V3", fp="C0603")
R("R11", "10k", "3V3", "EN"); C("C11", "1uF 10V", "EN")
part("SW1", "SW", "RESET", {"1":"EN","2":"GND"}, fp="Button_Switch_SMD:SW_SPST_TL3342", mpn="TL3342F160QG", mfr="E-Switch")
R("R12", "10k", "3V3", "KEY_BOOT")
part("SW2", "SW", "BOOT/ACTION", {"1":"KEY_BOOT","2":"GND"}, fp="Button_Switch_SMD:SW_SPST_TL3342", mpn="TL3342F160QG", mfr="E-Switch")
R("R13", "10k", "CAM_PWR_EN", "GND", note="camera rail OFF during reset/boot (IO3 strap: JTAG source only)")
R("R14", "10k", "DISP_PWR_EN", "GND", note="IO45 strap must be LOW at boot (VDD_SPI=3.3V)")
R("R15", "10k", "STRAP46", "GND", note="IO46 strap must be LOW at boot")
# ===== Camera rails (hardware-gated) =====
part("U5", "TLV75528PDBV", "TLV75528PDBVR", {"1":"VSYS","3":"CAM_PWR_EN","2":"GND","5":"CAM_2V8","4":NC}, mpn="TLV75528PDBVR", mfr="Texas Instruments")
part("U6", "TLV75512PDBV", "TLV75512PDBVR", {"1":"3V3","3":"CAM_2V8","2":"GND","5":"CAM_1V2","4":NC}, mpn="TLV75512PDBVR", mfr="Texas Instruments",
     note="EN chained to CAM_2V8; DNP for sensors with internal DVDD regulator")
C("C12", "1uF 10V", "VSYS"); C("C13", "1uF 10V", "CAM_2V8"); C("C14", "1uF 10V", "3V3"); C("C15", "1uF 10V", "CAM_1V2")
R("R16", "0R", "CAM_1V2", "CAM_DVDD", dnp=True, note="No default DVDD selection; release against exact FPC and sensor revision")
# R1-F3: R0 tied DOVDD to always-on 3V3 (sensor IO powered with AVDD off; privacy gate incomplete).
# Now 3V3 -> Q3 (P-FET high side; gate pulled low by Q2 when CAM_PWR_EN=1) -> CAM_3V3 -> DOVDD.
part("Q2", "NMOS_SOT23_GSD", "BSS138", {"1":"CAM_PWR_EN","3":"CAM_3V3_G","2":"GND"}, mpn="BSS138", mfr="onsemi")
part("Q3", "PMOS_SOT23_GSD", "DMG2305UX", {"1":"CAM_3V3_G","2":"3V3","3":"CAM_3V3"}, mpn="DMG2305UX-7", mfr="Diodes Inc.",
     note="any logic-level SOT-23 P-FET with G/S/D = 1/2/3; VERIFY pinout of the part actually bought")
R("R29", "100k", "3V3", "CAM_3V3_G", note="Q3 off by default")
C("C20", "1uF 10V", "CAM_3V3")
R("R17", "0R", "CAM_3V3", "CAM_DOVDD", dnp=True, note="No default DOVDD selection; 3.3V can damage a lower-voltage module")
R("R18", "0R", "CAM_2V8", "CAM_DOVDD", dnp=True, note="option DOVDD=2V8 (never fit together with R17)")
C("C16", "100nF", "CAM_DVDD"); C("C17", "100nF", "CAM_DOVDD"); C("C18", "100nF", "CAM_2V8")
R("R19", "4.7k", "CAM_DOVDD", "CAM_SIOD"); R("R20", "4.7k", "CAM_DOVDD", "CAM_SIOC")  # R1-F3: no back-feed via pull-ups
R("R21", "10k", "CAM_DOVDD", "CAM_RST_N"); C("C19", "100nF", "CAM_RST_N")
R("R22", "10k", "CAM_PWDN", "GND")
R("R23", "33R", "CAM_XCLK_R", "CAM_XCLK"); R("R24", "33R", "CAM_PCLK", "CAM_PCLK_R")
part("J3", "CAM_FPC24_DVP", "CAM DVP 24P", {"1":NC,"2":"GND","3":"CAM_SIOD","4":"CAM_2V8","5":"CAM_SIOC","6":"CAM_RST_N",
     "7":"CAM_VSYNC","8":"CAM_PWDN","9":"CAM_HREF","10":"CAM_DVDD","11":"CAM_DOVDD","12":"CAM_Y9","13":"CAM_XCLK","14":"CAM_Y8",
     "15":"GND","16":"CAM_Y7","17":"CAM_PCLK","18":"CAM_Y6","19":"CAM_Y2","20":"CAM_Y5","21":"CAM_Y3","22":"CAM_Y4","23":NC,"24":NC,"MP":"GND"},
     mpn="FH12-24S-0.5SH(55)", mfr="Hirose", dnp=True, note="Candidate bottom-contact FPC only. Confirm sensor drawing, tail side, AVDD/DVDD/DOVDD, signal levels and fit before use.")
# ===== Camera privacy indicator: pure hardware, driven by camera analog rail =====
R("R27", "560R 1%", "CAM_2V8", "CAM_LED_A")
part("D3", "LED", "Red low current", {"1":"GND", "2":"CAM_LED_A"},
     fp="LED_THT:LED_D3.0mm", mpn="WP710A10LID", mfr="Kingbright",
     note="Pin1 cathode. AVDD rail indication, nominal 2mA. Open or short LED does not disable camera power; hardware failure and visibility gates pending.")
# ===== Breakouts (verification board only; NOT the final display/audio interface) =====
part("J4", hdr(12), "DISP QSPI breakout", {"1":"3V3","2":"VSYS","3":"GND","4":"DISP_PWR_EN","5":"DISP_RST","6":"DISP_CS",
     "7":"DISP_CLK","8":"DISP_D0","9":"DISP_D1","10":"DISP_D2","11":"DISP_D3","12":"GND"},
     dnp=True, note="Lab test pads only; voltage, FPC, timing, controller and waveguide missing. Do not cable a light engine.")
part("J5", hdr(5), "MIC breakout", {"1":"3V3","2":"GND","3":"MIC_SCK","4":"MIC_WS","5":"MIC_SD"}, note="I2S or PDM (CLK=SCK, DATA=SD) mic board")
part("J6", hdr(6), "DEBUG UART", {"1":"3V3","2":"GND","3":"U0TXD","4":"U0RXD","5":"EN","6":"KEY_BOOT"})
part("J7", hdr(3), "AUDIO UART (isolated options)", {"1":"GND","2":"AUD_UART_TX","3":"AUD_UART_RX"},
     note="Diagnostic only, external EVB self-powered. J7.2 ESP TX to BM83 #29, J7.3 ESP RX from #30; never power-feed EVB.")
R("R33", "0R", "U0TXD", "AUD_UART_TX", dnp=True, note="Optional UART TX bridge; verify levels, console ownership and EVB isolation; mutually exclusive with I2C option")
R("R34", "0R", "U0RXD", "AUD_UART_RX", dnp=True, note="Optional UART RX bridge; verify levels, console ownership and EVB isolation; mutually exclusive with I2C option")
for i, n in enumerate(["VBUS","VSYS","VBAT","3V3","CAM_2V8","CAM_1V2","GND","CHG_ISET","CHG_PGOOD_N","CAM_3V3"], 1):
    part("TP%d" % i, "TP", n, {"1": n}, fp="TestPoint:TestPoint_Pad_D1.0mm")
R("R28", "100k", "VSYS", "CHG_PGOOD_N", dnp=True, note="pull-up for probing PGOOD")
# R2-F2: DNP pull-ups so J6.3/J6.4 (GPIO43/44) can become an always-on sensor I2C bus once Codex moves the console
# to USB-Serial-JTAG (ICR-05). Not fitted by default -> UART0 behaviour unchanged.
R("R30", "4.7k", "3V3", "U0TXD", dnp=True, note="R2-F2 option: sensor I2C SDA pull-up (only after ICR-05 accepted)")
R("R31", "4.7k", "3V3", "U0RXD", dnp=True, note="R2-F2 option: sensor I2C SCL pull-up (only after ICR-05 accepted)")
# Measurement only: the switched supply cannot be enabled by fitting a shunt.
part("TP11", "TP", "CAM_PWR_EN", {"1":"CAM_PWR_EN"}, fp="TestPoint:TestPoint_Pad_D1.0mm")
# Pin-15 function per TI BQ2407x datasheet (SLUS810) pin table / app note SLUA947 - used by the generator guard
BQ2407X_PIN15 = {"BQ24072": "TD", "BQ24073": "TD", "BQ24074": "ITERM", "BQ24075": "SYSOFF", "BQ24079": "SYSOFF"}

SINGLE_OK = set()   # nets intentionally allowed to have one pin

# R1-F1: ERC power drivers for nets fed from connectors
for i, n in enumerate(["VBUS", "GND"], 1):
    part("#FLG%d" % i, "PWR_FLAG", "PWR_FLAG", {"1": n})

# ESP32-S3 GPIO -> module pin (ESP32-S3-WROOM-1 datasheet pin definitions) for pin-map export / firmware cross-check
GPIO_PIN = {0:"27",1:"39",2:"38",3:"15",4:"4",5:"5",6:"6",7:"7",8:"12",9:"17",10:"18",11:"19",12:"20",13:"21",14:"22",
 15:"8",16:"9",17:"10",18:"11",19:"13",20:"14",21:"23",35:"28",36:"29",37:"30",38:"31",39:"32",40:"33",41:"34",42:"35",
 43:"37",44:"36",45:"26",46:"16",47:"24",48:"25"}

