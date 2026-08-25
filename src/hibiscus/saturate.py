"""Is the reference pool big enough? Answer it empirically.

Scores a fixed set of candidates against reference subsets of growing
size, repeating each size over several seeded subsets. When growing the
pool stops moving the win rates — and stops reordering the candidates —
the pool has saturated and further rating buys little.

This measures only that *the measurement has stopped moving*. A pool can
saturate around the wrong taste: consistently, reproducibly wrong. Use
:mod:`hibiscus.calibrate` for the separate question of whether the pool
and judge reproduce the tier ordering you assigned by hand.

Candidate *ordering* usually stabilizes well before absolute win rates
do, and ordering is often what the caller actually needs, so both are
reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Callable, Sequence

from .artifact import Artifact
from .cache import JudgeCache
from .compare import run_comparisons
from .judge.base import JudgeAdapter
from .pool import Pool
from .rng import sample_deterministic
from .score import score_candidate
from .tiers import Tier, parse_tier

DEFAULT_STEP = 5
DEFAULT_REPEATS = 3
#: Win rates counted as settled once the mean absolute move falls below this.
DEFAULT_RATE_TOLERANCE = 0.05
#: Ordering counted as settled once Kendall tau-b reaches this.
DEFAULT_TAU_TOLERANCE = 0.9


def kendall_tau(xs: Sequence[float], ys: Sequence[float]) -> "float | None":
    """Kendall tau-b between two rankings. ``None`` when undefined.

    Tau-b is used rather than tau-a because tied win rates are common
    with small pools and must not be counted as disagreements.
    """
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must be the same length")
    if n < 2:
        return None

    total_pairs = n * (n - 1) // 2
    concordant = discordant = tied_x = tied_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0:
                tied_x += 1
            if dy == 0:
                tied_y += 1
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1

    # tau-b = (C - D) / sqrt((n0 - n1)(n0 - n2)), where n1/n2 are the pairs
    # tied in x and in y. Zero denominator means one side is constant, so
    # no ordering can be compared at all.
    denominator = ((total_pairs - tied_x) * (total_pairs - tied_y)) ** 0.5
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


@dataclass(frozen=True)
class SaturationStep:
    """Results at one reference-pool size."""

    size: int
    repeats: int
    mean_win_rates: dict[str, float]
    within_size_stdev: float
    rate_delta: "float | None"
    tau_vs_previous: "float | None"

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "repeats": self.repeats,
            "mean_win_rates": self.mean_win_rates,
            "within_size_stdev": self.within_size_stdev,
            "rate_delta": self.rate_delta,
            "tau_vs_previous": self.tau_vs_previous,
        }


@dataclass(frozen=True)
class SaturationReport:
    """Whether, and where, the pool stopped changing the answer."""

    steps: list[SaturationStep]
    rate_saturated_at: "int | None"
    ordering_saturated_at: "int | None"
    rate_tolerance: float
    tau_tolerance: float
    pool_size: int
    n_candidates: int

    @property
    def saturated(self) -> bool:
        return self.rate_saturated_at is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "n_candidates": self.n_candidates,
            "rate_tolerance": self.rate_tolerance,
            "tau_tolerance": self.tau_tolerance,
            "rate_saturated_at": self.rate_saturated_at,
            "ordering_saturated_at": self.ordering_saturated_at,
            "steps": [s.to_dict() for s in self.steps],
        }


def plan_sizes(available: int, *, step: int = DEFAULT_STEP) -> list[int]:
    """Reference-subset sizes to try, always ending at the full pool."""
    sizes = list(range(step, available + 1, step))
    if not sizes or sizes[-1] != available:
        sizes.append(available)
    return [s for s in sizes if s >= 2]


def run_saturation(
    pool: Pool,
    candidates: Sequence[Artifact],
    judge: JudgeAdapter,
    *,
    tier: "Tier | str" = Tier.LOVE,
    seed: int = 0,
    step: int = DEFAULT_STEP,
    repeats: int = DEFAULT_REPEATS,
    sizes: "Sequence[int] | None" = None,
    question: "str | None" = None,
    model: str = "unknown",
    cache: "JudgeCache | None" = None,
    rate_tolerance: float = DEFAULT_RATE_TOLERANCE,
    tau_tolerance: float = DEFAULT_TAU_TOLERANCE,
    now: "Callable[[], str] | None" = None,
) -> SaturationReport:
    """Score ``candidates`` against growing reference subsets.

    Each (size, repeat) draws its own seeded subset and uses the whole
    subset as the reference set. Subsets at different sizes overlap
    heavily, so a shared ``cache`` turns most of the work into hits —
    pass one, this command is comparison-hungry.
    """
    tier = parse_tier(tier)
    available = len(pool.filter_by_tier(tier))
    if available < 2:
        raise ValueError(
            f"tier {tier.value!r} has {available} artifacts; need at least 2 to test saturation"
        )
    if not candidates:
        raise ValueError("need at least one candidate to test saturation")

    plan = list(sizes) if sizes else plan_sizes(available, step=step)
    plan = [s for s in plan if 2 <= s <= available]

    steps: list[SaturationStep] = []
    previous_rates: "dict[str, float] | None" = None

    for size in plan:
        per_repeat: list[dict[str, float]] = []
        for repeat in range(repeats):
            subset = sample_deterministic(
                pool.filter_by_tier(tier), size, seed + repeat * 7919, key=lambda r: r.id
            )
            subset_ids = {r.id for r in subset}
            excluded = {r.id for r in pool.filter_by_tier(tier)} - subset_ids

            rates: dict[str, float] = {}
            for candidate in candidates:
                records = run_comparisons(
                    candidate,
                    pool,
                    judge,
                    tier=tier,
                    k=size,
                    seed=seed + repeat * 7919,
                    question=question,
                    model=model,
                    cache=cache,
                    exclude_ids=excluded | {candidate.id},
                    now=now,
                )
                result = score_candidate(records)
                if result.has_signal:
                    rates[candidate.id] = result.point_estimate
            per_repeat.append(rates)

        shared = set(per_repeat[0])
        for rates in per_repeat[1:]:
            shared &= set(rates)
        ordered_ids = sorted(shared)

        mean_rates = {
            cid: mean([rates[cid] for rates in per_repeat]) for cid in ordered_ids
        }
        spreads = [pstdev([rates[cid] for rates in per_repeat]) for cid in ordered_ids]
        within = mean(spreads) if spreads else 0.0

        rate_delta: "float | None" = None
        tau: "float | None" = None
        if previous_rates is not None:
            common = sorted(set(mean_rates) & set(previous_rates))
            if common:
                rate_delta = mean(abs(mean_rates[c] - previous_rates[c]) for c in common)
                tau = kendall_tau(
                    [previous_rates[c] for c in common], [mean_rates[c] for c in common]
                )

        steps.append(
            SaturationStep(
                size=size,
                repeats=repeats,
                mean_win_rates=mean_rates,
                within_size_stdev=within,
                rate_delta=rate_delta,
                tau_vs_previous=tau,
            )
        )
        previous_rates = mean_rates

    rate_at = _first_settled(steps, lambda s: s.rate_delta is not None and s.rate_delta <= rate_tolerance)
    tau_at = _first_settled(
        steps, lambda s: s.tau_vs_previous is not None and s.tau_vs_previous >= tau_tolerance
    )

    return SaturationReport(
        steps=steps,
        rate_saturated_at=rate_at,
        ordering_saturated_at=tau_at,
        rate_tolerance=rate_tolerance,
        tau_tolerance=tau_tolerance,
        pool_size=available,
        n_candidates=len(candidates),
    )


def _first_settled(
    steps: Sequence[SaturationStep], predicate: Callable[[SaturationStep], bool]
) -> "int | None":
    """Size at the first of two consecutive steps that both satisfy ``predicate``.

    Two in a row, because a single quiet step is easy to hit by chance.
    """
    for i in range(len(steps) - 1):
        if predicate(steps[i]) and predicate(steps[i + 1]):
            return steps[i].size
    return None
