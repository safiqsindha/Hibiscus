from __future__ import annotations

from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.compare import ComparisonRecord, run_comparisons
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict
from hibiscus.score import length_bias


class LongerWinsJudge(JudgeAdapter):
    """The canonical length-biased judge: longer text always wins."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if len(text_a) > len(text_b) else "b", raw_response="len")


class ContentJudge(JudgeAdapter):
    """Decides on a marker in the text, ignoring length entirely."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if "GOOD" in text_a else "b", raw_response="content")


def _pool(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    for i in range(3):
        pool.add(RatedArtifact(id=f"r{i}", text="reference " + "y" * (40 + i), tier=Tier.LOVE))
    return pool


def _score_candidates(pool, judge, candidates):
    records = []
    for candidate in candidates:
        records.extend(run_comparisons(candidate, pool, judge, k=3, seed=1, model="test"))
    return records


def test_length_biased_judge_drives_the_diagnostic_high(tmp_path):
    candidates = [Artifact(id=f"c{i}", text="z" * (5 + i * 40)) for i in range(5)]
    records = _score_candidates(_pool(tmp_path), LongerWinsJudge(), candidates)

    bias = length_bias(records)

    assert bias.correlation is not None
    assert bias.correlation > 0.8
    assert bias.flagged


def test_content_judge_does_not_trip_the_diagnostic(tmp_path):
    # Length varies, but the verdict tracks the marker instead.
    candidates = [
        Artifact(id="c0", text="GOOD " + "z" * 10),
        Artifact(id="c1", text="bad " + "z" * 200),
        Artifact(id="c2", text="GOOD " + "z" * 150),
        Artifact(id="c3", text="bad " + "z" * 30),
    ]
    records = _score_candidates(_pool(tmp_path), ContentJudge(), candidates)

    bias = length_bias(records)

    assert bias.correlation is not None
    assert not bias.flagged


def test_records_without_lengths_are_counted_as_missing():
    records = [
        ComparisonRecord("c0", "r0", order, "candidate", "x", "m", "p", "t", False)
        for order in ("candidate_first", "reference_first")
    ]
    bias = length_bias(records)

    assert bias.correlation is None
    assert bias.missing_lengths == 1


def test_explicit_lengths_override_missing_record_data():
    records = []
    for i, outcome in enumerate(["candidate", "candidate", "reference", "reference"]):
        for order in ("candidate_first", "reference_first"):
            records.append(
                ComparisonRecord(f"c{i}", "r0", order, outcome, "x", "m", "p", "t", False)
            )

    bias = length_bias(records, lengths={"c0": 400, "c1": 300, "c2": 20, "c3": 10})

    assert bias.correlation is not None
    assert bias.flagged


def test_single_candidate_yields_no_correlation():
    records = [
        ComparisonRecord("c0", "r0", order, "candidate", "x", "m", "p", "t", False,
                         candidate_length=10)
        for order in ("candidate_first", "reference_first")
    ]
    bias = length_bias(records)

    assert bias.correlation is None
    assert not bias.flagged
