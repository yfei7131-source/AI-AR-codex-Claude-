#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Firmware <-> hardware pin-map cross-check (R2).  READ-ONLY on the repo (Codex owns firmware).
Usage: python3 tools/check_fw_compat.py <repo_root> [pinmap_hw.csv] [--profile CONFIG_GL_BOARD_EYE_V22]
Parses, in this order:
  1. firmware/main/board.h  -> field order of `typedef struct {...} gl_board;` (incl. `int a, d[8], b;`)
  2. firmware/main/board.c  -> every `static const gl_board x={...};` POSITIONAL initializer, per #if/#else branch
  3. legacy patterns (#define / .pin_x = / CONFIG_*GPIO*) anywhere under firmware/
Exit: 0 = selected profile matches hardware AND repo content complete
      2 = pins match but repo incomplete / hardware nets missing from firmware (cannot freeze)
      1 = pin conflict or nothing parsed
Writes fw_compat_report.md + pinmap_fw_crosscheck.csv next to the pin-map CSV."""
import csv, hashlib, os, re, sys
REQ = ["docs/FEATURES_F01_F22.md", "firmware/main/board.c", "firmware/main/board.h", "firmware/main/camera_adapter.c",
       "firmware/main/display_adapter.h", "firmware/main/ble_control.c", "protocols/DEVICE_MEDIA_V1.md",
       "protocols/events.schema.json", "mobile/lib", "mobile/ios/Runner/GlassesBleBridge.swift"]
# firmware struct field -> hardware net expected on that GPIO
FIELD_NET = {"button_gpio": "KEY_BOOT", "xclk": "CAM_XCLK_R", "sda": "CAM_SIOD", "scl": "CAM_SIOC", "vsync": "CAM_VSYNC",
             "href": "CAM_HREF", "pclk": "CAM_PCLK_R", "pwdn": "CAM_PWDN", "reset": "CAM_RST_N",
             "cam_pwr_en": "CAM_PWR_EN", "vbat_adc": "VBAT_ADC", "mic_sck": "MIC_SCK", "mic_ws": "MIC_WS", "mic_sd": "MIC_SD",
             "disp_cs": "DISP_CS", "disp_clk": "DISP_CLK", "disp_rst": "DISP_RST", "disp_pwr_en": "DISP_PWR_EN",
             "bt_aud_en": "BT_AUD_EN"}
FIELD_NET.update({"d[%d]" % i: "CAM_Y%d" % (i + 2) for i in range(8)})       # esp32-camera: D0..D7 == Y2..Y9
FIELD_NET.update({"disp_d[%d]" % i: "DISP_D%d" % i for i in range(4)})
NON_GPIO = {"name", "configured", "privacy_interlock_verified"}
LEGACY = [re.compile(r"#\s*define\s+(\w+)\s+\(?\s*(?:GPIO_NUM_)?(-?\d+)\s*\)?\s*(?://.*|/\*.*)?$"),
          re.compile(r"\.(\w*(?:pin|gpio|io)\w*)\s*=\s*(?:GPIO_NUM_)?(-?\d+)\s*,"),
          re.compile(r"^(CONFIG_\w*(?:PIN|GPIO)\w*)=(-?\d+)$")]

def strip_comments(s):
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", s, flags=re.S))

def struct_fields(h, typename="gl_board"):
    """-> flat list of scalar slots in declaration order, e.g. ['name','configured',...,'d[0]',...]"""
    m = re.search(r"typedef\s+struct\s*\w*\s*\{(.*?)\}\s*%s\s*;" % re.escape(typename), strip_comments(h), re.S)
    if not m: return None
    out = []
    for decl in m.group(1).split(";"):
        decl = decl.strip()
        if not decl: continue
        first, *rest = decl.split(",")
        names = [first.split()[-1].lstrip("*")] + [x.strip().lstrip("*") for x in rest]
        for n in names:
            a = re.match(r"(\w+)\s*\[\s*(\d+)\s*\]$", n)
            out += ["%s[%d]" % (a.group(1), i) for i in range(int(a.group(2)))] if a else [n]
    return out

def flat_init(body):
    """'"x",true,false,0,{1,2},3' -> ['"x"','true','false','0','1','2','3'] (brace elision flattening)"""
    return [t.strip() for t in re.findall(r'"(?:[^"\\]|\\.)*"|[^,{}]+', body) if t.strip()]

def profiles(c, typename="gl_board"):
    """-> [(condition, name, [tokens])] walking #if/#elif/#else/#endif"""
    res = []; stack = []
    for line in strip_comments(c).split("\n"):
        t = line.strip()
        m = re.match(r"#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)", t)
        if m:
            k, a = m.group(1), m.group(2).strip()
            if k in ("if", "ifdef", "ifndef"): stack.append([("!" if k == "ifndef" else "") + a])
            elif k == "elif" and stack: stack[-1].append(a)
            elif k == "else" and stack: stack[-1].append("else(!(" + " || ".join(stack[-1]) + "))")
            elif k == "endif" and stack: stack.pop()
            continue
        m = re.search(r"\b%s\s+\w+\s*=\s*\{(.*)\}\s*;" % re.escape(typename), t)
        if m:
            tok = flat_init(m.group(1))
            res.append((" && ".join(s[-1] for s in stack) or "(unconditional)", tok[0].strip('"') if tok else "?", tok))
    return res

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else None
    if want: args = [a for a in args if a != want]
    if not args: print(__doc__); return 1
    repo = args[0]
    pm = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "H02", "evt0_core", "pinmap_hw.csv")
    hw = {int(r["gpio"]): r for r in csv.DictReader(open(pm, encoding="utf-8"))}
    net2gpio = {r["hw_net"]: g for g, r in hw.items() if r["hw_net"] != "NC"}
    out = ["# fw_compat_report (tools/check_fw_compat.py R2)", "", "repo: `%s`" % repo, ""]
    conflicts = 0; incomplete = 0
    missing = [r for r in REQ if not os.path.exists(os.path.join(repo, r))]
    out.append("## Required repo content"); out += ["- %s `%s`" % ("MISSING" if r in missing else "ok", r) for r in REQ]
    if missing: incomplete += 1; out.append("\n**Repo incomplete -> result below covers ONLY the files present. Do NOT freeze GPIO.**")
    bh, bc = os.path.join(repo, "firmware/main/board.h"), os.path.join(repo, "firmware/main/board.c")
    rows = []; parsed = False
    if os.path.exists(bh) and os.path.exists(bc):
        out += ["", "## Inputs", "- board.h sha256 `%s`" % sha(bh), "- board.c sha256 `%s`" % sha(bc)]
        fields = struct_fields(open(bh, encoding="utf-8", errors="replace").read())
        profs = profiles(open(bc, encoding="utf-8", errors="replace").read())
        if fields and profs:
            parsed = True
            out += ["", "## gl_board struct slots (%d)" % len(fields), "`" + ", ".join(fields) + "`"]
            cfg = [p for p in profs if any(tk == "true" for tk in p[2][1:2])]
            sel = [p for p in profs if want and want in p[0] and not p[0].startswith("else")] or cfg[:1] or profs[:1]
            for cond, name, tok in profs:
                out += ["", "## Profile `%s`  (condition: `%s`)%s" % (name, cond, "  <- CHECKED" if (cond, name, tok) in sel else "")]
                if len(tok) != len(fields):
                    out.append("**PARSE MISMATCH: %d initializer tokens vs %d struct slots**" % (len(tok), len(fields))); conflicts += 1; continue
                kv = dict(zip(fields, tok))
                out.append("- configured=%s, privacy_interlock_verified=%s" % (kv.get("configured"), kv.get("privacy_interlock_verified")))
                if (cond, name, tok) not in sel: continue
                if kv.get("privacy_interlock_verified") != "true":
                    incomplete += 1; out.append("- **privacy_interlock_verified != true -> firmware refuses capture; needs H05 T11/T12 evidence + Codex profile (ICR-08/09)**")
                out += ["", "| fw field | fw gpio | expected hw net | hw net on that gpio | constraint | verdict |", "|---|---|---|---|---|---|"]
                for fld in fields:
                    if fld in NON_GPIO: continue
                    g = int(kv[fld]); exp = FIELD_NET.get(fld, "?")
                    if g < 0: v = "unused(-1)"; net = "-"; c = ""
                    else:
                        r = hw.get(g)
                        if r is None: v = "CONFLICT: GPIO not bonded out on WROOM-1"; net = "-"; c = ""; conflicts += 1
                        else:
                            net, c = r["hw_net"], r["constraint"]
                            if net == exp: v = "match"
                            elif net == "NC" or "PSRAM" in c: v = "CONFLICT: pin unavailable on hardware"; conflicts += 1
                            else: v = "CONFLICT: hw has %s here; %s is on GPIO%s" % (net, exp, net2gpio.get(exp, "?")); conflicts += 1
                    out.append("| %s | %d | %s | %s | %s | %s |" % (fld, g, exp, net, c, v)); rows.append((fld, g, exp, net, v, name))
                covered = {r[2] for r in rows}
                gap = [(g, r["hw_net"]) for g, r in sorted(hw.items()) if r["hw_net"] not in covered and r["hw_net"] != "NC"
                       and not r["hw_net"].startswith(("USB_", "U0"))]
                out += ["", "### Hardware nets with NO field in this firmware profile (need ICR, not a pin conflict)"]
                out += ["- GPIO%d %s" % x for x in gap]
                if gap: incomplete += 1
    else:
        out.append("\n**board.h / board.c not found.**")
    # legacy scan (informational; counts as conflict only if it hits an unavailable pin)
    found = []
    d = os.path.join(repo, "firmware")
    for root, dirs, files in os.walk(d) if os.path.isdir(d) else []:
        dirs[:] = [x for x in dirs if x not in ("build", "managed_components", ".git")]
        for fn in files:
            if not (fn.endswith((".c", ".h", ".cpp", ".hpp")) or fn.startswith(("sdkconfig", "Kconfig"))): continue
            fp = os.path.join(root, fn)
            for ln, line in enumerate(open(fp, encoding="utf-8", errors="replace"), 1):
                for pat in LEGACY:
                    m = pat.search(line.rstrip())
                    if m and re.search(r"PIN|GPIO|CAM|MIC|I2S|I2C|SPI|LCD|DISP|LED|KEY|BTN|BAT|UART|SDA|SCL|CLK", m.group(1), re.I) and -1 <= int(m.group(2)) <= 48:
                        found.append((m.group(1), int(m.group(2)), "%s:%d" % (os.path.relpath(fp, repo), ln)))
    out += ["", "## Other GPIO-like definitions under firmware/ (%d, review manually)" % len(set(found))]
    out += ["- `%s` = %d (%s) -> hw: %s" % (n, g, s, hw[g]["hw_net"] if g in hw else "-") for n, g, s in sorted(set(found), key=lambda x: x[1])]
    if not parsed and not found: conflicts += 1; out.append("\n**Nothing parsed: inspect board.[ch] manually.**")
    code = 1 if conflicts else (2 if incomplete else 0)
    out += ["", "## RESULT", "conflicts=%d incomplete_items=%d exit=%d (%s)" % (conflicts, incomplete, code,
            {0: "MATCH, repo complete", 2: "pins match where defined; NOT freezable", 1: "CONFLICT / parse failure"}[code])]
    base = os.path.dirname(os.path.abspath(pm))
    open(os.path.join(base, "fw_compat_report.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    with open(os.path.join(base, "pinmap_fw_crosscheck.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["gpio", "module_pin", "hw_net", "constraint", "fw_field", "fw_profile", "verdict"])
        by = {r[1]: r for r in rows if r[1] >= 0}
        for g, r in sorted(hw.items()):
            x = by.get(g)
            w.writerow([g, r["module_pin"], r["hw_net"], r["constraint"], x[0] if x else "", x[5] if x else "",
                        x[4] if x else ("n/a" if r["hw_net"] == "NC" or r["hw_net"].startswith(("USB_", "U0")) else "NOT IN FIRMWARE PROFILE")])
    print("\n".join(out)); return code
if __name__ == "__main__": sys.exit(main())
