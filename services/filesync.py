import os
import atexit
import datetime as dt
from typing import Optional

import pandas as pd

from services.storage import get_all_entries_df, import_dataframe


APP_DIR_NAME = "Learning Progress Tracker"
ENV_CSV_PATH = "LPT_CSV_PATH"


def _documents_dir() -> str:
    home = os.path.expanduser("~")
    # Prefer Documents if it exists
    docs = os.path.join(home, "Documents")
    if os.path.isdir(docs):
        return docs
    return home


def get_csv_path() -> str:
    override = os.getenv(ENV_CSV_PATH)
    if override:
        return os.path.abspath(override)
    base = _documents_dir()
    folder = os.path.join(base, APP_DIR_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "entries.csv")


def export_db_to_csv(path: Optional[str] = None) -> str:
    path = path or get_csv_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = get_all_entries_df()
    # Ensure stable column order
    cols = [
        "date",
        "topic",
        "minutes",
        "practiced",
        "challenges",
        "wins",
        "confidence",
        "tags",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = "" if c not in ("minutes", "confidence") else 0
    df = df[cols]
    df.to_csv(path, index=False)
    return path


def import_csv_to_db(path: Optional[str] = None) -> tuple[int, int, list[str]]:
    path = path or get_csv_path()
    if not os.path.exists(path):
        return 0, 0, []
    try:
        df = pd.read_csv(path)
    except Exception as ex:
        return 0, 0, [f"Failed to read CSV at {path}: {ex}"]
    return import_dataframe(df, dry_run=False)


def create_or_sync_on_launch() -> tuple[str, list[str]]:
    """Ensure a CSV exists in a user-visible location and sync DB from it if present.
    Returns (csv_path, messages) where messages are any non-fatal import notes.
    """
    path = get_csv_path()
    msgs: list[str] = []
    if os.path.exists(path):
        _, _, m = import_csv_to_db(path)
        msgs.extend(m)
    # Always ensure a CSV file exists after launch
    export_db_to_csv(path)
    return path, msgs


_registered = False


def register_atexit_export():
    global _registered
    if _registered:
        return

    def _export():
        try:
            export_db_to_csv()
        except Exception:
            # Best-effort on interpreter shutdown
            pass

    atexit.register(_export)
    _registered = True

