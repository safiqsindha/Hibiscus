"""Mechanical, deterministic degradation transforms for the synthetic ladder.

Every transform is content-blind (regex/split based), so applying it to any
of the 20 source texts requires no judgment calls and produces the same
output every run given the same seed.
"""

from __future__ import annotations

import random
import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s for s in SENTENCE_SPLIT.split(text.strip()) if s]


def truncate(text: str, fraction: float = 0.4) -> str:
    """Cut to ~`fraction` of the original length, on a sentence boundary."""
    sentences = split_sentences(text)
    target_words = int(len(text.split()) * fraction)
    kept: list[str] = []
    word_count = 0
    for s in sentences:
        kept.append(s)
        word_count += len(s.split())
        if word_count >= target_words:
            break
    if len(kept) == len(sentences):
        kept = kept[: max(1, len(kept) // 2)]
    return " ".join(kept)


def shuffle(text: str, seed: int) -> str:
    """Randomize sentence order (deterministic given seed)."""
    sentences = split_sentences(text)
    rng = random.Random(seed)
    shuffled = sentences[:]
    # Guarantee an actual reordering for len>=2 by retrying if rng returns identity.
    attempts = 0
    while True:
        rng.shuffle(shuffled)
        attempts += 1
        if shuffled != sentences or len(sentences) < 2 or attempts > 10:
            break
    return " ".join(shuffled)


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def pad(text: str) -> str:
    """Restate each sentence with filler wording. No new facts, ~2x length."""
    sentences = split_sentences(text)
    restated = []
    for s in sentences:
        restated.append(s)
        restated.append(f"In other words, {_lower_first(s)}")
    return " ".join(restated)


_VAGUE_NUMBERS = [
    "some",
    "several",
    "a number of",
    "many",
    "a handful of",
    "a certain number of",
]

_VAGUE_ENTITIES = [
    "a certain person",
    "someone",
    "a particular place",
    "a certain location",
    "an institution",
]

# Matches numerals -- proper thousands-grouped ("53,000"), bare 4-digit
# (years, mostly), decimals, or plain digit runs -- in that priority order
# so a trailing sentence comma like "1890, four" is never swallowed as a
# thousands separator. The space+unit is one atomic optional group so a
# missing unit never leaves a stray consumed space behind.
_NUMBER_RE = re.compile(
    r"\b(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4}s?\b|\d+\.\d+|\d+)"
    r"(?:\s?(?:percent|%|meters?|kilometers?|kilograms?|tons?|"
    r"dollars?|degrees?|years?|kg|km))?\b"
)

# Runs of 2+ consecutive Title-Case words: crude proper-noun detector. Also
# swallows a leading indefinite article, if any, since the replacement
# supplies its own ("a New Zealand coach" -> "someone", not "a someone").
_NAME_RE = re.compile(r"\b(?:an?\s+)?[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3}\b")


def strip_specifics(text: str, seed: int) -> str:
    """Replace numbers, dates, and proper-noun-like phrases with vague words."""
    rng = random.Random(seed)

    def repl_number(_match: re.Match) -> str:
        return rng.choice(_VAGUE_NUMBERS)

    def repl_name(_match: re.Match) -> str:
        return rng.choice(_VAGUE_ENTITIES)

    stripped = _NUMBER_RE.sub(repl_number, text)
    stripped = _NAME_RE.sub(repl_name, stripped)
    return stripped


DEGRADATION_CLASSES = ("truncated", "shuffled", "padded", "stripped")


def degrade(text: str, kind: str, seed: int) -> str:
    if kind == "truncated":
        return truncate(text)
    if kind == "shuffled":
        return shuffle(text, seed)
    if kind == "padded":
        return pad(text)
    if kind == "stripped":
        return strip_specifics(text, seed)
    raise ValueError(f"unknown degradation kind: {kind!r}")
