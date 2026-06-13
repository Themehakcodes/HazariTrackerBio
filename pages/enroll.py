"""
pages/enroll.py
───────────────
Add New Employee — simple form + fingerprint scan + employee list.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

import db
import sso_client
from mfs100_sdk import MFS100, QUALITY_MIN
from theme import *


class EnrollPage(tk.Frame):

    def __init__(self, master, sdk: MFS100, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self.sdk = sdk
        self._scanning = False
        self._sync_in_progress = False
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left: form ───────────────────────────────────────────────────────
        left = tk.Frame(self, bg=BG_SURFACE, padx=PAD_LG, pady=PAD_LG)
        left.pack(side="left", fill="both", expand=True,
                  padx=(PAD_MD, PAD_SM), pady=PAD_MD)

        tk.Label(left, text="Add New Employee",
                 font=FONT_H2, bg=BG_SURFACE,
                 fg=TEXT_PRIMARY).pack(anchor="w")
        tk.Label(left, text="Fill in details and scan fingerprint",
                 font=FONT_SMALL, bg=BG_SURFACE,
                 fg=TEXT_SECONDARY).pack(anchor="w")
        tk.Frame(left, bg=ACCENT, height=2).pack(fill="x", pady=(PAD_SM, PAD_LG))

        self._emp_id = self._field(left, "Employee ID  *", "e.g. EMP001")
        self._name   = self._field(left, "Full Name  *",   "e.g. Rahul Sharma")
        self._dept   = self._field(left, "Department",     "e.g. IT / Sales / HR")

        # Re-enroll checkbox
        self._re_enroll = tk.BooleanVar()
        tk.Checkbutton(left, text="Re-enroll (overwrite existing fingerprint)",
                       variable=self._re_enroll,
                       bg=BG_SURFACE, fg=TEXT_SECONDARY,
                       selectcolor=BG_INPUT,
                       activebackground=BG_SURFACE,
                       activeforeground=TEXT_SECONDARY,
                       font=FONT_SMALL, cursor="hand2").pack(anchor="w", pady=(PAD_SM, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=PAD_MD)

        # Buttons
        row = tk.Frame(left, bg=BG_SURFACE)
        row.pack(fill="x")
        
        self._btn = self._create_hover_btn(row, "🖐  Start Fingerprint Scan",
                                           ACCENT, TEXT_PRIMARY, self._start_scan,
                                           hover_bg=ACCENT_HOVER)
        self._btn.pack(side="left", padx=(0, PAD_SM))
        
        clear_btn = self._create_hover_btn(row, "Clear",
                                            BG_ELEVATED, TEXT_PRIMARY, self._clear,
                                            hover_bg="#2F2F2F")
        clear_btn.pack(side="left")

        # Status
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(left, textvariable=self._status_var,
                                    font=FONT_BODY, bg=BG_SURFACE,
                                    fg=TEXT_SECONDARY)
        self._status_lbl.pack(anchor="w", pady=(PAD_MD, 0))

        # Quality bar
        self._quality_var = tk.StringVar(value="Quality: —")
        tk.Label(left, textvariable=self._quality_var,
                 font=FONT_SMALL, bg=BG_SURFACE,
                 fg=TEXT_DISABLED).pack(anchor="w")

        if self.sdk.is_demo:
            tk.Label(left, text="⚠  DEMO MODE — no real device",
                     font=FONT_SMALL, bg=BG_SURFACE, fg=WARNING).pack(anchor="w")

        # ── Right: finger indicator + employee list ───────────────────────────
        right = tk.Frame(self, bg=BG_BASE, padx=PAD_MD, pady=PAD_MD)
        right.pack(side="right", fill="both", expand=True,
                   padx=(PAD_SM, PAD_MD), pady=PAD_MD)

        tk.Label(right, text="Fingerprint Status", font=FONT_H3,
                 bg=BG_BASE, fg=TEXT_SECONDARY).pack()

        self._ring = _SmallRing(right)
        self._ring.pack(pady=(PAD_SM, PAD_MD))

        # Header for Enrolled Employees with title and refresh button!
        header_row = tk.Frame(right, bg=BG_BASE)
        header_row.pack(fill="x", anchor="w", pady=(PAD_MD, 0))
        
        tk.Label(header_row, text="Enrolled Employees",
                 font=FONT_H3, bg=BG_BASE,
                 fg=TEXT_SECONDARY).pack(side="left")
                 
        self._refresh_btn = tk.Button(header_row, text=" ⟳ ", font=FONT_BODY,
                                      bg=BG_BASE, fg=TEXT_SECONDARY,
                                      activebackground=BG_ELEVATED,
                                      activeforeground=TEXT_PRIMARY,
                                      relief="flat", bd=0, cursor="hand2",
                                      command=self._manual_local_refresh)
        self._refresh_btn.pack(side="left", padx=(PAD_SM, 0))
        self._refresh_btn.bind("<Enter>", lambda e: self._refresh_btn.config(fg=ACCENT))
        self._refresh_btn.bind("<Leave>", lambda e: self._refresh_btn.config(fg=TEXT_SECONDARY))

        # Status label for animated spinner next to the refresh icon
        self._refresh_status_lbl = tk.Label(header_row, text="", font=FONT_SMALL,
                                            bg=BG_BASE, fg=ACCENT)
        self._refresh_status_lbl.pack(side="left", padx=(PAD_MD, 0))

        # Create a frame with 1px border to wrap Treeview beautifully
        tree_border = tk.Frame(right, bg=BORDER, bd=0, padx=1, pady=1)
        tree_border.pack(fill="both", expand=True, pady=(PAD_SM, PAD_SM))

        tree_frame = tk.Frame(tree_border, bg=BG_SURFACE)
        tree_frame.pack(fill="both", expand=True)

        cols = ("emp_id", "name", "dept", "enrolled")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  height=10, selectmode="browse")
        for col, w, label in [
            ("emp_id",   70,  "ID"),
            ("name",    160,  "Name"),
            ("dept",    100,  "Department"),
            ("enrolled", 100, "Enrolled At"),
        ]:
            self._tree.heading(col, text=label)
            self._tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Action buttons row
        btn_row = tk.Frame(right, bg=BG_BASE)
        btn_row.pack(fill="x", pady=(PAD_SM, 0))

        self._sync_btn = self._create_hover_btn(btn_row, "🔄  Sync from Cloud",
                                                ACCENT, TEXT_PRIMARY, self._sync_from_cloud,
                                                hover_bg=ACCENT_HOVER, font=FONT_SMALL,
                                                padx=PAD_SM, pady=6)
        self._sync_btn.pack(side="left")

        remove_btn = self._create_hover_btn(btn_row, "✕  Remove Selected",
                                             DANGER, TEXT_PRIMARY, self._delete_selected,
                                             hover_bg="#EF5F5F", font=FONT_SMALL,
                                             padx=PAD_SM, pady=6)
        remove_btn.pack(side="right")

        self.refresh()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _create_hover_btn(self, parent, text, bg, fg, command, hover_bg=None, font=FONT_H3, padx=PAD_MD, pady=PAD_SM) -> tk.Button:
        btn = tk.Button(parent, text=text, bg=bg, fg=fg, font=font,
                        activebackground=hover_bg or bg,
                        activeforeground=fg,
                        relief="flat", bd=0, padx=padx, pady=pady,
                        cursor="hand2", command=command)
        
        h_bg = hover_bg or bg
        if not hover_bg:
            if bg == ACCENT:
                h_bg = ACCENT_HOVER
            elif bg == DANGER:
                h_bg = "#EF5F5F"
            elif bg == BG_ELEVATED:
                h_bg = "#2F2F2F"
            elif bg == BG_SURFACE:
                h_bg = BG_ELEVATED
            else:
                h_bg = bg
                
        btn.bind("<Enter>", lambda e: btn.config(bg=h_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _on_tree_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0])["values"]
        if vals:
            self._emp_id.config(foreground=TEXT_PRIMARY)
            self._emp_id.delete(0, "end")
            self._emp_id.insert(0, vals[0])

            self._name.config(foreground=TEXT_PRIMARY)
            self._name.delete(0, "end")
            self._name.insert(0, vals[1])

            self._dept.config(foreground=TEXT_PRIMARY)
            self._dept.delete(0, "end")
            self._dept.insert(0, vals[2] if vals[2] != "—" else "")

            is_enrolled = (vals[3] != "No")
            self._re_enroll.set(is_enrolled)

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for emp in db.get_all_employees():
            enrolled_status = (emp["enrolled_at"] or "")[:10] if emp["is_enrolled"] else "No"
            self._tree.insert("", "end", values=(
                emp["emp_id"], emp["name"],
                emp["department"] or "—",
                enrolled_status,
            ))

    def _manual_local_refresh(self):
        self.refresh()
        # Trigger a cloud sync in the background and show the animated spinner
        if sso_client.is_authenticated():
            if self._sync_in_progress:
                return
                
            self._sync_in_progress = True
            self._refresh_btn.config(state="disabled", text=" ⏳ ")
            self._animate_spinner()
            
            def run_sync():
                ok, _ = sso_client.sync_employees_from_server()
                def on_sync_done():
                    self._sync_in_progress = False
                    self.refresh()
                self.after(0, on_sync_done)
            threading.Thread(target=run_sync, daemon=True).start()

    def _field(self, parent, label: str, ph: str = "") -> tk.Entry:
        tk.Label(parent, text=label, font=FONT_SMALL,
                 bg=BG_SURFACE, fg=TEXT_SECONDARY).pack(anchor="w", pady=(PAD_SM, 4))
        
        # Border wrapper frame to create a 1px border
        wrapper = tk.Frame(parent, bg=BORDER, bd=0, padx=1, pady=1)
        wrapper.pack(fill="x", pady=(0, PAD_MD))
        
        inner = tk.Frame(wrapper, bg=BG_INPUT, bd=0, padx=8, pady=6)
        inner.pack(fill="x")
        
        e = tk.Entry(inner, font=FONT_BODY, bg=BG_INPUT, fg=TEXT_PRIMARY,
                     insertbackground=TEXT_PRIMARY, bd=0, relief="flat",
                     highlightthickness=0)
        e.pack(fill="x")
        
        # Focus border change animation!
        def on_focus_in(event, w=wrapper, entry=e):
            w.config(bg=ACCENT)
            if entry.get() == ph:
                entry.delete(0, "end")
                entry.config(foreground=TEXT_PRIMARY)
                
        def on_focus_out(event, w=wrapper, entry=e):
            w.config(bg=BORDER)
            if not entry.get():
                entry.insert(0, ph)
                entry.config(foreground=TEXT_DISABLED)

        e.bind("<FocusIn>", on_focus_in)
        e.bind("<FocusOut>", on_focus_out)
        
        if ph:
            e.insert(0, ph)
            e.config(foreground=TEXT_DISABLED)
            
        return e

    def _get(self, e: tk.Entry, ph: str) -> str:
        v = e.get().strip()
        return "" if v == ph else v

    def _clear(self):
        for e, ph in [(self._emp_id, "e.g. EMP001"),
                      (self._name,   "e.g. Rahul Sharma"),
                      (self._dept,   "e.g. IT / Sales / HR")]:
            e.delete(0, "end")
            e.insert(0, ph)
            e.config(foreground=TEXT_DISABLED)
        self._ring.set_state("idle")
        self._status_var.set("")
        self._quality_var.set("Quality: —")
        self._btn.config(state="normal", text="🖐  Start Fingerprint Scan")

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        emp_id = self._tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Remove Employee",
                               f"Remove employee {emp_id}? This cannot be undone."):
            db.delete_employee(emp_id)
            self.refresh()

    def _sync_from_cloud(self):
        if not sso_client.is_authenticated():
            messagebox.showwarning("Sync Warning", "Please configure Cloud Sync first.")
            return

        if self._sync_in_progress:
            return

        self._sync_in_progress = True
        self._sync_btn.config(state="disabled", text="⏳  Syncing…")
        self._refresh_btn.config(state="disabled", text=" ⏳ ")
        self._animate_spinner()
        
        def run_sync():
            ok, msg = sso_client.sync_employees_from_server()
            def on_sync_done():
                self._sync_in_progress = False
                self._sync_btn.config(state="normal", text="🔄  Sync from Cloud")
                if ok:
                    messagebox.showinfo("Sync Success", msg)
                    self.refresh()
                else:
                    messagebox.showerror("Sync Error", msg)
            self.after(0, on_sync_done)

        threading.Thread(target=run_sync, daemon=True).start()

    def _animate_spinner(self, frame_idx=0):
        if not self._sync_in_progress:
            self._refresh_btn.config(state="normal", text=" ⟳ ")
            self._refresh_status_lbl.config(text="")
            return
            
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        char = spinner_chars[frame_idx % len(spinner_chars)]
        self._refresh_status_lbl.config(text=f"{char} Syncing cloud templates...")
        
        self.after(80, lambda: self._animate_spinner(frame_idx + 1))

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _start_scan(self):
        emp_id = self._get(self._emp_id, "e.g. EMP001")
        name   = self._get(self._name,   "e.g. Rahul Sharma")
        dept   = self._get(self._dept,   "e.g. IT / Sales / HR")

        if not emp_id or not name:
            messagebox.showwarning("Missing Fields",
                                   "Employee ID and Full Name are required.")
            return

        if not self._re_enroll.get() and db.get_employee(emp_id):
            messagebox.showwarning("Already Enrolled",
                                   f"{emp_id} already exists. Tick Re-enroll to overwrite.")
            return

        self._scanning = True
        self._btn.config(state="disabled", text="⏳  Preparing …")
        self._ring.set_state("scanning")
        self._status_lbl.config(fg=TEXT_SECONDARY)

        def countdown_and_scan():
            import time

            # 3 second visual countdown
            for i in range(3, 0, -1):
                self._status_var.set(f"Scanning starting in {i} seconds...")
                time.sleep(1)

            self._status_var.set("Place finger firmly on sensor…")
            self.after(0, lambda: self._btn.config(text="⏳  Scanning …"))
            
            # Step 3: Run scan
            self._do_scan(emp_id, name, dept)

        threading.Thread(target=countdown_and_scan, daemon=True).start()

    def _do_scan(self, emp_id, name, dept):
        import time
        ok, quality, template = self.sdk.capture_template(timeout_ms=12_000)
        
        # Step 4: Re-init device once after scan to reset sensor state and leave it ready
        if not self.sdk.is_demo:
            try:
                self.sdk.close_device()
                time.sleep(0.4)
                self.sdk.init_device()
            except Exception:
                pass

        upload_ok = True
        upload_msg = ""
        if ok and template:
            upload_ok, upload_msg = sso_client.upload_fingerprint_template(emp_id, template)
        self.after(0, self._on_done, ok, quality, template, emp_id, name, dept, upload_ok, upload_msg)

    def _on_done(self, ok, quality, template, emp_id, name, dept, upload_ok, upload_msg):
        self._scanning = False
        self._btn.config(state="normal", text="🖐  Start Fingerprint Scan")
        self._quality_var.set(f"Quality: {quality}/100")

        if not ok:
            self._ring.set_state("failure")
            msg = ("No finger detected — try again."
                   if quality == 0
                   else f"Quality too low ({quality}/100) — press firmly.")
            self._status_var.set(msg)
            self._status_lbl.config(fg=DANGER)
            return

        if not upload_ok:
            self._ring.set_state("failure")
            self._status_var.set(f"Cloud sync failed: {upload_msg}")
            self._status_lbl.config(fg=DANGER)
            return

        if self._re_enroll.get() and db.get_employee(emp_id):
            db.update_template(emp_id, template)
        else:
            if not db.add_employee(emp_id, name, dept, template):
                self._ring.set_state("failure")
                self._status_var.set("Employee ID already exists — tick Re-enroll.")
                self._status_lbl.config(fg=DANGER)
                return

        self._ring.set_state("success")
        self._status_var.set(f"✓  {name} enrolled successfully!")
        self._status_lbl.config(fg=SUCCESS)
        self.refresh()


# ─────────────────────────────────────────────────────────────────────────────

class _SmallRing(tk.Canvas):
    SIZE = 120
    CX = CY = 60

    def __init__(self, master, **kw):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         bg=BG_BASE, highlightthickness=0, **kw)
        self._state = "idle"
        self._angle = 0.0
        self._after = None
        self._draw()

    def set_state(self, state: str):
        self._state = state
        if self._after:
            self.after_cancel(self._after)
            self._after = None
        self._angle = 0.0
        if state == "scanning":
            self._animate()
        else:
            self._draw()

    def _animate(self):
        self._angle = (self._angle + 6) % 360
        self._draw()
        if self._state == "scanning":
            self._after = self.after(30, self._animate)

    def _draw(self):
        self.delete("all")
        s = self._state
        p = 8
        bg_c   = {"idle": BG_ELEVATED, "scanning": BG_ELEVATED,
                   "success": "#0A2A15", "failure": "#2A0A0A"}.get(s, BG_ELEVATED)
        ring_c = {"idle": BORDER, "scanning": ACCENT,
                  "success": SUCCESS, "failure": DANGER}.get(s, BORDER)
        self.create_oval(p, p, self.SIZE-p, self.SIZE-p, fill=bg_c, outline="")
        self.create_oval(p, p, self.SIZE-p, self.SIZE-p,
                         outline=ring_c, width=3, fill="")
        cx, cy = self.CX, self.CY
        if s == "scanning":
            self.create_arc(p, p, self.SIZE-p, self.SIZE-p,
                            start=-self._angle, extent=100,
                            outline=ACCENT, width=4, style="arc")
            for r in range(12, 36, 8):
                self.create_arc(cx-r, cy-r, cx+r, cy+r,
                                start=50, extent=260,
                                outline=ACCENT, width=1.2, style="arc")
        elif s == "success":
            self.create_line(cx-18, cy, cx-4, cy+14, cx+18, cy-12,
                             fill=SUCCESS, width=3, joinstyle="round", capstyle="round")
        elif s == "failure":
            d = 14
            self.create_line(cx-d, cy-d, cx+d, cy+d, fill=DANGER, width=3, capstyle="round")
            self.create_line(cx+d, cy-d, cx-d, cy+d, fill=DANGER, width=3, capstyle="round")
        else:
            for r in range(12, 36, 8):
                self.create_arc(cx-r, cy-r, cx+r, cy+r,
                                start=50, extent=260,
                                outline=TEXT_DISABLED, width=1, style="arc")
