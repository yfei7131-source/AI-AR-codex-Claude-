"""r6_stackup.py — R6-S2: insert a KiCad-native (stackup ...) into (setup ...) of the R6 PCB.
Candidate stackup C1 (1.0 mm 4L, 7628 prepreg; JLC04101H-7628-class public preset values),
chosen because it is the only evaluated 1.0 mm option that reaches ~90 ohm differential with the
board's 0.20 mm minimum trace (see evidence/usb_stackup/sweep.json). NOT fab-confirmed.
Idempotent: refuses if a stackup already exists. Text-level insert, no other bytes touched."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); raw = p.read_bytes(); nl = b'\r\n' if b'\r\n' in raw[:2000] else b'\n'
t = raw.decode('utf-8')
if '(stackup' in t: sys.exit('stackup already present')
L = [
 '(stackup',
 '\t(layer "F.SilkS" (type "Top Silk Screen"))',
 '\t(layer "F.Paste" (type "Top Solder Paste"))',
 '\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.0127) (material "LPI") (epsilon_r 3.8) (loss_tangent 0))',
 '\t(layer "F.Cu" (type "copper") (thickness 0.035))',
 '\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))',
 '\t(layer "In1.Cu" (type "copper") (thickness 0.0152))',
 '\t(layer "dielectric 2" (type "core") (thickness 0.45) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))',
 '\t(layer "In2.Cu" (type "copper") (thickness 0.0152))',
 '\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))',
 '\t(layer "B.Cu" (type "copper") (thickness 0.035))',
 '\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.0127) (material "LPI") (epsilon_r 3.8) (loss_tangent 0))',
 '\t(layer "B.Paste" (type "Bottom Solder Paste"))',
 '\t(layer "B.SilkS" (type "Bottom Silk Screen"))',
 '\t(copper_finish "ENIG")',
 '\t(dielectric_constraints no)',
 ')']
anchor = '\t(setup' + nl.decode()
i = t.index(anchor) + len(anchor)
ins = ''.join('\t\t' + l + nl.decode() for l in L)
t2 = t[:i] + ins + t[i:]
p.write_bytes(t2.encode('utf-8'))
print('inserted stackup, +%d lines' % len(L))
