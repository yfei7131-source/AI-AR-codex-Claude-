#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate KiCad 8 schematic (.kicad_sch), symbol lib (.kicad_sym), netlist.csv, BOM csv and a
connectivity self-check report from design.py.  No KiCad needed to run.
NOTE: the self-check is NOT KiCad ERC. ERC must be run in KiCad by a human before H03 layout."""
import csv, os, random, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJ = "evt0_core"
rnd = random.Random(20261111)
def uid():
    h = "%032x" % rnd.getrandbits(128)
    return "%s-%s-4%s-a%s-%s" % (h[:8], h[8:12], h[13:16], h[17:20], h[20:32])
ROOT = uid()
G = 2.54
def f(x): return ("%.4f" % x).rstrip("0").rstrip(".") if "." in ("%.4f" % x) else "%d" % x
FONT = "(effects (font (size 1.27 1.27)))"
def q(s): return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

# ---------- library symbols ----------
GEN2 = {  # generic horizontal 2-pin parts: prefix, graphics
 "R": ("R", '(rectangle (start -2.54 -1.016) (end 2.54 1.016) (stroke (width 0.254) (type default)) (fill (type none)))'),
 "C": ("C", '(polyline (pts (xy -0.508 -2.032) (xy -0.508 2.032)) (stroke (width 0.4) (type default)) (fill (type none)))'
            '(polyline (pts (xy 0.508 -2.032) (xy 0.508 2.032)) (stroke (width 0.4) (type default)) (fill (type none)))'
            '(polyline (pts (xy -2.54 0) (xy -0.508 0)) (stroke (width 0) (type default)) (fill (type none)))'
            '(polyline (pts (xy 0.508 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))'),
 "LED": ("D", '(polyline (pts (xy -1.27 0) (xy 1.27 1.27) (xy 1.27 -1.27) (xy -1.27 0)) (stroke (width 0.254) (type default)) (fill (type none)))'
              '(polyline (pts (xy -1.27 -1.27) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
              '(polyline (pts (xy -2.54 0) (xy -1.27 0)) (stroke (width 0) (type default)) (fill (type none)))'
              '(polyline (pts (xy 1.27 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))'
              '(polyline (pts (xy -0.508 1.524) (xy -1.524 2.54)) (stroke (width 0) (type default)) (fill (type none)))'),
 "D": ("D", '(polyline (pts (xy -1.27 0) (xy 1.27 1.27) (xy 1.27 -1.27) (xy -1.27 0)) (stroke (width 0.254) (type default)) (fill (type none)))'
            '(polyline (pts (xy -1.27 -1.27) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
            '(polyline (pts (xy -2.54 0) (xy -1.27 0)) (stroke (width 0) (type default)) (fill (type none)))'
            '(polyline (pts (xy 1.27 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))'),
 "SW": ("SW", '(circle (center -1.524 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))'
              '(circle (center 1.524 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))'
              '(polyline (pts (xy -2.032 1.27) (xy 2.032 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
              '(polyline (pts (xy -2.54 0) (xy -2.032 0)) (stroke (width 0) (type default)) (fill (type none)))'
              '(polyline (pts (xy 2.032 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))'),
 "PWR_FLAG": ("#FLG", '(polyline (pts (xy -2.54 0) (xy -1.27 0) (xy 0 1.27) (xy 1.27 0) (xy 0 -1.27) (xy -1.27 0)) (stroke (width 0.254) (type default)) (fill (type none)))'),
 "TP": ("TP", '(circle (center 0 0) (radius 1.016) (stroke (width 0.254) (type default)) (fill (type none)))'
              '(polyline (pts (xy -2.54 0) (xy -1.016 0)) (stroke (width 0) (type default)) (fill (type none)))'),
}
def pin_sx(typ, x, y, ang, length, name, num):
    return ('(pin %s line (at %s %s %d) (length %s) (name %s (effects (font (size 1.016 1.016)))) '
            '(number %s (effects (font (size 1.016 1.016)))))' % (typ, f(x), f(y), ang, f(length), q(name), q(num)))

class Sym:  # geometry of a library symbol
    def __init__(s, name):
        s.name = name; s.pins = {}   # num -> (x, y, side)  lib coords (Y up), connection point
        if name in GEN2:
            s.prefix, s.gfx = GEN2[name]; s.fp = ""; s.ds = ""; s.desc = name; s.generic = True
            s.pins["1"] = (-5.08, 0, "L"); s.h = 2.54; s.hw = 2.54
            one = name in ("TP", "PWR_FLAG")
            if not one: s.pins["2"] = (5.08, 0, "R")
            s.pindef = [("1", "~", "power_out" if name == "PWR_FLAG" else "passive")] + ([] if one else [("2", "~", "passive")])
        else:
            d = D.SYMS[name]; s.prefix = d["prefix"]; s.fp = d["fp"]; s.ds = d["ds"]; s.desc = d["desc"]; s.generic = False
            n = max(len(d["left"]), len(d["right"]))
            s.hw = 20.32 if name.startswith("ESP32") else (7.62 if name.startswith("HDR") or name.startswith("JST") else 12.7)
            top = G * (n // 2)
            s.h = G * (n + 1)
            s.top = top + G; s.bot = top - G * n
            s.pindef = []
            for i, (num, nm, typ) in enumerate(d["left"]):
                s.pins[num] = (-(s.hw + G), top - G * i, "L"); s.pindef.append((num, nm, typ))
            for i, (num, nm, typ) in enumerate(d["right"]):
                s.pins[num] = (s.hw + G, top - G * i, "R"); s.pindef.append((num, nm, typ))
    def lib(s, prefix="AIAR:"):
        yn = "no" if s.name == "PWR_FLAG" else "yes"
        o = ['(symbol %s %s (exclude_from_sim no) (in_bom %s) (on_board %s)' % (
            q(prefix + s.name), '(pin_numbers hide) (pin_names (offset 0) hide)' if s.generic else '(pin_names (offset 1.016))', yn, yn)]
        o.append('(property "Reference" %s (at 0 %s 0) %s)' % (q(s.prefix), f(getattr(s, "top", 2.54) + 1.27), FONT))
        o.append('(property "Value" %s (at 0 %s 0) %s)' % (q(s.name), f(getattr(s, "bot", -2.54) - 1.27), FONT))
        for k, v in (("Footprint", s.fp), ("Datasheet", s.ds), ("Description", s.desc)):
            o.append('(property %s %s (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (q(k), q(v)))
        if s.generic:
            o.append('(symbol %s %s)' % (q(s.name + "_0_1"), s.gfx))
        else:
            o.append('(symbol %s (rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background))))' % (
                q(s.name + "_0_1"), f(-s.hw), f(s.top), f(s.hw), f(s.bot)))
        o.append('(symbol %s' % q(s.name + "_1_1"))
        for num, nm, typ in s.pindef:
            x, y, side = s.pins[num]
            o.append(pin_sx(typ, x, y, 0 if side == "L" else 180, G, nm, num))
        o.append('))')
        return "\n".join(o)

syms = {}
for p in D.P:
    if p["sym"] not in syms: syms[p["sym"]] = Sym(p["sym"])

# ---------- placement ----------
SECTIONS = [  # (title, first ref, column, )
 ("USB-C INPUT / ESD", "J1", 0), ("CHARGER + POWER PATH (BQ24072, pin15=TD)", "U3", 0), ("3V3 SYSTEM RAIL", "U4", 0),
 ("MCU ESP32-S3-WROOM-1-N16R8", "U1", 1),
 ("CAMERA DVP + HARDWARE-GATED RAILS", "U5", 2), ("CAMERA RAIL INDICATOR (AVDD powered)", "R27", 2),
 ("VERIFICATION BREAKOUTS / TEST POINTS (not final product interfaces)", "J4", 2),
]
first = {s[1]: i for i, s in enumerate(SECTIONS)}
sec_parts = [[] for _ in SECTIONS]; cur = -1
for p in D.P:
    if p["ref"] in first: cur = first[p["ref"]]
    sec_parts[cur].append(p)
COLX = [25.4, 287.02, 548.64]; coly = [30.48, 30.48, 30.48]
ICX = 60.96; PASX = 137.16; PASDX = 60.96; PASDY = 7.62
place = {}; texts = []
for (title, _, col), parts in zip(SECTIONS, sec_parts):
    x0 = COLX[col]; y0 = coly[col]
    texts.append((x0, y0, title))
    y = y0 + 7.62; ymax = y
    for p in parts:
        s = syms[p["sym"]]
        if not s.generic:
            cy = round((y + s.top + G) / G) * G
            place[p["ref"]] = (x0 + ICX, cy); y = cy - s.bot + 3 * G; ymax = max(ymax, y)
    i = 0
    for p in parts:
        s = syms[p["sym"]]
        if s.generic:
            place[p["ref"]] = (x0 + PASX + (i % 2) * PASDX, round((y0 + 10.16 + (i // 2) * PASDY) / G) * G); i += 1
    ymax = max(ymax, y0 + 10.16 + ((i + 1) // 2) * PASDY)
    coly[col] = round((ymax + 12.7) / G) * G

# ---------- emit schematic ----------
STUB = 2 * G
body = []; nets = collections.defaultdict(list); pts = {}; segs = []; errors = []; warns = []
refs = set(); ptype = {}
for p in D.P:
    s = syms[p["sym"]]; X, Y = place[p["ref"]]
    if p["ref"] in refs: errors.append("duplicate ref " + p["ref"])
    refs.add(p["ref"])
    fp = p["fp"] or s.fp
    val = p["value"] + (" DNP" if p["dnp"] else "")
    yn = "no" if p["ref"].startswith("#") else "yes"
    o = ['(symbol (lib_id %s) (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board %s) (dnp %s) (uuid %s)' % (
        q("AIAR:" + s.name), f(X), f(Y), yn, yn, "yes" if p["dnp"] else "no", q(uid()))]
    ry = Y - (s.top + 1.27 if not s.generic else 1.905); vy = Y - (s.bot - 1.27 if not s.generic else -2.413)
    sz = "1.27 1.27" if not s.generic else "1.016 1.016"
    o.append('(property "Reference" %s (at %s %s 0) (effects (font (size %s))))' % (q(p["ref"]), f(X), f(ry), sz))
    o.append('(property "Value" %s (at %s %s 0) (effects (font (size %s))))' % (q(val), f(X), f(vy), sz))
    for k, v in (("Footprint", fp), ("Datasheet", s.ds), ("Description", s.desc), ("MPN", p["mpn"]), ("Manufacturer", p["mfr"]), ("Note", p["note"])):
        o.append('(property %s %s (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (q(k), q(v), f(X), f(Y)))
    for num in s.pins: o.append('(pin %s (uuid %s))' % (q(num), q(uid())))
    o.append('(instances (project %s (path %s (reference %s) (unit 1)))))' % (q(PROJ), q("/" + ROOT), q(p["ref"])))
    body.append("\n".join(o))
    for num in p["nets"]:
        if num not in s.pins: errors.append("%s: pin %s not in symbol %s" % (p["ref"], num, s.name))
    for num, (px, py, side) in s.pins.items():
        if num not in p["nets"]:
            errors.append("%s pin %s has no net / NC assignment" % (p["ref"], num)); continue
        net = p["nets"][num]; ax = X + px; ay = Y - py
        if net == D.NC:
            body.append('(no_connect (at %s %s) (uuid %s))' % (f(ax), f(ay), q(uid())))
            pts.setdefault((round(ax, 3), round(ay, 3)), set()).add("NC:%s.%s" % (p["ref"], num)); continue
        nets[net].append((p["ref"], num, p["dnp"]))
        ptype.setdefault(net, []).append((p["ref"] + "." + num, next(t for a, nm, t in s.pindef if a == num), p["dnp"]))
        ex = ax - STUB if side == "L" else ax + STUB
        body.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (f(ax), f(ay), f(ex), f(ay), q(uid())))
        body.append('(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid %s))' % (
            q(net), f(ex), f(ay), 180 if side == "L" else 0, "right" if side == "L" else "left", q(uid())))
        segs.append((round(ay, 3), min(ax, ex), max(ax, ex), net, p["ref"] + "." + num))
for x, y, t in texts:
    body.append('(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size 2.54 2.54) (bold yes)) (justify left bottom)) (uuid %s))' % (q(t), f(x), f(y), q(uid())))
body.append('(text %s (exclude_from_sim no) (at 25.4 570 0) (effects (font (size 1.778 1.778)) (justify left bottom)) (uuid %s))' % (
    q("Generated from gen/design.py. Connectivity is by net labels. Power nets are labels; VBUS/GND carry PWR_FLAG.\\n"
      "R3: bench design. For KiCad ERC and remaining blockers see ELECTRICAL_REVIEW.md."), q(uid())))

# geometric short check: stubs on same row overlapping with different nets
segs.sort()
for i in range(len(segs)):
    for j in range(i + 1, len(segs)):
        if segs[j][0] != segs[i][0]: break
        a, b = segs[i], segs[j]
        if a[1] <= b[2] + 0.01 and b[1] <= a[2] + 0.01 and a[3] != b[3]:
            errors.append("geometric overlap -> possible short: %s(%s) vs %s(%s)" % (a[4], a[3], b[4], b[3]))
# net checks
for n, pl in sorted(nets.items()):
    fitted = [x for x in pl if not x[2]]
    if len(pl) < 2 and n not in D.SINGLE_OK: errors.append("net %s has a single pin: %s" % (n, pl))
    elif len(fitted) < 2: warns.append("net %s has <2 fitted pins (others DNP): %s" % (n, pl))
# ERC-type pin rule check (subset of the KiCad ERC matrix; NOT a substitute for KiCad ERC)
DRIVERS = {"power_out", "output", "bidirectional", "passive", "open_collector", "tri_state"}
for n, pl in sorted(ptype.items()):
    t = [x[1] for x in pl if not x[2]]
    if t.count("power_out") > 1: errors.append("ERC: net %s has %d power_out pins: %s" % (n, t.count("power_out"), [x[0] for x in pl if x[1] == "power_out"]))
    if "power_out" in t and "output" in t: errors.append("ERC: net %s power_out vs output conflict" % n)
    if t.count("output") > 1: errors.append("ERC: net %s has multiple outputs" % n)
    if "power_in" in t and "power_out" not in t: errors.append("ERC: net %s has power_in pins but no power_out/PWR_FLAG driver" % n)
    if t and not (set(t) & DRIVERS): warns.append("ERC: net %s has only input pins (undriven)" % n)
    if "no_connect" in t: errors.append("ERC: net %s touches a no_connect-type pin" % n)
dn = {p["ref"]: p["dnp"] for p in D.P}
if not dn.get("R17") and not dn.get("R18"): errors.append("R17 and R18 both fitted: shorts 3V3 to CAM_2V8")
# strapping sanity for ESP32-S3
esp = next(p for p in D.P if p["ref"] == "U1")["nets"]
def has_pd(net): return any(p["sym"] == "R" and set(p["nets"].values()) == {net, "GND"} and not p["dnp"] for p in D.P)
for pin, io in (("26", "IO45"), ("16", "IO46")):
    if not has_pd(esp[pin]): errors.append("%s strap net %s lacks pull-down" % (io, esp[pin]))
for pin in ("28", "29", "30"):
    if esp[pin] != D.NC: errors.append("U1 pin %s (octal PSRAM IO35-37) must be NC" % pin)
if {esp["13"], esp["14"]} != {"USB_DM", "USB_DP"}: errors.append("IO19/IO20 must be USB D-/D+")
# R2 guard: BQ2407x pin-15 function must match the fitted variant (R1 bug: SYSOFF drawn on a BQ24072)
for p in D.P:
    for fam, fn in D.BQ2407X_PIN15.items():
        if p["mpn"].startswith(fam):
            nm = next(n for a, n, t in syms[p["sym"]].pindef if a == "15")
            if nm != fn: errors.append("%s %s: pin 15 must be %s per TI datasheet, symbol says %s" % (p["ref"], p["mpn"], fn, nm))
            if fn == "TD" and p["nets"]["15"] == D.NC: errors.append("%s: TD must not float" % p["ref"])
            if fn == "TD" and not any(q["sym"] == "R" and set(q["nets"].values()) == {p["nets"]["15"], "GND"} and not q["dnp"] for q in D.P):
                warns.append("%s: TD not strapped to GND -> charge termination may be disabled" % p["ref"])
if any("SYSOFF" in n for n in nets): errors.append("net named SYSOFF exists but no SYSOFF-capable charger is fitted")

hdr = ('(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")\n(uuid %s)\n(paper "A1")\n'
       '(title_block (title "AI/AR Glasses V1.0 - EVT-0 Core Verification Board") (date "2026-11-12") (rev "R3") '
       '(company "AI-AR-codex-Claude-") (comment 1 "H02 R3 - camera FPC and optical harness held - bench assembly review required") '
       '(comment 2 "Bench verification board, NOT glasses form factor"))\n' % q(ROOT))
libs = "(lib_symbols\n" + "\n".join(syms[k].lib() for k in sorted(syms)) + "\n)\n"
tail = '\n(sheet_instances (path "/" (page "1")))\n)\n'
with open(os.path.join(OUT, PROJ + ".kicad_sch"), "w", encoding="utf-8") as fh:
    fh.write(hdr + libs + "\n".join(body) + tail)
with open(os.path.join(OUT, "aiar.kicad_sym"), "w", encoding="utf-8") as fh:
    fh.write('(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor") (generator_version "8.0")\n'
             + "\n".join(syms[k].lib(prefix="") for k in sorted(syms)) + "\n)\n")
with open(os.path.join(OUT, "sym-lib-table"), "w") as fh:
    fh.write('(sym_lib_table\n  (version 7)\n  (lib (name "AIAR")(type "KiCad")(uri "${KIPRJMOD}/aiar.kicad_sym")(options "")(descr "AI/AR glasses project symbols"))\n)\n')

with open(os.path.join(OUT, "netlist.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["net", "ref", "pin", "pin_name", "dnp"])
    for n in sorted(nets):
        for ref, num, dnp in nets[n]:
            p = next(x for x in D.P if x["ref"] == ref); s = syms[p["sym"]]
            w.writerow([n, ref, num, next(nm for a, nm, t in s.pindef if a == num), "DNP" if dnp else ""])
grp = collections.OrderedDict()
for p in D.P:
    if p["ref"].startswith("#"): continue
    k = (p["value"], p["fp"] or syms[p["sym"]].fp, p["mpn"], p["mfr"], p["dnp"])
    grp.setdefault(k, []).append(p)
with open(os.path.join(OUT, "bom_evt0_core.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(["item", "refs", "qty", "value", "footprint", "MPN", "manufacturer", "fit", "notes"])
    for i, (k, ps) in enumerate(grp.items(), 1):
        w.writerow([i, " ".join(p["ref"] for p in ps), len(ps), k[0], k[1], k[2], k[3], "DNP" if k[4] else "FIT",
                    "; ".join(sorted({p["note"] for p in ps if p["note"]}))])
STRAP = {0: "strap: boot mode (pull-up)", 3: "strap: JTAG source", 45: "strap: VDD_SPI, LOW at reset", 46: "strap: LOW at reset",
         19: "USB D-", 20: "USB D+", 35: "octal PSRAM - unusable", 36: "octal PSRAM - unusable", 37: "octal PSRAM - unusable", 43: "U0TXD", 44: "U0RXD"}
with open(os.path.join(OUT, "pinmap_hw.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["gpio", "module_pin", "hw_net", "constraint", "fw_macro(board.h)", "fw_match"])
    for g in sorted(D.GPIO_PIN):
        n = esp[D.GPIO_PIN[g]]
        w.writerow([g, D.GPIO_PIN[g], "NC" if n == D.NC else n, STRAP.get(g, ""), "UNVERIFIED", "UNVERIFIED"])
with open(os.path.join(OUT, "selfcheck_report.txt"), "w", encoding="utf-8") as fh:
    fh.write("EVT-0 core R3 - connectivity + ERC-type pin rule self-check (NOT KiCad ERC)\n")
    fh.write("parts=%d nets=%d symbols=%d\n" % (len(D.P), len(nets), len(syms)))
    fh.write("ERRORS: %d\n" % len(errors)); [fh.write("  E: %s\n" % e) for e in errors]
    fh.write("WARNINGS: %d\n" % len(warns)); [fh.write("  W: %s\n" % e) for e in warns]
print(open(os.path.join(OUT, "selfcheck_report.txt")).read())
sys.exit(1 if errors else 0)
