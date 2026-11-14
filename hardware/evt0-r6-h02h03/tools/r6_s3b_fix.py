"""r6_s3b_fix.py — R6-S3b: correct two defects left by r6_pi_margins.py (S3), whose own self-check
assert failed AFTER P.save() (board was written, evidence was not):
  (a) J3.2 / J3.15 GND exit used a 0.20 mm neck -> violates DRU 'Power traces minimum width' (0.30).
      Fix: single 0.30 mm segment pad->via. Its edges coincide with the 0.30 mm pad, so the clearance to
      J3.1/J3.3 and J3.14/J3.16 equals the FOOTPRINT's own 0.20 mm pad-to-pad gap (= Power clearance 0.20).
      This is inherent to FH12 0.5 mm pitch with a 0.30 mm Power width rule; no rule is relaxed.
  (b) /CHG_PGOOD_N F.Cu exit at x=134.25 passed 0.100 mm from the /CHG_EN1 via b695d9a3 (needs 0.15).
      Fix: exit pad at x=134.30 (inside U3.7 pad; 0.288 mm to U3.8 GND pad, 0.227 mm to EN1 via), step to
      x=134.45 below U3.8 (0.30 mm edge gap to the via), 45-degree into a via at (133.80,118.45),
      which keeps 0.25 mm to the B.Cu /VBAT trunk at x=134.50; B.Cu tail unchanged in shape.
Only S3-tagged copper (a6030001/a6030002) is touched. Refuses to run unless the board is in the
post-S3 state (idempotence guard)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb
from r5_route import emit_blocks
from zy_pcb import Board, Rules, drc_lite, dangling

D = Path(sys.argv[1]); pcb_path = D / 'evt0_core.kicad_pcb'
B0 = Board(pcb_path)
have = {it.uuid for it in B0.items if it.kind != 'pad'}
U = lambda g, k: f'a603000{g}-0000-4000-8000-00000000000{k}'
DEL = [U(1, 1), U(1, 2), U(1, 4), U(1, 5),             # J3 GND neck + tail (vias kept)
       U(2, 1), U(2, 2), U(2, 3), U(2, 4)]              # PGOOD F.Cu exit, via, first B.Cu seg
if 'a6030004-0000-4000-8000-000000000001' in have: sys.exit('S3b already applied')
missing = [u for u in DEL if u not in have]
assert not missing, f'board not in post-S3 state, missing {missing}'
P = Pcb(pcb_path); P.delete_uuids(set(DEL))
V4 = lambda k: f'a6030004-0000-4000-8000-00000000000{k}'
ADD = [
    dict(kind='segment', start=[105.75, 99.45], end=[104.25, 99.45], width=0.3, layer='F.Cu', net='/GND', uuid=V4(1)),
    dict(kind='segment', start=[105.75, 105.95], end=[104.25, 105.95], width=0.3, layer='F.Cu', net='/GND', uuid=V4(2)),
    dict(kind='segment', start=[134.30, 116.4625], end=[134.30, 116.95], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid=V4(3)),
    dict(kind='segment', start=[134.30, 116.95], end=[134.45, 117.10], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid=V4(4)),
    dict(kind='segment', start=[134.45, 117.10], end=[134.45, 117.80], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid=V4(5)),
    dict(kind='segment', start=[134.45, 117.80], end=[133.80, 118.45], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid=V4(6)),
    dict(kind='via', at=[133.80, 118.45], size=0.6, drill=0.3, layers=['F.Cu', 'B.Cu'], net='/CHG_PGOOD_N', uuid=V4(7)),
    dict(kind='segment', start=[133.80, 118.45], end=[133.80, 120.30], width=0.2, layer='B.Cu', net='/CHG_PGOOD_N', uuid=V4(8)),
]
P.insert_copper(ADD, emit_blocks); P.save()
B = Board(pcb_path); R = Rules(D / 'evt0_core.kicad_pro')
g = sum(B.gaps().values()); V = drc_lite(B, R, 'all'); dl = dangling(B)
print(f'After R6-S3b: gaps={g}, violations={len(V)}, dangling={len(dl)}')
for v in V: print('  ', v)
out = D.parent / 'evidence' / 'step_r6_s3b_fix'; out.mkdir(parents=True, exist_ok=True)
(out / 'change.json').write_text(json.dumps({'deleted': DEL, 'added': ADD, 'gaps': g, 'violations': [repr(v) for v in V],
                                             'dangling': len(dl), 'note': 'zy_pcb selfcheck, NOT native DRC'}, indent=1))
sys.exit(0 if (g == 51 and not V and not dl) else 1)
