"""The ``hibiscus compare`` command: run pairwise comparisons against the pool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..artifact import Artifact
from ..cache import JudgeCache
from ..compare import order_disagreement_rate, run_comparisons, save_comparisons
from ..pairs import resolve_pairs, summarize_pairs
from ..pool import Pool


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "compare", help="Run pairwise comparisons against the reference pool."
    )
    parser.add_argument("--candidates", required=True, help="JSONL file of candidate artifacts")
    parser.add_argument("--pool", required=True)
    parser.add_argument("--tier", default="love")
    parser.add_argument("-k", type=int, default=2)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--judge", choices=["mock", "anthropic"], default="mock")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--question", help="Override the default comparison question")
    parser.add_argument("--dimension", default="overall")
    parser.add_argument("--cache", help="Path to a judge response cache JSONL file")
    parser.add_argument("--out", required=True, help="Where to append comparison records")
    parser.set_defaults(handler=_handle)


def _load_candidates(path: str) -> list[Artifact]:
    artifacts = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            artifacts.append(Artifact.from_dict(json.loads(line)))
    return artifacts


def _build_judge(name: str, model: str):
    if name == "mock":
        from ..judge.mock import MockJudge

        return MockJudge()
    from ..judge.anthropic_adapter import AnthropicJudge

    return AnthropicJudge(model=model)


def _handle(args) -> int:
    candidates = _load_candidates(args.candidates)
    pool = Pool(args.pool)
    judge = _build_judge(args.judge, args.model)
    cache = JudgeCache(args.cache) if args.cache else None

    all_records = []
    for candidate in candidates:
        records = run_comparisons(
            candidate,
            pool,
            judge,
            tier=args.tier,
            k=args.k,
            seed=args.seed,
            question=args.question,
            model=args.model,
            cache=cache,
            dimension=args.dimension,
        )
        all_records.extend(records)

    save_comparisons(args.out, all_records, append=True)

    disagreement = order_disagreement_rate(all_records)
    hits = sum(1 for r in all_records if r.cache_hit)
    summary = summarize_pairs(resolve_pairs(all_records))
    print(
        f"ran {len(all_records)} judge calls over {summary.total} pairs across "
        f"{len(candidates)} candidate(s); {hits} served from cache"
    )
    print(
        f"resolved: {summary.wins} win, {summary.losses} loss, {summary.ties} tie "
        f"({summary.judge_ties} judge, {summary.disagreement_ties} order-disagreement); "
        f"order-disagreement rate = {disagreement:.2%}"
    )
    if disagreement > 0.3:
        print(
            "warning: high order-disagreement rate — judge may be tracking "
            "position, not content",
            file=sys.stderr,
        )
    return 0
