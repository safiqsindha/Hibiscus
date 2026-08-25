"""Bradley-Terry ranking of candidates against each other. Optional.

This answers a different question from the rest of Hibiscus. The
pool-anchored win rate measures distance from a frozen set of curated
references, which makes it an absolute, comparable-over-time quantity you
can gate on. Bradley-Terry measures *relative* strength within whatever
population you happened to compare — exactly the drift the pool anchor
exists to avoid.

So: use this to rank a batch against itself. Do not use it as an
acceptance threshold, and do not average it together with a pool-anchored
win rate. They are not the same kind of number.

The model, for a comparison judged by judge ``k``:

    P(i beats j) = sigmoid(strength_i - strength_j + judge_effect_k)

``judge_effect_k`` shifts outcomes toward the item in the *candidate*
role. Because every record designates a candidate and an opponent, this
term is identified rather than cancelling, and it lets a harsh judge and
a lenient one be placed on one scale — which matters as soon as more
than one judge model is in play.

Fitted by gradient ascent on the penalized log-likelihood. Strengths are
mean-centered each iteration for identifiability (only differences are
meaningful), and an L2 penalty keeps undefeated items from running off to
infinity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .artifact import Artifact
from .cache import JudgeCache
from .compare import ComparisonRecord, run_comparisons
from .judge.base import JudgeAdapter
from .pairs import PairOutcome, resolve_pairs
from .pool import Pool, RatedArtifact
from .tiers import Tier

DEFAULT_ITERATIONS = 20000
DEFAULT_LEARNING_RATE = 1.0
DEFAULT_L2 = 1e-4


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


@dataclass(frozen=True)
class BradleyTerryResult:
    """Fitted strengths, plus per-judge offsets."""

    strengths: dict[str, float]
    judge_effects: dict[str, float]
    n_comparisons: int
    n_items: int
    iterations: int
    converged: bool

    def ranking(self) -> list[tuple[str, float]]:
        """Items from strongest to weakest."""
        return sorted(self.strengths.items(), key=lambda kv: kv[1], reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strengths": self.strengths,
            "judge_effects": self.judge_effects,
            "n_comparisons": self.n_comparisons,
            "n_items": self.n_items,
            "iterations": self.iterations,
            "converged": self.converged,
        }


def fit_bradley_terry(
    outcomes: Iterable[PairOutcome],
    *,
    iterations: int = DEFAULT_ITERATIONS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
    tolerance: float = 1e-7,
) -> BradleyTerryResult:
    """Fit strengths (and per-judge offsets) to resolved pair outcomes.

    Ties are excluded, consistent with win-rate scoring: a tie carries no
    information about which item is stronger. Each outcome's ``model``
    names the judge that produced it; with a single judge the effect is
    zero by construction and only the strengths are informative.
    """
    observations: list[tuple[str, str, float, str]] = []
    for pair in outcomes:
        if pair.outcome == "tie":
            continue
        observations.append(
            (
                pair.candidate_id,
                pair.reference_id,
                1.0 if pair.outcome == "win" else 0.0,
                pair.model or "default",
            )
        )

    items = sorted({i for obs in observations for i in (obs[0], obs[1])})
    judge_ids = sorted({obs[3] for obs in observations})
    if not observations:
        return BradleyTerryResult({}, {}, 0, 0, 0, True)

    strengths = {item: 0.0 for item in items}
    effects = {judge: 0.0 for judge in judge_ids}

    converged = False
    used = 0
    for step in range(iterations):
        used = step + 1
        grad_s = {item: 0.0 for item in items}
        grad_e = {judge: 0.0 for judge in judge_ids}

        for winner_side, loser_side, y, judge in observations:
            z = strengths[winner_side] - strengths[loser_side] + effects[judge]
            residual = y - _sigmoid(z)
            grad_s[winner_side] += residual
            grad_s[loser_side] -= residual
            grad_e[judge] += residual

        # Average the gradient so the step size does not scale with the
        # number of observations; otherwise a large batch diverges.
        scale = 1.0 / len(observations)
        for item in items:
            grad_s[item] = grad_s[item] * scale - l2 * strengths[item]
        for judge in judge_ids:
            grad_e[judge] = grad_e[judge] * scale - l2 * effects[judge]

        max_move = 0.0
        for item in items:
            move = learning_rate * grad_s[item]
            strengths[item] += move
            max_move = max(max_move, abs(move))
        for judge in judge_ids:
            move = learning_rate * grad_e[judge]
            effects[judge] += move
            max_move = max(max_move, abs(move))

        # Only differences in strength are identified.
        offset = sum(strengths.values()) / len(strengths)
        for item in items:
            strengths[item] -= offset

        if max_move < tolerance:
            converged = True
            break

    return BradleyTerryResult(
        strengths=strengths,
        judge_effects=effects,
        n_comparisons=len(observations),
        n_items=len(items),
        iterations=used,
        converged=converged,
    )


def run_round_robin(
    candidates: Sequence[Artifact],
    judge: JudgeAdapter,
    *,
    question: "str | None" = None,
    model: str = "unknown",
    cache: "JudgeCache | None" = None,
    now=None,
) -> list[ComparisonRecord]:
    """Compare every candidate against every other, both orders.

    Reuses :func:`hibiscus.compare.run_comparisons` against an in-memory
    pool of the candidates themselves, narrowing the reference set to one
    opponent per call, so position control, caching, and logging behave
    exactly as they do everywhere else.
    """
    if len(candidates) < 2:
        raise ValueError("need at least two candidates to rank them against each other")

    pool = _candidate_pool(candidates)
    all_ids = {c.id for c in candidates}

    records: list[ComparisonRecord] = []
    for i, candidate in enumerate(candidates):
        for opponent in candidates[i + 1 :]:
            records.extend(
                run_comparisons(
                    candidate,
                    pool,
                    judge,
                    tier=Tier.LOVE,
                    k=1,
                    seed=0,
                    question=question,
                    model=model,
                    cache=cache,
                    exclude_ids=all_ids - {opponent.id},
                    now=now,
                )
            )
    return records


def _candidate_pool(candidates: Sequence[Artifact]) -> Pool:
    """An in-memory Pool of the candidates, used only as an opponent set.

    The tier is meaningless here — no tier label ever reaches the judge —
    it is just the selector ``run_comparisons`` samples from.
    """
    return Pool.in_memory(
        RatedArtifact(id=c.id, text=c.text, tier=Tier.LOVE, metadata=c.metadata)
        for c in candidates
    )


def rank_candidates(
    candidates: Sequence[Artifact],
    judge: JudgeAdapter,
    *,
    question: "str | None" = None,
    model: str = "unknown",
    cache: "JudgeCache | None" = None,
    iterations: int = DEFAULT_ITERATIONS,
    now=None,
) -> tuple[BradleyTerryResult, list[ComparisonRecord]]:
    """Round-robin the candidates and fit Bradley-Terry to the result."""
    records = run_round_robin(
        candidates, judge, question=question, model=model, cache=cache, now=now
    )
    outcomes = resolve_pairs(records)
    return fit_bradley_terry(outcomes, iterations=iterations), records
