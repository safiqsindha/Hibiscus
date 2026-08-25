"""The ``hibiscus score`` command: win rates with Wilson intervals."""

from __future__ import annotations

import json
import sys

from ..compare import load_comparisons
from ..score import score_all, score_candidate, score_spread


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "score", help="Aggregate comparisons into win rates with Wilson intervals."
    )
    parser.add_argument("--comparisons", required=True)
    parser.add_argument("--candidate", help="Score only this candidate id")
    parser.add_argument("--dimension", help="Score only this dimension")
    parser.add_argument("--out", help="Write results as JSON to this path")
    parser.set_defaults(handler=_handle)


def _handle(args) -> int:
    records = load_comparisons(args.comparisons)

    if args.candidate:
        result = score_candidate(records, candidate_id=args.candidate, dimension=args.dimension)
        rows = {f"{args.candidate}:{args.dimension or 'overall'}": result}
    else:
        rows = {f"{cid}:{dim}": r for (cid, dim), r in score_all(records).items()}

    output = {
        key: {
            "wins": r.wins,
            "n": r.n,
            "win_rate": round(r.point_estimate, 4),
            "wilson_lower": round(r.lower, 4),
            "wilson_upper": round(r.upper, 4),
        }
        for key, r in rows.items()
    }

    for key, stats in output.items():
        print(
            f"{key}: {stats['win_rate']:.1%} win rate "
            f"[{stats['wilson_lower']:.1%}, {stats['wilson_upper']:.1%}] "
            f"({stats['wins']}/{stats['n']})"
        )

    payload: dict = {"scores": output}

    spread = score_spread(records, dimension=args.dimension)
    if spread.n_candidates > 1:
        payload["spread"] = {
            "n_candidates": spread.n_candidates,
            "mean": round(spread.mean, 4),
            "stdev": round(spread.stdev, 4),
            "min": round(spread.minimum, 4),
            "max": round(spread.maximum, 4),
            "dispersion_ratio": (
                None if spread.dispersion_ratio is None else round(spread.dispersion_ratio, 3)
            ),
            "discriminating": spread.discriminating,
        }
        ratio = spread.dispersion_ratio
        ratio_text = "n/a" if ratio is None else f"{ratio:.2f}x"
        print(
            f"\nspread across {spread.n_candidates} candidates: "
            f"{spread.minimum:.1%}–{spread.maximum:.1%} "
            f"(sd {spread.stdev:.3f}, {ratio_text} sampling noise)"
        )
        if not spread.discriminating:
            print(
                "warning: win rates are not clearly separated from what pure sampling "
                "noise would produce — the judge may not be discriminating between "
                "these candidates. Run `hibiscus calibrate` to check the judge against "
                "your own tiers.",
                file=sys.stderr,
            )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    return 0
