"""The judge adapter interface every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Winner = Literal["a", "b", "tie"]


@dataclass(frozen=True)
class JudgeVerdict:
    """The outcome of one pairwise judge call.

    ``winner`` may be ``"tie"`` when the judge finds the two texts
    genuinely indistinguishable. A tie is not half a win: it is excluded
    from the win-rate denominator rather than being coin-flipped into
    the score as noise.
    """

    winner: Winner
    raw_response: str

    @property
    def is_tie(self) -> bool:
        return self.winner == "tie"


class JudgeAdapter(ABC):
    """A pairwise judge: given two texts and a question, picks a winner.

    Adapters receive only whitelisted fields (see
    :mod:`hibiscus.judge.payload`) — never artifact ids, tier labels, or
    pool metadata. Implementations should not reach outside ``compare``'s
    arguments for anything about the artifacts being judged.
    """

    @abstractmethod
    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        """Return which of ``text_a``/``text_b`` better answers ``question``.

        May return a ``"tie"`` verdict, but should do so sparingly —
        judges markedly over-use ties when invited to.
        """
        raise NotImplementedError
