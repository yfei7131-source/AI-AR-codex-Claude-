"""Reproducible IDF build in an explicit ASCII workspace (Windows Unicode-safe).

Never flashes hardware or installs tools. Source remains in the repository.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--idf-root',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--python',default=sys.executable)
    parser.add_argument('--tools-root',type=Path)
    parser.add_argument('--tool-bin',action='append',default=[])
    parser.add_argument('--board',choices=['unconfigured','eye-v22','s3-carrier-a','evt0-r3'],default='unconfigured')
    parser.add_argument('--dev-ap',action='store_true',help='Compile opt-in development AP with large factory partition; never flashes')
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    version_file=args.idf_root/'tools/cmake/version.cmake'
    expected={'MAJOR':'5','MINOR':'4','PATCH':'3'}
    version_text=version_file.read_text(encoding='utf-8')
    if any(not re.search(r'set\(IDF_VERSION_'+key+r'\s+'+value+r'\)',version_text) for key,value in expected.items()):
        parser.error('This firmware build is pinned to official ESP-IDF v5.4.3')
    workspace=args.workspace.resolve()
    if not str(workspace).isascii() or ' ' in str(workspace):
        parser.error('--workspace must use an ASCII path without spaces')
    if workspace==source or source in workspace.parents or workspace in source.parents:
        parser.error('--workspace must be outside the source tree')
    variant=args.board+('-ap' if args.dev_ap else '')
    project=workspace/variant/'project'
    project.mkdir(parents=True,exist_ok=True)
    # Only copy source: no private files, toolchains or old generated config.
    source_files=[]
    for name in ['CMakeLists.txt','sdkconfig.defaults','sdkconfig.eye.defaults','sdkconfig.carrier.defaults','sdkconfig.evt0.defaults','sdkconfig.dev-ap.defaults','main']:
        origin=source/name
        if origin.is_dir():
            shutil.copytree(origin,project/name,dirs_exist_ok=True)
            source_files.extend(p for p in origin.rglob('*') if p.is_file())
        else:
            shutil.copy2(origin,project/name); source_files.append(origin)
    if (source/'dependencies.lock').exists(): shutil.copy2(source/'dependencies.lock',project/'dependencies.lock')
    env=os.environ.copy()
    env['IDF_PATH']=str(args.idf_root.resolve())
    env['IDF_PYTHON_ENV_PATH']=str(Path(args.python).resolve().parents[1])
    if args.tools_root: env['IDF_TOOLS_PATH']=str(args.tools_root.resolve())
    env['PATH']=os.pathsep.join(args.tool_bin+[str(Path(args.python).resolve().parent),env['PATH']])
    env['PYTHONUTF8']='1'
    overlays={'eye-v22':';sdkconfig.eye.defaults','s3-carrier-a':';sdkconfig.carrier.defaults','evt0-r3':';sdkconfig.evt0.defaults'}
    defaults='sdkconfig.defaults'+overlays.get(args.board,'')
    if args.dev_ap: defaults+=';sdkconfig.dev-ap.defaults'
    command=[args.python,str(args.idf_root/'tools/idf.py'),'-C',str(project),'-B',str(project/'build'),
             '-DIDF_TARGET=esp32s3','-DSDKCONFIG_DEFAULTS='+defaults,'reconfigure','build']
    evidence=source/'evidence'; evidence.mkdir(exist_ok=True)
    log=evidence/f'idf-{variant}.txt'
    metadata_path=evidence/f'build-{variant}.json'
    metadata_path.write_text(json.dumps({'board':args.board,'build_succeeded':False,
                                        'hardware_verified':False,'flashed':False})+'\n',encoding='utf-8')
    print('Building firmware (no flash), log:',log,flush=True)
    with log.open('w',encoding='utf-8') as output:
        output.write('COMMAND '+json.dumps(command)+'\n'); output.flush()
        result=subprocess.run(command,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=1800)
    print('IDF exit code:',result.returncode,flush=True)
    if result.returncode:
        print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-35:]))
        return result.returncode
    for artifact in [project/'dependencies.lock',project/'build/ai_ar_glasses_device.bin']:
        if artifact.name=='dependencies.lock' and artifact.exists(): shutil.copy2(artifact,source/artifact.name)
    binary=project/'build/ai_ar_glasses_device.bin'
    metadata={'board':args.board,'media_dev_ap':args.dev_ap,'build_succeeded':True,'target':'esp32s3','idf':'5.4.3','hardware_verified':False,'flashed':False,
              'binary_path':str(binary),'binary_bytes':binary.stat().st_size,
              'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
              'source_sha256':{str(p.relative_to(source)).replace('\\','/'):hashlib.sha256((project/p.relative_to(source)).read_bytes()).hexdigest() for p in sorted(source_files)}}
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metadata,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
