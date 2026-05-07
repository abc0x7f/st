# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['code\\流水线\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('releases\\比赛版\\图\\logo.png', 'releases\\比赛版\\图')],
    hiddenimports=[
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
    ],
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
    name='光碳智绘',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='光碳智绘',
)
