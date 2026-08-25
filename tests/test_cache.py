from __future__ import annotations

from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.cache import JudgeCache
from hibiscus.compare import run_comparisons
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict


class CountingJudge(JudgeAdapter):
    def __init__(self):
        self.calls = 0

    def compare(self, text_a, text_b, question):
        self.calls += 1
        return JudgeVerdict(winner="a", raw_response="mock:a")


def _pool(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="r1", text="reference one", tier=Tier.LOVE))
    pool.add(RatedArtifact(id="r2", text="reference two", tier=Tier.LOVE))
    return pool


def test_cache_hit_avoids_a_second_judge_call(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="candidate text")
    cache_path = tmp_path / "cache.jsonl"

    judge1 = CountingJudge()
    run_comparisons(candidate, pool, judge1, k=2, seed=1, model="test", cache=JudgeCache(cache_path))
    assert judge1.calls == 4

    judge2 = CountingJudge()
    run_comparisons(candidate, pool, judge2, k=2, seed=1, model="test", cache=JudgeCache(cache_path))
    assert judge2.calls == 0


def test_cache_is_scoped_by_model(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="candidate text")
    cache = JudgeCache(tmp_path / "cache.jsonl")

    judge_a = CountingJudge()
    run_comparisons(candidate, pool, judge_a, k=2, seed=1, model="model-a", cache=cache)

    judge_b = CountingJudge()
    run_comparisons(candidate, pool, judge_b, k=2, seed=1, model="model-b", cache=cache)

    assert judge_b.calls == 4  # different model => cache miss


def test_cache_records_hits_and_misses(tmp_path):
    pool = _pool(tmp_path)
    candidate = Artifact(id="c1", text="candidate text")
    cache = JudgeCache(tmp_path / "cache.jsonl")

    run_comparisons(candidate, pool, CountingJudge(), k=2, seed=1, model="test", cache=cache)
    assert cache.misses == 4
    assert cache.hits == 0

    run_comparisons(candidate, pool, CountingJudge(), k=2, seed=1, model="test", cache=cache)
    assert cache.hits == 4
