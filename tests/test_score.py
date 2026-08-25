from __future__ import annotations

import pytest

from hibiscus.compare import ComparisonRecord
from hibiscus.score import score_all, score_candidate, wilson_interval


def _rec(candidate_id, winner, dimension="overall"):
    return ComparisonRecord(
        candidate_id=candidate_id,
        reference_id="r",
        order="candidate_first",
        winner=winner,
        raw_response="x",
        model="m",
        prompt_hash="p",
        timestamp="t",
        cache_hit=False,
        dimension=dimension,
    )


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
    records = [
        _rec("c1", "candidate", dimension="overall"),
        _rec("c1", "reference", dimension="overall"),
        _rec("c1", "candidate", dimension="clarity"),
        _rec("c2", "candidate", dimension="overall"),
    ]
    result = score_candidate(records, candidate_id="c1", dimension="overall")
    assert result.wins == 1
    assert result.n == 2


def test_score_all_groups_by_candidate_and_dimension():
    records = [
        _rec("c1", "candidate"),
        _rec("c1", "reference"),
        _rec("c2", "candidate"),
    ]
    results = score_all(records)
    assert results[("c1", "overall")].n == 2
    assert results[("c1", "overall")].wins == 1
    assert results[("c2", "overall")].n == 1
