"""Validation 1 (MockJudge pass): synthetic degradation ladder.

Ground truth by construction: intact > {truncated, shuffled, padded,
stripped}. Ordering *among* the degraded classes is not asserted.

Pipeline:
  - Pool = the 20 intact source texts, all tier=love.
  - Candidates = each of the 20 sources degraded 4 ways (80 candidates),
    plus each intact source scored against the *other* 19 intact texts
    (self excluded) as a same-tier baseline, plus 20 near-identical
    control texts scored against the same pool.
  - `hibiscus score`-equivalent win rates (via score_candidate) per class.
  - `score_spread` across each class's candidates, and across the control
    set (which should NOT be flagged as discriminating).
  - `length_bias` across all degraded candidates (the padded-class probe).
  - `calibrate`-equivalent run (via run_calibration) once per degraded
    class: love=intact(20), okay=that class's 20 variants, nope=empty.

No library code is modified. Everything here is exercised through public
hibiscus APIs exactly as a user would call them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hibiscus import Artifact, Pool, RatedArtifact, Tier  # noqa: E402
from hibiscus.calibrate import run_calibration  # noqa: E402
from hibiscus.compare import ComparisonRecord, run_comparisons  # noqa: E402
from hibiscus.judge.mock import MockJudge  # noqa: E402
from hibiscus.score import length_bias, score_candidate, score_spread  # noqa: E402

from control_texts import CONTROLS  # noqa: E402
from degrade import DEGRADATION_CLASSES, degrade  # noqa: E402
from texts import SOURCES  # noqa: E402

SEED = 20240601
K_REFS = 5


def build_pool() -> Pool:
    pool = Pool(None)
    for tid, text in SOURCES:
        pool.add(RatedArtifact(id=tid, text=text, tier=Tier.LOVE))
    return pool


def run_all_comparisons(pool: Pool, judge) -> dict[str, list[ComparisonRecord]]:
    """Returns records grouped by degradation class, plus 'intact' (self-excluded)
    and 'control' (near-identical set)."""
    records_by_class: dict[str, list[ComparisonRecord]] = {k: [] for k in DEGRADATION_CLASSES}
    records_by_class["intact"] = []
    records_by_class["control"] = []

    for kind in DEGRADATION_CLASSES:
        for tid, text in SOURCES:
            degraded_text = degrade(text, kind, seed=hash(tid) % 10_000)
            candidate = Artifact(id=f"{tid}__{kind}", text=degraded_text)
            recs = run_comparisons(
                candidate, pool, judge, k=K_REFS, seed=SEED, model="mock-v1",
                dimension=kind,
            )
            records_by_class[kind].extend(recs)

    # Intact baseline: score each source against the *other* 19 (exclude self).
    for tid, text in SOURCES:
        candidate = Artifact(id=f"{tid}__intact", text=text)
        recs = run_comparisons(
            candidate, pool, judge, k=K_REFS, seed=SEED, model="mock-v1",
            dimension="intact", exclude_ids={tid},
        )
        records_by_class["intact"].extend(recs)

    # Control: near-identical texts, no exclusion needed (none are in the pool).
    for tid, text in CONTROLS:
        candidate = Artifact(id=tid, text=text)
        recs = run_comparisons(
            candidate, pool, judge, k=K_REFS, seed=SEED, model="mock-v1",
            dimension="control",
        )
        records_by_class["control"].extend(recs)

    return records_by_class


def report_win_rates(records_by_class: dict[str, list[ComparisonRecord]]) -> dict:
    out = {}
    for cls, records in records_by_class.items():
        by_candidate: dict[str, list[ComparisonRecord]] = {}
        for r in records:
            by_candidate.setdefault(r.candidate_id, []).append(r)
        per_candidate = {}
        for cid, recs in sorted(by_candidate.items()):
            result = score_candidate(recs)
            per_candidate[cid] = {
                "has_signal": result.has_signal,
                "win_rate": result.point_estimate if result.has_signal else None,
                "wins": result.wins,
                "n": result.n,
                "ties": result.summary.ties if result.summary else None,
            }
        rates = [v["win_rate"] for v in per_candidate.values() if v["win_rate"] is not None]
        mean_rate = sum(rates) / len(rates) if rates else None
        out[cls] = {"per_candidate": per_candidate, "mean_win_rate": mean_rate, "n_candidates": len(rates)}
    return out


def main() -> None:
    pool = build_pool()
    judge = MockJudge()
    print(f"pool: {len(pool.filter_by_tier(Tier.LOVE))} love-tier references")

    records_by_class = run_all_comparisons(pool, judge)

    print("\n=== Win rates by class (mean across candidates) ===")
    win_rates = report_win_rates(records_by_class)
    for cls in ["intact", "truncated", "shuffled", "padded", "stripped", "control"]:
        info = win_rates[cls]
        mean = info["mean_win_rate"]
        mean_str = f"{mean:.1%}" if mean is not None else "n/a"
        print(f"  {cls:>10}: mean win rate {mean_str} over {info['n_candidates']} candidates with signal")

    print("\n=== Spread check per class (score_spread) ===")
    spread_summary = {}
    for cls in ["truncated", "shuffled", "padded", "stripped", "control", "intact"]:
        spread = score_spread(records_by_class[cls], dimension=cls)
        ratio = "n/a" if spread.dispersion_ratio is None else f"{spread.dispersion_ratio:.2f}x"
        print(
            f"  {cls:>10}: n={spread.n_candidates:>2} spread {spread.minimum:.1%}-{spread.maximum:.1%} "
            f"(sd {spread.stdev:.3f}, {ratio} sampling noise) discriminating={spread.discriminating}"
        )
        spread_summary[cls] = {
            "n_candidates": spread.n_candidates,
            "mean": spread.mean,
            "stdev": spread.stdev,
            "minimum": spread.minimum,
            "maximum": spread.maximum,
            "dispersion_ratio": spread.dispersion_ratio,
            "discriminating": spread.discriminating,
        }

    print("\n=== Length bias check (the padded probe) ===")
    all_degraded_records = (
        records_by_class["truncated"]
        + records_by_class["shuffled"]
        + records_by_class["padded"]
        + records_by_class["stripped"]
    )
    for cls in ["truncated", "shuffled", "padded", "stripped"]:
        bias = length_bias(records_by_class[cls], dimension=cls)
        corr_str = "n/a" if bias.correlation is None else f"{bias.correlation:+.2f}"
        print(f"  {cls:>10}: length-vs-win-rate correlation {corr_str} (n={bias.n_candidates}) flagged={bias.flagged}")

    print("\n=== Calibrate-style check: love=intact(20) vs okay=<class>(20), nope=empty ===")
    calibration_summary = {}
    for kind in DEGRADATION_CLASSES:
        cal_pool = Pool(None)
        for tid, text in SOURCES:
            cal_pool.add(RatedArtifact(id=tid, text=text, tier=Tier.LOVE))
        for tid, text in SOURCES:
            degraded_text = degrade(text, kind, seed=hash(tid) % 10_000)
            cal_pool.add(RatedArtifact(id=f"{tid}__{kind}", text=degraded_text, tier=Tier.OKAY))

        report = run_calibration(
            cal_pool, MockJudge(), k=K_REFS, seed=SEED, model="mock-v1",
            max_per_tier=None,
        )
        love_wr = report.by_tier[Tier.LOVE].win_rate
        okay_wr = report.by_tier[Tier.OKAY].win_rate
        love_str = f"{love_wr.point_estimate:.1%}" if love_wr.has_signal else "no signal"
        okay_str = f"{okay_wr.point_estimate:.1%}" if okay_wr.has_signal else "no signal"
        verdict = "PASS" if report.ordering_holds else "FAIL"
        print(
            f"  {kind:>10}: love(intact)={love_str}  okay({kind})={okay_str}  "
            f"-> {verdict}  separation={report.separation}"
        )
        calibration_summary[kind] = {
            "love_win_rate": love_wr.point_estimate if love_wr.has_signal else None,
            "okay_win_rate": okay_wr.point_estimate if okay_wr.has_signal else None,
            "ordering_holds": report.ordering_holds,
            "inversions": [[hi.value, lo.value] for hi, lo in report.inversions],
            "separation": report.separation,
        }

    results = {
        "win_rates": win_rates,
        "spread": spread_summary,
        "calibration": calibration_summary,
    }
    out_path = Path(__file__).resolve().parent / "mock_results.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
