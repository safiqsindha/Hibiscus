"""Persistent cache of judge verdicts, keyed for reproducible, free reruns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .judge.base import JudgeVerdict


@dataclass(frozen=True)
class CacheKey:
    """Identifies one judge call: candidate, reference, order, prompt, model."""

    candidate_hash: str
    reference_hash: str
    order: str
    prompt_hash: str
    model: str

    def as_str(self) -> str:
        return "|".join(
            [self.candidate_hash, self.reference_hash, self.order, self.prompt_hash, self.model]
        )


class JudgeCache:
    """A UTF-8 JSONL-backed cache of judge verdicts.

    A hit means an identical (candidate, reference, order, prompt, model)
    comparison never re-hits the judge — reruns are free and reproduce
    the original verdict exactly.
    """

    def __init__(self, path: "str | Path"):
        self.path = Path(path)
        self._store: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                self._store[row["key"]] = row

    def get(self, key: CacheKey) -> "JudgeVerdict | None":
        row = self._store.get(key.as_str())
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return JudgeVerdict(winner=row["winner"], raw_response=row["raw_response"])

    def put(self, key: CacheKey, verdict: JudgeVerdict) -> None:
        row = {
            "key": key.as_str(),
            "candidate_hash": key.candidate_hash,
            "reference_hash": key.reference_hash,
            "order": key.order,
            "prompt_hash": key.prompt_hash,
            "model": key.model,
            "winner": verdict.winner,
            "raw_response": verdict.raw_response,
        }
        self._store[key.as_str()] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
