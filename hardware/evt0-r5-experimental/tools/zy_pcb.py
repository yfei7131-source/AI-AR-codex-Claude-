"""zy_pcb: 校准后的 PCB 几何/连通性/规则自检 (非 KiCad 原生 DRC, 仅辅助)。
连通模型按 KiCad 的“锚点落入对方铜形”规则: 走线锚点=两端点, 过孔/焊盘锚点=中心;
任一方锚点落入另一方同层铜形即连通。平面网络(In1 GND / In2 3V3)按铺铜轮廓连通。"""
import math, json, re, sys
from pathlib import Path
from collections import defaultdict
from sx import parse, find, one
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')
EPS = 1e-6
def rot(x, y, a):
    r = math.radians(a); c, s = math.cos(r), math.sin(r)
    return (x*c + y*s, -x*s + y*c)
# ---------- shapes: ('cap',x1,y1,x2,y2,r) or ('poly',[(x,y)...]) ----------
def d_pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1; L = dx*dx+dy*dy
    t = 0 if L == 0 else max(0, min(1, ((px-x1)*dx+(py-y1)*dy)/L))
    return math.hypot(px-(x1+t*dx), py-(y1+t*dy))
def _orient(ax, ay, bx, by, cx, cy): return (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)
def seg_x(a, b, c, d):
    o1 = _orient(*a, *b, *c); o2 = _orient(*a, *b, *d); o3 = _orient(*c, *d, *a); o4 = _orient(*c, *d, *b)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and o1*o2 != 0 and o3*o4 != 0
def d_seg_seg(a, b, c, d):
    if seg_x(a, b, c, d): return 0.0
    return min(d_pt_seg(*a, *c, *d), d_pt_seg(*b, *c, *d), d_pt_seg(*c, *a, *b), d_pt_seg(*d, *a, *b))
def pt_in_poly(x, y, P):
    ins = False; n = len(P)
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i+1) % n]
        if (y1 > y) != (y2 > y) and x < x1+(y-y1)*(x2-x1)/(y2-y1): ins = not ins
    return ins
def d_seg_poly(a, b, P):
    if pt_in_poly(*a, P) or pt_in_poly(*b, P): return 0.0
    return min(d_seg_seg(a, b, P[i], P[(i+1) % len(P)]) for i in range(len(P)))
def dist(s, t):
    """edge-to-edge distance between two shapes (<=0 means overlap)"""
    if s[0] == 'cap' and t[0] == 'cap':
        return d_seg_seg((s[1], s[2]), (s[3], s[4]), (t[1], t[2]), (t[3], t[4]))-s[5]-t[5]
    if s[0] == 'poly' and t[0] == 'cap': s, t = t, s
    if s[0] == 'cap':
        return d_seg_poly((s[1], s[2]), (s[3], s[4]), t[1])-s[5]-t[2]
    P, Q = s[1], t[1]
    if pt_in_poly(*P[0], Q) or pt_in_poly(*Q[0], P): return -s[2]-t[2]
    return -s[2]-t[2]+min(d_seg_seg(P[i], P[(i+1) % len(P)], Q[j], Q[(j+1) % len(Q)]) for i in range(len(P)) for j in range(len(Q)))
def contains(s, x, y):
    if s[0] == 'cap': return d_pt_seg(x, y, s[1], s[2], s[3], s[4]) <= s[5]+EPS
    return pt_in_poly(x, y, s[1]) or min(d_pt_seg(x, y, *s[1][i], *s[1][(i+1) % len(s[1])]) for i in range(len(s[1]))) <= s[2]+EPS
# ---------- board model ----------
class It:
    __slots__ = ('kind', 'net', 'layers', 'shape', 'anchors', 'ref', 'num', 'drill', 'hole', 'w', 'uuid', 'ptype', 'new', 'x', 'y')
    def __repr__(s): return f"{s.kind}:{s.ref or ''}{'.'+s.num if s.num else ''}[{s.net}]@{s.anchors[0][0]:.3f},{s.anchors[0][1]:.3f}"
def pad_shape(shape, x, y, w, h, ang, rr=0.0):
    if shape == 'circle': return ('cap', x, y, x, y, w/2)
    if shape == 'oval':
        if w >= h: dx, dy = rot((w-h)/2, 0, ang); r = h/2
        else: dx, dy = rot(0, (h-w)/2, ang); r = w/2
        return ('cap', x-dx, y-dy, x+dx, y+dy, r)
    r = rr*min(w, h) if shape == 'roundrect' else 0.0
    pts = []
    for sx_, sy_ in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        dx, dy = rot(sx_*(w/2-r), sy_*(h/2-r), ang); pts.append((x+dx, y+dy))
    return ('poly', pts, r)   # roundrect = 内缩矩形 + 圆角半径 r (精确)
class Board:
    def __init__(s, path):
        s.path = Path(path); s.txt = open(path, newline='').read(); s.tree = parse(s.txt)
        b = s.tree; s.items = []; s.fps = {}; s.keepouts = []; s.zones = {}
        for fp in find(b, 'footprint'):
            ref = [p[2] for p in find(fp, 'property') if p[1] == 'Reference'][0]
            at = one(fp, 'at'); fx, fy = float(at[1]), float(at[2]); fa = float(at[3]) if len(at) > 3 else 0.0
            attr = one(fp, 'attr') or []
            s.fps[ref] = dict(x=fx, y=fy, a=fa, dnp='dnp' in attr, lib=fp[1], layer=one(fp, 'layer')[1])
            for p in find(fp, 'pad'):
                o = It(); o.kind = 'pad'; o.ref = ref; o.num = p[1]; o.ptype = p[2]; o.new = False
                pa = one(p, 'at'); ang = float(pa[3]) if len(pa) > 3 else 0.0
                dx, dy = rot(float(pa[1]), float(pa[2]), fa); x, y = fx+dx, fy+dy
                sz = one(p, 'size'); w, h = float(sz[1]), float(sz[2])
                rr_ = one(p, 'roundrect_rratio'); o.shape = pad_shape(p[3], x, y, w, h, ang, float(rr_[1]) if rr_ else 0.0); o.anchors = [(x, y)]; o.x, o.y = x, y; o.w = min(w, h)
                dr = one(p, 'drill'); o.drill = None; o.hole = None
                if dr:
                    nums = [float(v) for v in dr[1:] if not isinstance(v, list) and re.match(r'^[\d.]+$', v)]
                    if nums:
                        o.drill = min(nums)
                        if 'oval' in dr and len(nums) == 2: o.hole = pad_shape('oval', x, y, nums[0], nums[1], ang)
                        else: o.hole = ('cap', x, y, x, y, nums[0]/2)
                L = set()
                for l in one(p, 'layers')[1:]:
                    if l == '*.Cu': L |= set(CU)
                    elif l.endswith('.Cu'): L.add(l)
                if o.ptype == 'np_thru_hole': L = set()
                o.layers = L; n = one(p, 'net'); o.net = n[1] if n else ''; o.uuid = (one(p, 'uuid') or [0, ''])[1]
                s.items.append(o)
            for z in find(fp, 'zone'):
                if one(z, 'keepout'):
                    s.keepouts.append([(float(q[1]), float(q[2])) for q in find(one(one(z, 'polygon'), 'pts'), 'xy')])
        for g in find(b, 'segment'): s.add_track(*map(float, one(g, 'start')[1:3]), *map(float, one(g, 'end')[1:3]), float(one(g, 'width')[1]), one(g, 'layer')[1], one(g, 'net')[1], one(g, 'uuid')[1], False)
        for v in find(b, 'via'): s.add_via(float(one(v, 'at')[1]), float(one(v, 'at')[2]), float(one(v, 'size')[1]), float(one(v, 'drill')[1]), one(v, 'net')[1], one(v, 'uuid')[1], False)
        for z in find(b, 'zone'):
            if one(z, 'net') and one(z, 'layer'):
                s.zones[one(z, 'net')[1]] = (one(z, 'layer')[1], [(float(q[1]), float(q[2])) for q in find(one(one(z, 'polygon'), 'pts'), 'xy')])
        xs = []; ys = []
        for g in find(b, 'gr_line'):
            if one(g, 'layer')[1] == 'Edge.Cuts': xs += [float(one(g, 'start')[1]), float(one(g, 'end')[1])]; ys += [float(one(g, 'start')[2]), float(one(g, 'end')[2])]
        s.edge = (min(xs), min(ys), max(xs), max(ys))
    def add_track(s, x1, y1, x2, y2, w, layer, net, uuid='', new=True):
        o = It(); o.kind = 'trk'; o.net = net; o.layers = {layer}; o.shape = ('cap', x1, y1, x2, y2, w/2); o.anchors = [(x1, y1), (x2, y2)]
        o.ref = o.num = None; o.drill = None; o.hole = None; o.w = w; o.uuid = uuid; o.ptype = None; o.new = new; o.x, o.y = x1, y1; s.items.append(o); return o
    def add_via(s, x, y, d, drill, net, uuid='', new=True):
        o = It(); o.kind = 'via'; o.net = net; o.layers = set(CU); o.shape = ('cap', x, y, x, y, d/2); o.anchors = [(x, y)]
        o.ref = o.num = None; o.drill = drill; o.hole = ('cap', x, y, x, y, drill/2); o.w = d; o.uuid = uuid; o.ptype = None; o.new = new; o.x, o.y = x, y; s.items.append(o); return o
    # ----- connectivity -----
    def clusters(s, only=None):
        par = {}
        def fd(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        bynet = defaultdict(list)
        for i, it in enumerate(s.items):
            if it.net and it.layers and (only is None or it.net in only): bynet[it.net].append(i)
        out = {}
        for net, ids in bynet.items():
            for i in ids: par[i] = i
            for a in range(len(ids)):
                A = s.items[ids[a]]
                for c in range(a+1, len(ids)):
                    B = s.items[ids[c]]
                    if not (A.layers & B.layers): continue
                    if any(contains(B.shape, *p) for p in A.anchors) or any(contains(A.shape, *p) for p in B.anchors):
                        par[fd(ids[a])] = fd(ids[c])
            if net in s.zones:
                L, poly = s.zones[net]
                pl = [i for i in ids if L in s.items[i].layers and pt_in_poly(*s.items[i].anchors[0], poly)
                      and not any(pt_in_poly(*s.items[i].anchors[0], k) for k in s.keepouts)]
                for i in pl[1:]: par[fd(pl[0])] = fd(i)
            g = defaultdict(list)
            for i in ids: g[fd(i)].append(i)
            out[net] = list(g.values())
        return out
    def gaps(s):
        return {n: len(c)-1 for n, c in s.clusters().items() if len(c) > 1 and not n.startswith('unconnected')}
# ---------- rules (from evt0_core.kicad_pro / .kicad_dru; 不放宽) ----------
class Rules:
    def __init__(s, pro):
        p = json.load(open(pro)); ns = p['net_settings']
        s.cls = {c['name']: c for c in ns['classes']}; s.pat = [(q['pattern'], q['netclass']) for q in ns['netclass_patterns']]
        r = p['board']['design_settings']['rules']; s.r = r
        s.edge = r['min_copper_edge_clearance']; s.hole_clr = r['min_hole_clearance']; s.h2h = r['min_hole_to_hole']
        s.min_drill = r['min_through_hole_diameter']; s.min_trk = r['min_track_width']; s.min_ann = r['min_via_annular_width']; s.min_via = r['min_via_diameter']
    def nc(s, net):
        import fnmatch
        for pat, c in s.pat:
            if fnmatch.fnmatchcase(net, pat): return c
        return 'Default'
    def clr(s, a, b):
        ca, cb = s.nc(a), s.nc(b)
        c = max(s.cls[ca]['clearance'], s.cls[cb]['clearance'])
        if (ca == 'CamClk') != (cb == 'CamClk'):          # DRU: CamClk 对非CamClk且非Power >=0.3
            other = cb if ca == 'CamClk' else ca
            if other != 'Power': c = max(c, 0.3)
        return c
    def width(s, net): return 0.3 if s.nc(net) == 'Power' else 0.2
def drc_lite(B, R, scope='new'):
    """scope='new': 只检查涉及新增铜的对; 'all': 全部 (焊盘-焊盘除外, 属封装固有)。返回违规列表。"""
    V = []; items = B.items; n = len(items)
    bb = []
    for it in items:
        sh = it.shape
        if sh[0] == 'cap': bb.append((min(sh[1], sh[3])-sh[5], min(sh[2], sh[4])-sh[5], max(sh[1], sh[3])+sh[5], max(sh[2], sh[4])+sh[5]))
        else: xs = [p[0] for p in sh[1]]; ys = [p[1] for p in sh[1]]; bb.append((min(xs)-sh[2], min(ys)-sh[2], max(xs)+sh[2], max(ys)+sh[2]))
    ex0, ey0, ex1, ey1 = B.edge
    for i in range(n):
        A = items[i]
        if A.kind != 'pad' and (scope == 'all' or A.new):
            if A.layers:
                b_ = bb[i]
                if min(b_[0]-ex0, b_[1]-ey0, ex1-b_[2], ey1-b_[3]) < R.edge-EPS: V.append(('copper_edge_clearance', A, None, min(b_[0]-ex0, b_[1]-ey0, ex1-b_[2], ey1-b_[3])))
                for k in B.keepouts:
                    if dist(A.shape, ('poly', k, 0.0)) <= 0: V.append(('items_not_allowed(keepout)', A, None, 0))
            if A.kind == 'trk':
                cls = R.nc(A.net)
                if A.w < R.min_trk-EPS or (cls == 'Power' and A.w < 0.3-EPS) or (cls == 'USB' and not (0.18-EPS <= A.w <= 0.25+EPS)): V.append(('track_width', A, None, A.w))
            if A.kind == 'via':
                if A.drill < R.min_drill-EPS: V.append(('drill_out_of_range', A, None, A.drill))
                if (A.w-A.drill)/2 < R.min_ann-EPS or A.w < R.min_via-EPS: V.append(('annular/via_diameter', A, None, A.w))
        if A.kind == 'pad' and A.drill and A.ptype == 'thru_hole' and A.drill < R.min_drill-EPS and scope == 'all': V.append(('drill_out_of_range', A, None, A.drill))
        for j in range(i+1, n):
            C = items[j]
            if A.kind == 'pad' and C.kind == 'pad': continue
            if scope == 'new' and not (A.new or C.new): continue
            m = 0.6
            if bb[i][0] > bb[j][2]+m or bb[j][0] > bb[i][2]+m or bb[i][1] > bb[j][3]+m or bb[j][1] > bb[i][3]+m: continue
            if A.net != C.net or not A.net:
                if A.layers & C.layers:
                    need = R.clr(A.net, C.net); d = dist(A.shape, C.shape)
                    if d < need-EPS: V.append(('shorting_items' if d <= 0 else 'clearance', A, C, round(d, 4), need))
                for H, O in ((A, C), (C, A)):
                    if H.hole and (O.layers or O.kind != 'pad'):
                        if O.layers:
                            d = dist(H.hole, O.shape)
                            if d < R.hole_clr-EPS: V.append(('hole_clearance', H, O, round(d, 4), R.hole_clr))
            if A.hole and C.hole:
                d = dist(A.hole, C.hole)
                if d < R.h2h-EPS and not (A.kind == 'pad' and C.kind == 'pad'): V.append(('hole_to_hole', A, C, round(d, 4), R.h2h))
    return V
def dangling(B):
    out = []
    for i, A in enumerate(B.items):
        if A.kind != 'trk': continue
        for p in A.anchors:
            if not any(C is not A and C.net == A.net and (A.layers & C.layers) and contains(C.shape, *p) for C in B.items): out.append((A, p))
    return out