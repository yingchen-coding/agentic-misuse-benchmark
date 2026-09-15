import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evalstats import (
    Z95,
    _wilson,
    kappa_interval,
    mcnemar_exact,
    n_to_resolve,
    wilson_interval,
    zero_failure_upper_bound,
)


def test_wilson_interval_matches_reference_values():
    assert wilson_interval(3, 6) == pytest.approx((0.1876, 0.8124), abs=1e-4)
    assert wilson_interval(21, 25) == pytest.approx((0.6534, 0.9360), abs=1e-4)


def test_wilson_interval_stays_inside_zero_and_one_at_the_edges():
    lo, hi = wilson_interval(0, 25)
    assert lo == 0.0 and hi == pytest.approx(0.1332, abs=1e-4)
    lo, hi = wilson_interval(25, 25)
    assert hi == 1.0 and lo == pytest.approx(0.8668, abs=1e-4)


@pytest.mark.parametrize("successes, n", [(1, 0), (-1, 5), (6, 5)])
def test_wilson_interval_rejects_impossible_counts(successes, n):
    with pytest.raises(ValueError):
        wilson_interval(successes, n)


def test_zero_failure_bound_matches_the_committed_adjudication_summary():
    assert round(zero_failure_upper_bound(240), 3) == 0.012
    assert round(zero_failure_upper_bound(30), 3) == 0.095


@pytest.mark.parametrize("rate, bar", [(0.0, 0.05), (0.5, 0.6), (0.84, 0.8), (1.0, 0.6)])
def test_n_to_resolve_is_the_smallest_sample_that_decides_the_bar(rate, bar):
    def decided(n):
        lo, hi = _wilson(rate, n, Z95)
        return hi < bar if rate < bar else lo > bar

    n = n_to_resolve(rate, bar)
    assert decided(n) and (n == 1 or not decided(n - 1))


def test_zero_false_positives_need_73_benign_cases_to_show_a_rate_under_5_percent():
    n = n_to_resolve(0.0, 0.05)
    assert n == 73
    assert wilson_interval(0, 73)[1] < 0.05 <= wilson_interval(0, 72)[1]


def test_n_to_resolve_is_none_when_the_rate_sits_on_the_bar():
    assert n_to_resolve(0.6, 0.6) is None


def test_mcnemar_exact_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(3, 3) == 1.0
    assert mcnemar_exact(1, 5) == pytest.approx(14 / 64)
    assert mcnemar_exact(25, 0) == pytest.approx(2 * 0.5 ** 25)


def test_kappa_interval_contains_kappa_and_widens_with_fewer_samples():
    wide = kappa_interval(0.783, 0.8, 60)
    narrow = kappa_interval(0.783, 0.8, 240)
    kappa = (0.783 - 0.8) / 0.2
    assert wide[0] < narrow[0] <= kappa <= narrow[1] < wide[1]
    assert not math.isnan(narrow[0])


def test_kappa_interval_rejects_degenerate_inputs():
    with pytest.raises(ValueError):
        kappa_interval(1.0, 1.0, 10)
    with pytest.raises(ValueError):
        kappa_interval(0.5, 0.5, 0)
