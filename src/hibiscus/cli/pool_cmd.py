"""The ``hibiscus pool`` command: add, list, export, import."""

from __future__ import annotations

import sys
from pathlib import Path

from ..pool import Pool, RatedArtifact
from ..tiers import parse_tier


def register(subparsers) -> None:
    parser = subparsers.add_parser("pool", help="Inspect and manage a rated pool.")
    sub = parser.add_subparsers(dest="pool_command", required=True)

    add_p = sub.add_parser("add", help="Add one rated artifact to the pool.")
    add_p.add_argument("--pool", required=True)
    add_p.add_argument("--id", required=True)
    add_p.add_argument("--text", help="Artifact text (mutually exclusive with --text-file)")
    add_p.add_argument("--text-file", help="Read artifact text from this UTF-8 file")
    add_p.add_argument("--tier", required=True, choices=["love", "okay", "nope"])
    add_p.add_argument("--note")
    add_p.set_defaults(handler=_handle_add)

    list_p = sub.add_parser("list", help="List rated artifacts.")
    list_p.add_argument("--pool", required=True)
    list_p.add_argument("--tier", choices=["love", "okay", "nope"])
    list_p.set_defaults(handler=_handle_list)

    export_p = sub.add_parser("export", help="Export the pool to a JSONL file.")
    export_p.add_argument("--pool", required=True)
    export_p.add_argument("--out", required=True)
    export_p.set_defaults(handler=_handle_export)

    import_p = sub.add_parser("import", help="Import rated artifacts from a JSONL file.")
    import_p.add_argument("--pool", required=True)
    import_p.add_argument("--src", required=True)
    import_p.add_argument("--overwrite", action="store_true")
    import_p.set_defaults(handler=_handle_import)


def _handle_add(args) -> int:
    if bool(args.text) == bool(args.text_file):
        print("error: pass exactly one of --text or --text-file", file=sys.stderr)
        return 2
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text

    pool = Pool(args.pool)
    pool.add(RatedArtifact(id=args.id, text=text, tier=parse_tier(args.tier), note=args.note))
    print(f"added {args.id!r} as {args.tier}")
    return 0


def _handle_list(args) -> int:
    pool = Pool(args.pool)
    tier = parse_tier(args.tier) if args.tier else None
    for rated in pool.list(tier=tier):
        note = f" — {rated.note}" if rated.note else ""
        print(f"{rated.id}\t{rated.tier.value}{note}")
    return 0


def _handle_export(args) -> int:
    pool = Pool(args.pool)
    pool.export_jsonl(args.out)
    print(f"exported {len(pool)} artifacts to {args.out}")
    return 0


def _handle_import(args) -> int:
    pool = Pool(args.pool)
    count = pool.import_jsonl(args.src, overwrite=args.overwrite)
    print(f"imported {count} artifacts into {args.pool}")
    return 0
