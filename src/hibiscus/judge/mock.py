"""A deterministic, offline judge adapter for demos and tests."""

from __future__ import annotations

from ..hashing import sha256_hex
from .base import JudgeAdapter, JudgeVerdict


class MockJudge(JudgeAdapter):
    """Picks a winner via a stable hash of each text plus the question.

    No network access, fully reproducible. Useful for exercising the
    Hibiscus pipeline end to end without an API key — not a substitute
    for a real judge's taste. Note that it compares content symmetrically,
    so it shows no position bias; that is a property of the mock, not
    evidence about real judges.

    ``tie_rate`` makes a deterministic fraction of comparisons come back
    as ties, so the tie-handling path can be exercised in tests.
    """

    def __init__(self, *, tie_rate: float = 0.0):
        if not 0.0 <= tie_rate <= 1.0:
            raise ValueError(f"tie_rate must be in [0, 1], got {tie_rate}")
        self.tie_rate = tie_rate

    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        if self.tie_rate:
            # Order-independent draw, so a tie holds under position swap.
            pair_key = "|".join(sorted([text_a, text_b])) + "|" + question
            draw = int(sha256_hex(pair_key)[:8], 16) / 0xFFFFFFFF
            if draw < self.tie_rate:
                return JudgeVerdict(winner="tie", raw_response="mock:tie")

        digest_a = sha256_hex(text_a + "|" + question)
        digest_b = sha256_hex(text_b + "|" + question)
        winner = "a" if digest_a < digest_b else "b"
        return JudgeVerdict(winner=winner, raw_response=f"mock:{winner}")
