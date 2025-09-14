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
- `services/filesync.py` - JSON sync utilities (CSV kept for compatibility)

## Data Flow
1. On launch:
   - Initialize DB and JSON sync (import JSON if present, else fall back to CSV once; always write JSON).
   - Show Log Entry tab with today’s form.
2. User saves entry - stored in DB.
3. History tab lists entries with filters and edit/delete actions.
4. Data tab provides JSON import/export (import validates then commits).

## Persistence and Backups
- SQLite DB at `data/tracker.db`.
- Daily backups are created under `data/backups/` as `tracker-YYYYMMDD.db` (best-effort on app start).
 - JSON sync: on app launch, the app imports from a user-visible JSON at `Documents/Learning Progress Tracker/entries.json` if present (or falls back to CSV once), then writes the current DB to JSON. On app exit, it saves again to JSON (best-effort).

## Settings
- Simple key/value `settings` table.
- Currently used keys: `weekly_goal_minutes`.
