"""r6_render.py — plot selected copper layers with REAL kicad-cli (PDF) and rasterize to PNG (PyMuPDF).
usage: python r6_render.py <board.kicad_pcb> <out_dir> --kicad-cli PATH [--clip x0,y0,x1,y1] [--dpi N]
Writes one PNG per view: In1 (GND plane), In2 (3V3 plane), F.Cu, B.Cu, each with Edge.Cuts.
--clip crops to a board-mm window (board origin of the PDF page is derived from Edge.Cuts bbox).
Visual aid only; KiCad DRC remains the authority."""
import sys, subprocess, tempfile, shutil
from pathlib import Path
import pymupdf
a = sys.argv[1:]
def opt(k, d=None):
    if k in a: i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d
cli = opt('--kicad-cli'); clip = opt('--clip'); dpi = int(opt('--dpi', '600'))
pcb, out = Path(a[0]).resolve(), Path(a[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
VIEWS = {'In1_GND': 'In1.Cu,Edge.Cuts', 'In2_3V3': 'In2.Cu,Edge.Cuts', 'F_Cu': 'F.Cu,Edge.Cuts', 'B_Cu': 'B.Cu,Edge.Cuts'}
W = Path(tempfile.mkdtemp(prefix='zy_render_'))
for name, layers in VIEWS.items():
    pdf = W / f'{name}.pdf'
    r = subprocess.run([cli, 'pcb', 'export', 'pdf', '--mode-single', '--black-and-white', '--drill-shape-opt', '2',
                        '-l', layers, '-o', str(pdf), str(pcb)], capture_output=True, text=True)
    if r.returncode: print(name, 'FAILED', r.stderr); continue
    doc = pymupdf.open(pdf); pg = doc[0]
    rect = None
    if clip:
        # page is plotted 1:1 in mm with board drawn at its absolute coordinates on the A4 sheet
        x0, y0, x1, y1 = map(float, clip.split(','))
        k = 72 / 25.4; rect = pymupdf.Rect(x0 * k, y0 * k, x1 * k, y1 * k)
    pix = pg.get_pixmap(dpi=dpi, clip=rect)
    png = out / f'{name}{"_clip" if clip else ""}.png'; pix.save(png); print('wrote', png, pix.width, 'x', pix.height)
shutil.rmtree(W, ignore_errors=True)
