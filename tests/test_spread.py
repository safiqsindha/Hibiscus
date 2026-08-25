from __future__ import annotations

from hibiscus.compare import ComparisonRecord
from hibiscus.score import score_spread


def _records(candidate_id, wins, losses, dimension="overall"):
    out = []
    for i in range(wins):
        out.append(_rec(candidate_id, "candidate", dimension, i))
    for i in range(losses):
        out.append(_rec(candidate_id, "reference", dimension, wins + i))
    return out


def _rec(candidate_id, winner, dimension, i):
    return ComparisonRecord(
        candidate_id=candidate_id,
        reference_id=f"r{i}",
        order="candidate_first",
        winner=winner,
        raw_response="x",
        model="m",
        prompt_hash="p",
        timestamp="t",
        cache_hit=False,
        dimension=dimension,
    )


def test_identical_candidates_are_not_discriminating():
    """The failure this exists to catch: everything scores the same."""
    records = []
    for c in range(8):
        records += _records(f"c{c}", 5, 5)

    spread = score_spread(records)

    assert spread.n_candidates == 8
    assert spread.stdev == 0.0
    assert not spread.discriminating


def test_widely_separated_candidates_are_discriminating():
    records = []
    for c in range(4):
        records += _records(f"win{c}", 10, 0)
    for c in range(4):
        records += _records(f"lose{c}", 0, 10)

    spread = score_spread(records)

    assert spread.discriminating
    assert spread.dispersion_ratio > spread.threshold
    assert spread.spread == 1.0


def test_dispersion_near_one_reads_as_noise():
    """Win rates that differ, but only as much as coin-flips would."""
    records = []
    for c, wins in enumerate([4, 5, 6, 5, 4, 6, 5, 5]):
        records += _records(f"c{c}", wins, 10 - wins)

    spread = score_spread(records)

    assert spread.dispersion_ratio is not None
    assert spread.dispersion_ratio < 1.5
    assert not spread.discriminating


def test_single_candidate_does_not_crash():
    spread = score_spread(_records("only", 3, 1))

    assert spread.n_candidates == 1
    assert spread.dispersion_ratio is None
    assert not spread.discriminating


def test_no_records_does_not_crash():
    spread = score_spread([])

    assert spread.n_candidates == 0
    assert spread.dispersion_ratio is None
    assert not spread.discriminating


def test_unanimous_outcomes_report_no_ratio():
    """Every comparison won by every candidate: no variance to compare against."""
    records = []
    for c in range(3):
        records += _records(f"c{c}", 6, 0)

    spread = score_spread(records)

    assert spread.dispersion_ratio is None
    assert not spread.discriminating


def test_spread_filters_by_dimension():
    records = _records("c0", 10, 0, dimension="a") + _records("c1", 0, 10, dimension="a")
    records += _records("c0", 5, 5, dimension="b") + _records("c1", 5, 5, dimension="b")

    assert score_spread(records, dimension="a").discriminating
    assert not score_spread(records, dimension="b").discriminating


def test_min_max_and_mean_track_the_candidates():
    records = _records("hi", 8, 2) + _records("lo", 2, 8)

    spread = score_spread(records)

    assert spread.minimum == 0.2
    assert spread.maximum == 0.8
    assert spread.mean == 0.5
