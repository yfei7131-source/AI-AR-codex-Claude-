"""r6_pi_margins.py — R6-S3: resolve J3 GND 0-margin stubs, PGOOD vs CHG_EN1 0.035 mm margin,
and VSYS 0.050 mm east-corridor margin. Only removes/adds listed copper UUIDs."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb
from r5_route import emit_blocks
from zy_pcb import Board, Rules, drc_lite, dangling, dist

D = Path(sys.argv[1])
pcb_path = D / 'evt0_core.kicad_pcb'
P = Pcb(pcb_path)

DEL = [
    # S4 J3.2 / J3.15 horizontal stubs + vias (0.000 mm margin to J3.1/3 and J3.14/16)
    "39eb2362-e2a6-4c95-9036-9fb3290a1b48",
    "5ece5c90-53e9-4430-afdd-55eb975bc53c",
    "c1eba3ab-b8c9-4b9b-963f-85367b1bf38c",
    "e774bfb5-6f96-42e5-b5e6-da06f340b7c5",
    # S1 /CHG_PGOOD_N 9 segments + 1 via (0.035 mm margin to /CHG_EN1 via b695d9a3)
    "5bc47c8f", "5dbe841b", "3c6168df", "22a656d7", "c5bfdbef",
    "897ffba0", "81b71345", "443a802a", "0e40fc42", "2d937512",
    # S5 /VSYS east-corridor 4 segments at x=148.25 (0.050 mm margin to J4/J5 pads)
    "8e95f292", "fbacaad0", "4da475cb", "4cb7c653",
]
# Resolve full UUIDs from current board
B0 = Board(pcb_path)
full_del = [it.uuid for it in B0.items if it.kind != 'pad' and any(it.uuid.startswith(p) for p in DEL)]
assert len(full_del) == len(DEL), f"UUID match mismatch: {len(full_del)} vs {len(DEL)}"
P.delete_uuids(set(full_del))

ADD = [
    # 1) J3.2 & J3.15 GND: exit w=0.20 inside pad (0.050 mm margin to neighbor pads), step to w=0.30 at x=104.95
    dict(kind='segment', start=[105.75, 99.45], end=[104.95, 99.45], width=0.2, layer='F.Cu', net='/GND', uuid='a6030001-0000-4000-8000-000000000001', tag='r6_s3_j3_gnd'),
    dict(kind='segment', start=[104.95, 99.45], end=[104.25, 99.45], width=0.3, layer='F.Cu', net='/GND', uuid='a6030001-0000-4000-8000-000000000002', tag='r6_s3_j3_gnd'),
    dict(kind='via', at=[104.25, 99.45], size=0.6, drill=0.3, layers=['F.Cu', 'B.Cu'], net='/GND', uuid='a6030001-0000-4000-8000-000000000003', tag='r6_s3_j3_gnd'),
    dict(kind='segment', start=[105.75, 105.95], end=[104.95, 105.95], width=0.2, layer='F.Cu', net='/GND', uuid='a6030001-0000-4000-8000-000000000004', tag='r6_s3_j3_gnd'),
    dict(kind='segment', start=[104.95, 105.95], end=[104.25, 105.95], width=0.3, layer='F.Cu', net='/GND', uuid='a6030001-0000-4000-8000-000000000005', tag='r6_s3_j3_gnd'),
    dict(kind='via', at=[104.25, 105.95], size=0.6, drill=0.3, layers=['F.Cu', 'B.Cu'], net='/GND', uuid='a6030001-0000-4000-8000-000000000006', tag='r6_s3_j3_gnd'),
    # 2) /CHG_PGOOD_N: clean 5-segment + 1-via route with >= 0.087 mm margin to U3.8 & CHG_EN1 via
    dict(kind='segment', start=[134.25, 116.4625], end=[134.25, 117.75], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000001', tag='r6_s3_pgood'),
    dict(kind='segment', start=[134.25, 117.75], end=[133.8, 118.2], width=0.2, layer='F.Cu', net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000002', tag='r6_s3_pgood'),
    dict(kind='via', at=[133.8, 118.2], size=0.6, drill=0.3, layers=['F.Cu', 'B.Cu'], net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000003', tag='r6_s3_pgood'),
    dict(kind='segment', start=[133.8, 118.2], end=[133.8, 120.3], width=0.2, layer='B.Cu', net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000004', tag='r6_s3_pgood'),
    dict(kind='segment', start=[133.8, 120.3], end=[132.35, 121.75], width=0.2, layer='B.Cu', net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000005', tag='r6_s3_pgood'),
    dict(kind='segment', start=[132.35, 121.75], end=[132.0, 121.75], width=0.2, layer='B.Cu', net='/CHG_PGOOD_N', uuid='a6030002-0000-4000-8000-000000000006', tag='r6_s3_pgood'),
    # 3) /VSYS east-corridor moved from x=148.25 -> x=148.60 (0.40 mm margin to J4/J5 pads, 1.25 mm to board edge)
    dict(kind='segment', start=[147.0, 71.54], end=[148.6, 73.14], width=0.3, layer='F.Cu', net='/VSYS', uuid='a6030003-0000-4000-8000-000000000001', tag='r6_s3_vsys'),
    dict(kind='segment', start=[148.6, 73.14], end=[148.6, 106.3], width=0.3, layer='F.Cu', net='/VSYS', uuid='a6030003-0000-4000-8000-000000000002', tag='r6_s3_vsys'),
    dict(kind='segment', start=[148.6, 106.3], end=[147.55, 107.35], width=0.3, layer='F.Cu', net='/VSYS', uuid='a6030003-0000-4000-8000-000000000003', tag='r6_s3_vsys'),
    dict(kind='segment', start=[147.55, 107.35], end=[146.45, 107.35], width=0.3, layer='F.Cu', net='/VSYS', uuid='a6030003-0000-4000-8000-000000000004', tag='r6_s3_vsys'),
]
P.insert_copper(ADD, emit_blocks)
P.save()

B = Board(pcb_path); R = Rules(D / 'evt0_core.kicad_pro')
g = sum(B.gaps().values()); V = drc_lite(B, R, 'all'); dl = dangling(B)
print(f"After R6-S3: gaps={g}, violations={len(V)}, dangling={len(dl)}")
assert g == 51 and not V and not dl
out = D.parent / 'evidence' / 'step_r6_s3_pi_margins'
out.mkdir(parents=True, exist_ok=True)
(out / 'change.json').write_text(json.dumps({'deleted': full_del, 'added': ADD, 'gaps': g, 'violations': len(V), 'dangling': len(dl)}, indent=1))
