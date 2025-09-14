import datetime as dt

from services.storage import init_db, upsert_entry, get_all_entries_df, export_csv_bytes, export_excel_bytes


def test_storage_roundtrip_and_exports():
    init_db()
    today = dt.date(2025, 1, 1)
    upsert_entry(
        date=today,
        topic="UnitTest",
        minutes=45,
        practiced="pytest",
        challenges="",
        wins="",
        confidence=4,
        tags="test, unit",
    )
    df = get_all_entries_df()
    assert not df.empty
    assert df.shape[0] == 1
    row = df.iloc[0]
    assert row["topic"] == "UnitTest"
    assert int(row["minutes"]) == 45
    assert int(row["confidence"]) == 4
    assert "test" in str(row.get("tags", ""))

    csv = export_csv_bytes(df)
    assert isinstance(csv, (bytes, bytearray)) and len(csv) > 0
    xlsx = export_excel_bytes(df)
    assert isinstance(xlsx, (bytes, bytearray)) and len(xlsx) > 0
