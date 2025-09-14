import datetime as dt

from services.storage import init_db, upsert_entry, get_all_entries_df, delete_entry


def test_delete_entry_by_date():
    init_db()
    d = dt.date(2025, 1, 2)
    upsert_entry(date=d, topic="T", minutes=5, practiced="p", challenges="", wins="", confidence=3, tags="a")
    df = get_all_entries_df()
    assert not df.empty
    delete_entry(d)
    df2 = get_all_entries_df()
    assert df2.empty

