#!/usr/bin/env python3
"""Compute a partial EVT-1 placement candidate from saved native pad readback.

Only exact system Devices whose native pad-set audit passed are candidates.
No package copper is authored for missing/antenna/BM28/nRF/JBD/passive parts.
The 0.20 mm component-bbox clearance is a conservative candidate metric, not a
vendor courtyard qualification or proof that a complete assembly is routable.
"""
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parent
OUT = ROOT / 'layout'
MM = 39.37007874015748
GAP = 0.20
BOARD = {
    'M-MAIN-L': {'doc': '8fbc3cae65886fe5', 'length': 46.0,
                 'polygon': [(0,0),(0,46),(5.8,46),(5.8,14),(8.2,14),(8.2,4.2),(5.8,4.2),(5.8,0)]},
    'M-OPT-BRIDGE': {'doc': '9ce45f14cb79dc9d', 'length': 22.0,
                     'polygon': [(0,0),(0,22),(4.2,22),(4.2,0)]},
    'M-AUD-R': {'doc': '1db01a36f669a47a', 'length': 34.0,
                'polygon': [(0,0),(0,34),(5.2,34),(5.2,0)]},
}
CRITICAL_RESERVES = {
    'M-MAIN-L': ['ANT1','J_CAM','J_BTB_L','J_CHG','R_SENSE','U7_INA','TP_BAT_L_P','TP_BAT_L_N','TP_NTC_L'],
    'M-OPT-BRIDGE': ['J_DISP_L','J_DISP_R','J_BRIDGE_IN','U6_OPT_AVDD'],
    'M-AUD-R': ['ANT2_BLE','U11_BLE','J_BTB_R','J_CHG_R','TP_BAT_R_P','TP_BAT_R_N','TP_NTC_R','TP_SWD_R','Y2_BLE'],
}
FIXED = {'U1_HOST': (4.10,9.00,'TOP',180), 'U2_FPGA': (2.10,9.50,'TOP',0)}
PRIORITY = ['U1_HOST','U2_FPGA','Y1_OSC','U9_IMU','MK1_L','MK2_C','MK3_R','U10_AMP_L','U10_AMP_R','U11_BLE']

def load_csv(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))

def number(value):
    try: return float(value)
    except (TypeError,ValueError): return None

def inside(point, polygon):
    x,y = point
    result = False
    for i,(x1,y1) in enumerate(polygon):
        x2,y2 = polygon[(i+1)%len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            result = not result
    return result

def bbox_at(item,x,y,rotation=None):
    rot = item['rotation'] if rotation is None else rotation
    w,h = (item['bboxWidthMm'],item['bboxHeightMm']) if rot % 180 == 0 else (item['bboxHeightMm'],item['bboxWidthMm'])
    return {'minX':x-w/2,'maxX':x+w/2,'minY':y-h/2,'maxY':y+h/2,'width':w,'height':h}

def overlap(a,b,gap=GAP):
    return a['minX'] < b['maxX']+gap and a['maxX'] > b['minX']-gap and a['minY'] < b['maxY']+gap and a['maxY'] > b['minY']-gap

def legal(item,x,y,layer,board,occupied,reservations,rotation=None):
    box = bbox_at(item,x,y,rotation)
    if min(box['minX'],box['minY']) < 0 or box['maxY'] > board['length']:
        return None
    polygon = board['polygon']
    probes = [(box['minX'],box['minY']),(box['minX'],box['maxY']),(box['maxX'],box['minY']),(box['maxX'],box['maxY']),
              ((box['minX']+box['maxX'])/2,box['minY']),((box['minX']+box['maxX'])/2,box['maxY']),
              (box['minX'],(box['minY']+box['maxY'])/2),(box['maxX'],(box['minY']+box['maxY'])/2)]
    if not all(inside(p,polygon) for p in probes):
        return None
    if any(overlap(box,other['bbox']) for other in occupied if other['layer']==layer):
        return None
    if any(overlap(box,r['bbox']) for r in reservations if layer in r['layers']):
        return None
    return box

def reserve(ref,bom):
    w,h = number(bom.get('Body_Width_X_mm')),number(bom.get('Body_Length_Y_mm'))
    x,y = number(bom.get('Center_X_mm')),number(bom.get('Center_Y_mm'))
    if None in (w,h,x,y): return None
    side = bom.get('Side','TOP')
    layers = ['TOP','BOTTOM'] if side not in ('TOP','BOTTOM') else [side]
    return {'ref':ref,'kind':'UNQUALIFIED_MECHANICAL_ENVELOPE','source':'effective_bom.csv nominal body; no copper authored',
            'center':{'x':x,'y':y},'layers':layers,'bbox':{'minX':x-w/2,'maxX':x+w/2,'minY':y-h/2,'maxY':y+h/2,'width':w,'height':h},
            'status':'BLOCKED' if ref.startswith(('J_','ANT','U11','Y2')) else 'UNVERIFIED'}

def pad_vector(audit,pad_number,rotation=0):
    component = next(c for c in audit['result']['components'] if c['primitiveId']==audit_entry['primitiveId'])
    bbox = component['bbox']
    cx,cy = (bbox['minX']+bbox['maxX'])/2,(bbox['minY']+bbox['maxY'])/2
    pad = next(p for p in component['pads'] if p['padNumber']==pad_number)
    x,y = (pad['x']-cx)/MM,(pad['y']-cy)/MM
    angle = math.radians(rotation)
    return (x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plan_bytes=(ROOT/'evidence/native-library/device-plan.json').read_bytes()
    pad_bytes=(ROOT/'evidence/pad-audit/native-pad-audit.json').read_bytes()
    fresh_bytes=(ROOT/'evidence/pad-audit/audit-pads-fresh.json').read_bytes()
    plan=json.loads(plan_bytes)
    audit_report=json.loads(pad_bytes)
    fresh=json.loads(fresh_bytes)
    boms={r['Item_ID']:r for r in load_csv(PACKAGE/'Inputs/effective_bom.csv')}
    audits={a['device']['deviceUuid']:a for a in audit_report['devices'] if a['pinPadSetStatus']=='PASS'}
    instances=[]
    for p in plan['parts']:
        if p['sourceKind']!='EXACT_SYSTEM_SYMBOL_PIN_SET_PASS': continue
        audit=audits.get(p['device']['deviceUuid'])
        if not audit: continue
        bom=boms[p['bomLine']]
        bb=audit['bbox']
        side=bom['Side'] if bom['Side'] in ('TOP','BOTTOM') else 'BOTTOM'
        x,y=number(bom['Center_X_mm']),number(bom['Center_Y_mm'])
        if p['sourceReference'] in FIXED:
            x,y,side,rotation=FIXED[p['sourceReference']]
        else:
            rotation=0
        instances.append({'board':p['board'],'ref':p['cadReference'],'sourceRef':p['sourceReference'],'mpn':p['mpn'],
            'device':p['device'],'bomLine':p['bomLine'],'auditReference':audit['auditReference'],
            'auditPrimitiveId':audit['primitiveId'],'bboxWidthMm':(bb['maxX']-bb['minX'])/MM,'bboxHeightMm':(bb['maxY']-bb['minY'])/MM,
            'requestedCenter':{'x':x,'y':y},'preferredLayer':side,'sourceSide':bom['Side'],'rotation':rotation,
            'pins':p['pins'],'schematicBinding':'UNBOUND_CONTROLLED_NETLIST_CANDIDATE',
            'landPatternQualification':'UNVERIFIED','nativePadSetStatus':'PASS'})
    result={}
    for board,board_info in BOARD.items():
        candidates=[i for i in instances if i['board']==board]
        by_source={i['sourceRef']:i for i in candidates}
        reservations=[]
        for ref in CRITICAL_RESERVES[board]:
            if ref in by_source: continue
            bom=next((b for b in boms.values() if b['RefDes']==ref and b['Board_Zone']==board),None)
            if not bom:
                reservations.append({'ref':ref,'status':'BLOCKED_MISSING_NOMINAL_ENVELOPE','layers':[]})
                continue
            r=reserve(ref,bom)
            reservations.append(r or {'ref':ref,'status':'BLOCKED_UNPLACED_NOMINAL_ENVELOPE','layers':[]})
        if board=='M-MAIN-L':
            reservations.append({'ref':'RF_FRONT_0_TO_4P2','kind':'RF_NO_COMPONENT_ZONE','layers':['TOP','BOTTOM'],
                'bbox':{'minX':0,'maxX':5.8,'minY':0,'maxY':4.2},'status':'UNVERIFIED'})
        if board=='M-AUD-R':
            reservations.append({'ref':'RF_FRONT_0_TO_4P0','kind':'RF_NO_COMPONENT_ZONE','layers':['TOP','BOTTOM'],
                'bbox':{'minX':0,'maxX':5.2,'minY':0,'maxY':4.0},'status':'UNVERIFIED'})
        # Reserve full-width top optical/FPC corridors in addition to connector bodies.
        if board=='M-OPT-BRIDGE':
            for r in list(reservations):
                if r.get('ref') in ('J_DISP_L','J_DISP_R'):
                    b=r['bbox']
                    reservations.append({'ref':r['ref']+'_FPC_CORRIDOR','kind':'OPTICAL_FPC_ASSEMBLY_CORRIDOR','layers':['TOP'],
                        'bbox':{'minX':0,'maxX':4.2,'minY':b['minY']-0.32,'maxY':b['maxY']+0.32},'status':'UNVERIFIED'})
        if board=='M-OPT-BRIDGE' and 'Y1_OSC' in by_source and 'U2_FPGA' in by_source:
            # Preserve the clock search region before filling opposite-side logic.
            clock=by_source['Y1_OSC']; fpga=by_source['U2_FPGA']
            fx,fy=FIXED['U2_FPGA'][:2]
            reservations.append({'ref':'Y1_CLOCK_SEARCH_RESERVE','kind':'CLOCK_OPPOSITE_SIDE_CANDIDATE_REGION','layers':['BOTTOM'],
                'bbox':{'minX':fx-clock['bboxWidthMm']/2,'maxX':fx+clock['bboxWidthMm']/2,
                        'minY':fy-clock['bboxHeightMm']/2,'maxY':fy+clock['bboxHeightMm']/2},'status':'UNVERIFIED'})
        placed=[];failed=[]
        ordered=sorted(candidates,key=lambda i: PRIORITY.index(i['sourceRef']) if i['sourceRef'] in PRIORITY else 100)
        # U2 must precede Y1; Y1 then gets its own pin-distance optimization.
        for inst in ordered:
            if inst['sourceRef']=='Y1_OSC': continue
            pref=inst['requestedCenter']
            px=pref['x'] if pref['x'] is not None else board_info['polygon'][-1][0]/2
            py=pref['y'] if pref['y'] is not None else board_info['length']/2
            fixed=inst['sourceRef'] in FIXED
            candidates_xy=[(px,py)] if fixed else [(px,py)]
            if not fixed:
                for radius in range(1,61):
                    d=radius*0.20
                    for step in range(-radius,radius+1):
                        q=step*0.20
                        candidates_xy.extend([(px+d,py+q),(px-d,py+q),(px+q,py+d),(px+q,py-d)])
                for yi in range(int(board_info['length']*2)+1):
                    for xi in range(17):
                        candidates_xy.append((xi*0.5+0.25,yi*0.5+0.25))
            seen=set();choice=None
            search_layers=[inst['preferredLayer']] if inst['sourceSide'] in ('TOP','BOTTOM') else ['BOTTOM','TOP']
            search_rotations=[inst['rotation']] if fixed else [0,90]
            for x,y in candidates_xy:
                for layer in search_layers:
                    for rotation in search_rotations:
                        key=(round(x,4),round(y,4),layer,rotation)
                        if key in seen: continue
                        seen.add(key)
                        box=legal(inst,x,y,layer,board_info,placed,reservations,rotation)
                        if not box: continue
                        score=math.hypot(x-px,y-py)+(0 if layer==inst['preferredLayer'] else 0.25)+(0 if rotation==inst['rotation'] else 0.01)
                        if choice is None or score<choice[0]:
                            choice=(score,x,y,box,layer,rotation)
                        if fixed or inst['sourceSide'] in ('TOP','BOTTOM'): break
                    if choice and (fixed or inst['sourceSide'] in ('TOP','BOTTOM')): break
                if choice and (fixed or inst['sourceSide'] in ('TOP','BOTTOM')): break
            if not choice:
                failed.append({'ref':inst['ref'],'sourceRef':inst['sourceRef'],'status':'BLOCKED_NO_LEGAL_CANDIDATE_IN_SEARCH',
                               'reason':'Fixed anchor conflict or bounded 0.20 mm full-bbox search found no legal position.'})
                continue
            _,x,y,box,layer,rotation=choice
            inst.update({'center':{'x':round(x,5),'y':round(y,5)},'layer':layer,'rotation':rotation,'bbox':box,
                         'placementStatus':'CANDIDATE_OFFLINE','displacementMm':None if fixed else round(math.hypot(x-px,y-py),5)})
            placed.append(inst)
        if board=='M-OPT-BRIDGE' and 'Y1_OSC' in by_source and 'U2_FPGA' in by_source:
            osc=by_source['Y1_OSC'];fpga=by_source['U2_FPGA']
            global audit_entry
            audit_entry=next(a for a in audits.values() if a['primitiveId']==fpga['auditPrimitiveId'])
            b3=pad_vector(fresh,'B3',fpga['rotation'])
            target=(fpga['center']['x']+b3[0],fpga['center']['y']+b3[1])
            audit_entry=next(a for a in audits.values() if a['primitiveId']==osc['auditPrimitiveId'])
            best=None
            for layer in ('TOP','BOTTOM'):
                for rot in (0,90,180,270):
                    pv=pad_vector(fresh,'3',rot)
                    for xi in range(85):
                        x=xi*0.05
                        for yi in range(111,271):
                            y=yi*0.05
                            box=legal(osc,x,y,layer,board_info,placed,[r for r in reservations if r.get('ref')!='Y1_CLOCK_SEARCH_RESERVE'],rot)
                            if not box: continue
                            distance=math.hypot(x+pv[0]-target[0],y+pv[1]-target[1])
                            candidate=(distance,rot,x,y,layer,box)
                            if best is None or candidate[:5]<best[:5]: best=candidate
            if best:
                distance,rot,x,y,layer,box=best
                osc.update({'center':{'x':x,'y':y},'layer':layer,'rotation':rot,'bbox':box,'placementStatus':'CANDIDATE_OFFLINE',
                            'fpgaB3ToOscPin3CenterDistanceMm':round(distance,5),'clockOptimization':'Minimize measured pad-center distance; opposite-side via and SI/startup remain UNVERIFIED.'})
                placed.append(osc)
            else:
                direct=bbox_at(osc,2.1,9.5,0)
                blockers=[p['sourceRef'] for p in placed if p['layer']=='BOTTOM' and overlap(direct,p['bbox'])]
                reserved_blockers=[r['ref'] for r in reservations if 'BOTTOM' in r['layers'] and r.get('ref')!='Y1_CLOCK_SEARCH_RESERVE' and overlap(direct,r['bbox'])]
                failed.append({'ref':osc['ref'],'sourceRef':osc['sourceRef'],'status':'BLOCKED_NO_LEGAL_CLOCK_CANDIDATE',
                               'directBottomBbox':direct,'directBottomComponentBlockers':blockers,'directBottomReservationBlockers':reserved_blockers})
        result[board]={'pcbUuid':board_info['doc'],'outlinePolygonMm':board_info['polygon'],'scope':'PARTIAL_EXACT_DEVICE_CANDIDATE_NOT_COMPLETE_LAYOUT',
            'minimumCandidateBboxGapMm':GAP,'placements':placed,'failedPlacements':failed,'reservations':reservations,
            'requiredButNotPlaced':[p['sourceReference'] for p in plan['parts'] if p['board']==board and p['sourceKind']!='EXACT_SYSTEM_SYMBOL_PIN_SET_PASS'],
            'unverified':['pin-1/package orientation against vendor top view','supplier courtyard/mask/paste','complete peripheral placement','FPC/shell/optical/battery/acoustic fit','routability and return paths']}
    output={'status':'CANDIDATE_PARTIAL_NOT_FOR_FAB','sourceSha256':{'devicePlan':hashlib.sha256(plan_bytes).hexdigest(),
        'nativePadAudit':hashlib.sha256(pad_bytes).hexdigest(),'freshPadReadback':hashlib.sha256(fresh_bytes).hexdigest()},
        'boards':result,'counts':{'candidate':sum(len(b['placements']) for b in result.values()),'failed':sum(len(b['failedPlacements']) for b in result.values())},
        'systemModules':[{ 'ref':r['RefDes'],'bodyMm':[r['Body_Width_X_mm'],r['Body_Length_Y_mm'],r['Body_Height_Z_mm']],
            'positionMm':[r['Center_X_mm'],r['Center_Y_mm']],'status':r['Verification_Status']} for r in boms.values() if r['Board_Zone'].startswith(('OPTICAL_BAY','BATTERY_BAY'))],
        'architecture':{'binocularTransparentAR':True,'assemblyMassTargetG':40,'massAchieved':False,'routingAuthorized':False}}
    (OUT/'candidate-placement-plan.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output['counts'],indent=2))
    for board,b in result.items(): print(board,'candidate',len(b['placements']),'failed',len(b['failedPlacements']),'reservations',len(b['reservations']))

if __name__=='__main__': main()
