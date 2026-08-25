from __future__ import annotations

import pytest

from hibiscus.compare import ComparisonRecord
from hibiscus.score import score_all, score_candidate, wilson_interval


def _pair(candidate_id, outcome, reference_id="r", dimension="overall"):
    """Both orders of one comparison, agreeing on ``outcome``.

    Scoring resolves a pair across its two orders, so a test that wants
    N trials needs N distinct reference ids, each with both orders.
    """
    return [
        ComparisonRecord(
            candidate_id=candidate_id,
            reference_id=reference_id,
            order=order,
            winner=outcome,
            raw_response="x",
            model="m",
            prompt_hash="p",
            timestamp="t",
            cache_hit=False,
            dimension=dimension,
        )
        for order in ("candidate_first", "reference_first")
    ]


def test_wilson_matches_hand_computed_values():
    # wins=8, n=10, z=1.96 -> hand-derived reference values.
    result = wilson_interval(8, 10, z=1.96)
    assert result.point_estimate == pytest.approx(0.8)
    assert result.lower == pytest.approx(0.4902, abs=0.001)
    assert result.upper == pytest.approx(0.9434, abs=0.001)


def test_wilson_degenerate_zero_wins():
    result = wilson_interval(0, 10)
    assert result.point_estimate == 0.0
    assert result.lower == pytest.approx(0.0, abs=1e-9)
    assert 0.0 < result.upper < 1.0


def test_wilson_degenerate_all_wins():
    result = wilson_interval(10, 10)
    assert result.point_estimate == 1.0
    assert result.upper == pytest.approx(1.0, abs=1e-9)
    assert 0.0 < result.lower < 1.0


def test_wilson_degenerate_single_trial():
    win = wilson_interval(1, 1)
    assert win.point_estimate == 1.0
    assert 0.0 <= win.lower <= win.upper <= 1.0

    loss = wilson_interval(0, 1)
    assert loss.point_estimate == 0.0
    assert 0.0 <= loss.lower <= loss.upper <= 1.0


def test_wilson_no_trials_does_not_crash():
    result = wilson_interval(0, 0)
    assert result.n == 0
    assert result.lower == 0.0
    assert result.upper == 1.0


def test_wilson_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(-1, 3)


def test_score_candidate_filters_by_candidate_and_dimension():
    records = (
        _pair("c1", "candidate", reference_id="r1")
        + _pair("c1", "reference", reference_id="r2")
        + _pair("c1", "candidate", reference_id="r1", dimension="clarity")
        + _pair("c2", "candidate", reference_id="r1")
    )
    result = score_candidate(records, candidate_id="c1", dimension="overall")
    assert result.wins == 1
    assert result.n == 2


def test_score_all_groups_by_candidate_and_dimension():
    records = (
        _pair("c1", "candidate", reference_id="r1")
        + _pair("c1", "reference", reference_id="r2")
        + _pair("c2", "candidate", reference_id="r1")
    )
    results = score_all(records)
    assert results[("c1", "overall")].n == 2
    assert results[("c1", "overall")].wins == 1
    assert results[("c2", "overall")].n == 1


def test_two_orders_of_one_pair_count_as_one_trial():
    """Regression: both orders used to be counted as independent trials."""
    result = score_candidate(_pair("c1", "candidate", reference_id="r1"))

    assert result.n == 1
    assert result.wins == 1


def test_order_disagreement_is_a_tie_not_a_win_and_a_loss():
    """Regression: a position-flipping judge used to manufacture 50%."""
    records = [
        ComparisonRecord("c1", "r1", "candidate_first", "candidate", "x", "m", "p", "t", False),
        ComparisonRecord("c1", "r1", "reference_first", "reference", "x", "m", "p", "t", False),
    ]
    result = score_candidate(records)

    assert result.n == 0
    assert not result.has_signal
    assert result.summary.disagreement_ties == 1
    assert result.summary.tie_rate == 1.0


def test_judge_tie_is_excluded_from_the_denominator():
    records = _pair("c1", "candidate", reference_id="r1") + _pair(
        "c1", "tie", reference_id="r2"
    )
    result = score_candidate(records)

    assert result.n == 1
    assert result.wins == 1
    assert result.summary.judge_ties == 1
    assert result.summary.tie_rate == 0.5
