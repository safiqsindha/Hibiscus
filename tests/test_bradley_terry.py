from __future__ import annotations

import math
import random

import pytest

from hibiscus import Artifact
from hibiscus.bradley_terry import fit_bradley_terry, rank_candidates, run_round_robin
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict
from hibiscus.pairs import PairOutcome


def _pair(candidate, reference, outcome, model=None):
    return PairOutcome(
        candidate_id=candidate,
        reference_id=reference,
        dimension="overall",
        outcome=outcome,
        model=model,
    )


def _synthetic_outcomes(strengths, *, seed=1, rounds=400, judge_effect=0.0, judge="j"):
    """Sample comparisons from a known Bradley-Terry model."""
    rng = random.Random(seed)
    items = sorted(strengths)
    outcomes = []
    for _ in range(rounds):
        a, b = rng.sample(items, 2)
        p = 1 / (1 + math.exp(-(strengths[a] - strengths[b] + judge_effect)))
        outcomes.append(_pair(a, b, "win" if rng.random() < p else "loss", model=judge))
    return outcomes


def test_recovers_known_strengths_ordering():
    truth = {"strong": 1.5, "middle": 0.0, "weak": -1.5}
    outcomes = _synthetic_outcomes(truth, seed=7, rounds=1500)

    result = fit_bradley_terry(outcomes)

    recovered = [item for item, _ in result.ranking()]
    assert recovered == ["strong", "middle", "weak"]


def test_recovers_known_strength_values_approximately():
    truth = {"a": 2.0, "b": 0.0, "c": -2.0}
    outcomes = _synthetic_outcomes(truth, seed=11, rounds=3000)

    result = fit_bradley_terry(outcomes)

    # Strengths are identified only up to a shift; center the truth too.
    offset = sum(truth.values()) / len(truth)
    for item, expected in truth.items():
        assert result.strengths[item] == pytest.approx(expected - offset, abs=0.4)


def test_judge_effect_recovers_a_known_harshness_offset():
    truth = {"a": 0.5, "b": -0.5}
    lenient = _synthetic_outcomes(
        truth, seed=3, rounds=1200, judge_effect=1.5, judge="lenient"
    )
    harsh = _synthetic_outcomes(
        truth, seed=4, rounds=1200, judge_effect=-1.5, judge="harsh"
    )

    result = fit_bradley_terry(lenient + harsh)

    assert result.judge_effects["lenient"] > result.judge_effects["harsh"]
    assert result.judge_effects["lenient"] > 0.5
    assert result.judge_effects["harsh"] < -0.5


def test_ties_are_excluded_from_the_fit():
    outcomes = [_pair("a", "b", "win"), _pair("a", "c", "tie")]

    result = fit_bradley_terry(outcomes)

    assert result.n_comparisons == 1
    assert "c" not in result.strengths


def test_no_decisive_comparisons_returns_empty_not_a_crash():
    result = fit_bradley_terry([_pair("a", "b", "tie")])

    assert result.n_comparisons == 0
    assert result.strengths == {}
    assert result.converged


def test_strengths_are_mean_centered():
    truth = {"a": 1.0, "b": 0.0, "c": -1.0}
    outcomes = _synthetic_outcomes(truth, seed=5, rounds=600)

    result = fit_bradley_terry(outcomes)

    assert sum(result.strengths.values()) == pytest.approx(0.0, abs=1e-6)


class LongerWinsJudge(JudgeAdapter):
    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if len(text_a) > len(text_b) else "b", raw_response="len")


def test_round_robin_covers_every_unordered_pair_in_both_orders():
    candidates = [Artifact(id=f"c{i}", text="z" * (10 + i * 10)) for i in range(4)]

    records = run_round_robin(candidates, LongerWinsJudge(), model="test")

    # 4 choose 2 == 6 pairs, each judged in both orders.
    assert len(records) == 12
    seen = {(r.candidate_id, r.reference_id) for r in records}
    assert len(seen) == 6
    for record in records:
        assert record.candidate_id != record.reference_id


def test_rank_candidates_orders_by_the_judges_preference():
    candidates = [Artifact(id=f"c{i}", text="z" * (10 + i * 40)) for i in range(4)]

    result, records = rank_candidates(candidates, LongerWinsJudge(), model="test")

    assert [item for item, _ in result.ranking()] == ["c3", "c2", "c1", "c0"]
    assert records


def test_rank_needs_at_least_two_candidates():
    with pytest.raises(ValueError, match="at least two"):
        run_round_robin([Artifact(id="only", text="x")], LongerWinsJudge())
