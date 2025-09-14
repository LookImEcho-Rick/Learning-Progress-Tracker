import datetime as dt
import pandas as pd

from services.metrics import compute_streaks, weekly_minutes, week_bounds_for


def test_compute_streaks_current_and_longest():
    today = dt.date.today()
    dates = [today - dt.timedelta(days=d) for d in [3,2,1,0]]  # 4-day streak to today
    cur, longest = compute_streaks(dates)
    assert cur == 4
    assert longest >= 4

    dates = [today - dt.timedelta(days=10), today - dt.timedelta(days=9), today - dt.timedelta(days=8), today - dt.timedelta(days=2), today]
    cur, longest = compute_streaks(dates)
    assert cur == 1
    assert longest == 3


def test_weekly_minutes_range():
    today = dt.date.today()
    start, end = week_bounds_for(today)
    df = pd.DataFrame({
        "date": [start, start + dt.timedelta(days=2), end, end + dt.timedelta(days=1)],
        "minutes": [30, 60, 10, 999],
        "confidence": [3,3,3,3]
    })
    assert weekly_minutes(df, today) == 100

