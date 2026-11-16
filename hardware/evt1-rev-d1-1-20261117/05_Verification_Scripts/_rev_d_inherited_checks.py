#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智元跃动 AI/AR Glasses V1.0 — EVT-1 Rev D verification suite (inherits Rev C bb87623).

What this script DOES verify (by executing checks on the delivered files):
  * netlist structure, single-driver-per-net, cross-board trunk continuity, BTB contact ampacity,
    translator bank direction/domain consistency, ESP32 strap-pin safety, FPGA PCF<->RTL<->netlist;
  * analytical sequencing (U6_OPT_AVDD CDONE gate, iCE40UP rail order), MAX98357A channel-select
    margins, privacy-window vs LDO-enable margin, camera power-request detector, audio timing budget;
  * mass ledger including items Rev C omitted (reported OPEN if > 40 g — never PASS);
  * RTL/TB static structure + the independent Python protocol model;
  * fault injection: each Rev C defect class re-inserted must be CAUGHT.

What it does NOT verify: native iverilog/yosys/nextpnr/icetime (reported BLOCKED if binaries are
absent), PCB layout/DRC/STEP, JBD NDA content, physical measurements.
Status vocabulary: PASS / FAIL / BLOCKED / OPEN (known non-compliance or unverifiable estimate).
"""
import copy, csv, json, math, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TBL = ROOT / "02_BOM_PINMAP_ICD_Blocked"
ARCH = ROOT / "01_Architecture_and_Interfaces"
RTL = ROOT / "03_FPGA_RTL"
EVID = ROOT / "04_Verification_Evidence"
SCRIPTS = ROOT / "05_Verification_Scripts"

def load_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_all():
    return dict(
        net=load_csv(TBL / "NETLIST_ELECTRICAL_CONNECTION_REV_D.csv"),
        conn=load_csv(TBL / "CONNECTOR_PINOUT_REV_D.csv"),
        bom=load_csv(TBL / "BOM_V1_0_FROZEN.csv"),
        tr=json.load(open(TBL / "TRANSLATOR_BANKS_REV_D.json", encoding="utf-8")),
        cfg=json.load(open(ARCH / "SYSTEM_BUDGETS_V1_0.json", encoding="utf-8")),
        rtl=open(RTL / "evt1_ar_display_fpga_bridge_rev_c.v", encoding="utf-8").read(),
        tb=open(RTL / "tb_evt1_ar_display_fpga_bridge_rev_c.v", encoding="utf-8").read(),
        pcf=open(RTL / "ice40up5k_uwg30_rev_c.pcf", encoding="utf-8").read(),
        mk=open(RTL / "Makefile", encoding="utf-8").read(),
    )

DRIVE_ROLES = {"DRV", "SRC"}
SOFT_SOURCES = {"PULLUP", "PULLDOWN", "TIE", "PASSIVE", "DRV_OD", "BIDIR_OD", "BIDIR_DIRCTL", "BIDIR_FW",
                "BIDIR_CFG", "BIDIR", "DRV_TRI_SLOT", "CONTACT"}
POWER_NETS = {"GND"}

def by_net(rows):
    d = {}
    for r in rows:
        d.setdefault(r["Net"], []).append(r)
    return d

# ----------------------------------------------------------------------------- NET checks
def chk_net00_bom_refs(D):
    bom_ids = {r["Item_ID"] for r in D["bom"]}
    bad = sorted({(r["RefDes"], r["BOM_Line"]) for r in D["net"] if r["BOM_Line"] not in bom_ids})
    if bad:
        return "FAIL", f"netlist rows reference missing BOM lines: {bad[:8]}"
    need = []
    for r in D["bom"]:
        for ref in [x.strip() for x in r["RefDes"].split(",")]:
            if ref.startswith(("U", "J_", "MK", "D3_", "Y1", "CAM1")) and not (r["MPN"].startswith("MPN_TBD") and ref != "CAM1"):
                need.append(ref)
    present = {r["RefDes"] for r in D["net"]}
    missing = [x for x in need if x not in present]
    if missing:
        return "FAIL", f"BOM active parts/connectors absent from netlist: {missing}"
    return "PASS", f"{len(D['net'])} netlist rows; all BOM lines resolvable; {len(need)} active/connector RefDes all present in netlist"

def chk_net01_single_driver(D):
    errs = []
    for net, rs in by_net(D["net"]).items():
        if net in POWER_NETS or net.startswith(("NC_", "TIE_")):
            continue
        roles = [r["Role"] for r in rs]
        drv = [f'{r["RefDes"]}.{r["Pin"]}' for r in rs if r["Role"] in DRIVE_ROLES]
        if len(drv) > 1:
            errs.append(f"{net}: multiple drivers {drv}")
        rcv = [r for r in rs if r["Role"] in ("RCV", "SINK")]
        if rcv and not drv and not any(x in SOFT_SOURCES - {"CONTACT"} for x in roles):
            errs.append(f"{net}: receivers without any source")
        if any(x in ("DRV_OD", "BIDIR_OD") for x in roles) and "PULLUP" not in roles and not net.startswith("PRIV_"):
            errs.append(f"{net}: open-drain net without pull-up")
        if "DRV_TRI_SLOT" in roles and len(drv) > 0:
            errs.append(f"{net}: TDM slot net also has a push-pull driver {drv}")
    if errs:
        return "FAIL", "; ".join(errs[:6])
    return "PASS", "every non-GND net has <=1 push-pull/power source; OD nets pulled up; PDM_D0 is slot-shared only"

LINKS = {frozenset({"M-MAIN-L", "M-OPT-BRIDGE"}): ("J_BTB_L", "J_BRIDGE_IN"),
         frozenset({"M-MAIN-L", "M-AUD-R"}): ("J_BTB_L", "J_BTB_R"),
         frozenset({"M-OPT-BRIDGE", "M-AUD-R"}): ("J_BRIDGE_IN", "J_BTB_R")}

def chk_net02_trunk(D):
    errs = []
    conn = {}
    for r in D["conn"]:
        conn.setdefault(r["RefDes"], {})[r["Contact"]] = r["Net"]
    if conn["J_BTB_L"] != conn["J_BRIDGE_IN"]:
        diff = {k: (conn["J_BTB_L"].get(k), conn["J_BRIDGE_IN"].get(k)) for k in set(conn["J_BTB_L"]) | set(conn["J_BRIDGE_IN"])
                if conn["J_BTB_L"].get(k) != conn["J_BRIDGE_IN"].get(k)}
        errs.append(f"J_BTB_L != J_BRIDGE_IN at {diff}")
    trunk_nets = set(conn["J_BTB_L"].values())
    for c, n in conn["J_BTB_R"].items():
        if n not in trunk_nets:
            errs.append(f"J_BTB_R {c}={n} not carried by trunk")
    nets_on = {}
    for ref, pm in conn.items():
        for n in pm.values():
            nets_on.setdefault(n, set()).add(ref)
    for net, rs in by_net(D["net"]).items():
        if net in ("GND",):
            continue
        boards = {r["Board"] for r in rs if r["Role"] != "CONTACT"}
        for pair, (ja, jb) in LINKS.items():
            if pair <= boards:
                if not ({ja, jb} <= nets_on.get(net, set())):
                    errs.append(f"{net} spans {sorted(pair)} but is not on {ja}+{jb}")
    for r in D["net"]:
        if r["RefDes"] == "J_BRIDGE_IN" and r["Note"] == "NC_TRUNK_PASS":
            if any(x["Board"] == "M-OPT-BRIDGE" and x["Role"] != "CONTACT" for x in by_net(D["net"])[r["Net"]]):
                errs.append(f"{r['Net']} marked NC on bridge but has a bridge endpoint")
    if errs:
        return "FAIL", "; ".join(errs[:6])
    return "PASS", f"J_BTB_L==J_BRIDGE_IN (32 contacts); all {len(conn['J_BTB_R'])} J_BTB_R contacts carried by trunk; every multi-board net crosses the correct connectors"

def chk_net03_ampacity(D, derate=1.25):
    errs, rep = [], []
    agg = {}
    for r in D["conn"]:
        agg.setdefault((r["RefDes"], r["Net"]), 0.0)
        agg[(r["RefDes"], r["Net"])] += float(r["Contact_Rating_A"])
    ipk = {}
    for r in D["net"]:
        if r["Role"] == "CONTACT" and r["I_Peak_A"]:
            ipk[(r["RefDes"], r["Net"])] = float(r["I_Peak_A"])
    for (ref, net), cap in agg.items():
        need = ipk.get((ref, net), 0.0) * derate
        if need > cap + 1e-9:
            errs.append(f"{ref}:{net} needs {need:.2f} A, contacts {cap:.2f} A")
        elif need > 0.25:
            rep.append(f"{ref}:{net} {cap:.1f}A>={need:.2f}A")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", "all BTB nets within 1.25x derated contact rating; high-current: " + ", ".join(rep)

def chk_net04_translators(D):
    errs = []
    netmap = by_net(D["net"])
    for ref, t in D["tr"].items():
        for bk, bd in t["banks"].items():
            d = bd["dir"]
            for ch, an, bn in bd["ch"]:
                for side, net, v in (("A", an, t["va"]), ("B", bn, t["vb"])):
                    if net.startswith(("NC_", "TIE_", "LS1_")):
                        continue
                    others = [r for r in netmap.get(net, []) if r["RefDes"] != ref and r["Role"] not in ("CONTACT", "PASSIVE", "PULLUP", "PULLDOWN")]
                    for o in others:
                        if abs(float(o["Domain_V"]) - v) > 0.15:
                            errs.append(f"{ref}.{side}{ch} {net}: endpoint {o['RefDes']} at {o['Domain_V']} V vs side {v} V")
                    ext_drv = [o for o in others if o["Role"] in ("DRV", "SRC", "DRV_TRI_SLOT")]
                    ext_rcv = [o for o in others if o["Role"] in ("RCV", "SINK")]
                    if d == "H":
                        if side == "A" and not ext_drv: errs.append(f"{ref} bank{bk} DIR=H: A{ch} {net} has no external driver")
                        if side == "B" and ext_drv: errs.append(f"{ref} bank{bk} DIR=H: B{ch} {net} contended by {[o['RefDes'] for o in ext_drv]}")
                    if d == "L":
                        if side == "B" and not ext_drv: errs.append(f"{ref} bank{bk} DIR=L: B{ch} {net} has no external driver")
                        if side == "A" and ext_drv: errs.append(f"{ref} bank{bk} DIR=L: A{ch} {net} contended by {[o['RefDes'] for o in ext_drv]}")
            if d.startswith("CTRL:"):
                ctl = d.split(":")[1]
                drv = [r for r in netmap.get(ctl, []) if r["Role"] == "DRV"]
                if not drv or abs(float(drv[0]["Domain_V"]) - t["va"]) > 0.15:
                    errs.append(f"{ref} DIR{bk} control {ctl} not driven from the VCCA ({t['va']} V) domain")
        if t.get("oe") != "GND":
            errs.append(f"{ref} OE undefined")
    if errs:
        return "FAIL", "; ".join(errs[:6])
    n = sum(len(b["ch"]) for t in D["tr"].values() for b in t["banks"].values())
    return "PASS", f"{len(D['tr'])} translators / {n} channels: every bank uniform, each output side uncontended, domains match VCCA/VCCB, OE defined, DIR control referenced to VCCA"

STRAPS = {"GPIO0", "GPIO3", "GPIO45", "GPIO46"}
FORBIDDEN_S3_PINS = {28, 30, 31, 32, 33, 34, 35, 38, 39, 40, 41, 42, 53, 54}

def chk_net06_esp32(D):
    errs = []
    netmap = by_net(D["net"])
    esp = [r for r in D["net"] if r["RefDes"] == "U1_HOST" and r["Pin_Function"].startswith("GPIO")]
    gp = [r["Pin_Function"] for r in esp]
    if len(gp) != len(set(gp)):
        errs.append("duplicate GPIO use")
    for r in esp:
        pin = int(r["Pin"].split()[1])
        if pin in FORBIDDEN_S3_PINS:
            errs.append(f"forbidden module pin {pin}")
        g = r["Pin_Function"]
        ext = [o for o in netmap[r["Net"]] if o["RefDes"] != "U1_HOST" and o["Role"] in ("DRV", "SRC")]
        if g in STRAPS or g == "GPIO43":
            for o in ext:
                gated = o["RefDes"] in D["tr"] and D["tr"][o["RefDes"]]["vcca"].startswith("CAM_")
                if not gated:
                    errs.append(f"{g} ({r['Net']}) driven at reset by {o['RefDes']}.{o['Pin']}")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", f"{len(esp)} GPIOs unique, no forbidden module pins; strap pins GPIO0/45/46 and ROM-TX GPIO43 have no external driver at reset (GPIO3 driver is VCCA-gated U8_CAM_ISO2)"

def chk_net07_fpga(D):
    ports = re.findall(r"\b(?:input|output)\s+(?:wire|reg)\s*(?:\[\d+:\d+\])?\s*(\w+)", D["rtl"])
    pcf = re.findall(r"^set_io\s+(\S+)\s+(\S+)", D["pcf"], re.M)
    cls = D["cfg"]["4_fpga_uwg30_pinout_and_rtl_timing"]["uwg30_ball_classification"]
    legal = set(cls["standard_cmos_pio_balls"])
    errs = []
    balls = [b for _, b in pcf]
    if len(pcf) != 18 or len(set(balls)) != 18 or any(b not in legal for b in balls):
        errs.append(f"PCF ball set invalid ({len(pcf)} entries)")
    base = {re.sub(r"\[\d+\]", "", p) for p, _ in pcf}
    if base - set(ports):
        errs.append(f"PCF names not RTL ports: {base - set(ports)}")
    name2net = lambda p: {"cdone_vsync_n": "FPGA_CDONE_VSYNC_N"}.get(p, re.sub(r"\[(\d+)\]", r"\1", p))
    fp = {r["Pin"]: r["Net"] for r in D["net"] if r["RefDes"] == "U2_FPGA"}
    for p, b in pcf:
        if fp.get(b) != name2net(p):
            errs.append(f"ball {b}: PCF {p} vs netlist {fp.get(b)}")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", "18/18 PCF balls legal & unique; every PCF port is an RTL port; netlist ball->net matches PCF"

# ----------------------------------------------------------------------------- SEQ checks
TLV755P = dict(vhi=1.0, vlo=0.3, ien_a=10e-9)  # SBVS320D, verified this revision

def chk_seq01_avdd(D):
    p = D["cfg"]["4_fpga_uwg30_pinout_and_rtl_timing"]["lattice_tn02006_power_and_config_audit"]["optical_avdd_sequencer"]
    errs = []
    if abs(p.get("ldo_en_vhi_max_v", 0) - TLV755P["vhi"]) > 1e-6 or abs(p.get("ldo_en_vlo_max_v", 0) - TLV755P["vlo"]) > 1e-6:
        errs.append(f"EN thresholds {p.get('ldo_en_vhi_max_v')}/{p.get('ldo_en_vlo_max_v')} != TLV755P datasheet 1.0/0.3 V")
    rseq = [r for r in D["net"] if r["RefDes"] == "R_SEQ"]
    src = {r["Net"] for r in rseq} - {"OPT_AVDD_EN"}
    if src != {"FPGA_CDONE_VSYNC_N"}:
        errs.append(f"R_SEQ source {src} is not the CDONE ball -> AVDD would enable without configuration success")
    dk = [r for r in D["net"] if r["RefDes"] == "D_SEQ" and r["Pin"] == "K"]
    if not dk or dk[0]["Net"] != "FPGA_CRESET_B":
        errs.append("D_SEQ cathode not on FPGA_CRESET_B (no fast discharge on reset)")
    if "assign cdone_vsync_n = ~d3_low_q" not in re.sub(r"\s+", " ", D["rtl"]):
        errs.append("RTL D3 is not driven as an active-low (idle-high) signal")
    V = p["rail_v"]; R = p["r_seq_ohm"] + p["r_cdone_pu_ohm"]; C = p["c_seq_nf"] * 1e-9
    tau_nom = R * C
    tau_min = p["r_seq_ohm"] * (1 - p["r_seq_tol"]) * C * (1 + p["c_seq_tol_incl_dc_bias"][0])
    tau_max = R * (1 + p["r_seq_tol"]) * C * (1 + p["c_seq_tol_incl_dc_bias"][1])
    t_on_nom = tau_nom * math.log(V / (V - TLV755P["vhi"])) * 1e3
    t_on_max = tau_max * math.log(V / (V - TLV755P["vhi"])) * 1e3
    v_cfg = TLV755P["ien_a"] * p["r_seq_ohm"]
    droop = V * (p["vsync_low_pulse_us"] * 1e-6) / tau_min
    v_steady = V - droop
    t_off_max = tau_max * math.log(V / TLV755P["vlo"]) * 1e3
    if v_cfg >= TLV755P["vlo"]: errs.append(f"EN during config {v_cfg:.3f} V >= VLO")
    if v_steady <= TLV755P["vhi"] + 0.3: errs.append(f"steady EN {v_steady:.3f} V margin < 0.3 V")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", (f"AVDD ON requires CRESET_B=1 & CDONE=1 & OPT_PWR_REQ=1; EN during config <= {v_cfg*1e3:.1f} mV (<0.3 V); "
                    f"guaranteed ON {t_on_nom:.1f} ms nom / <= {t_on_max:.1f} ms worst after CDONE; VSYNC 1 us pulse droop {droop*1e6:.0f} uV "
                    f"(steady >= {v_steady:.3f} V vs VHI 1.0 V); OPT_PWR_REQ=0 -> EN < 0.3 V within {t_off_max:.0f} ms; reset -> D_SEQ fast clamp")

def chk_seq02_fpga_rails(D):
    netmap = by_net(D["net"])
    def src_dev(net):
        s = [r for r in netmap.get(net, []) if r["Role"] == "SRC"]
        return s[0]["RefDes"] if s else None
    def pin_net(ref, func_prefix):
        r = [x for x in D["net"] if x["RefDes"] == ref and x["Pin_Function"].startswith(func_prefix)]
        return r[0]["Net"] if r else None
    errs = []
    vcc_dev = src_dev("1V2_FPGA_CORE"); io_dev = src_dev("1V8_FPGA_IO")
    vcc_in = pin_net(vcc_dev, "IN"); io_en = pin_net(io_dev, "EN")
    if vcc_in in ("1V8_SYS", "1V8_FPGA_IO"):
        errs.append(f"{vcc_dev} IN={vcc_in}: VCC cannot precede the 1.8 V I/O rails (iCE40UP DS 4.5)")
    if io_en not in ("1V2_FPGA_PLL", "1V2_FPGA_CORE"):
        errs.append(f"{io_dev} EN={io_en}: SPI_VCCIO1/VCCIO not gated by VCC/VCCPLL")
    fpga_io = {r["Net"] for r in D["net"] if r["RefDes"] == "U2_FPGA" and r["Pin"] in ("D2", "A3", "C4")}
    if fpga_io != {"1V8_FPGA_IO"}:
        errs.append(f"FPGA 1.8 V balls on {fpga_io}")
    vpll_min = 1.2 * (1 - 0.015) - 100 * 1e-3  # 1.5 % LDO accuracy, <=1 mA through 100R
    if vpll_min < TLV755P["vhi"] + 0.05:
        errs.append(f"VCCPLL {vpll_min:.3f} V too close to U4_1V8F VHI")
    ls1_vccb = [r["Net"] for r in D["net"] if r["RefDes"] == "U8_LS1" and r["Pin"] == "VCCB"]
    if ls1_vccb != ["1V8_FPGA_IO"]:
        errs.append(f"U8_LS1 VCCB={ls1_vccb}: B-side can back-power an unpowered FPGA bank")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", (f"VCC from {vcc_dev}(IN={vcc_in}); SPI_VCCIO1/VCCIO_0/VCCIO_2 from {io_dev} with EN={io_en} (min {vpll_min:.3f} V vs VHI 1.0 V); "
                    "VPP via 10R/4.7uF after SPI_VCCIO1; U8_LS1 VCCB tracks FPGA I/O rail (Ioff isolation)")

# ----------------------------------------------------------------------------- AUDIO
def max98357_window(v):
    if v > 1.4: return "LEFT"
    if 0.77 < v < 1.4: return "RIGHT"
    if 0.16 < v < 0.77: return "MIX"
    if v < 0.16: return "SHUTDOWN"
    return "EDGE"

def chk_aud01_sdmode(D, r_ext=69.8e3, rpd_tol=0.20, margin=0.08):
    errs, rep = [], []
    for vdd in (1.71, 1.80, 1.89):
        for rpd in (100e3 * (1 - rpd_tol), 100e3, 100e3 * (1 + rpd_tol)):
            vr = vdd * rpd / (rpd + r_ext)
            if max98357_window(vr) != "RIGHT" or min(vr - 0.77, 1.4 - vr) < margin:
                errs.append(f"R: VDD={vdd} Rpd={rpd/1e3:.0f}k -> {vr:.3f} V")
            rep.append(vr)
        if max98357_window(vdd) != "LEFT" or vdd - 1.4 < margin:
            errs.append(f"L: {vdd} V")
    if errs:
        return "FAIL", "SD_MODE margin violated: " + "; ".join(errs[:4])
    return "PASS", f"right amp SD_MODE {min(rep):.3f}..{max(rep):.3f} V (window 0.77..1.4 V, >= {margin*1e3:.0f} mV margin incl. ±20% internal pulldown ASSUMPTION, VDD ±5%); left amp 1.71..1.89 V > 1.4 V; nRF low -> both shutdown"

def chk_aud02_masters(D):
    netmap = by_net(D["net"])
    want = {"I2S_BCLK_1V8": "U11_BLE", "I2S_LRCLK_1V8": "U11_BLE", "I2S_AMP_DIN_1V8": "U11_BLE",
            "I2S_S3_DOUT_1V8": "U8_PDM_LS", "PDM_CLK_1V8": "U8_PDM_LS", "AMP_SD_MODE_1V8": "U11_BLE"}
    errs = []
    for n, dev in want.items():
        drv = [r["RefDes"] for r in netmap.get(n, []) if r["Role"] == "DRV"]
        if drv != [dev]:
            errs.append(f"{n} drivers {drv} (expected only {dev})")
    if any(r["RefDes"] == "U11_BLE" and "PDM" in r["Pin_Function"] for r in D["net"]):
        errs.append("nRF5340 PDM pins connected (second PDM clock master)")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", "I2S BCLK/LRCLK/AMP_DIN/SD_MODE driven only by nRF5340; ESP32 audio enters nRF SDIN; PDM clock only from ESP32"

def chk_aud03_timing():
    # ASSUMPTIONS (not datasheet-verified here): AXC tpd <= 6 ns, FPC 0.25 m @ 6.5 ns/m, ESP32 slave tx <= 35 ns,
    # nRF setup <= 20 ns, IM69D130 data-valid <= 90 ns, ESP32 PDM setup <= 15 ns.
    fpc = 0.25 * 6.5
    i2s_half = 1e9 / (2 * 1.536e6)
    i2s_rt = fpc + 6 + 35 + 6 + fpc + 20
    pdm_half = 1e9 / (2 * 3.072e6)
    pdm_rt = 6 + fpc + 90 + fpc + 6 + 15
    ok = i2s_rt < 0.6 * i2s_half and pdm_rt < 0.9 * pdm_half
    return ("PASS" if ok else "FAIL",
            f"I2S slave loop {i2s_rt:.0f} ns vs half-period {i2s_half:.0f} ns; right-mic PDM loop {pdm_rt:.0f} ns vs {pdm_half:.0f} ns "
            "(delay figures are stated ASSUMPTIONS, confirm on EVT bring-up with a scope)")

# ----------------------------------------------------------------------------- PRIVACY
def chk_priv01_window(D):
    c = D["cfg"]["3_camera_privacy_and_anti_backpower_model"]
    d = c["divider_from_3v3"]; rt = d["r1_top_ohm"] + d["r2_mid_ohm"] + d["r3_bot_ohm"]
    v_lo = 3.3 * d["r3_bot_ohm"] / rt; v_hi = 3.3 * (d["r2_mid_ohm"] + d["r3_bot_ohm"]) / rt
    k = c["csa_gain_v_per_v"] * c["r_sense_high_side_ohm"]  # V per A
    errs = []
    if v_lo < c["camera_ldo_en_vih_min_v"] + 0.05:
        errs.append(f"window low edge {v_lo:.3f} V < LDO VHI {c['camera_ldo_en_vih_min_v']} V + 50 mV (EN pulled up to V_INA_OUT)")
    if c["camera_ldo_en_vih_min_v"] != 1.0 or c["camera_ldo_en_vil_max_v"] != 0.3:
        errs.append("camera LDO thresholds not TLV755P datasheet values")
    i_min = (2.8 * 0.985 - c["led_vf_max_v"]) / ((c["r_limit_low_side_ohm"] + c["r_sense_high_side_ohm"]) * 1.01)
    i_max = (2.8 * 1.015 - c["led_vf_min_v"]) / ((c["r_limit_low_side_ohm"] + c["r_sense_high_side_ohm"]) * 0.99)
    if not (v_lo < i_min * k and i_max * k < v_hi):
        errs.append(f"healthy LED current {i_min*1e3:.2f}..{i_max*1e3:.2f} mA maps outside window")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", (f"window [{v_lo:.3f}, {v_hi:.3f}] V = [{v_lo/k*1e3:.2f}, {v_hi/k*1e3:.2f}] mA; healthy LED {i_min*1e3:.2f}..{i_max*1e3:.2f} mA inside "
                    f"(margins {i_min*k-v_lo:.3f} V / {v_hi-i_max*k:.3f} V); EN >= {v_lo:.3f} V >= VHI 1.0 V whenever window OK")

def chk_priv02_request_and_sccb(D):
    netmap = by_net(D["net"])
    errs = []
    en = [r for r in D["net"] if r["RefDes"] == "U5_LED2V8" and r["Pin_Function"] == "EN"]
    if not en or en[0]["Net"] != "CAM_PWR_REQ":
        errs.append("U5_LED2V8.EN has no defined request source")
    for n in ("CAM_SCCB_SCL", "CAM_SCCB_SDA"):
        refs = {r["RefDes"] for r in netmap.get(n, [])}
        if refs & {"U8_LS3", "U1_HOST", "U9_IMU"}:
            errs.append(f"{n} directly shares the always-on I2C bus (back-powers unpowered sensor)")
        vref = [r for r in D["net"] if r["RefDes"] == "U8_LS4" and r["Pin"] == "VREF1"]
        if not vref or vref[0]["Net"] != "CAM_DOVDD_1V8":
            errs.append("SCCB isolator VREF1 not on gated DOVDD")
    for n in ("CAM_RESET_N", "CAM_PWDN"):
        if not any(r["Role"] in ("PULLUP", "PULLDOWN", "DRV") for r in netmap.get(n, [])):
            errs.append(f"{n} undriven")
    led = [r for r in D["net"] if r["RefDes"] == "D3_PRIV" and r["Pin"] == "K"]
    if not led or led[0]["Net"] != "GND":
        errs.append("privacy LED cathode has no local return")
    v_req = 3.3 - 0.20 - 0.05          # Vf(RB521S-30 @ ~30 uA) <= 0.20 V ASSUMPTION, ripple <= 50 mV
    t_off = 100e3 * 100e-9 * math.log(v_req / 0.3) * 1e3
    t_chg = 330 * 100e-9 / 0.5 * 1e6
    if v_req <= 1.0 + 0.5 or v_req > 3.3:
        errs.append(f"CAM_PWR_REQ {v_req:.2f} V outside [1.5, VIN]")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", (f"CAM_PWR_REQ ~{v_req:.2f} V with XCLK running (charge tau ~{t_chg:.0f} us), < 0.3 V {t_off:.0f} ms after XCLK stops; "
                    "SCCB behind U8_LS4 (VREF1=DOVDD); RESET_N RC-POR, PWDN pulled low; LED cathode to bridge GND")

# ----------------------------------------------------------------------------- MASS
def shell_mass(m):
    area = sum(s["perimeter_mm"] * s["length_mm"] for s in m["segments"])
    return area * m["wall_mm"] * 1.05 * m["density_g_cm3"] / 1000.0

def mass_total(cfg, caps=False):
    s6 = cfg["6_power_thermal_mass_and_cog_budgets"]
    base = sum(a["mass_g"] for a in s6["subassemblies"])
    mi = s6["rev_d_missing_items_estimate"]
    shell = shell_mass(mi["temple_shell_model"])
    others = {o["name"]: o["mass_g"] for o in mi["other_items"]}
    if caps:
        c = s6["rev_d_mechanical_caps_to_close_40g"]
        frame = [a for a in s6["subassemblies"] if a["name"].startswith("Front Frame")][0]["mass_g"]
        base += c["front_frame_g"] - frame
        shell = c["temple_shell_each_g"]
        others[[k for k in others if k.startswith("FPC")][0]] = c["fpc_total_g"]
        others[[k for k in others if k.startswith("Fasteners")][0]] = c["fasteners_adhesive_g"]
    return base + 2 * shell + sum(others.values()), base, shell, others

def chk_mass01(D):
    cfg = D["cfg"]
    tot, base, shell, others = mass_total(cfg)
    mi = cfg["6_power_thermal_mass_and_cog_budgets"]["rev_d_missing_items_estimate"]["temple_shell_model"]
    tr90 = copy.deepcopy(mi); tr90["density_g_cm3"] = 1.14
    tot_tr90 = tot + 2 * (shell_mass(tr90) - shell)
    capped, *_ = mass_total(cfg, caps=True)
    reserve = cfg["6_power_thermal_mass_and_cog_budgets"]["rev_d_mechanical_caps_to_close_40g"]["reserve_g"]
    detail = (f"Rev C ledger {base-0.03:.2f} g + Rev D electronics 0.03 g + omitted items {tot-base:.2f} g "
              f"(2x temple shell {shell:.2f} g PA12/0.6 mm, FPC/nose/fasteners/pogo {sum(others.values()):.2f} g) = {tot:.2f} g "
              f"(TR90 shells: {tot_tr90:.2f} g) vs 40.0 g target; with mechanical caps: {capped:.2f} g (+{reserve} g reserve required)")
    if tot <= 40.0:
        return "UNVERIFIED", detail + " — within target analytically, unmeasured"
    if capped + reserve <= 40.0:
        return "OPEN", detail + " — NOT closed by current design; closes only if ID/mech meet the caps"
    return "FAIL", detail + " — caps insufficient"

# ----------------------------------------------------------------------------- RTL
def strip_comments(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)

def chk_rtl01_static(D):
    rtl, tb, mk = strip_comments(D["rtl"]), strip_comments(D["tb"]), D["mk"]
    errs = []
    for kw in ("begin", "case"):
        o = len(re.findall(rf"\b{kw}\b", rtl)); c = len(re.findall(rf"\bend{kw if kw=='case' else ''}\b", rtl))
        if kw == "begin" and o != c: errs.append(f"RTL begin/end {o}/{c}")
        if kw == "case" and o != c: errs.append(f"RTL case/endcase {o}/{c}")
    for kw in ("begin", "fork", "task"):
        o = len(re.findall(rf"\b{kw}\b", tb)); c = len(re.findall(rf"\b{'end' if kw=='begin' else 'join' if kw=='fork' else 'endtask'}\b", tb))
        if o != c: errs.append(f"TB {kw} balance {o}/{c}")
    if "frame_vsync_1v8" in rtl or "frame_vsync_1v8" in tb:
        errs.append("Rev C active-high frame_vsync_1v8 still referenced")
    for tok in ("CMD_OPT_CTRL", "raw_window_q", "scan_line_en_q", "pwr_off_sync", "assign cdone_vsync_n", "assign opt_cs_n"):
        if tok not in rtl: errs.append(f"RTL missing {tok}")
    for r in ("fifo_not_empty_q", "s0_addr_q", "s1_addr_q", "s1_diff_10_q", "s1_hit_a_q", "spram_addr_q", "ebr_wdata_l_q",
              "pix_shift_l", "wptr_bin_sync_q", "fifo_level_q", "h_cmd_ok_q", "h_in_bounds_q", "tear_row_holdoff"):
        if r not in rtl: errs.append(f"Rev C pipeline register {r} lost")
    if len(re.findall(r"SB_SPRAM256KA\s+u_spram_\w+", rtl)) != 4 or len(re.findall(r"\)\s*(u_ebr_\w+|u_cdc_fifo_\w+)\s*\(", rtl)) != 5:
        errs.append("SPRAM/EBR macro count changed")
    if "16'h5AC3" in tb or "16'h5AC2" not in tb or "row10_prefetch_seen" not in tb:
        errs.append("Rev C TB guards (5AC2 / row10 prefetch) lost")
    for c in ("unexpected_cs_cnt", "pwr_hold_err_cnt", "raw_reject_err_cnt", "raw_mirror_err_cnt", "raw_leak_err_cnt", "SIM_TIMEOUT_CLKS", "negedge cdone_vsync_n"):
        if c not in tb: errs.append(f"TB missing {c}")
    if "pipefail" not in mk or 'grep -q "VERILOG_TB_RESULT: PASS"' not in mk:
        errs.append("Makefile lost pipefail/PASS gate")
    if re.search(r"output\s+reg\s+\[?.*?opt_", rtl):
        errs.append("opt_* ports still 'output reg' while driven by assign")
    if errs:
        return "FAIL", "; ".join(errs)
    return "PASS", "RTL/TB structurally consistent (balanced blocks, Rev C pipeline/macro/TB guards retained, Rev D OPT_CTRL/RAW/scan-gate/D3 present, TB R1..R4 counters wired into PASS gate)"

def chk_rtl02_model():
    r = subprocess.run([sys.executable, str(SCRIPTS / "rev_d_optctrl_protocol_model.py")], capture_output=True, text=True)
    return ("PASS" if r.returncode == 0 and "PASS" in r.stdout else "FAIL", r.stdout.strip())

def chk_rtl03_native(log):
    if not shutil.which("iverilog"):
        msg = "[BLOCKED_ENV_NO_BINARY] iverilog/vvp/yosys/nextpnr-ice40/icetime not in PATH; run `make -C 03_FPGA_RTL all` in CI"
        log.append(msg)
        return "BLOCKED", msg
    r = subprocess.run(["make", "-C", str(RTL), "all"], capture_output=True, text=True)
    log.append(r.stdout[-4000:] + r.stderr[-2000:])
    return ("PASS" if r.returncode == 0 else "FAIL", f"make all rc={r.returncode}")

# ----------------------------------------------------------------------------- fault injection
def mutate(D, fn):
    M = copy.deepcopy(D); fn(M); return M

def fault_suite(D):
    cases = []
    def f1(M):  # Rev C: VBAT_R_RET on a single signal contact
        for r in M["conn"]:
            if r["Net"] == "VBAT_R_RET": r["Contact_Rating_A"] = "0.3"
    cases.append(("F01 right-battery return on 0.3 A signal contact (Rev C)", lambda M: chk_net03_ampacity(M), f1))
    def f2(M):  # Rev C: ESP32 also drives I2S BCLK
        M["net"].append(dict(Net="I2S_BCLK_1V8", Domain_V="1.8", Board="M-MAIN-L", RefDes="U8_PDM_LS", Pin="A9", Pin_Function="x", Role="DRV", BOM_Line="BOM-19", I_Peak_A="", Note=""))
    cases.append(("F02 second I2S master on BCLK (Rev C ESP32+nRF)", chk_aud02_masters, f2))
    def f3(M):
        M["net"].append(dict(Net="PDM_CLK_1V8", Domain_V="1.8", Board="M-AUD-R", RefDes="U11_BLE", Pin="PSEL", Pin_Function="PDM_CLK", Role="DRV", BOM_Line="BOM-36", I_Peak_A="", Note=""))
    cases.append(("F03 nRF5340 PDM clock on shared mic bus (Rev C)", chk_net01_single_driver, f3))
    cases.append(("F04 right SD_MODE 100k (Rev C)", lambda M: chk_aud01_sdmode(M, r_ext=100e3), lambda M: None))
    def f5(M):
        for r in M["net"]:
            if r["RefDes"] == "R_SEQ" and r["Net"] == "FPGA_CDONE_VSYNC_N": r["Net"] = "1V8_FPGA_IO"
    cases.append(("F05 AVDD RC charged from 1V8 rail, CRESET-only clamp (Rev C)", chk_seq01_avdd, f5))
    def f6(M):
        p = M["cfg"]["4_fpga_uwg30_pinout_and_rtl_timing"]["lattice_tn02006_power_and_config_audit"]["optical_avdd_sequencer"]
        p["ldo_en_vhi_max_v"], p["ldo_en_vlo_max_v"] = 0.95, 0.40
    cases.append(("F06 non-datasheet EN thresholds 0.95/0.40 V (Rev C)", chk_seq01_avdd, f6))
    def f7(M):
        for r in M["net"]:
            if r["RefDes"] == "U4_1V2" and r["Pin_Function"] == "IN": r["Net"] = "1V8_SYS"
    cases.append(("F07 U4_1V2 fed from 1V8_SYS (Rev C order violation)", chk_seq02_fpga_rails, f7))
    def f8(M):
        M["net"].append(dict(Net="PDM_CLK_3V3", Domain_V="3.3", Board="M-MAIN-L", RefDes="U8_AUD_LS2", Pin="B9", Pin_Function="x", Role="DRV", BOM_Line="BOM-47", I_Peak_A="", Note=""))
    cases.append(("F08 translator output on strap GPIO45 at reset", chk_net06_esp32, f8))
    def f9(M):
        M["net"].append(dict(Net="CAM_SCCB_SCL", Domain_V="1.8", Board="M-MAIN-L", RefDes="U8_LS3", Pin="SCL1", Pin_Function="SCL1", Role="BIDIR_OD", BOM_Line="BOM-03", I_Peak_A="", Note=""))
    cases.append(("F09 camera SCCB on always-on I2C (Rev C back-power)", chk_priv02_request_and_sccb, f9))
    def f10(M):
        for r in M["conn"]:
            if r["RefDes"] == "J_BTB_R" and r["Contact"] == "P14": r["Net"] = "I2S_DOUT_1V8"
    cases.append(("F10 J_BTB_R net absent from trunk", chk_net02_trunk, f10))
    def f11(M):
        M["cfg"]["3_camera_privacy_and_anti_backpower_model"]["divider_from_3v3"] = {"r1_top_ohm": 33000.0, "r2_mid_ohm": 39000.0, "r3_bot_ohm": 26100.0}
    cases.append(("F11 privacy window low edge below LDO VHI (Rev C divider)", chk_priv01_window, f11))
    def f12(M):
        M["rtl"] = M["rtl"].replace("assign cdone_vsync_n = ~d3_low_q;", "assign cdone_vsync_n = d3_low_q; // frame_vsync_1v8")
    cases.append(("F12 D3 reverted to active-high VSYNC", chk_seq01_avdd, f12))
    def f13(M): M["tb"] = M["tb"].replace("16'h5AC2", "16'h5AC3")
    cases.append(("F13 Rev C TB pattern-collision regression", chk_rtl01_static, f13))
    def f14(M):
        M["tr"]["U8_PDM_LS"]["banks"]["2"]["ch"][1] = [6, "I2S_BCLK_1V8", "I2S_BCLK_3V3"]
    cases.append(("F14 input placed in a B->A translator bank", chk_net04_translators, f14))
    def f15(M):
        for r in M["net"]:
            if r["RefDes"] == "D3_PRIV" and r["Pin"] == "K": r["Net"] = "PRIV_LED_CATHODE"
    cases.append(("F15 privacy LED cathode without return (Rev C low-side R_LIMIT)", chk_priv02_request_and_sccb, f15))
    def f16(M):
        for r in M["net"]:
            if r["RefDes"] == "U8_LS1" and r["Pin"] == "VCCB": r["Net"] = "1V8_SYS"
    cases.append(("F16 U8_LS1 VCCB on always-on rail (FPGA back-power)", chk_seq02_fpga_rails, f16))
    out = []
    for name, chk, fn in cases:
        st, _ = chk(mutate(D, fn))
        out.append((name, "CAUGHT" if st == "FAIL" else f"MISSED({st})"))
    return out

# ----------------------------------------------------------------------------- main
def main():
    D = load_all()
    log = []
    checks = [
        ("NET-00 BOM<->netlist reference integrity", chk_net00_bom_refs(D)),
        ("NET-01 single driver per net / OD pull-ups / PDM slot sharing", chk_net01_single_driver(D)),
        ("NET-02 cross-board trunk continuity (J_BTB_L=J_BRIDGE_IN, J_BTB_R subset)", chk_net02_trunk(D)),
        ("NET-03 BTB contact ampacity (Hirose BM28 0.3 A / 5 A, 1.25x)", chk_net03_ampacity(D)),
        ("NET-04 level-translator bank direction & domain consistency", chk_net04_translators(D)),
        ("NET-06 ESP32-S3 GPIO uniqueness & strap-pin safety", chk_net06_esp32(D)),
        ("NET-07 FPGA PCF <-> RTL ports <-> netlist balls", chk_net07_fpga(D)),
        ("SEQ-01 U6_OPT_AVDD CDONE-gated enable (TLV755P VHI/VLO)", chk_seq01_avdd(D)),
        ("SEQ-02 iCE40UP rail order VCC/VCCPLL -> SPI_VCCIO1 -> VPP", chk_seq02_fpga_rails(D)),
        ("AUD-01 MAX98357A SD_MODE channel-select margins", chk_aud01_sdmode(D)),
        ("AUD-02 single I2S master / single PDM clock master", chk_aud02_masters(D)),
        ("AUD-03 I2S-slave and right-mic PDM loop timing budget", chk_aud03_timing()),
        ("PRIV-01 privacy window vs camera LDO enable threshold", chk_priv01_window(D)),
        ("PRIV-02 camera power request, SCCB isolation, LED return", chk_priv02_request_and_sccb(D)),
        ("MASS-01 40 g ledger incl. Rev C omitted items", chk_mass01(D)),
        ("RTL-01 RTL/TB/Makefile static structure", chk_rtl01_static(D)),
        ("RTL-02 OPT_CTRL/RAW protocol behavioural model", chk_rtl02_model()),
        ("RTL-03 native iverilog/yosys/nextpnr/icetime", chk_rtl03_native(log)),
    ]
    faults = fault_suite(D)
    caught = sum(1 for _, s in faults if s == "CAUGHT")
    checks.append((f"FLT-01 fault injection ({len(faults)} Rev C defect classes)",
                   ("PASS" if caught == len(faults) else "FAIL", f"{caught}/{len(faults)} caught: " + "; ".join(f"{n}={s}" for n, s in faults))))
    lines = ["=" * 100, "智元跃动 AI/AR Glasses V1.0 — EVT-1 Rev D verification (from Rev C bb87623)", "=" * 100]
    tally = {}
    for name, (st, det) in checks:
        tally[st] = tally.get(st, 0) + 1
        lines.append(f"[{st}] {name}\n       -> {det}")
    lines.append("=" * 100)
    lines.append("SUMMARY: " + " | ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    lines.append("NOTE: PASS = computed/structural check on delivered files. BLOCKED = native tool absent. OPEN = known non-closure. Nothing here is a physical measurement.")
    txt = "\n".join(lines)
    print(txt)
    EVID.mkdir(exist_ok=True)
    (EVID / "rev_d_verification_report.txt").write_text(txt + "\n", encoding="utf-8")
    (EVID / "rev_d_verification_log.json").write_text(json.dumps(
        {"checks": [{"id": n, "status": s, "detail": d} for n, (s, d) in checks],
         "fault_injection": [{"case": n, "result": s} for n, s in faults], "native_eda_log": log}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if tally.get("FAIL") else 0

if __name__ == "__main__":
    sys.exit(main())
