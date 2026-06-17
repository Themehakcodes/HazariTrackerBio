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
import winsound

import db
import sso_client
from mfs100_sdk import MFS100
from theme import *

# Cooldown period (in seconds) to prevent accidental double punches
PUNCH_COOLDOWN_SECONDS = 300

def play_beep_success():
    try:
        # A nice clean high double beep
        winsound.Beep(1800, 150)
        winsound.Beep(2200, 150)
    except Exception:
        pass

def play_beep_warning():
    try:
        # A medium warning beep
        winsound.Beep(1000, 400)
    except Exception:
        pass

def play_beep_error():
    try:
        # A low error beep
        winsound.Beep(440, 500)
    except Exception:
        pass



class ScannerPage(tk.Frame):

    def __init__(self, master, sdk: MFS100, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self.sdk      = sdk
        self._running = False
        self._thread  = None
        self._last_punch_time = {}  # Keep track of last punch timestamp per employee ID
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
          - Reinit after a successful capture, as the hardware needs a reset between scans.
          - Check connection on failure and attempt automatic reconnection.
        """
        while self._running:
            self.after(0, self._ui_scanning)

            try:
                ok, quality, template = self.sdk.capture_iso_template(timeout_ms=1000)
                device_error = False
            except Exception as exc:
                print(f"[Scanner] capture error: {exc}")
                ok = False
                template = None
                device_error = True

            if not self._running:
                break

            # ── Check for disconnection or hardware failure ──────────────
            if not ok or template is None:
                is_connected = False
                try:
                    is_connected = self.sdk.is_connected()
                except Exception:
                    pass

                if not self.sdk.is_demo and (not is_connected or device_error):
                    print("[Scanner] Device disconnected or errored! Attempting recovery...")
                    self.after(0, lambda: self.master.master._update_badge(False))
                    self.after(0, self._ui_disconnected)

                    # Poll until device is reconnected
                    while self._running:
                        time.sleep(1.0)
                        try:
                            if self.sdk.is_connected():
                                break
                        except Exception:
                            pass
                    
                    if not self._running:
                        break

                    print("[Scanner] Device physically reconnected. Re-initializing...")
                    try:
                        self.sdk.close_device()
                        time.sleep(0.5)
                        init_ok, init_msg = self.sdk.init_device()
                        if init_ok:
                            print("[Scanner] Re-initialization successful.")
                            self.after(0, lambda: self.master.master._update_badge(True))
                            self.after(0, self._ui_scanning)
                            continue
                        else:
                            print(f"[Scanner] Re-initialization failed: {init_msg}")
                    except Exception as e:
                        print(f"[Scanner] Re-initialization error: {e}")
                    
                    time.sleep(1.0)
                    continue
                else:
                    # Normal timeout (no finger), back off briefly and continue
                    time.sleep(0.5)
                    continue

            # ── Real scan captured ────────────────────────────────────────────
            ts    = datetime.now().strftime("%H:%M:%S")
            match = self._find_match(template)

            if match:
                emp_id = match["emp_id"]
                name   = match["name"]
                now    = time.time()

                # Prevent instant double-punching (cooldown check)
                last_punch = self._last_punch_time.get(emp_id, 0.0)
                elapsed = now - last_punch
                if elapsed < PUNCH_COOLDOWN_SECONDS:
                    play_beep_warning()
                    remaining = int(PUNCH_COOLDOWN_SECONDS - elapsed)
                    rem_min = remaining // 60
                    rem_sec = remaining % 60
                    if rem_min > 0:
                        api_msg = f"Recent punch. Wait {rem_min}m {rem_sec}s."
                    else:
                        api_msg = f"Recent punch. Wait {rem_sec}s."
                    
                    self.after(0, self._ui_success, match, ts, quality, "already", api_msg)
                    time.sleep(2)
                    
                    # Reinit hardware even for cooldown capture, to reset state
                    if not self.sdk.is_demo:
                        try:
                            self.sdk.close_device()
                            time.sleep(0.4)
                            self.sdk.init_device()
                        except Exception:
                            pass
                            
                    if not self._running:
                        break
                    self.after(0, self._ui_reinit)
                    time.sleep(0.1)
                    continue

                # 1. Sync with server first (synchronously in background thread)
                success, res = sso_client.send_punch_to_server(emp_id)
                
                # Determine event type based on server response, fallback to local DB check
                event_type = "check_in"
                api_msg = ""
                if success and isinstance(res, dict):
                    server_type = res.get("punch_type")
                    api_msg = res.get("message", "")
                    if server_type == "out":
                        event_type = "check_out"
                    elif server_type == "in":
                        event_type = "check_in"
                    elif server_type == "already":
                        event_type = "already"
                else:
                    # Offline / error fallback: local check
                    if db.already_checked_in_today(emp_id) and not db.already_checked_out_today(emp_id):
                        event_type = "check_out"
                    else:
                        event_type = "check_in"
                        
                    if not success and res == "Unauthorized":
                        # Redirect to login
                        self.after(0, self._handle_unauthorized)
                    elif not success:
                        api_msg = str(res)

                # 2. Log in local DB (if check_in or check_out)
                if event_type in ("check_in", "check_out"):
                    db.log_attendance(emp_id, name, event_type, quality)
                    # Mark successful punch timestamp to start cooldown
                    self._last_punch_time[emp_id] = now

                # Play sound feedback
                if success and isinstance(res, dict) and res.get("punch_type") == "already":
                    play_beep_warning()
                elif success:
                    play_beep_success()
                else:
                    play_beep_warning()

                # 3. Update UI
                self.after(0, self._ui_success, match, ts, quality, event_type, api_msg)
            else:
                play_beep_error()
                self.after(0, self._ui_unknown, ts)

            # Show result for 2 seconds
            time.sleep(2)

            # Re-init hardware after capture to reset state and leave it ready
            if not self.sdk.is_demo:
                try:
                    self.sdk.close_device()
                    time.sleep(0.4)
                    self.sdk.init_device()
                except Exception as exc:
                    print(f"[Scanner] Re-init device failed: {exc}")

            if not self._running:
                break

            # Reinit UI state (keep hardware open for high-speed scanning)
            self.after(0, self._ui_reinit)
            time.sleep(0.1)

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

    def _handle_unauthorized(self):
        """Redirect the app to the login screen upon session expiry."""
        try:
            self.master.master.check_auth()
        except Exception:
            pass

    # ── UI helpers (always called via after()) ────────────────────────────────

    def _ui_scanning(self):
        self._canvas.set_state("scanning")
        self._name_var.set("Waiting for finger…")
        self._sub_var.set("")
        self._badge_var.set("")
        self._badge_lbl.config(fg=ACCENT)

    def _ui_success(self, emp: dict, ts: str, quality: int, event_type: str = "check_in", api_msg: str = ""):
        self._canvas.set_state("success" if event_type != "already" else "idle")
        self._name_var.set(emp["name"])
        
        if api_msg:
            self._sub_var.set(f"{api_msg}  ·  {emp['emp_id']}")
        else:
            self._sub_var.set(f"Employee  ·  {emp['emp_id']}")
        
        if event_type == "check_in":
            status_text = "PUNCHED IN"
            fg_col = SUCCESS
        elif event_type == "check_out":
            status_text = "PUNCHED OUT"
            fg_col = SUCCESS
        elif event_type == "already":
            status_text = "ALREADY RECORDED"
            fg_col = WARNING
        else:
            status_text = "SUCCESS"
            fg_col = SUCCESS

        self._badge_var.set(f"✓  {status_text}   {ts}")
        self._badge_lbl.config(fg=fg_col)
        self._last_var.set(
            f"Last scan: {ts}  ·  {emp['name']}  ·  {status_text}  ·  Quality {quality}  ✓"
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

    def _ui_disconnected(self):
        self._canvas.set_state("failure")
        self._name_var.set("Scanner Disconnected")
        self._sub_var.set("Please check the USB connection")
        self._badge_var.set("✗  DEVICE OFFLINE")
        self._badge_lbl.config(fg=DANGER)



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
