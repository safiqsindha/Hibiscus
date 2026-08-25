"""Validation 1 (real-judge pass): synthetic degradation ladder, small subset.

Same pipeline as run_mock.py, but on a 5-source subset, using ManualJudge
(see manual_judge.py) -- verdicts I produced by actually reading each pair,
since no ANTHROPIC_API_KEY is available in this sandbox. See FINDINGS.md
for the disclosed limitation (this cannot test position-bias susceptibility,
only whether real semantic judgment recovers the intended ordering).

60 raw judge calls total (well under the ~200 budget): 5 sources x 4
degraded classes x 2 references = 40, plus 5 sources' intact self-check x 2
references = 10, plus 5 control texts x 2 references = 10.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hibiscus import Artifact, Pool, RatedArtifact, Tier  # noqa: E402
from hibiscus.compare import ComparisonRecord, run_comparisons  # noqa: E402
from hibiscus.score import score_candidate, score_spread  # noqa: E402

from control_texts import CONTROLS  # noqa: E402
from degrade import degrade  # noqa: E402
from manual_judge import load_manual_judge  # noqa: E402
from texts import SOURCES  # noqa: E402

SEED = 20240601
K_REFS = 2
SUBSET = ["src-00", "src-03", "src-07", "src-11", "src-15"]


def main() -> None:
    src_map = dict(SOURCES)
    ctl_map = dict(CONTROLS)

    pool = Pool(None)
    for tid, text in SOURCES:
        pool.add(RatedArtifact(id=tid, text=text, tier=Tier.LOVE))

    # id_to_text must cover every id ManualJudge will be asked to resolve:
    # plain source ids (references, or the "intact" degradation baseline
    # sharing the source's own text), degraded-candidate ids, and control ids.
    id_to_text = dict(SOURCES)
    id_to_text.update(dict(CONTROLS))
    for tid in SUBSET:
        for kind in ("truncated", "shuffled", "padded", "stripped"):
            id_to_text[f"{tid}__{kind}"] = degrade(src_map[tid], kind, seed=hash(tid) % 10_000)
        id_to_text[f"{tid}__intact"] = src_map[tid]

    judge = load_manual_judge(Path(__file__).resolve().parent / "manual_verdicts.json", id_to_text)

    records_by_class: dict[str, list[ComparisonRecord]] = {
        "truncated": [], "shuffled": [], "padded": [], "stripped": [], "intact": [], "control": [],
    }

    for tid in SUBSET:
        for kind in ("truncated", "shuffled", "padded", "stripped"):
            candidate = Artifact(id=f"{tid}__{kind}", text=id_to_text[f"{tid}__{kind}"])
            recs = run_comparisons(candidate, pool, judge, k=K_REFS, seed=SEED, model="manual-v1", dimension=kind)
            records_by_class[kind].extend(recs)

        candidate = Artifact(id=f"{tid}__intact", text=src_map[tid])
        recs = run_comparisons(
            candidate, pool, judge, k=K_REFS, seed=SEED, model="manual-v1",
            dimension="intact", exclude_ids={tid},
        )
        records_by_class["intact"].extend(recs)

    for tid in ["ctl-00", "ctl-01", "ctl-02", "ctl-03", "ctl-04"]:
        candidate = Artifact(id=tid, text=ctl_map[tid])
        recs = run_comparisons(candidate, pool, judge, k=K_REFS, seed=SEED, model="manual-v1", dimension="control")
        records_by_class["control"].extend(recs)

    print(f"total ManualJudge.compare() calls: {judge.calls}")

    print("\n=== Win rates by class (mean across candidates), real-judge subset ===")
    win_rates = {}
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
                "wins": result.wins, "n": result.n,
                "ties": result.summary.ties if result.summary else None,
            }
            wr = "n/a" if not result.has_signal else f"{result.point_estimate:.0%}"
            print(f"    {cid:>20}: {wr} ({result.wins}/{result.n}, {result.summary.ties if result.summary else 0} ties)")
        rates = [v["win_rate"] for v in per_candidate.values() if v["win_rate"] is not None]
        mean_rate = sum(rates) / len(rates) if rates else None
        win_rates[cls] = {"per_candidate": per_candidate, "mean_win_rate": mean_rate, "n_candidates": len(rates)}
        mean_str = f"{mean_rate:.1%}" if mean_rate is not None else "n/a"
        print(f"  -> {cls:>10} mean: {mean_str}\n")

    print("=== Spread check per class ===")
    spread_summary = {}
    for cls in ["truncated", "shuffled", "padded", "stripped", "intact", "control"]:
        spread = score_spread(records_by_class[cls], dimension=cls)
        ratio = "n/a" if spread.dispersion_ratio is None else f"{spread.dispersion_ratio:.2f}x"
        print(
            f"  {cls:>10}: n={spread.n_candidates} spread {spread.minimum:.0%}-{spread.maximum:.0%} "
            f"(sd {spread.stdev:.3f}, {ratio}) discriminating={spread.discriminating}"
        )
        spread_summary[cls] = {
            "n_candidates": spread.n_candidates, "mean": spread.mean, "stdev": spread.stdev,
            "minimum": spread.minimum, "maximum": spread.maximum,
            "dispersion_ratio": spread.dispersion_ratio, "discriminating": spread.discriminating,
        }

    results = {"win_rates": win_rates, "spread": spread_summary, "n_calls": judge.calls}
    out_path = Path(__file__).resolve().parent / "real_judge_results.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
