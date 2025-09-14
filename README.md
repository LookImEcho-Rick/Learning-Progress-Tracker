# Learning Progress Tracker

A simple desktop app (PySide6) to log daily learning sessions, review history, and visualize progress over time. Data is stored locally in SQLite, with CSV import/export and automatic CSV sync.

## Features
- Log daily entries with topic, minutes, notes, challenges, wins, and confidence.
- Always-available form for today's entry.
- History table with date-range filtering.
- Insights: minutes per day, confidence trend, and progress score trend.
- Weekly summary table (totals and averages).
- Local SQLite storage in `data/tracker.db`.
 - Export data to CSV.
- Automatic daily backups in `data/backups/`.
- Tags for entries and tag-based filtering in History.
- Streaks (current and longest) and weekly goal tracking.
- Edit and delete past entries from the History page.
- Import CSV (merge by date) with background validation; errors only if something's wrong.

## Requirements
- Python 3.10+

## Quick Start (Desktop app)

1) Create a virtual environment

- Windows (PowerShell):
  - `python -m venv .venv`
  - `./.venv/Scripts/Activate.ps1`

- macOS/Linux (bash):
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`

2) Install dependencies

- `pip install -r requirements.txt`

3) Run the desktop app

- Windows: `pwsh -File scripts/run_desktop.ps1`
- macOS/Linux: `bash scripts/run_desktop.sh`

## Build a standalone executable

- Windows: `pwsh -File scripts/build_desktop.ps1`
- macOS/Linux: `bash scripts/build_desktop.sh`

Output is created under `dist/LearningProgressTracker`.

Note: This project runs as a standalone desktop app (no Streamlit).

The app stores a local SQLite database at `data/tracker.db` and creates the `data/` folder on first run.
It also writes a best-effort daily backup to `data/backups/tracker-YYYYMMDD.db`.

## Project Structure

- `services/storage.py` – SQLite persistence and exports
- `services/metrics.py` – progress score, week index, streaks & weekly helpers
- `docs/` – user guide and architecture notes
- `ROADMAP.md` – planned improvements
- `CHANGELOG.md` – changes by release
- `desktop/` – PySide6 desktop application
  - `main.py` – GUI (Log Entry, History, Insights, Data)

## Notes
- This repository ignores the local virtual environment (`.venv/`) and generated data files.
- Validation: Topic ≤ 200 chars, Minutes 0–1440, Confidence 1–5, Tags up to 10 with 32 chars each. Long fields are truncated with a warning.
- CSV sync: On launch, the app creates/updates a CSV in your Documents folder (`Documents/Learning Progress Tracker/entries.csv`) and imports from it if present. On exit, it saves the latest data back to the CSV automatically.

