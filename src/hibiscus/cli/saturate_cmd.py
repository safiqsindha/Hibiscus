"""The ``hibiscus saturate`` command: is the reference pool big enough?"""

from __future__ import annotations

import json

from ..cache import JudgeCache
from ..cli.compare_cmd import _load_candidates
from ..pool import Pool
from ..saturate import (
    DEFAULT_RATE_TOLERANCE,
    DEFAULT_REPEATS,
    DEFAULT_STEP,
    DEFAULT_TAU_TOLERANCE,
    run_saturation,
)


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "saturate",
        help="Check empirically whether the reference pool is large enough.",
    )
    parser.add_argument("--pool", required=True)
    parser.add_argument("--candidates", required=True, help="JSONL file of probe candidates")
    parser.add_argument("--tier", default="love")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--step", type=int, default=DEFAULT_STEP)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--judge", choices=["mock", "anthropic"], default="mock")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--question")
    parser.add_argument(
        "--cache", help="Judge cache JSONL — strongly recommended, this command is call-hungry"
    )
    parser.add_argument("--rate-tolerance", type=float, default=DEFAULT_RATE_TOLERANCE)
    parser.add_argument("--tau-tolerance", type=float, default=DEFAULT_TAU_TOLERANCE)
    parser.add_argument("--out", help="Write the full report as JSON to this path")
    parser.set_defaults(handler=_handle)


def _build_judge(name: str, model: str):
    if name == "mock":
        from ..judge.mock import MockJudge

        return MockJudge()
    from ..judge.anthropic_adapter import AnthropicJudge

    return AnthropicJudge(model=model)


def _handle(args) -> int:
    report = run_saturation(
        Pool(args.pool),
        _load_candidates(args.candidates),
        _build_judge(args.judge, args.model),
        tier=args.tier,
        seed=args.seed,
        step=args.step,
        repeats=args.repeats,
        question=args.question,
        model=args.model,
        cache=JudgeCache(args.cache) if args.cache else None,
        rate_tolerance=args.rate_tolerance,
        tau_tolerance=args.tau_tolerance,
    )

    print(
        f"probing {report.n_candidates} candidates against a {report.pool_size}-item pool, "
        f"{args.repeats} subsets per size\n"
    )
    print(f"{'size':>5}  {'mean move':>10}  {'ordering tau':>13}  {'within-size sd':>15}")
    for step in report.steps:
        delta = "     —" if step.rate_delta is None else f"{step.rate_delta:9.3f}"
        tau = "        —" if step.tau_vs_previous is None else f"{step.tau_vs_previous:12.3f}"
        print(f"{step.size:>5}  {delta:>10}  {tau:>13}  {step.within_size_stdev:>15.3f}")

    print()
    if report.ordering_saturated_at is not None:
        print(
            f"ordering settled at {report.ordering_saturated_at} references "
            f"(tau >= {report.tau_tolerance} for two consecutive sizes)"
        )
    else:
        print("ordering has NOT settled — candidates still reshuffle as the pool grows")

    if report.rate_saturated_at is not None:
        print(
            f"win rates settled at {report.rate_saturated_at} references "
            f"(mean move <= {report.rate_tolerance} for two consecutive sizes)"
        )
    else:
        print("win rates have NOT settled — keep rating, the pool is still too small")

    print(
        "\nNote: this shows the measurement has stopped moving, not that the pool "
        "captures your taste. A pool can settle on a consistently wrong answer. "
        "Run `hibiscus calibrate` for that question."
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)

    return 0
