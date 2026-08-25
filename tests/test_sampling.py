from __future__ import annotations

import pytest

from hibiscus import Pool, RatedArtifact, Tier
from hibiscus.compare import sample_references


def _pool_with(tmp_path, n, *, tier=Tier.LOVE):
    pool = Pool(tmp_path / "pool.jsonl")
    for i in range(n):
        pool.add(RatedArtifact(id=f"r{i}", text=f"reference {i}", tier=tier))
    return pool


def test_same_seed_gives_identical_sample(tmp_path):
    pool = _pool_with(tmp_path, 10)
    a = sample_references(pool, tier=Tier.LOVE, k=3, seed=42)
    b = sample_references(pool, tier=Tier.LOVE, k=3, seed=42)
    assert [x.id for x in a] == [x.id for x in b]


def test_different_seeds_can_give_different_samples(tmp_path):
    pool = _pool_with(tmp_path, 20)
    a = sample_references(pool, tier=Tier.LOVE, k=3, seed=1)
    b = sample_references(pool, tier=Tier.LOVE, k=3, seed=2)
    assert [x.id for x in a] != [x.id for x in b]


def test_sampling_ignores_other_tiers(tmp_path):
    pool = _pool_with(tmp_path, 5, tier=Tier.LOVE)
    pool.add(RatedArtifact(id="okay-0", text="not a love ref", tier=Tier.OKAY))
    sampled = sample_references(pool, tier=Tier.LOVE, k=5, seed=1)
    assert all(a.id.startswith("r") for a in sampled)


def test_not_enough_in_tier_raises(tmp_path):
    pool = _pool_with(tmp_path, 1)
    with pytest.raises(ValueError):
        sample_references(pool, tier=Tier.LOVE, k=2, seed=1)
