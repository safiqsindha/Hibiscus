"""Judge adapter backed by the Anthropic API.

The ``anthropic`` package is imported lazily inside ``__init__`` so that
importing :mod:`hibiscus` never requires it — only instantiating this
adapter does. Install the ``anthropic`` extra to use it:
``pip install hibiscus[anthropic]``.
"""

from __future__ import annotations

import os

from .base import JudgeAdapter, JudgeVerdict
from .payload import build_judge_payload

DEFAULT_MODEL = "claude-sonnet-5"


class AnthropicJudge(JudgeAdapter):
    """Pairwise judge that asks a Claude model to pick A or B.

    Keeps the comparison prompt short and opinionated on purpose: a long
    rubric in the system prompt measurably hurt judgment quality in the
    project this library is based on.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
        api_key: "str | None" = None,
        client: object = None,
    ):
        self.model = model
        self.temperature = temperature
        if client is not None:
            self._client = client
        else:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        payload = build_judge_payload(text_a, text_b, question)
        prompt = (
            f"{payload['question']}\n\n"
            f"Text A:\n{payload['text_a']}\n\n"
            f"Text B:\n{payload['text_b']}"
        )
        response = self._client.messages.create(
            model=self.model,
            max_tokens=8,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return JudgeVerdict(winner=_parse_winner(raw), raw_response=raw)


def _parse_winner(raw: str) -> "str":
    cleaned = raw.strip().upper()
    # Check TIE first: it also starts with "T", but "A"/"B" prefixes would
    # otherwise never collide with it.
    if cleaned.startswith("TIE") or cleaned == "T":
        return "tie"
    if cleaned.startswith("A"):
        return "a"
    if cleaned.startswith("B"):
        return "b"
    raise ValueError(f"could not parse judge response as A/B/TIE: {raw!r}")
