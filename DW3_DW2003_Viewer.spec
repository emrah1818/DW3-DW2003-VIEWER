# PyInstaller: one folder with DW3_DW2003_Viewer(.exe), the interface (www/) and the converter.
# Build: python tools/build_native.py && python -m PyInstaller --noconfirm DW3_DW2003_Viewer.spec
import sys
from pathlib import Path
root = Path(SPECPATH)
exe_name = 'dw3_converter.exe' if sys.platform == 'win32' else 'dw3_converter'
a = Analysis([str(root / 'run.py')], pathex=[str(root)],
             datas=[(str(root / 'www'), 'www'), (str(root / 'licenses'), 'licenses'),
                    (str(root / 'native' / 'dw3_converter' / 'CREDITS.md'), 'licenses'),
                    (str(root / 'native' / 'bin' / exe_name), 'native/bin')],
             hiddenimports=['PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets'],
             excludes=['tkinter', 'numpy', 'PIL', 'pytest', 'playwright'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DW3_DW2003_Viewer', console=False,
          **({'version': str(root / 'tools' / 'windows_version_info.txt')} if sys.platform == 'win32' else {}))
coll = COLLECT(exe, a.binaries, a.datas, name='DW3_DW2003_Viewer')
