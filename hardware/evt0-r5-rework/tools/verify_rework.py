"""verify_rework.py <evt0_core_dir>  — 文本级核对 S1-S4 + 原生KiCad检查(无kicad-cli则NOT RUN)。不修改任何文件。"""
import sys,re,shutil,subprocess,json
from pathlib import Path
D=Path(sys.argv[1]); pcb=open(D/'evt0_core.kicad_pcb',newline='',encoding='utf-8').read(); R={}
def vias_at(pts): return {str(p):bool(re.search(r'\(via\s+\(at %s %s\)'%(re.escape(str(p[0])),re.escape(str(p[1]))),pcb.replace('\r',''))) for p in pts}
R['S1_zone_filled_polygon_count']=pcb.count('(filled_polygon')            # 期望0(待KiCad重铺)
R['S1_PGOOD_via_133.8_118.1']=bool(re.search(r'\(via\s+\(at 133\.8 118\.1\)',pcb.replace('\r','')))
R['S1_PGOOD_net_items']=pcb.count('/CHG_PGOOD_N')
R['S2_U1_pad41_drill_0.3']=len(re.findall(r'\(pad "41" thru_hole.*?\(drill 0\.3\)',pcb,re.S))
R['S2_U1_pad41_drill_0.2_left']=len(re.findall(r'\(pad "41" thru_hole.*?\(drill 0\.2\)',pcb,re.S))
R['S3_pretty_dir']=(D/'aiar_fp.pretty').is_dir()
R['S3_fp_lib_table']='aiar_fp' in open(D/'fp-lib-table',newline='').read() if (D/'fp-lib-table').exists() else False
R['S3_pcb_lib_ids']=sorted(set(re.findall(r'\(footprint "(aiar_fp:[^"]+)"',pcb)))
R['S4_gnd_vias']=vias_at([(104.35,99.45),(104.35,105.95),(102.5,98.65),(102.5,110.75)])
k=shutil.which('kicad-cli')
if not k: R['native_ERC_DRC']='NOT RUN (kicad-cli not available)'
else:
    o=D/'native_reports'; o.mkdir(exist_ok=True)
    subprocess.run([k,'sch','erc','--severity-all','-f','json','-o',str(o/'erc.json'),str(D/'evt0_core.kicad_sch')])
    subprocess.run([k,'pcb','drc','--severity-all','--schematic-parity','--refill-zones','-f','json','-o',str(o/'drc.json'),str(D/'evt0_core.kicad_pcb')])
    R['native_ERC_DRC']='RUN: see native_reports/'
print(json.dumps(R,indent=1,ensure_ascii=False))
