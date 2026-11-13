#!/usr/bin/env python3
"""make_stage_zip.py <package_root> <out.zip>
断点打包工具(非检查器): 重算包内 03_SHA256SUMS.txt(除自身外全部文件), 以UTF-8文件名、固定排序打成全量阶段ZIP,
并回读校验每个条目哈希, 最后打印ZIP的SHA256。不修改任何工程文件内容。"""
import sys, os, hashlib, zipfile
root = os.path.abspath(sys.argv[1]); out = os.path.abspath(sys.argv[2])
SELF = '03_SHA256SUMS.txt'
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
files = []
for r, ds, fs in os.walk(root):
    ds[:] = [d for d in ds if d != '__pycache__']
    for f in fs:
        if f.endswith('.pyc'): continue
        rel = os.path.relpath(os.path.join(r, f), root).replace(os.sep, '/')
        if rel != SELF: files.append(rel)
files.sort(key=lambda s: s.encode('utf-8'))
with open(os.path.join(root, SELF), 'w', encoding='utf-8', newline='\n') as f:
    for rel in files: f.write(f"{sha(os.path.join(root, rel))}  {rel}\n")
allf = sorted(files + [SELF], key=lambda s: s.encode('utf-8'))
if os.path.exists(out): os.remove(out)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel in allf: z.write(os.path.join(root, rel), rel)
bad = 0
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for i in z.infolist():
        h = hashlib.sha256(z.read(i)).hexdigest()
        if h != sha(os.path.join(root, i.filename)): bad += 1; print('MISMATCH', i.filename)
print(f"entries={len(allf)} sums_listed={len(files)} mismatches={bad}")
print(f"{sha(out)}  {out}")
sys.exit(1 if bad else 0)
