"""The ``hibiscus score`` command: win rates with Wilson intervals."""

from __future__ import annotations

import json

from ..compare import load_comparisons
from ..score import score_all, score_candidate


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

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(output, fh, ensure_ascii=False, indent=2)

    return 0
