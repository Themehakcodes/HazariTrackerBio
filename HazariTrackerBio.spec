# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec — builds a one-folder Windows EXE (32-bit Python).
#
# Build command:
#   C:\Python311-32\python.exe -m PyInstaller HazariTrackerBio.spec --clean
#
# Prerequisites on the TARGET machine:
#   • .NET Framework 4.x  (ships with Windows 10+)
#   • Mantra MFS100 kernel driver — NOW BUNDLED in the Inno Setup installer
#     (drivers\MFS100Driver\ — installed automatically via DPInst /LM /Q)
# ─────────────────────────────────────────────────────────────────────────────

import os, sys
from version import VERSION, APP_NAME

block_cipher = None

# ── SDK DLLs sourced from the local drivers/ folder (self-contained repo) ────
DRIVERS_DIR = os.path.join(os.path.dirname(os.path.abspath('.')), 'drivers')
DRIVERS_DIR = os.path.join(os.path.abspath('.'), 'drivers')
MANTRA_DLL  = os.path.join(DRIVERS_DIR, 'MANTRA.MFS100.dll')
IENGINE     = os.path.join(DRIVERS_DIR, 'iengine_ansi_iso.dll')
MFS100DLL   = os.path.join(DRIVERS_DIR, 'MFS100Dll.dll')

# Fallback to system Mantra install if drivers/ not found on this build machine
if not os.path.isfile(MANTRA_DLL):
    MANTRA_DLL = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MANTRA.MFS100.dll"
    IENGINE    = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\iengine_ansi_iso.dll"
    MFS100DLL  = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MFS100Dll.dll"

# Collect DLLs to bundle alongside the EXE
extra_binaries = []
for dll in [MANTRA_DLL, IENGINE, MFS100DLL]:
    if os.path.isfile(dll):
        extra_binaries.append((dll, "."))

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=[
        ("pages",   "pages"),
        ("version.py", "."),
        ("icon.png", "."),
        ("icon.ico", "."),
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
    icon='icon.ico',
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
