"""``hibiscus`` CLI entry point: dispatches to rate/pool/compare/score/report."""

from __future__ import annotations

import argparse
import sys

from . import (
    calibrate_cmd,
    compare_cmd,
    pool_cmd,
    rank_cmd,
    rate,
    report_cmd,
    saturate_cmd,
    score_cmd,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hibiscus", description="Pairwise evaluation against a hand-rated reference pool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    rate.register(subparsers)
    pool_cmd.register(subparsers)
    compare_cmd.register(subparsers)
    score_cmd.register(subparsers)
    calibrate_cmd.register(subparsers)
    saturate_cmd.register(subparsers)
    report_cmd.register(subparsers)
    rank_cmd.register(subparsers)
    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
