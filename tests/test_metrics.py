import datetime as dt

from services.metrics import compute_week_index


def test_compute_week_index_same_week():
    start = dt.date(2024, 12, 30)
    d1 = dt.date(2025, 1, 1)
    d2 = dt.date(2025, 1, 5)
    assert compute_week_index(d1, start) == 0
    assert compute_week_index(d2, start) == 0


def test_compute_week_index_next_week():
    start = dt.date(2024, 12, 30)
    d = dt.date(2025, 1, 7)  # exactly 8 days after start -> index 1
    assert compute_week_index(d, start) == 1


def test_compute_week_index_year_boundary():
    start = dt.date(2024, 12, 28)
    d = dt.date(2025, 1, 2)
    # (2025-01-02 - 2024-12-28) = 5 days -> week 0
    assert compute_week_index(d, start) == 0

