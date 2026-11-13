#!/usr/bin/env python3
"""offline_recheck.py — 第四轮新增：独立于 zy_pcb 的离线复核 (NOT KiCad NATIVE).

目的：在没有 kicad-cli 时，对 J3 GND 短线 / PGOOD / VBUS / VSYS 新铜做第二套独立几何与电气核算，
并校准“悬空线”判定。不修改任何输入文件。结果仅供提前发现问题，**不能替代原生 ERC/DRC**。

与 tools/zy_pcb.py 的区别（刻意独立）:
  * 自带 S 表达式解析（本文件内），不 import sx.py / zy_pcb.py
  * 所有铜形统一转成“凸多边形外轮廓”(圆/胶囊按外接多边形取，偏保守)，再做多边形-多边形距离
  * 悬空同时给出两种判定：anchor(KiCad 锚点模型) 与 overlap(端帽铜皮重叠)
用法: offline_recheck.py <evt0_core.kicad_pcb> <evt0_core.kicad_pro> <out.json>
"""
import sys, os, re, json, math, hashlib, fnmatch, heapq
from collections import defaultdict
import numpy as np

# ---------------------------------------------------------------- parser
_TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')
def parse(text):
    st = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == '(': st.append([])
        elif t == ')': x = st.pop(); st[-1].append(x)
        elif t[0] == '"': st[-1].append(('S', t[1:-1]))
        else: st[-1].append(t)
    return st[0][0]
def hd(n): return n[0] if n and isinstance(n[0], str) else None
def kids(n, k): return [c for c in n[1:] if isinstance(c, list) and hd(c) == k]
def kid(n, k):
    r = kids(n, k); return r[0] if r else None
def sv(x): return x[1] if isinstance(x, tuple) else x
def f(x): return float(x)

# ---------------------------------------------------------------- geometry
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')
def rot(x, y, a):                 # KiCad: 角度逆时针为正, y 向下 => 板坐标 = (x c + y s, -x s + y c)
    r = math.radians(a); c, s = math.cos(r), math.sin(r)
    return x * c + y * s, -x * s + y * c
def circ_poly(cx, cy, r, n=64):
    R = r / math.cos(math.pi / n)  # 外接
    return np.array([(cx + R * math.cos(2 * math.pi * (i + .5) / n), cy + R * math.sin(2 * math.pi * (i + .5) / n)) for i in range(n)])
def capsule_poly(x1, y1, x2, y2, r, n=24):
    ang = math.atan2(y2 - y1, x2 - x1); R = r / math.cos(math.pi / (2 * n))
    pts = []
    for i in range(n + 1):  # 终点端半圆
        a = ang - math.pi / 2 + math.pi * i / n; pts.append((x2 + R * math.cos(a), y2 + R * math.sin(a)))
    for i in range(n + 1):  # 起点端半圆
        a = ang + math.pi / 2 + math.pi * i / n; pts.append((x1 + R * math.cos(a), y1 + R * math.sin(a)))
    return np.array(pts)
def rrect_poly(cx, cy, w, h, ang, rr, n=8):
    r = rr * min(w, h); hw, hh = w / 2, h / 2; pts = []
    if r <= 1e-9:
        loc = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    else:
        loc = []
        for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
            ccx, ccy = sx * (hw - r), sy * (hh - r)
            for i in range(n + 1):
                a = math.radians(a0 + 90.0 * i / n); loc.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    for (lx, ly) in loc:
        dx, dy = rot(lx, ly, ang); pts.append((cx + dx, cy + dy))
    return np.array(pts)
def oval_poly(cx, cy, w, h, ang):
    if w >= h: dx, dy = rot((w - h) / 2, 0, ang); r = h / 2
    else: dx, dy = rot(0, (h - w) / 2, ang); r = w / 2
    return capsule_poly(cx - dx, cy - dy, cx + dx, cy + dy, r)
def _edges(P): return P, np.roll(P, -1, axis=0)
def pt_seg_d(p, a, b):               # p:(m,2) a,b:(n,2) -> (m,n)
    ab = b - a; L = (ab ** 2).sum(1); L[L == 0] = 1e-18
    ap = p[:, None, :] - a[None, :, :]
    t = np.clip((ap * ab[None]).sum(2) / L[None], 0, 1)
    q = a[None] + t[..., None] * ab[None]
    return np.sqrt(((p[:, None, :] - q) ** 2).sum(2))
def inside(P, q):
    x, y = q; ins = False; n = len(P)
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): ins = not ins
    return ins
def seg_cross(A, B):                 # 任意边相交?
    a1, a2 = _edges(A); b1, b2 = _edges(B)
    def o(p, q, r): return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
    A1, A2 = a1[:, None], a2[:, None]; B1, B2 = b1[None], b2[None]
    d1 = o(A1, A2, B1); d2 = o(A1, A2, B2); d3 = o(B1, B2, A1); d4 = o(B1, B2, A2)
    return bool((((d1 > 0) != (d2 > 0)) & ((d3 > 0) != (d4 > 0))).any())
def poly_dist(A, B):
    """凸多边形间最小边到边距离; 重叠返回 0.0"""
    if seg_cross(A, B) or inside(A, B[0]) or inside(B, A[0]): return 0.0
    a1, a2 = _edges(A); b1, b2 = _edges(B)
    return float(min(pt_seg_d(A, b1, b2).min(), pt_seg_d(B, a1, a2).min()))
def bbox(P): return P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()

# ---------------------------------------------------------------- board model
class Item:
    __slots__ = ('kind', 'net', 'layers', 'poly', 'bb', 'ref', 'num', 'anchors', 'w', 'drill', 'uuid', 'p', 'q', 'tht', 'r', 'desc')
    def __repr__(s):
        if s.kind == 'pad': return f"pad {s.ref}.{s.num}"
        if s.kind == 'via': return f"via@({s.p[0]:.3f},{s.p[1]:.3f})"
        return f"trk({s.p[0]:.3f},{s.p[1]:.3f})-({s.q[0]:.3f},{s.q[1]:.3f}) w{s.w}"
def load(pcb_path):
    t = parse(open(pcb_path, encoding='utf-8', newline='').read()); items = []
    for fp in kids(t, 'footprint'):
        ref = [sv(p[2]) for p in kids(fp, 'property') if sv(p[1]) == 'Reference'][0]
        at = kid(fp, 'at'); fx, fy = f(at[1]), f(at[2]); fa = f(at[3]) if len(at) > 3 else 0.0
        for p in kids(fp, 'pad'):
            it = Item(); it.kind = 'pad'; it.ref = ref; it.num = sv(p[1]); ptype = p[2]; shp = p[3]
            pa = kid(p, 'at'); ang = f(pa[3]) if len(pa) > 3 else 0.0
            dx, dy = rot(f(pa[1]), f(pa[2]), fa); x, y = fx + dx, fy + dy
            sz = kid(p, 'size'); w, h = f(sz[1]), f(sz[2])
            if shp == 'circle': poly = circ_poly(x, y, w / 2); it.desc = ('circ', x, y, w / 2)
            elif shp == 'oval': poly = oval_poly(x, y, w, h, ang); it.desc = ('oval', x, y, w, h, ang)
            else:
                rr = kid(p, 'roundrect_rratio'); rv = f(rr[1]) if (shp == 'roundrect' and rr) else 0.0
                poly = rrect_poly(x, y, w, h, ang, rv); it.desc = ('rrect', x, y, w, h, ang, rv)
            L = set()
            for l in kid(p, 'layers')[1:]:
                l = sv(l)
                if l == '*.Cu': L |= set(CU)
                elif l.endswith('.Cu'): L.add(l)
            if ptype == 'np_thru_hole': L = set()
            n = kid(p, 'net'); dr = kid(p, 'drill'); dd = None
            if dr:
                nums = [f(v) for v in dr[1:] if isinstance(v, str) and re.match(r'^[\d.]+$', v)]
                dd = min(nums) if nums else None
            it.net = sv(n[1]) if n else ''; it.layers = L; it.poly = poly; it.bb = bbox(poly); it.anchors = [(x, y)]
            it.w = min(w, h); it.drill = dd; it.uuid = sv((kid(p, 'uuid') or [0, ''])[1]); it.p = (x, y); it.q = None
            it.tht = ptype == 'thru_hole'; it.r = None
            items.append(it)
    for g in kids(t, 'segment'):
        it = Item(); it.kind = 'trk'; s = kid(g, 'start'); e = kid(g, 'end'); w = f(kid(g, 'width')[1])
        it.p = (f(s[1]), f(s[2])); it.q = (f(e[1]), f(e[2])); it.w = w; it.layers = {sv(kid(g, 'layer')[1])}
        it.poly = capsule_poly(*it.p, *it.q, w / 2); it.bb = bbox(it.poly); it.net = sv(kid(g, 'net')[1])
        it.uuid = sv(kid(g, 'uuid')[1]); it.anchors = [it.p, it.q]; it.ref = it.num = None; it.drill = None; it.tht = False; it.r = w / 2; it.desc = ('cap', it.p[0], it.p[1], it.q[0], it.q[1], w / 2)
        items.append(it)
    for v in kids(t, 'via'):
        it = Item(); it.kind = 'via'; a = kid(v, 'at'); x, y = f(a[1]), f(a[2]); d = f(kid(v, 'size')[1])
        it.p = (x, y); it.q = None; it.w = d; it.drill = f(kid(v, 'drill')[1]); it.layers = set(CU)
        it.poly = circ_poly(x, y, d / 2); it.bb = bbox(it.poly); it.net = sv(kid(v, 'net')[1]); it.uuid = sv(kid(v, 'uuid')[1])
        it.anchors = [(x, y)]; it.ref = it.num = None; it.tht = True; it.r = d / 2; it.desc = ('circ', x, y, d / 2)
        items.append(it)
    edge = []
    for g in kids(t, 'gr_line'):
        if sv(kid(g, 'layer')[1]) == 'Edge.Cuts':
            s = kid(g, 'start'); e = kid(g, 'end'); edge.append(((f(s[1]), f(s[2])), (f(e[1]), f(e[2])), f(kid(g, 'width')[1]) if kid(g, 'width') else 0.05))
    zones = []
    for z in kids(t, 'zone'):
        if kid(z, 'net') and kid(z, 'layer'):
            zones.append(dict(net=sv(kid(z, 'net')[1]), layer=sv(kid(z, 'layer')[1]),
                              filled=len(kids(z, 'filled_polygon')), clearance=f(kid(kid(z, 'connect_pads'), 'clearance')[1]) if kid(z, 'connect_pads') and kid(kid(z, 'connect_pads'), 'clearance') else None,
                              connect=[x for x in kid(z, 'connect_pads')[1:] if isinstance(x, str)] if kid(z, 'connect_pads') else None))
    return items, edge, zones

# ---------------------------------------------------------------- rules (读 .kicad_pro; DRU 规则在此硬编码并注明来源)
class Rules:
    def __init__(s, pro_path):
        p = json.load(open(pro_path, encoding='utf-8')); ds = p['board']['design_settings']['rules']; ns = p['net_settings']
        s.min_track = ds['min_track_width']; s.min_through = ds['min_through_hole_diameter']; s.min_ann = ds['min_via_annular_width']
        s.min_via_dia = ds['min_via_diameter']; s.h2h = ds['min_hole_to_hole']; s.edge_board = ds['min_copper_edge_clearance']
        s.cls = {c['name']: c for c in ns['classes']}; s.pats = [(x['pattern'], x['netclass']) for x in ns['netclass_patterns']]
        s.edge_dru = 0.3; s.power_min_w = 0.3; s.camclk_keepaway = 0.3   # evt0_core.kicad_dru
    def netclass(s, net):
        for pat, c in s.pats:
            if fnmatch.fnmatch(net, pat): return c
        return 'Default'
    def clearance(s, na, nb):
        ca, cb = s.netclass(na), s.netclass(nb); c = max(s.cls[ca]['clearance'], s.cls[cb]['clearance'])
        for x, y in ((ca, cb), (cb, ca)):   # DRU: CamClk vs 非 CamClk/非 Power >= 0.3
            if x == 'CamClk' and y not in ('CamClk', 'Power'): c = max(c, s.camclk_keepaway)
        return c

def shared(a, b): return bool(a.layers & b.layers)
def near(a, b, m):
    return not (a.bb[2] + m < b.bb[0] or b.bb[2] + m < a.bb[0] or a.bb[3] + m < b.bb[1] or b.bb[3] + m < a.bb[1])

def hires(it):
    """高精度外轮廓(圆 720 边/半圆 360 段, 近似误差 <1e-5 mm), 仅用于 margin<0.02 的候选复算。"""
    d = it.desc
    if d[0] == 'circ': return circ_poly(d[1], d[2], d[3], 720)
    if d[0] == 'cap': return capsule_poly(d[1], d[2], d[3], d[4], d[5], 360)
    if d[0] == 'oval':
        _, x, y, w, h, ang = d
        if w >= h: dx, dy = rot((w - h) / 2, 0, ang); r = h / 2
        else: dx, dy = rot(0, (h - w) / 2, ang); r = w / 2
        return capsule_poly(x - dx, y - dy, x + dx, y + dy, r, 360)
    _, x, y, w, h, ang, rv = d
    return rrect_poly(x, y, w, h, ang, rv, 180)
DRC_EPS = 0.0025     # KiCad: GetDRCEpsilon() = max_error/2 ; 本工程 max_error=0.005 => 2.5 µm
def classify(margin):
    if margin < -DRC_EPS: return 'VIOLATION(offline)'
    if margin < 0.005: return 'ZERO-MARGIN'
    if margin < 0.02: return 'MARGINAL'
    return 'PASS(offline)'
def exact_dist(a, b):
    return poly_dist(hires(a), hires(b))

def clearance_audit(items, rules, focus):
    out = []
    for fi in focus:
        best = []
        for o in items:
            if o is fi or not o.layers or o.net == fi.net or not shared(fi, o) or not near(fi, o, 1.0): continue
            d = poly_dist(fi.poly, o.poly); req = rules.clearance(fi.net, o.net)
            if d - req < 0.02: d = exact_dist(fi, o)          # 近阈值候选用高精度复算
            best.append((d - req, d, req, o))
        best.sort(key=lambda t: t[0])
        if best:
            m, d, req, o = best[0]
            out.append(dict(item=repr(fi), uuid=fi.uuid, net=fi.net, layers=sorted(fi.layers) if fi.kind != 'via' else 'all', min_clear=round(d, 4), required=req,
                            margin=round(m, 4), status=classify(m), nearest=repr(o), nearest_net=o.net,
                            next=[(repr(t[3]), t[3].net, round(t[1], 4), round(t[0], 4)) for t in best[1:3]]))
        else:
            out.append(dict(item=repr(fi), uuid=fi.uuid, net=fi.net, note='no other-net copper within 1mm on shared layers'))
    return out

def edge_audit(items, edge, rules, focus):
    out = []
    for fi in focus:
        best = 1e9
        for (a, b, w) in edge:
            seg = capsule_poly(*a, *b, w / 2); best = min(best, poly_dist(fi.poly, seg))
        out.append(dict(item=repr(fi), edge_dist=round(best, 4), board_rule=rules.edge_board, dru=rules.edge_dru,
                        margin_vs_board_0p5=round(best - rules.edge_board, 4), margin_vs_dru_0p3=round(best - rules.edge_dru, 4)))
    return out

def hole_to_hole(items, rules, focus):
    holes = [(it, it.p, it.drill / 2) for it in items if it.drill and (it.kind == 'via' or it.tht)]
    out = []
    for fi in focus:
        if fi.kind != 'via': continue
        best = min(((math.hypot(fi.p[0] - h[1][0], fi.p[1] - h[1][1]) - fi.drill / 2 - h[2]), h[0]) for h in holes if h[0] is not fi)
        out.append(dict(via=repr(fi), nearest_hole=repr(best[1]), hole_edge_gap=round(best[0], 4), rule=rules.h2h, margin=round(best[0] - rules.h2h, 4)))
    return out

def dimension_audit(rules, focus):
    out = []
    for fi in focus:
        if fi.kind == 'trk':
            req = rules.min_track
            if rules.netclass(fi.net) == 'Power': req = max(req, rules.power_min_w)
            out.append(dict(item=repr(fi), kind='trk', width=fi.w, required_min=req, ok=fi.w + 1e-9 >= req, margin=round(fi.w - req, 4)))
        elif fi.kind == 'via':
            ann = (fi.w - fi.drill) / 2
            out.append(dict(item=repr(fi), kind='via', size=fi.w, drill=fi.drill, annular=round(ann, 4), annular_min=rules.min_ann,
                            drill_min=rules.min_through, size_min=rules.min_via_dia,
                            ok=ann + 1e-9 >= rules.min_ann and fi.drill + 1e-9 >= rules.min_through and fi.w + 1e-9 >= rules.min_via_dia,
                            margins=dict(annular=round(ann - rules.min_ann, 4), drill=round(fi.drill - rules.min_through, 4), size=round(fi.w - rules.min_via_dia, 4))))
    return out

# ---------------------------------------------------------------- connectivity / dangling
def pt_in(it, pt, layer):
    return layer in it.layers and inside(it.poly, pt)
def track_end_status(items):
    """每条走线每个端点: anchor 模型(端点落入同网他件铜形) 与 overlap 模型(端帽圆盘与同网他件铜形有重叠)。"""
    bynet = defaultdict(list)
    for it in items:
        if it.net and it.layers: bynet[it.net].append(it)
    res = []
    for it in items:
        if it.kind != 'trk': continue
        layer = next(iter(it.layers))
        for k, pt in enumerate((it.p, it.q)):
            a_ok = o_ok = False; who = []
            disk = circ_poly(pt[0], pt[1], it.w / 2, 24)
            for o in bynet[it.net]:
                if o is it or layer not in o.layers: continue
                if not (o.bb[0] - 0.5 <= pt[0] <= o.bb[2] + 0.5 and o.bb[1] - 0.5 <= pt[1] <= o.bb[3] + 0.5): continue
                if inside(o.poly, pt):
                    a_ok = True; who.append(repr(o))
                if poly_dist(disk, o.poly) == 0.0: o_ok = True; who.append('~' + repr(o))
            res.append(dict(uuid=it.uuid, end=k, pt=pt, net=it.net, layer=layer, anchor_connected=a_ok, overlap_connected=a_ok or o_ok, who=sorted(set(who))[:4]))
    return res

def components(items, zones):
    """锚点模型连通性; 平面网络: 同网过孔/通孔焊盘并入平面分量 (假设重铺成功, 不考虑热焊盘/孤岛)。"""
    plane_nets = {z['net'] for z in zones}
    idx = [i for i, it in enumerate(items) if it.net and it.layers]; par = {i: i for i in idx}
    def fd(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    def un(a, b): par[fd(a)] = fd(b)
    bynet = defaultdict(list)
    for i in idx: bynet[items[i].net].append(i)
    for net, ids in bynet.items():
        for x in range(len(ids)):
            A = items[ids[x]]
            for y in range(x + 1, len(ids)):
                B = items[ids[y]]
                if not (A.layers & B.layers) or not near(A, B, 0.2): continue
                for L in A.layers & B.layers:
                    if any(pt_in(B, a, L) for a in A.anchors) or any(pt_in(A, b, L) for b in B.anchors):
                        un(ids[x], ids[y]); break
        if net in plane_nets:
            pl = [i for i in ids if items[i].kind == 'via' or items[i].tht]
            for i in pl[1:]: un(pl[0], i)
    gaps = {}
    for net, ids in bynet.items():
        c = len({fd(i) for i in ids}); 
        if c > 1: gaps[net] = c - 1
    return gaps

# ---------------------------------------------------------------- electrical (载流/压降, 假设值在报告中写明)
RHO = 1.72e-8         # Ω·m @20°C 纯铜
def ipc2221_ext(w_mm, t_um, dT):
    A = (w_mm / 0.0254) * (t_um / 25.4)            # mil^2
    return 0.048 * dT ** 0.44 * A ** 0.725
def path_resistance(items, net, src_pads, dst_pad, t_um=35.0, hot=1.0):
    """沿同网铜 Dijkstra: 边权=走线电阻; 焊盘/过孔视为零阻点(过孔筒电阻约 mΩ 级, 忽略并在报告注明)。"""
    nodes = [it for it in items if it.net == net and it.layers]
    key = lambda it: id(it)
    adj = defaultdict(list)
    for x in range(len(nodes)):
        for y in range(x + 1, len(nodes)):
            A, B = nodes[x], nodes[y]
            if not (A.layers & B.layers) or not near(A, B, 0.2): continue
            hit = any(pt_in(B, a, L) or False for a in A.anchors for L in A.layers & B.layers) or any(pt_in(A, b, L) for b in B.anchors for L in A.layers & B.layers)
            if hit:
                adj[key(A)].append((B, 0.0)); adj[key(B)].append((A, 0.0))
    def rseg(it):
        if it.kind != 'trk': return 0.0
        L = math.hypot(it.q[0] - it.p[0], it.q[1] - it.p[1]) * 1e-3
        return RHO * hot * L / ((it.w * 1e-3) * (t_um * 1e-6))
    # 将走线本身的电阻放在“穿过该走线”的边上: 展开为 节点分裂 (入/出)
    dist = {}; pq = []; start = [it for it in nodes if it.kind == 'pad' and (it.ref, it.num) in src_pads]
    for s in start: dist[key(s)] = 0.0; heapq.heappush(pq, (0.0, id(s), s))
    best = None
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > dist.get(key(u), 1e9): continue
        if u.kind == 'pad' and (u.ref, u.num) == dst_pad: best = d; break
        for v, _w in adj[key(u)]:
            nd = d + 0.5 * (rseg(u) + rseg(v))
            if nd < dist.get(key(v), 1e9): dist[key(v)] = nd; heapq.heappush(pq, (nd, id(v), v))
    return best

def board_scan(items, rules, new_uuids, thresh=0.02):
    """全板两两扫描(异网同层): 列出 margin<thresh 的对。new_uuids 标记本工程新增铜(其余=R4/既有)。"""
    res = []; n = len(items)
    cand = [it for it in items if it.net and it.layers]
    for i in range(len(cand)):
        A = cand[i]
        for j in range(i + 1, len(cand)):
            B = cand[j]
            if A.net == B.net or not (A.layers & B.layers) or not near(A, B, 0.5): continue
            if A.kind == 'pad' and B.kind == 'pad' and A.ref == B.ref and A.num == B.num: continue
            d = poly_dist(A.poly, B.poly); req = rules.clearance(A.net, B.net)
            if d - req < thresh:
                d = exact_dist(A, B)
                if d - req < thresh:
                    res.append(dict(a=repr(A), b=repr(B), a_net=A.net, b_net=B.net, dist=round(d, 5), req=req, margin=round(d - req, 5),
                                    involves_new=(A.uuid in new_uuids or B.uuid in new_uuids)))
    res.sort(key=lambda r: r['margin']); return res

# ---------------------------------------------------------------- main
def main(pcb, pro, outp):
    sha = hashlib.sha256(open(pcb, 'rb').read()).hexdigest()
    items, edge, zones = load(pcb); R = Rules(pro)
    by_uuid = {it.uuid: it for it in items}
    root = os.path.dirname(os.path.dirname(os.path.abspath(pcb)))
    s4 = json.load(open(os.path.join(root, 'evidence/step4_gnd_j3/change.json')))['added_copper']
    s5 = json.load(open(os.path.join(root, 'evidence/step5_vbus_vsys/added_copper.json')))['added_copper']
    grp = dict(
        J3_GND=[by_uuid[c['uuid']] for c in s4 if c['uuid'] in by_uuid],
        VBUS_new=[by_uuid[c['uuid']] for c in s5 if c['net'] == '/VBUS' and c['uuid'] in by_uuid],
        VSYS_new=[by_uuid[c['uuid']] for c in s5 if c['net'] == '/VSYS' and c['uuid'] in by_uuid],
        PGOOD_all=[it for it in items if it.net == '/CHG_PGOOD_N' and it.kind in ('trk', 'via')])
    rep = dict(input_sha256=sha, note='OFFLINE independent recheck - NOT KiCad native. 未重铺内层填充; 不含丝印/阻焊/热焊盘分析。',
               rules=dict(min_track=R.min_track, min_through_hole=R.min_through, min_annular=R.min_ann, min_via_dia=R.min_via_dia,
                          hole_to_hole=R.h2h, board_edge=R.edge_board, dru_edge=R.edge_dru, classes={k: v['clearance'] for k, v in R.cls.items()}),
               zones=zones, groups={})
    for g, fo in grp.items():
        rep['groups'][g] = dict(n=len(fo), clearance=clearance_audit(items, R, fo), edge=edge_audit(items, edge, R, fo),
                                dims=dimension_audit(R, fo), hole2hole=hole_to_hole(items, R, fo))
    new_uuids = {c['uuid'] for c in s4 + s5}
    scan = board_scan(items, R, new_uuids)
    rep['board_scan'] = dict(threshold=0.02, n_pairs=len(scan),
                             existing_pairs_margin_lt_0p005=[r for r in scan if not r['involves_new'] and r['margin'] < 0.005],
                             new_pairs=[r for r in scan if r['involves_new']],
                             worst_existing=[r for r in scan if not r['involves_new']][:10])
    ends = track_end_status(items)
    rep['dangling'] = dict(total_track_ends=len(ends),
                           anchor_model_dangling=[e for e in ends if not e['anchor_connected']],
                           overlap_model_dangling=[e for e in ends if not e['overlap_connected']])
    gaps = components(items, zones); rep['connectivity'] = dict(gaps_total=sum(gaps.values()), by_net=dict(sorted(gaps.items(), key=lambda kv: -kv[1])))
    # 电气
    vb = grp['VBUS_new']; L = sum(math.hypot(i.q[0] - i.p[0], i.q[1] - i.p[1]) for i in vb if i.kind == 'trk')
    ev = dict(assumptions=dict(copper_um=35.0, rho_ohm_m=RHO, note='外层成品铜厚 35µm 为假设(叠层未定); 70°C 取 ×1.27'),
              VBUS_new=dict(total_length_mm=round(L, 3), width_mm=0.3,
                            I_allow_A={f'dT{d}K': round(ipc2221_ext(0.3, 35, d), 2) for d in (10, 20, 30)},
                            R_ohm_20C=round(RHO * L * 1e-3 / (0.3e-3 * 35e-6), 4)))
    ev['VBUS_new']['drop_mV'] = {f'{i}A': round(ev['VBUS_new']['R_ohm_20C'] * i * 1000, 1) for i in (0.1, 0.5, 1.0, 1.5)}
    vs = grp['VSYS_new']; L2 = sum(math.hypot(i.q[0] - i.p[0], i.q[1] - i.p[1]) for i in vs if i.kind == 'trk')
    ev['VSYS_new'] = dict(total_length_mm=round(L2, 3), width_mm=0.3, connects='J4.2 (DNP) 仅作为稳态无电流分支',
                          R_ohm_20C=round(RHO * L2 * 1e-3 / (0.3e-3 * 35e-6), 4))
    srcs = {('U3', '10'), ('U3', '11')}
    ev['VSYS_main_paths_R_ohm_20C'] = {f'U3.OUT->{r}.{n}': (None if (x := path_resistance(items, '/VSYS', srcs, (r, n))) is None else round(x, 4))
                                       for (r, n) in (('U4', '1'), ('U5', '1'), ('C12', '1'), ('TP2', '1'), ('C3', '1'), ('C5', '1'))}
    # 包含 VSYS 新支路后到 J4.2 的阻抗
    ev['VSYS_U3_to_J4.2_R_ohm_20C'] = path_resistance(items, '/VSYS', srcs, ('J4', '2'))
    rep['electrical'] = ev
    json.dump(rep, open(outp, 'w'), indent=1, ensure_ascii=False, default=str)
    return rep

if __name__ == '__main__':
    main(*sys.argv[1:4])
