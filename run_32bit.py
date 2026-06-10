"""
run_32bit.py
────────────
Launcher that automatically re-executes app.py under a 32-bit Python
interpreter (required because the Mantra MFS100 native DLLs are 32-bit x86).

How to use
──────────
  1. Run this script with any Python (32 or 64-bit):
         python run_32bit.py

  2. It will detect if the current interpreter is 64-bit.
     If so, it searches for a 32-bit Python installation and re-launches.

  3. If no 32-bit Python is found it prints instructions and exits.

Common 32-bit Python install locations checked
───────────────────────────────────────────────
  %LOCALAPPDATA%\\Programs\\Python\\Python3*-32\\python.exe
  %PROGRAMFILES%\\Python3*-32\\python.exe
  C:\\Python3*-32\\python.exe
  C:\\Python3*\\python.exe  (if it happens to be 32-bit)
"""

import struct
import sys
import os
import glob
import subprocess

IS_64BIT = struct.calcsize("P") * 8 == 64
APP_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def find_32bit_python() -> str | None:
    """Return path to a 32-bit python.exe, or None if not found."""
    candidates = []

    # ── Known / fixed install paths (checked first for speed) ────────────────
    known = [
        r"C:\Python311-32\python.exe",    # installed by run_32bit.py setup
        r"C:\Python311-32\python.exe",
        r"C:\Python310-32\python.exe",
        r"C:\Python39-32\python.exe",
        r"C:\Python38-32\python.exe",
    ]
    for p in known:
        if os.path.isfile(p) and p not in candidates:
            candidates.append(p)

    # ── Glob search in common installation roots ───────────────────────────────
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
        os.path.expandvars(r"%PROGRAMFILES%"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%"),
        r"C:\\",
    ]

    for root in roots:
        if not os.path.isdir(root):
            continue
        for pattern in ["Python3*-32", "Python3*"]:
            for d in glob.glob(os.path.join(root, pattern)):
                exe = os.path.join(d, "python.exe")
                if os.path.isfile(exe) and exe not in candidates:
                    candidates.append(exe)

    # Also check PATH entries
    import shutil
    for name in ["python3", "python"]:
        found = shutil.which(name)
        if found and found not in candidates:
            candidates.append(found)

    # Check each candidate
    for exe in candidates:
        try:
            result = subprocess.run(
                [exe, "-c", "import struct; print(struct.calcsize('P')*8)"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip() == "32":
                return exe
        except Exception:
            continue

    return None


def main():
    if not IS_64BIT:
        # Already 32-bit — just run the app directly
        import importlib.util
        spec = importlib.util.spec_from_file_location("app", APP_SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return

    print("Current Python is 64-bit — searching for 32-bit Python …")
    py32 = find_32bit_python()

    if py32:
        print(f"Found 32-bit Python: {py32}")
        print(f"Launching: {py32} {APP_SCRIPT}")
        # subprocess.Popen is more reliable than os.execv on Windows.
        # It spawns the GUI in a new process and exits this launcher cleanly.
        import subprocess
        proc = subprocess.Popen([py32, APP_SCRIPT],
                                cwd=os.path.dirname(APP_SCRIPT))
        proc.wait()   # keep launcher alive until app closes (so terminal stays tidy)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("  32-bit Python NOT FOUND")
        print("=" * 60)
        print()
        print("The Mantra MFS100 DLL is 32-bit (x86).")
        print("You must install 32-bit Python 3.x to use real hardware.")
        print()
        print("Download from:")
        print("  https://www.python.org/downloads/windows/")
        print("  → Click the version → choose 'Windows installer (32-bit)'")
        print()
        print("After installing, run:")
        print("  python run_32bit.py")
        print()
        print("Alternatively you can start in DEMO MODE (no real device):")
        print("  python app.py")
        input("\nPress Enter to exit …")


if __name__ == "__main__":
    main()
