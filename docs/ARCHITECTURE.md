# Architecture

## Tech Stack
- Python 3.10+
- Streamlit (UI/UX)
- SQLite (local storage)
- Pandas (data management)
- Altair/Plotly (visualizations)

## Data Model
- **Session**
  - date
  - week_index (since start date)
  - topic
  - minutes
  - practiced
  - challenges
  - wins
  - confidence (1–5)
  - progress_score (minutes × confidence)

## Modules
- `app.py` – entry point for Streamlit UI
- `services/storage.py` – database CRUD
- `services/metrics.py` – week index, progress score, rollups
- `services/charts.py` – visualization builders
- `ui/forms.py` – today’s entry form
- `ui/tables.py` – history view
- `ui/layout.py` – overall UI layout

## Data Flow
1. On launch:
   - Load existing DB (or initialize new one).
   - Prefill today’s blank entry.
2. User saves entry → stored in DB.
3. Charts and summaries auto-update.
4. Weekly summary aggregates based on week index.
