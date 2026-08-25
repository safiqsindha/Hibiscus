"""Whitelisted judge payload construction.

The judge receives only the candidate text, the reference text, and a
short comparison question — never an artifact id, tier label, or pool
metadata. This is enforced by construction (the payload builder only ever
assembles the three allowed fields) and re-checked explicitly so a future
edit that widens the payload fails loudly instead of silently leaking
fields to the judge.
"""

from __future__ import annotations

from typing import Any

ALLOWED_PAYLOAD_KEYS = frozenset({"text_a", "text_b", "question"})

DEFAULT_QUESTION = (
    "Below are two texts, A and B. Which one is better? "
    "Answer with only the single letter A or B."
)


def validate_payload(payload: dict[str, Any]) -> None:
    """Assert that ``payload`` contains only whitelisted keys.

    Raises ``AssertionError`` rather than a plain exception so a
    disallowed field fails the build, not the judge call.
    """
    extra = set(payload.keys()) - ALLOWED_PAYLOAD_KEYS
    assert not extra, f"judge payload contains disallowed keys: {sorted(extra)}"


def build_judge_payload(
    text_a: str, text_b: str, question: "str | None" = None
) -> dict[str, Any]:
    """Assemble the payload sent to a judge adapter: text_a, text_b, question."""
    payload = {
        "text_a": text_a,
        "text_b": text_b,
        "question": question or DEFAULT_QUESTION,
    }
    validate_payload(payload)
    return payload
