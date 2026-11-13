"""r5_route: R4 -> R5 增量布线器 (纯 Python/numpy/scipy, 不依赖 pcbnew)。
复用 zy_pcb.Board/Rules/drc_lite (19:47 已校准: 原生 DRC 58/58 对应)。本工具只新增 segment/via 文本块,
不移动/删除任何既有铜、封装、焊盘、DNP, 不改规则。结果必须再用原生 KiCad DRC 复核 (本沙箱无 kicad-cli)。
"""
import math, uuid, json, sys, heapq, time
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from matplotlib.path import Path as MPath
sys.path.insert(0, str(Path(__file__).parent))
from zy_pcb import Board, Rules, drc_lite, dist, contains, dangling, CU, EPS

G = 0.05            # 栅格 mm
VIA_D, VIA_DRILL = 0.6, 0.3          # 与 R4 现有过孔一致 (DRU: 孔径>=0.3)
ROUTE_LAYERS = ('F.Cu', 'B.Cu')      # In1/In2 为 GND/3V3 整面平面, 不走信号
LIDX = {'F.Cu': 0, 'B.Cu': 1}


def shape_bbox(sh, m=0.0):
    if sh[0] == 'cap':
        return (min(sh[1], sh[3]) - sh[5] - m, min(sh[2], sh[4]) - sh[5] - m, max(sh[1], sh[3]) + sh[5] + m, max(sh[2], sh[4]) + sh[5] + m)
    xs = [p[0] for p in sh[1]]; ys = [p[1] for p in sh[1]]
    return (min(xs) - sh[2] - m, min(ys) - sh[2] - m, max(xs) + sh[2] + m, max(ys) + sh[2] + m)


class Win:
    """栅格窗口: 世界坐标 <-> 格点。"""
    def __init__(s, x0, y0, x1, y1):
        s.x0 = math.floor(x0 / G) * G; s.y0 = math.floor(y0 / G) * G
        s.nx = int(math.ceil((x1 - s.x0) / G)) + 1; s.ny = int(math.ceil((y1 - s.y0) / G)) + 1
        xs = s.x0 + np.arange(s.nx) * G; ys = s.y0 + np.arange(s.ny) * G
        s.X, s.Y = np.meshgrid(xs, ys, indexing='xy')     # shape (ny, nx)
    def ij(s, x, y): return int(round((y - s.y0) / G)), int(round((x - s.x0) / G))
    def xy(s, i, j): return (s.x0 + j * G, s.y0 + i * G)
    def inside(s, i, j): return 0 <= i < s.ny and 0 <= j < s.nx


def dist_field(win, sh):
    """栅格各点到形状(边界, 内部为0)的距离, 仅限包围盒附近(其余设为大数)。返回 (slice_i, slice_j, dist_array)。"""
    return None


def mask_item(win, sh, R):
    """返回 (si, sj, bool_mask) : 距形状 < R 的格点。"""
    bx0, by0, bx1, by1 = shape_bbox(sh, R)
    j0 = max(0, int(math.floor((bx0 - win.x0) / G))); j1 = min(win.nx, int(math.ceil((bx1 - win.x0) / G)) + 1)
    i0 = max(0, int(math.floor((by0 - win.y0) / G))); i1 = min(win.ny, int(math.ceil((by1 - win.y0) / G)) + 1)
    if i0 >= i1 or j0 >= j1: return None
    X = win.X[i0:i1, j0:j1]; Y = win.Y[i0:i1, j0:j1]
    if sh[0] == 'cap':
        x1, y1, x2, y2, r = sh[1:6]
        dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
        if L == 0: d = np.hypot(X - x1, Y - y1)
        else:
            t = np.clip(((X - x1) * dx + (Y - y1) * dy) / L, 0, 1)
            d = np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy))
        m = d < (r + R)
    else:
        P = sh[1]; rr = sh[2]
        cx = sum(p[0] for p in P) / 4; cy = sum(p[1] for p in P) / 4
        ex = (P[1][0] - P[0][0], P[1][1] - P[0][1]); ey = (P[3][0] - P[0][0], P[3][1] - P[0][1])
        lx_ = math.hypot(*ex); ly_ = math.hypot(*ey)
        ux = (ex[0] / lx_, ex[1] / lx_); uy = (ey[0] / ly_, ey[1] / ly_)
        px = (X - cx) * ux[0] + (Y - cy) * ux[1]; py = (X - cx) * uy[0] + (Y - cy) * uy[1]
        ax_ = np.maximum(np.abs(px) - lx_ / 2, 0); ay_ = np.maximum(np.abs(py) - ly_ / 2, 0)
        d = np.hypot(ax_, ay_)
        m = d < (rr + R)
    return (slice(i0, i1), slice(j0, j1), m)


class Router:
    def __init__(s, board, rules, log=print):
        s.B, s.R, s.log = board, rules, log
        s.added = []          # 新增铜记录 dict
        s.net_of_uuid = {}

    # ------------------------------------------------------------------ obstacles
    def build_masks(s, win, net, width, extra=0.03):
        """返回 trk_mask[layer] (中心线禁入) 与 via_mask (过孔中心禁入, 贯穿所有铜层)。同网铜不是障碍。"""
        R = s.R; hw = width / 2
        tm = {L: np.zeros((win.ny, win.nx), bool) for L in ROUTE_LAYERS}
        vm = np.zeros((win.ny, win.nx), bool)
        vr = VIA_D / 2
        wb = (win.x0, win.y0, win.x0 + win.nx * G, win.y0 + win.ny * G)
        for it in s.B.items:
            if not it.layers and not (it.kind == 'pad' and it.hole): continue
            bb = shape_bbox(it.shape, 2.0)
            if bb[0] > wb[2] or bb[2] < wb[0] or bb[1] > wb[3] or bb[3] < wb[1]: continue
            other = (it.net != net) or not it.net
            if other and it.layers:
                clr = R.clr(net, it.net) if it.net else R.clr(net, net)
                for L in ROUTE_LAYERS:
                    if L in it.layers:
                        r = mask_item(win, it.shape, clr + hw + extra)
                        if r: tm[L][r[0], r[1]] |= r[2]
                r = mask_item(win, it.shape, clr + vr + extra)       # 过孔贯穿所有层: 任一铜层上的他网铜都约束过孔
                if r: vm[r[0], r[1]] |= r[2]
            if it.hole and (other or it.kind == 'pad' and not it.net):
                # 他网/无网孔: 走线边缘到孔边 >= hole_clr ; 过孔外圆到孔边 >= hole_clr; 孔到孔 >= h2h
                hh = it.hole
                for L in ROUTE_LAYERS:
                    r = mask_item(win, hh, R.hole_clr + hw + extra)
                    if r: tm[L][r[0], r[1]] |= r[2]
                r = mask_item(win, hh, max(R.hole_clr + vr, R.h2h + VIA_DRILL / 2) + extra)
                if r: vm[r[0], r[1]] |= r[2]
            elif it.hole and not other:
                pass
        # 他网过孔(贯穿)对本层走线 (已含于 it.layers=CU) ; 关键字: 板边与禁布区
        ex0, ey0, ex1, ey1 = s.B.edge
        for (rect) in ((ex0 - 5, ey0 - 5, ex1 + 5, ey0), (ex0 - 5, ey1, ex1 + 5, ey1 + 5), (ex0 - 5, ey0 - 5, ex0, ey1 + 5), (ex1, ey0 - 5, ex1 + 5, ey1 + 5)):
            pass
        Xc, Yc = win.X, win.Y
        e = R.edge + 0.02 + extra
        edge_t = (Xc < ex0 + e + hw) | (Xc > ex1 - e - hw) | (Yc < ey0 + e + hw) | (Yc > ey1 - e - hw)
        edge_v = (Xc < ex0 + e + vr) | (Xc > ex1 - e - vr) | (Yc < ey0 + e + vr) | (Yc > ey1 - e - vr)
        for L in ROUTE_LAYERS: tm[L] |= edge_t
        vm |= edge_v
        pts = np.column_stack([Xc.ravel(), Yc.ravel()])
        for k in s.B.keepouts:
            inside = MPath(k).contains_points(pts).reshape(Xc.shape)
            grow = int(math.ceil((hw + 0.1) / G)); growv = int(math.ceil((vr + 0.1) / G))
            for L in ROUTE_LAYERS: tm[L] |= ndimage.binary_dilation(inside, iterations=grow)
            vm |= ndimage.binary_dilation(inside, iterations=growv)
        return tm, vm

    # ------------------------------------------------------------------ cluster cells
    def core_cells(s, win, sh, hw):
        """形状收缩 hw 后的格点集合 (走线可完整落在铜内); 过小则只取中心最近格点。"""
        bx0, by0, bx1, by1 = shape_bbox(sh, 0.0)
        j0 = max(0, int(math.floor((bx0 - win.x0) / G))); j1 = min(win.nx, int(math.ceil((bx1 - win.x0) / G)) + 1)
        i0 = max(0, int(math.floor((by0 - win.y0) / G))); i1 = min(win.ny, int(math.ceil((by1 - win.y0) / G)) + 1)
        if i0 >= i1 or j0 >= j1: return []
        X = win.X[i0:i1, j0:j1]; Y = win.Y[i0:i1, j0:j1]
        if sh[0] == 'cap':
            x1, y1, x2, y2, r = sh[1:6]
            dx, dy = x2 - x1, y2 - y1; Lq = dx * dx + dy * dy
            if Lq == 0: d = np.hypot(X - x1, Y - y1)
            else:
                t = np.clip(((X - x1) * dx + (Y - y1) * dy) / Lq, 0, 1); d = np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy))
            m = d <= max(r - hw, 0.0) + 1e-9
        else:
            P = sh[1]; rr = sh[2]
            cx = sum(p[0] for p in P) / 4; cy = sum(p[1] for p in P) / 4
            ex = (P[1][0] - P[0][0], P[1][1] - P[0][1]); ey = (P[3][0] - P[0][0], P[3][1] - P[0][1])
            lx_ = math.hypot(*ex); ly_ = math.hypot(*ey)
            ux = (ex[0] / lx_, ex[1] / lx_); uy = (ey[0] / ly_, ey[1] / ly_)
            px = (X - cx) * ux[0] + (Y - cy) * ux[1]; py = (X - cx) * uy[0] + (Y - cy) * uy[1]
            m = (np.abs(px) <= max(lx_ / 2 - hw, 0) + 1e-9) & (np.abs(py) <= max(ly_ / 2 - hw, 0) + 1e-9)
        ii, jj = np.nonzero(m)
        return [(i0 + a, j0 + b) for a, b in zip(ii, jj)]

    def attach_cells(s, win, items_idx, net, hw):
        """某簇的起/终格点: {layer: {(i,j): item_idx}}。焊盘取收缩核心格点, 走线取中心线, 过孔取中心。"""
        out = {L: {} for L in ROUTE_LAYERS}
        for idx in items_idx:
            it = s.B.items[idx]; sh = it.shape
            for L in ROUTE_LAYERS:
                if L not in it.layers: continue
                if it.kind == 'pad':
                    cells = s.core_cells(win, sh, hw)
                    ci, cj = win.ij(it.x, it.y)
                    if win.inside(ci, cj): cells = cells + [(ci, cj)]
                    for c in cells: out[L].setdefault(c, idx)
                elif it.kind == 'trk':
                    x1, y1, x2, y2 = sh[1:5]
                    n = max(1, int(math.hypot(x2 - x1, y2 - y1) / (G * 0.5)))
                    for k in range(n + 1):
                        x = x1 + (x2 - x1) * k / n; y = y1 + (y2 - y1) * k / n
                        i, j = win.ij(x, y)
                        if win.inside(i, j): out[L].setdefault((i, j), idx)
                else:
                    i, j = win.ij(it.x, it.y)
                    if win.inside(i, j): out[L][(i, j)] = idx
        return out

    # ------------------------------------------------------------------ search
    def search(s, win, tm, vm, src, dst, via_cost=2.0, allow_via=True, goal_via_drop=False, bend_eps=1e-4):
        """多源最短路 (scipy Dijkstra)。节点 = layer*N + i*nx + j。src/dst: {layer:set((i,j))}。
        goal_via_drop: 目标是"任意可放过孔的格点" (平面网络, 如 GND)。返回路径节点列表 [(layer,i,j)...] 或 None。"""
        ny, nx = win.ny, win.nx; N = ny * nx
        free = np.stack([~tm['F.Cu'], ~tm['B.Cu']])        # (2, ny, nx)
        # 源/目标格点即使落在"禁入"里 (焊盘/同网铜内部边缘), 也强制可通行
        for L in ROUTE_LAYERS:
            for (i, j) in src[L]: free[LIDX[L], i, j] = True
            if dst is not None:
                for (i, j) in dst[L]: free[LIDX[L], i, j] = True
        idx = np.arange(2 * N).reshape(2, ny, nx)
        rows = []; cols = []; wts = []
        def add(a_mask, a_idx, b_idx, w):
            rows.append(a_idx[a_mask]); cols.append(b_idx[a_mask]); wts.append(np.full(a_mask.sum(), w))
        for l in (0, 1):
            f = free[l]; ix = idx[l]
            # 4 邻
            for di, dj, w in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2))):
                i0 = slice(0, ny - di); i1 = slice(di, ny)
                if dj >= 0: j0 = slice(0, nx - dj); j1 = slice(dj, nx)
                else: j0 = slice(-dj, nx); j1 = slice(0, nx + dj)
                m = f[i0, j0] & f[i1, j1]
                if di == 1 and abs(dj) == 1:   # 对角线不得切角: 两个直角邻也须空闲
                    if dj == 1: m &= f[i0, j1] & f[i1, j0]
                    else: m &= f[i0, j1] & f[i1, j0]
                a = ix[i0, j0]; b = ix[i1, j1]
                rows.append(a[m]); cols.append(b[m]); wts.append(np.full(m.sum(), w * G))
                rows.append(b[m]); cols.append(a[m]); wts.append(np.full(m.sum(), w * G))
        if allow_via:
            ok = (~vm) & free[0] & free[1]
            a = idx[0][ok]; b = idx[1][ok]
            rows += [a, b]; cols += [b, a]; wts += [np.full(a.size, via_cost), np.full(a.size, via_cost)]
        r = np.concatenate(rows); c = np.concatenate(cols); w = np.concatenate(wts)
        Gm = csr_matrix((w, (r, c)), shape=(2 * N, 2 * N))
        sidx = [LIDX[L] * N + i * nx + j for L in ROUTE_LAYERS for (i, j) in src[L]]
        if not sidx: return None
        d, pred, srcs = dijkstra(Gm, directed=True, indices=sidx, return_predecessors=True, min_only=True)
        if goal_via_drop:
            ok = (~vm)
            cand = np.where(np.isfinite(d[:N]) & ok.ravel() & free[0].ravel() & free[1].ravel(), d[:N], np.inf)
            cand2 = np.where(np.isfinite(d[N:]) & ok.ravel() & free[0].ravel() & free[1].ravel(), d[N:], np.inf)
            k0 = int(np.argmin(cand)); k1 = int(np.argmin(cand2))
            if min(cand[k0], cand2[k1]) == np.inf: return None
            node = k0 if cand[k0] <= cand2[k1] else N + k1
        else:
            didx = [LIDX[L] * N + i * nx + j for L in ROUTE_LAYERS for (i, j) in dst[L]]
            if not didx: return None
            dd = d[didx]
            k = int(np.argmin(dd))
            if not np.isfinite(dd[k]): return None
            node = didx[k]
        path = []
        while True:
            l, rem = divmod(node, N); i, j = divmod(rem, nx)
            path.append((ROUTE_LAYERS[l], i, j))
            p = pred[node]
            if p < 0: break
            node = p
        path.reverse()
        return path

    # ------------------------------------------------------------------ path -> geometry
    @staticmethod
    def octilinear_simplify(path, free_cb):
        """沿同层连续的格点段, 贪心地把子路径替换为 <=2 段 (正交/45度) 折线, 只要沿途格点全空闲。"""
        out = [path[0]]; k = 0; n = len(path)
        while k < n - 1:
            L = path[k][0]; best = k + 1
            # 同层区间终点
            e = k
            while e + 1 < n and path[e + 1][0] == L: e += 1
            if e == k: out.append(path[k + 1]); k += 1; continue
            far = e
            while far > k + 1:
                a = path[k]; b = path[far]
                pts = Router._two_seg(a, b, free_cb, L)
                if pts is not None:
                    out.extend(pts); k = far; break
                far -= 1
            else:
                out.append(path[k + 1]); k += 1
        return out

    @staticmethod
    def _two_seg(a, b, free_cb, L):
        (_, i0, j0), (_, i1, j1) = a, b
        di, dj = i1 - i0, j1 - j0
        adi, adj = abs(di), abs(dj)
        sdi = int(di > 0) - int(di < 0); sdj = int(dj > 0) - int(dj < 0)
        cands = []
        if adi == 0 or adj == 0 or adi == adj: cands.append([(i1, j1)])
        else:
            m = min(adi, adj)
            # 先对角后直线 / 先直线后对角
            cands.append([(i0 + sdi * m, j0 + sdj * m), (i1, j1)])
            if adi > adj: cands.append([(i0 + sdi * (adi - m), j0), (i1, j1)])
            else: cands.append([(i0, j0 + sdj * (adj - m)), (i1, j1)])
        for c in cands:
            cur = (i0, j0); ok = True
            for nxt in c:
                if not Router._line_free(cur, nxt, free_cb, L): ok = False; break
                cur = nxt
            if ok: return [(L, p[0], p[1]) for p in c]
        return None

    @staticmethod
    def _line_free(p, q, free_cb, L):
        di = int(q[0] > p[0]) - int(q[0] < p[0]); dj = int(q[1] > p[1]) - int(q[1] < p[1])
        i, j = p
        while (i, j) != q:
            ni, nj = i + di, j + dj
            if not free_cb(L, ni, nj): return False
            if di != 0 and dj != 0 and not (free_cb(L, i, nj) and free_cb(L, ni, j)): return False
            i, j = ni, nj
        return True

    # ------------------------------------------------------------------ commit
    def commit_path(s, win, path_cells, net, width, anchor_from, anchor_to, tag):
        """把格点路径转成 segment/via; 起止点吸附到精确锚点 (焊盘中心/既有走线上的点)。"""
        segs = []; vias = []
        pts = [(L, *win.xy(i, j)) for (L, i, j) in path_cells]
        # 拆分层
        runs = []; cur = [pts[0]]
        for p in pts[1:]:
            if p[0] == cur[-1][0]: cur.append(p)
            else: runs.append(cur); vias.append((cur[-1][1], cur[-1][2])); cur = [p]
        runs.append(cur)
        if anchor_from is not None:
            ax_, ay_ = anchor_from; L0, x0_, y0_ = runs[0][0]; runs[0][0] = (L0, ax_, ay_)
        if anchor_to is not None:
            ax_, ay_ = anchor_to; Ln, xn, yn = runs[-1][-1]; runs[-1][-1] = (Ln, ax_, ay_)
        for run in runs:
            # 去共线点
            L = run[0][0]; q = [(p[1], p[2]) for p in run]
            red = [q[0]]
            for k in range(1, len(q) - 1):
                a, b, c = red[-1], q[k], q[k + 1]
                cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
                if abs(cr) > 1e-9: red.append(b)
            red.append(q[-1])
            for a, b in zip(red, red[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6: continue
                segs.append((a, b, L))
        return segs, vias

    def add_to_board(s, segs, vias, net, width, tag):
        recs = []
        for (a, b, L) in segs:
            u = str(uuid.uuid4())
            s.B.add_track(a[0], a[1], b[0], b[1], width, L, net, u, True)
            recs.append(dict(kind='segment', start=[round(a[0], 4), round(a[1], 4)], end=[round(b[0], 4), round(b[1], 4)], width=width, layer=L, net=net, uuid=u, tag=tag))
        for (x, y) in vias:
            u = str(uuid.uuid4())
            s.B.add_via(x, y, VIA_D, VIA_DRILL, net, u, True)
            recs.append(dict(kind='via', at=[round(x, 4), round(y, 4)], size=VIA_D, drill=VIA_DRILL, layers=['F.Cu', 'B.Cu'], net=net, uuid=u, tag=tag))
        s.added += recs
        return recs

    def snapshot(s): return len(s.B.items), len(s.added)

    def rollback(s, n_items, n_added):
        del s.B.items[n_items:]; del s.added[n_added:]


def fmt(v):
    t = f"{v:.4f}".rstrip('0').rstrip('.')
    return t if t not in ('-0', '') else '0'


def emit_blocks(recs):
    out = []
    for r in recs:
        if r['kind'] == 'segment':
            out.append(f"\t(segment\r\n\t\t(start {fmt(r['start'][0])} {fmt(r['start'][1])})\r\n\t\t(end {fmt(r['end'][0])} {fmt(r['end'][1])})\r\n\t\t(width {fmt(r['width'])})\r\n\t\t(layer \"{r['layer']}\")\r\n\t\t(net \"{r['net']}\")\r\n\t\t(uuid \"{r['uuid']}\")\r\n\t)\r\n")
        else:
            out.append(f"\t(via\r\n\t\t(at {fmt(r['at'][0])} {fmt(r['at'][1])})\r\n\t\t(size {fmt(r['size'])})\r\n\t\t(drill {fmt(r['drill'])})\r\n\t\t(layers \"F.Cu\" \"B.Cu\")\r\n\t\t(net \"{r['net']}\")\r\n\t\t(uuid \"{r['uuid']}\")\r\n\t)\r\n")
    return ''.join(out)
