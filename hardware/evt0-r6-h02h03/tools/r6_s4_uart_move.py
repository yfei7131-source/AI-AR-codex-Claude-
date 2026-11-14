"""r6_s4_uart_move.py — R6-S4: relocate the DNP audio-UART bridge options R33/R34 next to J7.

Problem: R33/R34 (0R DNP, UART0 <-> J7 audio-EVB bridge) sat at the TOP of the board (y~71) while
J7 is at y=100, so /AUD_UART_TX/RX had to cross the full board height (~37 mm each, 3-4 vias) and
walled off the U1 -> J4 display corridor. UART0 (U0TXD/U0RXD) already arrives at J6/R30/R31 (y 95-100).
Fix (placement only, schematic unchanged -> parity must stay 0):
  R33 -> (131.60, 97.50) rot 0 (horizontal: its 0.94 mm courtyard fits the 1.4 mm J6/J7 courtyard gap),
         between J6.3 (U0TXD) and J7.2 (AUD_UART_TX)
  R34 -> (137.60,102.00) rot 270 (vertical: clears J7 courtyard corner), between R31.2 (U0RXD) and J7.3;
         U0RXD passes 0.23 mm under R31.1 (3V3, Power 0.20) and 0.22 mm from the /VBAT_ADC diagonal
  delete the now-dangling U0RXD branch that only fed the old R34.1 (5 segments + 2 vias);
  U0TXD passed THROUGH old R33.1, its two segments still meet end-to-end, so nothing removed there.
  add 4 short 0.2 mm F.Cu links (all octilinear).
Bridge stays DNP; mutual exclusion with the I2C option (R30/R31) and EVB isolation notes unchanged."""
import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb
from r5_route import emit_blocks
from zy_pcb import Board, Rules, drc_lite, dangling

D = Path(sys.argv[1]); pcb = D / 'evt0_core.kicad_pcb'
P = Pcb(pcb)

def move_fp(ref, x, y, rot, old_rot=90):
    a, b = P._fp_span(ref); t = P.t[a:b]
    hdr = re.search(r'\r\n\t\t\(at ([-\d.]+) ([-\d.]+) %s\)' % old_rot, t)
    assert hdr, ref
    t = t[:hdr.start()] + '\r\n\t\t(at %s %s %s)' % (x, y, rot) + t[hdr.end():]
    # every child (at u v old_rot) -> (at u v rot): KiCad stores absolute orientation on pads/texts
    t, n = re.subn(r'\(at ([-\d.]+) ([-\d.]+) %s\)' % old_rot, lambda m: '(at %s %s %s)' % (m.group(1), m.group(2), rot), t)
    P.t = P.t[:a] + t + P.t[b:]
    return n

if 'a6030005-0000-4000-8000-000000000001' in P.t: sys.exit('S4 already applied')
n33 = move_fp('R33', 131.6, 97.5, 0); n34 = move_fp('R34', 137.6, 102.0, 270)
BR = ['4caaa460', '09371066', '80178b78', '37d39124', 'f297e674', '295ac172', '7f9c9f1c']
B0 = Board(pcb)
full = [it.uuid for it in B0.items if it.kind != 'pad' and any(it.uuid.startswith(p) for p in BR)]
assert len(full) == len(BR), full
P.delete_uuids(set(full))
U = lambda k: f'a6030005-0000-4000-8000-00000000000{k}'
seg = lambda a, b, k, net: dict(kind='segment', start=list(a), end=list(b), width=0.2, layer='F.Cu', net=net, uuid=U(k))
ADD = [
    seg((131.09, 97.5), (131.09, 96.99), 1, '/U0TXD'), seg((131.09, 96.99), (132.08, 96.0), 2, '/U0TXD'),
    seg((132.08, 96.0), (132.08, 95.0), 3, '/U0TXD'),
    seg((132.11, 97.5), (132.11, 99.57), 4, '/AUD_UART_TX'), seg((132.11, 99.57), (132.54, 100.0), 5, '/AUD_UART_TX'),
    seg((137.6, 101.49), (137.94, 101.15), 6, '/U0RXD'), seg((137.94, 101.15), (139.51, 101.15), 7, '/U0RXD'),
    seg((139.51, 101.15), (139.51, 100.6), 8, '/U0RXD'),
    seg((137.6, 102.51), (135.57, 102.51), 9, '/AUD_UART_RX'), seg((135.57, 102.51), (135.08, 102.02), 'a', '/AUD_UART_RX'),
    seg((135.08, 102.02), (135.08, 100.0), 'b', '/AUD_UART_RX'),
]
P.insert_copper(ADD, emit_blocks); P.save()
B = Board(pcb); R = Rules(D / 'evt0_core.kicad_pro')
pads = {f'{it.ref}.{it.num}': (round(it.x, 3), round(it.y, 3)) for it in B.items if it.kind == 'pad' and it.ref in ('R33', 'R34')}
g = B.gaps(); V = drc_lite(B, R, 'all'); dl = dangling(B)
print('pads', pads, 'angle edits', n33, n34)
print(f'After R6-S4: gaps={sum(g.values())}, violations={len(V)}, dangling={len(dl)}')
for v in V: print('  ', v)
for a, p in dl: print('  dangling', a, p)
out = D.parent / 'evidence' / 'step_r6_s4_uart_move'; out.mkdir(parents=True, exist_ok=True)
(out / 'change.json').write_text(json.dumps(dict(moved={'R33': [131.6, 97.5, 0], 'R34': [137.6, 102.0, 270]}, pads_after=pads,
    deleted=full, added=ADD, gaps=sum(g.values()), violations=[repr(v) for v in V], dangling=len(dl),
    note='zy_pcb selfcheck, NOT native DRC'), indent=1))
sys.exit(0 if (not V and not dl) else 1)
