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


def test_checkout_counting_per_target():
    os.environ.setdefault("TRAFFIC_READ_PAT", "x")
    from scraper import count_checkouts
    wf = """
jobs:
  a:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: squid-protocol/cics-crucible
          path: cics
      # - uses: actions/checkout@v4 (commented out, not counted)
      - uses: actions/checkout@v4
        with:
          repository: ${{ github.repository }}
"""
    got = count_checkouts(wf, "gitgalaxy")
    assert got["squid-protocol/gitgalaxy"] == 2   # bare checkout + expression -> own repo
    assert got["squid-protocol/cics-crucible"] == 1


def test_shell_fetches_counted():
    os.environ.setdefault("TRAFFIC_READ_PAT", "x")
    from scraper import count_checkouts
    wf = """
      - run: |
          ci_retry.sh 4 10 -- bash -c 'rm -rf language-crucible && git clone --branch "$1" --depth 1 https://github.com/squid-protocol/language-crucible.git language-crucible' _ "$ref"
          git -C cics-crucible remote add origin https://github.com/squid-protocol/cics-crucible.git
          # git clone https://github.com/squid-protocol/estate-crucible (comment)
"""
    got = count_checkouts(wf, "gitgalaxy")
    assert got["squid-protocol/language-crucible"] == 1
    assert got["squid-protocol/cics-crucible"] == 1
    assert "squid-protocol/estate-crucible" not in got
