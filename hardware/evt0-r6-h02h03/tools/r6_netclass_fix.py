"""r6_netclass_fix.py — R6-S1: raise netclass default via drill 0.25->0.30 / dia 0.5->0.6 (board
through-hole min is 0.30; this RAISES rules, never relaxes), and set USB class to the
candidate 90 ohm geometry W=0.22 / S=0.15 (stackup C1, see USB_STACKUP_90R.md).
Edits only net_settings.classes in evt0_core.kicad_pro; preserves key order / 2-space indent."""
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); d = json.loads(p.read_text(encoding='utf-8'))
log = []
for c in d['net_settings']['classes']:
    if c['via_drill'] < 0.3:
        log.append(f"{c['name']}: via_drill {c['via_drill']}->0.3, via_diameter {c['via_diameter']}->0.6")
        c['via_drill'] = 0.3; c['via_diameter'] = max(c['via_diameter'], 0.6)
    if c['diff_pair_via_gap'] < 0.25: c['diff_pair_via_gap'] = 0.25
    if c['name'] == 'USB':
        log.append(f"USB: track/diff width {c['track_width']}/{c['diff_pair_width']}->0.22, gap {c['diff_pair_gap']}->0.15")
        c['track_width'] = 0.22; c['diff_pair_width'] = 0.22; c['diff_pair_gap'] = 0.15
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('\n'.join(log))
