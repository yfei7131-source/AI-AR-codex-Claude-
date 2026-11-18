#!/usr/bin/env python3
"""Run native ERC and check its exported board netlists against the effective inputs."""

import argparse
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from generate_kicad import BOARD_PROJECTS, PACKAGE, input_tables, local_net, read_csv


def run(command, logfile):
    process = subprocess.run(command, cwd=PACKAGE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    logfile.write_bytes(process.stdout)
    return process.returncode


def load_nodes(xml_file):
    root = ET.parse(xml_file).getroot()
    components = {}
    for comp in root.findall('./components/comp'):
        ref = comp.attrib['ref']
        source = comp.findtext('./fields/field[@name="EVT1 Source Ref"]')
        fp = comp.findtext('./footprint') or ''
        pcb_use = 'EXTERNAL' if comp.find('./property[@name="exclude_from_board"]') is not None else 'BOARD'
        if ref in components:
            raise ValueError(f'Duplicate KiCad reference: {ref}')
        components[ref] = (source, fp, pcb_use)
    nodes = {}
    for net in root.findall('./nets/net'):
        physical_nodes = [n for n in net.findall('node') if not n.attrib['ref'].startswith('#FLG')]
        for node in physical_nodes:
            identity = (node.attrib['ref'], node.attrib['pin'])
            if identity in nodes:
                raise ValueError(f'KiCad exported multiple nets at {identity}')
            name = net.attrib['name']
            # Eeschema includes isolated NC pins on per-terminal generated nets.
            if name.startswith('unconnected-(') and len(physical_nodes) == 1:
                name = ''
            nodes[identity] = name
    return nodes, components


def parity(manifest, actual, components):
    expected = {(r['CAD_Reference'], r['Pin']): r['CAD_Net'] for r in manifest}
    if len(expected) != len(manifest):
        raise ValueError('The terminal map contains duplicate native reference/pin pairs')
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    nets = [{'ref': ref, 'pin': pin, 'expected': expected[ref, pin], 'kicad': actual[ref, pin]}
            for ref, pin in sorted(expected.keys() & actual.keys()) if expected[ref, pin] != actual[ref, pin]]
    props = []
    for r in {r['CAD_Reference']: r for r in manifest}.values():
        cad = r['CAD_Reference']
        found = components.get(cad)
        expected_props = (r['Source_RefDes'], r['Footprint'], r['PCB_Use'])
        if found != expected_props:
            props.append({'ref': cad, 'expected': expected_props, 'kicad': found})
    return {'missing_terminals': missing, 'unexpected_terminals': extra, 'net_mismatches': nets, 'symbol_metadata_mismatches': props}


def audit_manifest(terminal_map):
    source, _ = input_tables()
    footprint_rows = read_csv(PACKAGE / 'FOOTPRINT_MAP.csv')
    footprints = {(r['Board'], r['RefDes']): r['Footprint'] for r in footprint_rows}
    source_parts = {(r['Board'], r['RefDes']) for r in source}
    if len(footprints) != len(footprint_rows) or footprints.keys() != source_parts:
        raise ValueError('The footprint map must contain one entry for each effective electrical source reference')
    expected = {(r['Board'], r['RefDes'], r['Pin']): (r['Net'], local_net(r), footprints[r['Board'], r['RefDes']])
                for r in source if r['Board'] in BOARD_PROJECTS}
    compiled = {(r['Board'], r['Source_RefDes'], r['Pin']): (r['Source_Net'], r['CAD_Net'], r['Footprint'])
                for r in terminal_map}
    if len(compiled) != len(terminal_map) or compiled != expected:
        raise ValueError('Native terminal map does not match the effective electrical tables and footprint map')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kicad-cli', default='kicad-cli')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pdf', action='store_true', help='Also export the actual KiCad schematic pages as vector PDF')
    args = parser.parse_args()
    exe = shutil.which(args.kicad_cli)
    if not exe:
        print('BLOCKED: kicad-cli executable not found')
        return 2
    output = args.output.resolve()
    output.mkdir(exist_ok=True, parents=True)
    version = subprocess.check_output([exe, 'version'], text=True, encoding='utf-8').strip()
    result = {'kicad': version, 'board_results': [], 'fabrication_status': 'BLOCKED',
              'scope': 'Default native KiCad ERC and schematic netlist terminal parity. Vendor and PCB qualification remain BLOCKED.'}
    terminals = read_csv(PACKAGE / 'kicad/CAD_TERMINALS.csv')
    audit_manifest(terminals)
    failed = False
    for board, (project, _) in BOARD_PROJECTS.items():
        root = PACKAGE / f'kicad/{project}/{project}.kicad_sch'
        xml = output / f'{project}.xml'
        erc = output / f'{project}-erc.json'
        commands = {
            'export': [exe, 'sch', 'export', 'netlist', '--format', 'kicadxml', '--output', str(xml), str(root)],
            'erc': [exe, 'sch', 'erc', '--format', 'json', '--severity-all', '--exit-code-violations', '--output', str(erc), str(root)],
        }
        if args.pdf:
            commands['pdf'] = [exe, 'sch', 'export', 'pdf', '--output', str(output/f'{project}.pdf'), str(root)]
        for artifact in (xml, erc):
            artifact.unlink(missing_ok=True)
        exit_codes = {kind: run(cmd, output/f'{project}-{kind}.log') for kind, cmd in commands.items()}
        manifest = [r for r in terminals if r['Board'] == board]
        board_result = {'board':board, 'project':project, 'terminal_count':len(manifest),
                        'declared_no_connect_count':sum(not r['CAD_Net'] for r in manifest), 'command_exit_codes':exit_codes}
        if exit_codes['export'] != 0 or not xml.is_file():
            board_result['terminal_parity'] = 'FAIL'
        else:
            board_result['parity_details'] = parity(manifest, *load_nodes(xml))
            board_result['terminal_parity'] = 'FAIL' if any(board_result['parity_details'].values()) else 'PASS'
        if not erc.is_file():
            board_result['erc'] = 'FAIL'
        else:
            evidence = json.loads(erc.read_text(encoding='utf-8'))
            violations = [v for sheet in evidence['sheets'] for v in sheet['violations']]
            board_result['erc_counts'] = {kind:sum(v['severity']==kind for v in violations) for kind in ('error','warning','exclusion')}
            board_result['erc'] = 'FAIL' if exit_codes['erc'] or violations else 'PASS'
        if 'pdf' in exit_codes and exit_codes['pdf'] != 0:
            board_result['pdf'] = 'FAIL'
        failed |= 'FAIL' in board_result.values()
        result['board_results'].append(board_result)
        print(f"{board}: terminal parity {board_result['terminal_parity']} ({len(manifest)} pins), ERC {board_result['erc']} {board_result.get('erc_counts', '')}")
        if board_result['terminal_parity'] == 'FAIL':
            print(json.dumps(board_result.get('parity_details', {}), ensure_ascii=False, indent=2)[:5000])
    result['pipeline'] = 'FAIL' if failed else 'PASS'
    summary = output / 'kicad-verification.json'
    summary.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(f'{result["pipeline"]}: detailed evidence at {summary}')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
