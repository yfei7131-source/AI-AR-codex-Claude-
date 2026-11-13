"""selfcheck: zy_pcb 自检汇总 (非 KiCad 原生 DRC)。python selfcheck.py <prj_dir> [out.json]"""
import sys, json, time
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent))
from zy_pcb import Board, Rules, drc_lite, dangling
def run(D):
    D = Path(D); t = time.time()
    B = Board(D/'evt0_core.kicad_pcb'); R = Rules(D/'evt0_core.kicad_pro')
    g = B.gaps(); V = drc_lite(B, R, 'all'); dl = dangling(B)
    return dict(note='zy_pcb selfcheck, NOT KiCad native DRC', gaps_total=sum(g.values()),
                gaps_by_net=dict(sorted(g.items(), key=lambda x: (-x[1], x[0]))),
                violations=dict(Counter(v[0] for v in V)),
                violation_detail=[[v[0], repr(v[1]), repr(v[2]) if len(v) > 2 else '', *[x for x in v[3:]]] for v in V],
                dangling=[[repr(a), list(p)] for a, p in dl], seconds=round(time.time()-t, 1))
if __name__ == '__main__':
    r = run(sys.argv[1]); s = json.dumps(r, indent=1, ensure_ascii=False, default=str)
    if len(sys.argv) > 2: Path(sys.argv[2]).write_text(s)
    print(json.dumps({k: r[k] for k in ('gaps_total', 'violations', 'seconds')}), 'dangling', len(r['dangling']))
