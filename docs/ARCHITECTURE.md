# Architecture

## Tech Stack
- Python 3.10+
- PySide6 (desktop UI)
- SQLite (local storage)
- Pandas (data management)

## Data Model
- **Session**
  - date
  - week_index (derived since first entry)
  - topic
  - minutes
  - practiced
  - challenges
  - wins
  - confidence (1-5)
  - progress_score (minutes x confidence)
  - tags (comma-separated text)

## Modules
- `desktop/main.py` - PySide6 desktop app (Log, History, Insights, Data)
- `services/storage.py` - database CRUD, export helpers, daily backups, settings
- `services/metrics.py` - week index, progress score, derived fields, streaks & weekly helpers
- `services/filesync.py` - CSV sync utilities

## Data Flow
1. On launch:
   - Initialize DB and CSV sync (import if present, then write CSV).
   - Show Log Entry tab with today’s form.
2. User saves entry - stored in DB.
3. History tab lists entries with filters and edit/delete actions.
4. Data tab provides CSV import/export (import validates then commits).

## Persistence and Backups
- SQLite DB at `data/tracker.db`.
- Daily backups are created under `data/backups/` as `tracker-YYYYMMDD.db` (best-effort on app start).
 - CSV sync: on app launch, the app imports from a user-visible CSV at `Documents/Learning Progress Tracker/entries.csv` if present, then writes the current DB to that CSV. On app exit, it saves again to the CSV (best-effort).

## Settings
- Simple key/value `settings` table.
- Currently used keys: `weekly_goal_minutes`.
