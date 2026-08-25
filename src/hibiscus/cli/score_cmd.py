"""The ``hibiscus score`` command: win rates with Wilson intervals."""

from __future__ import annotations

import json
import sys

from ..compare import load_comparisons
from ..pairs import count_legacy_records, resolve_pairs, summarize_pairs
from ..score import length_bias, score_all, score_candidate, score_spread


def _filtered(records, args):
    """Apply the same candidate/dimension filters used for the score rows."""
    return [
        r
        for r in records
        if (not args.candidate or r.candidate_id == args.candidate)
        and (not args.dimension or r.dimension == args.dimension)
    ]


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
            "win_rate": round(r.point_estimate, 4) if r.has_signal else None,
            "wilson_lower": round(r.lower, 4) if r.has_signal else None,
            "wilson_upper": round(r.upper, 4) if r.has_signal else None,
            **(r.summary.to_dict() if r.summary else {}),
        }
        for key, r in rows.items()
    }

    for key, r in rows.items():
        summary = r.summary
        ties = f", {summary.ties} tie" + ("s" if summary.ties != 1 else "") if summary else ""
        if not r.has_signal:
            print(f"{key}: no discriminating comparisons — every pair tied")
            if summary:
                print(
                    f"    ({summary.ties} tied pairs: {summary.judge_ties} judge, "
                    f"{summary.disagreement_ties} order-disagreement)"
                )
            continue
        print(
            f"{key}: {r.point_estimate:.1%} win rate "
            f"[{r.lower:.1%}, {r.upper:.1%}] "
            f"({r.wins}/{r.n} decisive pairs{ties})"
        )

    payload: dict = {"scores": output}

    all_pairs = resolve_pairs(_filtered(records, args))
    overall = summarize_pairs(all_pairs, legacy_records=count_legacy_records(records))
    payload["pairs"] = overall.to_dict()
    if overall.total:
        print(
            f"\ntie rate: {overall.tie_rate:.1%} of {overall.total} pairs "
            f"({overall.judge_ties} judge, {overall.disagreement_ties} order-disagreement)"
        )
    if overall.uncounterbalanced:
        print(
            f"warning: {overall.uncounterbalanced} pair(s) had only one order and could not "
            "be position-controlled",
            file=sys.stderr,
        )
    if overall.legacy_records:
        print(
            f"note: {overall.legacy_records} record(s) predate the pair-resolution fix. They "
            "have been re-scored with the corrected logic, so these numbers will differ from "
            "any previously reported for the same file — the older numbers double-counted "
            "each pair.",
            file=sys.stderr,
        )

    bias = length_bias(records, dimension=args.dimension)
    payload["length_bias"] = bias.to_dict()
    if bias.correlation is not None:
        print(f"length-vs-win-rate correlation: {bias.correlation:+.2f}")
        if bias.flagged:
            print(
                f"warning: |r| >= {bias.threshold} — the judge may be rewarding length "
                "rather than quality. Diagnostic only; whether that is wrong depends on "
                "your artifacts.",
                file=sys.stderr,
            )

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
