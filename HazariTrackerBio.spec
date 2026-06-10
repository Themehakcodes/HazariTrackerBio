# HazariTrackerBio.spec
# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec — builds a one-folder Windows EXE (32-bit Python).
#
# Build command:
#   C:\Python311-32\python.exe -m PyInstaller HazariTrackerBio.spec --clean
#
# Prerequisites on the TARGET machine (cannot be bundled):
#   • Mantra MFS100 driver (installs MFS100.sys kernel driver)
#   • .NET Framework 4.x  (ships with Windows 10+)
# ─────────────────────────────────────────────────────────────────────────────

import os, sys
from version import VERSION, APP_NAME

block_cipher = None

# Paths
MANTRA_DLL = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MANTRA.MFS100.dll"
IENGINE    = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\iengine_ansi_iso.dll"

# Collect DLLs to bundle alongside the EXE
extra_binaries = []
if os.path.isfile(MANTRA_DLL):
    extra_binaries.append((MANTRA_DLL, "."))
if os.path.isfile(IENGINE):
    extra_binaries.append((IENGINE,    "."))

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=[
        ("pages",   "pages"),
        ("version.py", "."),
    ],
    hiddenimports=[
        "clr",
        "pythonnet",
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "MANTRA",
        "MANTRA.MFS100",
        "sqlite3",
        "csv",
        "threading",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f"HazariTrackerBio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No black terminal window
    icon=None,              # Add icon.ico here when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=f"HazariTrackerBio-v{VERSION}",
)
