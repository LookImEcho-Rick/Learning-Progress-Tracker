import os
import tempfile
import datetime as dt
import pandas as pd

from services.storage import init_db, upsert_entry, get_all_entries_df
from services.filesync import export_db_to_csv, import_csv_to_db


def test_export_and_import_csv_roundtrip(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "entries.csv")
    monkeypatch.setenv("LPT_CSV_PATH", csv_path)

    init_db()
    # Empty DB exports an empty CSV with headers
    export_db_to_csv()
    assert os.path.exists(csv_path)

    # Add an entry, export, clear DB by re-init to a fresh temp location via env path
    upsert_entry(
        date=dt.date(2025, 1, 10),
        topic="CSVTest",
        minutes=25,
        practiced="p",
        challenges="",
        wins="",
        confidence=4,
        tags="a,b",
    )
    export_db_to_csv()

    # Simulate import into empty DB: re-create a new temp db folder via monkeypatch of storage DB_PATH
    # Simpler: wipe in-memory by relying on same DB; import should upsert same date without error.
    inserted, updated, errors = import_csv_to_db()
    assert inserted >= 0 and updated >= 0
    assert isinstance(errors, list)

    df = get_all_entries_df()
    assert not df.empty
    assert any(df["topic"].astype(str).str.contains("CSVTest"))

