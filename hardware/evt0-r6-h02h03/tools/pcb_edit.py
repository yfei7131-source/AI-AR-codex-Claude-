"""pcb_edit: R5 rework 的 KiCad PCB 文本级编辑器 (不依赖 pcbnew)。
只做可追踪的最小文本改动, 保持 CRLF/制表符格式:
  - insert_copper(recs)          追加 segment/via 块 (r5_route.emit_blocks 格式)
  - delete_uuids(uuids)          删除顶层 segment/via 块 (按 uuid)
  - set_pad_drill(ref, num, d)   修改某封装某编号全部 THT 焊盘的钻孔
  - set_fp_lib(ref, lib_id)      修改封装库标识 (lib_id)
  - knockout_vias(vias)          在 In1/In2 已铺铜 filled_polygon 中为新增他网过孔挖出隔离孔
                                 (KiCad 断裂多边形 "slit" 表示法; 仅当整圆位于填充内部才挖, 否则报错拒绝)
所有 KiCad 原生结果仍须用 kicad-cli pcb drc --refill-zones 复核。
"""
import math, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sx import parse, find, one
from zy_pcb import d_pt_seg, pt_in_poly

NL = '\r\n'


class Pcb:
    def __init__(s, path):
        s.path = Path(path); s.t = open(path, newline='').read()
        assert s.t.count('\r\n') > 1000, 'expect CRLF board'
        s.log = []

    def save(s, path=None):
        open(path or s.path, 'w', newline='').write(s.t)

    # ---------------- top-level block helpers
    def _blocks(s, kind):
        """yield (start, end) of top-level blocks '\t(kind' ... '\t)\r\n'"""
        pat = NL + '\t(' + kind + NL
        i = s.t.find(pat)
        while i >= 0:
            a = i + len(NL); b = s.t.find(NL + '\t)' + NL, a) + len(NL + '\t)' + NL)
            yield a, b
            i = s.t.find(pat, b - len(NL))

    def insert_copper(s, recs, emit):
        txt = emit(recs)
        end = s.t.rstrip()
        assert end.endswith(')')
        k = s.t.rstrip().rfind(')')
        s.t = s.t[:k] + txt + s.t[k:]
        s.log.append(('insert', len(recs)))

    def delete_uuids(s, uuids):
        uuids = set(uuids); hit = []
        for kind in ('segment', 'via'):
            spans = [(a, b) for a, b in s._blocks(kind) if re.search(r'\(uuid "([^"]+)"\)', s.t[a:b]).group(1) in uuids]
            for a, b in reversed(spans):
                hit.append(re.search(r'\(uuid "([^"]+)"\)', s.t[a:b]).group(1)); s.t = s.t[:a] + s.t[b:]
        missing = uuids - set(hit)
        assert not missing, f'uuids not found: {missing}'
        s.log.append(('delete', sorted(hit)))
        return hit

    def _fp_span(s, ref):
        for a, b in s._fp_spans():
            if re.search(r'\(property "Reference" "%s"' % re.escape(ref), s.t[a:b]): return a, b
        raise KeyError(ref)

    def _fp_spans(s):
        pat = NL + '\t(footprint '
        i = s.t.find(pat)
        while i >= 0:
            a = i + len(NL); b = s.t.find(NL + '\t)' + NL, a) + len(NL + '\t)' + NL)
            yield a, b
            i = s.t.find(pat, b - len(NL))

    def set_pad_drill(s, ref, num, new_drill, old_drill=None):
        a, b = s._fp_span(ref); fp = s.t[a:b]; n = 0
        def rep(m):
            nonlocal n
            blk = m.group(0)
            if 'thru_hole' not in blk.split(NL)[0]: return blk
            d = re.search(r'\(drill ([\d.]+)\)', blk)
            if old_drill is not None and abs(float(d.group(1)) - old_drill) > 1e-9: return blk
            n += 1
            return blk.replace(d.group(0), '(drill %s)' % new_drill)
        fp2 = re.sub(r'\(pad "%s" .*?\r\n\t\t\)' % re.escape(num), rep, fp, flags=re.S)
        s.t = s.t[:a] + fp2 + s.t[b:]
        s.log.append(('pad_drill', ref, num, new_drill, n))
        return n

    def set_fp_lib(s, ref, lib_id):
        a, b = s._fp_span(ref); fp = s.t[a:b]
        m = re.match(r'\s*\(footprint "([^"]+)"', fp)
        assert m, 'footprint header not found for ' + ref
        old = m.group(1)
        hdr = m.group(0).replace('"%s"' % old, '"%s"' % lib_id, 1)
        s.t = s.t[:a] + hdr + fp[len(m.group(0)):] + s.t[b:]
        s.log.append(('fp_lib', ref, old, lib_id))
        return old

    def set_title_rev(s, rev, comment=None):
        s.t = re.sub(r'(\(title_block.*?\(rev ")[^"]*(")', lambda m: m.group(1) + rev + m.group(2), s.t, count=1, flags=re.S)

    def clear_zone_fills(s):
        """删除全部 zone 的 filled_polygon (保留 zone 轮廓/规则), 由 KiCad 重铺。"""
        n = 0
        while True:
            i = s.t.find('\t\t(filled_polygon\r\n')
            if i < 0: break
            j = s.t.find('\r\n\t\t)\r\n', i) + len('\r\n\t\t)\r\n')
            assert s.t[i:j].count('(pts') == 1, 'unexpected filled_polygon structure'
            s.t = s.t[:i] + s.t[j:]; n += 1
        s.log.append(('clear_zone_fills', n)); return n

    # ---------------- zone knockouts
    def zone_fills(s):
        """[(net, layer, (start,end) of pts text, [(x,y)...])]"""
        out = []
        for za, zb in s._blocks('zone'):
            zt = s.t[za:zb]
            net = re.search(r'\(net "([^"]*)"\)', zt).group(1); layer = re.search(r'\(layer "([^"]+)"\)', zt).group(1)
            for m in re.finditer(r'\(filled_polygon\r\n\t\t\t\(layer "[^"]+"\)\r\n(?:\t\t\t\(island\)\r\n)?\t\t\t\(pts\r\n(.*?)\r\n\t\t\t\)', zt, re.S):
                body = m.group(1)
                pts = [(float(x), float(y)) for x, y in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', body)]
                out.append((net, layer, (za + m.start(1), za + m.end(1)), pts))
        return out

    @staticmethod
    def _fmt_pts(P):
        def f(v):
            t = ('%.6f' % v).rstrip('0').rstrip('.'); return t
        rows = []
        for k in range(0, len(P), 4):
            rows.append('\t\t\t\t' + ' '.join('(xy %s %s)' % (f(x), f(y)) for x, y in P[k:k + 4]))
        return NL.join(rows)

    def knockout_vias(s, vias, clearance=0.25, margin=0.02, nseg=24):
        """vias: [(x,y,diameter,net)]. 对每个铺铜(他网)若过孔落在填充内, 用 slit 法挖孔。"""
        report = []
        for (x, y, d, net) in vias:
            r = d / 2 + clearance + margin
            rc = r / math.cos(math.pi / nseg)            # 外接正多边形, 保证覆盖整圆
            fills = s.zone_fills()
            for (znet, layer, (a, b), P) in fills:
                if znet == net: continue
                if not pt_in_poly(x, y, P):
                    # 过孔中心不在填充中: 检查圆是否与填充相交 (相交则不能安全省略)
                    dmin = min(d_pt_seg(x, y, *P[i], *P[(i + 1) % len(P)]) for i in range(len(P)))
                    if dmin < r: raise RuntimeError(f'via {x},{y} partially overlaps {znet}/{layer} fill (d={dmin:.3f})')
                    report.append((x, y, znet, layer, 'outside-fill')); continue
                # 最近边界点
                best = None
                for i in range(len(P)):
                    (x1, y1), (x2, y2) = P[i], P[(i + 1) % len(P)]
                    dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
                    t = 0 if L == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L))
                    qx, qy = x1 + t * dx, y1 + t * dy; dd = math.hypot(qx - x, qy - y)
                    if best is None or dd < best[0]: best = (dd, i, t, qx, qy)
                dd, i, t, qx, qy = best
                if dd < rc + 0.01: raise RuntimeError(f'via {x},{y} too close to {znet}/{layer} fill boundary (d={dd:.3f} < {rc:.3f})')
                # 孔多边形 (与外轮廓反向), 起点在朝向最近边界点的方向
                ang0 = math.atan2(qy - y, qx - x)
                area = sum(P[k][0] * P[(k + 1) % len(P)][1] - P[(k + 1) % len(P)][0] * P[k][1] for k in range(len(P)))
                sgn = -1 if area > 0 else 1
                H = [(x + rc * math.cos(ang0 + sgn * 2 * math.pi * k / nseg), y + rc * math.sin(ang0 + sgn * 2 * math.pi * k / nseg)) for k in range(nseg)]
                Q = (round(qx, 6), round(qy, 6))
                newP = P[:i + 1] + ([Q] if Q not in (P[i], P[(i + 1) % len(P)]) else []) + H + [H[0], Q] + P[i + 1:]
                if Q == P[i]: newP = P[:i + 1] + H + [H[0], Q] + P[i + 1:]
                s.t = s.t[:a] + s._fmt_pts(newP) + s.t[b:]
                report.append((x, y, znet, layer, 'knocked r=%.3f' % rc))
        s.log.append(('knockout', report))
        return report
