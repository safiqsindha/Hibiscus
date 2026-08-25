from __future__ import annotations

import pytest

from hibiscus.compare import SCHEMA_VERSION, ComparisonRecord
from hibiscus.pairs import count_legacy_records, resolve_pairs, summarize_pairs


def _rec(order, winner, *, candidate="c", reference="r", dimension="overall", version=None):
    kwargs = {}
    if version is not None:
        kwargs["schema_version"] = version
    return ComparisonRecord(
        candidate_id=candidate,
        reference_id=reference,
        order=order,
        winner=winner,
        raw_response="x",
        model="m",
        prompt_hash="p",
        timestamp="t",
        cache_hit=False,
        dimension=dimension,
        **kwargs,
    )


# Every combination of the two order verdicts.
@pytest.mark.parametrize(
    "first,second,expected,reason",
    [
        ("candidate", "candidate", "win", None),
        ("reference", "reference", "loss", None),
        ("candidate", "reference", "tie", "order_disagreement"),
        ("reference", "candidate", "tie", "order_disagreement"),
        ("tie", "tie", "tie", "judge"),
        ("tie", "candidate", "tie", "judge"),
        ("candidate", "tie", "tie", "judge"),
        ("tie", "reference", "tie", "judge"),
        ("reference", "tie", "tie", "judge"),
    ],
)
def test_pair_resolution_matrix(first, second, expected, reason):
    pairs = resolve_pairs([_rec("candidate_first", first), _rec("reference_first", second)])

    assert len(pairs) == 1
    assert pairs[0].outcome == expected
    assert pairs[0].tie_reason == reason
    assert pairs[0].counterbalanced


def test_pairs_are_grouped_by_candidate_reference_and_dimension():
    records = [
        _rec("candidate_first", "candidate", reference="r1"),
        _rec("reference_first", "candidate", reference="r1"),
        _rec("candidate_first", "reference", reference="r2"),
        _rec("reference_first", "reference", reference="r2"),
        _rec("candidate_first", "candidate", reference="r1", dimension="clarity"),
        _rec("reference_first", "candidate", reference="r1", dimension="clarity"),
    ]
    pairs = resolve_pairs(records)

    assert len(pairs) == 3
    assert {(p.reference_id, p.dimension, p.outcome) for p in pairs} == {
        ("r1", "overall", "win"),
        ("r2", "overall", "loss"),
        ("r1", "clarity", "win"),
    }


def test_single_order_pair_is_resolved_but_flagged():
    pairs = resolve_pairs([_rec("candidate_first", "candidate")])

    assert len(pairs) == 1
    assert pairs[0].outcome == "win"
    assert not pairs[0].counterbalanced

    summary = summarize_pairs(pairs)
    assert summary.uncounterbalanced == 1


def test_summary_counts_both_kinds_of_tie():
    records = [
        _rec("candidate_first", "candidate", reference="r1"),
        _rec("reference_first", "candidate", reference="r1"),
        _rec("candidate_first", "tie", reference="r2"),
        _rec("reference_first", "tie", reference="r2"),
        _rec("candidate_first", "candidate", reference="r3"),
        _rec("reference_first", "reference", reference="r3"),
    ]
    summary = summarize_pairs(resolve_pairs(records))

    assert summary.wins == 1
    assert summary.losses == 0
    assert summary.ties == 2
    assert summary.judge_ties == 1
    assert summary.disagreement_ties == 1
    assert summary.decisive == 1
    assert summary.total == 3
    assert summary.tie_rate == pytest.approx(2 / 3)


def test_tie_rate_of_empty_set_is_zero_not_a_crash():
    summary = summarize_pairs([])
    assert summary.total == 0
    assert summary.tie_rate == 0.0


def test_records_without_a_version_marker_count_as_legacy():
    legacy = ComparisonRecord.from_dict(
        {
            "candidate_id": "c",
            "reference_id": "r",
            "order": "candidate_first",
            "winner": "candidate",
            "raw_response": "x",
            "model": "m",
            "prompt_hash": "p",
            "timestamp": "t",
            "cache_hit": False,
        }
    )
    current = _rec("candidate_first", "candidate")

    assert legacy.schema_version == 1
    assert current.schema_version == SCHEMA_VERSION
    assert count_legacy_records([legacy, current]) == 1


def test_future_schema_version_fails_loudly():
    with pytest.raises(ValueError, match="schema_version"):
        ComparisonRecord.from_dict(
            {
                "candidate_id": "c",
                "reference_id": "r",
                "order": "candidate_first",
                "winner": "candidate",
                "raw_response": "x",
                "model": "m",
                "prompt_hash": "p",
                "timestamp": "t",
                "cache_hit": False,
                "schema_version": SCHEMA_VERSION + 1,
            }
        )


def test_candidate_length_is_carried_onto_the_pair():
    records = [
        ComparisonRecord("c", "r", "candidate_first", "candidate", "x", "m", "p", "t", False,
                         candidate_length=42),
        ComparisonRecord("c", "r", "reference_first", "candidate", "x", "m", "p", "t", False,
                         candidate_length=42),
    ]
    assert resolve_pairs(records)[0].candidate_length == 42
