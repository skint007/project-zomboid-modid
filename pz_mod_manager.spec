# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    [str(Path("src") / "pz_mod_manager" / "__main__.py")],
    pathex=[str(Path("src"))],
    binaries=[],
    datas=[
        (str(Path("src") / "pz_mod_manager" / "resources"), "pz_mod_manager/resources"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtWebEngine",
        "PySide6.QtMultimedia",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtTest",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pz-mod-manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=sys.platform != "win32",
    disable_windowed_traceback=False,
    icon=str(Path("src") / "pz_mod_manager" / "resources" / "icon.ico") if sys.platform == "win32" else None,
    codesign_identity=None,
    entitlements_file=None,
)
