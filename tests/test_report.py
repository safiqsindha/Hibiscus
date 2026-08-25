from __future__ import annotations

import pytest

from hibiscus.report import ScoreRow, build_correlation_report, load_rows, pearson


def test_pearson_perfect_positive_correlation():
    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)


def test_pearson_perfect_negative_correlation():
    assert pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)


def test_pearson_zero_variance_returns_zero():
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0


def test_correlation_report_flags_duplicated_dimension():
    base_scores = {"a1": 0.9, "a2": 0.2, "a3": 0.5, "a4": 0.8, "a5": 0.1}
    rows = []
    for artifact_id, score in base_scores.items():
        rows.append(ScoreRow(artifact_id, "novelty", score))
        rows.append(ScoreRow(artifact_id, "novelty_dup", score))  # exact duplicate signal
        rows.append(ScoreRow(artifact_id, "unrelated", 0.5))  # no variance -> uncorrelated

    report = build_correlation_report(rows, threshold=0.85)

    flagged = {(a, b) for a, b, _ in report.redundant_pairs}
    assert ("novelty", "novelty_dup") in flagged
    assert not any("unrelated" in pair for pair in flagged)


def test_correlation_report_matrix_diagonal_is_one():
    rows = [
        ScoreRow("a1", "x", 0.1),
        ScoreRow("a2", "x", 0.9),
        ScoreRow("a1", "y", 0.4),
        ScoreRow("a2", "y", 0.6),
    ]
    report = build_correlation_report(rows, threshold=0.85)
    for dim in report.dimensions:
        assert report.matrix[dim][dim] == pytest.approx(1.0)


def test_correlation_report_requires_shared_artifacts():
    rows = [ScoreRow("a1", "x", 0.5), ScoreRow("a1", "y", 0.5)]
    with pytest.raises(ValueError):
        build_correlation_report(rows)


def test_load_rows_csv(tmp_path):
    path = tmp_path / "scores.csv"
    path.write_text("artifact_id,dimension,score\na1,x,0.5\na1,y,0.7\n", encoding="utf-8")
    rows = load_rows(path)
    assert len(rows) == 2
    assert rows[0] == ScoreRow("a1", "x", 0.5)


def test_load_rows_jsonl(tmp_path):
    path = tmp_path / "scores.jsonl"
    path.write_text(
        '{"artifact_id": "a1", "dimension": "x", "score": 0.5}\n'
        '{"artifact_id": "a1", "dimension": "y", "score": 0.7}\n',
        encoding="utf-8",
    )
    rows = load_rows(path)
    assert len(rows) == 2
    assert rows[1] == ScoreRow("a1", "y", 0.7)
