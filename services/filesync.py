import os
import atexit
import json
from typing import Optional

import pandas as pd

from services.storage import get_all_entries_df, import_dataframe


APP_DIR_NAME = "Learning Progress Tracker"
ENV_CSV_PATH = "LPT_CSV_PATH"
ENV_JSON_PATH = "LPT_JSON_PATH"


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


def get_json_path() -> str:
    override = os.getenv(ENV_JSON_PATH)
    if override:
        return os.path.abspath(override)
    base = _documents_dir()
    folder = os.path.join(base, APP_DIR_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "entries.json")


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


def export_db_to_json(path: Optional[str] = None) -> str:
    path = path or get_json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = get_all_entries_df()
    # Ensure all expected columns exist
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
    # Write as a list of dicts
    with open(path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
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


def import_json_to_db(path: Optional[str] = None) -> tuple[int, int, list[str]]:
    path = path or get_json_path()
    if not os.path.exists(path):
        return 0, 0, []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return 0, 0, ["Invalid JSON format: expected a list of entries"]
        df = pd.DataFrame(data)
    except Exception as ex:
        return 0, 0, [f"Failed to read JSON at {path}: {ex}"]
    return import_dataframe(df, dry_run=False)


def create_or_sync_on_launch() -> tuple[str, list[str]]:
    """Prefer JSON for user-visible sync; fall back to CSV if present.
    Returns (path_used, messages) where messages are any non-fatal import notes.
    """
    msgs: list[str] = []
    json_path = get_json_path()
    csv_path = get_csv_path()
    used_path = json_path
    if os.path.exists(json_path):
        _, _, m = import_json_to_db(json_path)
        msgs.extend(m)
    elif os.path.exists(csv_path):
        used_path = csv_path
        _, _, m = import_csv_to_db(csv_path)
        msgs.extend(m)
    # Always ensure a JSON file exists after launch
    used_path = export_db_to_json(json_path)
    return used_path, msgs


_registered = False


def register_atexit_export():
    global _registered
    if _registered:
        return

    def _export():
        try:
            export_db_to_json()
        except Exception:
            # Best-effort on interpreter shutdown
            pass

    atexit.register(_export)
    _registered = True
