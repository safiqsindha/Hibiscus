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
