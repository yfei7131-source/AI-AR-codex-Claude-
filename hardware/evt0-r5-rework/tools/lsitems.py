"""列出窗口内的走线/过孔: python lsitems.py prj x0 y0 x1 y1 [layer]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from zy_pcb import *
def ls(B,x0,y0,x1,y1,layer=None):
    for it in B.items:
        if it.kind=='pad': continue
        sh=it.shape
        if max(sh[1],sh[3])<x0 or min(sh[1],sh[3])>x1 or max(sh[2],sh[4])<y0 or min(sh[2],sh[4])>y1: continue
        if layer and layer not in it.layers: continue
        if it.kind=='trk': print(f"T {sorted(it.layers)[0][0]} {it.net:16s} ({sh[1]:.3f},{sh[2]:.3f})-({sh[3]:.3f},{sh[4]:.3f}) w{it.w} {it.uuid[:8]}")
        else: print(f"V   {it.net:16s} ({sh[1]:.3f},{sh[2]:.3f}) d{it.w}/{it.drill} {it.uuid[:8]}")
if __name__=='__main__':
    B=Board(sys.argv[1]+'/evt0_core.kicad_pcb'); ls(B,*map(float,sys.argv[2:6]),*(sys.argv[6:7]))
