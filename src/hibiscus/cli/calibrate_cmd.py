"""The ``hibiscus calibrate`` command: sanity-check the judge against your tiers."""

from __future__ import annotations

import json
import sys

from ..cache import JudgeCache
from ..calibrate import DEFAULT_MAX_PER_TIER, run_calibration
from ..compare import order_disagreement_rate, save_comparisons
from ..pool import Pool


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "calibrate",
        help="Check that the judge reproduces your own tier ordering before you trust it.",
    )
    parser.add_argument("--pool", required=True)
    parser.add_argument("--reference-tier", default="love")
    parser.add_argument("-k", type=int, default=2)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--judge", choices=["mock", "anthropic"], default="mock")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--question", help="Override the default comparison question")
    parser.add_argument("--cache", help="Path to a judge response cache JSONL file")
    parser.add_argument(
        "--max-per-tier",
        type=int,
        default=DEFAULT_MAX_PER_TIER,
        help=f"Cap items scored per tier (default {DEFAULT_MAX_PER_TIER}; 0 for no cap)",
    )
    parser.add_argument("--out", help="Write the calibration report as JSON to this path")
    parser.add_argument("--comparisons-out", help="Append the raw comparison records here")
    parser.set_defaults(handler=_handle)


def _build_judge(name: str, model: str):
    if name == "mock":
        from ..judge.mock import MockJudge

        return MockJudge()
    from ..judge.anthropic_adapter import AnthropicJudge

    return AnthropicJudge(model=model)


def _handle(args) -> int:
    pool = Pool(args.pool)
    report = run_calibration(
        pool,
        _build_judge(args.judge, args.model),
        reference_tier=args.reference_tier,
        k=args.k,
        seed=args.seed,
        question=args.question,
        model=args.model,
        cache=JudgeCache(args.cache) if args.cache else None,
        max_per_tier=args.max_per_tier or None,
    )

    print(f"scored each tier against the {report.reference_tier.value!r} pool\n")
    for tier in report.tiers_high_to_low:
        cal = report.by_tier[tier]
        wr = cal.win_rate
        capped = f"  (capped from {cal.n_available})" if cal.capped else ""
        print(
            f"  {tier.value:>5}: {wr.point_estimate:6.1%} "
            f"[{wr.lower:.1%}, {wr.upper:.1%}]  "
            f"{cal.n_candidates} items, {wr.n} comparisons{capped}"
        )

    disagreement = order_disagreement_rate(report.records)
    print(f"\norder-disagreement rate: {disagreement:.1%}")

    if report.separation is not None:
        print(f"top-to-bottom separation: {report.separation:.1%}")

    if report.ordering_holds:
        print("\nPASS — win rates follow your hand-assigned tier ordering.")
    else:
        for higher, lower in report.inversions:
            print(
                f"  inversion: {lower.value!r} outscored {higher.value!r}",
                file=sys.stderr,
            )
        if not report.inversions and report.separation == 0:
            print(
                "  every tier scored identically — the judge is not separating them",
                file=sys.stderr,
            )
        print(
            "\nFAIL — win rates do not follow your tier ordering. Scores from this "
            "judge/pool pairing should not be trusted until this is resolved.",
            file=sys.stderr,
        )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)
    if args.comparisons_out:
        save_comparisons(args.comparisons_out, report.records, append=True)

    return 0 if report.ordering_holds else 1
