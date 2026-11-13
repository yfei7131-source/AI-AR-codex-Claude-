"""独立 S-expression 解析器(本轮新写, 不依赖 tools/sx.py)。"""
import re
_TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')
def parse(text):
    st=[[]]
    for m in _TOK.finditer(text):
        t=m.group(0)
        if t=='(':
            st.append([])
        elif t==')':
            x=st.pop(); st[-1].append(x)
        elif t[0]=='"':
            st[-1].append(('S',t[1:-1].replace('\\"','"').replace('\\\\','\\')))
        else:
            st[-1].append(t)
    return st[0][0]
def head(n): return n[0] if n and isinstance(n[0],str) else None
def kids(n,name): return [c for c in n[1:] if isinstance(c,list) and head(c)==name]
def kid(n,name):
    k=kids(n,name); return k[0] if k else None
def sval(x): return x[1] if isinstance(x,tuple) else x
