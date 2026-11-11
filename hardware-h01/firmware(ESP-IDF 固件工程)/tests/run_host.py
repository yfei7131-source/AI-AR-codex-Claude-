"""Build and execute actual portable firmware C core; no simulated test report."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cc', default=os.getenv('CC', 'cc'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    compiler=shutil.which(args.cc) or args.cc
    command=[compiler]
    if Path(compiler).stem.lower()=='zig': command.append('cc')
    with tempfile.TemporaryDirectory(prefix='glasses-host-') as directory:
        binary=Path(directory)/('firmware_tests.exe' if os.name=='nt' else 'firmware_tests')
        command+=['-std=c11','-Wall','-Wextra','-Werror','-pedantic','-I',str(root/'main'),
                  str(root/'main/core.c'),str(root/'main/display_adapter.c'),str(root/'tests/test_core.c'),'-o',str(binary)]
        subprocess.run(command,check=True,timeout=180)
        subprocess.run([str(binary)],check=True,timeout=30)
        media=Path(directory)/('media_tests.exe' if os.name=='nt' else 'media_tests')
        command=[compiler]+(['cc'] if Path(compiler).stem.lower()=='zig' else [])
        command+=['-std=c11','-Wall','-Wextra','-Werror','-pedantic','-I',str(root/'main'),
                  str(root/'main/media_core.c'),str(root/'tests/test_media.c'),'-o',str(media)]
        subprocess.run(command,check=True,timeout=180)
        subprocess.run([str(media)],check=True,timeout=30)

if __name__=='__main__': main()
