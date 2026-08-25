"""Hibiscus: pairwise evaluation against a hand-rated reference pool.

Judges generated artifacts the way a jury does — not with a score out of
five, but by hanging each candidate next to accepted work and asking
which is better.
"""

from __future__ import annotations

from .artifact import Artifact
from .bradley_terry import BradleyTerryResult, fit_bradley_terry, rank_candidates, run_round_robin
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
from .pairs import PairOutcome, PairSummary, resolve_pairs, summarize_pairs
from .pool import Pool, RatedArtifact
from .report import CorrelationReport, ScoreRow, build_correlation_report, load_rows, pearson
from .saturate import SaturationReport, SaturationStep, kendall_tau, run_saturation
from .score import (
    LengthBiasResult,
    SpreadResult,
    WinRateResult,
    length_bias,
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
    "LengthBiasResult",
    "length_bias",
    "PairOutcome",
    "PairSummary",
    "resolve_pairs",
    "summarize_pairs",
    "CalibrationReport",
    "TierCalibration",
    "run_calibration",
    "SaturationReport",
    "SaturationStep",
    "run_saturation",
    "kendall_tau",
    "BradleyTerryResult",
    "fit_bradley_terry",
    "rank_candidates",
    "run_round_robin",
    "ScoreRow",
    "CorrelationReport",
    "build_correlation_report",
    "load_rows",
    "pearson",
]
