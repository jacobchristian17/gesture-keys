# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('C:\\Users\\wsenr\\repos\\source\\gesture-keys\\models\\hand_landmarker.task', 'models'), ('C:\\Users\\wsenr\\repos\\source\\gesture-keys\\config.yaml', '.')]
datas += collect_data_files('mediapipe')


a = Analysis(
    ['C:\\Users\\wsenr\\repos\\source\\gesture-keys\\gesture_keys\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['pystray._win32', 'PIL._tkinter_finder', 'mediapipe', 'pynput.keyboard._win32', 'pynput.mouse._win32'],
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
    name='GestureKeys',
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
    name='GestureKeys',
)
