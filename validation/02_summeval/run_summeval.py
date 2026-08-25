"""Validation 2: SummEval correlation check.

Reshapes the real SummEval human expert annotations (100 articles x 16
summarization systems, 3 expert annotators per summary, averaged) into
Hibiscus's {artifact_id, dimension, score} shape, runs `hibiscus report`
on it, and independently recomputes the same correlation matrix with
numpy/scipy as a cross-check. No library code is modified.

Data source: https://storage.googleapis.com/sfr-summarization-repo-research/model_annotations.aligned.jsonl
(the canonical SummEval release, Yale-LILY/SummEval + Salesforce Research;
Project Gutenberg-style direct GitHub API browsing wasn't available, but
this file -- linked from the SummEval GitHub README -- downloaded directly).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np  # noqa: E402
from scipy.stats import pearsonr  # noqa: E402

from hibiscus.report import ScoreRow, build_correlation_report  # noqa: E402

DATA_URL = "https://storage.googleapis.com/sfr-summarization-repo-research/model_annotations.aligned.jsonl"
DATA_PATH = Path(__file__).resolve().parent / "data" / "model_annotations.aligned.jsonl"
DIMENSIONS = ["coherence", "consistency", "fluency", "relevance"]


def ensure_data() -> None:
    if DATA_PATH.exists():
        return
    print(f"{DATA_PATH} not found; downloading from {DATA_URL} ...")
    import urllib.request

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(DATA_URL, DATA_PATH)


def load_rows() -> list[ScoreRow]:
    rows: list[ScoreRow] = []
    with DATA_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            artifact_id = f"{rec['id']}__{rec['model_id']}"
            experts = rec["expert_annotations"]
            for dim in DIMENSIONS:
                scores = [e[dim] for e in experts]
                rows.append(ScoreRow(artifact_id, dim, mean(scores)))
    return rows


def independent_matrix(rows: list[ScoreRow]) -> dict:
    """Recompute the same dimension x dimension Pearson matrix with scipy,
    over the same shared-artifact-per-pair basis build_correlation_report uses."""
    by_dim: dict[str, dict[str, float]] = {d: {} for d in DIMENSIONS}
    for r in rows:
        by_dim[r.dimension][r.artifact_id] = r.score

    matrix = {}
    for a in DIMENSIONS:
        matrix[a] = {}
        for b in DIMENSIONS:
            shared = sorted(set(by_dim[a]) & set(by_dim[b]))
            xs = np.array([by_dim[a][k] for k in shared])
            ys = np.array([by_dim[b][k] for k in shared])
            if len(shared) < 2 or xs.std() == 0 or ys.std() == 0:
                matrix[a][b] = None
                continue
            r_value, _p = pearsonr(xs, ys)
            matrix[a][b] = float(r_value)
    return matrix


def main() -> None:
    ensure_data()
    rows = load_rows()
    n_artifacts = len({r.artifact_id for r in rows})
    print(f"loaded {len(rows)} score rows across {n_artifacts} artifacts (article x system)")
    print(f"dimensions: {DIMENSIONS}")

    report = build_correlation_report(rows, threshold=0.85)

    print("\n=== hibiscus report correlation matrix ===")
    print("\t".join([""] + report.dimensions))
    for a in report.dimensions:
        cells = [f"{report.matrix[a][b]:.4f}" if report.matrix[a][b] is not None else "n/a" for b in report.dimensions]
        print("\t".join([a] + cells))

    print(f"\nredundant pairs (>= 0.85): {report.redundant_pairs if report.redundant_pairs else 'none'}")

    print("\n=== independent scipy/numpy recomputation ===")
    indep = independent_matrix(rows)
    print("\t".join([""] + DIMENSIONS))
    for a in DIMENSIONS:
        cells = [f"{indep[a][b]:.4f}" if indep[a][b] is not None else "n/a" for b in DIMENSIONS]
        print("\t".join([a] + cells))

    print("\n=== agreement check: hibiscus vs scipy/numpy ===")
    max_abs_diff = 0.0
    for a in DIMENSIONS:
        for b in DIMENSIONS:
            hib = report.matrix[a][b]
            ind = indep[a][b]
            if hib is None or ind is None:
                continue
            diff = abs(hib - ind)
            max_abs_diff = max(max_abs_diff, diff)
    print(f"max abs difference across all matrix cells: {max_abs_diff:.10f}")

    out = {
        "n_rows": len(rows),
        "n_artifacts": n_artifacts,
        "hibiscus_matrix": report.matrix,
        "scipy_matrix": indep,
        "redundant_pairs_0.85": [{"a": a, "b": b, "corr": c} for a, b, c in report.redundant_pairs],
        "max_abs_diff_hibiscus_vs_scipy": max_abs_diff,
    }
    out_path = Path(__file__).resolve().parent / "summeval_results.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
