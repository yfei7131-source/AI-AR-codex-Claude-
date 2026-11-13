"""manual_copper: 按 JSON 规格添加人工指定的 segment/via, 自检 (drc_lite new + dangling + 连通) 全过才写回。
spec: [{"net":..,"width":..,"layer":..,"pts":[[x,y],...]} | {"net":..,"via":[x,y]}] ; 可选 "delete":[uuid...] (先删后加)"""
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from zy_pcb import Board, Rules, drc_lite, dangling
from r5_route import emit_blocks, VIA_D, VIA_DRILL
from pcb_edit import Pcb
def apply(D, spec, tag, write=True):
    D = Path(D); B = Board(D/'evt0_core.kicad_pcb'); R = Rules(D/'evt0_core.kicad_pro')
    dele = set(spec.get('delete', []))
    g0 = B.gaps(); nets = set()
    if dele:
        B.items = [it for it in B.items if it.uuid not in dele or it.kind == 'pad']
    recs = []
    for e in spec['add']:
        nets.add(e['net'])
        if 'via' in e:
            u = str(uuid.uuid4()); x, y = e['via']; B.add_via(x, y, VIA_D, VIA_DRILL, e['net'], u, True)
            recs.append(dict(kind='via', at=[x, y], size=VIA_D, drill=VIA_DRILL, layers=['F.Cu', 'B.Cu'], net=e['net'], uuid=u, tag=tag))
        else:
            for a, b in zip(e['pts'], e['pts'][1:]):
                u = str(uuid.uuid4()); B.add_track(a[0], a[1], b[0], b[1], e['width'], e['layer'], e['net'], u, True)
                recs.append(dict(kind='segment', start=a, end=b, width=e['width'], layer=e['layer'], net=e['net'], uuid=u, tag=tag))
    V = drc_lite(B, R, 'new'); dl = [(a, p) for a, p in dangling(B) if a.new]
    g1 = B.gaps()
    worse = {n: (g0.get(n, 0), g1.get(n, 0)) for n in set(g0) | set(g1) if g1.get(n, 0) > g0.get(n, 0)}
    ok = not V and not dl and not worse
    rep = dict(tag=tag, ok=ok, gaps_before=sum(g0.values()), gaps_after=sum(g1.values()),
               nets={n: (g0.get(n, 0), g1.get(n, 0)) for n in nets | {B2 for B2 in worse}}, worse=worse,
               violations=[str(v) for v in V], dangling=[str(x) for x in dl], deleted=sorted(dele), added_copper=recs)
    if ok and write:
        P = Pcb(D/'evt0_core.kicad_pcb')
        if dele: P.delete_uuids(dele)
        P.insert_copper(recs, emit_blocks); P.save()
    return rep
if __name__ == '__main__':
    D, specf, tag = sys.argv[1:4]
    spec = json.load(open(specf)); rep = apply(D, spec, tag, write='--dry' not in sys.argv)
    out = Path(D).parent/'evidence'/tag; out.mkdir(parents=True, exist_ok=True)
    if '--dry' not in sys.argv: json.dump(rep, open(out/'change.json', 'w'), indent=1)
    print(json.dumps({k: rep[k] for k in ('ok', 'gaps_before', 'gaps_after', 'nets', 'worse', 'violations', 'dangling')}, indent=0))
