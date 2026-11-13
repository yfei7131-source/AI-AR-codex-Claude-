#!/usr/bin/env python3
"""ZY EVT-1 parametric assembly (R5). Run: python zy_evt1_asm.py [resin|sic075|sic035]"""
import sys, json, csv, itertools, pathlib
import cadquery as cq

OUT = pathlib.Path(__file__).resolve().parent / "out"; OUT.mkdir(exist_ok=True)
VARIANT = sys.argv[1] if len(sys.argv) > 1 else "resin"
ID_MASTER = pathlib.Path(__file__).resolve().parent / "id_master_silvergrey.step"  # 银灰ID母版(存在则叠加校核)

P = {  # value, flag
 "lens_w":(50.0,"A"), "lens_h":(38.0,"A"), "bridge":(18.0,"A"),
 "rim_face":(4.0,"A"), "rim_depth":(5.0,"A"),
 "end_w":(10.0,"A"), "end_l":(12.0,"A"), "end_h":(12.5,"A"),
 "temple_len":(145.0,"A"), "temple_w":(6.5,"A"), "temple_h":(11.5,"A"), "wall":(0.8,"A"),
 "wg_t":({"resin":1.0,"sic075":0.75,"sic035":0.35}[VARIANT], "S/A"),
 "eng_x":(6.0,"A"), "eng_y":(7.0,"A"), "eng_z":(5.0,"A"),      # 含支架包络; 核心0.2cc(S)
 "pcbL_len":(40.0,"A"), "pcbR_len":(28.0,"A"), "pcb_w":(8.5,"A"), "pcb_stack":(2.4,"A"),
 "bat_len":(28.0,"A"), "bat_w":(9.0,"A"), "bat_t":(4.0,"A"),  # ~100mAh级
 "cam_xy":(6.5,"S"), "cam_d":(4.5,"A"), "led":(1.6,"A"),
 "spk_len":(12.0,"A"), "spk_t":(3.5,"A"), "spk_h":(8.0,"A"),
 "ear_bend_y":(-107.0,"A"), "min_gap":(0.30,"A"),
}
v = lambda k: P[k][0]
TR90 = 1.00                                   # g/cm3 Grilamid TR90 ISO1183 (S)
WG_MASS = {"resin":4.0, "sic075":3.795, "sic035":1.98}[VARIANT]   # g/片 (S)

def box(x0,x1,y0,y1,z0,z1):
    return cq.Workplane("XY").box(x1-x0,y1-y0,z1-z0,centered=False).translate((x0,y0,z0)).val()

def shell(x0,x1,y0,y1,z0,z1,w,open_front=False,open_back=False):
    inner = box(x0+w,x1-w, y0-1 if open_back else y0+w, y1+1 if open_front else y1-w, z0+w,z1-w)
    return box(x0,x1,y0,y1,z0,z1).cut(inner)

parts = []   # name, shape|None, mass_g, flag, kind(shell|comp|optic|massonly), side
def add(n,s,m,f,k,side): parts.append(dict(name=n,shape=s,mass=m,flag=f,kind=k,side=side))

hw = v("bridge")/2 + v("lens_w") + v("rim_face")
add("bridge", box(-v("bridge")/2,v("bridge")/2,0,v("rim_depth"),v("lens_h")/2-4,v("lens_h")/2), None,"S*V","shell","C")
for side, sx in (("L",-1),("R",1)):
    cx = sx*(v("bridge")/2+v("lens_w")/2)
    ow, oh = v("lens_w")+2*v("rim_face"), v("lens_h")+2*v("rim_face")
    rim = box(cx-ow/2,cx+ow/2,0,v("rim_depth"),-oh/2,oh/2).cut(
          box(cx-v("lens_w")/2,cx+v("lens_w")/2,-1,v("rim_depth")+1,-v("lens_h")/2,v("lens_h")/2))
    add(f"rim_{side}", rim, None, "S*V", "shell", side)
    i = 0.35
    add(f"waveguide_{side}", box(cx-v("lens_w")/2+i,cx+v("lens_w")/2-i,
        v("rim_depth")/2-v("wg_t")/2, v("rim_depth")/2+v("wg_t")/2, -v("lens_h")/2+i, v("lens_h")/2-i),
        WG_MASS, "S", "optic", side)
    ex = sx*(hw+v("end_w")/2)
    add(f"endpiece_{side}", shell(ex-v("end_w")/2,ex+v("end_w")/2,-v("end_l"),v("rim_depth"),
        -v("end_h")/2,v("end_h")/2,v("wall"),open_back=True), None,"S*V","shell",side)
    ty1 = -v("end_l"); ty0 = ty1 - v("temple_len")
    add(f"temple_{side}", shell(ex-v("temple_w")/2,ex+v("temple_w")/2,ty0,ty1,
        -v("temple_h")/2,v("temple_h")/2,v("wall"),open_front=True), None,"S*V","shell",side)
    # 光机(端件内, 后置对准耦入区)
    ey0 = -v("end_l")+v("wall")+0.5
    add(f"light_engine_{side}", box(ex-v("eng_x")/2,ex+v("eng_x")/2,ey0,ey0+v("eng_y"),
        -v("eng_z")/2,v("eng_z")/2), 0.5+0.6, "S+A", "comp", side)
    if side == "L":   # 相机 + 隐私LED(硬连相机供电, 防篡改检测)
        cy1 = v("rim_depth")-v("wall")
        add("camera_L", box(ex-v("cam_xy")/2,ex+v("cam_xy")/2,cy1-v("cam_d"),cy1,
            -v("cam_xy")/2,v("cam_xy")/2), 0.60, "A", "comp", side)
        lz0 = v("cam_xy")/2 + v("min_gap")
        add("privacy_led_L", box(ex-v("led")/2,ex+v("led")/2,cy1-1.0,cy1,lz0,lz0+v("led")),
            0.10, "A", "comp", side)
    # FPC 跨铰链
    fx = ex - sx*1.9
    add(f"fpc_{side}", box(fx-0.075,fx+0.075,ty1-6.0,ey0-0.4,-2.5,2.5), 0.30, "A", "comp", side)
    pl = v("pcbL_len") if side=="L" else v("pcbR_len")
    py1 = ty1-2.0; py0 = py1-pl
    add(f"pcb_{side}", box(ex-v("pcb_stack")/2,ex+v("pcb_stack")/2,py0,py1,-v("pcb_w")/2,v("pcb_w")/2),
        2.60 if side=="L" else 1.40, "A", "comp", side)
    by1 = py0-2.0; by0 = by1-v("bat_len")
    add(f"battery_{side}", box(ex-v("bat_t")/2,ex+v("bat_t")/2,by0,by1,-v("bat_w")/2,v("bat_w")/2),
        2.50, "A(2-3g S)", "comp", side)
    sy1 = by0-2.0
    add(f"speaker_{side}", box(ex-v("spk_t")/2,ex+v("spk_t")/2,sy1-v("spk_len"),sy1,
        -v("spk_h")/2,v("spk_h")/2), 0.90, "A", "comp", side)
    for n,m in (("hinge",0.60),("graphite_spreader",0.30)):
        add(f"{n}_{side}", None, m, "A", "massonly", side)
for n,m in (("mics_x4",0.20),("nose_pads",0.80),("adhesive_screws_gaskets",1.00),
            ("touch_hall_pogo",0.40),("silvergrey_finish",0.30)):
    add(n, None, m, "A", "massonly", "C")

# ---- 质量 ----
for p in parts:
    if p["mass"] is None: p["mass"] = p["shape"].Volume()/1000.0*TR90
total = sum(p["mass"] for p in parts)
side_m = {s: sum(p["mass"] for p in parts if p["side"]==s) for s in "LRC"}

# ---- 空间校核 ----
geo = [p for p in parts if p["shape"] is not None]
issues = []
for a,b in itertools.combinations(geo,2):
    if a["kind"]=="shell" and b["kind"]=="shell": continue
    iv = a["shape"].intersect(b["shape"]).Volume()
    if iv > 1e-6: issues.append(("INTERFERENCE",a["name"],b["name"],round(iv,4)))
    elif a["kind"]!="shell" and b["kind"]!="shell" and a["side"]==b["side"]:
        d = a["shape"].distance(b["shape"])
        if d < v("min_gap"): issues.append(("GAP<min",a["name"],b["name"],round(d,3)))
for p in geo:
    if p["kind"]=="comp" and p["name"].startswith(("speaker","battery","pcb")):
        y_min = p["shape"].BoundingBox().ymin
        if y_min < v("ear_bend_y"): issues.append(("PAST_EAR_BEND",p["name"],"",round(y_min,2)))

res = dict(variant=VARIANT, total_g=round(total,2), reserve_10pct_g=round(total*1.10,2),
           pass_50g=total*1.10<=50.0, pass_40g_no_reserve=total<=40.0,
           side_g={k:round(x,2) for k,x in side_m.items()},
           LR_imbalance_g=round(side_m["L"]-side_m["R"],2), issues=issues,
           assumptions={k:f for k,(_,f) in P.items()})
(OUT/f"evt1_check_{VARIANT}.json").write_text(json.dumps(res,indent=2,ensure_ascii=False))
with open(OUT/f"mass_budget_{VARIANT}.csv","w",newline="") as fh:
    w = csv.writer(fh); w.writerow(["part","side","mass_g","flag"])
    for p in parts: w.writerow([p["name"],p["side"],round(p["mass"],3),p["flag"]])

assy = cq.Assembly(name=f"ZY_EVT1_{VARIANT}")
COL = {"shell":cq.Color(0.75,0.76,0.78,1),"optic":cq.Color(0.6,0.8,1,0.4),"comp":cq.Color(0.2,0.6,0.3,1)}
for p in geo: assy.add(cq.Workplane().add(p["shape"]), name=p["name"], color=COL[p["kind"]])
if ID_MASTER.exists():
    assy.add(cq.importers.importStep(str(ID_MASTER)), name="ID_master_ref", color=cq.Color(1,0,0,0.15))
(assy.export if hasattr(assy,"export") else assy.save)(str(OUT/f"ZY_EVT1_{VARIANT}.step"))
print(json.dumps({k:res[k] for k in ("total_g","reserve_10pct_g","pass_50g","LR_imbalance_g")}))
sys.exit(1 if any(i[0]=="INTERFERENCE" for i in issues) else 0)
