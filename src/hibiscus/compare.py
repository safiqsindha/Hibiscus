"""Sample references, run position-controlled pairwise comparisons, log them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Collection, Literal

from .artifact import Artifact
from .cache import CacheKey, JudgeCache
from .hashing import sha256_hex
from .judge.base import JudgeAdapter
from .judge.payload import DEFAULT_QUESTION, build_judge_payload
from .pool import Pool
from .rng import sample_deterministic
from .tiers import Tier, parse_tier

Order = Literal["candidate_first", "reference_first"]
Winner = Literal["candidate", "reference"]


@dataclass(frozen=True)
class ComparisonRecord:
    """One logged judge call: who was compared, in what order, who won."""

    candidate_id: str
    reference_id: str
    order: Order
    winner: Winner
    raw_response: str
    model: str
    prompt_hash: str
    timestamp: str
    cache_hit: bool
    dimension: str = "overall"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "reference_id": self.reference_id,
            "order": self.order,
            "winner": self.winner,
            "raw_response": self.raw_response,
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "timestamp": self.timestamp,
            "cache_hit": self.cache_hit,
            "dimension": self.dimension,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComparisonRecord":
        return cls(**data)


def sample_references(
    pool: Pool,
    *,
    tier: "Tier | str" = Tier.LOVE,
    k: int = 2,
    seed: int,
    exclude_ids: "Collection[str] | None" = None,
) -> list[Artifact]:
    """Deterministically sample ``k`` references from ``tier`` of ``pool``.

    ``exclude_ids`` drops artifacts from the population before sampling —
    used during calibration so a pool member scored as a candidate is
    never compared against itself.
    """
    tier = parse_tier(tier)
    candidates = pool.filter_by_tier(tier)
    if exclude_ids:
        excluded = set(exclude_ids)
        candidates = [r for r in candidates if r.id not in excluded]
    if len(candidates) < k:
        raise ValueError(
            f"pool has only {len(candidates)} eligible artifacts in tier {tier.value!r}; "
            f"need at least {k}"
        )
    sampled = sample_deterministic(candidates, k, seed, key=lambda r: r.id)
    return [r.artifact for r in sampled]


def run_comparisons(
    candidate: Artifact,
    pool: Pool,
    judge: JudgeAdapter,
    *,
    tier: "Tier | str" = Tier.LOVE,
    k: int = 2,
    seed: int = 0,
    question: "str | None" = None,
    model: str = "unknown",
    cache: "JudgeCache | None" = None,
    dimension: str = "overall",
    exclude_ids: "Collection[str] | None" = None,
    now: "Callable[[], str] | None" = None,
) -> list[ComparisonRecord]:
    """Compare ``candidate`` against ``k`` references sampled from ``tier``.

    Every (candidate, reference) pair is judged in both orders —
    candidate-first and reference-first — to control for position bias.
    Results are looked up in ``cache`` first when provided.

    ``exclude_ids`` is forwarded to reference sampling; pass the
    candidate's own id when scoring an artifact that lives in the pool.
    """
    question = question or DEFAULT_QUESTION
    prompt_hash = sha256_hex(question)
    candidate_hash = sha256_hex(candidate.text)
    references = sample_references(pool, tier=tier, k=k, seed=seed, exclude_ids=exclude_ids)
    stamp = now or (lambda: datetime.now(timezone.utc).isoformat())

    records: list[ComparisonRecord] = []
    for reference in references:
        reference_hash = sha256_hex(reference.text)
        for order in ("candidate_first", "reference_first"):
            if order == "candidate_first":
                text_a, text_b = candidate.text, reference.text
            else:
                text_a, text_b = reference.text, candidate.text
            payload = build_judge_payload(text_a, text_b, question)

            cache_key = CacheKey(candidate_hash, reference_hash, order, prompt_hash, model)
            verdict = cache.get(cache_key) if cache else None
            cache_hit = verdict is not None
            if verdict is None:
                verdict = judge.compare(payload["text_a"], payload["text_b"], payload["question"])
                if cache is not None:
                    cache.put(cache_key, verdict)

            if order == "candidate_first":
                winner: Winner = "candidate" if verdict.winner == "a" else "reference"
            else:
                winner = "reference" if verdict.winner == "a" else "candidate"

            records.append(
                ComparisonRecord(
                    candidate_id=candidate.id,
                    reference_id=reference.id,
                    order=order,
                    winner=winner,
                    raw_response=verdict.raw_response,
                    model=model,
                    prompt_hash=prompt_hash,
                    timestamp=stamp(),
                    cache_hit=cache_hit,
                    dimension=dimension,
                )
            )
    return records


def order_disagreement_rate(records: list[ComparisonRecord]) -> float:
    """Fraction of (candidate, reference) pairs whose two order-swapped
    runs disagree on the winner.

    High disagreement means the judge is tracking which position a text
    appeared in rather than its content — a judge-reliability red flag.
    """
    pairs: dict[tuple[str, str], dict[str, str]] = {}
    for r in records:
        pairs.setdefault((r.candidate_id, r.reference_id), {})[r.order] = r.winner

    complete = [v for v in pairs.values() if "candidate_first" in v and "reference_first" in v]
    if not complete:
        return 0.0
    disagreements = sum(1 for v in complete if v["candidate_first"] != v["reference_first"])
    return disagreements / len(complete)


def save_comparisons(
    path: "str | Path", records: list[ComparisonRecord], *, append: bool = False
) -> None:
    """Write comparison records to a UTF-8 JSONL file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with out.open(mode, encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


def load_comparisons(path: "str | Path") -> list[ComparisonRecord]:
    """Read comparison records back from a UTF-8 JSONL file."""
    records = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(ComparisonRecord.from_dict(json.loads(line)))
    return records
