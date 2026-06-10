"""
pages/enroll.py
───────────────
Add New Employee — simple form + fingerprint scan + employee list.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

import db
from mfs100_sdk import MFS100, QUALITY_MIN
from theme import *


class EnrollPage(tk.Frame):

    def __init__(self, master, sdk: MFS100, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self.sdk = sdk
        self._scanning = False
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
                       selectcolor=BG_ELEVATED,
                       activebackground=BG_SURFACE,
                       font=FONT_SMALL, cursor="hand2").pack(anchor="w", pady=(PAD_SM, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=PAD_MD)

        # Buttons
        row = tk.Frame(left, bg=BG_SURFACE)
        row.pack(fill="x")
        self._btn = tk.Button(row, text="🖐  Start Fingerprint Scan",
                              bg=ACCENT, fg=TEXT_PRIMARY, font=FONT_H3,
                              activebackground=ACCENT_HOVER,
                              activeforeground=TEXT_PRIMARY,
                              relief="flat", bd=0, padx=PAD_MD, pady=PAD_SM,
                              cursor="hand2", command=self._start_scan)
        self._btn.pack(side="left", padx=(0, PAD_SM))
        tk.Button(row, text="Clear", bg=BG_ELEVATED, fg=TEXT_PRIMARY,
                  font=FONT_H3, relief="flat", bd=0,
                  padx=PAD_MD, pady=PAD_SM,
                  cursor="hand2", command=self._clear).pack(side="left")

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

        tk.Label(right, text="Fingerprint", font=FONT_H3,
                 bg=BG_BASE, fg=TEXT_SECONDARY).pack()

        self._ring = _SmallRing(right)
        self._ring.pack(pady=(PAD_SM, PAD_MD))

        # Enrolled employee list
        tk.Label(right, text="Enrolled Employees",
                 font=FONT_H3, bg=BG_BASE,
                 fg=TEXT_SECONDARY).pack(anchor="w")

        cols = ("emp_id", "name", "dept", "enrolled")
        self._tree = ttk.Treeview(right, columns=cols, show="headings",
                                  height=10, selectmode="browse")
        for col, w, label in [
            ("emp_id",   70,  "ID"),
            ("name",    160,  "Name"),
            ("dept",    100,  "Department"),
            ("enrolled", 100, "Enrolled At"),
        ]:
            self._tree.heading(col, text=label)
            self._tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(right, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Delete button
        tk.Button(right, text="✕  Remove Selected",
                  bg=DANGER, fg=TEXT_PRIMARY, font=FONT_SMALL,
                  relief="flat", bd=0, padx=PAD_SM, pady=4,
                  cursor="hand2",
                  command=self._delete_selected).pack(pady=(PAD_SM, 0))

        self.refresh()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for emp in db.get_all_employees():
            self._tree.insert("", "end", values=(
                emp["emp_id"], emp["name"],
                emp["department"] or "—",
                (emp["enrolled_at"] or "")[:10],
            ))

    def _field(self, parent, label: str, ph: str = "") -> ttk.Entry:
        tk.Label(parent, text=label, font=FONT_SMALL,
                 bg=BG_SURFACE, fg=TEXT_SECONDARY).pack(anchor="w", pady=(PAD_SM, 2))
        e = ttk.Entry(parent, font=FONT_BODY)
        e.pack(fill="x", ipady=6)
        if ph:
            e.insert(0, ph)
            e.config(foreground=TEXT_DISABLED)
            e.bind("<FocusIn>",  lambda _, en=e, p=ph: (en.delete(0, "end"), en.config(foreground=TEXT_PRIMARY)) if en.get() == p else None)
            e.bind("<FocusOut>", lambda _, en=e, p=ph: (en.insert(0, p), en.config(foreground=TEXT_DISABLED)) if not en.get() else None)
        return e

    def _get(self, e: ttk.Entry, ph: str) -> str:
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
        self._btn.config(state="disabled", text="⏳  Scanning …")
        self._ring.set_state("scanning")
        self._status_var.set("Place finger firmly on sensor…")
        self._status_lbl.config(fg=TEXT_SECONDARY)

        threading.Thread(
            target=self._do_scan,
            args=(emp_id, name, dept),
            daemon=True,
        ).start()

    def _do_scan(self, emp_id, name, dept):
        ok, quality, template = self.sdk.capture_template(timeout_ms=12_000)
        self.after(0, self._on_done, ok, quality, template, emp_id, name, dept)

    def _on_done(self, ok, quality, template, emp_id, name, dept):
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
