"""Regenerate the four-layer EVT-0 lab placement and the partial power routing.

Run with KiCad 10's bundled Python. Reads a fresh schematic netlist, checks every
physical pad against it, then writes a board. Output still requires signal layout.
"""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pcbnew as k


HERE = Path(__file__).resolve().parents[1]
MM = k.FromMM
# x/y from upper-left board corner, rotation in KiCad degrees.
P = {
    'U1':(25,12.8,0),'C9':(14,8.81,180),'C10':(11,8.81,180),
    'R11':(13,11,180),'C11':(10,11,180),'R12':(30,29,0),
    'SW1':(10,32,0),'SW2':(20,32,0),
    'J1':(25,66.1,0),'U2':(24.5,58.5,90),'D1':(30.5,59,90),
    'R1':(18.8,59,90),'R2':(20.9,59,90),
    'U3':(34,55,0),'C1':(34.75,51.8,90),'C2':(30.1,55.25,180),
    'C3':(37.9,55.25,0),'R3':(31,57.5,0),'R4':(38,53.1,0),
    'R5':(31.4,52,180),'R6':(32.5,50.2,90),'R7':(36,60,0),
    'R36':(32.2,59.6,90),'D2':(36,62,0),'R28':(32.2,62.9,90),
    'J2':(46.65,63,90),'JP1':(41,62,0),
    'U4':(13,55,0),'C5':(9.7,54.05,180),'C6':(16,54.05,0),
    'C7':(17,51.4,90),'C8':(10.5,50.1,90),'R9':(40,46,0),
    'R10':(40,48,0),'C4':(37,46,0),'J3':(3.9,44,270),
    'U5':(13,41,0),'C12':(10,40.05,180),'C13':(16,40.05,0),
    'U6':(22,42,0),'C14':(19,41.05,180),'C15':(25,41.05,0),
    'Q2':(9.5,45.5,180),'Q3':(17.2,45.5,0),'R29':(14,46.7,0),
    'R13':(9,43,0),'R35':(13,44,0),'R16':(25,44,0),
    'R17':(20,47,0),'R18':(23,47,0),'C16':(6,55,0),
    'C17':(7.5,57,0),'C18':(7.5,59,0),'C19':(14,49,0),
    'C20':(18,49,0),'R19':(9.2,37.5,0),'R20':(12,37.5,0),
    'R21':(14.8,37.5,0),'R22':(17.6,37.5,0),'R23':(27,27,0),
    'R24':(3.1,32,90),'D3':(4.3,24,0),'R27':(8.4,27.6,0),
    'R33':(37.3,11.5,90),'R34':(39.5,11.5,90),'R15':(39.5,15,90),
    'J4':(47,9,0),'R14':(42.5,11.5,90),'J5':(47,41,0),
    'J6':(27,35,90),'J7':(30,40,90),'R30':(39,38.5,0),
    'R31':(39,40.5,0),
}
for i in range(1,12):
    P['TP'+str(i)] = (6+(i-1)%6*6.4, 52+(i-1)//6*6, 0)


def vec(x,y):
    return k.VECTOR2I(MM(x),MM(y))


def board_xy(x,y):
    return vec(100+x,60+y)


def netlist():
    cli = Path(sys.executable).with_name('kicad-cli.exe' if os.name=='nt' else 'kicad-cli')
    if not cli.is_file():
        cli = 'kicad-cli'
    with tempfile.TemporaryDirectory() as d:
        path = Path(d)/'net.xml'
        subprocess.run([cli,'sch','export','netlist','--format','kicadxml','-o',str(path),
                        str(HERE/'evt0_core.kicad_sch')],check=True)
        return ET.parse(path)


def create_board(components, nets, library):
    board = k.BOARD()
    board.SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(MM(1.0))
    tb = board.GetTitleBlock()
    tb.SetTitle('AI/AR V1 EVT-0 core verification board')
    tb.SetRevision('R3')
    tb.SetComment(0,'Partial power routing; open connections; not for fabrication')
    corners = [board_xy(*p) for p in [(0,0),(50,0),(50,70),(0,70)]]
    for a,b in zip(corners,corners[1:]+corners[:1]):
        edge = k.PCB_SHAPE(board)
        edge.SetShape(k.SHAPE_T_SEGMENT)
        edge.SetStart(a)
        edge.SetEnd(b)
        edge.SetWidth(MM(.1))
        edge.SetLayer(k.Edge_Cuts)
        board.Add(edge)
    nodes,infos = {},{}
    for n in nets:
        info = k.NETINFO_ITEM(board,n.get('name'))
        board.Add(info)
        infos[n.get('name')] = info
        for pin in n.findall('node'):
            nodes[pin.get('ref'),pin.get('pin')] = (info,pin)
    parts = {}
    if {c.get('ref') for c in components} != set(P):
        raise ValueError('Placement set differs from schematic')
    seen = set()
    for c in components:
        ref = c.get('ref')
        lib,name = c.findtext('footprint').split(':')
        f = k.FootprintLoad(str(library/(lib+'.pretty')),name)
        if not f:
            raise ValueError('Footprint missing: '+ref+' '+name)
        f.SetFPID(k.LIB_ID(lib,name))
        f.SetReference(ref)
        f.SetValue(c.findtext('value'))
        f.SetPath(k.KIID_PATH('/'+c.findtext('tstamps')))
        f.SetSheetname('evt0_core')
        f.SetSheetfile('evt0_core.kicad_sch')
        f.SetDNP(c.find("property[@name='dnp']") is not None)
        f.SetExcludedFromBOM(c.find("property[@name='exclude_from_bom']") is not None)
        for field in c.findall('fields/field'):
            if field.get('name') in ('Value','Footprint'):
                continue
            f.SetField(field.get('name'),field.text or '')
            f.GetField(field.get('name')).SetVisible(False)
        board.Add(f)
        x,y,deg = P[ref]
        if ref.startswith('TP'):
            f.Flip(f.GetPosition(),k.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(deg)
        f.SetPosition(board_xy(x,y))
        for pad in f.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            info,node = nodes[ref,num]
            pad.SetNet(info)
            pad.SetPinType(node.get('pintype',''))
            pad.SetPinFunction(node.get('pinfunction',''))
            seen.add((ref,num))
        parts[ref] = f
    if nodes.keys()-seen:
        raise ValueError('Unmapped pin(s): '+str(nodes.keys()-seen))
    return board,parts,infos


def plane(board,net,layer,name):
    zone = k.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetZoneName(name)
    zone.SetLocalClearance(MM(.25))
    zone.SetPadConnection(k.ZONE_CONNECTION_THT_THERMAL)
    zone.SetThermalReliefGap(MM(.25))
    zone.SetThermalReliefSpokeWidth(MM(.35))
    poly = zone.Outline()
    poly.NewOutline()
    # Full-width keep-back across antenna end, in addition to stock footprint RF rule area.
    for x,y in ((.35,6.4),(49.65,6.4),(49.65,69.65),(.35,69.65)):
        poly.Append(board_xy(x,y))
    board.Add(zone)


def power_fanout(board, parts, all_pads):
    # F.Cu short power connections and off-pad escapes into internal planes.
    # Keep J3/J4 unrouted until the two supplier interfaces are signed off.
    obstacles = []
    pads = []
    for ref,f in parts.items():
        for p in f.Pads():
            if p.IsOnLayer(k.F_Cu):
                obstacles.append((p.GetNetname(),p.GetEffectiveShape(k.F_Cu)))
                if p.GetNumber() and ref not in ('J3','J4'):
                    pads.append((ref,p))

    def clear(net,shape):
        return not any(k.SHAPE.Collide(shape,item,MM(.23)) for name,item in obstacles if name!=net)

    def segment(net,a,b):
        track = k.PCB_TRACK(board)
        track.SetNet(net)
        track.SetLayer(k.F_Cu)
        track.SetWidth(MM(.30))
        track.SetStart(a)
        track.SetEnd(b)
        board.Add(track)
        obstacles.append((net.GetNetname(),k.SHAPE_SEGMENT(a,b,MM(.30))))

    def within_board(p):
        return MM(100.8)<p.x<MM(149.2) and MM(66.8)<p.y<MM(129.2)

    local = {'/3V3','/GND','/VBUS','/VBAT','/VBAT_CONN','/VSYS','/CAM_2V8','/CAM_1V2','/CAM_3V3'}
    pairs = []
    for (ref,a),(other,b) in itertools.combinations(pads,2):
        if a.GetNetname() not in local or a.GetNetname()!=b.GetNetname():
            continue
        length = (a.GetPosition()-b.GetPosition()).EuclideanNorm()
        if MM(.1) < length < MM(8.5):
            pairs.append((length,ref,other,a,b))
    # Only join different local trees; leave long paths for a reviewed layout.
    groups = {}
    def root(pad):
        key = (pad.GetParentFootprint().GetReference(),pad.GetPosition().x,pad.GetPosition().y)
        while key in groups:
            key = groups[key]
        return key
    for _,_,_,a,b in sorted(pairs,key=lambda p:p[0]):
        if root(a)==root(b):
            continue
        start,end = a.GetPosition(),b.GetPosition()
        dx,dy = end.x-start.x,end.y-start.y
        diag = min(abs(dx),abs(dy))
        offset = k.VECTOR2I(diag*(1 if dx>=0 else -1),diag*(1 if dy>=0 else -1))
        for bend in (start+offset,end-offset):
            path = [start,bend,end] if bend!=start and bend!=end else [start,end]
            legs = list(zip(path,path[1:]))
            if all(clear(a.GetNetname(),k.SHAPE_SEGMENT(s,t,MM(.30))) for s,t in legs):
                for s,t in legs:
                    segment(a.GetNet(),s,t)
                groups[root(b)] = root(a)
                break
    # One via per connected surface island where possible. THT ground/power already hits the planes.
    escaped = {root(p) for _,p in pads if p.IsOnLayer(k.In1_Cu) and p.GetNetname() in ('/GND','/3V3')}
    for _,p in pads:
        net = p.GetNetname()
        if net not in ('/GND','/3V3') or root(p) in escaped:
            continue
        start = p.GetPosition()
        for dist,(dx,dy) in itertools.product((.95,1.35,1.85,2.4),
                ((-1,0),(1,0),(0,-1),(0,1),(1,1),(-1,-1),(1,-1),(-1,1))):
            at = start+vec(dx*dist,dy*dist)
            disk = k.SHAPE_CIRCLE(at,MM(.32))
            stub = k.SHAPE_SEGMENT(start,at,MM(.30))
            if not within_board(at) or not clear(net,disk) or not clear(net,stub):
                continue
            # No via-in-pad; retain tenting and drill-to-drill clearance.
            if any(k.SHAPE.Collide(disk,shape,MM(.15)) for _,shape in all_pads):
                continue
            segment(p.GetNet(),start,at)
            via = k.PCB_VIA(board)
            via.SetPosition(at)
            via.SetWidth(MM(.64))
            via.SetDrill(MM(.3))
            via.SetNet(p.GetNet())
            board.Add(via)
            obstacles.append((net,disk))
            all_pads.append((net,disk))
            escaped.add(root(p))
            break


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lib',type=Path,default=os.environ.get('KICAD10_FOOTPRINT_DIR') or
        Path(sys.executable).resolve().parents[1]/'share/kicad/footprints')
    parser.add_argument('--out',type=Path,default=HERE/'evt0_core.kicad_pcb')
    args = parser.parse_args()
    xml = netlist()
    board,parts,nets = create_board(xml.findall('components/comp'),xml.findall('nets/net'),args.lib)
    all_pads = [(p.GetNetname(),p.GetEffectiveShape(layer)) for f in parts.values() for p in f.Pads()
                for layer in (k.F_Cu,k.B_Cu) if p.IsOnLayer(layer)]
    power_fanout(board,parts,all_pads)
    plane(board,nets['/GND'],k.In1_Cu,'L2 ground return')
    plane(board,nets['/3V3'],k.In2_Cu,'L3 regulated 3V3')
    k.ZONE_FILLER(board).Fill(board.Zones())
    k.SaveBoard(str(args.out),board)
    print(f"{len(parts)} footprints; {len(list(board.GetTracks()))} tracks and vias; 2 filled planes")
