# -*- coding: utf-8 -*-
"""R8 parity: EDA connectivity IR vs R7 KiCad netlist.csv (authoritative)."""
import json, csv, sys

R7 = 'r6_git_upload/hardware/evt0-r6-h02h03/evt0_core/netlist.csv'
EDA = 'r8_rebuild/conn_now.json'

# KiCad combined-pad -> EDA split pads (USB-C etc.)
K2E = {
    ('J1','A1B12'): ['A1B12'],
    ('J1','B1A12'): ['B1A12'],
    ('J1','A4B9'):  ['A4B9'],
    ('J1','B4A9'):  ['B4A9'],
}
# R7 KiCad pin names that map to different EDA pad names
PIN_MAP = {
    ('J1','A1'): 'A1B12', ('J1','B12'): 'A1B12',
    ('J1','B1'): 'B1A12', ('J1','A12'): 'B1A12',
    ('J1','A4'): 'A4B9',  ('J1','B9'): 'A4B9',
    ('J1','B4'): 'B4A9',  ('J1','A9'): 'B4A9',
}

r7 = {}   # (ref,pin) -> net   (KiCad pin naming)
with open(R7, encoding='utf-8-sig') as f:
    for row in list(csv.reader(f))[1:]:
        net, ref, pin = row[0].strip(), row[1].strip(), row[2].strip()
        r7[(ref, pin)] = net

d = json.load(open(EDA, encoding='utf-8'))
r = d.get('result', d)
netmap = {n['id']: n['name'] for n in r['nets']}
eda = {}  # (ref,pin) -> net
for c in r['connections']:
    ref = c['componentId'].replace('cmp-', '')
    eda[(ref, c['pinNumber'])] = netmap.get(c['netId'], '?')
eda_pinset = set()
for comp in r['components']:
    ref = comp['ref']
    for p in comp['pins']:
        eda_pinset.add((ref, p['number']))

missing_in_eda = []   # R7 pin not present in EDA symbol at all
mismatch = []         # net differs
ok = 0
for (ref, pin), net in sorted(r7.items()):
    epin = PIN_MAP.get((ref, pin), pin)
    if (ref, epin) not in eda_pinset:
        missing_in_eda.append((ref, pin, net))
        continue
    enet = eda.get((ref, epin))
    if enet != net:
        mismatch.append((ref, pin, net, enet))
    else:
        ok += 1

extra_nets = []  # EDA pins connected but not in R7 (excluding NC)
r7_mapped = set()
for (ref, pin) in r7:
    r7_mapped.add((ref, PIN_MAP.get((ref, pin), pin)))
for (ref, pin), net in sorted(eda.items()):
    if (ref, pin) not in r7_mapped:
        extra_nets.append((ref, pin, net))

print(f'R7 entries: {len(r7)}  EDA pins: {len(eda_pinset)}  EDA connected: {len(eda)}')
print(f'OK: {ok}')
print(f'MISSING in EDA symbol: {len(missing_in_eda)}')
for m in missing_in_eda: print('  ', m)
print(f'MISMATCH: {len(mismatch)}')
for m in mismatch: print('  ', m)
print(f'EXTRA connected in EDA (not in R7): {len(extra_nets)}')
for m in extra_nets: print('  ', m)
