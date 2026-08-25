"""Aggregate comparisons into win rates with Wilson score intervals.

Scoring works on *pairs*, not on individual judge calls: the two orders
of a comparison are resolved into one outcome first (see
:mod:`hibiscus.pairs`), and ties are excluded from the denominator.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .compare import ComparisonRecord
from .pairs import PairOutcome, PairSummary, count_legacy_records, resolve_pairs, summarize_pairs

#: |r| at or above which length correlation is called out. Heuristic.
LENGTH_BIAS_THRESHOLD = 0.4


@dataclass(frozen=True)
class WinRateResult:
    """A win rate with its Wilson score confidence interval.

    ``n`` counts *decisive pairs* — ties are excluded — so ``wins/n`` is
    the share of comparisons the candidate actually won. ``summary``
    carries the tie counts that ``n`` leaves out.
    """

    wins: int
    n: int
    point_estimate: float
    lower: float
    upper: float
    z: float = 1.96
    summary: "PairSummary | None" = None

    @property
    def has_signal(self) -> bool:
        """False when every pair tied, so no win rate is defined."""
        return self.n > 0


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


def _select(
    records: Iterable[ComparisonRecord],
    candidate_id: "str | None",
    dimension: "str | None",
) -> list[ComparisonRecord]:
    return [
        r
        for r in records
        if (candidate_id is None or r.candidate_id == candidate_id)
        and (dimension is None or r.dimension == dimension)
    ]


def score_candidate(
    records: Iterable[ComparisonRecord],
    *,
    candidate_id: "str | None" = None,
    dimension: "str | None" = None,
    z: float = 1.96,
) -> WinRateResult:
    """Win rate for one candidate (optionally on one dimension).

    Both orders of each comparison are resolved into a single pair
    outcome before counting, and ties are excluded from the denominator.
    When every pair ties, the result carries ``n == 0`` and
    ``has_signal`` is False rather than raising or inventing a rate.
    """
    selected = _select(records, candidate_id, dimension)
    outcomes = resolve_pairs(selected)
    summary = summarize_pairs(outcomes, legacy_records=count_legacy_records(selected))
    result = wilson_interval(summary.wins, summary.decisive, z=z)
    return WinRateResult(
        wins=result.wins,
        n=result.n,
        point_estimate=result.point_estimate,
        lower=result.lower,
        upper=result.upper,
        z=result.z,
        summary=summary,
    )


def score_all(
    records: Iterable[ComparisonRecord], *, z: float = 1.96
) -> dict[tuple[str, str], WinRateResult]:
    """Score every (candidate_id, dimension) pair present in ``records``."""
    grouped: dict[tuple[str, str], list[ComparisonRecord]] = defaultdict(list)
    for r in records:
        grouped[(r.candidate_id, r.dimension)].append(r)
    return {key: score_candidate(rs, z=z) for key, rs in grouped.items()}


@dataclass(frozen=True)
class LengthBiasResult:
    """Correlation between candidate text length and win rate.

    Length is the second-best-documented pairwise judge bias after
    position: judges over-prefer longer texts on tasks that do not
    penalize verbosity. This is reported, never corrected for — what to
    do about it depends on whether length is legitimately part of quality
    for the artifacts being judged, which only the caller knows.
    """

    n_candidates: int
    correlation: "float | None"
    threshold: float
    flagged: bool
    missing_lengths: int

    def to_dict(self) -> dict:
        return {
            "n_candidates": self.n_candidates,
            "correlation": self.correlation,
            "threshold": self.threshold,
            "flagged": self.flagged,
            "missing_lengths": self.missing_lengths,
        }


def length_bias(
    records: Iterable[ComparisonRecord],
    *,
    dimension: "str | None" = None,
    threshold: float = LENGTH_BIAS_THRESHOLD,
    lengths: "dict[str, int] | None" = None,
) -> LengthBiasResult:
    """Correlate candidate text length against win rate across candidates.

    Lengths come from the comparison records themselves (recorded at
    compare time). ``lengths`` overrides them, for records written before
    the field existed.
    """
    from .report import pearson

    selected = _select(records, None, dimension)
    grouped: dict[str, list[ComparisonRecord]] = defaultdict(list)
    for r in selected:
        grouped[r.candidate_id].append(r)

    xs: list[float] = []
    ys: list[float] = []
    missing = 0
    for candidate_id, group in sorted(grouped.items()):
        if lengths is not None and candidate_id in lengths:
            length = lengths[candidate_id]
        else:
            found = [r.candidate_length for r in group if r.candidate_length is not None]
            if not found:
                missing += 1
                continue
            length = found[0]
        result = score_candidate(group)
        if not result.has_signal:
            continue
        xs.append(float(length))
        ys.append(result.point_estimate)

    if len(xs) < 2:
        return LengthBiasResult(
            n_candidates=len(xs),
            correlation=None,
            threshold=threshold,
            flagged=False,
            missing_lengths=missing,
        )

    corr = pearson(xs, ys)
    return LengthBiasResult(
        n_candidates=len(xs),
        correlation=corr,
        threshold=threshold,
        flagged=abs(corr) >= threshold,
        missing_lengths=missing,
    )


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

    # Candidates whose every pair tied have no win rate to spread.
    results = [score_candidate(rs) for rs in per_candidate.values()]
    results = [r for r in results if r.has_signal]
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
