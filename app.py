"""
app.py
──────
HazariTracker Bio — Main Application

Close behaviour: minimises to system tray (scanner keeps running).
Right-click tray icon → Show / Exit.
"""

import tkinter as tk
from tkinter import ttk
import threading
import sys
import os

import db
db.init_db()

from mfs100_sdk import MFS100
from theme import *
from pages.scanner import ScannerPage
from pages.enroll  import EnrollPage
from pages.reports import ReportsPage
from pages.sso     import SSOPage, SSOLoginFrame
import sso_client
from version import VERSION as APP_VERSION


class HazariTrackerApp(tk.Tk):

    APP_TITLE = "HazariTracker Bio"
    VERSION   = APP_VERSION

    def __init__(self):
        super().__init__()
        self.title(f"{self.APP_TITLE}  v{self.VERSION}")
        self.geometry("1060x680")
        self.minsize(900, 600)
        self.configure(bg=BG_BASE)
        self._centre()
        self._apply_ttk()

        # Set Window Icon
        icon_path = "icon.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self._tray_icon = None
        self._login_frame = None

        # Load SDK (no USB yet — fast)
        self.sdk = MFS100()

        if sso_client.is_authenticated():
            self._show_main_app()
        else:
            self._show_login_screen()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start auto-update check in background after window initializes
        from updater import AutoUpdater
        self.updater = AutoUpdater(self)
        self.after(2000, self.updater.start_check)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        self._build_nav()
        self._build_content()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_SURFACE, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        brand = tk.Frame(hdr, bg=BG_SURFACE)
        brand.pack(side="left", padx=PAD_LG, pady=PAD_SM)
        tk.Label(brand, text="Hazari",   font=FONT_H1,
                 bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(brand, text="Tracker",  font=FONT_H1,
                 bg=BG_SURFACE, fg=ACCENT).pack(side="left")
        tk.Label(brand, text=" Bio",     font=(FONT_FAMILY, 13),
                 bg=BG_SURFACE, fg=TEXT_SECONDARY).pack(side="left", pady=(6, 0))

        right = tk.Frame(hdr, bg=BG_SURFACE)
        right.pack(side="right", padx=PAD_LG)
        
        self._badge = tk.Label(right, text="Initialising…",
                               font=FONT_SMALL, bg=BG_SURFACE,
                               fg=TEXT_SECONDARY)
        self._badge.pack(side="right", padx=(PAD_MD, 0))
        
        self._cloud_badge = tk.Label(right, text="○ Cloud Sync Disabled",
                                     font=FONT_SMALL, bg=BG_SURFACE,
                                     fg=TEXT_DISABLED)
        self._cloud_badge.pack(side="right")

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _update_cloud_badge(self):
        if sso_client.is_authenticated():
            user = sso_client.get_user_info()
            name = user.get("name", "Connected") if user else "Connected"
            self._cloud_badge.config(text=f"● Cloud Sync: {name}", fg=SUCCESS)
        else:
            self._cloud_badge.config(text="○ Cloud Sync Disabled", fg=TEXT_DISABLED)

    def _build_nav(self):
        nav = tk.Frame(self, bg=BG_SURFACE, height=42)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        self._nav_btns = {}
        for key, label in [("scanner", "  🖐  Scanner  "),
                            ("enroll",  "  👤  Employees  "),
                            ("reports", "  📋  Reports  "),
                            ("sso",     "  ☁  Cloud Sync  ")]:
            b = tk.Button(nav, text=label, font=FONT_H3,
                          bg=BG_SURFACE, fg=TEXT_SECONDARY,
                          relief="flat", bd=0, padx=PAD_SM,
                          cursor="hand2",
                          command=lambda k=key: self._show(k))
            b.pack(side="left")
            self._nav_btns[key] = b

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_content(self):
        self._content = tk.Frame(self, bg=BG_BASE)
        self._content.pack(fill="both", expand=True)

        self._scanner_page = ScannerPage(self._content, sdk=self.sdk)
        self._enroll_page  = EnrollPage (self._content, sdk=self.sdk)
        self._reports_page = ReportsPage(self._content)
        self._sso_page     = SSOPage(self._content)

        self._pages = {"scanner": self._scanner_page,
                       "enroll":  self._enroll_page,
                       "reports": self._reports_page,
                       "sso":     self._sso_page}
        self._show("scanner")

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_SURFACE, height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom")

        tk.Label(bar,
                 text=f"  {self.APP_TITLE} v{self.VERSION}  ·  {db.DB_PATH}",
                 font=FONT_SMALL, bg=BG_SURFACE,
                 fg=TEXT_DISABLED).pack(side="left", padx=4)

        mode_lbl = tk.Label(bar,
                             text="DEMO  " if self.sdk.is_demo else "LIVE  ",
                             font=FONT_SMALL, bg=BG_SURFACE,
                             fg=WARNING if self.sdk.is_demo else SUCCESS)
        mode_lbl.pack(side="right")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show(self, key: str):
        # 1. Stop scanning thread if leaving scanner page
        if hasattr(self, "_scanner_page") and self._scanner_page:
            self._scanner_page.stop()

        for page in self._pages.values():
            page.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for k, btn in self._nav_btns.items():
            btn.config(bg=BG_ELEVATED if k == key else BG_SURFACE,
                       fg=ACCENT       if k == key else TEXT_SECONDARY)

        # 2. Start scanner if entering scanner page
        if key == "scanner":
            self._scanner_page.start()
        elif key == "enroll":
            self._enroll_page.refresh()
        elif key == "reports":
            self._reports_page.refresh()
        elif key == "sso":
            self._sso_page.refresh()

    def _show_main_app(self):
        if self._login_frame:
            self._login_frame.destroy()
            self._login_frame = None

        # Clean up any residual widgets
        for child in self.winfo_children():
            child.destroy()

        self._build()
        self._update_cloud_badge()

        # Start employee template synchronization and schedule periodic sync
        self._run_periodic_sync()

        if not self.sdk.is_demo:
            self.after(250, self._init_device)
        else:
            self._update_badge(False)
            self._scanner_page.start()

    def _run_periodic_sync(self):
        if not sso_client.is_authenticated():
            return
        
        def sync_worker():
            print("[AutoSync] Running periodic employee template sync...")
            ok, msg = sso_client.sync_employees_from_server()
            if ok:
                print(f"[AutoSync] {msg}")
                if hasattr(self, "_enroll_page") and self._enroll_page:
                    try:
                        self.after(0, self._enroll_page.refresh)
                    except Exception:
                        pass
            else:
                print(f"[AutoSync] Failed: {msg}")
            
            # Reschedule in 60 seconds (60000 ms)
            try:
                self.after(60000, self._run_periodic_sync)
            except Exception:
                pass

        threading.Thread(target=sync_worker, daemon=True).start()

    def _show_login_screen(self):
        if self._login_frame:
            return  # already showing login screen

        # Stop scanner and close device
        if hasattr(self, "_scanner_page") and self._scanner_page:
            try:
                self._scanner_page.stop()
            except Exception:
                pass
        try:
            self.sdk.close_device()
        except Exception:
            pass

        # Destroy all main widgets
        for child in self.winfo_children():
            child.destroy()

        self._nav_btns = {}
        self._pages = {}

        self._login_frame = SSOLoginFrame(self)
        self._login_frame.pack(fill="both", expand=True)

    def check_auth(self):
        """Verify auth status and update the UI accordingly."""
        if not sso_client.is_authenticated():
            self.after(0, self._show_login_screen)
        else:
            self.after(0, self._update_cloud_badge)
            if hasattr(self, "_sso_page"):
                self.after(0, self._sso_page.refresh)

    # ── Device init ───────────────────────────────────────────────────────────

    def _init_device(self):
        ok, msg = self.sdk.init_device()
        self._update_badge(ok)
        if ok:
            self._scanner_page.start()
        else:
            if not self._login_frame:
                self.after(3000, self._init_device)

    def _update_badge(self, connected: bool):
        try:
            if self.sdk.is_demo:
                text, col = "DEMO MODE", WARNING
            elif connected:
                text, col = "● MFS100 Connected", SUCCESS
            else:
                text, col = "○ Connect MFS100…", DANGER
            self._badge.config(text=text, fg=col)
        except Exception:
            pass

    # ── System Tray ───────────────────────────────────────────────────────────

    def _on_close(self):
        """Hide window to tray (if logged in), otherwise exit."""
        if self._login_frame:
            self._quit_app()
        else:
            self.withdraw()
            self._show_tray()

    def _show_tray(self):
        """Create/show system tray icon."""
        if self._tray_icon is not None:
            return   # already in tray

        try:
            import pystray
            from PIL import Image, ImageDraw, ImageFont

            # Try to load icon.png or fallback to generating one
            icon_png_path = "icon.png"
            if hasattr(sys, "_MEIPASS"):
                icon_png_path = os.path.join(sys._MEIPASS, "icon.png")

            if os.path.exists(icon_png_path):
                try:
                    img = Image.open(icon_png_path)
                except Exception:
                    img = None
            else:
                img = None

            if img is None:
                # Build a simple orange circle icon (64×64) fallback
                size = 64
                img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse([4, 4, 60, 60], fill="#FF6B00")
                # White "H" letter
                try:
                    draw.text((20, 16), "H", fill="white",
                              font=ImageFont.truetype("segoeui.ttf", 30))
                except Exception:
                    draw.text((22, 18), "H", fill="white")

            def on_show(icon, item):
                icon.stop()
                self._tray_icon = None
                self.after(0, self._restore_window)

            def on_exit(icon, item):
                icon.stop()
                self._tray_icon = None
                self.after(0, self._quit_app)

            menu = pystray.Menu(
                pystray.MenuItem("Show HazariTracker Bio", on_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", on_exit),
            )

            self._tray_icon = pystray.Icon(
                "HazariTracker Bio", img,
                "HazariTracker Bio — Scanner running", menu
            )

            t = threading.Thread(target=self._tray_icon.run, daemon=True)
            t.start()

        except ImportError:
            # pystray not installed — just minimise instead
            self.iconify()

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self):
        if hasattr(self, "_scanner_page") and self._scanner_page:
            try:
                self._scanner_page.stop()
            except Exception:
                pass
        try:
            self.sdk.close_device()
        except Exception:
            pass
        self.destroy()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _centre(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1060x680+{(sw-1060)//2}+{(sh-680)//2}")

    def _apply_ttk(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".",
                        background=BG_BASE, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_INPUT, font=FONT_BODY,
                        troughcolor=BG_ELEVATED,
                        selectbackground=ACCENT, selectforeground=TEXT_PRIMARY)
        style.configure("TSeparator", background=BORDER)
        style.configure("TEntry",
                        fieldbackground=BG_INPUT, foreground=TEXT_PRIMARY,
                        insertcolor=TEXT_PRIMARY, bordercolor=BORDER, padding=6)
        style.configure("Treeview",
                        background=BG_SURFACE, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_SURFACE,
                        rowheight=28, borderwidth=0, font=FONT_BODY)
        style.configure("Treeview.Heading",
                        background=BG_ELEVATED, foreground=TEXT_SECONDARY,
                        font=FONT_H3, borderwidth=0, relief="flat")
        style.map("Treeview",
                  background=[("selected", ACCENT_DARK)],
                  foreground=[("selected", TEXT_PRIMARY)])
        style.configure("Vertical.TScrollbar",
                        background=BG_ELEVATED, troughcolor=BG_SURFACE,
                        arrowcolor=TEXT_SECONDARY, width=8)


if __name__ == "__main__":
    app = HazariTrackerApp()
    app.mainloop()
