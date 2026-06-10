"""
pages/scanner.py
────────────────
Auto-continuous fingerprint scanner.

Performance design
──────────────────
  • AutoCapture(timeout=5000) already blocks for 5 s waiting for a finger.
    On timeout (no finger) we just loop — NO reinit. Reinit only happens
    after a successful capture, as the hardware needs a reset between scans.
  • Background thread yields with time.sleep(0.05) on error paths to avoid
    tight CPU-spin on repeated failures.
  • All UI updates go via self.after(0, …) — never touch widgets from the
    background thread.

API hook: override _api_punch() with your HTTP call when ready.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk
from datetime import datetime

import db
from mfs100_sdk import MFS100
from theme import *


class ScannerPage(tk.Frame):

    def __init__(self, master, sdk: MFS100, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self.sdk      = sdk
        self._running = False
        self._thread  = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header strip
        hdr = tk.Frame(self, bg=BG_SURFACE, pady=PAD_MD)
        hdr.pack(fill="x")
        tk.Label(hdr, text="● AUTO FINGERPRINT SCANNER",
                 font=FONT_H3, bg=BG_SURFACE, fg=ACCENT).pack()
        tk.Label(hdr, text="Place your finger anytime — continuous detection",
                 font=FONT_SMALL, bg=BG_SURFACE, fg=TEXT_SECONDARY).pack()

        # Centre area
        centre = tk.Frame(self, bg=BG_BASE)
        centre.pack(expand=True, fill="both")

        self._canvas = _FingerprintRing(centre)
        self._canvas.pack(pady=(PAD_XL, PAD_MD))

        self._name_var = tk.StringVar(value="Waiting for finger…")
        tk.Label(centre, textvariable=self._name_var,
                 font=FONT_LARGE, bg=BG_BASE, fg=TEXT_PRIMARY).pack()

        self._sub_var = tk.StringVar(value="")
        tk.Label(centre, textvariable=self._sub_var,
                 font=FONT_H3, bg=BG_BASE, fg=TEXT_SECONDARY).pack(pady=(PAD_SM, 0))

        self._badge_var = tk.StringVar(value="")
        self._badge_lbl = tk.Label(centre, textvariable=self._badge_var,
                                   font=FONT_H2, bg=BG_BASE,
                                   fg=ACCENT, padx=PAD_MD, pady=PAD_SM)
        self._badge_lbl.pack(pady=(PAD_SM, 0))

        # Bottom last-scan strip
        strip = tk.Frame(self, bg=BG_ELEVATED, pady=PAD_SM)
        strip.pack(fill="x", side="bottom")
        self._last_var = tk.StringVar(value="Last scan: —")
        tk.Label(strip, textvariable=self._last_var,
                 font=FONT_SMALL, bg=BG_ELEVATED, fg=TEXT_SECONDARY).pack()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Start continuous scan loop. Safe to call multiple times."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the loop to exit on next iteration."""
        self._running = False

    # ── Scan loop (background thread) ─────────────────────────────────────────

    def _loop(self):
        """
        Optimised loop:
          - AutoCapture blocks for up to 5 s internally.
          - No reinit on timeout — only reinit after a REAL scan.
          - Small yield (0.05 s) on errors to avoid CPU spin.
        """
        while self._running:
            self.after(0, self._ui_scanning)

            try:
                ok, quality, template = self.sdk.capture_iso_template(timeout_ms=5000)
            except Exception as exc:
                print(f"[Scanner] capture error: {exc}")
                time.sleep(0.5)
                continue

            if not self._running:
                break

            # ── Timeout / no finger: loop immediately, no reinit ──────────────
            if not ok or template is None:
                time.sleep(0.05)   # tiny yield — prevents tight spin on fast errors
                continue

            # ── Real scan captured ────────────────────────────────────────────
            ts    = datetime.now().strftime("%H:%M:%S")
            match = self._find_match(template)

            if match:
                self.after(0, self._ui_success, match, ts, quality)
                db.log_attendance(match["emp_id"], match["name"], "check_in", quality)
                self._api_punch(match, ts)
            else:
                self.after(0, self._ui_unknown, ts)

            # Show result for 2 seconds
            time.sleep(2)

            if not self._running:
                break

            # Reinit hardware (only after a real scan)
            self.after(0, self._ui_reinit)
            self.sdk.close_device()
            time.sleep(0.4)
            ok2, _ = self.sdk.init_device()
            if not ok2:
                # Device temporarily unavailable — wait before retrying
                time.sleep(3)

    # ── Matching ──────────────────────────────────────────────────────────────

    def _find_match(self, template: bytes) -> dict | None:
        """Compare template against every enrolled employee."""
        for emp_id, name, stored in db.get_all_templates():
            if not stored:
                continue
            try:
                matched, _ = self.sdk.match_iso(stored, template)
                if matched:
                    return {"emp_id": emp_id, "name": name}
            except Exception:
                continue
        return None

    # ── API hook ──────────────────────────────────────────────────────────────

    def _api_punch(self, employee: dict, timestamp: str):
        """TODO: Replace with your HTTP API call when ready."""
        print(f"[API] PUNCH  {employee['emp_id']}  {employee['name']}  {timestamp}")

    # ── UI helpers (always called via after()) ────────────────────────────────

    def _ui_scanning(self):
        self._canvas.set_state("scanning")
        self._name_var.set("Waiting for finger…")
        self._sub_var.set("")
        self._badge_var.set("")
        self._badge_lbl.config(fg=ACCENT)

    def _ui_success(self, emp: dict, ts: str, quality: int):
        self._canvas.set_state("success")
        self._name_var.set(emp["name"])
        self._sub_var.set(f"Employee  ·  {emp['emp_id']}")
        self._badge_var.set(f"✓  PUNCHED IN   {ts}")
        self._badge_lbl.config(fg=SUCCESS)
        self._last_var.set(
            f"Last scan: {ts}  ·  {emp['name']}  ·  Quality {quality}  ✓"
        )

    def _ui_unknown(self, ts: str):
        self._canvas.set_state("failure")
        self._name_var.set("Unknown Employee")
        self._sub_var.set("Fingerprint not registered in system")
        self._badge_var.set("✗  NOT RECOGNISED")
        self._badge_lbl.config(fg=DANGER)
        self._last_var.set(f"Last scan: {ts}  ·  Unknown  ✗")

    def _ui_reinit(self):
        self._canvas.set_state("idle")
        self._name_var.set("Reinitialising scanner…")
        self._sub_var.set("")
        self._badge_var.set("")


# ─────────────────────────────────────────────────────────────────────────────
# Animated fingerprint ring widget
# ─────────────────────────────────────────────────────────────────────────────

class _FingerprintRing(tk.Canvas):
    SIZE = 220
    CX = CY = 110

    def __init__(self, master, **kw):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         bg=BG_BASE, highlightthickness=0, **kw)
        self._state     = "idle"
        self._angle     = 0.0
        self._pulse     = 1.0
        self._pulse_dir = 0.018
        self._after     = None
        self._draw()

    def set_state(self, state: str):
        self._state = state
        if self._after:
            self.after_cancel(self._after)
            self._after = None
        self._angle = 0.0
        self._pulse = 1.0
        if state == "scanning":
            self._animate()
        else:
            self._draw()

    def _animate(self):
        self._angle = (self._angle + 5) % 360
        self._pulse += self._pulse_dir
        if self._pulse > 1.12 or self._pulse < 0.88:
            self._pulse_dir *= -1
        self._draw()
        if self._state == "scanning":
            self._after = self.after(33, self._animate)   # ~30 fps

    def _draw(self):
        self.delete("all")
        s   = self._state
        cx  = cy = self.CX
        r   = int(90 * (self._pulse if s == "scanning" else 1.0))
        pad = self.CX - r

        bg_c, ring_c = {
            "idle":     (BG_ELEVATED, BORDER),
            "scanning": (BG_ELEVATED, ACCENT),
            "success":  ("#0A2A15",   SUCCESS),
            "failure":  ("#2A0A0A",   DANGER),
        }.get(s, (BG_ELEVATED, BORDER))

        # Outer glow ring (scanning only)
        if s == "scanning":
            gp = max(pad - 10, 0)
            self.create_oval(gp, gp, self.SIZE - gp, self.SIZE - gp,
                             outline=ACCENT, width=1, fill="")

        # Background + main ring
        self.create_oval(pad, pad, self.SIZE - pad, self.SIZE - pad,
                         fill=bg_c, outline="")
        self.create_oval(pad, pad, self.SIZE - pad, self.SIZE - pad,
                         outline=ring_c, width=4, fill="")

        # Spinning arc
        if s == "scanning":
            self.create_arc(pad, pad, self.SIZE - pad, self.SIZE - pad,
                            start=-self._angle, extent=100,
                            outline=ACCENT, width=5, style="arc")
            # Fingerprint ridges
            for rad in range(20, 55, 11):
                self.create_arc(cx - rad, cy - rad, cx + rad, cy + rad,
                                start=50, extent=260,
                                outline=ACCENT, width=1.5, style="arc")

        elif s == "idle":
            for rad in range(20, 55, 11):
                self.create_arc(cx - rad, cy - rad, cx + rad, cy + rad,
                                start=50, extent=260,
                                outline=TEXT_DISABLED, width=1, style="arc")

        elif s == "success":
            pts = [cx - 28, cy, cx - 8, cy + 22, cx + 28, cy - 18]
            self.create_line(*pts, fill=SUCCESS, width=5,
                             joinstyle="round", capstyle="round")

        elif s == "failure":
            d = 24
            self.create_line(cx-d, cy-d, cx+d, cy+d,
                             fill=DANGER, width=5, capstyle="round")
            self.create_line(cx+d, cy-d, cx-d, cy+d,
                             fill=DANGER, width=5, capstyle="round")
