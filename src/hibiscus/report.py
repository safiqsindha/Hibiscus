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
    """A dimension x dimension correlation matrix plus flagged redundant pairs.

    A matrix entry is ``None`` when that dimension pair shares fewer than
    two artifacts, so a correlation could not be computed for it.
    """

    dimensions: list[str]
    matrix: dict[str, dict[str, "float | None"]]
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

    Each pair is correlated over the artifacts scored on *both* of its
    dimensions, rather than only over artifacts scored on every dimension
    in the set. Real rubric history is usually ragged — one dimension
    added late, a handful of artifacts never scored on it — and
    intersecting across all dimensions at once would silently discard
    most of it, or all of it if any two dimensions never overlap.
    """
    by_dimension: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        by_dimension[row.dimension][row.artifact_id] = row.score

    dimensions = sorted(by_dimension)

    matrix: dict[str, dict[str, "float | None"]] = {}
    redundant: list[tuple[str, str, float]] = []
    computed_any = False
    for i, dim_a in enumerate(dimensions):
        matrix[dim_a] = {}
        for j, dim_b in enumerate(dimensions):
            shared = sorted(set(by_dimension[dim_a]) & set(by_dimension[dim_b]))
            if len(shared) < 2:
                matrix[dim_a][dim_b] = None
                continue
            corr = pearson(
                [by_dimension[dim_a][a] for a in shared],
                [by_dimension[dim_b][a] for a in shared],
            )
            matrix[dim_a][dim_b] = corr
            computed_any = True
            if i < j and corr >= threshold:
                redundant.append((dim_a, dim_b, corr))

    if not computed_any:
        raise ValueError(
            "no dimension pair shares at least two scored artifacts; "
            "cannot compute any correlation"
        )

    return CorrelationReport(dimensions=dimensions, matrix=matrix, redundant_pairs=redundant)
