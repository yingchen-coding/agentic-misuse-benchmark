"""Small-sample statistics for evaluation gates (standard library only).

A gate that compares a point estimate with a bar says nothing about whether the suite is
big enough to tell a pass from a fail. These helpers put an interval around each measured
rate, report how many samples would resolve an unresolved check, and test paired
before/after outcomes on the same cases.
"""
from __future__ import annotations

import math

Z95 = 1.959963984540054


def _wilson(rate: float, n: float, z: float) -> tuple[float, float]:
    denom = 1 + z * z / n
    centre = (rate + z * z / (2 * n)) / denom
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (well behaved at 0 and n)."""
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if not 0 <= successes <= n:
        raise ValueError(f"successes must be within 0..{n}, got {successes}")
    lo, hi = _wilson(successes / n, n, z)
    # Pin the closed ends exactly; float rounding otherwise leaves 1e-17 and 0.9999999999999999.
    return (0.0 if successes == 0 else lo), (1.0 if successes == n else hi)


def zero_failure_upper_bound(n: int, confidence: float = 0.95) -> float:
    """Exact one-sided upper bound on a failure rate after n trials with no failures."""
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return 1 - (1 - confidence) ** (1 / n)


def n_to_resolve(rate: float, bar: float, z: float = Z95, max_n: int = 1_000_000) -> int | None:
    """Smallest sample size at which a Wilson interval around the observed `rate` would
    exclude `bar` — how big the suite must be for this check to be decided by data.

    None when the rate sits exactly on the bar, or more than `max_n` samples are needed.
    """
    if not 0 <= rate <= 1 or not 0 <= bar <= 1:
        raise ValueError(f"rate and bar must be within [0, 1], got {rate} and {bar}")
    if rate == bar:
        return None

    def excludes(n: int) -> bool:
        lo, hi = _wilson(rate, n, z)
        return hi < bar if rate < bar else lo > bar

    if not excludes(max_n):
        return None
    lo, hi = 1, 1
    while not excludes(hi):
        lo, hi = hi, hi * 2
    while lo < hi:
        mid = (lo + hi) // 2
        if excludes(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def mcnemar_exact(regressed: int, improved: int) -> float:
    """Two-sided exact McNemar p-value for paired outcomes on the same cases.

    `regressed` counts cases that passed before and fail now, `improved` the reverse;
    cases with the same outcome both times carry no information about a change.
    """
    if regressed < 0 or improved < 0:
        raise ValueError("discordant counts must be non-negative")
    n = regressed + improved
    if n == 0:
        return 1.0
    k = min(regressed, improved)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def kappa_interval(observed: float, expected: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Large-sample confidence interval for Cohen's kappa from its observed and chance
    agreement."""
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if not 0 <= expected < 1:
        raise ValueError(f"expected agreement must be in [0, 1), got {expected}")
    kappa = (observed - expected) / (1 - expected)
    se = math.sqrt(observed * (1 - observed) / (n * (1 - expected) ** 2))
    return max(-1.0, kappa - z * se), min(1.0, kappa + z * se)
