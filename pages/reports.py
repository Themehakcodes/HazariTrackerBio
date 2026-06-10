"""
pages/reports.py
────────────────
Date-wise attendance report.

Features
────────
  • Navigate day by day (← Today →)
  • Table: Time | Employee ID | Name | Department | Quality
  • Summary bar: Present / Enrolled count
  • Export to CSV
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
from datetime import date, timedelta

import db
from theme import *


class ReportsPage(tk.Frame):

    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self._current_date = date.today()
        self._build()
        self.refresh()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Top controls ──────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG_SURFACE, pady=PAD_MD, padx=PAD_LG)
        ctrl.pack(fill="x")

        # Date nav
        nav = tk.Frame(ctrl, bg=BG_SURFACE)
        nav.pack(side="left")

        self._btn_prev = tk.Button(nav, text="◀", font=FONT_H2,
                                   bg=BG_ELEVATED, fg=TEXT_PRIMARY,
                                   relief="flat", bd=0, padx=PAD_MD, pady=4,
                                   cursor="hand2",
                                   command=self._prev_day)
        self._btn_prev.pack(side="left")

        self._date_var = tk.StringVar()
        self._date_lbl = tk.Label(nav, textvariable=self._date_var,
                                  font=FONT_H2, bg=BG_SURFACE,
                                  fg=TEXT_PRIMARY, width=20, anchor="center")
        self._date_lbl.pack(side="left", padx=PAD_MD)

        self._btn_next = tk.Button(nav, text="▶", font=FONT_H2,
                                   bg=BG_ELEVATED, fg=TEXT_PRIMARY,
                                   relief="flat", bd=0, padx=PAD_MD, pady=4,
                                   cursor="hand2",
                                   command=self._next_day)
        self._btn_next.pack(side="left")

        tk.Button(nav, text="Today", font=FONT_BODY,
                  bg=ACCENT, fg=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=PAD_MD, pady=4,
                  cursor="hand2",
                  command=self._go_today).pack(side="left", padx=(PAD_MD, 0))

        # Export button
        tk.Button(ctrl, text="⬇  Export CSV", font=FONT_BODY,
                  bg=BG_ELEVATED, fg=TEXT_SECONDARY,
                  relief="flat", bd=0, padx=PAD_MD, pady=4,
                  cursor="hand2",
                  command=self._export_csv).pack(side="right")

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # ── Summary strip ─────────────────────────────────────────────────────
        summary = tk.Frame(self, bg=BG_ELEVATED, pady=PAD_SM, padx=PAD_LG)
        summary.pack(fill="x")

        self._present_var = tk.StringVar(value="Present: 0")
        self._enrolled_var = tk.StringVar(value="Total Enrolled: 0")
        self._scans_var   = tk.StringVar(value="Total Scans: 0")

        for var, col in [(self._present_var,  SUCCESS),
                         (self._enrolled_var, TEXT_SECONDARY),
                         (self._scans_var,    ACCENT)]:
            tk.Label(summary, textvariable=var, font=FONT_H3,
                     bg=BG_ELEVATED, fg=col).pack(side="left", padx=PAD_LG)

        # ── Attendance table ──────────────────────────────────────────────────
        tbl_frame = tk.Frame(self, bg=BG_BASE, padx=PAD_LG, pady=PAD_MD)
        tbl_frame.pack(fill="both", expand=True)

        cols = ("time", "emp_id", "name", "dept", "quality")
        self._tree = ttk.Treeview(tbl_frame, columns=cols,
                                  show="headings", selectmode="browse")

        for col, width, label in [
            ("time",    90,  "Time"),
            ("emp_id",  90,  "Employee ID"),
            ("name",   200,  "Name"),
            ("dept",   140,  "Department"),
            ("quality", 80,  "Quality"),
        ]:
            self._tree.heading(col, text=label,
                               command=lambda c=col: self._sort(c))
            self._tree.column(col, width=width, anchor="w")

        self._tree.tag_configure("even", background=BG_SURFACE)
        self._tree.tag_configure("odd",  background=BG_ELEVATED)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ── Empty state label ─────────────────────────────────────────────────
        self._empty_lbl = tk.Label(tbl_frame,
                                   text="No attendance records for this date.",
                                   font=FONT_H3, bg=BG_BASE,
                                   fg=TEXT_DISABLED)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload data for the current date."""
        ds = self._current_date.isoformat()

        # Update date label
        weekday = self._current_date.strftime("%A")
        friendly = self._current_date.strftime("%d %B %Y")
        suffix = " (Today)" if self._current_date == date.today() else ""
        self._date_var.set(f"{weekday}, {friendly}{suffix}")

        # Disable "next" if current date is today
        future = self._current_date >= date.today()
        self._btn_next.config(state="disabled" if future else "normal",
                              fg=TEXT_DISABLED if future else TEXT_PRIMARY)

        # Fetch records
        rows = db.get_attendance(date_filter=ds, limit=1000)
        enrolled_count = len(db.get_all_employees())

        # Unique employees present
        seen_employees = set()
        for r in rows:
            seen_employees.add(r["emp_id"])

        self._present_var.set(f"Present: {len(seen_employees)}")
        self._enrolled_var.set(f"Total Enrolled: {enrolled_count}")
        self._scans_var.set(f"Total Scans: {len(rows)}")

        # Populate table
        for item in self._tree.get_children():
            self._tree.delete(item)

        if not rows:
            self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._empty_lbl.place_forget()
            for i, row in enumerate(rows):
                ts = row["timestamp"] or ""
                time_str = ts[11:19] if len(ts) >= 19 else ts
                quality  = row["score"] if row["score"] else "—"
                tag = "even" if i % 2 == 0 else "odd"
                self._tree.insert("", "end", tag=tag, values=(
                    time_str,
                    row["emp_id"],
                    row["emp_name"],
                    self._get_dept(row["emp_id"]),
                    quality,
                ))

        self._dept_cache = {}  # clear cache after refresh

    # ── Department lookup (cached) ─────────────────────────────────────────────

    def _get_dept(self, emp_id: str) -> str:
        if not hasattr(self, "_dept_cache"):
            self._dept_cache = {}
        if emp_id not in self._dept_cache:
            emp = db.get_employee(emp_id)
            self._dept_cache[emp_id] = (emp["department"] if emp else "—") or "—"
        return self._dept_cache[emp_id]

    # ── Navigation ────────────────────────────────────────────────────────────

    def _prev_day(self):
        self._current_date -= timedelta(days=1)
        self.refresh()

    def _next_day(self):
        if self._current_date < date.today():
            self._current_date += timedelta(days=1)
            self.refresh()

    def _go_today(self):
        self._current_date = date.today()
        self.refresh()

    # ── Sorting ───────────────────────────────────────────────────────────────

    def _sort(self, col: str):
        rows = [(self._tree.set(k, col), k)
                for k in self._tree.get_children("")]
        rows.sort()
        for i, (_, k) in enumerate(rows):
            self._tree.move(k, "", i)
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.item(k, tags=(tag,))

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_csv(self):
        ds   = self._current_date.isoformat()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"attendance_{ds}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Attendance Report",
        )
        if not path:
            return

        rows = db.get_attendance(date_filter=ds, limit=10000)
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Time", "Employee ID",
                                 "Name", "Department", "Quality"])
                for row in rows:
                    ts = row["timestamp"] or ""
                    writer.writerow([
                        ds,
                        ts[11:19] if len(ts) >= 19 else ts,
                        row["emp_id"],
                        row["emp_name"],
                        self._get_dept(row["emp_id"]),
                        row["score"] or "",
                    ])
            messagebox.showinfo("Export Complete",
                                f"Saved {len(rows)} records to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))
