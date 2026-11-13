"""Incremental R3 lab layout. Never regenerate or remove existing copper.

Run with KiCad 10 Python. --prepare fixes two placement conflicts; --route
adds only reviewed DC/low-speed nets from a native DRC JSON. USB, camera
data/clock, display, and unqualified connector endpoints stay blocked.
Native DRC remains mandatory; this conservative grid search is not a signoff.
"""
import argparse
from collections import defaultdict
import heapq
import json
import math
from pathlib import Path

import numpy as np
import pcbnew as k

MM = k.FromMM
STEP = .25
NX, NY = 197, 254
ORIGIN = (100.5, 66.5)  # excludes antenna region on every routing layer
LAYERS = (k.F_Cu, k.B_Cu)
POWER = {'GND', '3V3', 'VBUS', 'VSYS', 'VBAT', 'VBAT_CONN',
         'CAM_2V8', 'CAM_1V2', 'CAM_3V3'}
SIGNALS = {'EN', 'KEY_BOOT', 'STRAP45', 'STRAP46', 'CC1', 'CC2',
           'BAT_NTC', 'VBAT_ADC', 'CAM_PWR_EN', 'CAM_3V3_G', 'CAM_LED_A',
           'U0TXD', 'U0RXD', 'MIC_SCK', 'MIC_WS', 'MIC_SD'}


def vec(x, y):
    return k.VECTOR2I(MM(x), MM(y))


def point(cell):
    return vec(ORIGIN[0]+cell[0]*STEP, ORIGIN[1]+cell[1]*STEP)


def cell(p):
    return (round((k.ToMM(p.x)-ORIGIN[0])/STEP),
            round((k.ToMM(p.y)-ORIGIN[1])/STEP))


def add_track(board, net, a, b, layer, width):
    if a == b:
        return
    t = k.PCB_TRACK(board)
    t.SetNetCode(net)
    t.SetLayer(layer)
    t.SetWidth(MM(width))
    t.SetStart(a)
    t.SetEnd(b)
    board.Add(t)


def prepare(board):
    parts = {f.GetReference(): f for f in board.GetFootprints()}
    # Existing copper is retained, including stubs to the previous R3 pad.
    # A later route reconnects the shifted GND pad. J3 has no existing copper.
    parts['R3'].SetPosition(vec(130, 116.5))
    parts['J3'].SetPosition(vec(103.9, 104.7))
    # Dense small-part reference labels belong on the assembly drawing.
    # Keep values, pin-1 markers, courtyard and all copper unchanged.
    for f in board.GetFootprints():
        f.Reference().SetLayer(k.B_Fab if f.IsFlipped() else k.F_Fab)
        for g in f.GraphicalItems():
            if g.GetLayer() not in (k.F_SilkS, k.B_SilkS):
                continue
            box = g.GetBoundingBox()
            if (k.ToMM(box.GetLeft()) < 100.25 or k.ToMM(box.GetRight()) > 149.75
                    or k.ToMM(box.GetTop()) < 60.25 or k.ToMM(box.GetBottom()) > 129.75):
                g.SetLayer(k.B_Fab if f.IsFlipped() else k.F_Fab)
    labels = [('R3 LAB ONLY', 125, 89), ('CAM / AR BLOCKED', 125, 91)]
    existing = {d.GetText() for d in board.GetDrawings() if isinstance(d, k.PCB_TEXT)}
    for value, x, y in labels:
        if value in existing:
            continue
        t = k.PCB_TEXT(board)
        t.SetText(value)
        t.SetPosition(vec(x, y))
        t.SetTextSize(vec(.8, .8))
        t.SetTextThickness(MM(.12))
        t.SetLayer(k.B_SilkS)
        t.SetMirrored(True)
        board.Add(t)


class Router:
    def __init__(self, board):
        self.board = board
        self.shapes = [[], []]
        self.spatial = [defaultdict(list), defaultdict(list)]
        for f in board.GetFootprints():
            for p in f.Pads():
                for index, layer in enumerate(LAYERS):
                    if p.IsOnLayer(layer):
                        self.add_shape(index, p.GetNetCode(), p.GetEffectiveShape(layer))
        for t in board.GetTracks():
            self.remember(t)
        self.holes = [(t.GetPosition(), t.GetDrillValue()) for t in board.GetTracks()
                      if isinstance(t, k.PCB_VIA)]
        self.holes += [(p.GetPosition(), p.GetDrillSize().x)
                       for f in board.GetFootprints() for p in f.Pads() if p.GetDrillSize().x]

    def remember(self, t):
        for index, layer in enumerate(LAYERS):
            if t.IsOnLayer(layer):
                self.add_shape(index, t.GetNetCode(), t.GetEffectiveShape(layer))

    @staticmethod
    def bins(shape, gap=0):
        box = shape.BBox()
        unit = MM(2)
        return [(x, y) for x in range((box.GetLeft()-gap)//unit, (box.GetRight()+gap)//unit+1)
                for y in range((box.GetTop()-gap)//unit, (box.GetBottom()+gap)//unit+1)]

    def add_shape(self, layer, net, shape):
        item = (net, shape)
        self.shapes[layer].append(item)
        for bucket in self.bins(shape):
            self.spatial[layer][bucket].append(item)

    def clear(self, net, shape, layer, gap=.21):
        return not any(k.SHAPE.Collide(shape, s, MM(gap))
                       for bucket in self.bins(shape, MM(gap))
                       for n, s in self.spatial[layer].get(bucket, ()) if n != net)

    def masks(self, net, width):
        masks = [np.zeros((NX, NY), dtype=np.bool_) for _ in LAYERS]
        radius = width/2+.23
        for layer in range(2):
            for other, shape in self.shapes[layer]:
                if other == net:
                    continue
                box = shape.BBox()
                left = max(0, math.floor((k.ToMM(box.GetLeft())-radius-ORIGIN[0])/STEP))
                right = min(NX-1, math.ceil((k.ToMM(box.GetRight())+radius-ORIGIN[0])/STEP))
                top = max(0, math.floor((k.ToMM(box.GetTop())-radius-ORIGIN[1])/STEP))
                bottom = min(NY-1, math.ceil((k.ToMM(box.GetBottom())+radius-ORIGIN[1])/STEP))
                for x in range(left, right+1):
                    for y in range(top, bottom+1):
                        if not masks[layer][x, y]:
                            masks[layer][x, y] = k.SHAPE.Collide(
                                k.SHAPE_CIRCLE(point((x, y)), MM(radius)), shape, 0)
        return masks

    def route(self, net, start, end, start_layers, end_layers, width):
        masks = self.masks(net, width)
        sc, ec = cell(start), cell(end)
        # Fine-pitch pad centres need an exact, checked escape to the grid.
        def candidates(anchor, c, layers):
            result = []
            for layer in layers:
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        x, y = c[0]+dx, c[1]+dy
                        if not (0 <= x < NX and 0 <= y < NY) or masks[layer][x, y]:
                            continue
                        if self.clear(net, k.SHAPE_SEGMENT(anchor, point((x, y)), MM(width)), layer):
                            result.append((x, y, layer))
            return result
        starts = candidates(start, sc, start_layers)
        ends = set(candidates(end, ec, end_layers))
        if not starts or not ends:
            return False
        def h(s):
            return math.hypot(s[0]-ec[0], s[1]-ec[1])
        todo, cost, prev = [], {}, {}
        for s in starts:
            cost[s] = math.hypot(s[0]-sc[0], s[1]-sc[1])
            heapq.heappush(todo, (cost[s]+h(s), cost[s], s))
        moves = [(x, y, math.hypot(x, y)) for x, y in
                 ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))]
        goal = None
        visited = 0
        while todo:
            _, g, s = heapq.heappop(todo)
            if g != cost.get(s):
                continue
            visited += 1
            if visited > 60000:
                return False  # leave an explicit airwire rather than run an unbounded search
            if s in ends:
                goal = s
                break
            x, y, layer = s
            nexts = []
            for dx, dy, length in moves:
                xx, yy = x+dx, y+dy
                if not (0 <= xx < NX and 0 <= yy < NY) or masks[layer][xx, yy]:
                    continue
                if dx and dy and (masks[layer][x+dx, y] or masks[layer][x, y+dy]):
                    continue
                nexts.append(((xx, yy, layer), length))
            other = 1-layer
            if not masks[other][x, y]:
                disk = k.SHAPE_CIRCLE(point((x, y)), MM(.3))
                at = point((x, y))
                hole_clear = all((pos-at).EuclideanNorm() >
                                 (MM(.3)+drill)/2+MM(.26) for pos, drill in self.holes)
                if hole_clear and self.clear(net, disk, layer) and self.clear(net, disk, other):
                    nexts.append(((x, y, other), 12))
            for t, length in nexts:
                gg = g+length
                if gg < cost.get(t, math.inf):
                    cost[t] = gg
                    prev[t] = s
                    heapq.heappush(todo, (gg+h(t), gg, t))
        if goal is None:
            return False
        path = [goal]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        # Collapse collinear grid edges; never create copper without shape checks.
        compact = [path[0]]
        for i in range(1, len(path)-1):
            a, b, c = path[i-1:i+2]
            if tuple(b[j]-a[j] for j in range(3)) != tuple(c[j]-b[j] for j in range(3)):
                compact.append(b)
        compact.append(path[-1])
        legs = [(start, point(compact[0]), compact[0][2])]
        vias = []
        for a, b in zip(compact, compact[1:]):
            if a[2] != b[2]:
                vias.append(point(a))
            else:
                legs.append((point(a), point(b), a[2]))
        legs.append((point(compact[-1]), end, compact[-1][2]))
        if any(not self.clear(net, k.SHAPE_SEGMENT(a, b, MM(width)), layer)
               for a, b, layer in legs):
            return False
        for a, b, layer in legs:
            add_track(self.board, net, a, b, LAYERS[layer], width)
            self.add_shape(layer, net, k.SHAPE_SEGMENT(a, b, MM(width)))
        for p in vias:
            v = k.PCB_VIA(self.board)
            v.SetPosition(p)
            v.SetWidth(MM(.6))
            v.SetDrill(MM(.3))
            v.SetNetCode(net)
            self.board.Add(v)
            self.remember(v)
            self.holes.append((p, MM(.3)))
        return True


def route_drc(board, report, only):
    objects = {o.m_Uuid.AsString(): o for o in board.GetTracks()}
    objects.update({p.m_Uuid.AsString(): p for f in board.GetFootprints() for p in f.Pads()})
    router = Router(board)
    count, skipped = 0, []
    for issue in json.loads(report.read_text(encoding='utf-8'))['unconnected_items']:
        items = issue['items']
        a, b = [objects.get(i['uuid']) for i in items]
        if a is None or b is None:
            continue
        name = a.GetNetname().removeprefix('/')
        if only and name not in only:
            continue
        if name not in POWER | SIGNALS and not name.startswith('CHG_'):
            continue
        # Do not create tracks into an unconfirmed physical interface.
        if any(isinstance(p, k.PAD) and p.GetParentFootprint().GetReference() in ('J3', 'J4', 'J7')
               for p in (a, b)):
            continue
        layer_a = [i for i, l in enumerate(LAYERS) if a.IsOnLayer(l)]
        layer_b = [i for i, l in enumerate(LAYERS) if b.IsOnLayer(l)]
        pa, pb = [vec(i['pos']['x'], i['pos']['y']) for i in items]
        if router.route(a.GetNetCode(), pa, pb, layer_a, layer_b, .3 if name in POWER else .2):
            count += 1
            print('routed', name, flush=True)
        else:
            skipped.append(name)
    print('Added connections:', count, 'search did not resolve:', skipped)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('board', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--route', type=Path, help='Fresh native DRC JSON for this board')
    p.add_argument('--nets', nargs='+', help='Limit the reviewed nets to route')
    args = p.parse_args()
    board = k.LoadBoard(str(args.board))
    original = {t.m_Uuid.AsString() for t in board.GetTracks()}
    if args.prepare:
        prepare(board)
    if args.route:
        route_drc(board, args.route, set(args.nets or []))
    assert original <= {t.m_Uuid.AsString() for t in board.GetTracks()}, 'Original copper removed'
    k.ZONE_FILLER(board).Fill(board.Zones())
    k.SaveBoard(str(args.out), board)
    print('Saved', args.out, 'tracks/vias:', len(list(board.GetTracks())))


if __name__ == '__main__':
    main()
