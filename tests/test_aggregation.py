import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aggregation import all_time_window_totals, non_overlapping_fetch_dates


def _daily_snapshots(days, per_window=10):
    # a steady stream: every daily fetch reports the same trailing-14-day total
    end = pd.Timestamp("2026-10-03")
    return pd.DataFrame([
        {"fetch_date": (end - pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
         "site": "reddit.com", "unique_visitors": per_window, "total_views": per_window * 2}
        for i in range(days)])


def test_overlapping_windows_not_summed():
    df = _daily_snapshots(86)
    naive = df["unique_visitors"].sum()  # 860, the old buggy figure
    fixed = all_time_window_totals(df, "site").iloc[0]["unique_visitors"]
    assert naive == 860
    assert fixed == 10 * 7  # 86 days -> snapshots at 0,14,...,84 -> 7 windows
    assert fixed < naive / 10


def test_snapshots_spaced_at_least_14_days():
    kept = non_overlapping_fetch_dates(_daily_snapshots(60)["fetch_date"])
    assert kept[0] == pd.Timestamp("2026-10-03")
    assert all((a - b).days >= 14 for a, b in zip(kept, kept[1:]))


def test_gap_in_history_and_empty():
    df = _daily_snapshots(1)
    assert all_time_window_totals(df, "site").iloc[0]["unique_visitors"] == 10
    assert all_time_window_totals(df.iloc[0:0], "site").empty


def test_engine_checkout_counting():
    os.environ.setdefault("TRAFFIC_READ_PAT", "x")
    from scraper import count_engine_checkouts
    wf = """
jobs:
  a:
    steps:
      - uses: actions/checkout@v4
      - name: other
        uses: actions/checkout@v4
        with:
          repository: squid-protocol/gitgalaxy
      - name: sibling
        uses: actions/checkout@v4
        with:
          repository: squid-protocol/language-crucible
"""
    assert count_engine_checkouts(wf, "gitgalaxy") == 2      # default + explicit engine
    assert count_engine_checkouts(wf, "keyword-rosetta") == 1  # only the explicit engine one
