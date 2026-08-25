from __future__ import annotations

import pytest

from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict
from hibiscus.saturate import kendall_tau, plan_sizes, run_saturation


class LongerWinsJudge(JudgeAdapter):
    """Cleanly separates candidates by length — a stable, learnable signal."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if len(text_a) > len(text_b) else "b", raw_response="len")


def _pool(tmp_path, n=20):
    pool = Pool(tmp_path / "pool.jsonl")
    for i in range(n):
        pool.add(RatedArtifact(id=f"r{i:02d}", text="y" * (50 + i * 3), tier=Tier.LOVE))
    return pool


def _candidates():
    # Well separated: one clearly short, one mid, one clearly long.
    return [
        Artifact(id="short", text="z" * 10),
        Artifact(id="mid", text="z" * 80),
        Artifact(id="long", text="z" * 200),
    ]


def test_kendall_tau_perfect_agreement():
    assert kendall_tau([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_kendall_tau_perfect_inversion():
    assert kendall_tau([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_kendall_tau_needs_two_points():
    assert kendall_tau([1], [1]) is None


def test_kendall_tau_all_tied_is_undefined_not_a_crash():
    assert kendall_tau([1, 1, 1], [2, 2, 2]) is None


def test_plan_sizes_always_ends_at_the_full_pool():
    assert plan_sizes(20, step=5) == [5, 10, 15, 20]
    assert plan_sizes(17, step=5) == [5, 10, 15, 17]
    assert plan_sizes(3, step=5) == [3]


def test_rankings_stabilize_on_a_cleanly_separated_set(tmp_path):
    report = run_saturation(
        _pool(tmp_path), _candidates(), LongerWinsJudge(), seed=1, step=5, repeats=2, model="test"
    )

    assert report.ordering_saturated_at is not None
    # The judge is deterministic on well-separated candidates, so the
    # ordering never moves once there is anything to compare against.
    final = report.steps[-1].mean_win_rates
    assert final["long"] > final["mid"] > final["short"]


def test_same_seed_reproduces_the_run(tmp_path):
    kwargs = dict(seed=3, step=5, repeats=2, model="test")
    pool = _pool(tmp_path)
    a = run_saturation(pool, _candidates(), LongerWinsJudge(), **kwargs)
    b = run_saturation(pool, _candidates(), LongerWinsJudge(), **kwargs)

    assert [s.to_dict() for s in a.steps] == [s.to_dict() for s in b.steps]
    assert a.rate_saturated_at == b.rate_saturated_at
    assert a.ordering_saturated_at == b.ordering_saturated_at


def test_different_seeds_draw_different_subsets(tmp_path):
    pool = _pool(tmp_path)
    a = run_saturation(pool, _candidates(), LongerWinsJudge(), seed=1, step=5, repeats=1,
                       sizes=[5], model="test")
    b = run_saturation(pool, _candidates(), LongerWinsJudge(), seed=999, step=5, repeats=1,
                       sizes=[5], model="test")

    # Same deterministic judge, but different reference draws, so the
    # mid candidate's win rate should be able to move.
    assert a.steps[0].mean_win_rates != b.steps[0].mean_win_rates


def test_explicit_sizes_are_respected(tmp_path):
    report = run_saturation(
        _pool(tmp_path), _candidates(), LongerWinsJudge(), seed=1, repeats=1,
        sizes=[4, 8, 12], model="test",
    )
    assert [s.size for s in report.steps] == [4, 8, 12]


def test_tiny_pool_raises_rather_than_reporting_nonsense(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="only", text="x", tier=Tier.LOVE))

    with pytest.raises(ValueError, match="at least 2"):
        run_saturation(pool, _candidates(), LongerWinsJudge(), seed=1, model="test")


def test_no_candidates_raises(tmp_path):
    with pytest.raises(ValueError, match="at least one candidate"):
        run_saturation(_pool(tmp_path), [], LongerWinsJudge(), seed=1, model="test")


def test_cache_makes_a_repeat_run_free(tmp_path):
    from hibiscus.cache import JudgeCache

    class CountingJudge(LongerWinsJudge):
        def __init__(self):
            self.calls = 0

        def compare(self, text_a, text_b, question):
            self.calls += 1
            return super().compare(text_a, text_b, question)

    cache_path = tmp_path / "cache.jsonl"
    pool = _pool(tmp_path, n=10)

    first = CountingJudge()
    run_saturation(pool, _candidates(), first, seed=1, step=5, repeats=1, model="test",
                   cache=JudgeCache(cache_path))
    assert first.calls > 0

    second = CountingJudge()
    run_saturation(pool, _candidates(), second, seed=1, step=5, repeats=1, model="test",
                   cache=JudgeCache(cache_path))
    assert second.calls == 0
