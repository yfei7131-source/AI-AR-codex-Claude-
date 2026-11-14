#!/usr/bin/env python3
"""usb_impedance.py — 第四轮新增: 边缘耦合微带(F.Cu 差分对 / In1 GND 参考)阻抗计算 (估算, 非板厂确认值).

方法: 2D 准 TEM 有限体积场求解(非均匀网格, 导体为 Dirichlet, 介质/阻焊分区)。
  Zodd = 1/(c * sqrt(C_odd * C_odd_air)),  Zdiff = 2*Zodd,  Zeven 同理, Zcommon = Zeven/2
  电容由静电能 W = 1/2 * sum(g*(dphi)^2) 得出 (even: c_e = W_e/V^2, odd: c_o = W_o/V^2, V=1, 每导体)
验证: 单微带 vs Hammerstad-Jensen 解析式; 均匀介质 Z 比 = sqrt(er); 耦合线 vs IPC-2141 近似(仅作量级对照)。
限制: 矩形导体(未建模蚀刻梯形)、无粗糙度/损耗、介质各向同性均匀、仅一层参考平面(In1 实心铜假设);
      **最终线宽/线距必须以板厂对其实际叠层的阻抗计算/测试 coupon 为准。**
"""
import math, json, sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

EPS0 = 8.8541878128e-12; C0 = 299792458.0; ETA0 = 376.730313668

def _grid(crit, lo, hi, fine, grow=1.25):
    """crit: 必须出现的网格线(升序); 在其间按 <=fine 细分, 远场按几何增长"""
    crit = sorted(set(round(c, 9) for c in crit))
    xs = [lo]
    # 左远场
    lines = [lo] + [c for c in crit if lo < c < hi] + [hi]
    lines = sorted(set(lines)); out = [lines[0]]
    fmin, fmax = crit[0], crit[-1]
    for a, b in zip(lines[:-1], lines[1:]):
        L = b - a; seg = [a]; x = a
        # 区间内: 靠近 [fmin-0.3, fmax+0.3] 用 fine, 否则增长
        while x < b - 1e-12:
            d_to_core = 0 if (fmin - 0.2 <= x <= fmax + 0.2) else min(abs(x - fmin), abs(x - fmax))
            step = fine if d_to_core == 0 else min(fine * (grow ** (d_to_core / (fine * 6))), 0.25)
            step = min(step, 0.25)
            nx = x + step
            if nx > b - 0.35 * step: nx = b
            seg.append(nx); x = nx
        out += seg[1:]
    return np.array(sorted(set(round(v, 9) for v in out)))

def solve_energy(xs, ys, eps_cell, cond_nodes, volts):
    """xs,ys: 节点坐标; eps_cell[(ny-1),(nx-1)]; cond_nodes: bool(ny,nx) 与同形 volts(ny,nx)(导体电位); 边界节点=0V"""
    nx, ny = len(xs), len(ys); dx = np.diff(xs); dy = np.diff(ys)
    N = nx * ny; idx = np.arange(N).reshape(ny, nx)
    # x 向边 (i,j)-(i+1,j): 上下两个单元
    up = np.zeros((ny, nx - 1)); dn = np.zeros((ny, nx - 1))
    up[:-1, :] = eps_cell * dy[:, None] * 0.5               # 上方单元 (j) 的半高
    dn[1:, :] = eps_cell * dy[:, None] * 0.5                # 下方单元 (j-1) 的半高
    gx = (up + dn) / dx[None, :]
    # y 向边 (i,j)-(i,j+1): 左右两个单元
    lf = np.zeros((ny - 1, nx)); rt = np.zeros((ny - 1, nx))
    lf[:, 1:] = eps_cell * dx[None, :] * 0.5
    rt[:, :-1] = eps_cell * dx[None, :] * 0.5
    gy = (lf + rt) / dy[:, None]
    ia = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()]); ib = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    g = np.concatenate([gx.ravel(), gy.ravel()])
    fixed = np.zeros((ny, nx), bool); fixed[0, :] = fixed[-1, :] = True; fixed[:, 0] = fixed[:, -1] = True
    phi = np.zeros((ny, nx)); fixed |= cond_nodes; phi[cond_nodes] = volts[cond_nodes]
    fx = fixed.ravel(); ph = phi.ravel(); free = np.where(~fx)[0]; pos = -np.ones(N, int); pos[free] = np.arange(len(free))
    deg = np.zeros(N); np.add.at(deg, ia, g); np.add.at(deg, ib, g)
    ra, rb = pos[ia], pos[ib]
    m = (ra >= 0) & (rb >= 0)
    rows = np.concatenate([ra[m], rb[m], np.arange(len(free))]); cols = np.concatenate([rb[m], ra[m], np.arange(len(free))])
    vals = np.concatenate([-g[m], -g[m], deg[free]])
    A = sp.csr_matrix((vals, (rows, cols)), shape=(len(free), len(free)))
    rhs = np.zeros(len(free))
    m1 = (ra >= 0) & (rb < 0); np.add.at(rhs, ra[m1], g[m1] * ph[ib[m1]])
    m2 = (rb >= 0) & (ra < 0); np.add.at(rhs, rb[m2], g[m2] * ph[ia[m2]])
    sol = spl.spsolve(A.tocsc(), rhs); ph[free] = sol
    W = 0.5 * float((g * (ph[ia] - ph[ib]) ** 2).sum()) * EPS0   # J/m (1V 等效)
    return W

def build(w, s, t, h, er_sub, tm_top, er_mask, n_traces=2, fine=0.004, xhalf=3.5, ymax=2.5, mask=True):
    """mm 单位。坐标: 参考平面 y=0; 基板 0..h; 铜 h..h+t; 阻焊(平顶)到 h+t+tm_top; 其上空气。
    n_traces=2: 迹线 [-s/2-w,-s/2] 与 [s/2,s/2+w]; =1: [-w/2,w/2]"""
    if n_traces == 2: tr = [(-s / 2 - w, -s / 2), (s / 2, s / 2 + w)]
    else: tr = [(-w / 2, w / 2)]
    ytop_mask = h + t + (tm_top if mask else 0.0)
    xs = _grid([a for ab in tr for a in ab] + [0.0], -xhalf, xhalf, fine)
    ys = _grid([0, h, h + t, ytop_mask], 0.0, ymax, fine)
    nx, ny = len(xs), len(ys)
    xc = 0.5 * (xs[:-1] + xs[1:]); yc = 0.5 * (ys[:-1] + ys[1:])
    X, Y = np.meshgrid(xc, yc)
    def eps_for(er_s, er_m, er_air=1.0):
        e = np.full(X.shape, er_air)
        e[Y < ytop_mask] = er_m if mask else er_air
        e[Y < h + t] = np.where(Y[Y < h + t] < h, er_s, er_m if mask else er_air)
        return e
    # 导体节点
    XX, YY = np.meshgrid(xs, ys); cond = []
    for (a, b) in tr:
        cond.append((XX >= a - 1e-9) & (XX <= b + 1e-9) & (YY >= h - 1e-9) & (YY <= h + t + 1e-9))
    return xs, ys, eps_for(er_sub, er_mask), eps_for(1.0, 1.0), cond

def impedance(w, s, t, h, er_sub, tm_top=0.02, er_mask=3.8, mask=True, fine=0.004):
    """返回 dict: Zdiff, Zodd, Zeven, Zcommon, Z0_single"""
    out = {}
    xs, ys, ed, ea, cond = build(w, s, t, h, er_sub, tm_top, er_mask, 2, fine, mask=mask)
    def W_mode(eps, v1, v2):
        v = np.zeros(cond[0].shape); v[cond[0]] = v1; v[cond[1]] = v2
        return solve_energy(xs, ys, eps, cond[0] | cond[1], v)
    ce_d = W_mode(ed, 1, 1); ce_a = W_mode(ea, 1, 1); co_d = W_mode(ed, 1, -1); co_a = W_mode(ea, 1, -1)
    Ze = 1 / (C0 * math.sqrt(ce_d * ce_a)); Zo = 1 / (C0 * math.sqrt(co_d * co_a))
    out.update(Zodd=Zo, Zeven=Ze, Zdiff=2 * Zo, Zcommon=Ze / 2)
    return out

def single(w, t, h, er_sub, tm_top=0.02, er_mask=3.8, mask=False, fine=0.004):
    xs, ys, ed, ea, cond = build(w, 0, t, h, er_sub, tm_top, er_mask, 1, fine, mask=mask)
    v = np.zeros(cond[0].shape); v[cond[0]] = 1.0
    cd = 2 * solve_energy(xs, ys, ed, cond[0], v); ca = 2 * solve_energy(xs, ys, ea, cond[0], v)
    return 1 / (C0 * math.sqrt(cd * ca))

# ---------------- 解析参考 (验证/对照) ----------------
def hammerstad_jensen(u, er):
    """u=w/h (零厚度). 返回 Z0"""
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    z01 = ETA0 / (2 * math.pi) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    return z01 / math.sqrt(eeff), eeff
def ipc2141_single(w, t, h, er):
    return 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (0.8 * w + t))
def ipc_diff(w, s, t, h, er):
    return 2 * ipc2141_single(w, t, h, er) * (1 - 0.48 * math.exp(-0.96 * s / h))

def validate():
    res = {}
    # 1) 单微带, 近零厚度, 无阻焊: 与 Hammerstad-Jensen 比较
    rows = []
    for (u, er) in ((1.0, 4.4), (2.0, 4.4), (0.5, 4.1), (1.9, 4.1)):
        h = 0.1; w = u * h; t = 0.002
        z = single(w, t, h, er, mask=False); zh, ee = hammerstad_jensen(u, er)
        rows.append(dict(w_over_h=u, er=er, solver=round(z, 3), hammerstad_jensen=round(zh, 3), err_pct=round(100 * (z / zh - 1), 2)))
    res['single_vs_HJ_t0'] = rows
    # 2) 均匀介质比例检验: 全部 eps=er 时 Z = Z_air/sqrt(er) —— 用 mask=True, h 层 er_sub=er_mask=er 且 tm 大使介质占满导体附近
    er = 4.0; xs, ys, ed, ea, cond = build(0.2, 0.15, 0.035, 0.1, er, 2.0, er, 2, 0.004, mask=True, ymax=2.5)
    ed[:] = er  # 整个域均匀 er
    v = np.zeros(cond[0].shape); v[cond[0]] = 1; v[cond[1]] = -1
    cod = solve_energy(xs, ys, ed, cond[0] | cond[1], v); coa = solve_energy(xs, ys, ea, cond[0] | cond[1], v)
    res['homogeneous_ratio_check'] = dict(expected_sqrt_er=round(math.sqrt(er), 6), solver_ratio=round(math.sqrt(cod / coa), 6))
    # 3) 大间距 -> Zdiff -> 2*Z0(单)
    z2 = impedance(0.2, 3.0, 0.035, 0.1, 4.1, mask=False); z1 = single(0.2, 0.035, 0.1, 4.1, mask=False)
    res['large_gap_limit'] = dict(Zdiff_s3mm=round(z2['Zdiff'], 2), two_times_single=round(2 * z1, 2), err_pct=round(100 * (z2['Zdiff'] / (2 * z1) - 1), 2))
    # 4) 网格收敛
    r = []
    for fine in (0.008, 0.004, 0.002):
        r.append(dict(fine_mm=fine, Zdiff=round(impedance(0.2, 0.15, 0.035, 0.1, 4.1, fine=fine)['Zdiff'], 3)))
    res['grid_convergence'] = r
    return res

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'validate':
        print(json.dumps(validate(), indent=1))
    else:
        print(json.dumps(impedance(0.2, 0.15, 0.035, 0.1, 4.1), indent=1))
