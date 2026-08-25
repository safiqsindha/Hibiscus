"""End-to-end walkthrough of Hibiscus, entirely offline (no network calls).

Builds a small love-tier reference pool, compares two candidates against
it with the deterministic MockJudge, scores them with Wilson intervals,
and runs the correlation diagnostic on a synthetic rubric with a
deliberately duplicated dimension.

Run with:
    pip install -e .
    python examples/worked_example.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hibiscus import Artifact, JudgeCache, Pool, RatedArtifact, Tier
from hibiscus.compare import order_disagreement_rate, run_comparisons
from hibiscus.judge.mock import MockJudge
from hibiscus.report import ScoreRow, build_correlation_report
from hibiscus.score import score_candidate

LOVE_POOL = [
    "The kettle sings before the sun clears the ridge.",
    "She left the porch light on for a guest who never came.",
    "Snow collects in the mailbox no one checks anymore.",
    "A single crow negotiates the length of the wire.",
    "The tide takes the footprints before we're done arguing.",
]

CANDIDATES = {
    "strong": "The lighthouse keeper counts ships instead of sheep.",
    "weak": "Thing happened and it was a thing that happened, yes.",
}


def build_pool(pool_path: Path) -> Pool:
    pool = Pool(pool_path)
    for i, text in enumerate(LOVE_POOL):
        pool.add(RatedArtifact(id=f"love-{i}", text=text, tier=Tier.LOVE))
    pool.add(RatedArtifact(id="okay-0", text="It rained. The bus was late again.", tier=Tier.OKAY))
    pool.add(RatedArtifact(id="nope-0", text="asdkj alksdj laksjd laksjdl", tier=Tier.NOPE))
    return pool


def run_compare_and_score(pool: Pool, cache_path: Path) -> None:
    judge = MockJudge()
    cache = JudgeCache(cache_path)

    for name, text in CANDIDATES.items():
        candidate = Artifact(id=name, text=text)
        records = run_comparisons(candidate, pool, judge, k=2, seed=7, model="mock-v1", cache=cache)
        result = score_candidate(records, candidate_id=name)
        disagreement = order_disagreement_rate(records)
        print(
            f"{name:>7}: win rate {result.point_estimate:.0%} "
            f"[{result.lower:.0%}, {result.upper:.0%}] over {result.n} comparisons, "
            f"order-disagreement {disagreement:.0%}"
        )


def run_correlation_diagnostic() -> None:
    scores = {"art-1": 0.9, "art-2": 0.3, "art-3": 0.6, "art-4": 0.8, "art-5": 0.1}
    rows = []
    for artifact_id, score in scores.items():
        rows.append(ScoreRow(artifact_id, "originality", score))
        rows.append(ScoreRow(artifact_id, "novelty", score))  # same signal, different name
        rows.append(ScoreRow(artifact_id, "technical_execution", 1.0 - score))

    report = build_correlation_report(rows, threshold=0.85)

    print("\ncorrelation matrix:")
    for dim_a in report.dimensions:
        row = ", ".join(f"{dim_b}={report.matrix[dim_a][dim_b]:.2f}" for dim_b in report.dimensions)
        print(f"  {dim_a:>20}: {row}")

    print("\nflagged as redundant:")
    for a, b, corr in report.redundant_pairs:
        print(f"  {a} <-> {b}: {corr:.2f}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        print("== building the love-tier reference pool ==")
        pool = build_pool(tmp_path / "pool.jsonl")
        print(f"pool has {len(pool.filter_by_tier(Tier.LOVE))} love-tier references\n")

        print("== comparing two candidates against the pool ==")
        run_compare_and_score(pool, tmp_path / "cache.jsonl")

        print("\n== running the correlation diagnostic on synthetic dimension scores ==")
        run_correlation_diagnostic()


if __name__ == "__main__":
    main()
