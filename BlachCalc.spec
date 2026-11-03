# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH)
datas = [
    (str(project_root / 'logo.png'), '.'),
    (str(project_root / 'BlachCalc.ico'), '.'),
]
datas += [
    (str(test_file), '_test_suite')
    for test_file in project_root.glob('test_*.py')
]
binaries = []
hiddenimports = ['run_tests', 'ui_harness']
tmp_ret = collect_all('pymupdf')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(project_root / 'blachcalc.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlachCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_root / 'BlachCalc.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BlachCalc',
)
