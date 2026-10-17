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
