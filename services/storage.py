import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Optional
import datetime as dt

import pandas as pd
from services.validation import normalize_tags, validate_entry_fields


DB_PATH = os.path.join("data", "tracker.db")


@contextmanager
def conn_ctx():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with conn_ctx() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                topic TEXT,
                minutes INTEGER DEFAULT 0,
                practiced TEXT,
                challenges TEXT,
                wins TEXT,
                confidence INTEGER DEFAULT 3,
                tags TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date)")
        # Settings table for simple key/value configuration (e.g., weekly goal minutes)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        # Migration: ensure 'tags' column exists on older DBs
        cur = conn.execute("PRAGMA table_info(sessions)")
        cols = [r[1] for r in cur.fetchall()]
        if "tags" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN tags TEXT")
    # After ensuring DB exists, create a daily backup if not already present
    try:
        backup_db_daily()
    except Exception:
        # Backups are best-effort; avoid blocking app
        pass


def upsert_entry(
    *,
    date: dt.date,
    topic: str,
    minutes: int,
    practiced: str,
    challenges: str,
    wins: str,
    confidence: int,
    tags: Optional[str] = "",
) -> None:
    d = date.isoformat()
    with conn_ctx() as conn:
        cur = conn.execute("SELECT id FROM sessions WHERE date = ?", (d,))
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE sessions
                SET topic=?, minutes=?, practiced=?, challenges=?, wins=?, confidence=?, tags=?
                WHERE date=?
                """,
                (topic, minutes, practiced, challenges, wins, confidence, tags, d),
            )
        else:
            conn.execute(
                """
                INSERT INTO sessions (date, topic, minutes, practiced, challenges, wins, confidence, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (d, topic, minutes, practiced, challenges, wins, confidence, tags),
            )


def fetch_all_entries() -> Iterable[sqlite3.Row]:
    with conn_ctx() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT date, topic, minutes, practiced, challenges, wins, confidence, tags FROM sessions ORDER BY date ASC"
        )
        return cur.fetchall()


def get_entry_by_date(date: dt.date) -> Optional[sqlite3.Row]:
    with conn_ctx() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT date, topic, minutes, practiced, challenges, wins, confidence, tags FROM sessions WHERE date=?",
            (date.isoformat(),),
        )
        return cur.fetchone()


def delete_entry(date: dt.date) -> None:
    with conn_ctx() as conn:
        conn.execute("DELETE FROM sessions WHERE date=?", (date.isoformat(),))


def get_all_entries_df() -> pd.DataFrame:
    rows = fetch_all_entries()
    if not rows:
        return pd.DataFrame(columns=[
            "date",
            "topic",
            "minutes",
            "practiced",
            "challenges",
            "wins",
            "confidence",
            "tags",
        ])
    df = pd.DataFrame(rows, columns=rows[0].keys())
    return df


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def export_excel_bytes(df: pd.DataFrame) -> bytes:
    import io
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Progress")
    bio.seek(0)
    return bio.read()


def backup_db_daily() -> None:
    """Create a once-per-day backup copy of the SQLite DB.
    Stored under data/backups/tracker-YYYYMMDD.db
    """
    if not os.path.exists(DB_PATH):
        return
    backups_dir = os.path.join("data", "backups")
    os.makedirs(backups_dir, exist_ok=True)
    today_tag = dt.date.today().strftime("%Y%m%d")
    backup_path = os.path.join(backups_dir, f"tracker-{today_tag}.db")
    if not os.path.exists(backup_path):
        # Copy the DB file bytes
        with open(DB_PATH, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())


# Simple settings helpers
def set_setting(key: str, value: str) -> None:
    with conn_ctx() as conn:
        conn.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with conn_ctx() as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        return row[0]


def import_dataframe(df: pd.DataFrame, *, dry_run: bool = False) -> tuple[int, int, list[str]]:
    """Import/merge entries from a DataFrame.
    Required columns: date
    Optional columns: topic, minutes, practiced, challenges, wins, confidence, tags
    Returns: (inserted_count, updated_count, errors)
    """
    # Ensure schema exists
    init_db()

    if df is None or df.empty:
        return 0, 0, ["No rows to import."]

    # Standardize columns
    cols = {c.lower(): c for c in df.columns}
    def col(name):
        return cols.get(name, None)

    errors: list[str] = []
    inserted = 0
    updated = 0

    for idx, row in df.iterrows():
        try:
            # Date parsing
            raw_date = row[col("date")] if col("date") else None
            if pd.isna(raw_date):
                errors.append(f"Row {idx}: missing date")
                continue
            if isinstance(raw_date, dt.date) and not isinstance(raw_date, dt.datetime):
                d = raw_date
            else:
                d = pd.to_datetime(raw_date).date()

            topic = str(row[col("topic")] if col("topic") else "")
            practiced = str(row[col("practiced")] if col("practiced") else "")
            challenges = str(row[col("challenges")] if col("challenges") else "")
            wins = str(row[col("wins")] if col("wins") else "")
            tags_raw = row[col("tags")] if col("tags") else ""

            minutes = row[col("minutes")] if col("minutes") else 0
            confidence = row[col("confidence")] if col("confidence") else 3
            try:
                minutes = int(minutes)
            except Exception:
                minutes = 0
            try:
                confidence = int(confidence)
            except Exception:
                confidence = 3

            sanitized, msgs = validate_entry_fields(
                topic=topic,
                minutes=minutes,
                confidence=confidence,
                practiced=practiced,
                challenges=challenges,
                wins=wins,
                tags=str(tags_raw or ""),
            )

            existed = get_entry_by_date(d) is not None
            if not dry_run:
                upsert_entry(
                    date=d,
                    topic=sanitized["topic"],
                    minutes=sanitized["minutes"],
                    practiced=sanitized["practiced"],
                    challenges=sanitized["challenges"],
                    wins=sanitized["wins"],
                    confidence=sanitized["confidence"],
                    tags=sanitized["tags"],
                )
            if existed:
                updated += 1
            else:
                inserted += 1
            # Collect non-fatal messages
            for m in msgs:
                errors.append(f"Row {idx}: {m}")
        except Exception as ex:
            errors.append(f"Row {idx}: {ex}")

    return inserted, updated, errors
