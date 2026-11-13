
"""r5_run: 驱动 r5_route 对指定网络布线。输出: 新增铜记录 JSON + 插入后的 kicad_pcb。仅新增 segment/via。"""
import json, math, sys, time, hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from r5_route import *

def check_new(B, R, new_idx):
    """新增铜 vs 全部既有铜的精确检查 (复用 drc_lite 的判据, 仅遍历 新x全部)。"""
    items = B.items; V = []
    nset = set(new_idx)
    def bbox(it):
        return shape_bbox(it.shape, 0.0)
    bbs = {}
    ex0, ey0, ex1, ey1 = B.edge
    for a in new_idx:
        A = items[a]; ba = bbox(A)
        if min(ba[0]-ex0, ba[1]-ey0, ex1-ba[2], ey1-ba[3]) < R.edge-EPS: V.append(('copper_edge_clearance', A, None))
        for k in B.keepouts:
            if dist(A.shape, ('poly', k, 0.0)) <= 0: V.append(('keepout', A, None))
        if A.kind == 'trk':
            cls = R.nc(A.net)
            if A.w < R.min_trk-EPS or (cls == 'Power' and A.w < 0.3-EPS) or (cls == 'USB' and not (0.18-EPS <= A.w <= 0.25+EPS)): V.append(('track_width', A, None))
        if A.kind == 'via':
            if A.drill < R.min_drill-EPS: V.append(('drill', A, None))
            if (A.w-A.drill)/2 < R.min_ann-EPS or A.w < R.min_via-EPS: V.append(('annular', A, None))
        for c, C in enumerate(items):
            if c == a: continue
            if c in nset and c < a: continue
            bc = bbox(C)
            if ba[0] > bc[2]+0.6 or bc[0] > ba[2]+0.6 or ba[1] > bc[3]+0.6 or bc[1] > ba[3]+0.6: continue
            if A.net != C.net or not A.net:
                if A.layers & C.layers:
                    need = R.clr(A.net, C.net); d = dist(A.shape, C.shape)
                    if d < need-EPS: V.append(('shorting' if d <= 0 else 'clearance', A, C, round(d, 4), need))
                for H, O in ((A, C), (C, A)):
                    if H.hole and O.layers:
                        d = dist(H.hole, O.shape)
                        if d < R.hole_clr-EPS: V.append(('hole_clearance', H, O, round(d, 4), R.hole_clr))
            if A.hole and C.hole:
                d = dist(A.hole, C.hole)
                if d < R.h2h-EPS and not (A.kind == 'pad' and C.kind == 'pad'): V.append(('hole_to_hole', A, C, round(d, 4), R.h2h))
    return V

def proj_on_track(it, x, y):
    x1, y1, x2, y2 = it.shape[1:5]; dx, dy = x2-x1, y2-y1; L = dx*dx+dy*dy
    t = 0 if L == 0 else max(0, min(1, ((x-x1)*dx+(y-y1)*dy)/L))
    return (x1+t*dx, y1+t*dy)

def anchor_of(RT, idx, cell_xy):
    it = RT.B.items[idx]
    if it.kind == 'trk': return proj_on_track(it, *cell_xy)
    return (it.x, it.y)

def cluster_xy(B, c):
    return np.array([B.items[i].anchors[0] for i in c])

def route_net(RT, net, width, via_cost=2.0, plane=False, margins=(7.0, 14.0, 30.0), extras=(0.03, 0.06, 0.1), log=print, only_clusters=None, max_conn=99):
    B, R = RT.B, RT.R
    hw = width/2; done = 0; failed = []
    for _ in range(max_conn):
        cl = B.clusters(only={net})[net]
        if len(cl) <= 1: break
        order = sorted(range(len(cl)), key=lambda k: len(cl[k]))
        ok_any = False
        for ci in order[:-1] if not plane else order:
            c = cl[ci]
            if only_clusters is not None and not any(B.items[i].kind == 'pad' and f"{B.items[i].ref}.{B.items[i].num}" in only_clusters for i in c): continue
            if plane:
                dcand = []
            XY = cluster_xy(B, c)
            best = None
            for di, d in enumerate(cl):
                if di == ci: continue
                XD = cluster_xy(B, d)
                D = np.hypot(XY[:, None, 0]-XD[None, :, 0], XY[:, None, 1]-XD[None, :, 1])
                a, b = np.unravel_index(np.argmin(D), D.shape)
                if best is None or D[a, b] < best[0]: best = (D[a, b], di, a, b)
            if best is None: continue
            dist0, di, a, b = best
            d = cl[di]
            for mg, ex in zip(margins, extras):
                pa = XY[a]; pb = cluster_xy(B, d)[b]
                x0, x1 = min(pa[0], pb[0])-mg, max(pa[0], pb[0])+mg; y0, y1 = min(pa[1], pb[1])-mg, max(pa[1], pb[1])+mg
                ex0, ey0, ex1, ey1 = B.edge; x0 = max(x0, ex0); y0 = max(y0, ey0); x1 = min(x1, ex1); y1 = min(y1, ey1)
                win = Win(x0, y0, x1, y1)
                tm, vm = RT.build_masks(win, net, width, extra=ex)
                src = RT.attach_cells(win, c, net, hw)
                dst = RT.attach_cells(win, d, net, hw)
                if not any(src.values()) or (not plane and not any(dst.values())): continue
                path = RT.search(win, tm, vm, src, None if plane else dst, via_cost=via_cost, goal_via_drop=plane)
                if not path: continue
                def free_cb(L, i, j, tm=tm, win=win): return win.inside(i, j) and not tm[L][i, j]
                path = RT.octilinear_simplify(path, free_cb) if len(path) > 2 else path
                # anchors
                (L0, i0, j0) = path[0]; (L1, i1, j1) = path[-1]
                a_item = src[L0].get((i0, j0)); a_anchor = anchor_of(RT, a_item, win.xy(i0, j0)) if a_item is not None else None
                if plane:
                    b_anchor = None
                else:
                    b_item = dst[L1].get((i1, j1)); b_anchor = anchor_of(RT, b_item, win.xy(i1, j1)) if b_item is not None else None
                snap = RT.snapshot()
                segs, vias = RT.commit_path(win, path, net, width, a_anchor, b_anchor, f"{net}")
                if plane: vias.append(win.xy(i1, j1))
                n0 = len(B.items)
                RT.add_to_board(segs, vias, net, width, net)
                V = check_new(B, R, list(range(n0, len(B.items))))
                if V:
                    log(f"  [{net}] margin={mg} extra={ex}: {len(V)} viol e.g. {V[0][0]} -> retry")
                    RT.rollback(*snap); continue
                # 连通性确认
                cl2 = B.clusters(only={net})[net]
                if len(cl2) < len(cl):
                    log(f"  [{net}] connected cluster ({len(c)} items) -> nearest ({len(d)} items): {len(segs)} seg, {len(vias)} via; gaps {len(cl)-1}->{len(cl2)-1}")
                    done += 1; ok_any = True; break
                else:
                    log(f"  [{net}] path committed but cluster count unchanged -> rollback"); RT.rollback(*snap)
            if ok_any: break
        if not ok_any:
            failed.append(net); log(f"  [{net}] UNROUTED, remaining gaps {len(cl)-1}"); break
    return done, failed

def load(D):
    B = Board(D/'evt0_core.kicad_pcb'); R = Rules(D/'evt0_core.kicad_pro')
    return B, R

if __name__ == '__main__':
    D = Path(sys.argv[1]); nets = sys.argv[2:]
    B, R = load(D); RT = Router(B, R)
    for n in nets:
        t = time.time(); w = 0.3 if R.nc(n) == 'Power' else 0.2
        print(n, route_net(RT, n, w), f"{time.time()-t:.1f}s")
    print('gaps now', sum(B.gaps().values()), 'added', len(RT.added))