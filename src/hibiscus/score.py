"""Aggregate comparisons into win rates with Wilson score intervals."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .compare import ComparisonRecord


@dataclass(frozen=True)
class WinRateResult:
    """A win rate with its Wilson score confidence interval."""

    wins: int
    n: int
    point_estimate: float
    lower: float
    upper: float
    z: float = 1.96


def wilson_interval(wins: int, n: int, z: float = 1.96) -> WinRateResult:
    """Compute the Wilson score interval for ``wins`` out of ``n`` trials.

    Handles the degenerate cases (n=0, wins=0, wins=n, n=1) without
    dividing by zero or producing bounds outside [0, 1].
    """
    if n < 0 or wins < 0 or wins > n:
        raise ValueError(f"invalid wins/n: wins={wins}, n={n}")
    if n == 0:
        return WinRateResult(wins=0, n=0, point_estimate=0.0, lower=0.0, upper=1.0, z=z)

    p_hat = wins / n
    denom = 1 + z**2 / n
    center = p_hat + z**2 / (2 * n)
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)
    lower = (center - spread) / denom
    upper = (center + spread) / denom
    return WinRateResult(
        wins=wins,
        n=n,
        point_estimate=p_hat,
        lower=max(0.0, lower),
        upper=min(1.0, upper),
        z=z,
    )


def score_candidate(
    records: Iterable[ComparisonRecord],
    *,
    candidate_id: "str | None" = None,
    dimension: "str | None" = None,
    z: float = 1.96,
) -> WinRateResult:
    """Win rate for one candidate (optionally on one dimension) across records."""
    wins = 0
    n = 0
    for r in records:
        if candidate_id is not None and r.candidate_id != candidate_id:
            continue
        if dimension is not None and r.dimension != dimension:
            continue
        n += 1
        if r.winner == "candidate":
            wins += 1
    return wilson_interval(wins, n, z=z)


def score_all(
    records: Iterable[ComparisonRecord], *, z: float = 1.96
) -> dict[tuple[str, str], WinRateResult]:
    """Score every (candidate_id, dimension) pair present in ``records``."""
    grouped: dict[tuple[str, str], list[ComparisonRecord]] = defaultdict(list)
    for r in records:
        grouped[(r.candidate_id, r.dimension)].append(r)
    return {key: score_candidate(rs, z=z) for key, rs in grouped.items()}


@dataclass(frozen=True)
class SpreadResult:
    """How much the win rates actually spread out across a candidate set.

    This is the guard against the failure that motivated the library:
    scores compressed into a narrow band, every output looking alike.
    Per-candidate win rates alone won't show it — you have to look at the
    distribution.

    ``dispersion_ratio`` compares the observed spread to the spread you
    would expect from sampling noise alone if every candidate had the
    same true win rate. Around 1.0 means the differences between
    candidates are indistinguishable from coin-flips: the judge is not
    discriminating, whatever the individual numbers look like. Above 1.0
    means real signal. It is ``None`` when it cannot be computed (fewer
    than two candidates, or every single comparison went the same way).
    """

    n_candidates: int
    mean: float
    stdev: float
    minimum: float
    maximum: float
    expected_stdev: "float | None"
    dispersion_ratio: "float | None"
    discriminating: bool
    threshold: float

    @property
    def spread(self) -> float:
        """Difference between the best and worst candidate win rate."""
        return self.maximum - self.minimum


def score_spread(
    records: Iterable[ComparisonRecord],
    *,
    dimension: "str | None" = None,
    threshold: float = 1.2,
) -> SpreadResult:
    """Measure how far apart candidates actually landed.

    ``threshold`` is the dispersion ratio above which the set is called
    discriminating. It is a heuristic, not a test statistic — 1.0 is the
    pure-noise expectation and the default leaves some headroom.
    """
    per_candidate: dict[str, list[ComparisonRecord]] = defaultdict(list)
    for r in records:
        if dimension is not None and r.dimension != dimension:
            continue
        per_candidate[r.candidate_id].append(r)

    results = [score_candidate(rs) for rs in per_candidate.values()]
    rates = [r.point_estimate for r in results]
    n = len(rates)

    if n < 2:
        return SpreadResult(
            n_candidates=n,
            mean=rates[0] if rates else 0.0,
            stdev=0.0,
            minimum=rates[0] if rates else 0.0,
            maximum=rates[0] if rates else 0.0,
            expected_stdev=None,
            dispersion_ratio=None,
            discriminating=False,
            threshold=threshold,
        )

    mean = sum(rates) / n
    observed_var = sum((r - mean) ** 2 for r in rates) / (n - 1)

    # Null model: every candidate shares the pooled win rate, so the only
    # variation is binomial noise from a finite number of comparisons.
    total_wins = sum(r.wins for r in results)
    total_n = sum(r.n for r in results)
    pooled = total_wins / total_n if total_n else 0.0
    mean_inverse_n = sum(1 / r.n for r in results if r.n) / n
    expected_var = pooled * (1 - pooled) * mean_inverse_n

    if expected_var <= 0:
        expected_stdev: "float | None" = 0.0 if total_n else None
        ratio: "float | None" = None
        discriminating = False
    else:
        expected_stdev = math.sqrt(expected_var)
        ratio = math.sqrt(observed_var / expected_var)
        discriminating = ratio > threshold

    return SpreadResult(
        n_candidates=n,
        mean=mean,
        stdev=math.sqrt(observed_var),
        minimum=min(rates),
        maximum=max(rates),
        expected_stdev=expected_stdev,
        dispersion_ratio=ratio,
        discriminating=discriminating,
        threshold=threshold,
    )
