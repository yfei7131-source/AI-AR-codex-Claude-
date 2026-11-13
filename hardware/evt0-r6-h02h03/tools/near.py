"""near.py — list copper items within a box: python near.py <prj> x0 y0 x1 y1 [layer]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from zy_pcb import Board, Rules
D = Path(sys.argv[1]); x0, y0, x1, y1 = map(float, sys.argv[2:6]); lay = sys.argv[6] if len(sys.argv) > 6 else None
B = Board(D / 'evt0_core.kicad_pcb'); R = Rules(D / 'evt0_core.kicad_pro')
for it in B.items:
    sh = it.shape
    xs = [sh[1], sh[3]] if sh[0] == 'cap' else [p[0] for p in sh[1]]
    ys = [sh[2], sh[4]] if sh[0] == 'cap' else [p[1] for p in sh[1]]
    if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
    if lay and lay not in it.layers: continue
    L = ','.join(sorted(l[:2] if l[0] in 'FB' else l[:3] for l in it.layers))
    if it.kind == 'trk': g = f"({sh[1]:.3f},{sh[2]:.3f})->({sh[3]:.3f},{sh[4]:.3f}) w={it.w}"
    elif it.kind == 'via': g = f"({it.x:.3f},{it.y:.3f}) d={it.w} dr={it.drill}"
    else:
        g = f"({it.x:.3f},{it.y:.3f}) " + (f"cap r={sh[5]:.3f}" if sh[0]=='cap' else 'poly x%.3f..%.3f y%.3f..%.3f' % (min(xs), max(xs), min(ys), max(ys)))
    print(f"{it.kind:3} {(it.ref or '')+('.'+it.num if it.num else ''):8} {it.net:16} {R.nc(it.net):8} {L:12} {g} {it.uuid[:8]}")
