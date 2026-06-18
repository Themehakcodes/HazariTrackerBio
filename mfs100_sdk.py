"""
mfs100_sdk.py
─────────────
Python wrapper for the Mantra MFS100 fingerprint scanner.

Backend: MANTRA.MFS100.dll  (managed .NET assembly, v9.0.2.5)
         loaded via pythonnet (clr).

DLL location (official Mantra driver install):
  C:\\Program Files\\Mantra\\MFS100\\Driver\\MFS100Test\\MANTRA.MFS100.dll

The .NET assembly already bundles the iengine license and calls
MFS100R0.dll internally — no separate iengine.lic file is needed.

DEMO MODE
─────────
  If the MANTRA.MFS100.dll cannot be found or pythonnet is not
  installed, the class operates in DEMO MODE: synthetic data is
  returned so the GUI can be exercised without real hardware.

Public API (same interface as the old ctypes wrapper)
──────────────────────────────────────────────────────
  sdk = MFS100()
  ok, msg = sdk.init_device()
  ok, quality, template, is_timeout = sdk.capture_iso_template(timeout_ms=10_000)
  matched, score = sdk.match_iso(template_a, template_b)
  sdk.close_device()

is_timeout
──────────
  capture_iso_template returns a 4th value: is_timeout.
  True  → no finger was placed within timeout_ms — completely normal, not an error.
  False → a real device / DLL error occurred and recovery may be needed.
"""

import os
import sys
import random

# ── Constants ────────────────────────────────────────────────────────────────
QUALITY_MIN     = 50      # reject captures below this quality (0–99)
SECURITY_LEVEL  = 5       # match security level (passed to MatchISO / MatchANSI)
MATCH_THRESHOLD = 1400    # minimum score to consider fingerprints a match (0–10000)
TEMPLATE_ALLOC  = 2048    # max template size (informational)
RET_SUCCESS     = 0

# Mantra SDK return codes that mean "no finger placed — timed out", i.e. normal.
# These must NOT be counted as device errors in the scan loop.
# Source: Mantra MFS100 SDK documentation & observed values.
# If you see a new ret code on idle, add it here.
_TIMEOUT_RET_CODES = {
    -3,    # AutoCapture standard timeout
    1,     # Some SDK versions return 1 on timeout
    101,   # "No Finger" status in some firmware versions
    104,   # "Finger Not Placed" in extended status
}

# ── DLL location ─────────────────────────────────────────────────────────────
_SYSTEM_INSTALL = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test"


def _find_dll_dir() -> str:
    """
    Locate the folder that contains MANTRA.MFS100.dll.
    Priority:
      1. PyInstaller _MEIPASS (bundled EXE)
      2. Same folder as this script / EXE
      3. System Mantra install
    """
    # PyInstaller bundle
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and os.path.isfile(os.path.join(meipass, "MANTRA.MFS100.dll")):
        return meipass

    # Next to the running script or exe
    here = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    ))
    if os.path.isfile(os.path.join(here, "MANTRA.MFS100.dll")):
        return here

    # System install fallback
    return _SYSTEM_INSTALL


_MFS100_TEST_DIR = _find_dll_dir()
_MANTRA_DLL      = os.path.join(_MFS100_TEST_DIR, "MANTRA.MFS100.dll")


def _load_dotnet():
    """
    Import the MANTRA.MFS100 .NET assembly via pythonnet.
    Returns (MFS100_class, FingerData_class) or (None, None) on failure.
    """
    if not os.path.isfile(_MANTRA_DLL):
        print(f"[MFS100] DLL not found: {_MANTRA_DLL}")
        return None, None

    try:
        import clr  # pythonnet
    except ImportError:
        print("[MFS100] pythonnet not installed — run: pip install pythonnet")
        return None, None

    try:
        sys.path.insert(0, _MFS100_TEST_DIR)
        clr.AddReference("MANTRA.MFS100")
        from MANTRA import MFS100 as _MFS100Class
        from MANTRA import FingerData as _FingerDataClass
        print("[MFS100] Loaded MANTRA.MFS100.dll via pythonnet")
        return _MFS100Class, _FingerDataClass
    except Exception as exc:
        print(f"[MFS100] Failed to load .NET assembly: {exc}")
        return None, None


_MFS100Class, _FingerDataClass = _load_dotnet()


# ─────────────────────────────────────────────────────────────────────────────

class MFS100:
    """
    High-level Python interface to the MFS100 fingerprint scanner.

    Backed by the official MANTRA.MFS100 .NET assembly (pythonnet).
    Falls back to DEMO MODE if the assembly is unavailable.

    Typical usage
    ─────────────
        sdk = MFS100()
        ok, msg = sdk.init_device()

        ok, quality, template = sdk.capture_iso_template()
        if ok:
            matched, score = sdk.match_iso(stored_template, template)

    All public methods return simple Python types (bool, int, bytes).
    They never raise — errors are returned as (False, message) tuples.
    """

    def __init__(self):
        self._mfs    = None   # MANTRA.MFS100 .NET instance
        self.is_demo = (_MFS100Class is None)
        self._width  = 0
        self._height = 0

        if not self.is_demo:
            try:
                self._mfs = _MFS100Class()
            except Exception as exc:
                print(f"[MFS100] Cannot create MFS100 instance: {exc}")
                self.is_demo = True

    # =========================================================================
    # Public API
    # =========================================================================

    def init_device(self) -> tuple[bool, str]:
        """Open the MFS100 USB device."""
        if self.is_demo:
            return True, "DEMO MODE — device simulated"

        try:
            ret = self._mfs.Init()
        except Exception as exc:
            print(f"[MFS100] Init() raised: {exc}")
            return False, str(exc)

        if ret != RET_SUCCESS:
            msg = self._safe_error_msg(ret)
            print(f"[MFS100] Init() failed: {ret} — {msg}")
            return False, msg

        # Fetch device info
        try:
            info = self._mfs.GetDeviceInfo()
            self._width  = info.Width
            self._height = info.Height
            ver = self._mfs.GetSDKVersion()
            serial = info.SerialNo
            print(f"[MFS100] SDK v{ver}  serial={serial}  {self._width}x{self._height}px")
            return True, f"MFS100 ready (SDK v{ver}, serial {serial})"
        except Exception as exc:
            return True, "MFS100 ready"

    def close_device(self):
        """Release the USB device handle."""
        if not self.is_demo and self._mfs:
            try:
                self._mfs.Uninit()
            except Exception:
                pass

    def is_connected(self) -> bool:
        """Check whether the sensor is physically plugged in."""
        if self.is_demo:
            return True
        try:
            return bool(self._mfs.IsConnected())
        except Exception:
            return False

    # ── Capture ───────────────────────────────────────────────────────────────

    def capture_iso_template(
        self,
        timeout_ms: int = 10_000,
        min_quality: int = QUALITY_MIN,
    ) -> tuple[bool, int, bytes | None, bool]:
        """
        Wait for a finger, capture raw image, extract ISO template.

        Returns
        -------
        (success, quality, iso_template_bytes, is_timeout)
          success           : True if capture + extraction succeeded
          quality           : 0–100 score (0 means failure / no image)
          iso_template_bytes: bytes object or None on failure
          is_timeout        : True when no finger was placed (normal) —
                              caller must NOT count this as a device error
        """
        if self.is_demo:
            ok, q, t = self._demo_capture()
            # _demo_capture returns (False, 0, None) for a simulated timeout
            is_timeout = (not ok and t is None)
            return ok, q, t, is_timeout

        try:
            # AutoCapture: ref param is returned as second element of tuple
            ret, fd = self._mfs.AutoCapture(
                _FingerDataClass(), timeout_ms, False, True
            )
        except Exception as exc:
            print(f"[MFS100] AutoCapture raised: {exc}")
            return False, 0, None, False   # real exception → is_timeout=False

        if ret != RET_SUCCESS:
            is_timeout = ret in _TIMEOUT_RET_CODES
            quality    = self._safe_quality(fd)
            if is_timeout:
                # Normal idle — no finger placed.  Only log at high verbosity.
                # Uncomment next line temporarily to discover your SDK's timeout code:
                # print(f"[MFS100] DEBUG timeout ret={ret}")
                pass
            else:
                msg = self._safe_error_msg(ret)
                print(f"[MFS100] AutoCapture ERROR ret={ret} — {msg}")
            return False, quality, None, is_timeout

        quality = self._safe_quality(fd)

        # Extract ISO template
        try:
            iso_bytes = bytes(fd.ISOTemplate)
        except Exception as exc:
            print(f"[MFS100] ISOTemplate conversion failed: {exc}")
            return False, quality, None, False

        if not iso_bytes:
            print("[MFS100] ISOTemplate is empty")
            return False, quality, None, False

        print(f"[MFS100] Capture OK  quality={quality}  ISO={len(iso_bytes)} bytes")
        return True, quality, iso_bytes, False

    def get_live_frame(self) -> bytes | None:
        """
        Return a raw greyscale preview frame (for live video display).
        Returns None if unavailable (the .NET SDK handles preview via events).
        """
        if self.is_demo:
            w, h = self._width or 300, self._height or 400
            return bytes(random.getrandbits(8) for _ in range(w * h))
        return None  # .NET SDK uses event-driven preview, not polling

    # ── Matching ──────────────────────────────────────────────────────────────

    def match_iso(
        self,
        template_a: bytes,
        template_b: bytes,
        security_level: int = SECURITY_LEVEL,
    ) -> tuple[bool, int]:
        """
        1:1 compare two ISO templates.

        Returns
        -------
        (matched, score)
          matched : True if fingerprints match (score >= MATCH_THRESHOLD)
          score   : Matching score (0–10000), or negative on error
        """
        if self.is_demo:
            return self._demo_match(template_a, template_b)

        try:
            import System
            # Convert Python bytes → .NET byte arrays
            arr_a = System.Array[System.Byte](list(template_a))
            arr_b = System.Array[System.Byte](list(template_b))
            # MatchISO(probe, gallery, out score) → returns (ret, score)
            ret, score = self._mfs.MatchISO(arr_a, arr_b, 0)
            print(f"[MFS100] MatchISO ret={ret} score={score}")
            # ret=0 indicates the match operation completed successfully (no error).
            # The match decision must be made by checking if score >= MATCH_THRESHOLD.
            matched = (ret == RET_SUCCESS and score >= MATCH_THRESHOLD)
            return matched, score
        except Exception as exc:
            print(f"[MFS100] MatchISO raised: {exc}")
            return False, -1

    # ── Convenience aliases ───────────────────────────────────────────────────

    def match(
        self,
        template_a: bytes,
        template_b: bytes,
        security_level: int = SECURITY_LEVEL,
    ) -> tuple[bool, int]:
        """Alias for match_iso — keeps attendance.py interface stable."""
        return self.match_iso(template_a, template_b, security_level)

    def capture_template(
        self,
        timeout_ms: int = 10_000,
    ) -> tuple[bool, int, bytes | None]:
        """Alias for capture_iso_template — keeps enroll.py interface stable.

        Strips the 4th `is_timeout` value so callers that unpack (ok, quality, template)
        are not broken.  Only scanner._loop needs the full 4-tuple.
        """
        ok, quality, template, _is_timeout = self.capture_iso_template(timeout_ms=timeout_ms)
        return ok, quality, template

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _safe_quality(self, fd) -> int:
        """Extract quality from a FingerData object safely."""
        try:
            q = int(fd.Quality)
            # Clamp: valid range is 0–100; negative = SDK error code, map to 0
            return max(0, min(100, q))
        except Exception:
            return 0

    def _safe_error_msg(self, ret: int) -> str:
        """Get human-readable error string from return code."""
        try:
            return str(self._mfs.GetErrorMsg(ret))
        except Exception:
            return f"Error code {ret}"

    # =========================================================================
    # Demo-mode helpers
    # =========================================================================

    def _demo_capture(self) -> tuple[bool, int, bytes]:
        # Simulate the hardware blocking for ~1 second (as real AutoCapture does).
        # 90 % of the time: no finger placed — return timeout.
        # 10 % of the time: simulate a finger scan.
        time.sleep(1.0)
        if random.random() < 0.90:
            return False, 0, None  # simulated timeout (is_timeout handled by caller)
        quality  = random.randint(70, 95)
        template = bytes(random.getrandbits(8) for _ in range(1566))
        return True, quality, template

    def _demo_match(self, a: bytes, b: bytes) -> tuple[bool, int]:
        matched = (a[:8] == b[:8])
        score = 10000 if matched else 0
        return matched, score
