"""r6_s5_plane_cleanup.py — R6-S5: replace long surface GND/3V3 traces with short via drops to the
In1 (GND) / In2 (3V3) planes inside a bounding box, to (1) cut loop inductance / improve PI and
(2) free the F.Cu/B.Cu corridor needed by the USB pair and the camera bus.

Method: delete every /GND and /3V3 segment+via whose anchors all lie inside the box (pads untouched),
then for every resulting cluster that no longer reaches its plane, r5_run.route_net(plane=True)
adds the shortest stub + via (0.3 mm Power width, 0.6/0.3 via). Box excludes the charger/battery
protection area (U3, J2, Q1, x > 128) so battery protection copper is not touched.
Abort (nothing written) if any cluster cannot be re-attached, or self-check fails.
usage: python r6_s5_plane_cleanup.py <prj> x0 y0 x1 y1 [--dry]"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb
from r5_route import Router, emit_blocks
from r5_run import route_net, load
from zy_pcb import drc_lite, dangling
from r6_route import smooth_net

import r5_route
from r5_route import mask_item, VIA_D
_bm = Router.build_masks
def build_masks_no_via_in_pad(s, win, net, width, extra=0.03):
    """same as r5_route, plus: no via may touch ANY SMD pad (incl. same net) -> no via-in-pad."""
    tm, vm = _bm(s, win, net, width, extra)
    for it in s.B.items:
        if it.kind == 'pad' and it.ptype == 'smd':
            r = mask_item(win, it.shape, VIA_D / 2 + 0.05)
            if r: vm[r[0], r[1]] |= r[2]
    return tm, vm
Router.build_masks = build_masks_no_via_in_pad

a = sys.argv[1:]; dry = '--dry' in a; a = [x for x in a if x != '--dry']
D = Path(a[0]); X0, Y0, X1, Y1 = map(float, a[1:5]); pcb = D / 'evt0_core.kicad_pcb'
NETS = ('/GND', '/3V3')
B, R = load(D)
inbox = lambda it: all(X0 <= x <= X1 and Y0 <= y <= Y1 for x, y in it.anchors)
rip = [it for it in B.items if it.kind in ('trk', 'via') and it.net in NETS and inbox(it)]
g0 = sum(B.gaps().values())
P = Pcb(pcb); P.delete_uuids({it.uuid for it in rip})
tmp = D / '_s5_tmp.kicad_pcb'; P.save(tmp)
B, R = load(D); B.__init__(tmp)
# boundary-crossing GND/3V3 tracks left with an open end: remove them too, until none remain
while True:
    dl = {x.uuid: x for x, p in dangling(B) if x.net in NETS}
    if not dl: break
    rip += list(dl.values()); P.delete_uuids(set(dl)); P.save(tmp); B.__init__(tmp)
tmp.unlink()
RT = Router(B, R); logs = []
def log(*x): s = ' '.join(str(v) for v in x); print(s, flush=True); logs.append(s)
log(f'ripped {len(rip)} items ({sum(1 for i in rip if i.kind == "trk")} seg, {sum(1 for i in rip if i.kind == "via")} via); gaps after rip {sum(B.gaps().values())}')
for net in NETS:
    while True:
        cl = B.clusters(only={net})[net]
        if len(cl) <= 1: break
        n0, k0 = RT.snapshot()
        done, failed = route_net(RT, net, 0.3, via_cost=1.0, plane=True, log=log, max_conn=1)
        if not done: break
        smooth_net(RT, net, 0.3, n0, k0, log)
    log(net, 'clusters remaining', len(B.clusters(only={net})[net]))
g1 = sum(B.gaps().values()); V = drc_lite(B, R, 'new'); dl = [x for x, p in dangling(B) if x.new]
nv = sum(1 for r in RT.added if r['kind'] == 'via')
import math
L_old = sum(math.dist(*i.anchors) for i in rip if i.kind == 'trk')
L_new = sum(math.dist(r['start'], r['end']) for r in RT.added if r['kind'] == 'segment')
log(f'gaps {g0}->{g1}; surface GND/3V3 copper {L_old:.1f} mm -> {L_new:.1f} mm; new vias {nv}; drc_lite(new) {len(V)}; dangling(new) {len(dl)}')
for v in V[:10]: log('  VIOL', v)
ok = g1 == g0 and not V and not dl
out = D.parent / 'evidence' / 'step_r6_s5_plane_cleanup'; out.mkdir(parents=True, exist_ok=True)
(out / 'change.json').write_text(json.dumps(dict(box=[X0, Y0, X1, Y1], deleted=[i.uuid for i in rip], added=RT.added,
    gaps_before=g0, gaps_after=g1, surface_len_before=round(L_old, 2), surface_len_after=round(L_new, 2), ok=ok,
    note='zy_pcb selfcheck, NOT native DRC'), indent=1))
(out / 'log.txt').write_text('\n'.join(logs) + '\n')
if not ok: sys.exit('self-check failed, nothing written')
if not dry:
    P.insert_copper(RT.added, emit_blocks); P.save(); log('written')
