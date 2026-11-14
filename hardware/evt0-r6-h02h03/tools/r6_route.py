"""r6_route.py — R6 incremental router driver = r5_route grid search + EXACT-geometry smoothing.

Why: the 0.05 mm grid search leaves stair-step chains wherever the shortest path is not 0/45/90 deg.
After each net is routed, its new copper is re-shaped chain by chain (between vias / junctions / pad
anchors, which stay fixed) by greedy shortcutting. A shortcut is accepted only if it passes an exact
clearance check (zy_pcb shapes, same rules as drc_lite: netclass clearance incl. CamClk DRU rule,
hole clearance, board-edge clearance, keepouts) with an extra safety margin. Preference order:
one octilinear segment > two octilinear segments > one any-angle segment.
Only ADDS segment/via blocks to the board; never moves/deletes existing copper, pads or rules.
Native KiCad DRC (tools/r6_native.py) remains the acceptance gate.

usage: python r6_route.py <prj_dir> <step_tag> [--via-cost C] [--dry] NET [NET ...]
writes  <prj_dir>/../evidence/<step_tag>/{added_copper.json, route_log.txt}"""
import json, sys, time, math
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent))
from r5_route import Router, emit_blocks, shape_bbox
from r5_run import route_net, load
from pcb_edit import Pcb
from zy_pcb import drc_lite, dangling, dist, EPS

MARGIN = 0.02          # extra clearance margin for smoothed geometry (mm)


class Smoother:
    def __init__(s, B, R, net, width):
        s.B, s.R, s.net, s.w = B, R, net, width
        s.obs = defaultdict(list)       # layer -> [(bbox, shape, need)]
        s.holes = []                    # [(bbox, hole_shape)]
        for it in B.items:
            if it.net == net and it.net: continue
            if it.layers:
                need = R.clr(net, it.net) if it.net else R.clr(net, net)
                bb = shape_bbox(it.shape, 0)
                for L in it.layers: s.obs[L].append((bb, it.shape, need))
            if it.hole is not None:
                s.holes.append((shape_bbox(it.hole, 0), it.hole))
        s.edge = B.edge

    def ok(s, a, b, L):
        hw = s.w / 2; sh = ('cap', a[0], a[1], b[0], b[1], hw)
        x0, y0 = min(a[0], b[0]) - hw, min(a[1], b[1]) - hw
        x1, y1 = max(a[0], b[0]) + hw, max(a[1], b[1]) + hw
        ex0, ey0, ex1, ey1 = s.edge
        if min(x0 - ex0, y0 - ey0, ex1 - x1, ey1 - y1) < s.R.edge + MARGIN: return False
        m = 0.8
        for bb, osh, need in s.obs[L]:
            if bb[0] > x1 + m or bb[2] < x0 - m or bb[1] > y1 + m or bb[3] < y0 - m: continue
            if dist(sh, osh) < need + MARGIN: return False
        for bb, h in s.holes:
            if bb[0] > x1 + m or bb[2] < x0 - m or bb[1] > y1 + m or bb[3] < y0 - m: continue
            if dist(sh, h) < s.R.hole_clr + MARGIN: return False
        for k in s.B.keepouts:
            if dist(sh, ('poly', k, 0.0)) <= 0: return False
        return True

    @staticmethod
    def octi(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        return abs(dx) < 1e-6 or abs(dy) < 1e-6 or abs(abs(dx) - abs(dy)) < 1e-6

    def candidates(s, a, b):
        if s.octi(a, b): yield [a, b]; return
        dx, dy = b[0] - a[0], b[1] - a[1]; m = min(abs(dx), abs(dy))
        sx, sy = math.copysign(1, dx), math.copysign(1, dy)
        yield [a, (a[0] + sx * m, a[1] + sy * m), b]                 # diagonal first
        yield [a, (b[0] - sx * m, b[1] - sy * m), b]                 # straight first
        yield [a, b]                                                 # any-angle

    def smooth_chain(s, P, L):
        out = [P[0]]; i = 0; n = len(P) - 1
        while i < n:
            done = False
            for j in range(n, i, -1):
                for c in s.candidates(P[i], P[j]):
                    if j == i + 1 and len(c) == 2 and c == [P[i], P[j]]:
                        good = True              # original segment, already validated by the router
                    else:
                        good = all(s.ok(p, q, L) for p, q in zip(c, c[1:]))
                    if good:
                        out += c[1:]; i = j; done = True; break
                if done: break
            if not done: out.append(P[i + 1]); i += 1
        # drop collinear interior points
        red = [out[0]]
        for k in range(1, len(out) - 1):
            a, b, c = red[-1], out[k], out[k + 1]
            if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9: red.append(b)
        red.append(out[-1])
        return red


def chains(segs, fixed):
    """segs: [(a,b,L)] -> [(L, [pts])], split at fixed points and nodes of degree != 2."""
    key = lambda p: (round(p[0], 4), round(p[1], 4), )
    out = []
    by_layer = defaultdict(list)
    for a, b, L in segs: by_layer[L].append((a, b))
    for L, ss in by_layer.items():
        adj = defaultdict(list); pt = {}
        for k, (a, b) in enumerate(ss):
            ka, kb = key(a), key(b); pt[ka] = a; pt[kb] = b
            adj[ka].append((k, kb)); adj[kb].append((k, ka))
        used = set()
        stop = lambda q: len(adj[q]) != 2 or q in fixed
        starts = [q for q in adj if stop(q)] + list(adj)
        for q0 in starts:
            for k, q1 in adj[q0]:
                if k in used: continue
                used.add(k); P = [pt[q0], pt[q1]]; q = q1
                while not stop(q):
                    nxt = [(kk, qq) for kk, qq in adj[q] if kk not in used]
                    if not nxt: break
                    kk, qq = nxt[0]; used.add(kk); P.append(pt[qq]); q = qq
                out.append((L, P))
    return out


def smooth_net(RT, net, width, n_items0, n_added0, log):
    B, R = RT.B, RT.R
    recs = RT.added[n_added0:]
    if not recs: return 0
    segs = [((r['start'][0], r['start'][1]), (r['end'][0], r['end'][1]), r['layer']) for r in recs if r['kind'] == 'segment']
    vias = [(r['at'][0], r['at'][1]) for r in recs if r['kind'] == 'via']
    g_before = B.clusters(only={net})[net].__len__()
    snap_items = B.items[n_items0:]; snap_added = RT.added[n_added0:]
    del B.items[n_items0:]; del RT.added[n_added0:]
    S = Smoother(B, R, net, width)
    fixed = {(round(x, 4), round(y, 4)) for x, y in vias}
    new_segs = []
    for L, P in chains(segs, fixed):
        Q = S.smooth_chain(P, L)
        new_segs += [(a, b, L) for a, b in zip(Q, Q[1:]) if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6]
    RT.add_to_board(new_segs, vias, net, width, net)
    if len(B.clusters(only={net})[net]) != g_before or any(a.new and a.net == net for a, p in dangling(B)):
        log(f'  [{net}] smoothing changed connectivity -> keep unsmoothed')
        del B.items[n_items0:]; del RT.added[n_added0:]
        B.items += snap_items; RT.added += snap_added
        return 0
    log(f'  [{net}] smoothed {len(segs)} -> {len(new_segs)} segments, {len(vias)} vias')
    return len(segs) - len(new_segs)


if __name__ == '__main__':
    a = sys.argv[1:]
    vc = 4.0; dry = False
    if '--via-cost' in a: i = a.index('--via-cost'); vc = float(a[i + 1]); del a[i:i + 2]
    if '--dry' in a: a.remove('--dry'); dry = True
    D = Path(a[0]); tag = a[1]; nets = a[2:]
    out = D.parent / 'evidence' / tag; out.mkdir(parents=True, exist_ok=True)
    B, R = load(D); RT = Router(B, R); logs = []
    def log(*x): s_ = ' '.join(str(v) for v in x); print(s_, flush=True); logs.append(s_)
    g0 = sum(B.gaps().values()); res = {}
    for net in nets:
        t = time.time(); w = 0.3 if R.nc(net) == 'Power' else (0.22 if R.nc(net) == 'USB' else 0.2)
        n0, k0 = RT.snapshot()
        done, failed = route_net(RT, net, w, via_cost=vc, log=log)
        smooth_net(RT, net, w, n0, k0, log)
        res[net] = dict(done=done, failed=failed, sec=round(time.time() - t, 1)); log(net, res[net])
    V = drc_lite(B, R, 'new'); dl = [x for x, p in dangling(B) if x.new]
    g1 = sum(B.gaps().values())
    nv = sum(1 for r in RT.added if r['kind'] == 'via'); ns = len(RT.added) - nv
    log(f'gaps {g0}->{g1}; new segments {ns}, vias {nv}; drc_lite(new) {len(V)}; dangling(new) {len(dl)}')
    for v in V[:10]: log('  VIOL', v)
    if V or dl: sys.exit('self-check failed, nothing written')
    if RT.added and not dry:
        P = Pcb(D / 'evt0_core.kicad_pcb'); P.insert_copper(RT.added, emit_blocks); P.save()
    json.dump(dict(note='r6_route (r5_route grid + exact smoothing); zy_pcb self-check, NOT KiCad native DRC',
                   via_cost=vc, gaps_before=g0, gaps_after=g1, result=res, added_copper=RT.added),
              open(out / 'added_copper.json', 'w'), indent=1)
    (out / 'route_log.txt').write_text('\n'.join(logs) + '\n')
