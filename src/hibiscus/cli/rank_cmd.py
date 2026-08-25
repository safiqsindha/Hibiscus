"""The ``hibiscus rank`` command: Bradley-Terry ranking of candidates.

Optional and deliberately separate from ``score``. The pool-anchored win
rate is the default and recommended path; this ranks a batch against
itself and produces a population-relative number that must not be used as
a gate.
"""

from __future__ import annotations

import json
import sys

from ..bradley_terry import rank_candidates
from ..cache import JudgeCache
from ..cli.compare_cmd import _load_candidates
from ..compare import save_comparisons


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "rank",
        help="Rank candidates against EACH OTHER (Bradley-Terry). Not an acceptance gate.",
    )
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--judge", choices=["mock", "anthropic"], default="mock")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--question")
    parser.add_argument("--cache")
    parser.add_argument("--out", help="Write the fitted model as JSON to this path")
    parser.add_argument("--comparisons-out", help="Append the raw comparison records here")
    parser.set_defaults(handler=_handle)


def _build_judge(name: str, model: str):
    if name == "mock":
        from ..judge.mock import MockJudge

        return MockJudge()
    from ..judge.anthropic_adapter import AnthropicJudge

    return AnthropicJudge(model=model)


def _handle(args) -> int:
    candidates = _load_candidates(args.candidates)
    if len(candidates) < 2:
        print("error: need at least two candidates to rank", file=sys.stderr)
        return 2

    result, records = rank_candidates(
        candidates,
        _build_judge(args.judge, args.model),
        question=args.question,
        model=args.model,
        cache=JudgeCache(args.cache) if args.cache else None,
    )

    print(
        f"Bradley-Terry over {result.n_comparisons} decisive comparisons "
        f"among {result.n_items} candidates "
        f"({'converged' if result.converged else f'stopped at {result.iterations} iterations'})\n"
    )
    for rank, (item, strength) in enumerate(result.ranking(), start=1):
        print(f"  {rank:>3}. {item:<24} {strength:+.3f}")

    if len(result.judge_effects) > 1:
        print("\njudge effects (positive = more lenient toward the candidate side):")
        for judge, effect in sorted(result.judge_effects.items()):
            print(f"  {judge:<28} {effect:+.3f}")

    print(
        "\nNote: these strengths are RELATIVE to this batch. They shift when the batch "
        "changes and are not comparable across runs, so do not use them as an acceptance "
        "threshold — use the pool-anchored win rate from `hibiscus score` for that, and "
        "do not average the two together."
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)
    if args.comparisons_out:
        save_comparisons(args.comparisons_out, records, append=True)

    return 0
