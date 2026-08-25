"""A deterministic, offline judge adapter for demos and tests."""

from __future__ import annotations

from ..hashing import sha256_hex
from .base import JudgeAdapter, JudgeVerdict


class MockJudge(JudgeAdapter):
    """Picks a winner via a stable hash of each text plus the question.

    No network access, fully reproducible. Useful for exercising the
    Hibiscus pipeline end to end without an API key — not a substitute
    for a real judge's taste.
    """

    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        digest_a = sha256_hex(text_a + "|" + question)
        digest_b = sha256_hex(text_b + "|" + question)
        winner = "a" if digest_a < digest_b else "b"
        return JudgeVerdict(winner=winner, raw_response=f"mock:{winner}")
