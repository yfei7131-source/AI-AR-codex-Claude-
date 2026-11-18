#!/usr/bin/env python3
"""Compile the EVT-1 electrical tables to three electrically separate KiCad projects."""

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


PACKAGE = Path(__file__).resolve().parents[1]
BASELINE = PACKAGE.parent / 'evt1-rev-d1-1-20261117/02_BOM_PINMAP_ICD_Blocked'
BOARD_PROJECTS = {
    'M-MAIN-L': ('evt1-main-left', 'Left temple | ESP32-S3, power and privacy'),
    'M-OPT-BRIDGE': ('evt1-optical-bridge', 'Bridge | FPGA, binocular links and AVDD interlock'),
    'M-AUD-R': ('evt1-audio-right', 'Right temple | nRF5340, audio and independent charger'),
}
FORMAT_VERSION = 20231120
GRID = 2.54
EXTERNAL = {'BAT_L', 'BAT_R', 'SPK_L', 'SPK_R'}
POWER_INHERITED = {
    'M-MAIN-L': {'1V8_FPGA_IO': 'J_BTB_L.P6, source U4_1V8F on the bridge',
                 'VBAT_R_RET': 'J_BTB_L.PWR1, protected right pack',
                 'VBAT_R_ISOLATED': 'Q_CHG_ISO_R conducts from protected right pack when enabled'},
    'M-OPT-BRIDGE': {'GND': 'J_BRIDGE_IN.PWR2, system return',
                     'VSYS': 'J_BRIDGE_IN.P2/P3, source LM66200 on left main board',
                     '1V8_SYS': 'J_BRIDGE_IN.P4/P5, source TPS62840 on left main board',
                     '1V2_FPGA_PLL': 'R_PLL supplies filtered core rail',
                     '1V8_FPGA_VPP': 'R_VPP supplies D4 from the inherited 1V8 FPGA IO rail; not NVCM programming voltage'},
    'M-AUD-R': {'GND': 'J_BTB_R.PWR2, system return',
                'VBUS_5V': 'J_BTB_R.P1, charging interface on left main board',
                '1V8_SYS': 'J_BTB_R.P4, source TPS62840 on left main board'},
}


def ident(*parts):
    """Allocate stable UUIDs so the KiCad files can be reproduced and diffed."""
    return str(uuid5(NAMESPACE_URL, 'evt1-native-eda-20261118/' + '/'.join(map(str, parts))))


def quoted(value):
    return json.dumps(str(value), ensure_ascii=False)


def coord(x):
    return format(x, '.4f').rstrip('0').rstrip('.') or '0'


def point(x, y):
    return f'{coord(x)} {coord(y)}'


def font(size=0.9, justify='', hidden=False):
    return (f'(effects (font (size {size} {size}))'
            f'{" (justify " + justify + ")" if justify else ""}'
            f'{" (hide yes)" if hidden else ""})')


def prop(key, value, x, y, *, size=0.9, hidden=False):
    return f'(property {quoted(key)} {quoted(value)} (at {point(x, y)} 0) {font(size, hidden=hidden)})'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'Expected at least one row for {path}')
    path.parent.mkdir(exist_ok=True, parents=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def save(path, text):
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_bytes(text.encode('utf-8'))


def input_tables():
    effective_netlist = PACKAGE / 'Inputs/effective_netlist.csv'
    effective_bom = PACKAGE / 'Inputs/effective_bom.csv'
    if effective_netlist.exists() != effective_bom.exists():
        raise ValueError('Both effective input tables are needed together')
    if effective_netlist.is_file():
        return read_csv(effective_netlist), read_csv(effective_bom)
    return read_csv(BASELINE / 'NETLIST_ELECTRICAL_CONNECTION_REV_D1_1.csv'), read_csv(BASELINE / 'BOM_V1_0_FROZEN.csv')


def natural(value):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', value)]


def local_net(row):
    # The D1.1 connector can carry these nets on the FPC without a copper
    # connection on its bridge footprint. Keep the local contact physically open.
    if row['Role'] == 'NC' or row['Note'].strip() == 'NC_TRUNK_PASS':
        return ''
    return row['Net']


def section(board, ref):
    if ref.startswith('J_'):
        return 'Harness and board interfaces'
    if board == 'M-MAIN-L':
        if any(word in ref for word in ('CAM', 'XREQ', 'INA', 'WIN', 'PRIV', 'LED', 'SCCB', 'R_SENSE', 'R_LIMIT', 'LDOVDD', 'LDO_AVDD', 'LDO_DOVDD', 'LDO_DVDD')):
            return 'Camera rails and privacy interlock'
        if any(word in ref for word in ('BAT', 'CHG', 'OR_', 'U4_OR', 'U3_L', 'ISO_GATE', 'ISO_PD', 'CHG_ISO', 'BB_', 'BK_', 'U4_BB', 'U4_1V8', 'VSET', 'L1_BB', 'L2_1V8', 'NTC')):
            return 'Battery, charger and DC conversion'
        if any(word in ref for word in ('PDM', 'AUD', 'AMP', 'SPK', 'MK1')):
            return 'Audio and digital translation'
        return 'ESP32-S3, USB and host interfaces'
    if board == 'M-OPT-BRIDGE':
        if 'AVDD' in ref or 'LDO_OPT' in ref:
            return 'Optical power supervisor and AVDD qualification'
        if any(word in ref for word in ('IMU', 'MK2', 'PRIV')):
            return 'Bridge sensors, microphone and privacy LED'
        if any(word in ref for word in ('DAMP', 'OPTCS')):
            return 'Independent optical-link termination'
        return 'FPGA, configuration and rail sequence'
    if any(word in ref for word in ('BAT', 'CHG', 'MUTE', 'U3_R', 'ISET', 'VSET', 'NTC')):
        return 'Right protected battery and independent charging'
    if any(word in ref for word in ('U11_BLE', 'NRF_', 'Y2_', 'ANT2', 'SWD')):
        return 'nRF5340, reference clock, RF and SWD'
    return 'Right audio and microphone'


def prefix(ref):
    if ref.startswith('NRF_C'):
        return 'C'
    if ref.startswith('NRF_L'):
        return 'L'
    if ref.startswith('D3_PRIV'):
        return 'D'
    return re.match(r'[A-Za-z]+', ref).group().upper()


def allocate_references(refs):
    """Preserve recognizable numeric IDs and allocate unambiguous schematic refs."""
    mapping = {}
    used = set()
    ordered = sorted(refs, key=natural)
    for ref in ordered:
        candidate = re.match(r'[A-Za-z]+\d+(?=_|$)', ref)
        if candidate and candidate.group() not in used:
            mapping[ref] = candidate.group()
            used.add(candidate.group())
    for ref in ordered:
        if ref in mapping:
            continue
        designator = prefix(ref)
        number = 1
        while f'{designator}{number}' in used:
            number += 1
        mapping[ref] = f'{designator}{number}'
        used.add(mapping[ref])
    return mapping


def compact(value, n):
    value = ' '.join(value.split())
    return value if len(value) <= n else value[:n-3] + '...'


def electrical_type(row, *, bonded_output=False, external=False):
    role = row['Role']
    device = row['RefDes']
    if device in {'U8_LS3','U8_LS4'} and row['Pin_Function'] == 'VREF2':
        # SCPS113O §8.1/§9.2: VREF2 is a 200k-fed analog bias. EN may be
        # actively clamped low by an open-drain output; no power flag here.
        return 'input'
    if external or device.startswith(('D', 'Q_', 'ANT', 'J_')):
        if device == 'J_CHG' and role == 'SRC':
            return 'power_out'
        return 'passive'
    if role == 'SRC':
        # Two bonded leads on one regulated output count as one native ERC source.
        return 'passive' if bonded_output else 'power_out'
    if role == 'SINK':
        return 'power_in'
    return {'DRV': 'output', 'DRV_OD': 'open_collector', 'RCV': 'input',
            'BIDIR': 'bidirectional', 'BIDIR_OD': 'bidirectional', 'BIDIR_FW': 'bidirectional',
            'BIDIR_CFG': 'bidirectional', 'BIDIR_DIRCTL': 'bidirectional', 'DRV_TRI_SLOT': 'tri_state',
            'NC': 'no_connect'}.get(role, 'passive')


@dataclass(frozen=True)
class Pin:
    number: str
    function: str
    kind: str
    x: float
    y: float
    side: str
    net: str


@dataclass
class Component:
    source: str
    cad: str
    part: str
    value: str
    metadata: dict
    pins: list
    top: float
    bottom: float
    half_width: float
    style: str
    native: bool = True
    dnp: bool = False

    @property
    def height(self):
        return self.top - self.bottom + 5 * GRID

    @property
    def libname(self):
        return f'{self.cad}_{self.source}'

    def library(self, namespace=''):
        included = 'yes' if self.native else 'no'
        hide_pin_names = self.style != 'block'
        prefix_line = '(pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))' if hide_pin_names else '(pin_names (offset 0.65))'
        name = namespace + self.libname
        out = [f'(symbol {quoted(name)} {prefix_line} (exclude_from_sim no) (in_bom {included}) (on_board {included})']
        if self.style == 'flag':
            out.append('(power)')
        out.extend(prop(key, value, 0, loc, hidden=hidden) for key, value, loc, hidden in [
            ('Reference', '#FLG' if self.style == 'flag' else prefix(self.source), self.top + 1.27, self.style == 'flag'),
            ('Value', self.libname, self.bottom - 1.27, False),
            ('Footprint', self.metadata.get('Footprint', ''), 0, True),
            ('Datasheet', self.metadata.get('Datasheet', ''), 0, True),
            ('Description', self.part, 0, True),
        ])
        graphics = self.graphics()
        out.append(f'(symbol {quoted(self.libname + "_0_1")} {graphics})')
        out.append(f'(symbol {quoted(self.libname + "_1_1")}')
        for p in self.pins:
            angle = 0 if p.side == 'L' else 180
            visible_name = compact(p.function, 34) if self.style == 'block' else '~'
            out.append(f'(pin {p.kind} line (at {point(p.x, p.y)} {angle}) (length {coord(GRID)}) '
                       f'(name {quoted(visible_name or "~")} {font(0.8)}) (number {quoted(p.number)} {font(0.75)}))')
        out.append('))')
        return '\n'.join(out)

    def graphics(self):
        def poly(*points, width=0.19):
            return ('(polyline (pts ' + ' '.join(f'(xy {point(x,y)})' for x, y in points) +
                    f') (stroke (width {width}) (type default)) (fill (type none)))')
        match self.style:
            case 'C':
                return ''.join((poly((-2.54, 0), (-0.55, 0)), poly((0.55, 0), (2.54, 0)),
                                poly((-0.55, -1.55), (-0.55, 1.55)), poly((0.55, -1.55), (0.55, 1.55))))
            case 'L':
                return ''.join(poly((x, 0), (x + 0.42, 1.02), (x + 0.85, 0)) for x in (-2.54, -1.69, -0.84, 0.01, 0.86, 1.71))
            case 'D':
                return ''.join((poly((-2.54, 0), (-1.24, 0)), poly((-1.24, -1.15), (-1.24, 1.15), (1.24, 0), (-1.24, -1.15)),
                                poly((1.24, -1.15), (1.24, 1.15)), poly((1.24, 0), (2.54, 0))))
            case 'TP':
                return poly((-2.54, 0), (-0.65, 0)) + '(circle (center 0 0) (radius 0.65) (stroke (width 0.23) (type default)) (fill (type none)))'
            case 'flag':
                return poly((-2.54, 0), (-1.27, 0), (0, 1.02), (1.27, 0), (0, -1.02), (-1.27, 0))
            case 'R':
                return '(rectangle (start -2.54 -0.85) (end 2.54 0.85) (stroke (width 0.19) (type default)) (fill (type none)))'
            case _:
                return (f'(rectangle (start {point(-self.half_width, self.top)}) (end {point(self.half_width, self.bottom)}) '
                        '(stroke (width 0.23) (type default)) (fill (type background)))')


def component(cad, ref, rows, bom, footprint):
    functions = [r['Pin_Function'].strip() for r in rows]
    part = bom['MPN']
    pfx = prefix(ref)
    style = 'block'
    if len(rows) == 2 and pfx in {'R','C','L'}:
        style = pfx
    elif len(rows) == 2 and [r['Pin'] for r in rows] == ['A','K']:
        style = 'D'
    elif pfx == 'TP' and len(rows) == 1:
        style = 'TP'
    is_passive = style in {'R','C','L','D','TP'}
    value = next((x for x in functions if x), part) if is_passive else part
    if value.startswith(('Probe ', 'pad ')):
        value = 'probe pad'
    if not value or ('cluster' in value.lower() and is_passive):
        value = 'VALUE OPEN'
    if is_passive:
        half_width = GRID
        top, bottom = 1.27, -1.27
        layout = [(left, -2*GRID if left else 2*GRID, 0) for left in [True, False][:len(rows)]]
    else:
        half_width = 17.78 if len(rows) >= 18 else 13.97
        left_count = (len(rows) + 1) // 2
        top, bottom = GRID, -left_count * GRID
        layout = [(i < left_count, -(half_width + GRID) if i < left_count else half_width + GRID,
                   -(i % left_count) * GRID) for i in range(len(rows))]
    sources = set()
    pins = []
    for row, (left, px, py) in zip(rows, layout):
        net = local_net(row)
        kind = electrical_type(row, bonded_output=net in sources, external=ref in EXTERNAL)
        if kind == 'power_out':
            sources.add(net)
        if not net:
            kind = 'no_connect'
        # NC and FPC-only contacts intentionally have native no-connect markers.
        pins.append(Pin(row['Pin'], row['Pin_Function'], kind, px, py, 'L' if left else 'R', net))
    fp_status = footprint.get('Status', 'BLOCKED — no controlled package mapping')
    if ref in EXTERNAL:
        fp_status = 'External assembly boundary; no PCB footprint'
    notes = ' | '.join(dict.fromkeys(r['Note'].strip() for r in rows if r['Note'].strip()))
    if ref.startswith('J_DISP_'):
        notes = 'BLOCKED JBD_FPC and AVDD. Connector is bridge-side only. ' + notes
    if ref == 'J_CAM':
        notes = 'BLOCKED sensor-specific pinout, power sequence and PWDN polarity. ' + notes
    if ref in {'J_CAM','J_DISP_L','J_DISP_R','U6_OPT_AVDD'}:
        value = 'BLOCKED | ' + value
    metadata = {'Footprint': footprint.get('Footprint', ''), 'Datasheet': bom['Datasheet_URL'],
                'EVT1 Source Ref': ref, 'BOM Line': rows[0]['BOM_Line'], 'MPN': part,
                'Manufacturer': bom['Manufacturer'], 'Footprint Status': fp_status, 'Design Notes': compact(notes, 1400)}
    dnp = any(re.search(r'\bDNP\b', row['Pin_Function']) for row in rows)
    return Component(ref, cad, part, compact(value, 56), metadata, pins, top, bottom, half_width, style,
                     native=ref not in EXTERNAL, dnp=dnp)


def flag(cad, net, origin):
    return Component('SUPPLY_ORIGIN', cad, origin, 'PWR_FLAG', {'Design Notes': origin},
                     [Pin('1','source','power_out',-2*GRID,0,'L',net)], 1.27, -1.27, GRID, 'flag', native=False)


def text(value, scope, key, x, y, size=1.27):
    return f'(text {quoted(value)} (at {point(x, y)} 0) {font(size, "left")} (uuid {quoted(ident(*scope, "text", key))}))'


def schematic_header(uid, title, paper='A3'):
    return (f'(kicad_sch (version {FORMAT_VERSION}) (generator "evt1_native_eda") (generator_version "1.0")\n'
            f'(uuid {quoted(uid)})\n(paper {quoted(paper)})\n(title_block (title {quoted(title)}) '
            '(date "2026-11-18") (rev "D1.1-EDA") (company "Zhiyuan Yuedong AI/AR V1.0") '
            '(comment 1 "NOT FOR FAB - native conversion from Rev D1.1 / PR #25") '
            '(comment 2 "Vendor-blocked interfaces and missing footprints require closure"))\n')


def place_symbol(symbol, scope, project, hierarchy, x, y):
    included = 'yes' if symbol.native else 'no'
    out = [f'(symbol (lib_id {quoted("EVT1:" + symbol.libname)}) (at {point(x,y)} 0) (unit 1) '
           f'(exclude_from_sim no) (in_bom {included}) (on_board {included}) '
           f'(dnp {"yes" if symbol.dnp else "no"}) (uuid {quoted(ident(*scope, symbol.cad))})']
    out.append(prop('Reference', symbol.cad, x, y-symbol.top-2.54, size=1.12, hidden=symbol.style == 'flag'))
    value = f'{symbol.source} | {symbol.value}' if symbol.style != 'flag' else 'PWR_FLAG'
    out.append(prop('Value', compact(value, 72), x, y-symbol.bottom+2.54, size=0.92))
    for k,v in symbol.metadata.items():
        out.append(prop(k, v, x, y, hidden=True))
    for p in symbol.pins:
        out.append(f'(pin {quoted(p.number)} (uuid {quoted(ident(*scope, symbol.cad, p.number, "pin"))}))')
    out.append(f'(instances (project {quoted(project)} (path {quoted(hierarchy)} (reference {quoted(symbol.cad)}) (unit 1)))))')
    for p in symbol.pins:
        ax, ay = x+p.x, y-p.y
        if not p.net:
            out.append(f'(no_connect (at {point(ax,ay)}) (uuid {quoted(ident(*scope, symbol.cad, p.number, "nc"))}))')
            continue
        lx = ax-GRID if p.side == 'L' else ax+GRID
        out.append(f'(wire (pts (xy {point(ax,ay)}) (xy {point(lx,ay)})) (stroke (width 0) (type default)) '
                   f'(uuid {quoted(ident(*scope, symbol.cad, p.number, "wire"))}))')
        angle = 0 if p.side == 'L' else 180
        justify = 'right' if p.side == 'L' else 'left'
        out.append(f'(global_label {quoted(p.net)} (shape passive) (at {point(lx,ay)} {angle}) {font(1.0, justify)} '
                   f'(uuid {quoted(ident(*scope, symbol.cad, p.number, "label"))}))')
    return '\n'.join(out)


def paginate(symbols):
    """Pack three fixed-width A3 columns, using the explicit body/pin heights."""
    pages = [[]]
    centers = [76.2, 208.28, 340.36]
    heights = [35.56] * len(centers)
    for s in symbols:
        col = min(range(len(centers)), key=lambda i: heights[i])
        if heights[col] + s.height > 251.46:
            pages.append([])
            heights = [35.56] * len(centers)
            col = 0
        y = heights[col] + s.top + 2*GRID
        pages[-1].append((s, centers[col], y))
        heights[col] += s.height
    return pages


def write_board(board, rows, bom, footprints, output):
    proj, title = BOARD_PROJECTS[board]
    directory = output / proj
    root_uid = ident(board, 'root')
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['RefDes']].append(row)
    numeric = allocate_references(grouped)
    by_section = defaultdict(list)
    records = []
    origins = []
    for ref, pin_rows in grouped.items():
        cad = numeric[ref]
        sorted_pins = sorted(pin_rows, key=lambda r: natural(r['Pin']))
        keys = {r['Pin'] for r in sorted_pins}
        if len(keys) != len(sorted_pins):
            raise ValueError(f'Duplicate pin: {board} {ref}')
        fp = footprints.get((board,ref), {})
        s = component(cad, ref, sorted_pins, bom[pin_rows[0]['BOM_Line']], fp)
        by_section[section(board, ref)].append(s)
        for row in sorted_pins:
            state = 'LOCAL_NC' if row['Note'].strip() == 'NC_TRUNK_PASS' else ('NC' if not local_net(row) else 'CONNECTED')
            records.append({'Board': board, 'CAD_Reference': cad, 'Source_RefDes': ref, 'Pin': row['Pin'],
                            'Source_Net': row['Net'], 'CAD_Net': local_net(row), 'Local_State': state,
                            'Role': row['Role'], 'Pin_Function': row['Pin_Function'], 'BOM_Line': row['BOM_Line'],
                            'Footprint': s.metadata['Footprint'], 'Footprint_Status': s.metadata['Footprint Status']})
    for i, (net, origin) in enumerate(POWER_INHERITED[board].items(), 1):
        if not any(local_net(r) == net for r in rows):
            continue
        if any(p.net == net and p.kind == 'power_out' for items in by_section.values() for s in items for p in s.pins):
            continue
        by_section['Supply origins'].append(flag(f'#FLG0{i}', net, origin))
        origins.append({'Board':board, 'Net':net, 'KiCad_Flag':f'#FLG0{i}', 'Electrical_Source':origin})
    sheet_defs = []
    lib_parts = []
    page_number = 1
    for section_number, (area, symbols) in enumerate(sorted(by_section.items()), 1):
        ordered = sorted(symbols, key=lambda s: (-len(s.pins), natural(s.cad)))
        lib_parts.extend(ordered)
        pages = paginate(ordered)
        for page_index, placements in enumerate(pages, 1):
            page_number += 1
            slug = re.sub(r'[^a-z0-9]+', '-', area.lower()).strip('-')
            key = f'{section_number:02d}-{slug}-{page_index}'
            sheet_name = area + (f' ({page_index}/{len(pages)})' if len(pages) > 1 else '')
            file_name = f'{key}.kicad_sch'
            sheet_uid = ident(board, key, 'sheet')
            hierarchy = f'/{root_uid}/{sheet_uid}'
            scope = (board, key)
            hdr = schematic_header(ident(board,key,'file'), f'{board} | {sheet_name}')
            symbols_text = '\n'.join(s.library('EVT1:') for s, _, _ in placements)
            content = [hdr, f'(lib_symbols\n{symbols_text}\n)',
                       text(f'{board} | {sheet_name}', scope, 'title', 20.32, 15.24, 3),
                       text('NOT FOR FAB | Global labels are local to this PCB project. Source reference follows each KiCad reference.',
                            scope, 'subtitle', 20.32, 22.86),
                       text('Blank footprint fields require mapping review. Visit the root sheet for external interface gates.',
                            scope, 'status', 20.32, 27.94)]
            content.extend(place_symbol(s, scope, proj, hierarchy, x, y) for s, x, y in placements)
            save(directory/file_name, '\n'.join(content) + '\n)\n')
            sheet_defs.append((sheet_name, file_name, sheet_uid, page_number))

    root = [schematic_header(root_uid, title), '(lib_symbols)',
            text('EVT-1 | '+title, (board,'root'), 'title', 25.4, 25.4, 3.8),
            text('NOT FOR FAB | Rev D1.1 native schematic. Board-outline and manufacturing gates remain open.',
                 (board,'root'), 'source', 25.4, 35.56, 1.8),
            text('Each tile contains editable symbols, wires and labels. Connector and FPC mapping are external to this PCB.',
                 (board,'root'), 'guide', 25.4, 45.72),
            text('BLOCKED | JBD mechanical/pin/POR and AVDD interface. No supplier-side panel pins have been assigned.',
                 (board,'root'), 'optical', 25.4, 54.61),
            text('BLOCKED | Camera part, external pack/charger and controlled footprint inputs remain under review.',
                 (board,'root'), 'other', 25.4, 61.0)]
    for i, (name, filename, uid, page) in enumerate(sheet_defs):
        x, y = 25.4 + i % 3 * 127, 78.74 + i // 3 * 40.64
        root.append(f'(sheet (at {point(x,y)}) (size 106.68 25.4) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) '
                    f'(uuid {quoted(uid)}) (property "Sheetname" {quoted(name)} (at {point(x,y-1.27)} 0) {font(1.65,"left bottom")}) '
                    f'(property "Sheetfile" {quoted(filename)} (at {point(x,y+26.67)} 0) {font(1.27,"left top")}) '
                    f'(instances (project {quoted(proj)} (path {quoted("/"+root_uid)} (page {quoted(page)})))))')
    root.extend(['(sheet_instances (path "/" (page "1")))', ')\n'])
    save(directory/(proj+'.kicad_sch'), '\n'.join(root))
    save(directory/(proj+'.kicad_pro'), json.dumps({'meta': {'filename':proj+'.kicad_pro', 'version':1}}, indent=2)+'\n')
    save(directory/'sym-lib-table', '(sym_lib_table\n  (version 7)\n  (lib (name "EVT1")(type "KiCad")'
         '(uri "${KIPRJMOD}/evt1.kicad_sym")(options "")(descr "EVT-1 generated symbols"))\n)\n')
    footprint_libs = sorted({s.metadata['Footprint'].split(':', 1)[0] for s in lib_parts if s.metadata.get('Footprint')})
    fp_entries = []
    for lib in footprint_libs:
        uri = f'${{KICAD10_FOOTPRINT_DIR}}/{lib}.pretty'
        if (PACKAGE/f'{lib}.pretty').is_dir():
            uri = f'${{KIPRJMOD}}/../../{lib}.pretty'
        fp_entries.append(f'  (lib (name {quoted(lib)}) (type "KiCad") (uri {quoted(uri)}) (options "") (descr ""))')
    save(directory/'fp-lib-table', '(fp_lib_table\n  (version 7)\n'+'\n'.join(fp_entries)+'\n)\n')
    slib = '\n'.join(s.library() for s in lib_parts)
    save(directory/'evt1.kicad_sym', f'(kicad_symbol_lib (version {FORMAT_VERSION}) (generator "evt1_native_eda")\n{slib}\n)\n')
    # Remove stale generated pages only. User-edited sheets with another
    # generator or a custom basename are outside this tool's output contract.
    current = {filename for _,filename,_,_ in sheet_defs}
    for page in directory.glob('[0-9][0-9]-*.kicad_sch'):
        if page.name not in current and '(generator "evt1_native_eda")' in page.read_text(encoding='utf-8')[:200]:
            page.unlink()
    return records, len(sheet_defs), origins


def main():
    rows, bom_rows = input_tables()
    bom = {row['Item_ID']:row for row in bom_rows}
    if len(bom) != len(bom_rows):
        raise ValueError('Input BOM IDs must be unique')
    footprint_file = PACKAGE/'FOOTPRINT_MAP.csv'
    footprints = {(row['Board'],row['RefDes']):row for row in read_csv(footprint_file)} if footprint_file.is_file() else {}
    output = PACKAGE/'kicad'
    records, summary, origins = [], [], []
    for board in BOARD_PROJECTS:
        selected = [row for row in rows if row['Board'] == board]
        if not selected:
            raise ValueError(f'Board {board} has no terminals')
        refs, sheets, rail_flags = write_board(board, selected, bom, footprints, output)
        records.extend(refs)
        origins.extend(rail_flags)
        summary.append((board, sheets, len(refs)))
    external = [dict(row, Status='BLOCKED: supplier pinout not frozen; logical interface only')
                for row in rows if row['Board'] not in BOARD_PROJECTS]
    if len(records)+len(external) != len(rows):
        raise ValueError('Board and external terminal coverage must span the inputs')
    write_csv(output/'CAD_TERMINALS.csv', records)
    write_csv(output/'EXTERNAL_INTERFACE_TERMINALS_BLOCKED.csv', external)
    write_csv(output/'POWER_ORIGINS.csv', origins)
    for board, sheets, terminals in summary:
        print(f'{board}: {sheets} editable pages, {terminals} board terminal records')
    print(f'{len(external)} external source terminals remain BLOCKED; no supplier pin map emitted')


if __name__ == '__main__':
    main()
