# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification for HoraryApp
# Bundles the built frontend and excludes unnecessary GUI libraries

block_cipher = None

a = Analysis(
    ['backend/app.py'],          # Python entry point
    pathex=['.'],
    binaries=[],
    datas=[('frontend/dist', 'frontend/dist')],   # bundle frontend build
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HoraryApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                      # windowed
    icon='frontend/assets/icon.ico',    # icon file
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, name='HoraryApp'
)
