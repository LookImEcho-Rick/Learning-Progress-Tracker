## Getting Started

This guide covers local setup using a Python virtual environment and how to run the app.

**Requirements**
- Python 3.10+

**1) Create a virtual environment**

- Windows (PowerShell):
  - `python -m venv .venv`
  - `./.venv/Scripts/Activate.ps1`

- macOS/Linux (bash):
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`

**2) Install dependencies**

- `pip install -r requirements.txt`

**3) Run the app**

- `streamlit run app.py`

The app stores a local SQLite database at `data/tracker.db` and creates the `data/` folder on first run.

**Project Structure**
- `app.py` – main Streamlit app (UI, pages)
- `services/storage.py` – SQLite persistence and exports
- `services/metrics.py` – progress score and derived fields
- `services/charts.py` – Altair chart builders
- `docs/` – user guide and architecture notes
- `ROADMAP.md` – planned improvements
- `CHANGELOG.md` – changes by release

**Notes**
- The local virtual environment (`.venv/`) and generated data files are ignored by git.
