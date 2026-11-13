import re
TOK=re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()]+))')
class S(str):  # quoted string marker
    pass
def parse(t):
    pos=0; st=[[]]
    n=len(t)
    while True:
        m=TOK.match(t,pos)
        if not m: break
        pos=m.end()
        if m.group(1): st.append([])
        elif m.group(2):
            x=st.pop(); st[-1].append(x)
        elif m.group(3) is not None: st[-1].append(S(m.group(3)))
        else: st[-1].append(m.group(4))
    return st[0][0]
def find(n,k): return [c for c in n if isinstance(c,list) and c and c[0]==k]
def one(n,k):
    r=find(n,k); return r[0] if r else None
