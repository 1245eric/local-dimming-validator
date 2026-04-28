# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['local_dimming_align.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['cv2', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='local_dimming_validator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='local_dimming_validator',
)
