#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVT-1 Rev D -> Rev D1 deterministic migration (智元跃动 AI/AR V1.0).

Run once on an unmodified Rev D tree:  python3 rev_d1_apply.py <package_root>
Every edit made to NETLIST / BOM / PINMAP / SYSTEM_BUDGETS / TRANSLATOR_BANKS is coded here so that the
Rev D -> Rev D1 delta is reviewable line by line (see REV_D1_DEFECT_AND_FIX_LEDGER.md for the reasons and
DATASHEET_EVIDENCE_LEDGER.csv DS-08..DS-21 for the vendor sources). RTL / PCF / TB are NOT touched.
"""
import csv, json, sys, copy
from pathlib import Path

ROOT = Path(ROOT).resolve()  # set by transactional driver
TBL = ROOT / "02_BOM_PINMAP_ICD_Blocked"
ARCH = ROOT / "01_Architecture_and_Interfaces"
NET_IN = TBL / "NETLIST_ELECTRICAL_CONNECTION_REV_D.csv"
NET_OUT = TBL / "NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv"
F = ["Net", "Domain_V", "Board", "RefDes", "Pin", "Pin_Function", "Role", "BOM_Line", "I_Peak_A", "Note"]

def rd(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def wr(p, rows, fields):
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def R(net, dom, board, ref, pin, func, role, bom, ipk="", note=""):
    return dict(Net=net, Domain_V=str(dom), Board=board, RefDes=ref, Pin=str(pin), Pin_Function=func,
                Role=role, BOM_Line=bom, I_Peak_A=str(ipk), Note=note)

if NET_OUT.exists():
    sys.exit("Rev D1 netlist already present - migration already applied")
net = rd(NET_IN)

# ------------------------------------------------------------------ 1. translators: physical pin numbers
RJW = {"DIR1": "1", "A1": "2", "A2": "3", "A3": "4", "A4": "5", "A5": "6", "A6": "7", "A7": "8", "A8": "9",
       "DIR2": "10", "B8": "13", "B7": "14", "B6": "15", "B5": "16", "B4": "17", "B3": "18", "B2": "19",
       "B1": "20", "OE": "21", "VCCA": "24"}            # VCCB = 22 + 23, GND = 11 + 12 (TI SCES875C Table 4-1)
RSV_FUNC = {"A1": "1A1", "A2": "1A2", "A3": "2A1", "A4": "2A2", "B1": "1B1", "B2": "1B2", "B3": "2B1", "B4": "2B2",
            "1DIR": "1DIR", "2DIR": "2DIR", "VCCA": "VCCA", "VCCB": "VCCB"}
RSV = {"1OE": "1", "VCCB": "2", "VCCA": "3", "1DIR": "4", "2DIR": "5", "1A1": "6", "1A2": "7", "2A1": "8",
       "2A2": "9", "2B2": "12", "2B1": "13", "1B2": "14", "1B1": "15", "2OE": "16"}  # GND = 10 + 11 (TI SCES877B)
AXC8 = ["U8_LS1", "U8_PDM_LS", "U8_CAM_ISO1", "U8_CAM_ISO2"]
out, seen = [], set()
for r in net:
    ref = r["RefDes"]
    if ref in AXC8:
        p = r["Pin"]
        key = (ref, p)
        if key in seen:      # Rev D listed U8_CAM_ISO2 B6 twice
            continue
        seen.add(key)
        if p == "OE":
            r = dict(r, Pin="21", Pin_Function="OE", Note=(r["Note"] + "; OE active-low tied GND").strip("; "))
            out.append(r); continue
        if p == "VCCB":
            for pp in ("22", "23"):
                out.append(dict(r, Pin=pp, Pin_Function="VCCB"))
            out.append(R("GND", 0, r["Board"], ref, "11", "GND", "SINK", r["BOM_Line"]))
            out.append(R("GND", 0, r["Board"], ref, "12", "GND", "SINK", r["BOM_Line"]))
            continue
        if p in ("DIR1", "DIR2", "VCCA"):
            out.append(dict(r, Pin=RJW[p], Pin_Function=p, Note=(r["Note"] + "; " + r["Pin_Function"]).strip("; ")))
            continue
        out.append(dict(r, Pin=RJW[p], Pin_Function=p, Note=(r["Note"] + "; " + r["Pin_Function"]).strip("; ")))
        continue
    if ref == "U8_AUD_LS2":
        p = r["Pin"]
        if p == "1OE,2OE":
            out.append(dict(r, Pin="1", Pin_Function="1OE"))
            out.append(dict(r, Pin="16", Pin_Function="2OE"))
            continue
        fn = RSV_FUNC[p]
        out.append(dict(r, Pin=RSV[fn], Pin_Function=fn, Note=(r["Note"] + "; " + r["Pin_Function"]).strip("; ")))
        if p == "VCCB":
            out.append(R("GND", 0, r["Board"], ref, "10", "GND", "SINK", r["BOM_Line"]))
            out.append(R("GND", 0, r["Board"], ref, "11", "GND", "SINK", r["BOM_Line"]))
        continue
    out.append(r)
net = out

# ------------------------------------------------------------------ 2. remove rows that are rebuilt from datasheets
REBUILD = {"U10_AMP_L", "U10_AMP_R", "U3_L", "U3_R", "U9_IMU", "MK1_L", "MK2_C", "MK3_R", "U11_BLE",
           "U8_LS3", "U8_LS4", "U4_BB", "U4_1V8", "U4_1V2", "U4_1V8F", "U6_OPT_AVDD", "U5_LED2V8",
           "U6_CAM_DOVDD", "U6_CAM_DVDD", "U6_CAM_AVDD"}
net = [r for r in net if r["RefDes"] not in REBUILD]
L, B, A = "M-MAIN-L", "M-OPT-BRIDGE", "M-AUD-R"
add = []

# MAX98357A WLP-9 (ADI datasheet 19-6779 Rev 13, Pin Description): A1 SD_MODE, A2 VDD, A3 OUTP, B1 DIN,
# B2 GAIN_SLOT (inner bump), B3 OUTN, C1 BCLK, C2 GND, C3 LRCLK
for ref, bd, bom, vdd, sd, sp, dom in (("U10_AMP_L", L, "BOM-04", "VSYS", "AMP_SD_MODE_1V8", "SPK_L", 4.4),
                                      ("U10_AMP_R", A, "BOM-38", "VBAT_R_RET", "AMP_R_SD_MODE", "SPK_R", 4.2)):
    add += [R(sd, 1.8 if ref.endswith("L") else 1.06, bd, ref, "A1", "SD_MODE", "RCV", bom, "",
              "direct GPIO -> LEFT (>B2 1.5 V max)" if ref.endswith("L") else "69.8k RSMALL -> RIGHT (B1 0.825 V max .. B2 1.245 V min)"),
            R(vdd, dom, bd, ref, "A2", "VDD", "SINK", bom, "0.35", "10 uF + 0.1 uF at bump"),
            R(sp + "_P", dom, bd, ref, "A3", "OUTP", "DRV", bom),
            R("I2S_AMP_DIN_1V8", 1.8, bd, ref, "B1", "DIN", "RCV", bom),
            R("GND", 0, bd, ref, "B2", "GAIN_SLOT", "TIE", bom, "", "tied to adjacent C2 GND bump (12 dB, no via; ADI AN6643)"),
            R(sp + "_N", dom, bd, ref, "B3", "OUTN", "DRV", bom),
            R("I2S_BCLK_1V8", 1.8, bd, ref, "C1", "BCLK", "RCV", bom),
            R("GND", 0, bd, ref, "C2", "GND", "SINK", bom),
            R("I2S_LRCLK_1V8", 1.8, bd, ref, "C3", "LRCLK", "RCV", bom)]

# BQ25180 YBG-8 (TI SLUSE99C Table 6-1): A1 /INT, A2 IN, B1 SCL, B2 SYS, C1 SDA, C2 BAT, D1 TS/MR, D2 GND
add += [R("NC_CHG_L_INT", 1.8, L, "U3_L", "A1", "/INT", "NC", "BOM-20", "", "open-drain; no free host GPIO; status polled over I2C"),
        R("VBUS_5V", 5.0, L, "U3_L", "A2", "IN", "SINK", "BOM-20", "0.5", "1 uF (25 V) at pin"),
        R("SYS_I2C_SCL_1V8", 1.8, L, "U3_L", "B1", "SCL", "BIDIR_OD", "BOM-20", "", "7-bit addr 0x6A"),
        R("VOUT_L_PPATH", 4.5, L, "U3_L", "B2", "SYS", "SRC", "BOM-20", "1.2", "SYS_REG default 4.5 V (> VBAT_R max 4.2 V) keeps LM66200 priority; 10 uF"),
        R("SYS_I2C_SDA_1V8", 1.8, L, "U3_L", "C1", "SDA", "BIDIR_OD", "BOM-20"),
        R("VBAT_L", 4.2, L, "U3_L", "C2", "BAT", "BIDIR", "BOM-20", "1.0", "1 uF"),
        R("NTC_TS_L", 0.4, L, "U3_L", "D1", "TS/MR", "RCV", "BOM-20", "", "10k NTC in pack (38 uA bias); TS must not float (charge suspends)"),
        R("GND", 0, L, "U3_L", "D2", "GND", "SINK", "BOM-20"),
        R("NTC_TS_L", 0.4, L, "TP_NTC_L", "1", "solder pad NTC (left pack)", "PASSIVE", "BOM-43")]

# BQ25170 DSG-8 (TI SLUSDJ8A Table 5-1): 1 IN, 2 ISET, 3 TS, 4 GND, 5 /PG, 6 STAT, 7 VSET, 8 OUT, EP
add += [R("VBUS_5V", 5.0, A, "U3_R", "1", "IN", "SINK", "BOM-37"),
        R("CHG_R_ISET", 0.3, A, "U3_R", "2", "ISET", "PASSIVE", "BOM-37", "", "R_ISET_R 5.49k -> 54.6 mA (KISET 300 AOhm, range 375R..30k)"),
        R("NTC_TS_R", 1.0, A, "U3_R", "3", "TS", "RCV", "BOM-37"),
        R("GND", 0, A, "U3_R", "4", "GND", "SINK", "BOM-37"),
        R("NC_CHG_R_PG", 1.8, A, "U3_R", "5", "/PG", "NC", "BOM-37", "", "open-drain, unused"),
        R("NC_CHG_R_STAT", 1.8, A, "U3_R", "6", "STAT", "NC", "BOM-37", "", "open-drain, unused"),
        R("CHG_R_VSET", 0.5, A, "U3_R", "7", "VSET", "PASSIVE", "BOM-37", "", "R_VSET_R 27k 1% -> 4.20 V (Table 7-1)"),
        R("VBAT_R_RET", 4.2, A, "U3_R", "8", "OUT", "SRC", "BOM-37", "", "battery node"),
        R("GND", 0, A, "U3_R", "EP", "Thermal pad", "SINK", "BOM-37"),
        R("CHG_R_ISET", 0.3, A, "R_ISET_R", "1", "5.49k 1%", "PASSIVE", "BOM-53"),
        R("GND", 0, A, "R_ISET_R", "2", "5.49k 1%", "PASSIVE", "BOM-53"),
        R("CHG_R_VSET", 0.5, A, "R_VSET_R", "1", "27k 1%", "PASSIVE", "BOM-53"),
        R("GND", 0, A, "R_VSET_R", "2", "27k 1%", "PASSIVE", "BOM-53")]

# ICM-42688-P LGA-14 (TDK DS-000347 sec.4.1 as reproduced by two independent library sources)
imu = {"1": ("AP_SDO/AP_AD0", "GND", "TIE", "AD0=0 -> 7-bit addr 0x68"),
       "2": ("RESV", "NC_IMU_2", "NC", ""), "3": ("RESV", "NC_IMU_3", "NC", ""),
       "4": ("INT1/INT", "NC_IMU_INT1", "NC", "no free FPGA/host input; data-ready polled over I2C"),
       "5": ("VDDIO", "1V8_FPGA_IO", "SINK", "10 nF"), "6": ("GND", "GND", "SINK", ""),
       "7": ("RESV", "GND", "TIE", "RESV pin 7 -> GND"), "8": ("VDD", "1V8_FPGA_IO", "SINK", "0.1 uF + 2.2 uF"),
       "9": ("INT2/FSYNC/CLKIN", "FPGA_CDONE_VSYNC_N", "RCV", "configure pin 9 as FSYNC, falling edge (Rev D had pin 11 = RESV)"),
       "10": ("RESV", "NC_IMU_10", "NC", ""), "11": ("RESV", "NC_IMU_11", "NC", ""),
       "12": ("AP_CS", "1V8_FPGA_IO", "TIE", "AP_CS high = I2C mode"),
       "13": ("AP_SCL/AP_SCLK", "SYS_I2C_SCL_1V8", "BIDIR_OD", ""),
       "14": ("AP_SDA/AP_SDIO/AP_SDI", "SYS_I2C_SDA_1V8", "BIDIR_OD", "")}
for p, (fn, n, role, note) in imu.items():
    add.append(R(n, 0 if n == "GND" else 1.8, B, "U9_IMU", p, fn, role, "BOM-30", "", note))

# IM69D130 LGA-5 (Infineon DS v1.0 Table 7): 1 DATA, 2 VDD, 3 CLOCK, 4 SELECT, 5 GND
for ref, bd, bom, vdd, data, sel, role in (("MK1_L", L, "BOM-14", "1V8_SYS", "PDM_D0_1V8", "GND", "DRV_TRI_SLOT"),
                                          ("MK2_C", B, "BOM-34", "1V8_FPGA_IO", "PDM_D0_1V8", "1V8_FPGA_IO", "DRV_TRI_SLOT"),
                                          ("MK3_R", A, "BOM-39", "1V8_SYS", "PDM_D1_1V8", "GND", "DRV")):
    add += [R(data, 1.8, bd, ref, "1", "DATA", role, bom, "", "tDV <= 100 ns, tDD 40..80 ns, tHZ 5..30 ns"),
            R(vdd, 1.8, bd, ref, "2", "VDD", "SINK", bom, "", "100 nF at VDD"),
            R("PDM_CLK_1V8", 1.8, bd, ref, "3", "CLOCK", "RCV", bom),
            R(sel, 0 if sel == "GND" else 1.8, bd, ref, "4", "SELECT", "TIE", bom, "", "SELECT=" + ("GND" if sel == "GND" else "VDD")),
            R("GND", 0, bd, ref, "5", "GND", "SINK", bom)]

# PCA9306 DQE (TI SCPS113O Table 5-1): 1 GND, 2 VREF1, 3 SCL1, 4 SDA1, 5 SDA2, 6 SCL2, 7 VREF2, 8 EN
for ref, bom, v1, s1c, s1d, tag in (("U8_LS3", "BOM-03", "1V8_SYS", "SYS_I2C_SCL_1V8", "SYS_I2C_SDA_1V8", "LS3"),
                                   ("U8_LS4", "BOM-48", "CAM_DOVDD_1V8", "CAM_SCCB_SCL", "CAM_SCCB_SDA", "LS4")):
    add += [R("GND", 0, L, ref, "1", "GND", "SINK", bom),
            R(v1, 1.8, L, ref, "2", "VREF1", "SINK", bom, "", "gated DOVDD: 0 V => isolated" if tag == "LS4" else ""),
            R(s1c, 1.8, L, ref, "3", "SCL1", "BIDIR_OD", bom), R(s1d, 1.8, L, ref, "4", "SDA1", "BIDIR_OD", bom),
            R("SYS_I2C_SDA_3V3", 3.3, L, ref, "5", "SDA2", "BIDIR_OD", bom), R("SYS_I2C_SCL_3V3", 3.3, L, ref, "6", "SCL2", "BIDIR_OD", bom),
            R(tag + "_VREF2_EN", 3.3, L, ref, "7", "VREF2", "SINK", bom, "", "VREF2 tied to EN (TI typical application)"),
            R(tag + "_VREF2_EN", 3.3, L, ref, "8", "EN", "RCV", bom),
            R(tag + "_VREF2_EN", 3.3, L, "R_" + tag + "_EN", "1", "200k", "PULLUP", "BOM-24" if tag == "LS3" else "BOM-49"),
            R("3V3_SYS", 3.3, L, "R_" + tag + "_EN", "2", "200k", "PASSIVE", "BOM-24" if tag == "LS3" else "BOM-49")]

# TLV755P DQN (TI SBVS320D): 1 OUT, 2 GND, 3 EN, 4 IN
ldo = [("U4_1V2", B, "BOM-32", "VSYS", "VSYS", "1V2_FPGA_CORE", 4.4, 1.2, "EN tied IN"),
       ("U4_1V8F", B, "BOM-46", "VSYS", "1V2_FPGA_PLL", "1V8_FPGA_IO", 4.4, 1.8, "EN from VCCPLL (>=1.082 V > VHI 1.0 V)"),
       ("U6_OPT_AVDD", B, "BOM-45", "VSYS", "OPT_AVDD_EN", "AVDD_OPT_BIAS", 4.4, 2.8, "120R active discharge"),
       ("U5_LED2V8", L, "BOM-10", "3V3_SYS", "CAM_PWR_REQ", "LED_2V8", 3.3, 2.8, ""),
       ("U6_CAM_DOVDD", L, "BOM-11", "3V3_SYS", "PRIV_WINDOW_OK_F", "CAM_DOVDD_1V8", 3.3, 1.8, "120R discharge"),
       ("U6_CAM_DVDD", L, "BOM-12", "3V3_SYS", "PRIV_WINDOW_OK_F", "CAM_DVDD_1V2", 3.3, 1.2, "120R discharge"),
       ("U6_CAM_AVDD", L, "BOM-13", "3V3_SYS", "PRIV_WINDOW_OK_F", "CAM_AVDD_2V8", 3.3, 2.8, "120R discharge")]
for ref, bd, bom, vin, en, vout, dvin, dvout, note in ldo:
    add += [R(vout, dvout, bd, ref, "1", "OUT", "SRC", bom, "", note),
            R("GND", 0, bd, ref, "2", "GND", "SINK", bom),
            R(en, 1.8, bd, ref, "3", "EN", "RCV", bom),
            R(vin, dvin, bd, ref, "4", "IN", "SINK", bom)]

# TPS63805 YFF-15 (TI SLVSDS9E Fig 7-1 / Table 7-1): A1 EN, B1 MODE, C1 AGND, D1 FB, E1 PG,
# A2/A3 VIN, B2/B3 L1, C2/C3 GND, D2/D3 L2, E2/E3 VOUT
bb = [("A1", "EN", "VSYS", "TIE", "EN tied VIN (must not float)"), ("B1", "MODE", "GND", "TIE", "power-save mode"),
      ("C1", "AGND", "GND", "SINK", ""), ("D1", "FB", "BB_FB", "PASSIVE", "R_FB1 560k (VOUT) / R_FB2 100k (GND): 0.5 V x 6.6 = 3.30 V"),
      ("E1", "PG", "NC_BB_PG", "NC", "open-drain, unused"),
      ("A2", "VIN", "VSYS", "SINK", "CIN eff >= 4 uF"), ("A3", "VIN", "VSYS", "SINK", ""),
      ("B2", "L1", "BB_L1", "PASSIVE", ""), ("B3", "L1", "BB_L1", "PASSIVE", ""),
      ("C2", "GND", "GND", "SINK", ""), ("C3", "GND", "GND", "SINK", ""),
      ("D2", "L2", "BB_L2", "PASSIVE", ""), ("D3", "L2", "BB_L2", "PASSIVE", ""),
      ("E2", "VOUT", "3V3_SYS", "SRC", "COUT eff >= 7 uF (22 uF nom)"), ("E3", "VOUT", "3V3_SYS", "SRC", "")]
for p, fn, n, role, note in bb:
    add.append(R(n, 0 if n in ("GND",) else (3.3 if n == "3V3_SYS" else 4.4), L, "U4_BB", p, fn, role, "BOM-06", "", note))
add += [R("BB_L1", 4.4, L, "L1_BB", "1", "0.47 uH", "PASSIVE", "BOM-07"), R("BB_L2", 3.3, L, "L1_BB", "2", "0.47 uH", "PASSIVE", "BOM-07"),
        R("3V3_SYS", 3.3, L, "R_BB_FB1", "1", "560k 1%", "PASSIVE", "BOM-24"), R("BB_FB", 0.5, L, "R_BB_FB1", "2", "560k 1%", "PASSIVE", "BOM-24"),
        R("BB_FB", 0.5, L, "R_BB_FB2", "1", "100k 1%", "PASSIVE", "BOM-24"), R("GND", 0, L, "R_BB_FB2", "2", "100k 1%", "PASSIVE", "BOM-24")]

# TPS62840 DLC-8 (TI SLVSEC6D: VIN=2, VSET=5, VOS=8 confirmed; 1 GND, 3 MODE, 4 EN, 6 STOP, 7 SW from pin figure)
b1 = [("1", "GND", "GND", "SINK", ""), ("2", "VIN", "VSYS", "SINK", "CIN 4.7 uF"), ("3", "MODE", "GND", "TIE", "auto PFM/PWM"),
      ("4", "EN", "VSYS", "TIE", "always on (internal 450k pull-down overridden)"), ("5", "VSET", "BK_VSET", "PASSIVE", "RSET per SLVSEC6D Table 1 for 1.8 V (E96, 1%)"),
      ("6", "STOP", "GND", "TIE", ""), ("7", "SW", "BK_SW", "PASSIVE", ""), ("8", "VOS", "1V8_SYS", "RCV", "sense at COUT 10 uF")]
for p, fn, n, role, note in b1:
    add.append(R(n, 0 if n == "GND" else (1.8 if n in ("1V8_SYS",) else 4.4), L, "U4_1V8", p, fn, role, "BOM-08", "", note))
add += [R("BK_SW", 4.4, L, "L2_1V8", "1", "2.2 uH", "PASSIVE", "BOM-09"),
        R("1V8_SYS", 1.8, L, "L2_1V8", "2", "2.2 uH (output node, 1V8_SYS source)", "SRC", "BOM-09", "0.4", "buck output delivered through L2"),
        R("BK_VSET", 0.0, L, "R_VSET_1V8", "1", "RSET(1.8 V)", "PASSIVE", "BOM-24"), R("GND", 0, L, "R_VSET_1V8", "2", "RSET(1.8 V)", "PASSIVE", "BOM-24")]

# ESP32-S3-PICO-1: Pin 1 LNA_IN, Pin 4 CHIP_PU ("Do not leave the CHIP_PU pin floating") - absent in Rev D
add += [R("ESP_RF_ANT", 0, L, "U1_HOST", "Pin 1", "LNA_IN", "PASSIVE", "BOM-02", "", "RF matching is inside the SiP; RN_ESP_RF = antenna tuning pi only"),
        R("ESP_RF_ANT", 0, L, "RN_ESP_RF", "1", "pi-network port A (values tuned on VNA)", "PASSIVE", "BOM-01"),
        R("ESP_ANT_FEED", 0, L, "RN_ESP_RF", "2", "pi-network port B", "PASSIVE", "BOM-01"),
        R("ESP_ANT_FEED", 0, L, "ANT1", "FEED", "feed terminal (second terminal per Johanson drawing)", "PASSIVE", "BOM-01"),
        R("ESP_CHIP_PU", 3.3, L, "U1_HOST", "Pin 4", "CHIP_PU", "RCV", "BOM-02", "", "RC delay: R_CHIP_PU to 3V3_SYS + C_CHIP_PU to GND (values per Espressif HW design guidelines)"),
        R("ESP_CHIP_PU", 3.3, L, "R_CHIP_PU", "1", "10k to 3V3_SYS", "PULLUP", "BOM-24"),
        R("3V3_SYS", 3.3, L, "R_CHIP_PU", "2", "10k", "PASSIVE", "BOM-24"),
        R("ESP_CHIP_PU", 3.3, L, "C_CHIP_PU", "1", "1 uF to GND", "PASSIVE", "BOM-24"),
        R("ESP_CHIP_PU", 3.3, L, "TP_ESP_EN", "1", "test pad (reset/boot fixture)", "PASSIVE", "BOM-58"),
        R("QSPI_DIR1_EN", 3.3, L, "TP_ESP_BOOT", "1", "test pad on GPIO0 (download mode)", "PASSIVE", "BOM-58")]

# nRF5340-CMAA WLCSP-95 (Nordic nRF5340 PS, Table 3 WLCSP pin assignments)
N = "U11_BLE"
func = [("K5", "P0.20", "I2S_BCLK_1V8", "DRV", "I2S SCK (PSEL)"), ("K4", "P0.22", "I2S_LRCLK_1V8", "DRV", "I2S LRCK (PSEL)"),
        ("J4", "P0.21", "I2S_AMP_DIN_1V8", "DRV", "I2S SDOUT (PSEL)"), ("J5", "P0.19", "I2S_S3_DOUT_1V8", "RCV", "I2S SDIN (PSEL)"),
        ("K3", "P1.04", "IPC_NRF_TX_1V8", "DRV", "UARTE TXD (PSEL)"), ("L3", "P1.05", "IPC_S3_TX_1V8", "RCV", "UARTE RXD (PSEL), pull-up enabled"),
        ("K2", "P0.24", "AMP_SD_MODE_1V8", "DRV", "GPIO, standard drive")]
for ball, gpio, n, role, note in func:
    add.append(R(n, 1.8, A, N, ball, gpio, role, "BOM-36", "", note + "; ball chosen away from ANT(D1)/XC1-XC2(A1-A2), QSPI, TRACE and NFC pins"))
for ball in ("A3", "B7", "B10", "D2", "E11", "H11", "K1", "L5", "L11"):
    add.append(R("1V8_SYS", 1.8, A, N, ball, "VDD", "SINK", "BOM-36", "0.03" if ball == "A3" else "", "decouple per PS reference circuitry"))
add.append(R("1V8_SYS", 1.8, A, N, "B12", "VDDH", "SINK", "BOM-36", "", "VDD-supplied (normal voltage) configuration: VDDH tied to VDD per PS supply configuration - KIMI verify against PS circuit configuration table"))
for ball in ("A5", "B2", "B9", "C2", "D12", "E5", "E6", "E7", "E8", "F5", "F6", "F7", "F8", "G6", "G7", "G8"):
    add.append(R("GND", 0, A, N, ball, "VSS", "SINK", "BOM-36"))
for ball in ("G5", "K6", "K11"):
    add.append(R("GND", 0, A, N, ball, "AVSS", "SINK", "BOM-36"))
for ball, fn in (("B8", "DECA"), ("A7", "DECD"), ("B5", "DECN"), ("B4", "DECR"), ("B1", "DECRF"), ("C11", "DECUSB")):
    add.append(R("NRF_" + fn, 1.0, A, N, ball, fn, "PASSIVE", "BOM-36", "", "decoupling capacitor per PS reference circuitry (RN_BLE_RF)"))
    add.append(R("NRF_" + fn, 1.0, A, "RN_BLE_RF", fn, "decoupling C (value per PS)", "PASSIVE", "BOM-56"))
for ball, fn in (("B6", "DCC"), ("A9", "DCCD"), ("D11", "DCCH")):
    add.append(R("NRF_" + fn, 1.0, A, N, ball, fn, "NC", "BOM-36", "", "LDO mode (DC/DC off). If DC/DC is enabled add the PS reference inductors"))
add += [R("NC_NRF_VBUS", 0, A, N, "B11", "VBUS", "NC", "BOM-36", "", "USB unused; handle per PS"),
        R("NC_NRF_DM", 0, A, N, "A11", "D-", "NC", "BOM-36"), R("NC_NRF_DP", 0, A, N, "A12", "D+", "NC", "BOM-36"),
        R("NC_NRF_XL1", 0, A, N, "F11", "P0.00/XL1", "NC", "BOM-36", "", "no 32.768 kHz crystal: LFRC + calibration"),
        R("NC_NRF_XL2", 0, A, N, "F12", "P0.01/XL2", "NC", "BOM-36"),
        R("BLE_XC1", 0.5, A, N, "A1", "XC1", "PASSIVE", "BOM-36", "", "32 MHz crystal (required by RADIO)"),
        R("BLE_XC2", 0.5, A, N, "A2", "XC2", "PASSIVE", "BOM-36"),
        R("BLE_XC1", 0.5, A, "Y2_BLE", "X1", "crystal terminal", "PASSIVE", "BOM-55"),
        R("BLE_XC2", 0.5, A, "Y2_BLE", "X2", "crystal terminal", "PASSIVE", "BOM-55"),
        R("GND", 0, A, "Y2_BLE", "CASE", "case/GND pads per crystal drawing", "SINK", "BOM-55"),
        R("BLE_RF_ANT", 0, A, N, "D1", "ANT", "PASSIVE", "BOM-36", "", "single-ended 50 ohm; matching per PS reference circuitry"),
        R("BLE_RF_ANT", 0, A, "RN_BLE_RF", "RF_A", "matching network port A", "PASSIVE", "BOM-56"),
        R("BLE_ANT_FEED", 0, A, "RN_BLE_RF", "RF_B", "matching network port B / antenna tuning", "PASSIVE", "BOM-56"),
        R("BLE_ANT_FEED", 0, A, "ANT2_BLE", "FEED", "feed terminal", "PASSIVE", "BOM-35"),
        R("BLE_SWDIO", 1.8, A, N, "F1", "SWDIO", "BIDIR", "BOM-36"), R("BLE_SWDCLK", 1.8, A, N, "F2", "SWDCLK", "RCV", "BOM-36"),
        R("BLE_NRESET", 1.8, A, N, "G2", "nRESET", "RCV", "BOM-36", "", "internal pull-up"),
        R("BLE_SWDIO", 1.8, A, "TP_SWD_R", "SWDIO", "programming pad", "PASSIVE", "BOM-57"),
        R("BLE_SWDCLK", 1.8, A, "TP_SWD_R", "SWDCLK", "programming pad", "PASSIVE", "BOM-57"),
        R("BLE_NRESET", 1.8, A, "TP_SWD_R", "nRESET", "programming pad", "PULLUP", "BOM-57", "", "nRESET has internal pull-up"),
        R("1V8_SYS", 1.8, A, "TP_SWD_R", "VTREF", "programming pad", "PASSIVE", "BOM-57"),
        R("GND", 0, A, "TP_SWD_R", "GND", "programming pad", "PASSIVE", "BOM-57")]

net += add
net = [r for r in net if not (r["RefDes"] == "R_SDR")] + [
    R("AMP_SD_MODE_1V8", 1.8, A, "R_SDR", "1", "69.8k 1%", "PASSIVE", "BOM-53"),
    R("AMP_R_SD_MODE", 1.06, A, "R_SDR", "2", "69.8k 1%", "PASSIVE", "BOM-53")]
wr(NET_OUT, net, F)
# Rev D remains available for inherited comparison; active netlist is Rev D1.
print("netlist rows:", len(net))
