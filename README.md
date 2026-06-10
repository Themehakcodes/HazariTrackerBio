# HazariTracker Bio

Fingerprint-based employee attendance system using the Mantra MFS100 scanner.

## Requirements

- **32-bit Python 3.11** at `C:\Python311-32\python.exe`
- Mantra MFS100 driver installed (provides `MANTRA.MFS100.dll`)
- `pip install -r requirements.txt`

## Run

```
python run_32bit.py
```

## Features

| Tab | What it does |
|---|---|
| 🖐 Scanner | Continuous auto-detect → match → punch → reinit loop |
| 👤 Employees | Add / remove employees with fingerprint enrolment |
| 📋 Reports | Date-wise attendance table with CSV export |

## Folder

```
app.py              Main window (3 tabs, system tray on close)
db.py               SQLite persistence (employees + attendance)
mfs100_sdk.py       MANTRA.MFS100.dll wrapper via pythonnet
theme.py            Orange/dark design tokens
run_32bit.py        32-bit Python launcher
MANTRA.MFS100.dll   Mantra .NET SDK (do not move)
pages/
  scanner.py        Continuous scan page
  enroll.py         Employee enrolment page
  reports.py        Date-wise attendance report
```

## API Integration (future)

In `pages/scanner.py` → `_api_punch(employee, timestamp)` — replace the `print` with your HTTP call.
