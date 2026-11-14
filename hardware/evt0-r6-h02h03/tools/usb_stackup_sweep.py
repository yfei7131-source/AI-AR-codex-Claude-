"""usb_stackup_sweep.py — R6: sweep USB2 90 ohm edge-coupled microstrip (F.Cu over In1 GND)
for candidate 1.0 mm 4-layer stackups. ESTIMATE ONLY (2D quasi-TEM solver usb_impedance.py,
~2-4 % below Hammerstad-Jensen in its validation). Final W/S must come from the fab's own
impedance calculation for the ordered stackup + coupon. Board min trace 0.20 mm is NOT relaxed.
usage: python usb_stackup_sweep.py out.json
"""
import json, sys, itertools
from usb_impedance import impedance, ipc_diff

# Candidate stackups (values = public JLCPCB 1.0 mm 4L impedance-controlled presets, to be
# re-confirmed against the fab quotation at order time; NOT a released stackup).
STACKUPS = {
    "C1_7628_PP0.2104_er4.4": dict(h=0.2104, er=4.4, t=0.035, mask_t=0.0127, mask_er=3.8),
    "C2_3313_PP0.0994_er4.1": dict(h=0.0994, er=4.1, t=0.035, mask_t=0.0127, mask_er=3.8),
}
W = [0.20, 0.22, 0.25]          # >= board min trace 0.20 mm
S = [0.15, 0.18, 0.20, 0.22, 0.25]
out = {"note": "ESTIMATE, not fab-confirmed; solver error budget ~ -4 %..0 % vs analytic", "results": []}
for name, k in STACKUPS.items():
    for w, s in itertools.product(W, S):
        z = impedance(w, s, k["t"], k["h"], k["er"], tm_top=k["mask_t"], er_mask=k["mask_er"], fine=0.005)
        out["results"].append(dict(stackup=name, w=w, s=s, Zdiff=round(z["Zdiff"], 1),
                                   Zcommon=round(z["Zcommon"], 1),
                                   ipc2141_diff=round(ipc_diff(w, s, k["t"], k["h"], k["er"]), 1)))
        print(name, w, s, out["results"][-1]["Zdiff"], out["results"][-1]["ipc2141_diff"], flush=True)
if len(sys.argv) > 1:
    open(sys.argv[1], "w").write(json.dumps(out, indent=1))
