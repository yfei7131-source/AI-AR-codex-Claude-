import json, random
rnd=random.Random(7)
def uid():
    h="%032x"%rnd.getrandbits(128); return "%s-%s-4%s-a%s-%s"%(h[:8],h[8:12],h[13:16],h[17:20],h[20:32])
def nc(name,cl,tw,vd,vdr,dpw=0.2,dpg=0.15):
    return {"bus_width":12,"clearance":cl,"diff_pair_gap":dpg,"diff_pair_via_gap":0.25,"diff_pair_width":dpw,"line_style":0,
            "microvia_diameter":0.3,"microvia_drill":0.1,"name":name,"pcb_color":"rgba(0, 0, 0, 0.000)",
            "schematic_color":"rgba(0, 0, 0, 0.000)","track_width":tw,"via_diameter":vd,"via_drill":vdr,"wire_width":6}
pro={"meta":{"filename":"evt0_core.kicad_pro","version":1},
 "net_settings":{"meta":{"version":3},
  "classes":[nc("Default",0.15,0.15,0.5,0.25), nc("Power",0.2,0.4,0.6,0.3), nc("USB",0.15,0.2,0.5,0.25,0.2,0.15), nc("CamClk",0.2,0.15,0.5,0.25)],
  "netclass_patterns":[{"netclass":"Power","pattern":p} for p in ["VBUS","VSYS","VBAT","VBAT_CONN","3V3","CAM_2V8","CAM_1V2","CAM_DVDD","CAM_DOVDD","GND"]]
   +[{"netclass":"USB","pattern":"USB_D*"},{"netclass":"CamClk","pattern":"CAM_XCLK*"},{"netclass":"CamClk","pattern":"CAM_PCLK*"},{"netclass":"CamClk","pattern":"DISP_CLK"}]},
 "libraries":{"pinned_footprint_libs":[],"pinned_symbol_libs":["AIAR"]},
 "sheets":[], "text_variables":{"REV":"R0"}}
json.dump(pro,open("evt0_core.kicad_pro","w"),indent=2)

layers=[(0,"F.Cu","signal",None),(1,"In1.Cu","power",None),(2,"In2.Cu","power",None),(31,"B.Cu","signal",None),
 (32,"B.Adhes","user","B.Adhesive"),(33,"F.Adhes","user","F.Adhesive"),(34,"B.Paste","user",None),(35,"F.Paste","user",None),
 (36,"B.SilkS","user","B.Silkscreen"),(37,"F.SilkS","user","F.Silkscreen"),(38,"B.Mask","user",None),(39,"F.Mask","user",None),
 (40,"Dwgs.User","user","User.Drawings"),(41,"Cmts.User","user","User.Comments"),(42,"Eco1.User","user","User.Eco1"),
 (43,"Eco2.User","user","User.Eco2"),(44,"Edge.Cuts","user",None),(45,"Margin","user",None),(46,"B.CrtYd","user","B.Courtyard"),
 (47,"F.CrtYd","user","F.Courtyard"),(48,"B.Fab","user",None),(49,"F.Fab","user",None)]
L="\n".join('    (%d "%s" %s%s)'%(n,a,t,' "%s"'%u if u else "") for n,a,t,u in layers)
W,H=50.0,70.0; X0,Y0=100.0,60.0
def line(x1,y1,x2,y2,layer,w=0.1):
    return '  (gr_line (start %g %g) (end %g %g) (stroke (width %g) (type default)) (layer "%s") (uuid "%s"))'%(x1,y1,x2,y2,w,layer,uid())
def text(t,x,y,layer="Cmts.User",s=1.2):
    return '  (gr_text "%s" (at %g %g) (layer "%s") (uuid "%s") (effects (font (size %g %g) (thickness 0.15)) (justify left bottom)))'%(t,x,y,layer,uid(),s,s)
g=[line(X0,Y0,X0+W,Y0,"Edge.Cuts"),line(X0+W,Y0,X0+W,Y0+H,"Edge.Cuts"),line(X0+W,Y0+H,X0,Y0+H,"Edge.Cuts"),line(X0,Y0+H,X0,Y0,"Edge.Cuts")]
# antenna keep-out marker (module antenna overhangs top edge): drawn on Dwgs.User as guidance
ax0,ax1=X0+16,X0+34
g+=[line(ax0,Y0,ax1,Y0,"Dwgs.User",0.15),line(ax1,Y0,ax1,Y0+7,"Dwgs.User",0.15),line(ax1,Y0+7,ax0,Y0+7,"Dwgs.User",0.15),line(ax0,Y0+7,ax0,Y0,"Dwgs.User",0.15)]
g+=[text("U1 antenna zone: no copper on any layer, module antenna at board edge",X0+W+2,Y0+3),
    text("EVT-0 core verification board 50x70mm, 4L 1.0mm. Outline + guidance only.",X0,Y0-6),
    text("NO footprints placed yet: run 'Update PCB from Schematic' after ERC passes in KiCad.",X0,Y0-3.5),
    text("J1 USB-C: bottom edge centre. J3 camera FPC: left edge. J2 battery: right edge.",X0,Y0+H+3),
    text("Stackup/rules: hardware/h03/H03_STACKUP_AND_RULES.md, evt0_core.kicad_dru",X0,Y0+H+5.5)]
pcb='''(kicad_pcb (version 20240108) (generator "pcbnew") (generator_version "8.0")
  (general (thickness 1.0) (legacy_teardrops no))
  (paper "A4")
  (title_block (title "AI/AR Glasses V1.0 - EVT-0 Core Verification Board") (date "2026-11-11") (rev "R0") (comment 1 "H03 shell: outline only - DRC NOT RUN"))
  (layers
%s
  )
  (setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))
  (net 0 "")
%s
)
'''%(L,"\n".join(g))
open("evt0_core.kicad_pcb","w").write(pcb)
dru='''(version 1)
# EVT-0 core board custom rules (KiCad 8). Targets a standard low-cost 4-layer process
# (min trace/space 0.1/0.1 mm capability; design to 0.127/0.127; min drill 0.25 mm). Confirm with chosen fab in H04.
(rule "USB2 diff pair width/gap (90R, verify with fab stackup calculator)"
  (condition "A.NetClass == 'USB'")
  (constraint track_width (min 0.18) (opt 0.2) (max 0.25))
  (constraint diff_pair_gap (min 0.13) (opt 0.15) (max 0.2)))
(rule "USB2 diff pair skew"
  (condition "A.NetClass == 'USB'")
  (constraint skew (max 1.0)))
(rule "Camera/display clocks keep-away from other signals"
  (condition "A.NetClass == 'CamClk' && B.NetClass != 'CamClk' && B.NetClass != 'Power'")
  (constraint clearance (min 0.3)))
(rule "Power traces minimum width"
  (condition "A.NetClass == 'Power'")
  (constraint track_width (min 0.3)))
(rule "Via drill minimum"
  (constraint hole_size (min 0.25)))
(rule "Copper to board edge"
  (constraint edge_clearance (min 0.3)))
'''
open("evt0_core.kicad_dru","w").write(dru)