#!/usr/bin/env python3
"""compare_native_expected.py <native_out_dir|drc.json> <expected.json>
结果比对器(非检查器): 读取 KiCad 原生 drc.json, 按网络统计 unconnected_items(取描述里方括号内网名, 与界面语言无关),
与 expected.json 的预期逐网比较, 并列出违规类型/原理图一致性条目数。退出码: 0=与预期完全一致, 1=存在偏差。"""
import sys, json, re
from pathlib import Path
from collections import Counter
src = Path(sys.argv[1]); src = src / 'drc.json' if src.is_dir() else src
exp = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
drc = json.loads(src.read_text(encoding='utf-8'))
nat = Counter()
for u in drc.get('unconnected_items', []):
    nets = sorted({(re.search(r'\[([^\]]*)\]', i['description']) or [None, '?'])[1] for i in u['items']})
    nat['+'.join(nets)] += 1
want = Counter(exp['expected_unconnected_by_net'])
diff = {k: (nat.get(k, 0), want.get(k, 0)) for k in set(nat) | set(want) if nat.get(k, 0) != want.get(k, 0)}
viol = Counter(v['type'] for v in drc.get('violations', []))
r = dict(kicad_version=drc.get('kicad_version'), native_unconnected=sum(nat.values()), expected_unconnected=sum(want.values()),
         unconnected_by_net_diff_native_vs_expected=diff, violations_by_type=dict(viol),
         expected_violations_by_type=exp.get('expected_violations_by_type', {}),
         schematic_parity_items=len(drc.get('schematic_parity', [])), expected_parity_items=exp.get('expected_parity_items'))
print(json.dumps(r, ensure_ascii=False, indent=1))
ok = (not diff and dict(viol) == exp.get('expected_violations_by_type', {}) and r['schematic_parity_items'] == exp.get('expected_parity_items'))
print('MATCHES_EXPECTED' if ok else 'DEVIATES_FROM_EXPECTED -- 逐项分诊, 勿据此宣称通过/失败')
sys.exit(0 if ok else 1)
