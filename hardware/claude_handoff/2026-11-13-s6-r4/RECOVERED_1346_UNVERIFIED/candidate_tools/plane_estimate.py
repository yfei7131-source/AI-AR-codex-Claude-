#!/usr/bin/env python3
"""plane_estimate.py — 第四轮新增：In1(GND)/In2(3V3) 局部“重铺近似” (NOT KiCad NATIVE REFILL).

KiCad 无法运行时，用 0.01~0.02 mm 栅格近似估计：新过孔会不会让相邻 GND/3V3 过孔“热焊盘辐条不足”
或产生孤岛。模型(均取自 evt0_core.kicad_pcb 的 zone 参数):
  * zone clearance 0.25 ; thermal_gap 0.25 ; thermal_bridge_width 0.35 ; min_thickness 0.25
  * connect_pads = thru_hole_only (通孔焊盘/过孔同网 => 热焊盘; 4 根辐条)
  * island_removal_mode 0 (无连接孤岛被删除)
  * 不同网通孔/过孔: 以 其铜边 + 0.25 挖空
未建模: 阻焊、丝印、铜皮倒角算法细节、辐条角度的 KiCad 实现(此处同时试 0°/45°)。
**必须先在 R4 原生已通过的区域(U1 EP 过孔簇)做对照**, 再解读新过孔结果。输出只能说明“风险提示”, 不是通过证明。
用法: plane_estimate.py <pcb> <pro> <outdir>
"""
import sys, os, json, math
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import offline_recheck as oc

ZCLR, TGAP, TBW, TMIN = 0.25, 0.25, 0.35, 0.25

def raster_poly(poly, x0, y0, res, shape):
    """多边形(凸)栅格化: 以包围盒内逐格点 inside 判定(向量化叉积)。"""
    H, W = shape; m = np.zeros(shape, bool)
    xs = (np.arange(W) + .5) * res + x0; ys = (np.arange(H) + .5) * res + y0
    bx0, by0, bx1, by1 = oc.bbox(poly)
    ix0 = max(0, int((bx0 - x0) / res) - 1); ix1 = min(W, int((bx1 - x0) / res) + 2)
    iy0 = max(0, int((by0 - y0) / res) - 1); iy1 = min(H, int((by1 - y0) / res) + 2)
    if ix0 >= ix1 or iy0 >= iy1: return m
    X, Y = np.meshgrid(xs[ix0:ix1], ys[iy0:iy1]); ins = np.ones(X.shape, bool)
    n = len(poly); sgn = 0
    # 凸多边形: 所有边叉积同号
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    s = 1 if area > 0 else -1
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
        ins &= s * ((bx - ax) * (Y - ay) - (by - ay) * (X - ax)) >= 0
    m[iy0:iy1, ix0:ix1] = ins; return m

def estimate(items, plane_net, layer, cx, cy, half, res, spoke_deg, targets=None):
    x0, y0 = cx - half, cy - half; N = int(2 * half / res); shape = (N, N)
    fill = np.ones(shape, bool)
    thr = []
    for it in items:
        if layer not in it.layers or not (it.kind == 'via' or it.tht): continue
        if it.bb[2] < x0 - 2 or it.bb[0] > x0 + 2 * half + 2 or it.bb[3] < y0 - 2 or it.bb[1] > y0 + 2 * half + 2: continue
        m = raster_poly(it.poly, x0, y0, res, shape)
        dist = ndi.distance_transform_edt(~m) * res
        if it.net == plane_net: thr.append((it, m, dist)); continue
        fill &= ~(dist <= ZCLR)            # 异网: 铜边 + 0.25 挖空 (含铜本体)
    keep_ring = np.zeros(shape, bool); spokes = {}
    for it, m, dist in thr:
        ring = (dist > 0) & (dist <= TGAP); fill &= ~ring; fill &= ~m  # 热焊盘间隙 + 焊盘本体另算
        cxp, cyp = it.p; R = max(it.w, 0.1) / 2 + TGAP + 0.6
        yy, xx = np.mgrid[0:N, 0:N]; X = (xx + .5) * res + x0 - cxp; Y = (yy + .5) * res + y0 - cyp
        sp = []
        for k in range(4):
            a = math.radians(spoke_deg + 90 * k); ux, uy = math.cos(a), math.sin(a)
            along = X * ux + Y * uy; across = np.abs(-X * uy + Y * ux)
            band = (along > 0) & (along <= R) & (across <= TBW / 2)
            sp.append(band & ring)          # 辐条只在间隙环内“搭桥”
        spokes[id(it)] = sp
        for b in sp: fill |= b
    # 最小线宽: 开运算 (半径 TMIN/2)
    r = int(round(TMIN / 2 / res)); yy, xx = np.ogrid[-r:r + 1, -r:r + 1]; se = (xx * xx + yy * yy) <= r * r
    # 辐条本身 0.35 宽 > 0.25, 不会被开运算删掉; 对 fill 开运算
    fo = ndi.binary_opening(fill, structure=se)
    lab, n = ndi.label(fo, structure=np.ones((3, 3)))
    sizes = ndi.sum(fo, lab, range(1, n + 1)) if n else []
    main = 1 + int(np.argmax(sizes)) if n else 0
    out = dict(n_components=int(n), main_area_mm2=round(float(max(sizes)) * res * res, 2) if n else 0.0, thermal=[])
    for it, m, dist in thr:
        if targets is not None and (round(it.p[0], 2), round(it.p[1], 2)) not in targets and not any(math.hypot(it.p[0] - t[0], it.p[1] - t[1]) < 0.01 for t in targets): continue
        # 辐条连通: 辐条条带(在环内) 的外端是否接入主分量
        ok = 0
        for b in spokes[id(it)]:
            outer = ndi.binary_dilation(b, iterations=2) & ~b   # 辐条外缘一圈
            if (lab[outer & fo] == main).any(): ok += 1
        out['thermal'].append(dict(item=repr(it), net=it.net, spokes_connected=ok, starved=(ok < 2)))
    return out

def run(pcb, pro, outdir):
    items, edge, zones = oc.load(pcb); os.makedirs(outdir, exist_ok=True)
    cases = {
      'CONTROL_U1_EP_cluster (R4 原生已通过的同类结构)': dict(cx=123.5, cy=75.26, half=4.5, targets=None, only_pad41=True),
      'NEW_PGOOD_via (133.8,118.1)': dict(cx=133.8, cy=118.1, half=4.0, targets=None),
      'NEW_J3_GND_via (104.35,99.45)': dict(cx=104.35, cy=99.45, half=3.5, targets=None),
      'NEW_J3_GND_via (104.35,105.95)': dict(cx=104.35, cy=105.95, half=3.5, targets=None),
      'NEW_J3_GND_via (102.5,98.65)': dict(cx=102.5, cy=98.65, half=3.5, targets=None),
      'NEW_J3_GND_via (102.5,110.75)': dict(cx=102.5, cy=110.75, half=3.5, targets=None),
    }
    res_all = {}
    for name, c in cases.items():
        res_all[name] = {}
        for plane_net, layer in (('/GND', 'In1.Cu'), ('/3V3', 'In2.Cu')):
            for deg in (0, 45):
                e = estimate(items, plane_net, layer, c['cx'], c['cy'], c['half'], 0.02, deg)
                near_pts = [t for t in e['thermal'] if True]
                # 仅保留窗口中心 1.6 mm 内的同网通孔项, 突出关注点
                keep = []
                for t in near_pts:
                    import re
                    m = re.search(r'\(([\d.]+),([\d.]+)\)', t['item'])
                    if m: x, y = float(m.group(1)), float(m.group(2))
                    else:
                        m = re.search(r'pad (\w+)\.(\w+)', t['item']); x = y = None
                    keep.append(t)
                e['thermal_focus'] = [t for t in keep]
                res_all[name][f'{layer}/{plane_net}/spoke{deg}'] = dict(n_components=e['n_components'], main_area_mm2=e['main_area_mm2'],
                    n_same_net_tht=len(e['thermal']), n_starved=sum(1 for t in e['thermal'] if t['starved']),
                    starved=[t['item'] for t in e['thermal'] if t['starved']][:12])
    json.dump(res_all, open(os.path.join(outdir, 'plane_estimate.json'), 'w'), indent=1, ensure_ascii=False)
    return res_all

if __name__ == '__main__':
    r = run(*sys.argv[1:4])
    for k, v in r.items():
        print('==', k)
        for kk, vv in v.items(): print('  ', kk, vv)
