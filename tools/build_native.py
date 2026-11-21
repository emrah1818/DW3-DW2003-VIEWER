"""Build the bundled DW3 model converter (MIT, native/dw3_converter) with GCC/Clang or MSVC.
Output: native/bin/dw3_converter(.exe)."""
from pathlib import Path
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
source = root / 'native' / 'dw3_converter'
out = root / 'native' / 'bin'
out.mkdir(parents=True, exist_ok=True)
sources = [str(source / (n + '.cpp')) for n in ('cli', 'model', 'game', 'dw2', 'gltf', 'stage_export')]
cxx = os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++') or shutil.which('cl')
if not cxx:
    raise SystemExit('C++17-Compiler fehlt: MSVC Build Tools oder GCC installieren.')
target = out / ('dw3_converter.exe' if os.name == 'nt' else 'dw3_converter')
if Path(cxx).name.lower() in ('cl', 'cl.exe'):
    cmd = [cxx, '/nologo', '/std:c++17', '/EHsc', '/O2', '/I' + str(source), *sources, '/Fe:' + str(target)]
else:
    cmd = [cxx, '-std=c++17', '-O2', '-I' + str(source), *sources, '-o', str(target)]
    if os.name == 'nt':
        cmd += ['-static']
subprocess.run(cmd, cwd=out, check=True)
for junk in out.glob('*.obj'):
    junk.unlink()
print(target)
