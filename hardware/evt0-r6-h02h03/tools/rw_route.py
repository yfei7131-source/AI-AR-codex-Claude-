"""rw_route: 复用 r5_route/r5_run 布线器, 对指定网络增量布线并真正写回 kicad_pcb (仅追加 segment/via)。
用法: python rw_route.py <prj_dir> <step_tag> NET[:plane] ...   输出 evidence/<step_tag>/added_copper.json + route_log.txt"""
import json, sys, time, io, contextlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from r5_route import Router, emit_blocks
from r5_run import route_net, load
from pcb_edit import Pcb
from zy_pcb import drc_lite, dangling
D = Path(sys.argv[1]); tag = sys.argv[2]; specs = sys.argv[3:]
out = D.parent/'evidence'/tag; out.mkdir(parents=True, exist_ok=True)
B, R = load(D); RT = Router(B, R)
g0 = sum(B.gaps().values()); logs = []
def log(*a): s = ' '.join(str(x) for x in a); print(s); logs.append(s)
res = {}
for sp in specs:
    net, _, mode = sp.partition(':')
    t = time.time(); w = 0.3 if R.nc(net) == 'Power' else 0.2
    done, failed = route_net(RT, net, w, plane=(mode == 'plane'), log=log)
    res[net] = dict(done=done, failed=failed, sec=round(time.time()-t, 1)); log(net, res[net])
V = drc_lite(B, R, 'new'); dl = [a for a, p in dangling(B) if a.new]
g1 = sum(B.gaps().values())
log(f'gaps {g0}->{g1}; new items {len(RT.added)}; drc_lite(new) {len(V)}; dangling(new) {len(dl)}')
assert not V and not dl, 'self-check failed, nothing written'
if RT.added:
    P = Pcb(D/'evt0_core.kicad_pcb'); P.insert_copper(RT.added, emit_blocks); P.save()
json.dump(dict(note='zy_pcb/r5_route incremental routing; NOT KiCad native DRC', gaps_before=g0, gaps_after=g1, result=res, added_copper=RT.added), open(out/'added_copper.json', 'w'), indent=1)
(out/'route_log.txt').write_text('\n'.join(logs) + '\n')
