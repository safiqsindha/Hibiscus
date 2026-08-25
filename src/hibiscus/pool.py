"""Storage and query for a hand-rated reference pool.

A pool is a UTF-8 JSONL file, one rated artifact per line. Multiple named
pools are just multiple files — e.g. ``pools/meeting-notes.jsonl`` and
``pools/status-reports.jsonl`` — there is no separate registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .artifact import Artifact
from .tiers import Tier, parse_tier


@dataclass(frozen=True)
class RatedArtifact:
    """An artifact plus its hand-assigned tier and optional note."""

    id: str
    text: str
    tier: Tier
    note: "str | None" = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rated_at: "str | None" = None

    @property
    def artifact(self) -> Artifact:
        return Artifact(id=self.id, text=self.text, metadata=self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "tier": self.tier.value,
            "note": self.note,
            "metadata": self.metadata,
            "rated_at": self.rated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RatedArtifact":
        return cls(
            id=data["id"],
            text=data["text"],
            tier=parse_tier(data["tier"]),
            note=data.get("note"),
            metadata=data.get("metadata", {}),
            rated_at=data.get("rated_at"),
        )


class Pool:
    """A rated artifact pool backed by a UTF-8 JSONL file.

    The file is the source of truth. Every mutating call appends to disk
    immediately (explicit UTF-8, ``ensure_ascii=False``), so a Pool is
    always resumable and safe to reopen mid-session.
    """

    def __init__(self, path: "str | Path"):
        self.path = Path(path)
        self._by_id: dict[str, RatedArtifact] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rated = RatedArtifact.from_dict(json.loads(line))
                self._by_id[rated.id] = rated

    def __contains__(self, artifact_id: str) -> bool:
        return artifact_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self) -> Iterator[RatedArtifact]:
        return iter(self.list())

    def get(self, artifact_id: str) -> "RatedArtifact | None":
        return self._by_id.get(artifact_id)

    def add(self, rated: RatedArtifact, *, overwrite: bool = False) -> None:
        """Append a rating. Raises unless ``overwrite`` if already rated."""
        if rated.id in self._by_id and not overwrite:
            raise ValueError(
                f"artifact {rated.id!r} is already rated; pass overwrite=True to replace"
            )
        self._by_id[rated.id] = rated
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rated.to_dict(), ensure_ascii=False) + "\n")

    def filter_by_tier(self, tier: "Tier | str") -> list[RatedArtifact]:
        tier = parse_tier(tier)
        return [r for r in self._by_id.values() if r.tier is tier]

    def list(self, tier: "Tier | str | None" = None) -> list[RatedArtifact]:
        items = self.filter_by_tier(tier) if tier is not None else list(self._by_id.values())
        return sorted(items, key=lambda r: r.id)

    def export_jsonl(self, path: "str | Path") -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for rated in self.list():
                fh.write(json.dumps(rated.to_dict(), ensure_ascii=False) + "\n")

    def import_jsonl(self, path: "str | Path", *, overwrite: bool = False) -> int:
        count = 0
        with Path(path).open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                self.add(RatedArtifact.from_dict(json.loads(line)), overwrite=overwrite)
                count += 1
        return count

    def rewrite(self) -> None:
        """Compact the backing file, dropping stale rows left by an overwrite."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for rated in self.list():
                fh.write(json.dumps(rated.to_dict(), ensure_ascii=False) + "\n")
        tmp.replace(self.path)
