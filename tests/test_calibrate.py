from __future__ import annotations

import pytest

from hibiscus import Pool, RatedArtifact, Tier
from hibiscus.calibrate import run_calibration
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict
from hibiscus.tiers import TIER_ORDER

# Longer text == better, so a pool whose love items are long and nope
# items short gives a judge that agrees with the tiers. Lengths vary
# *within* each tier too: equal-length items would make every same-tier
# comparison flip under position swap and resolve to a tie, leaving the
# tier with no signal at all.
TIER_BASE_LENGTH = {Tier.LOVE: 120, Tier.OKAY: 60, Tier.NOPE: 10}


def _text(tier: Tier, i: int) -> str:
    return f"{tier.value}-{i} " + "x" * (TIER_BASE_LENGTH[tier] + i * 7)


class LengthJudge(JudgeAdapter):
    """Agrees with the tiers: prefers the longer text, ignores position."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if len(text_a) >= len(text_b) else "b", raw_response="len")


class AlwaysReferenceJudge(JudgeAdapter):
    """Disagrees with everything: always picks whichever text came second."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="b", raw_response="always-b")


class InvertedJudge(JudgeAdapter):
    """Prefers the shorter text, so it ranks the tiers upside down."""

    def compare(self, text_a, text_b, question):
        return JudgeVerdict(winner="a" if len(text_a) <= len(text_b) else "b", raw_response="inv")


def _tiered_pool(tmp_path, *, per_tier=3):
    pool = Pool(tmp_path / "pool.jsonl")
    for tier in (Tier.LOVE, Tier.OKAY, Tier.NOPE):
        for i in range(per_tier):
            pool.add(RatedArtifact(id=f"{tier.value}-{i}", text=_text(tier, i), tier=tier))
    return pool


def test_aligned_judge_reproduces_the_tier_ordering(tmp_path):
    report = run_calibration(_tiered_pool(tmp_path), LengthJudge(), k=2, seed=1, model="test")

    assert report.ordering_holds
    assert report.inversions == []
    rates = [report.by_tier[t].win_rate.point_estimate for t in report.tiers_high_to_low]
    assert rates == sorted(rates, reverse=True)
    assert report.separation > 0


def test_judge_that_separates_nothing_fails_calibration(tmp_path):
    """Every tier scores identically, so the ordering carries no information."""
    report = run_calibration(
        _tiered_pool(tmp_path), AlwaysReferenceJudge(), k=2, seed=1, model="test"
    )

    assert not report.ordering_holds
    assert report.inversions == []
    assert report.separation == 0


def test_inverted_judge_is_reported_as_an_inversion(tmp_path):
    report = run_calibration(_tiered_pool(tmp_path), InvertedJudge(), k=2, seed=1, model="test")

    assert not report.ordering_holds
    assert report.inversions
    higher, lower = report.inversions[0]
    assert TIER_ORDER[higher] > TIER_ORDER[lower]


def test_tied_lower_tiers_are_tolerated(tmp_path):
    """okay and nope both flooring at zero against love foils is expected."""
    report = run_calibration(_tiered_pool(tmp_path), LengthJudge(), k=2, seed=1, model="test")

    okay = report.by_tier[Tier.OKAY].win_rate.point_estimate
    nope = report.by_tier[Tier.NOPE].win_rate.point_estimate
    assert okay == nope == 0.0
    assert report.ordering_holds


def test_pool_items_are_never_compared_against_themselves(tmp_path):
    report = run_calibration(_tiered_pool(tmp_path), LengthJudge(), k=2, seed=1, model="test")

    assert report.records
    for record in report.records:
        assert record.candidate_id != record.reference_id


def test_each_tier_is_recorded_with_its_own_dimension(tmp_path):
    report = run_calibration(_tiered_pool(tmp_path), LengthJudge(), k=2, seed=1, model="test")

    dimensions = {r.dimension for r in report.records}
    assert dimensions == {"calibration:love", "calibration:okay", "calibration:nope"}


def test_max_per_tier_caps_work_and_records_the_cap(tmp_path):
    pool = _tiered_pool(tmp_path, per_tier=5)
    report = run_calibration(pool, LengthJudge(), k=2, seed=1, model="test", max_per_tier=2)

    love = report.by_tier[Tier.LOVE]
    assert love.n_candidates == 2
    assert love.n_available == 5
    assert love.capped is True


def test_uncapped_run_is_not_marked_capped(tmp_path):
    report = run_calibration(
        _tiered_pool(tmp_path, per_tier=3), LengthJudge(), k=2, seed=1, model="test",
        max_per_tier=None,
    )
    assert all(not cal.capped for cal in report.by_tier.values())


def test_reference_tier_needs_room_to_exclude_the_candidate(tmp_path):
    """With k=2 and only 2 love items, scoring a love item leaves 1 reference."""
    pool = Pool(tmp_path / "pool.jsonl")
    for i in range(2):
        pool.add(RatedArtifact(id=f"love-{i}", text=f"reference {i}", tier=Tier.LOVE))

    with pytest.raises(ValueError, match="eligible"):
        run_calibration(pool, LengthJudge(), k=2, seed=1, model="test")


def test_missing_tiers_are_skipped_not_fatal(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    for i in range(3):
        pool.add(RatedArtifact(id=f"love-{i}", text=_text(Tier.LOVE, i), tier=Tier.LOVE))
        pool.add(RatedArtifact(id=f"nope-{i}", text=_text(Tier.NOPE, i), tier=Tier.NOPE))

    report = run_calibration(pool, LengthJudge(), k=2, seed=1, model="test")

    assert set(report.by_tier) == {Tier.LOVE, Tier.NOPE}
    assert report.ordering_holds


def test_report_serializes_to_dict(tmp_path):
    report = run_calibration(_tiered_pool(tmp_path), LengthJudge(), k=2, seed=1, model="test")
    data = report.to_dict()

    assert data["reference_tier"] == "love"
    assert data["ordering_holds"] is True
    assert set(data["tiers"]) == {"love", "okay", "nope"}
    assert data["tiers"]["love"]["n"] > 0
