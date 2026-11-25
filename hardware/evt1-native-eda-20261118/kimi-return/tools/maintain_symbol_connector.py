#!/usr/bin/env python3
"""Bounded same-version connector repair; never edits design geometry via debug."""
from pathlib import Path
import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
SOURCE = REPO / '.tools' / 'easyeda-agent-src'
OUT = ROOT / 'evidence' / 'connector-repair'
CLI = Path.home() / '.local/bin/easyeda.exe'
PROJECT = 'cc395d487bad78844a2449d2f05c8a71461fc6bf64e50f48cacb1ef5f7356662'
DOCS = [
    ('pcb', '8fbc3cae65886fe5'), ('pcb', '9ce45f14cb79dc9d'),
    ('pcb', '1db01a36f669a47a'), ('pcb', '271a28697816c22b'),
    ('schematic', 'dff3a8fe270050d6'), ('schematic', '43a42f20d31f8062'),
    ('schematic', '388fb7a3b1e5f2d6'), ('schematic', '4d7420b4f42714c8'),
]

def decode(text):
    start = text.find('{')
    if start < 0:
        return {'ok': True, 'message': text.strip()}
    return json.JSONDecoder().raw_decode(text[start:])[0]

def call(args, log, timeout=120):
    result = subprocess.run([str(CLI), *args, '--project', PROJECT], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('$ ' + ' '.join([str(CLI), *args, '--project', PROJECT]) + '\n' + result.stdout + result.stderr, encoding='utf-8')
    parsed = decode(result.stdout)
    if result.returncode or parsed.get('ok') is False:
        raise RuntimeError(f'Command failed; see {log}')
    return parsed

def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Apply the preflighted same-version connector update')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    before = call(['health'], OUT / '00-health-before.log')
    window = next(w for w in before['found']['raw']['windows'] if w['context']['projectUuid'] == PROJECT)
    save_receipts = []
    for kind, uuid in DOCS:
        call(['doc', 'switch', uuid], OUT / f'save-{uuid}-switch.log')
        save = call(['sch' if kind == 'schematic' else 'pcb', 'save'], OUT / f'save-{uuid}.log')
        if save.get('result', {}).get('saved') is not True:
            raise RuntimeError(f'Explicit saved:true missing for {uuid}')
        save_receipts.append({'uuid': uuid, 'saved': True})
    code = (ROOT / 'tools' / 'connector-identity-probe.js').read_text(encoding='utf-8')
    probe = call(['debug', 'exec', '--timeout', '60', '--code', code], OUT / '01-installed-identity.log')
    debug_value = probe.get('result', {}).get('value', {})
    candidates = debug_value.get('candidates', []) if isinstance(debug_value, dict) else []
    if len(candidates) != 1:
        raise RuntimeError(f'Expected exactly one installed connector identity, got {len(candidates)}')
    identity = candidates[0]
    extension = json.loads((SOURCE / 'extension' / 'extension.json').read_text(encoding='utf-8'))
    bundle = SOURCE / 'extension' / 'dist' / 'index.js'
    new_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if identity['uuid'] != extension['uuid'] or identity['version'] != extension['version']:
        raise RuntimeError('Installed connector identity/version differs from the authorized same-version source')
    if not identity['enabled'] or not identity['allowExternalInteractions']:
        raise RuntimeError('Installed connector is not enabled for the existing interaction permission')
    if identity['installedBundleSha256'] == new_sha:
        raise RuntimeError('Installed and built bundle hashes are identical; no update is required')
    preflight = {
        'scope': 'same-version connector repair only; no design geometry via debug',
        'projectUuid': PROJECT,
        'windowBefore': window,
        'savedDocuments': save_receipts,
        'identity': identity,
        'newBundleSha256': new_sha,
        'newBundleBytes': bundle.stat().st_size,
        'sourceVersion': extension['version'],
        'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip(),
        'sourceDiff': subprocess.check_output(['git', 'diff', '--', 'extension/src/actions.ts', 'extension/src/actions.test.ts'], cwd=SOURCE, text=True),
    }
    dump('preflight.json', preflight)
    print(json.dumps({'preflight': 'PASS', 'identity': identity, 'newBundleSha256': new_sha}, indent=2), flush=True)
    if not args.apply:
        return 0
    inject = (SOURCE / 'extension' / 'scripts' / 'hot-reload-inject.js').read_text(encoding='utf-8')
    inject += '\nreturn await hotReloadConnector(' + json.dumps({
        'TEAM': identity['team'], 'UUID': identity['uuid'], 'VERSION': extension['version'],
        'EXPECTED_VERSION': identity['version'], 'EXPECTED_SHA256': identity['installedBundleSha256'],
        'BUNDLE_SHA256': new_sha, 'PORT': 8790, 'RELOAD': True,
    }) + ');\n'
    (OUT / 'hot-reload-invocation.js').write_text(inject, encoding='utf-8')
    node_executable = subprocess.check_output(['cmd.exe', '/d', '/c', 'node -p process.execPath'], text=True).strip().splitlines()[-1]
    node_env = dict(__import__('os').environ, ELECTRON_RUN_AS_NODE='1')
    server_log = (OUT / '02-hot-reload-server.log').open('w', encoding='utf-8')
    server = subprocess.Popen([node_executable, str(SOURCE / 'extension' / 'scripts' / 'hot-reload-server.mjs'), '--keep'],
                              cwd=SOURCE, stdout=server_log, stderr=subprocess.STDOUT, env=node_env)
    try:
        deadline = time.monotonic() + 10
        while True:
            if server.poll() is not None:
                raise RuntimeError('Hot-reload WebSocket server exited before serving')
            try:
                with socket.create_connection(('127.0.0.1', 8790), timeout=0.3):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        receipt = call(['debug', 'exec', '--timeout', '60', '--code', inject], OUT / '03-hot-reload-receipt.log', timeout=90)
        dump('hot-reload-receipt.json', receipt)
        reload_value = receipt.get('result', {}).get('value', {})
        if reload_value.get('ok') is not True or reload_value.get('sha256') != new_sha:
            raise RuntimeError('Hot-reload did not return a matching stored-hash receipt')
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        server_log.close()
    time.sleep(8)
    health = None
    for attempt in range(12):
        time.sleep(3)
        try:
            health = call(['health'], OUT / f'04-health-after-{attempt:02d}.log')
            current = next(w for w in health['found']['raw']['windows'] if w['context']['projectUuid'] == PROJECT)
            if current['windowId'] != window['windowId'] and current['connectedAt'] != window['connectedAt'] and current['connectorVersion'] == extension['version']:
                break
        except Exception:
            current = None
    else:
        raise RuntimeError('No new connected window was observed after connector reload')
    dump('reload-verification.json', {'windowBefore': window, 'windowAfter': current,
        'newWindowObserved': True, 'newBundleSha256': new_sha, 'sameVersion': True})
    print(json.dumps({'reload': 'PASS', 'windowAfter': current['windowId'], 'connectorVersion': current['connectorVersion']}, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
