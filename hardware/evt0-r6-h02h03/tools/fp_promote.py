"""fp_promote: 把板上 (含 R3/R5 本地修改的) 封装固化为项目封装库 aiar_fp.pretty,
并把 PCB 与原理图的 Footprint 库标识改指向该项目库, 以消除 lib_footprint_mismatch (不使用 ignore/降级)。

板文件 -> .kicad_mod 转换规则 (KiCad 板文件约定: 焊盘/文本角度为绝对角, 封装内 zone 为绝对坐标):
  - 去掉实例数据: 顶层 (at)/(uuid)/(path)/(sheetname)/(sheetfile), 焊盘 (net)/(pinfunction)/(pintype)
  - 焊盘/属性/fp_text 角度减去封装角度; 封装内 zone 坐标减去封装原点 (仅支持 0° 封装含 zone)
  - Reference 文本改 REF**; 去掉原理图回填字段 MPN/Manufacturer/Note (库副本中不存在, KiCad 比较时不计)
用法: python fp_promote.py <prj_dir> REF:NEWNAME ...
"""
import re, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb

LIB = 'aiar_fp'
DROP_FIELDS = ('MPN', 'Manufacturer', 'Note')


def norm_ang(a):
    a = (a % 360 + 360) % 360
    return 0.0 if abs(a) < 1e-9 or abs(a - 360) < 1e-9 else a


def fnum(v):
    t = ('%.6f' % v).rstrip('0').rstrip('.')
    return '0' if t in ('-0', '') else t


def to_lib(fp_text, newname):
    L = fp_text.split('\r\n')
    head = re.match(r'\t\(footprint "([^"]+)"', L[0]); assert head
    at = None
    for l in L[1:8]:
        m = re.match(r'\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)$', l)
        if m: at = (float(m.group(1)), float(m.group(2)), float(m.group(3) or 0)); break
    fx, fy, fa = at
    out = ['(footprint "%s"' % newname, '\t(version 20260206)', '\t(generator "pcbnew")', '\t(generator_version "10.0")']
    i = 1; n = len(L)
    def block_end(k):            # index of line closing the block opened at line k (same indent)
        ind = len(L[k]) - len(L[k].lstrip('\t'))
        if L[k].rstrip().endswith(')') and L[k].count('(') == L[k].count(')'): return k
        j = k + 1
        while not (L[j] == '\t' * ind + ')'): j += 1
        return j
    while i < n - 1:
        l = L[i]
        if not l.startswith('\t\t('):
            i += 1; continue
        e = block_end(i)
        blk = L[i:e + 1]
        key = re.match(r'\t\t\((\w+)', l).group(1)
        if key in ('at', 'uuid', 'path', 'sheetname', 'sheetfile'):
            i = e + 1; continue
        if key == 'property':
            name = re.match(r'\t\t\(property "([^"]+)"', l).group(1)
            if name in DROP_FIELDS: i = e + 1; continue
            if name == 'Reference': blk[0] = re.sub(r'"[^"]*"$', '"REF**"', blk[0]) if blk[0].endswith('"') else re.sub(r'(\(property "Reference" )"[^"]*"', r'\1"REF**"', blk[0])
        if key in ('property', 'fp_text', 'pad'):
            for k, b in enumerate(blk):
                m = re.match(r'(\t\t\t\(at ([-\d.]+) ([-\d.]+))(?: ([-\d.]+))?\)$', b)
                if m:
                    a = norm_ang(float(m.group(4) or 0) - fa)
                    blk[k] = m.group(1) + ((' ' + fnum(a)) if a else '') + ')'
                    break
        if key == 'pad':
            blk = [b for b in blk if not re.match(r'\t\t\t\((net|pinfunction|pintype) ', b)]
        if key == 'zone':
            if abs(fa) > 1e-9: raise RuntimeError('zone in rotated footprint not supported')
            blk = [re.sub(r'\(xy ([-\d.]+) ([-\d.]+)\)', lambda m: '(xy %s %s)' % (fnum(float(m.group(1)) - fx), fnum(float(m.group(2)) - fy)), b) for b in blk]
        out += [b[1:] for b in blk]          # 去掉一级缩进
        i = e + 1
    out.append(')')
    return '\n'.join(out) + '\n', head.group(1), at


def main(D, specs):
    D = Path(D); P = Pcb(D/'evt0_core.kicad_pcb')
    pretty = D/(LIB + '.pretty'); pretty.mkdir(exist_ok=True)
    rec = []
    for spec in specs:
        ref, newname = spec.split(':')
        a, b = P._fp_span(ref)
        txt, old, at = to_lib(P.t[a:b], newname)
        (pretty/(newname + '.kicad_mod')).write_text(txt)
        P.set_fp_lib(ref, '%s:%s' % (LIB, newname))
        rec.append(dict(ref=ref, old_lib_id=old, new_lib_id='%s:%s' % (LIB, newname), placed_at=at))
    P.save()
    # fp-lib-table
    t = (D/'fp-lib-table').read_text(newline='') if False else open(D/'fp-lib-table', newline='').read()
    if '(name "%s")' % LIB not in t:
        line = '  (lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/%s.pretty") (options "") (descr "R5 project-local footprint variants (R3/R5 deviations from KiCad10 std lib, see CHANGELOG)"))\r\n' % (LIB, LIB)
        k = t.rstrip().rfind(')'); t = t[:k] + line + t[k:]
        open(D/'fp-lib-table', 'w', newline='').write(t)
    # schematic + symbol lib: Footprint property of those refs
    sch = open(D/'evt0_core.kicad_sch', newline='').read()
    for r in rec:
        n0 = sch.count('"%s"' % r['old_lib_id'])
        # 实例 Footprint 属性 (按 Reference 定位 symbol 块)
        pat = re.compile(r'(\(symbol\r?\n\t\t\(lib_id "[^"]+"\).*?\(property "Reference" "%s".*?\(property "Footprint" ")%s(")' % (re.escape(r['ref']), re.escape(r['old_lib_id'])), re.S)
        sch, k = pat.subn(lambda m: m.group(1) + r['new_lib_id'] + m.group(2), sch, count=1)
        r['sch_instance_updated'] = k; r['old_id_occurrences_in_sch_before'] = n0
    open(D/'evt0_core.kicad_sch', 'w', newline='').write(sch)
    print(json.dumps(rec, indent=1))
    return rec


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
