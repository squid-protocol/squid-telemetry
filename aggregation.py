"""Aggregation helpers for GitHub traffic tables that store ROLLING-window snapshots.

`referring_sites` and `popular_content` hold one row per (fetch_date, key), and every row
is GitHub's trailing-14-day total as of that fetch. Summing across fetch_dates counts the
same visit up to ~14 times. These helpers pick only snapshots whose windows do not overlap.

Even then the result is "visitor-windows": a person who shows up in two different
windows is counted twice, because GitHub exposes no identity to deduplicate against.
"""
import pandas as pd

WINDOW_DAYS = 14


def non_overlapping_fetch_dates(fetch_dates, window_days=WINDOW_DAYS):
    """Walk back from the newest fetch, keeping a snapshot only if it is at least
    `window_days` older than the previously kept one. Returns dates (Timestamps), newest first."""
    ds = sorted(pd.to_datetime(pd.Series(list(fetch_dates))).unique(), reverse=True)
    kept = []
    for d in ds:
        d = pd.Timestamp(d)
        if not kept or (kept[-1] - d).days >= window_days:
            kept.append(d)
    return kept


def all_time_window_totals(df, key_col, value_cols=("unique_visitors", "total_views"),
                           date_col="fetch_date", window_days=WINDOW_DAYS):
    """Sum value_cols per key over non-overlapping rolling-window snapshots only."""
    if df.empty:
        return pd.DataFrame(columns=[key_col, *value_cols])
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    keep = non_overlapping_fetch_dates(d[date_col].unique(), window_days)
    return (d[d[date_col].isin(keep)].groupby(key_col)[list(value_cols)].sum()
            .sort_values(value_cols[0], ascending=False).reset_index())
