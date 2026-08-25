from __future__ import annotations

from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.compare import load_comparisons, order_disagreement_rate, run_comparisons, save_comparisons
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict


class AlwaysAJudge(JudgeAdapter):
    """Always prefers whichever text is passed as text_a — pure position bias."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a", raw_response="mock:a")


class ContentAwareJudge(JudgeAdapter):
    """Prefers the longer text regardless of position — no position bias."""

    def compare(self, text_a, text_b, question):
        winner = "a" if len(text_a) >= len(text_b) else "b"
        return JudgeVerdict(winner=winner, raw_response=f"mock:{winner}")


def _pool(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="r1", text="reference one", tier=Tier.LOVE))
    pool.add(RatedArtifact(id="r2", text="reference two", tier=Tier.LOVE))
    return pool


def test_every_comparison_runs_in_both_orders(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="a candidate worth judging")

    records = run_comparisons(candidate, pool, AlwaysAJudge(), k=2, seed=1, model="test")

    assert len(records) == 4  # 2 references x 2 orders
    orders = {(r.reference_id, r.order) for r in records}
    for ref_id in ("r1", "r2"):
        assert (ref_id, "candidate_first") in orders
        assert (ref_id, "reference_first") in orders


def test_position_biased_judge_shows_full_disagreement(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="a candidate worth judging")

    records = run_comparisons(candidate, pool, AlwaysAJudge(), k=2, seed=1, model="test")

    assert order_disagreement_rate(records) == 1.0


def test_content_aware_judge_shows_no_disagreement(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="a candidate worth judging, and a rather long one")

    records = run_comparisons(candidate, pool, ContentAwareJudge(), k=2, seed=1, model="test")

    assert order_disagreement_rate(records) == 0.0


def test_disagreement_rate_on_empty_records_is_zero():
    assert order_disagreement_rate([]) == 0.0


def test_save_and_load_comparisons_round_trip(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="a candidate worth judging")
    records = run_comparisons(candidate, pool, AlwaysAJudge(), k=2, seed=1, model="test")

    out = tmp_path / "comparisons.jsonl"
    save_comparisons(out, records)
    reloaded = load_comparisons(out)

    assert [r.to_dict() for r in reloaded] == [r.to_dict() for r in records]


def test_save_append_accumulates_across_calls(tmp_path):
    pool = _pool(tmp_path)
    out = tmp_path / "comparisons.jsonl"

    r1 = run_comparisons(Artifact(id="c1", text="one"), pool, AlwaysAJudge(), k=2, seed=1, model="test")
    save_comparisons(out, r1, append=True)
    r2 = run_comparisons(Artifact(id="c2", text="two"), pool, AlwaysAJudge(), k=2, seed=1, model="test")
    save_comparisons(out, r2, append=True)

    assert len(load_comparisons(out)) == len(r1) + len(r2)
