import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generate_graph import _fmt_count, _spread_positions


def test_close_labels_pushed_apart_in_input_order():
    out = _spread_positions([0.50, 0.10, 0.51, 0.505], min_gap=0.04)
    assert out[1] == 0.10  # isolated label stays on its line
    stacked = sorted([out[0], out[2], out[3]])
    assert all(b - a >= 0.04 - 1e-9 for a, b in zip(stacked, stacked[1:]))


def test_stack_stays_under_ceiling():
    out = _spread_positions([0.97, 0.975, 0.98], min_gap=0.04, upper=0.98)
    assert max(out) <= 0.98
    s = sorted(out)
    assert all(b - a >= 0.04 - 1e-9 for a, b in zip(s, s[1:]))


def test_fmt_count():
    assert [_fmt_count(v) for v in (165330, 9673, 1000, 412)] == ['165k', '9.7k', '1k', '412']


def test_clone_split_sums_to_total():
    from generate_graph import split_clone_sources
    # 100 clones from 20 machines, CI ran 15 checkouts
    assert split_clone_sources(100, 20, 15) == {'own_ci': 15, 'repeat': 80, 'outside': 5}
    # CI estimate larger than the unique cloners is capped
    assert split_clone_sources(10, 8, 50) == {'own_ci': 8, 'repeat': 2, 'outside': 0}
    assert split_clone_sources(0, 0, 3) == {'own_ci': 0, 'repeat': 0, 'outside': 0}


def test_ci_rate_collapses_authenticated_checkouts():
    import pandas as pd
    from generate_graph import ci_unique_rate, split_clone_sources
    # 30 days where every 12 CI checkouts add one unique cloner on top of 40 outside ones
    ci = pd.Series([120 * (1 + d % 5) for d in range(30)])
    days = pd.DataFrame({'own_ci_est': ci, 'unique_cloners': 40 + ci // 12})
    rate = ci_unique_rate(days)
    assert abs(rate - 1 / 12) < 0.01
    # 600 CI checkouts, 90 unique: CI accounts for ~50 uniques, ~40 left as outside
    got = split_clone_sources(2000, 90, 600, rate)
    assert got['own_ci'] == 50 and got['outside'] == 40 and sum(got.values()) == 2000


def test_ci_rate_short_history_falls_back_to_one():
    import pandas as pd
    from generate_graph import ci_unique_rate
    days = pd.DataFrame({'own_ci_est': [1, 5, 9], 'unique_cloners': [1, 1, 1]})
    assert ci_unique_rate(days) == 1.0
