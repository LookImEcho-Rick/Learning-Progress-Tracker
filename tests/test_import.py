import datetime as dt
import pandas as pd

from services.storage import init_db, get_all_entries_df, import_dataframe


def test_import_dataframe_insert_and_update():
    init_db()
    df = pd.DataFrame([
        {"date": dt.date(2025, 1, 1), "topic": "A", "minutes": 30, "confidence": 3, "tags": "x, y"},
        {"date": "2025-01-02", "topic": "B", "minutes": 15, "confidence": 5, "tags": "z"},
    ])
    inserted, updated, errors = import_dataframe(df)
    assert inserted == 2 and updated == 0
    assert not errors

    # Update one row
    df2 = pd.DataFrame([
        {"date": "2025-01-02", "topic": "B2", "minutes": 60, "confidence": 4, "tags": "z, y"},
    ])
    inserted2, updated2, errors2 = import_dataframe(df2)
    assert inserted2 == 0 and updated2 == 1
    assert not errors2

    out = get_all_entries_df()
    assert out.shape[0] == 2
    # Check update applied
    row = out[out["date"] == "2025-01-02"].iloc[0]
    assert int(row["minutes"]) == 60
    assert row["topic"] == "B2"


def test_import_validation_and_truncation():
    from services.validation import MAX_TOPIC_LEN, MAX_TAGS, MAX_TAG_LEN
    long_topic = "X" * (MAX_TOPIC_LEN + 10)
    too_many_tags = ",".join([f"tag{i}" for i in range(MAX_TAGS + 5)])
    long_tag = "Y" * (MAX_TAG_LEN + 5)

    df = pd.DataFrame([
        {"date": "bad-date", "topic": "Invalid", "minutes": -5, "confidence": 9},  # bad row
        {"date": "2025-02-01", "topic": long_topic, "minutes": 2000, "confidence": 0, "tags": too_many_tags + "," + long_tag},
    ])
    inserted, updated, errors = import_dataframe(df)
    # First row should be reported as error and skipped; second inserted
    assert inserted == 1
    assert any("missing date" in e.lower() or "out of bounds" in e.lower() or "bad-date" in e.lower() for e in errors) or len(errors) >= 1
    # Should include messages about truncation or tag limits
    assert any("truncated" in e.lower() or "first" in e.lower() for e in errors)


def test_import_dry_run_no_changes():
    init_db()
    df = pd.DataFrame([
        {"date": "2025-03-01", "topic": "A", "minutes": 30, "confidence": 3},
        {"date": "2025-03-02", "topic": "B", "minutes": 45, "confidence": 4},
    ])
    inserted, updated, errors = import_dataframe(df, dry_run=True)
    assert inserted == 2 and updated == 0
    out = get_all_entries_df()
    # DB should remain empty on dry run
    assert out.empty
