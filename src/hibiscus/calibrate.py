"""Calibration: does the judge reproduce the tier ordering you already gave it?

A win rate against the love pool only means something if the judge and
the pool agree with the taste that built the pool. That is checkable
without any new labeling: score your own ``okay`` and ``nope`` items as
if they were candidates. You already know how they should rank. If
love-tier items don't beat nope-tier items, the number this pipeline
reports for a real candidate does not mean what you think it means —
and you learn that before trusting it, not after.

A pool item scored this way is never compared against itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .cache import JudgeCache
from .compare import ComparisonRecord, run_comparisons
from .judge.base import JudgeAdapter
from .pool import Pool
from .score import WinRateResult, score_candidate
from .tiers import TIER_ORDER, Tier, parse_tier

DEFAULT_MAX_PER_TIER = 25


@dataclass(frozen=True)
class TierCalibration:
    """How one tier's items fared when scored against the reference pool."""

    tier: Tier
    n_candidates: int
    n_available: int
    win_rate: WinRateResult

    @property
    def capped(self) -> bool:
        """True when only some of the tier's items were scored."""
        return self.n_candidates < self.n_available


@dataclass(frozen=True)
class CalibrationReport:
    """Observed tier ordering versus the ordering you hand-assigned.

    ``ordering_holds`` requires two things: no inversion (a lower tier
    outscoring a higher one), and non-zero separation between the top and
    bottom tier. Ties are tolerated because they are expected — when
    every foil is drawn from the love tier, ``okay`` and ``nope`` can
    both legitimately floor near zero. What must never happen is a lower
    tier scoring *above* a higher one, or every tier landing on the same
    number, which means the judge is telling you nothing.
    """

    reference_tier: Tier
    by_tier: dict[Tier, TierCalibration]
    ordering_holds: bool
    inversions: list[tuple[Tier, Tier]]
    separation: "float | None"
    records: list[ComparisonRecord]
    tiers_without_signal: list[Tier]

    @property
    def tiers_high_to_low(self) -> list[Tier]:
        return sorted(self.by_tier, key=lambda t: TIER_ORDER[t], reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_tier": self.reference_tier.value,
            "ordering_holds": self.ordering_holds,
            "inversions": [[hi.value, lo.value] for hi, lo in self.inversions],
            "tiers_without_signal": [t.value for t in self.tiers_without_signal],
            "separation": self.separation,
            "tiers": {
                tier.value: {
                    "n_candidates": cal.n_candidates,
                    "n_available": cal.n_available,
                    "capped": cal.capped,
                    "wins": cal.win_rate.wins,
                    "n": cal.win_rate.n,
                    "win_rate": cal.win_rate.point_estimate,
                    "wilson_lower": cal.win_rate.lower,
                    "wilson_upper": cal.win_rate.upper,
                }
                for tier, cal in self.by_tier.items()
            },
        }


def run_calibration(
    pool: Pool,
    judge: JudgeAdapter,
    *,
    reference_tier: "Tier | str" = Tier.LOVE,
    tiers: "Sequence[Tier | str]" = (Tier.LOVE, Tier.OKAY, Tier.NOPE),
    k: int = 2,
    seed: int = 0,
    question: "str | None" = None,
    model: str = "unknown",
    cache: "JudgeCache | None" = None,
    max_per_tier: "int | None" = DEFAULT_MAX_PER_TIER,
    now: "Callable[[], str] | None" = None,
) -> CalibrationReport:
    """Score each tier's own items against the reference tier.

    Every candidate faces the same sampled foils (one seed for the whole
    run), so tiers differ by their contents rather than by which
    references they happened to draw. ``max_per_tier`` caps the judge
    calls; the cap is recorded on each :class:`TierCalibration` rather
    than applied silently.
    """
    reference_tier = parse_tier(reference_tier)
    resolved = [parse_tier(t) for t in tiers]

    by_tier: dict[Tier, TierCalibration] = {}
    all_records: list[ComparisonRecord] = []

    for tier in resolved:
        available = pool.list(tier=tier)
        if not available:
            continue
        selected = available[:max_per_tier] if max_per_tier else available

        tier_records: list[ComparisonRecord] = []
        for rated in selected:
            tier_records.extend(
                run_comparisons(
                    rated.artifact,
                    pool,
                    judge,
                    tier=reference_tier,
                    k=k,
                    seed=seed,
                    question=question,
                    model=model,
                    cache=cache,
                    dimension=f"calibration:{tier.value}",
                    exclude_ids={rated.id},
                    now=now,
                )
            )

        all_records.extend(tier_records)
        by_tier[tier] = TierCalibration(
            tier=tier,
            n_candidates=len(selected),
            n_available=len(available),
            win_rate=score_candidate(tier_records),
        )

    ordered = sorted(by_tier, key=lambda t: TIER_ORDER[t], reverse=True)
    rates = [by_tier[t].win_rate.point_estimate for t in ordered]

    # A tier whose every pair tied has no win rate at all. Its
    # point_estimate is 0.0 by convention, which would masquerade as a
    # genuine zero and could fake a passing ordering, so it invalidates
    # the check instead.
    without_signal = [t for t in ordered if not by_tier[t].win_rate.has_signal]

    inversions = [
        (ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1) if rates[i] < rates[i + 1]
    ]
    separation = rates[0] - rates[-1] if len(rates) > 1 else None
    ordering_holds = (
        bool(rates)
        and not inversions
        and not without_signal
        and separation is not None
        and separation > 0
    )

    return CalibrationReport(
        reference_tier=reference_tier,
        by_tier=by_tier,
        ordering_holds=ordering_holds,
        inversions=inversions,
        separation=separation,
        records=all_records,
        tiers_without_signal=without_signal,
    )
