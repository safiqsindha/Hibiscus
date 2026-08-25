"""The domain-agnostic unit Hibiscus judges: an id, some text, and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Artifact:
    """A text blob to be rated or compared.

    Deliberately minimal — Hibiscus does not assume a document type.
    ``metadata`` is free-form and is never sent to a judge.
    """

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "metadata": self.metadata}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        return cls(id=data["id"], text=data["text"], metadata=data.get("metadata", {}))
