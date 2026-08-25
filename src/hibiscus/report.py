"""The dimension-correlation diagnostic.

Point this at any set of artifacts scored on multiple dimensions —
Hibiscus's own output or an existing rubric's score history — and it
flags dimension pairs that are effectively measuring the same thing.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScoreRow:
    """One (artifact, dimension, score) observation."""

    artifact_id: str
    dimension: str
    score: float


def load_rows(path: "str | Path") -> list[ScoreRow]:
    """Load score rows from a CSV or JSONL file (chosen by extension)."""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return _load_csv(p)
    return _load_jsonl(p)


def _load_csv(path: Path) -> list[ScoreRow]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(ScoreRow(row["artifact_id"], row["dimension"], float(row["score"])))
    return rows


def _load_jsonl(path: Path) -> list[ScoreRow]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rows.append(ScoreRow(data["artifact_id"], data["dimension"], float(data["score"])))
    return rows


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient. Returns 0.0 when either series has no variance."""
    n = len(xs)
    if n == 0 or n != len(ys):
        raise ValueError("xs and ys must be the same nonzero length")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


@dataclass(frozen=True)
class CorrelationReport:
    """A dimension x dimension correlation matrix plus flagged redundant pairs."""

    dimensions: list[str]
    matrix: dict[str, dict[str, float]]
    redundant_pairs: list[tuple[str, str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "matrix": self.matrix,
            "redundant_pairs": [
                {"dimension_a": a, "dimension_b": b, "correlation": c}
                for a, b, c in self.redundant_pairs
            ],
        }


def build_correlation_report(rows: list[ScoreRow], *, threshold: float = 0.85) -> CorrelationReport:
    """Build a correlation matrix across dimensions and flag pairs >= threshold.

    Only artifacts scored on every dimension present are used, so the
    matrix compares like with like.
    """
    by_dimension: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        by_dimension[row.dimension][row.artifact_id] = row.score

    dimensions = sorted(by_dimension)
    shared_artifacts = (
        set.intersection(*(set(d) for d in by_dimension.values())) if dimensions else set()
    )
    if len(shared_artifacts) < 2:
        raise ValueError(
            "need at least two artifacts scored on every dimension to compute correlations"
        )
    ordered_artifacts = sorted(shared_artifacts)

    matrix: dict[str, dict[str, float]] = {}
    redundant: list[tuple[str, str, float]] = []
    for i, dim_a in enumerate(dimensions):
        matrix[dim_a] = {}
        xs = [by_dimension[dim_a][a] for a in ordered_artifacts]
        for j, dim_b in enumerate(dimensions):
            ys = [by_dimension[dim_b][a] for a in ordered_artifacts]
            corr = pearson(xs, ys)
            matrix[dim_a][dim_b] = corr
            if i < j and corr >= threshold:
                redundant.append((dim_a, dim_b, corr))

    return CorrelationReport(dimensions=dimensions, matrix=matrix, redundant_pairs=redundant)
