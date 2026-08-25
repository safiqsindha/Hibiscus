"""The ``hibiscus rate`` command: fast, resumable human rating.

Presents one artifact at a time, accepts a single keystroke for
love/okay/nope (plus skip/quit), and never re-presents an artifact
that's already in the pool. Optimized for getting a human through
hundreds of items in an hour: one keystroke rates an item and advances
immediately — no Enter, no confirmation prompt.

Notes are opt-in, because prompting for one on every item would double
the keystrokes in the common case. Shift the rating key (``L``/``O``/``N``)
to rate *and* be asked for a note; the lowercase key rates silently.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, TextIO

from ..artifact import Artifact
from ..pool import Pool, RatedArtifact
from ..tiers import Tier

KEY_TO_TIER = {"l": Tier.LOVE, "o": Tier.OKAY, "n": Tier.NOPE}
QUIT_KEYS = {"q"}
SKIP_KEYS = {"s"}

PROMPT = "(l)ove  (o)kay  (n)ope  (s)kip  (q)uit  [SHIFT+rating to add a note] > "


def load_artifacts(path: "str | Path") -> list[Artifact]:
    """Read candidate artifacts to rate from a UTF-8 JSONL file."""
    artifacts = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            artifacts.append(Artifact.from_dict(json.loads(line)))
    return artifacts


def default_reader() -> Callable[[], str]:
    """Return a function that reads one keystroke without waiting for Enter.

    Falls back to line-buffered reads when stdin isn't a real terminal
    (piped input, non-interactive shells) so the session still works
    there — just without single-keystroke speed.

    Case is preserved: a shifted rating key is what asks for a note.
    """
    if not sys.stdin.isatty():

        def _line_reader() -> str:
            line = sys.stdin.readline()
            if not line:
                return "q"
            return line.strip()[:1] or "\n"

        return _line_reader

    import termios
    import tty

    def _tty_reader() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        # Raw mode swallows the usual signal handling, so translate the
        # interrupt byte into the same clean exit as pressing "q".
        if ch == "\x03":
            return "q"
        return ch

    return _tty_reader


def run_rate_session(
    artifacts: Iterable[Artifact],
    pool: Pool,
    *,
    read_key: Callable[[], str],
    read_note: "Callable[[], str] | None" = None,
    out: TextIO = sys.stdout,
    now: "Callable[[], str] | None" = None,
) -> None:
    """Run one rating session over ``artifacts``, appending ratings to ``pool``.

    Already-rated ids are skipped up front, and repeated ids within one
    artifact list are collapsed, so calling this again with the same (or
    a superset) artifact list resumes cleanly and never re-presents a
    rated item. ``read_key``/``read_note`` are injectable for testing
    without a real terminal.

    A lowercase rating key records the rating and moves on immediately.
    An uppercase one records it and asks for a note first.
    """
    read_note = read_note or (lambda: input("note (Enter to skip): "))
    stamp = now or (lambda: datetime.now(timezone.utc).isoformat())

    pending: list[Artifact] = []
    queued: set[str] = set()
    for artifact in artifacts:
        if artifact.id in pool or artifact.id in queued:
            continue
        queued.add(artifact.id)
        pending.append(artifact)
    total = len(pending)
    for i, artifact in enumerate(pending, start=1):
        out.write(f"\n[{i}/{total}] {artifact.id}\n")
        out.write(artifact.text + "\n")
        out.write(PROMPT)
        out.flush()

        while True:
            key = read_key()
            folded = key.lower()
            if folded in QUIT_KEYS:
                out.write("\nstopped — resume anytime, already-rated items won't reappear\n")
                return
            if folded in SKIP_KEYS:
                out.write("\nskipped\n")
                break
            if folded in KEY_TO_TIER:
                tier = KEY_TO_TIER[folded]
                note = None
                if key.isupper():
                    try:
                        note = read_note().strip() or None
                    except EOFError:
                        note = None
                pool.add(
                    RatedArtifact(
                        id=artifact.id,
                        text=artifact.text,
                        tier=tier,
                        note=note,
                        metadata=artifact.metadata,
                        rated_at=stamp(),
                    )
                )
                out.write(f"-> {tier.value}\n")
                break
            out.write(PROMPT)

    out.write(f"\ndone — {len(pool)} rated total\n")


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "rate", help="Rate artifacts into love/okay/nope tiers, one at a time."
    )
    parser.add_argument("--artifacts", required=True, help="JSONL file of artifacts to rate")
    parser.add_argument("--pool", required=True, help="Pool JSONL file to read/append ratings to")
    parser.set_defaults(handler=_handle)


def _handle(args) -> int:
    artifacts = load_artifacts(args.artifacts)
    pool = Pool(args.pool)
    run_rate_session(artifacts, pool, read_key=default_reader())
    return 0
