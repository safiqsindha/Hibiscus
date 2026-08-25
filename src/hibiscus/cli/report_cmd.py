"""The ``hibiscus report`` command: the dimension-correlation diagnostic."""

from __future__ import annotations

import json

from ..report import build_correlation_report, load_rows


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "report",
        help="Compute a dimension correlation report and flag redundant dimensions.",
    )
    parser.add_argument("--data", required=True, help="CSV or JSONL of {artifact_id, dimension, score}")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--out", help="Write the full report as JSON to this path")
    parser.set_defaults(handler=_handle)


def _handle(args) -> int:
    rows = load_rows(args.data)
    report = build_correlation_report(rows, threshold=args.threshold)

    print(f"dimensions: {', '.join(report.dimensions)}")
    print("\t".join([""] + report.dimensions))
    for dim_a in report.dimensions:
        line = [dim_a] + [f"{report.matrix[dim_a][dim_b]:.2f}" for dim_b in report.dimensions]
        print("\t".join(line))

    if report.redundant_pairs:
        print(f"\nredundant pairs (>= {args.threshold}):")
        for a, b, corr in report.redundant_pairs:
            print(f"  {a} <-> {b}: {corr:.3f}")
    else:
        print("\nno redundant dimension pairs found")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)

    return 0
