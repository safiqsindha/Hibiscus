"""Hibiscus: pairwise evaluation against a hand-rated reference pool.

Judges generated artifacts the way a jury does — not with a score out of
five, but by hanging each candidate next to accepted work and asking
which is better.
"""

from __future__ import annotations

from .artifact import Artifact
from .cache import CacheKey, JudgeCache
from .calibrate import CalibrationReport, TierCalibration, run_calibration
from .compare import (
    ComparisonRecord,
    load_comparisons,
    order_disagreement_rate,
    run_comparisons,
    sample_references,
    save_comparisons,
)
from .pool import Pool, RatedArtifact
from .report import CorrelationReport, ScoreRow, build_correlation_report, load_rows, pearson
from .score import (
    SpreadResult,
    WinRateResult,
    score_all,
    score_candidate,
    score_spread,
    wilson_interval,
)
from .tiers import Tier, parse_tier

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Artifact",
    "Tier",
    "parse_tier",
    "Pool",
    "RatedArtifact",
    "JudgeCache",
    "CacheKey",
    "ComparisonRecord",
    "run_comparisons",
    "sample_references",
    "order_disagreement_rate",
    "save_comparisons",
    "load_comparisons",
    "WinRateResult",
    "wilson_interval",
    "score_candidate",
    "score_all",
    "SpreadResult",
    "score_spread",
    "CalibrationReport",
    "TierCalibration",
    "run_calibration",
    "ScoreRow",
    "CorrelationReport",
    "build_correlation_report",
    "load_rows",
    "pearson",
]
