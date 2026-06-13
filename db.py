"""
db.py
─────
SQLite-backed persistence layer for HazariTracker Bio.

Tables
──────
  employees  — enrolled users + their stored fingerprint template
  attendance — every attendance event (check-in / check-out)
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "hazari_bio.db")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    """Create tables if they don't exist yet, running migrations if required."""
    with _connect() as con:
        # Check if the 'attendance' table has a broken foreign key referencing 'employees_old'
        broken_fk = False
        try:
            fk_list = con.execute("PRAGMA foreign_key_list(attendance)").fetchall()
            for fk in fk_list:
                if fk["table"] == "employees_old":
                    broken_fk = True
                    break
        except Exception:
            pass

        if broken_fk:
            print("[DB] Fixing broken foreign key in attendance table...")
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DROP TABLE IF EXISTS attendance")
            con.execute("PRAGMA foreign_keys = ON")

        # Check if the 'template' column exists and is NOT NULL
        schema_info = con.execute("PRAGMA table_info(employees)").fetchall()
        needs_migration = False
        if schema_info:
            for col in schema_info:
                if col["name"] == "template" and col["notnull"] == 1:
                    needs_migration = True
                    break

        if needs_migration:
            print("[DB] Migrating employees table to support nullable templates...")
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DROP TABLE IF EXISTS attendance")
            con.execute("ALTER TABLE employees RENAME TO employees_old")
            con.execute("""
                CREATE TABLE employees (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    emp_id      TEXT    NOT NULL UNIQUE,
                    name        TEXT    NOT NULL,
                    department  TEXT    DEFAULT '',
                    template    BLOB,
                    enrolled_at TEXT
                )
            """)
            con.execute("""
                INSERT INTO employees (id, emp_id, name, department, template, enrolled_at)
                SELECT id, emp_id, name, department, template, enrolled_at FROM employees_old
            """)
            con.execute("DROP TABLE employees_old")
            con.execute("PRAGMA foreign_keys = ON")
            print("[DB] Migration completed successfully.")

        con.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id      TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                department  TEXT    DEFAULT '',
                template    BLOB,
                enrolled_at TEXT
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id      TEXT    NOT NULL,
                emp_name    TEXT    NOT NULL,
                event_type  TEXT    NOT NULL DEFAULT 'check_in',
                timestamp   TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                score       INTEGER DEFAULT 0,
                FOREIGN KEY (emp_id) REFERENCES employees(emp_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)


# ── Settings operations ───────────────────────────────────────────────────────

def get_setting(key: str) -> str | None:
    with _connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with _connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def delete_setting(key: str):
    with _connect() as con:
        con.execute("DELETE FROM settings WHERE key = ?", (key,))


# ── Employee operations ───────────────────────────────────────────────────────

def add_employee(emp_id: str, name: str, department: str, template: bytes | None = None) -> bool:
    """Insert a new employee. Returns False if emp_id already exists."""
    clean_id = str(emp_id or "").strip().upper()
    clean_name = str(name or "").strip()
    clean_dept = str(department or "").strip()
    try:
        with _connect() as con:
            enrolled = datetime.now().isoformat(timespec="seconds") if template else None
            con.execute(
                """INSERT INTO employees (emp_id, name, department, template, enrolled_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (clean_id, clean_name, clean_dept, template, enrolled),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_employee_details(emp_id: str, name: str, department: str):
    """Update employee name and department details."""
    clean_id = str(emp_id or "").strip().upper()
    clean_name = str(name or "").strip()
    clean_dept = str(department or "").strip()
    with _connect() as con:
        con.execute(
            "UPDATE employees SET name = ?, department = ? WHERE emp_id = ?",
            (clean_name, clean_dept, clean_id),
        )


def update_template(emp_id: str, template: bytes):
    """Overwrite the stored fingerprint template for an existing employee."""
    clean_id = str(emp_id or "").strip().upper()
    now_str = datetime.now().isoformat(timespec="seconds")
    with _connect() as con:
        con.execute(
            "UPDATE employees SET template = ?, enrolled_at = ? WHERE emp_id = ?",
            (template, now_str, clean_id),
        )


def delete_employee(emp_id: str):
    clean_id = str(emp_id or "").strip().upper()
    with _connect() as con:
        con.execute("DELETE FROM employees WHERE emp_id = ?", (clean_id,))


def get_employee(emp_id: str) -> sqlite3.Row | None:
    clean_id = str(emp_id or "").strip().upper()
    with _connect() as con:
        return con.execute(
            "SELECT * FROM employees WHERE emp_id = ?", (clean_id,)
        ).fetchone()


def get_all_employees() -> list[sqlite3.Row]:
    with _connect() as con:
        return con.execute(
            "SELECT id, emp_id, name, department, enrolled_at, (template IS NOT NULL) as is_enrolled FROM employees ORDER BY name"
        ).fetchall()


def get_all_templates() -> list[tuple[str, str, bytes]]:
    """Return (emp_id, name, template) for every enrolled employee."""
    with _connect() as con:
        rows = con.execute(
            "SELECT emp_id, name, template FROM employees WHERE template IS NOT NULL"
        ).fetchall()
    return [(r["emp_id"], r["name"], bytes(r["template"])) for r in rows]


# ── Attendance operations ─────────────────────────────────────────────────────

def already_checked_in_today(emp_id: str) -> bool:
    """True if there's a check_in record for this employee today with no checkout."""
    today = date.today().isoformat()
    with _connect() as con:
        row = con.execute(
            """SELECT COUNT(*) as cnt FROM attendance
               WHERE emp_id = ? AND date = ? AND event_type = 'check_in'""",
            (emp_id, today),
        ).fetchone()
    return row["cnt"] > 0


def already_checked_out_today(emp_id: str) -> bool:
    today = date.today().isoformat()
    with _connect() as con:
        row = con.execute(
            """SELECT COUNT(*) as cnt FROM attendance
               WHERE emp_id = ? AND date = ? AND event_type = 'check_out'""",
            (emp_id, today),
        ).fetchone()
    return row["cnt"] > 0


def log_attendance(emp_id: str, emp_name: str, event_type: str = "check_in", score: int = 0):
    now = datetime.now()
    with _connect() as con:
        con.execute(
            """INSERT INTO attendance (emp_id, emp_name, event_type, timestamp, date, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (emp_id, emp_name, event_type,
             now.isoformat(timespec="seconds"),
             now.date().isoformat(), score),
        )


def get_attendance(
    date_filter: str | None = None,
    emp_id_filter: str | None = None,
    limit: int = 500,
) -> list[sqlite3.Row]:
    query  = "SELECT * FROM attendance WHERE 1=1"
    params: list = []
    if date_filter:
        query  += " AND date = ?"
        params.append(date_filter)
    if emp_id_filter:
        query  += " AND emp_id = ?"
        params.append(emp_id_filter.strip().upper())
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with _connect() as con:
        return con.execute(query, params).fetchall()


def get_attendance_summary(target_date: str | None = None) -> list[sqlite3.Row]:
    """
    Returns one row per employee showing their first check-in and last check-out
    for the given date (defaults to today).
    """
    target_date = target_date or date.today().isoformat()
    with _connect() as con:
        return con.execute(
            """
            SELECT
                emp_id,
                emp_name,
                MIN(CASE WHEN event_type='check_in'  THEN timestamp END) AS check_in,
                MAX(CASE WHEN event_type='check_out' THEN timestamp END) AS check_out
            FROM attendance
            WHERE date = ?
            GROUP BY emp_id
            ORDER BY emp_name
            """,
            (target_date,),
        ).fetchall()
