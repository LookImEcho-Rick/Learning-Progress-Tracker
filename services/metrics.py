from __future__ import annotations

import datetime as dt
import pandas as pd


def compute_progress_score(minutes: int, confidence: int) -> int:
    return int(minutes) * int(confidence)


def compute_week_index(date: dt.date, start_date: dt.date) -> int:
    """Week index since start_date (0-based), 7-day windows.
    Example: start_date=2025-01-01, date=2025-01-07 -> 0, 2025-01-08 -> 1.
    """
    delta = (date - start_date).days
    return max(0, delta // 7)


def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["progress_score"] = out.apply(lambda r: compute_progress_score(int(r["minutes"]), int(r["confidence"])), axis=1)
    start_date = out["date"].min()
    out["week_index"] = out["date"].apply(lambda d: compute_week_index(d, start_date))
    return out


def compute_streaks(dates: list[dt.date]) -> tuple[int, int]:
    """Return (current_streak, longest_streak) based on a set of study dates.
    Current streak counts consecutive days ending at today.
    """
    if not dates:
        return 0, 0
    uniq = sorted(set(dates))
    longest = 1
    current = 1 if uniq[-1] == dt.date.today() else 0
    # Walk consecutive runs
    run = 1
    for i in range(1, len(uniq)):
        if (uniq[i] - uniq[i - 1]).days == 1:
            run += 1
        else:
            longest = max(longest, run)
            run = 1
    longest = max(longest, run)
    # compute current streak back from today
    if uniq[-1] != dt.date.today():
        current = 0
    else:
        current = 1
        for i in range(len(uniq) - 1, 0, -1):
            if (uniq[i] - uniq[i - 1]).days == 1:
                current += 1
            else:
                break
    return current, longest


def week_bounds_for(date: dt.date) -> tuple[dt.date, dt.date]:
    start = date - dt.timedelta(days=date.weekday())  # Monday
    end = start + dt.timedelta(days=6)
    return start, end


def weekly_minutes(df: pd.DataFrame, week_of: dt.date | None = None) -> int:
    if df.empty:
        return 0
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"]).dt.date
    ref = week_of or dt.date.today()
    start, end = week_bounds_for(ref)
    m = (df2["date"] >= start) & (df2["date"] <= end)
    return int(df2.loc[m, "minutes"].sum())
