"""Resolve order-counterbalanced comparisons into one outcome per pair.

``compare`` judges every candidate-reference pair twice, once in each
order. Those two calls are two *measurements of one comparison*, not two
comparisons. Treating them as independent Bernoulli trials inflates the
denominator twofold — making every confidence interval far narrower than
the evidence supports — and, worse, records an order-dependent verdict as
one win plus one loss, dragging the candidate toward an exact coin flip.
That is score compression manufactured by the scoring layer, which is
precisely the failure this library exists to detect.

So each pair resolves to a single outcome first:

===========================  ==========================  ========
candidate-first says         reference-first says        outcome
===========================  ==========================  ========
candidate                    candidate                   WIN
reference                    reference                   LOSS
anything else (incl. ties)   ...                         TIE
===========================  ==========================  ========

Ties are then excluded from the win-rate denominator — symmetrically, so
they bias nothing — and reported separately as a rate. A tie arising from
the judge saying so and a tie arising from the judge contradicting itself
under position swap are recorded distinctly, because they mean different
things: the first is "these are equivalent", the second is "this judge
cannot tell".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Literal

from .compare import SCHEMA_VERSION, ComparisonRecord

Outcome = Literal["win", "loss", "tie"]
TieReason = Literal["judge", "order_disagreement"]


@dataclass(frozen=True)
class PairOutcome:
    """One candidate-reference pair, resolved across both orders."""

    candidate_id: str
    reference_id: str
    dimension: str
    outcome: Outcome
    tie_reason: "TieReason | None" = None
    counterbalanced: bool = True
    candidate_length: "int | None" = None
    model: "str | None" = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "reference_id": self.reference_id,
            "dimension": self.dimension,
            "outcome": self.outcome,
            "tie_reason": self.tie_reason,
            "counterbalanced": self.counterbalanced,
            "candidate_length": self.candidate_length,
            "model": self.model,
        }


@dataclass(frozen=True)
class PairSummary:
    """Counts over a set of resolved pairs."""

    wins: int
    losses: int
    ties: int
    judge_ties: int
    disagreement_ties: int
    uncounterbalanced: int
    legacy_records: int

    @property
    def decisive(self) -> int:
        """Pairs that count toward the win rate."""
        return self.wins + self.losses

    @property
    def total(self) -> int:
        return self.decisive + self.ties

    @property
    def tie_rate(self) -> float:
        """Share of resolved pairs that produced no usable verdict."""
        return self.ties / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "judge_ties": self.judge_ties,
            "disagreement_ties": self.disagreement_ties,
            "decisive": self.decisive,
            "tie_rate": self.tie_rate,
            "uncounterbalanced": self.uncounterbalanced,
            "legacy_records": self.legacy_records,
        }


def resolve_pairs(records: Iterable[ComparisonRecord]) -> list[PairOutcome]:
    """Collapse both orders of each pair into one outcome.

    Records are grouped by (candidate, reference, dimension). A pair
    missing one of its two orders cannot be counterbalanced; it is still
    resolved, from the single verdict available, but flagged so the
    caller can report how much of the data lacked position control.
    """
    # Keyed by model too: the same pair judged by two different models is
    # two observations, not one, and collapsing them would silently drop
    # data and make per-judge effects unidentifiable.
    grouped: dict[tuple[str, str, str, str], list[ComparisonRecord]] = defaultdict(list)
    for record in records:
        grouped[
            (record.candidate_id, record.reference_id, record.dimension, record.model)
        ].append(record)

    outcomes: list[PairOutcome] = []
    for (candidate_id, reference_id, dimension, model), group in grouped.items():
        verdicts = {r.order: r.winner for r in group}
        lengths = [r.candidate_length for r in group if r.candidate_length is not None]
        candidate_length = lengths[0] if lengths else None
        counterbalanced = len(verdicts) >= 2

        winners = list(verdicts.values())
        if any(w == "tie" for w in winners):
            outcome: Outcome = "tie"
            tie_reason: "TieReason | None" = "judge"
        elif all(w == "candidate" for w in winners):
            outcome, tie_reason = "win", None
        elif all(w == "reference" for w in winners):
            outcome, tie_reason = "loss", None
        else:
            outcome, tie_reason = "tie", "order_disagreement"

        outcomes.append(
            PairOutcome(
                candidate_id=candidate_id,
                reference_id=reference_id,
                dimension=dimension,
                outcome=outcome,
                tie_reason=tie_reason,
                counterbalanced=counterbalanced,
                candidate_length=candidate_length,
                model=model,
            )
        )

    outcomes.sort(key=lambda p: (p.candidate_id, p.dimension, p.reference_id, p.model or ""))
    return outcomes


def summarize_pairs(
    outcomes: Iterable[PairOutcome], *, legacy_records: int = 0
) -> PairSummary:
    """Count wins, losses, and the two kinds of tie."""
    wins = losses = ties = judge_ties = disagreement_ties = uncounterbalanced = 0
    for pair in outcomes:
        if not pair.counterbalanced:
            uncounterbalanced += 1
        if pair.outcome == "win":
            wins += 1
        elif pair.outcome == "loss":
            losses += 1
        else:
            ties += 1
            if pair.tie_reason == "judge":
                judge_ties += 1
            else:
                disagreement_ties += 1

    return PairSummary(
        wins=wins,
        losses=losses,
        ties=ties,
        judge_ties=judge_ties,
        disagreement_ties=disagreement_ties,
        uncounterbalanced=uncounterbalanced,
        legacy_records=legacy_records,
    )


def count_legacy_records(records: Iterable[ComparisonRecord]) -> int:
    """How many records predate the current record schema."""
    return sum(1 for r in records if r.schema_version < SCHEMA_VERSION)
